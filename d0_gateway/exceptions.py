"""
Gateway-specific exceptions
"""
from core.exceptions import LeadFactoryError


class GatewayError(LeadFactoryError):
    """Base exception for gateway domain"""

    pass


class APIProviderError(GatewayError):
    """Error from external API provider"""

    def __init__(
        self,
        provider: str,
        message: str,
        status_code: int = None,
        response_data: dict = None,
    ):
        self.provider = provider
        self.response_data = response_data
        super().__init__(message=f"{provider}: {message}", status_code=status_code or 500)


class RateLimitExceededError(GatewayError):
    """Rate limit exceeded for provider"""

    def __init__(self, provider: str, limit_type: str, retry_after: int = None):
        self.provider = provider
        self.limit_type = limit_type
        self.retry_after = retry_after
        message = f"Rate limit exceeded for {provider} ({limit_type})"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message)


class CircuitBreakerOpenError(GatewayError):
    """Circuit breaker is open, preventing API calls"""

    def __init__(self, provider: str, failure_count: int):
        self.provider = provider
        self.failure_count = failure_count
        super().__init__(f"Circuit breaker open for {provider} after {failure_count} failures")


class AuthenticationError(APIProviderError):
    """Authentication failed with API provider"""

    def __init__(self, provider: str, message: str = "Authentication failed"):
        super().__init__(provider, message, status_code=401)


class QuotaExceededError(APIProviderError):
    """API quota exceeded for provider"""

    def __init__(self, provider: str, quota_type: str = "daily"):
        message = f"API quota exceeded ({quota_type})"
        super().__init__(provider, message, status_code=429)


class ServiceUnavailableError(APIProviderError):
    """External service is temporarily unavailable"""

    def __init__(self, provider: str, message: str = "Service temporarily unavailable"):
        super().__init__(provider, message, status_code=503)


class InvalidResponseError(APIProviderError):
    """Invalid or unexpected response from API provider"""

    def __init__(self, provider: str, expected_format: str, received_data: str = None):
        message = f"Invalid response format, expected {expected_format}"
        super().__init__(provider, message, response_data={"received": received_data})


class TimeoutError(APIProviderError):
    """Request to API provider timed out"""

    def __init__(self, provider: str, timeout_seconds: int):
        message = f"Request timed out after {timeout_seconds}s"
        super().__init__(provider, message, status_code=408)


class ConfigurationError(GatewayError):
    """Gateway configuration error"""

    def __init__(self, provider: str, setting: str, message: str = None):
        self.provider = provider
        self.setting = setting
        default_message = f"Invalid configuration for {provider}: {setting}"
        super().__init__(message or default_message)
