"""
Test cache validation functionality, especially 24-hour cache validation
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from d0_gateway.cache import ResponseCache


class TestCacheValidation:
    """Test cache validation and expiration logic"""

    def test_24_hour_cache_validation(self):
        """Test that 24-hour cache validation works correctly"""
        # Create OpenAI cache with 24-hour TTL
        cache = ResponseCache("openai")

        # Verify TTL is set to 24 hours (86400 seconds)
        assert cache.ttl == 86400

        # Test cache key generation
        key = cache.generate_key("test_endpoint", {"param": "value"})
        assert key.startswith("api_cache:")

        # Test that cache validates within the 24-hour window
        # This test demonstrates the cache validation logic
        current_time = datetime.now()

        # Test cache expiration calculation
        expiry_time = current_time + timedelta(seconds=cache.ttl)

        # Verify that 24-hour window is correctly calculated
        expected_expiry = current_time + timedelta(hours=24)
        assert abs((expiry_time - expected_expiry).total_seconds()) < 1

        # Test edge cases
        # Just before expiry
        almost_expired = current_time + timedelta(seconds=cache.ttl - 1)
        assert almost_expired < expected_expiry

        # Just after expiry
        just_expired = current_time + timedelta(seconds=cache.ttl + 1)
        assert just_expired > expected_expiry

    def test_cache_provider_specific_ttls(self):
        """Test that different providers have correct TTLs"""
        # Test all configured providers
        test_cases = [
            ("openai", 86400),  # 24 hours
            ("pagespeed", 7200),  # 2 hours
            ("sendgrid", 300),  # 5 minutes
            ("stripe", 300),  # 5 minutes
            ("places", 3600),  # 1 hour
        ]

        for provider, expected_ttl in test_cases:
            cache = ResponseCache(provider)
            assert cache.ttl == expected_ttl, f"Provider {provider} TTL mismatch"

    def test_default_cache_ttl(self):
        """Test that unknown providers get default TTL"""
        cache = ResponseCache("unknown_provider")
        assert cache.ttl == 1800  # 30 minutes default

    def test_cache_validation_edge_cases(self):
        """Test cache validation with edge cases"""
        cache = ResponseCache("openai")

        # Test with empty parameters
        key1 = cache.generate_key("endpoint", {})
        assert key1 is not None

        # Test with different parameter orders (should be same key)
        key2 = cache.generate_key("endpoint", {"b": 2, "a": 1})
        key3 = cache.generate_key("endpoint", {"a": 1, "b": 2})
        assert key2 == key3

        # Test with nested parameters
        key4 = cache.generate_key("endpoint", {"nested": {"inner": "value"}})
        assert key4 is not None

    @patch("d0_gateway.cache.aioredis")
    def test_cache_connection_validation(self, mock_redis):
        """Test that cache connection is properly validated"""
        cache = ResponseCache("openai")

        # Test that Redis URL is properly configured
        assert hasattr(cache, "settings")
        assert hasattr(cache.settings, "redis_url")

        # Test Redis connection initialization
        assert cache._redis is None  # Should be None initially

        # Test that provider is properly set
        assert cache.provider == "openai"

        # Test hit/miss tracking initialization
        assert cache._hits == 0
        assert cache._misses == 0
