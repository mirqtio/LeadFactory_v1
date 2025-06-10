"""
SendGrid API v3 client implementation for email delivery
"""
import base64
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import BaseAPIClient


class SendGridClient(BaseAPIClient):
    """SendGrid API v3 client for email delivery"""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(provider="sendgrid", api_key=api_key)

    def _get_base_url(self) -> str:
        """Get SendGrid API base URL"""
        return "https://api.sendgrid.com"

    def _get_headers(self) -> Dict[str, str]:
        """Get SendGrid API headers"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_rate_limit(self) -> Dict[str, int]:
        """Get SendGrid rate limit configuration"""
        return {
            "daily_limit": 100000,  # Very high for email service
            "daily_used": 0,
            "burst_limit": 100,
            "window_seconds": 1,
        }

    def calculate_cost(self, operation: str, **kwargs) -> Decimal:
        """
        Calculate cost for SendGrid operations

        SendGrid pricing (estimated):
        - Free tier: 100 emails/day
        - Paid tier: ~$0.0006 per email
        """
        if operation.startswith("POST:/v3/mail/send"):
            # Estimate cost per email
            return Decimal("0.0006")
        else:
            # Other operations (webhooks, stats, etc.)
            return Decimal("0.0001")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        from_email: str,
        from_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        text_content: Optional[str] = None,
        template_id: Optional[str] = None,
        dynamic_template_data: Optional[Dict[str, Any]] = None,
        custom_args: Optional[Dict[str, str]] = None,
        tracking_settings: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send a single email via SendGrid

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email content
            from_email: Sender email address
            from_name: Sender name
            reply_to: Reply-to email address
            text_content: Plain text content
            template_id: Dynamic template ID
            dynamic_template_data: Data for dynamic templates
            custom_args: Custom arguments for tracking
            tracking_settings: Email tracking settings

        Returns:
            Dict containing send response
        """
        # Build email payload
        payload = {
            "personalizations": [{"to": [{"email": to_email}], "subject": subject}],
            "from": {"email": from_email, "name": from_name or from_email},
        }

        # Add reply-to if specified
        if reply_to:
            payload["reply_to"] = {"email": reply_to}

        # Add template or content
        if template_id:
            payload["template_id"] = template_id
            if dynamic_template_data:
                payload["personalizations"][0][
                    "dynamic_template_data"
                ] = dynamic_template_data
        else:
            payload["content"] = []
            if text_content:
                payload["content"].append({"type": "text/plain", "value": text_content})
            if html_content:
                payload["content"].append({"type": "text/html", "value": html_content})

        # Add custom arguments for tracking
        if custom_args:
            payload["custom_args"] = custom_args

        # Add tracking settings
        if tracking_settings:
            payload["tracking_settings"] = tracking_settings
        else:
            # Default tracking settings
            payload["tracking_settings"] = {
                "click_tracking": {"enable": True},
                "open_tracking": {"enable": True},
                "subscription_tracking": {"enable": False},
            }

        return await self.make_request("POST", "/v3/mail/send", json=payload)

    async def send_bulk_emails(
        self,
        emails: List[Dict[str, Any]],
        from_email: str,
        from_name: Optional[str] = None,
        template_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send multiple emails efficiently

        Args:
            emails: List of email dictionaries with to_email, subject, content
            from_email: Sender email address
            from_name: Sender name
            template_id: Dynamic template ID

        Returns:
            Dict containing bulk send results
        """
        results = {"total_emails": len(emails), "sent": 0, "failed": 0, "results": []}

        for email in emails:
            try:
                result = await self.send_email(
                    to_email=email["to_email"],
                    subject=email["subject"],
                    html_content=email.get("html_content", ""),
                    text_content=email.get("text_content"),
                    from_email=from_email,
                    from_name=from_name,
                    template_id=template_id,
                    dynamic_template_data=email.get("template_data"),
                    custom_args=email.get("custom_args"),
                )

                results["sent"] += 1
                results["results"].append(
                    {
                        "email": email["to_email"],
                        "status": "sent",
                        "message_id": result.get("message_id"),
                    }
                )

            except Exception as e:
                results["failed"] += 1
                results["results"].append(
                    {"email": email["to_email"], "status": "failed", "error": str(e)}
                )
                self.logger.error(f"Failed to send email to {email['to_email']}: {e}")

        return results

    async def get_email_stats(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        aggregated_by: str = "day",
    ) -> Dict[str, Any]:
        """
        Get email statistics

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            aggregated_by: Aggregation period (day, week, month)

        Returns:
            Dict containing email statistics
        """
        params = {"start_date": start_date, "aggregated_by": aggregated_by}

        if end_date:
            params["end_date"] = end_date

        return await self.make_request("GET", "/v3/stats", params=params)

    async def get_bounces(
        self,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get bounce information

        Args:
            start_time: Start timestamp
            end_time: End timestamp
            limit: Number of results to return
            offset: Offset for pagination

        Returns:
            Dict containing bounce information
        """
        params = {"limit": limit, "offset": offset}

        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        return await self.make_request("GET", "/v3/suppression/bounces", params=params)

    async def delete_bounce(self, email: str) -> Dict[str, Any]:
        """
        Remove an email from the bounce list

        Args:
            email: Email address to remove from bounces

        Returns:
            Dict containing deletion response
        """
        return await self.make_request("DELETE", f"/v3/suppression/bounces/{email}")

    async def create_contact(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a contact in SendGrid

        Args:
            email: Contact email address
            first_name: Contact first name
            last_name: Contact last name
            custom_fields: Additional custom fields

        Returns:
            Dict containing contact creation response
        """
        contact_data = {"email": email}

        if first_name:
            contact_data["first_name"] = first_name
        if last_name:
            contact_data["last_name"] = last_name
        if custom_fields:
            contact_data.update(custom_fields)

        payload = {"contacts": [contact_data]}

        return await self.make_request("PUT", "/v3/marketing/contacts", json=payload)

    async def validate_email_address(self, email: str) -> Dict[str, Any]:
        """
        Validate an email address

        Args:
            email: Email address to validate

        Returns:
            Dict containing validation results
        """
        payload = {"email": email, "source": "signup"}

        return await self.make_request("POST", "/v3/validations/email", json=payload)

    async def get_webhook_stats(self) -> Dict[str, Any]:
        """
        Get webhook event statistics

        Returns:
            Dict containing webhook statistics
        """
        return await self.make_request("GET", "/v3/user/webhooks/event/settings")

    def format_email_for_lead_outreach(
        self,
        business_name: str,
        recipient_email: str,
        website_issues: List[Dict[str, Any]],
        sender_name: str = "Website Performance Team",
    ) -> Dict[str, Any]:
        """
        Format email data for lead outreach campaigns

        Args:
            business_name: Target business name
            recipient_email: Recipient email address
            website_issues: List of website performance issues
            sender_name: Sender name

        Returns:
            Formatted email data ready for sending
        """
        # Generate subject line
        issue_count = len(website_issues)
        subject = f"Quick website improvements for {business_name}"

        if issue_count > 0:
            top_issue = website_issues[0].get("issue", "performance optimization")
            subject = f"Found {issue_count} ways to improve {business_name}'s website"

        # Generate email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Website Performance Analysis for {business_name}</h2>

            <p>Hi there,</p>

            <p>I recently analyzed {business_name}'s website and found some opportunities to improve performance and user experience.</p>

            {self._format_issues_html(website_issues)}

            <p>These improvements could help:</p>
            <ul>
                <li>Increase website speed and user satisfaction</li>
                <li>Improve search engine rankings</li>
                <li>Boost conversion rates</li>
            </ul>

            <p>Would you be interested in a free detailed analysis?</p>

            <p>Best regards,<br>{sender_name}</p>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""
        Website Performance Analysis for {business_name}

        Hi there,

        I recently analyzed {business_name}'s website and found some opportunities to improve performance and user experience.

        {self._format_issues_text(website_issues)}

        These improvements could help increase website speed, improve search rankings, and boost conversion rates.

        Would you be interested in a free detailed analysis?

        Best regards,
        {sender_name}
        """

        return {
            "to_email": recipient_email,
            "subject": subject,
            "html_content": html_content,
            "text_content": text_content,
            "custom_args": {
                "business_name": business_name,
                "campaign": "lead_outreach",
                "issues_count": str(issue_count),
            },
        }

    def _format_issues_html(self, issues: List[Dict[str, Any]]) -> str:
        """Format issues for HTML email"""
        if not issues:
            return "<p>Your website looks good overall!</p>"

        html = "<p><strong>Key areas for improvement:</strong></p><ul>"
        for issue in issues[:3]:  # Top 3 issues
            html += f"<li><strong>{issue.get('issue', 'Unknown')}:</strong> {issue.get('improvement', 'Optimization recommended')}</li>"
        html += "</ul>"

        return html

    def _format_issues_text(self, issues: List[Dict[str, Any]]) -> str:
        """Format issues for plain text email"""
        if not issues:
            return "Your website looks good overall!"

        text = "Key areas for improvement:\n"
        for i, issue in enumerate(issues[:3], 1):
            text += f"{i}. {issue.get('issue', 'Unknown')}: {issue.get('improvement', 'Optimization recommended')}\n"

        return text
