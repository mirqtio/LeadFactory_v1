"""
Custom exceptions for D2 Sourcing domain

Provides specific exception types for Yelp API integration, quota management,
and data sourcing error handling.
"""


class SourcingException(Exception):
    """Base exception for all sourcing-related errors"""
    pass


class YelpAPIException(SourcingException):
    """Yelp API specific errors"""

    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code

    def __str__(self):
        if self.status_code:
            return f"Yelp API Error {self.status_code}: {super().__str__()}"
        return super().__str__()


class YelpRateLimitException(YelpAPIException):
    """Yelp API rate limit exceeded"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = None):
        super().__init__(message, status_code=429)
        self.retry_after = retry_after

    def __str__(self):
        if self.retry_after:
            return f"{super().__str__()} - Retry after {self.retry_after} seconds"
        return super().__str__()


class YelpQuotaExceededException(YelpAPIException):
    """Daily/monthly quota exceeded"""

    def __init__(self, message: str = "API quota exceeded", quota_type: str = "daily"):
        super().__init__(message, status_code=429)
        self.quota_type = quota_type


class YelpAuthenticationException(YelpAPIException):
    """Invalid API key or authentication failure"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class YelpBusinessNotFoundException(YelpAPIException):
    """Business not found on Yelp"""

    def __init__(self, business_id: str):
        super().__init__(f"Business not found: {business_id}", status_code=404)
        self.business_id = business_id


class PaginationException(SourcingException):
    """Pagination handling errors"""

    def __init__(self, message: str, current_offset: int = None, total_results: int = None):
        super().__init__(message)
        self.current_offset = current_offset
        self.total_results = total_results


class BatchQuotaException(SourcingException):
    """Batch processing quota errors"""

    def __init__(self, message: str, current_usage: int = None, limit: int = None):
        super().__init__(message)
        self.current_usage = current_usage
        self.limit = limit

    def __str__(self):
        if self.current_usage is not None and self.limit is not None:
            return f"{super().__str__()} (Usage: {self.current_usage}/{self.limit})"
        return super().__str__()


class DataValidationException(SourcingException):
    """Data validation and normalization errors"""

    def __init__(self, message: str, field: str = None, value = None):
        super().__init__(message)
        self.field = field
        self.value = value

    def __str__(self):
        if self.field:
            return f"Validation error for field '{self.field}': {super().__str__()}"
        return super().__str__()


class DeduplicationException(SourcingException):
    """Business deduplication errors"""

    def __init__(self, message: str, business_ids: list = None):
        super().__init__(message)
        self.business_ids = business_ids or []


class ErrorRecoveryException(SourcingException):
    """Error recovery mechanism failures"""

    def __init__(self, message: str, original_error: Exception = None, retry_count: int = 0):
        super().__init__(message)
        self.original_error = original_error
        self.retry_count = retry_count

    def __str__(self):
        base_msg = super().__str__()
        if self.retry_count > 0:
            base_msg += f" (Retry {self.retry_count})"
        if self.original_error:
            base_msg += f" - Original: {str(self.original_error)}"
        return base_msg


class ConfigurationException(SourcingException):
    """Configuration and setup errors"""

    def __init__(self, message: str, config_key: str = None):
        super().__init__(message)
        self.config_key = config_key


class NetworkException(SourcingException):
    """Network connectivity and timeout errors"""

    def __init__(self, message: str, timeout_seconds: int = None):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
