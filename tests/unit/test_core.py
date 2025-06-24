"""
Test core utilities, config, and exceptions
"""
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from core.config import Settings, get_settings
from core.exceptions import (
    ConfigurationError,
    ExternalAPIError,
    LeadFactoryError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from core.logging import get_logger, setup_logging
from core.utils import (
    calculate_percentage,
    chunk_list,
    clean_url,
    deep_merge,
    extract_domain,
    format_currency,
    generate_slug,
    generate_token,
    get_date_range,
    hash_email,
    mask_sensitive_data,
    normalize_phone,
    parse_currency,
    safe_divide,
    truncate_text,
)


class TestConfig:
    def test_default_settings(self):
        """Test default settings values"""
        settings = Settings()

        # Environment may be overridden by env vars
        expected_env = os.getenv("ENVIRONMENT", "development")
        assert settings.environment == expected_env
        assert settings.use_stubs is True
        # Database URL may be overridden by system env vars
        assert settings.max_daily_emails == 100
        assert settings.report_price_cents == 19900

    def test_environment_override(self, monkeypatch):
        """Test environment variable override"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("USE_STUBS", "false")
        monkeypatch.setenv("SECRET_KEY", "production-secret")

        settings = Settings()

        assert settings.environment == "production"
        assert settings.use_stubs is False
        assert settings.is_production is True

    def test_api_urls_with_stubs(self):
        """Test API URLs when using stubs"""
        settings = Settings(use_stubs=True, stub_base_url="http://stub:5010")
        urls = settings.api_base_urls

        assert urls["yelp"] == "http://stub:5010"
        assert urls["stripe"] == "http://stub:5010"
        assert all(url == "http://stub:5010" for url in urls.values())

    def test_api_urls_production(self):
        """Test API URLs for production"""
        settings = Settings(use_stubs=False)
        urls = settings.api_base_urls

        assert urls["yelp"] == "https://api.yelp.com"
        assert urls["stripe"] == "https://api.stripe.com"
        assert urls["openai"] == "https://api.openai.com"

    def test_get_api_key_with_stubs(self):
        """Test API key generation for stubs"""
        settings = Settings(use_stubs=True)

        assert settings.get_api_key("yelp") == "stub-yelp-key"
        assert settings.get_api_key("stripe") == "stub-stripe-key"

    def test_get_api_key_missing(self):
        """Test missing API key raises error"""
        settings = Settings(use_stubs=False, yelp_api_key=None)

        with pytest.raises(ValueError, match="API key not configured"):
            settings.get_api_key("yelp")


class TestLogging:
    def test_get_logger(self):
        """Test logger creation with context"""
        logger = get_logger("test.module", domain="d0", operation="test")

        assert logger.extra["domain"] == "d0"
        assert logger.extra["operation"] == "test"

    def test_logger_with_context(self):
        """Test adding context to logger"""
        logger = get_logger("test")
        context_logger = logger.with_context(request_id="123", user_id="456")

        assert context_logger.extra["request_id"] == "123"
        assert context_logger.extra["user_id"] == "456"

    def test_setup_logging_json_format(self, monkeypatch):
        """Test JSON logging format"""
        monkeypatch.setenv("LOG_FORMAT", "json")
        setup_logging()

        # Check that root logger has correct configuration
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0


class TestExceptions:
    def test_leadfactory_error(self):
        """Test base exception"""
        error = LeadFactoryError(
            "Test error",
            error_code="TEST_ERROR",
            details={"key": "value"},
            status_code=500,
        )

        assert str(error) == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details["key"] == "value"
        assert error.status_code == 500

        error_dict = error.to_dict()
        assert error_dict["error"] == "TEST_ERROR"
        assert error_dict["message"] == "Test error"

    def test_validation_error(self):
        """Test validation error with field"""
        error = ValidationError("Invalid email", field="email")

        assert error.status_code == 400
        assert error.details["field"] == "email"

    def test_not_found_error(self):
        """Test not found error"""
        error = NotFoundError("Business", "123")

        assert error.status_code == 404
        assert "Business not found: 123" in str(error)
        assert error.details["resource"] == "Business"

    def test_external_api_error(self):
        """Test external API error"""
        error = ExternalAPIError(
            provider="yelp",
            message="Service unavailable",
            status_code=503,
            response_body="Error response",
        )

        assert error.status_code == 503  # Uses provided status_code
        assert "yelp API error" in str(error)
        assert error.details["provider"] == "yelp"
        assert error.details["api_status_code"] == 503

        # Test default status code when none provided
        error_default = ExternalAPIError(provider="stripe", message="API down")
        assert error_default.status_code == 502  # Default Bad Gateway

    def test_rate_limit_error(self):
        """Test rate limit error"""
        error = RateLimitError(
            provider="yelp", retry_after=60, daily_limit=5000, daily_used=5000
        )

        assert error.status_code == 429
        assert "retry after 60 seconds" in str(error)
        assert error.details["daily_limit"] == 5000


class TestUtils:
    def test_generate_token(self):
        """Test token generation"""
        token1 = generate_token(32)
        token2 = generate_token(32)

        assert len(token1) > 32  # URL-safe encoding is longer
        assert token1 != token2  # Should be unique

    def test_hash_email(self):
        """Test email hashing"""
        hash1 = hash_email("Test@Example.com")
        hash2 = hash_email("test@example.com")
        hash3 = hash_email("other@example.com")

        assert hash1 == hash2  # Case insensitive
        assert hash1 != hash3  # Different emails
        assert len(hash1) == 64  # SHA-256 hex length

    def test_normalize_phone(self):
        """Test phone normalization"""
        assert normalize_phone("(555) 123-4567") == "+15551234567"
        assert normalize_phone("1-555-123-4567") == "+15551234567"
        assert normalize_phone("5551234567") == "+15551234567"
        assert normalize_phone("") is None

    def test_clean_url(self):
        """Test URL cleaning"""
        assert clean_url("example.com") == "https://example.com"
        assert clean_url("http://example.com/") == "http://example.com"
        assert clean_url("https://example.com/path/") == "https://example.com/path"

    def test_truncate_text(self):
        """Test text truncation"""
        assert truncate_text("Short", 10) == "Short"
        assert truncate_text("This is a long text", 10) == "This is..."
        assert truncate_text("Exact", 5) == "Exact"

    def test_calculate_percentage(self):
        """Test percentage calculation"""
        assert calculate_percentage(25, 100) == 25.0
        assert calculate_percentage(1, 3, decimals=1) == 33.3
        assert calculate_percentage(5, 0) == 0.0  # Division by zero

    def test_format_currency(self):
        """Test currency formatting"""
        assert format_currency(19900) == "$199.00"
        assert format_currency(1050) == "$10.50"
        assert format_currency(100, "EUR") == "1.00 EUR"

    def test_parse_currency(self):
        """Test currency parsing"""
        assert parse_currency("$199.00") == 19900
        assert parse_currency("10.50") == 1050
        assert parse_currency("€ 99,99") == 9999

    def test_chunk_list(self):
        """Test list chunking"""
        items = list(range(10))
        chunks = chunk_list(items, 3)

        assert len(chunks) == 4
        assert chunks[0] == [0, 1, 2]
        assert chunks[-1] == [9]

    def test_deep_merge(self):
        """Test deep dictionary merge"""
        dict1 = {"a": 1, "b": {"c": 2}}
        dict2 = {"b": {"d": 3}, "e": 4}

        result = deep_merge(dict1, dict2)

        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3
        assert result["e"] == 4

    def test_get_date_range(self):
        """Test date range generation"""
        start, end = get_date_range(7)

        assert end == date.today()
        assert (end - start).days == 7

    def test_safe_divide(self):
        """Test safe division"""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(10, 0) == 0.0
        assert safe_divide(10, 0, default=100) == 100

    def test_extract_domain(self):
        """Test domain extraction"""
        assert extract_domain("https://www.example.com/path") == "example.com"
        assert extract_domain("http://subdomain.example.com") == "subdomain.example.com"
        assert extract_domain("invalid") is None

    def test_generate_slug(self):
        """Test slug generation"""
        assert generate_slug("Hello World!") == "hello-world"
        assert generate_slug("Test & Special #Characters") == "test-special-characters"
        assert len(generate_slug("A" * 100, max_length=20)) <= 20

    def test_mask_sensitive_data(self):
        """Test sensitive data masking"""
        assert mask_sensitive_data("1234567890", 4) == "******7890"
        assert mask_sensitive_data("short", 4) == "*hort"
        assert mask_sensitive_data("123", 4) == "***"
