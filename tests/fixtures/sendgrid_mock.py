"""
SendGrid API Mock Factory

Provides realistic mock responses for SendGrid email API testing.
"""
from datetime import datetime
from typing import Any, Dict, List

from tests.fixtures.mock_factory import MockFactory


class SendGridMockFactory(MockFactory):
    """Mock factory for SendGrid API responses."""

    @classmethod
    def create_success_response(cls, **overrides) -> Dict[str, Any]:
        """
        Create a successful email send response.

        Args:
            **overrides: Override default values

        Returns:
            Dict representing SendGrid API response
        """
        base_response = {
            "message_id": "<test.123456789@mail.sendgrid.net>",
            "status_code": 202,
            "headers": {
                "X-Message-Id": "test-message-123",
                "X-Request-Id": "request-456",
                "X-RateLimit-Limit": "600",
                "X-RateLimit-Remaining": "599",
                "X-RateLimit-Reset": "1640995200",
            },
        }

        base_response.update(overrides)
        return base_response

    @classmethod
    def create_error_response(cls, error_type: str, **overrides) -> Dict[str, Any]:
        """
        Create an error response for various SendGrid API errors.

        Args:
            error_type: Type of error (invalid_email, rate_limit, etc.)
            **overrides: Additional fields to include

        Returns:
            Dict representing error response
        """
        error_responses = {
            "invalid_email": {
                "errors": [
                    {
                        "message": "The email address 'invalid-email' is not valid.",
                        "field": "to.0.email",
                        "help": "http://sendgrid.com/docs/API_Reference/Web_API_v3/Mail/errors.html#message.to.email",
                    }
                ],
                "status_code": 400,
            },
            "rate_limit": {
                "errors": [
                    {
                        "message": "Too many requests",
                        "field": None,
                        "help": "https://sendgrid.com/docs/API_Reference/Web_API_v3/rate_limits.html",
                    }
                ],
                "status_code": 429,
                "headers": {
                    "X-RateLimit-Limit": "600",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": "1640995200",
                },
            },
            "unauthorized": {
                "errors": [
                    {
                        "message": "The provided authorization grant is invalid, expired, or revoked",
                        "field": None,
                        "help": "https://sendgrid.com/docs/API_Reference/Web_API_v3/Authentication/index.html",
                    }
                ],
                "status_code": 401,
            },
            "bad_request": {
                "errors": [
                    {
                        "message": "Bad Request",
                        "field": "personalizations.0",
                        "help": "http://sendgrid.com/docs/API_Reference/Web_API_v3/Mail/errors.html",
                    }
                ],
                "status_code": 400,
            },
        }

        response = error_responses.get(error_type, error_responses["bad_request"])
        response.update(overrides)
        return response

    @classmethod
    def create_batch_send_response(cls, recipient_count: int = 3, **overrides) -> Dict[str, Any]:
        """Create a batch email send response."""
        return {
            "batch_id": "batch_123456",
            "status_code": 201,
            "message": f"Batch created with {recipient_count} recipients",
            "headers": {"X-Batch-Id": "batch_123456", "X-RateLimit-Remaining": str(600 - recipient_count)},
        }

    @classmethod
    def create_bounce_webhook(cls, email: str, reason: str = "bounce", **overrides) -> Dict[str, Any]:
        """Create a bounce webhook event."""
        base_event = {
            "email": email,
            "timestamp": int(datetime.now().timestamp()),
            "smtp-id": "<14c5d75ce93.dfd.64b469@ismtpd-555>",
            "event": "bounce",
            "category": ["cat facts"],
            "sg_event_id": "sg_event_123",
            "sg_message_id": "sg_message_456",
            "reason": reason,
            "status": "5.0.0",
            "type": "bounce",
        }

        base_event.update(overrides)
        return base_event

    @classmethod
    def create_click_webhook(cls, email: str, url: str, **overrides) -> Dict[str, Any]:
        """Create a click tracking webhook event."""
        base_event = {
            "email": email,
            "timestamp": int(datetime.now().timestamp()),
            "url": url,
            "url_offset": {"index": 0, "type": "html"},
            "event": "click",
            "category": ["newsletter"],
            "sg_event_id": "sg_click_123",
            "sg_message_id": "sg_message_456",
            "useragent": "Mozilla/5.0",
        }

        base_event.update(overrides)
        return base_event

    @classmethod
    def create_open_webhook(cls, email: str, **overrides) -> Dict[str, Any]:
        """Create an open tracking webhook event."""
        base_event = {
            "email": email,
            "timestamp": int(datetime.now().timestamp()),
            "event": "open",
            "category": ["newsletter"],
            "sg_event_id": "sg_open_123",
            "sg_message_id": "sg_message_456",
            "useragent": "Mozilla/5.0",
        }

        base_event.update(overrides)
        return base_event

    @classmethod
    def create_template_response(cls, template_id: str = "template_123", **overrides) -> Dict[str, Any]:
        """Create a template retrieval response."""
        base_response = {
            "id": template_id,
            "name": "Test Email Template",
            "generation": "dynamic",
            "updated_at": "2023-12-25 10:00:00",
            "versions": [
                {
                    "id": "version_123",
                    "template_id": template_id,
                    "active": 1,
                    "name": "Version 1",
                    "html_content": "<html><body>Hello {{name}}!</body></html>",
                    "plain_content": "Hello {{name}}!",
                    "subject": "{{subject}}",
                    "updated_at": "2023-12-25 10:00:00",
                }
            ],
        }

        base_response.update(overrides)
        return base_response

    @classmethod
    def create_stats_response(cls, start_date: str, end_date: str, **overrides) -> List[Dict[str, Any]]:
        """Create email statistics response."""
        base_response = [
            {
                "date": start_date,
                "stats": [
                    {
                        "metrics": {
                            "blocks": 0,
                            "bounce_drops": 0,
                            "bounces": 0,
                            "clicks": 5,
                            "deferred": 0,
                            "delivered": 100,
                            "invalid_emails": 0,
                            "opens": 75,
                            "processed": 100,
                            "requests": 100,
                            "spam_report_drops": 0,
                            "spam_reports": 0,
                            "unique_clicks": 3,
                            "unique_opens": 50,
                            "unsubscribe_drops": 0,
                            "unsubscribes": 1,
                        }
                    }
                ],
            }
        ]

        if overrides:
            base_response[0].update(overrides)

        return base_response

    @classmethod
    def create_suppression_response(cls, email: str, group_id: int = 123, **overrides) -> Dict[str, Any]:
        """Create a suppression list response."""
        base_response = {
            "recipient_email": email,
            "group_id": group_id,
            "group_name": "Test Suppression Group",
            "suppressed_at": int(datetime.now().timestamp()),
            "created_at": int(datetime.now().timestamp()),
        }

        base_response.update(overrides)
        return base_response

    @classmethod
    def create_validation_response(cls, email: str, is_valid: bool = True, **overrides) -> Dict[str, Any]:
        """Create an email validation response."""
        base_response = {
            "result": {
                "email": email,
                "verdict": "Valid" if is_valid else "Invalid",
                "score": 0.95 if is_valid else 0.15,
                "local": email.split("@")[0],
                "host": email.split("@")[1] if "@" in email else "",
                "checks": {
                    "domain": {
                        "has_valid_address_syntax": is_valid,
                        "has_mx_or_a_record": is_valid,
                        "is_suspected_disposable_address": False,
                    },
                    "local_part": {"is_suspected_role_address": False},
                },
            }
        }

        base_response.update(overrides)
        return base_response
