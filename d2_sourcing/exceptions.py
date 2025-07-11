"""
Custom exceptions for D2 Sourcing domain

Provides specific exception types for Yelp API integration, quota management,
and data sourcing error handling.
"""


class SourcingException(Exception):
    """Base exception for all sourcing-related errors"""

    pass


# Yelp exceptions removed per P0-009 - Yelp provider no longer supported


class PaginationException(SourcingException):
    """Pagination handling errors"""

    def __init__(
        self, message: str, current_offset: int = None, total_results: int = None
    ):
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

    def __init__(self, message: str, field: str = None, value=None):
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

    def __init__(
        self, message: str, original_error: Exception = None, retry_count: int = 0
    ):
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
