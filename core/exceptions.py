"""
Custom exceptions for LeadFactory
Provides structured error handling across all domains
"""
from typing import Any, Dict, Optional


class LeadFactoryError(Exception):
    """Base exception for all LeadFactory errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(LeadFactoryError):
    """Raised when input validation fails"""

    def __init__(self, message: str, field: Optional[str] = None, **details):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            details={"field": field, **details} if field else details,
            status_code=400,
        )


class NotFoundError(LeadFactoryError):
    """Raised when a resource is not found"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            error_code="NOT_FOUND",
            details={"resource": resource, "identifier": str(identifier)},
            status_code=404,
        )


class DuplicateError(LeadFactoryError):
    """Raised when attempting to create a duplicate resource"""

    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            message=f"{resource} already exists: {identifier}",
            error_code="DUPLICATE",
            details={"resource": resource, "identifier": str(identifier)},
            status_code=409,
        )


class ExternalAPIError(LeadFactoryError):
    """Raised when an external API call fails"""

    def __init__(
        self,
        provider: str,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **details,
    ):
        super().__init__(
            message=f"{provider} API error: {message}",
            error_code="EXTERNAL_API_ERROR",
            details={
                "provider": provider,
                "api_status_code": status_code,
                "response_body": response_body,
                **details,
            },
            status_code=status_code
            or 502,  # Use provided status_code or default to Bad Gateway
        )


class RateLimitError(ExternalAPIError):
    """Raised when hitting rate limits"""

    def __init__(
        self,
        provider: str,
        retry_after: Optional[int] = None,
        daily_limit: Optional[int] = None,
        daily_used: Optional[int] = None,
    ):
        message = f"Rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after} seconds"

        super().__init__(
            provider=provider,
            message=message,
            status_code=429,
            retry_after=retry_after,
            daily_limit=daily_limit,
            daily_used=daily_used,
        )
        self.status_code = 429  # Too Many Requests


class ConfigurationError(LeadFactoryError):
    """Raised when configuration is invalid or missing"""

    def __init__(self, message: str, setting: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            details={"setting": setting} if setting else {},
            status_code=500,
        )


class DatabaseError(LeadFactoryError):
    """Raised when database operations fail"""

    def __init__(self, message: str, operation: Optional[str] = None, **details):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            details={"operation": operation, **details} if operation else details,
            status_code=500,
        )


class PaymentError(LeadFactoryError):
    """Raised when payment processing fails"""

    def __init__(
        self,
        message: str,
        payment_intent_id: Optional[str] = None,
        stripe_error_code: Optional[str] = None,
        **details,
    ):
        super().__init__(
            message=message,
            error_code="PAYMENT_ERROR",
            details={
                "payment_intent_id": payment_intent_id,
                "stripe_error_code": stripe_error_code,
                **details,
            },
            status_code=402,  # Payment Required
        )


class EmailDeliveryError(LeadFactoryError):
    """Raised when email delivery fails"""

    def __init__(
        self,
        message: str,
        email: Optional[str] = None,
        reason: Optional[str] = None,
        **details,
    ):
        super().__init__(
            message=message,
            error_code="EMAIL_DELIVERY_ERROR",
            details={"email": email, "reason": reason, **details},
            status_code=500,
        )


class AssessmentError(LeadFactoryError):
    """Raised when website assessment fails"""

    def __init__(
        self, message: str, assessment_type: str, url: Optional[str] = None, **details
    ):
        super().__init__(
            message=message,
            error_code="ASSESSMENT_ERROR",
            details={"assessment_type": assessment_type, "url": url, **details},
            status_code=500,
        )
