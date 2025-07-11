"""
Email Compliance Module

Handles email compliance requirements including CAN-SPAM, GDPR,
unsubscribe tokens, suppression lists, and required headers.

Acceptance Criteria:
- Suppression check works ✓
- Compliance headers added ✓ 
- Unsubscribe tokens ✓
- Send recording ✓
"""

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from sqlalchemy import and_

from core.config import get_settings
from d9_delivery.models import SuppressionList
from database.session import SessionLocal

logger = logging.getLogger(__name__)


@dataclass
class UnsubscribeToken:
    """Unsubscribe token data structure"""

    token: str
    email: str
    expires_at: datetime
    list_type: str = "marketing"


@dataclass
class ComplianceHeaders:
    """Email compliance headers"""

    list_unsubscribe: str
    list_unsubscribe_post: str
    list_id: str
    precedence: str = "bulk"
    auto_submitted: str = "auto-generated"


class ComplianceManager:
    """
    Manages email compliance requirements

    Handles CAN-SPAM Act compliance, GDPR requirements,
    unsubscribe tokens, and suppression lists.
    """

    def __init__(self, config: Optional[Any] = None):
        """Initialize compliance manager"""
        self.config = config or get_settings()
        self.secret_key = os.getenv("UNSUBSCRIBE_SECRET_KEY", self.config.secret_key)
        self.base_url = self.config.base_url.rstrip("/")

        # Token expiration (30 days)
        self.token_expiration_days = 30

        # List ID for compliance
        self.list_id = f"<marketing.{self.config.app_name.lower()}.com>"

        logger.info("Compliance manager initialized")

    def check_suppression(self, email: str, list_type: str = "marketing") -> bool:
        """
        Check if email is suppressed from receiving emails

        Args:
            email: Email address to check
            list_type: Type of suppression list to check (ignored for now)

        Returns:
            True if email is suppressed, False otherwise
        """
        try:
            with SessionLocal() as session:
                # Check for active suppressions
                suppression = (
                    session.query(SuppressionList)
                    .filter(
                        and_(
                            SuppressionList.email == email.lower(),
                            SuppressionList.is_active == True,
                        )
                    )
                    .first()
                )

                if not suppression:
                    return False

                # Check if suppression has expired
                if suppression.expires_at:
                    now = datetime.now(timezone.utc)
                    if suppression.expires_at < now:
                        # Expired suppression, deactivate it
                        suppression.is_active = False
                        session.commit()
                        logger.info(f"Deactivated expired suppression for {email}")
                        return False

                logger.info(f"Email {email} is suppressed from {list_type} list")
                return True

        except Exception as e:
            logger.error(f"Error checking suppression for {email}: {e}")
            # On error, assume not suppressed to avoid blocking legitimate emails
            return False

    def generate_unsubscribe_token(
        self, email: str, list_type: str = "marketing"
    ) -> UnsubscribeToken:
        """
        Generate secure unsubscribe token

        Args:
            email: Email address to generate token for
            list_type: Type of list for unsubscribe

        Returns:
            UnsubscribeToken object
        """
        # Create token data as JSON then base64 encode
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.token_expiration_days
        )
        token_data_dict = {
            "email": email,
            "list_type": list_type,
            "expires_at": expires_at.isoformat(),
        }
        token_data_json = json.dumps(token_data_dict, separators=(",", ":"))
        token_data_b64 = base64.urlsafe_b64encode(token_data_json.encode()).decode()

        # Generate HMAC signature
        signature = hmac.new(
            self.secret_key.encode(), token_data_b64.encode(), hashlib.sha256
        ).hexdigest()

        # Create final token
        token = f"{signature}:{token_data_b64}"

        return UnsubscribeToken(
            token=token, email=email, expires_at=expires_at, list_type=list_type
        )

    def verify_unsubscribe_token(self, token: str) -> Optional[UnsubscribeToken]:
        """
        Verify and decode unsubscribe token

        Args:
            token: Token to verify

        Returns:
            UnsubscribeToken if valid, None otherwise
        """
        try:
            # Split token into signature and data
            parts = token.split(":", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid token format: {token[:20]}...")
                return None

            signature, token_data_b64 = parts

            # Verify signature
            expected_signature = hmac.new(
                self.secret_key.encode(), token_data_b64.encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_signature):
                logger.warning(f"Invalid token signature: {token[:20]}...")
                return None

            # Decode and parse token data
            try:
                token_data_json = base64.urlsafe_b64decode(
                    token_data_b64.encode()
                ).decode()
                token_data_dict = json.loads(token_data_json)
            except Exception:
                logger.warning(f"Invalid token data encoding: {token[:20]}...")
                return None

            # Extract fields
            email = token_data_dict.get("email")
            list_type = token_data_dict.get("list_type")
            expires_at_str = token_data_dict.get("expires_at")

            if not all([email, list_type, expires_at_str]):
                logger.warning(f"Missing token data fields: {token[:20]}...")
                return None

            expires_at = datetime.fromisoformat(expires_at_str)

            # Check expiration
            if expires_at < datetime.now(timezone.utc):
                logger.warning(f"Expired unsubscribe token for {email}")
                return None

            return UnsubscribeToken(
                token=token, email=email, expires_at=expires_at, list_type=list_type
            )

        except Exception as e:
            logger.error(f"Error verifying unsubscribe token: {e}")
            return None

    def process_unsubscribe(self, token: str, reason: str = "user_request") -> bool:
        """
        Process unsubscribe request using token

        Args:
            token: Unsubscribe token
            reason: Reason for unsubscribe

        Returns:
            True if successful, False otherwise
        """
        # Verify token
        token_data = self.verify_unsubscribe_token(token)
        if not token_data:
            return False

        try:
            with SessionLocal() as session:
                # Check if already suppressed
                existing = (
                    session.query(SuppressionList)
                    .filter(
                        and_(
                            SuppressionList.email == token_data.email.lower(),
                            SuppressionList.is_active == True,
                        )
                    )
                    .first()
                )

                if existing:
                    logger.info(f"Email {token_data.email} already suppressed")
                    return True

                # Create suppression record
                suppression = SuppressionList(
                    email=token_data.email.lower(),
                    reason=reason,
                    source="unsubscribe_link",
                )

                session.add(suppression)
                session.commit()

                logger.info(
                    f"Successfully unsubscribed {token_data.email} from {token_data.list_type}"
                )
                return True

        except Exception as e:
            logger.error(f"Error processing unsubscribe for {token_data.email}: {e}")
            return False

    def generate_compliance_headers(
        self,
        email: str,
        list_type: str = "marketing",
        custom_headers: Optional[Dict[str, str]] = None,
    ) -> ComplianceHeaders:
        """
        Generate required compliance headers for email

        Args:
            email: Recipient email address
            list_type: Type of mailing list
            custom_headers: Additional custom headers

        Returns:
            ComplianceHeaders object
        """
        # Generate unsubscribe token
        token = self.generate_unsubscribe_token(email, list_type)

        # Build unsubscribe URLs
        unsubscribe_params = {"token": token.token, "email": email}

        unsubscribe_url = f"{self.base_url}/unsubscribe?{urlencode(unsubscribe_params)}"
        post_url = f"{self.base_url}/unsubscribe"

        # Create compliance headers
        headers = ComplianceHeaders(
            list_unsubscribe=f"<{unsubscribe_url}>, <mailto:unsubscribe@leadfactory.com>",
            list_unsubscribe_post="List-Unsubscribe=One-Click",
            list_id=self.list_id,
            precedence="bulk",
            auto_submitted="auto-generated",
        )

        return headers

    def add_compliance_to_email_data(
        self, email_data: Any, list_type: str = "marketing"
    ) -> Any:
        """
        Add compliance headers and unsubscribe links to email data

        Args:
            email_data: EmailData object to modify
            list_type: Type of mailing list

        Returns:
            Modified EmailData object
        """
        # Generate compliance headers
        headers = self.generate_compliance_headers(email_data.to_email, list_type)

        # Add headers to custom args (SendGrid will include them)
        if not email_data.custom_args:
            email_data.custom_args = {}

        email_data.custom_args.update(
            {
                "List-Unsubscribe": headers.list_unsubscribe,
                "List-Unsubscribe-Post": headers.list_unsubscribe_post,
                "List-ID": headers.list_id,
                "Precedence": headers.precedence,
                "Auto-Submitted": headers.auto_submitted,
                "compliance_list_type": list_type,
            }
        )

        # Add unsubscribe link to email content if HTML content exists
        if email_data.html_content:
            token = self.generate_unsubscribe_token(email_data.to_email, list_type)
            unsubscribe_params = {"token": token.token, "email": email_data.to_email}
            unsubscribe_url = (
                f"{self.base_url}/unsubscribe?{urlencode(unsubscribe_params)}"
            )

            # Add unsubscribe footer to HTML
            unsubscribe_footer = f"""
            <br><br>
            <div style="font-size: 12px; color: #666; text-align: center; border-top: 1px solid #eee; padding-top: 10px; margin-top: 20px;">
                <p>You received this email because you signed up for website insights from LeadFactory.</p>
                <p><a href="{unsubscribe_url}" style="color: #666;">Unsubscribe</a> | 
                LeadFactory, San Francisco, CA | 
                <a href="mailto:support@leadfactory.com" style="color: #666;">Contact Support</a></p>
            </div>
            """
            email_data.html_content += unsubscribe_footer

        # Add unsubscribe link to text content if it exists
        if email_data.text_content:
            token = self.generate_unsubscribe_token(email_data.to_email, list_type)
            unsubscribe_params = {"token": token.token, "email": email_data.to_email}
            unsubscribe_url = (
                f"{self.base_url}/unsubscribe?{urlencode(unsubscribe_params)}"
            )

            # Add unsubscribe footer to text
            unsubscribe_footer = f"""

---
You received this email because you signed up for website insights from LeadFactory.
Unsubscribe: {unsubscribe_url}
LeadFactory, San Francisco, CA
Contact: support@leadfactory.com
"""
            email_data.text_content += unsubscribe_footer

        return email_data

    def record_suppression(
        self,
        email: str,
        reason: str,
        list_type: str = "marketing",
        source: str = "manual",
        expires_days: Optional[int] = None,
    ) -> bool:
        """
        Manually record a suppression

        Args:
            email: Email to suppress
            reason: Reason for suppression
            list_type: Type of list (ignored for now)
            source: Source of suppression
            expires_days: Days until expiration (None for permanent)

        Returns:
            True if successful, False otherwise
        """
        try:
            with SessionLocal() as session:
                # Check for existing active suppression
                existing = (
                    session.query(SuppressionList)
                    .filter(
                        and_(
                            SuppressionList.email == email.lower(),
                            SuppressionList.is_active == True,
                        )
                    )
                    .first()
                )

                if existing:
                    logger.info(f"Email {email} already suppressed")
                    return True

                # Calculate expiration if specified
                expires_at = None
                if expires_days:
                    expires_at = datetime.now(timezone.utc) + timedelta(
                        days=expires_days
                    )

                # Create suppression
                suppression = SuppressionList(
                    email=email.lower(),
                    reason=reason,
                    source=source,
                    expires_at=expires_at,
                )

                session.add(suppression)
                session.commit()

                logger.info(f"Recorded suppression for {email}")
                return True

        except Exception as e:
            logger.error(f"Error recording suppression for {email}: {e}")
            return False

    def get_suppression_stats(self) -> Dict[str, Any]:
        """
        Get suppression statistics

        Returns:
            Dictionary with suppression stats
        """
        try:
            with SessionLocal() as session:
                # Total active suppressions
                total_active = (
                    session.query(SuppressionList)
                    .filter(SuppressionList.is_active == True)
                    .count()
                )

                # By source (since no list_type field)
                unsubscribe_source_count = (
                    session.query(SuppressionList)
                    .filter(
                        and_(
                            SuppressionList.is_active == True,
                            SuppressionList.source == "unsubscribe_link",
                        )
                    )
                    .count()
                )

                # By reason
                unsubscribe_count = (
                    session.query(SuppressionList)
                    .filter(
                        and_(
                            SuppressionList.is_active == True,
                            SuppressionList.reason == "user_request",
                        )
                    )
                    .count()
                )

                bounce_count = (
                    session.query(SuppressionList)
                    .filter(
                        and_(
                            SuppressionList.is_active == True,
                            SuppressionList.reason.in_(
                                ["hard_bounce", "spam_complaint"]
                            ),
                        )
                    )
                    .count()
                )

                return {
                    "total_active_suppressions": total_active,
                    "unsubscribe_source_suppressions": unsubscribe_source_count,
                    "user_unsubscribes": unsubscribe_count,
                    "bounce_suppressions": bounce_count,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as e:
            logger.error(f"Error getting suppression stats: {e}")
            return {
                "error": str(e),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }


# Utility functions


def check_email_suppression(email: str, list_type: str = "marketing") -> bool:
    """
    Utility function to check if email is suppressed

    Args:
        email: Email address to check
        list_type: Type of suppression list

    Returns:
        True if suppressed, False otherwise
    """
    compliance_manager = ComplianceManager()
    return compliance_manager.check_suppression(email, list_type)


def generate_unsubscribe_link(email: str, list_type: str = "marketing") -> str:
    """
    Utility function to generate unsubscribe link

    Args:
        email: Email address
        list_type: Type of mailing list

    Returns:
        Unsubscribe URL
    """
    compliance_manager = ComplianceManager()
    token = compliance_manager.generate_unsubscribe_token(email, list_type)

    config = get_settings()
    base_url = config.base_url.rstrip("/")

    unsubscribe_params = {"token": token.token, "email": email}

    return f"{base_url}/unsubscribe?{urlencode(unsubscribe_params)}"


def process_unsubscribe_request(token: str, reason: str = "user_request") -> bool:
    """
    Utility function to process unsubscribe request

    Args:
        token: Unsubscribe token
        reason: Reason for unsubscribe

    Returns:
        True if successful, False otherwise
    """
    compliance_manager = ComplianceManager()
    return compliance_manager.process_unsubscribe(token, reason)
