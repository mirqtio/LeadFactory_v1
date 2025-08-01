"""
SendGrid API Client

Handles email sending through SendGrid via Gateway with proper error handling
and response tracking.

Acceptance Criteria:
- SendGrid API integration ✓
- Email building works ✓
- Categories added ✓
- Custom args included ✓
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from core.config import get_settings
from core.exceptions import ExternalAPIError, RateLimitError
from d0_gateway.facade import get_gateway_facade

logger = logging.getLogger(__name__)


@dataclass
class SendGridResponse:
    """SendGrid API response data"""

    success: bool
    message_id: str | None = None
    batch_id: str | None = None
    error_message: str | None = None
    status_code: int | None = None
    headers: dict[str, str] | None = None
    rate_limit_remaining: int | None = None
    rate_limit_reset: int | None = None


@dataclass
class EmailData:
    """Email data structure for SendGrid"""

    to_email: str
    from_email: str
    subject: str
    to_name: str | None = None
    from_name: str | None = None
    html_content: str | None = None
    text_content: str | None = None
    categories: list[str] | None = None
    custom_args: dict[str, Any] | None = None
    reply_to_email: str | None = None
    reply_to_name: str | None = None
    batch_id: str | None = None


class SendGridClient:
    """
    SendGrid API client for email delivery

    Handles authentication, rate limiting, error handling,
    and proper integration with SendGrid's v3 API.
    """

    def __init__(self, api_key: str | None = None, sandbox_mode: bool = False):
        """Initialize SendGrid client"""
        self.config = get_settings()
        self.sandbox_mode = sandbox_mode or os.getenv("SENDGRID_SANDBOX_MODE", "false").lower() == "true"

        # Get gateway facade
        self.gateway = get_gateway_facade()

        # Default settings
        self.default_from_email = os.getenv("SENDGRID_FROM_EMAIL", "noreply@leadfactory.com")
        self.default_from_name = os.getenv("SENDGRID_FROM_NAME", "LeadFactory")
        self.default_categories = ["leadfactory", "automated"]

        logger.info(f"SendGrid client initialized (sandbox: {self.sandbox_mode})")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""

    async def send_email(self, email_data: EmailData) -> SendGridResponse:
        """
        Send email through SendGrid API

        Args:
            email_data: Email data to send

        Returns:
            SendGridResponse with send results
        """
        # Prepare tracking settings
        tracking_settings = {
            "click_tracking": {"enable": True, "enable_text": False},
            "open_tracking": {"enable": True},
            "subscription_tracking": {"enable": False},  # We'll handle unsubscribes ourselves
        }

        # Add sandbox mode to tracking settings
        if self.sandbox_mode:
            tracking_settings["sandbox_mode"] = {"enable": True}

        try:
            # Use gateway facade to send email
            result = await self.gateway.send_email(
                to_email=email_data.to_email,
                from_email=email_data.from_email or self.default_from_email,
                from_name=email_data.from_name or self.default_from_name,
                subject=email_data.subject,
                html_content=email_data.html_content or "",
                text_content=email_data.text_content,
                reply_to=email_data.reply_to_email,
                custom_args=self._prepare_custom_args(email_data),
                tracking_settings=tracking_settings,
            )

            # Gateway returns successful response
            logger.info(f"Email sent successfully to {email_data.to_email}")

            return SendGridResponse(
                success=True,
                message_id=result.get("message_id"),
                batch_id=email_data.batch_id,
                status_code=202,  # SendGrid success code
                headers=result.get("headers", {}),
            )

        except RateLimitError as e:
            logger.warning(f"SendGrid rate limit exceeded: {e}")
            raise

        except ExternalAPIError as e:
            logger.error(f"SendGrid API error: {e}")
            return SendGridResponse(
                success=False,
                error_message=str(e),
                status_code=e.status_code if hasattr(e, "status_code") else None,
            )

        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return SendGridResponse(success=False, error_message=f"Unexpected error: {str(e)}")

    def _prepare_custom_args(self, email_data: EmailData) -> dict[str, str]:
        """
        Prepare custom arguments for email tracking

        Args:
            email_data: Email data containing custom args

        Returns:
            Dict of custom arguments as strings
        """
        custom_args = {}

        # Add provided custom args
        if email_data.custom_args:
            custom_args.update({k: str(v) for k, v in email_data.custom_args.items()})

        # Add categories as custom args
        categories = email_data.categories or []
        if self.default_categories:
            categories.extend(self.default_categories)

        # Remove duplicates and limit to 10
        categories = list(set(categories))[:10]
        if categories:
            custom_args["categories"] = ",".join(categories)

        # Add batch ID if provided
        if email_data.batch_id:
            custom_args["batch_id"] = email_data.batch_id

        return custom_args

    async def send_batch_emails(self, emails: list[EmailData], batch_id: str | None = None) -> list[SendGridResponse]:
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
                results.append(SendGridResponse(success=False, error_message=str(response)))
            else:
                results.append(response)

        return results

    async def validate_api_key(self) -> bool:
        """
        Validate SendGrid API key by making a test request

        Returns:
            True if API key is valid, False otherwise
        """
        try:
            # Try to get email stats for today - minimal API call
            from datetime import date

            await self.gateway.get_email_stats(start_date=date.today().isoformat(), end_date=date.today().isoformat())
            return True
        except Exception as e:
            logger.error(f"Error validating SendGrid API key: {e}")
            return False

    async def get_account_details(self) -> dict[str, Any] | None:
        """
        Get SendGrid account details

        Returns:
            Account details dict or None if error
        """
        try:
            # Get recent email stats as a proxy for account details
            from datetime import date, timedelta

            stats = await self.gateway.get_email_stats(
                start_date=(date.today() - timedelta(days=7)).isoformat(),
                end_date=date.today().isoformat(),
                aggregated_by="week",
            )

            # Return basic account info derived from stats
            return {
                "active": True,
                "stats_available": bool(stats),
                "recent_stats": stats,
            }
        except Exception as e:
            logger.error(f"Error getting account details: {e}")
            return None


# Utility functions


async def send_single_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
    to_name: str | None = None,
    from_email: str | None = None,
    from_name: str | None = None,
    categories: list[str] | None = None,
    custom_args: dict[str, Any] | None = None,
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
        custom_args=custom_args,
    )

    async with SendGridClient() as client:
        return await client.send_email(email_data)


def create_email_data(
    to_email: str,
    from_email: str,
    subject: str,
    html_content: str,
    text_content: str | None = None,
    **kwargs,
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
        **kwargs,
    )
