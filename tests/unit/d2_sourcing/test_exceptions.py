"""Unit tests for D2 sourcing exceptions."""
import pytest

from d2_sourcing.exceptions import (
    BatchQuotaException,
    ConfigurationException,
    DataValidationException,
    DeduplicationException,
    ErrorRecoveryException,
    NetworkException,
    PaginationException,
    SourcingException,
)


class TestSourcingException:
    """Test base SourcingException."""

    def test_basic_exception(self):
        """Test basic exception creation and message."""
        exc = SourcingException("Test error")
        assert str(exc) == "Test error"
        assert isinstance(exc, Exception)

    def test_inheritance(self):
        """Test that it inherits from Exception."""
        exc = SourcingException("Test")
        assert isinstance(exc, Exception)


class TestPaginationException:
    """Test PaginationException."""

    def test_basic_pagination_error(self):
        """Test basic pagination exception."""
        exc = PaginationException("Page not found")
        assert str(exc) == "Page not found"
        assert exc.current_offset is None
        assert exc.total_results is None

    def test_pagination_with_context(self):
        """Test pagination exception with offset and total."""
        exc = PaginationException("Invalid offset", current_offset=100, total_results=50)
        assert str(exc) == "Invalid offset"
        assert exc.current_offset == 100
        assert exc.total_results == 50

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = PaginationException("Test")
        assert isinstance(exc, SourcingException)


class TestBatchQuotaException:
    """Test BatchQuotaException."""

    def test_basic_quota_error(self):
        """Test basic quota exception."""
        exc = BatchQuotaException("Quota exceeded")
        assert str(exc) == "Quota exceeded"
        assert exc.current_usage is None
        assert exc.limit is None

    def test_quota_with_usage(self):
        """Test quota exception with usage info."""
        exc = BatchQuotaException("Quota exceeded", current_usage=1500, limit=1000)
        assert str(exc) == "Quota exceeded (Usage: 1500/1000)"
        assert exc.current_usage == 1500
        assert exc.limit == 1000

    def test_quota_partial_info(self):
        """Test quota with only current usage."""
        exc = BatchQuotaException("Quota issue", current_usage=500)
        assert str(exc) == "Quota issue"
        assert exc.current_usage == 500
        assert exc.limit is None

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = BatchQuotaException("Test")
        assert isinstance(exc, SourcingException)


class TestDataValidationException:
    """Test DataValidationException."""

    def test_basic_validation_error(self):
        """Test basic validation exception."""
        exc = DataValidationException("Invalid data")
        assert str(exc) == "Invalid data"
        assert exc.field is None
        assert exc.value is None

    def test_validation_with_field(self):
        """Test validation exception with field info."""
        exc = DataValidationException("Invalid format", field="email", value="not-an-email")
        assert str(exc) == "Validation error for field 'email': Invalid format"
        assert exc.field == "email"
        assert exc.value == "not-an-email"

    def test_validation_without_field(self):
        """Test validation without field still works."""
        exc = DataValidationException("General validation error", value=123)
        assert str(exc) == "General validation error"
        assert exc.field is None
        assert exc.value == 123

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = DataValidationException("Test")
        assert isinstance(exc, SourcingException)


class TestDeduplicationException:
    """Test DeduplicationException."""

    def test_basic_dedup_error(self):
        """Test basic deduplication exception."""
        exc = DeduplicationException("Duplicate found")
        assert str(exc) == "Duplicate found"
        assert exc.business_ids == []

    def test_dedup_with_ids(self):
        """Test deduplication with business IDs."""
        ids = ["biz1", "biz2", "biz3"]
        exc = DeduplicationException("Multiple duplicates", business_ids=ids)
        assert str(exc) == "Multiple duplicates"
        assert exc.business_ids == ids

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = DeduplicationException("Test")
        assert isinstance(exc, SourcingException)


class TestErrorRecoveryException:
    """Test ErrorRecoveryException."""

    def test_basic_recovery_error(self):
        """Test basic error recovery exception."""
        exc = ErrorRecoveryException("Recovery failed")
        assert str(exc) == "Recovery failed"
        assert exc.original_error is None
        assert exc.retry_count == 0

    def test_recovery_with_retry_count(self):
        """Test recovery exception with retry count."""
        exc = ErrorRecoveryException("Still failing", retry_count=3)
        assert str(exc) == "Still failing (Retry 3)"
        assert exc.retry_count == 3

    def test_recovery_with_original_error(self):
        """Test recovery exception with original error."""
        original = ValueError("Original problem")
        exc = ErrorRecoveryException("Recovery failed", original_error=original)
        assert str(exc) == "Recovery failed - Original: Original problem"
        assert exc.original_error is original

    def test_recovery_with_all_info(self):
        """Test recovery exception with all information."""
        original = RuntimeError("Network timeout")
        exc = ErrorRecoveryException("Failed after retries", original_error=original, retry_count=5)
        assert str(exc) == "Failed after retries (Retry 5) - Original: Network timeout"
        assert exc.original_error is original
        assert exc.retry_count == 5

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = ErrorRecoveryException("Test")
        assert isinstance(exc, SourcingException)


class TestConfigurationException:
    """Test ConfigurationException."""

    def test_basic_config_error(self):
        """Test basic configuration exception."""
        exc = ConfigurationException("Missing config")
        assert str(exc) == "Missing config"
        assert exc.config_key is None

    def test_config_with_key(self):
        """Test configuration exception with key."""
        exc = ConfigurationException("Invalid value", config_key="api_timeout")
        assert str(exc) == "Invalid value"
        assert exc.config_key == "api_timeout"

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = ConfigurationException("Test")
        assert isinstance(exc, SourcingException)


class TestNetworkException:
    """Test NetworkException."""

    def test_basic_network_error(self):
        """Test basic network exception."""
        exc = NetworkException("Connection failed")
        assert str(exc) == "Connection failed"
        assert exc.timeout_seconds is None

    def test_network_with_timeout(self):
        """Test network exception with timeout."""
        exc = NetworkException("Request timed out", timeout_seconds=30)
        assert str(exc) == "Request timed out"
        assert exc.timeout_seconds == 30

    def test_inheritance(self):
        """Test that it inherits from SourcingException."""
        exc = NetworkException("Test")
        assert isinstance(exc, SourcingException)


class TestExceptionHierarchy:
    """Test the exception hierarchy relationships."""

    def test_all_inherit_from_sourcing(self):
        """Test that all exceptions inherit from SourcingException."""
        exceptions = [
            PaginationException("test"),
            BatchQuotaException("test"),
            DataValidationException("test"),
            DeduplicationException("test"),
            ErrorRecoveryException("test"),
            ConfigurationException("test"),
            NetworkException("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, SourcingException)
            assert isinstance(exc, Exception)

    def test_exception_names(self):
        """Test that exception names are properly set."""
        assert PaginationException.__name__ == "PaginationException"
        assert BatchQuotaException.__name__ == "BatchQuotaException"
        assert DataValidationException.__name__ == "DataValidationException"
