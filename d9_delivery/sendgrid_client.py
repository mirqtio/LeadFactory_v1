"""
SendGrid API Client

Handles email sending through SendGrid with proper error handling,
rate limiting, and response tracking.

Acceptance Criteria:
- SendGrid API integration ✓
- Email building works ✓
- Categories added ✓
- Custom args included ✓
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timezone
import asyncio
import aiohttp
from dataclasses import dataclass

from core.config import get_settings
from core.exceptions import ExternalAPIError, RateLimitError, ConfigurationError


logger = logging.getLogger(__name__)


@dataclass
class SendGridResponse:
    """SendGrid API response data"""
    success: bool
    message_id: Optional[str] = None
    batch_id: Optional[str] = None
    error_message: Optional[str] = None
    status_code: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None


@dataclass
class EmailData:
    """Email data structure for SendGrid"""
    to_email: str
    from_email: str
    subject: str
    to_name: Optional[str] = None
    from_name: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    categories: Optional[List[str]] = None
    custom_args: Optional[Dict[str, Any]] = None
    reply_to_email: Optional[str] = None
    reply_to_name: Optional[str] = None
    batch_id: Optional[str] = None


class SendGridClient:
    """
    SendGrid API client for email delivery
    
    Handles authentication, rate limiting, error handling,
    and proper integration with SendGrid's v3 API.
    """
    
    def __init__(self, api_key: Optional[str] = None, sandbox_mode: bool = False):
        """Initialize SendGrid client"""
        self.config = get_settings()
        self.api_key = api_key or os.getenv('SENDGRID_API_KEY')
        self.sandbox_mode = sandbox_mode or os.getenv('SENDGRID_SANDBOX_MODE', 'false').lower() == 'true'
        
        if not self.api_key:
            raise ConfigurationError("SendGrid API key is required")
        
        self.base_url = "https://api.sendgrid.com/v3"
        self.session = None
        
        # Default settings
        self.default_from_email = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@leadfactory.com')
        self.default_from_name = os.getenv('SENDGRID_FROM_NAME', 'LeadFactory')
        self.default_categories = ['leadfactory', 'automated']
        
        # Rate limiting
        self.max_requests_per_second = 100  # SendGrid limit
        self.request_timestamps = []
        
        logger.info(f"SendGrid client initialized (sandbox: {self.sandbox_mode})")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _ensure_session(self):
        """Ensure aiohttp session is created"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'LeadFactory/1.0'
                }
            )
    
    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        now = datetime.now()
        
        # Remove old timestamps (older than 1 second)
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if (now - ts).total_seconds() < 1.0
        ]
        
        # Check if we're at the limit
        if len(self.request_timestamps) >= self.max_requests_per_second:
            sleep_time = 1.0 - (now - self.request_timestamps[0]).total_seconds()
            if sleep_time > 0:
                logger.warning(f"Rate limit approached, sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
        
        self.request_timestamps.append(now)
    
    async def send_email(self, email_data: EmailData) -> SendGridResponse:
        """
        Send email through SendGrid API
        
        Args:
            email_data: Email data to send
            
        Returns:
            SendGridResponse with send results
        """
        await self._ensure_session()
        await self._check_rate_limit()
        
        # Build SendGrid payload
        payload = self._build_email_payload(email_data)
        
        try:
            async with self.session.post(
                f"{self.base_url}/mail/send",
                json=payload
            ) as response:
                
                # Extract rate limit headers
                rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
                rate_limit_reset = response.headers.get('X-RateLimit-Reset')
                
                if response.status == 202:
                    # Success - SendGrid returns 202 for accepted emails
                    message_id = response.headers.get('X-Message-Id')
                    
                    logger.info(f"Email sent successfully to {email_data.to_email}, message_id: {message_id}")
                    
                    return SendGridResponse(
                        success=True,
                        message_id=message_id,
                        batch_id=email_data.batch_id,
                        status_code=response.status,
                        headers=dict(response.headers),
                        rate_limit_remaining=int(rate_limit_remaining) if rate_limit_remaining else None,
                        rate_limit_reset=int(rate_limit_reset) if rate_limit_reset else None
                    )
                
                elif response.status == 429:
                    # Rate limit exceeded
                    error_text = await response.text()
                    logger.warning(f"SendGrid rate limit exceeded: {error_text}")
                    
                    raise RateLimitError(
                        provider="SendGrid",
                        retry_after=int(response.headers.get('Retry-After', 60))
                    )
                
                else:
                    # Error response
                    error_text = await response.text()
                    try:
                        error_data = json.loads(error_text)
                        error_message = error_data.get('errors', [{}])[0].get('message', error_text)
                    except:
                        error_message = error_text
                    
                    logger.error(f"SendGrid API error {response.status}: {error_message}")
                    
                    return SendGridResponse(
                        success=False,
                        error_message=error_message,
                        status_code=response.status,
                        headers=dict(response.headers),
                        rate_limit_remaining=int(rate_limit_remaining) if rate_limit_remaining else None,
                        rate_limit_reset=int(rate_limit_reset) if rate_limit_reset else None
                    )
        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error sending email: {e}")
            return SendGridResponse(
                success=False,
                error_message=f"HTTP client error: {str(e)}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return SendGridResponse(
                success=False,
                error_message=f"Unexpected error: {str(e)}"
            )
    
    def _build_email_payload(self, email_data: EmailData) -> Dict[str, Any]:
        """
        Build SendGrid API payload from email data
        
        Args:
            email_data: Email data to convert
            
        Returns:
            SendGrid API payload dict
        """
        # Build personalizations (recipients)
        personalizations = [{
            "to": [{
                "email": email_data.to_email,
                "name": email_data.to_name or email_data.to_email
            }]
        }]
        
        # Add custom args to personalization if provided
        if email_data.custom_args:
            personalizations[0]["custom_args"] = {
                k: str(v) for k, v in email_data.custom_args.items()
            }
        
        # Build from field
        from_field = {
            "email": email_data.from_email or self.default_from_email,
            "name": email_data.from_name or self.default_from_name
        }
        
        # Build content array
        content = []
        if email_data.text_content:
            content.append({
                "type": "text/plain",
                "value": email_data.text_content
            })
        
        if email_data.html_content:
            content.append({
                "type": "text/html", 
                "value": email_data.html_content
            })
        
        # If no content provided, add minimal text
        if not content:
            content.append({
                "type": "text/plain",
                "value": "This email was sent from LeadFactory."
            })
        
        # Build main payload
        payload = {
            "personalizations": personalizations,
            "from": from_field,
            "subject": email_data.subject,
            "content": content
        }
        
        # Add reply-to if provided
        if email_data.reply_to_email:
            payload["reply_to"] = {
                "email": email_data.reply_to_email,
                "name": email_data.reply_to_name or email_data.reply_to_email
            }
        
        # Add categories
        categories = email_data.categories or []
        if self.default_categories:
            categories.extend(self.default_categories)
        
        # Remove duplicates and limit to 10 (SendGrid limit)
        categories = list(set(categories))[:10]
        if categories:
            payload["categories"] = categories
        
        # Add batch ID if provided
        if email_data.batch_id:
            payload["batch_id"] = email_data.batch_id
        
        # Add mail settings
        payload["mail_settings"] = {
            "sandbox_mode": {
                "enable": self.sandbox_mode
            }
        }
        
        # Add tracking settings
        payload["tracking_settings"] = {
            "click_tracking": {
                "enable": True,
                "enable_text": False
            },
            "open_tracking": {
                "enable": True
            },
            "subscription_tracking": {
                "enable": False  # We'll handle unsubscribes ourselves
            }
        }
        
        return payload
    
    async def send_batch_emails(self, emails: List[EmailData], batch_id: Optional[str] = None) -> List[SendGridResponse]:
        """
        Send multiple emails as a batch
        
        Args:
            emails: List of email data to send
            batch_id: Optional batch ID for tracking
            
        Returns:
            List of SendGridResponse objects
        """
        if batch_id:
            for email in emails:
                email.batch_id = batch_id
        
        # Send emails concurrently with rate limiting
        semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        
        async def send_single(email_data: EmailData) -> SendGridResponse:
            async with semaphore:
                return await self.send_email(email_data)
        
        tasks = [send_single(email) for email in emails]
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed responses
        results = []
        for i, response in enumerate(responses):
            if isinstance(response, Exception):
                logger.error(f"Batch email {i} failed: {response}")
                results.append(SendGridResponse(
                    success=False,
                    error_message=str(response)
                ))
            else:
                results.append(response)
        
        return results
    
    async def validate_api_key(self) -> bool:
        """
        Validate SendGrid API key by making a test request
        
        Returns:
            True if API key is valid, False otherwise
        """
        await self._ensure_session()
        
        try:
            async with self.session.get(f"{self.base_url}/user/profile") as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Error validating SendGrid API key: {e}")
            return False
    
    async def get_account_details(self) -> Optional[Dict[str, Any]]:
        """
        Get SendGrid account details
        
        Returns:
            Account details dict or None if error
        """
        await self._ensure_session()
        
        try:
            async with self.session.get(f"{self.base_url}/user/profile") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get account details: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting account details: {e}")
            return None
    
    def close(self):
        """Close the client session"""
        if self.session and not self.session.closed:
            # Schedule the close for the next event loop iteration
            asyncio.create_task(self.session.close())


# Utility functions

async def send_single_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    to_name: Optional[str] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    categories: Optional[List[str]] = None,
    custom_args: Optional[Dict[str, Any]] = None
) -> SendGridResponse:
    """
    Utility function to send a single email
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        html_content: HTML email content
        text_content: Plain text email content (optional)
        to_name: Recipient name (optional)
        from_email: Sender email (optional, uses default)
        from_name: Sender name (optional, uses default)
        categories: Email categories (optional)
        custom_args: Custom arguments (optional)
        
    Returns:
        SendGridResponse with send results
    """
    email_data = EmailData(
        to_email=to_email,
        to_name=to_name,
        from_email=from_email,
        from_name=from_name,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        categories=categories,
        custom_args=custom_args
    )
    
    async with SendGridClient() as client:
        return await client.send_email(email_data)


def create_email_data(
    to_email: str,
    from_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None,
    **kwargs
) -> EmailData:
    """
    Factory function to create EmailData objects
    
    Args:
        to_email: Recipient email
        from_email: Sender email
        subject: Email subject
        html_content: HTML content
        text_content: Text content (optional)
        **kwargs: Additional EmailData fields
        
    Returns:
        EmailData object
    """
    return EmailData(
        to_email=to_email,
        from_email=from_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
        **kwargs
    )