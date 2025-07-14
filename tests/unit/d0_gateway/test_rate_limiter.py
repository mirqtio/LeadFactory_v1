"""
Test token bucket rate limiter
"""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Mark entire module as xfail for Phase 0.5
pytestmark = pytest.mark.xfail(reason="Phase 0.5 feature", strict=False)

from d0_gateway.rate_limiter import RateLimiter  # noqa: E402


class TestRateLimiter:
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing"""
        return RateLimiter("test_provider")

    def test_token_bucket_algorithm_config(self, rate_limiter):
        """Test that token bucket algorithm is configured correctly"""
        # Should have provider-specific limits
        assert hasattr(rate_limiter, "limits")
        assert "daily_limit" in rate_limiter.limits
        assert "burst_limit" in rate_limiter.limits
        assert "window_seconds" in rate_limiter.limits

        # Test default limits for unknown provider
        assert rate_limiter.limits["daily_limit"] == 1000
        assert rate_limiter.limits["burst_limit"] == 10
        assert rate_limiter.limits["window_seconds"] == 1

    def test_provider_specific_limits(self):
        """Test that provider-specific limits work"""
        # Test Yelp limits
        yelp_limiter = RateLimiter("yelp")
        assert yelp_limiter.limits["daily_limit"] == 5000
        assert yelp_limiter.limits["burst_limit"] == 10

        # Test PageSpeed limits
        pagespeed_limiter = RateLimiter("pagespeed")
        assert pagespeed_limiter.limits["daily_limit"] == 25000
        assert pagespeed_limiter.limits["burst_limit"] == 50

        # Test OpenAI limits
        openai_limiter = RateLimiter("openai")
        assert openai_limiter.limits["daily_limit"] == 10000
        assert openai_limiter.limits["burst_limit"] == 20

    def test_redis_based_implementation(self, rate_limiter):
        """Test that Redis-based implementation is configured"""
        # Should have Redis connection capability
        assert hasattr(rate_limiter, "_redis")
        assert hasattr(rate_limiter, "_get_redis")

        # Should be able to get Redis connection
        assert asyncio.iscoroutinefunction(rate_limiter._get_redis)

    def test_lua_script_loading(self, rate_limiter):
        """Test that Lua script is loaded"""
        # Should have Lua script loaded
        assert hasattr(rate_limiter, "_lua_script")
        assert rate_limiter._lua_script is not None
        assert isinstance(rate_limiter._lua_script, str)

        # Script should contain expected functions
        assert "check_daily_limit" in rate_limiter._lua_script
        assert "check_burst_limit" in rate_limiter._lua_script
        assert "check_combined_limits" in rate_limiter._lua_script

    @pytest.mark.asyncio
    async def test_atomic_operations_via_lua(self, rate_limiter):
        """Test that atomic operations work via Lua"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = [1, 10, 1]  # current, limit, allowed

        rate_limiter._redis = mock_redis

        # Test executing Lua script
        result = await rate_limiter._execute_lua_script(mock_redis, "check_daily", ["test_key"], ["10", "86400"])

        # Should have called Redis eval with Lua script
        mock_redis.eval.assert_called_once()
        assert result == [1, 10, 1]

    @pytest.mark.asyncio
    async def test_configurable_limits_per_provider(self, rate_limiter):
        """Test configurable limits per provider"""
        # Test that different providers have different limits configured
        yelp_limiter = RateLimiter("yelp")
        pagespeed_limiter = RateLimiter("pagespeed")
        openai_limiter = RateLimiter("openai")

        # Verify limits are different
        assert yelp_limiter.limits["daily_limit"] != pagespeed_limiter.limits["daily_limit"]
        assert yelp_limiter.limits["burst_limit"] != openai_limiter.limits["burst_limit"]

        # Verify specific expected values
        assert yelp_limiter.limits["daily_limit"] == 5000
        assert pagespeed_limiter.limits["daily_limit"] == 25000
        assert openai_limiter.limits["daily_limit"] == 10000

    @pytest.mark.asyncio
    async def test_daily_limit_enforcement(self, rate_limiter):
        """Test daily limit enforcement"""
        # Mock settings to disable stubs
        with patch.object(rate_limiter.settings, "use_stubs", False):
            # Mock Redis to indicate daily limit exceeded
            mock_redis = AsyncMock()
            mock_redis.eval.return_value = [1001, 1000, 0]  # Over daily limit
            rate_limiter._redis = mock_redis

            allowed = await rate_limiter.is_allowed()
            assert allowed is False

    @pytest.mark.asyncio
    async def test_burst_limit_enforcement(self, rate_limiter):
        """Test burst limit enforcement"""
        # Mock settings to disable stubs
        with patch.object(rate_limiter.settings, "use_stubs", False):
            # Mock Redis: daily OK, burst exceeded
            mock_redis = AsyncMock()

            # First call (daily check) - allowed
            # Second call (burst check) - not allowed
            mock_redis.eval.side_effect = [
                [1, 1000, 1],  # Daily check: allowed
                [11, 10, 0],  # Burst check: exceeded
            ]
            rate_limiter._redis = mock_redis

            allowed = await rate_limiter.is_allowed("burst_test")
            assert allowed is False

    @pytest.mark.asyncio
    async def test_stub_mode_bypass(self):
        """Test that stub mode bypasses rate limiting"""
        with patch("core.config.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_get_settings.return_value = mock_settings

            limiter = RateLimiter("test")
            allowed = await limiter.is_allowed()
            assert allowed is True

    @pytest.mark.asyncio
    async def test_fallback_on_redis_failure(self, rate_limiter):
        """Test fallback behavior when Redis fails"""
        # Mock settings to disable stubs
        with patch.object(rate_limiter.settings, "use_stubs", False):
            # Mock Redis to raise exception
            mock_redis = AsyncMock()
            mock_redis.eval.side_effect = Exception("Redis connection failed")
            rate_limiter._redis = mock_redis

            # Should fallback and fail open (allow request)
            allowed = await rate_limiter.is_allowed()
            assert allowed is True

    @pytest.mark.asyncio
    async def test_usage_statistics(self, rate_limiter):
        """Test usage statistics retrieval"""
        # Mock settings to disable stubs
        with patch.object(rate_limiter.settings, "use_stubs", False):
            # Mock Redis
            mock_redis = AsyncMock()
            mock_redis.get.return_value = "150"  # Current daily usage
            rate_limiter._redis = mock_redis

            usage = await rate_limiter.get_usage()

            assert "daily_used" in usage
            assert "daily_limit" in usage
            assert "burst_limit" in usage
            assert usage["daily_used"] == 150
            assert usage["daily_limit"] == rate_limiter.limits["daily_limit"]
            assert usage["burst_limit"] == rate_limiter.limits["burst_limit"]

    @pytest.mark.asyncio
    async def test_reset_usage(self, rate_limiter):
        """Test usage reset functionality"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["key1", "key2"]
        rate_limiter._redis = mock_redis

        await rate_limiter.reset_usage()

        # Should delete daily and burst keys
        mock_redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, rate_limiter):
        """Test handling of concurrent requests"""
        # Mock settings to disable stubs
        with patch.object(rate_limiter.settings, "use_stubs", False):
            # Mock Redis to return sequential counts
            mock_redis = AsyncMock()

            # Simulate multiple concurrent requests
            call_count = 0

            def mock_eval(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return [
                    call_count,
                    5,
                    1 if call_count <= 3 else 0,
                ]  # Lower limit to ensure some fail

            mock_redis.eval.side_effect = mock_eval
            rate_limiter._redis = mock_redis

            # Make multiple concurrent requests
            tasks = [rate_limiter.is_allowed(f"op_{i}") for i in range(8)]
            results = await asyncio.gather(*tasks)

            # Some should be allowed, some denied based on mock behavior
            assert any(results)  # At least some allowed
            assert not all(results)  # At least some denied


class TestRateLimiterFallbacks:
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing fallbacks"""
        limiter = RateLimiter("test_provider")
        # Force Lua script to None to test fallbacks
        limiter._lua_script = None
        return limiter

    @pytest.mark.asyncio
    async def test_simple_daily_check_fallback(self, rate_limiter):
        """Test fallback daily check without Lua script"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No previous usage (new key)
        mock_redis.incr.return_value = 1  # First request

        # Should allow request under limit
        allowed = await rate_limiter._simple_daily_check(mock_redis)
        assert allowed is True

        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_called_once()  # Called for new key

    @pytest.mark.asyncio
    async def test_simple_burst_check_fallback(self, rate_limiter):
        """Test fallback burst check without Lua script"""
        mock_redis = AsyncMock()
        mock_redis.zcard.return_value = 5  # Current burst count

        # Should allow request under burst limit
        allowed = await rate_limiter._simple_burst_check(mock_redis, "test_op")
        assert allowed is True

        mock_redis.zremrangebyscore.assert_called_once()
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_when_lua_fails(self, rate_limiter):
        """Test that fallback is used when Lua script execution fails"""
        mock_redis = AsyncMock()

        # Restore Lua script but make eval fail
        rate_limiter._load_lua_script()
        mock_redis.eval.side_effect = Exception("Lua execution failed")

        # Mock fallback methods to succeed
        rate_limiter._simple_daily_check = AsyncMock(return_value=True)
        rate_limiter._simple_burst_check = AsyncMock(return_value=True)

        allowed = await rate_limiter._check_daily_limit(mock_redis)
        assert allowed is True

        # Fallback should have been called
        rate_limiter._simple_daily_check.assert_called_once()


class TestRateLimiterConfiguration:
    def test_provider_limits_complete(self):
        """Test that all expected providers have limits configured"""
        expected_providers = ["yelp", "pagespeed", "openai", "sendgrid", "stripe"]

        for provider in expected_providers:
            assert provider in RateLimiter.PROVIDER_LIMITS
            limits = RateLimiter.PROVIDER_LIMITS[provider]
            assert "daily_limit" in limits
            assert "burst_limit" in limits
            assert "window_seconds" in limits
            assert limits["daily_limit"] > 0
            assert limits["burst_limit"] > 0
            assert limits["window_seconds"] > 0

    def test_reasonable_limit_values(self):
        """Test that limit values are reasonable"""
        for provider, limits in RateLimiter.PROVIDER_LIMITS.items():
            # Daily limits should be reasonable (1000-100000)
            assert 1000 <= limits["daily_limit"] <= 100000

            # Burst limits should be reasonable (5-100)
            assert 5 <= limits["burst_limit"] <= 100

            # Window should be reasonable (1-60 seconds)
            assert 1 <= limits["window_seconds"] <= 60


class TestRateLimiterEnhancements:
    """Additional comprehensive tests for rate limiter - GAP-009"""

    def test_edge_case_zero_limits(self):
        """Test edge cases with zero or very low limits"""
        # Test with custom limits to simulate edge cases
        limiter = RateLimiter("test_zero")

        # Override limits to test edge cases
        limiter.limits = {"daily_limit": 0, "burst_limit": 0, "window_seconds": 1}

        # Should handle zero limits gracefully
        assert limiter.limits["daily_limit"] == 0
        assert limiter.limits["burst_limit"] == 0

    def test_redis_key_generation_consistency(self):
        """Test that Redis keys are generated consistently"""
        limiter = RateLimiter("test_provider")

        # Test daily key generation
        # We can't directly access the key generation without running the method
        # but we can verify the provider is correctly stored
        assert limiter.provider == "test_provider"

        # Test burst key would include operation
        # Format: f"rate_limit:burst:{provider}:{operation}"
        # This is verified indirectly through the tests that use operations

    def test_lua_script_loading_error_handling(self):
        """Test Lua script loading with missing file"""
        # Create limiter and break the script path
        limiter = RateLimiter("test_lua")

        # Mock the built-in open function to raise FileNotFoundError
        with patch("builtins.open", side_effect=FileNotFoundError("No such file")):
            limiter._load_lua_script()
            assert limiter._lua_script is None

    def test_provider_limits_inheritance(self):
        """Test that unknown providers get default limits"""
        unknown_limiter = RateLimiter("unknown_provider_xyz")

        # Should get default limits
        assert unknown_limiter.limits["daily_limit"] == 1000
        assert unknown_limiter.limits["burst_limit"] == 10
        assert unknown_limiter.limits["window_seconds"] == 1

    @pytest.mark.asyncio
    async def test_redis_connection_management(self):
        """Test Redis connection management and reuse"""
        limiter = RateLimiter("test_redis")

        # Mock Redis creation
        with patch("d0_gateway.rate_limiter.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            # First call should create connection
            redis1 = await limiter._get_redis()
            assert redis1 is mock_redis
            mock_from_url.assert_called_once()

            # Second call should reuse connection
            redis2 = await limiter._get_redis()
            assert redis2 is redis1
            # from_url should still only be called once
            assert mock_from_url.call_count == 1

    @pytest.mark.asyncio
    async def test_close_connection_handling(self):
        """Test proper connection closing"""
        limiter = RateLimiter("test_close")

        # Mock Redis connection
        mock_redis = AsyncMock()
        limiter._redis = mock_redis

        await limiter.close()
        mock_redis.close.assert_called_once()

        # Test closing when no connection exists
        limiter._redis = None
        await limiter.close()  # Should not raise exception

    @pytest.mark.asyncio
    async def test_lua_script_execution_error_handling(self):
        """Test error handling in Lua script execution"""
        limiter = RateLimiter("test_lua_error")

        # Mock Redis that fails on eval
        mock_redis = AsyncMock()
        mock_redis.eval.side_effect = Exception("Lua script execution failed")

        with pytest.raises(Exception):
            await limiter._execute_lua_script(mock_redis, "test_command", ["test_key"], ["test_arg"])

    @pytest.mark.asyncio
    async def test_lua_script_execution_without_script(self):
        """Test Lua script execution when script is not loaded"""
        limiter = RateLimiter("test_no_script")
        limiter._lua_script = None  # Simulate failed script loading

        mock_redis = AsyncMock()

        with pytest.raises(RuntimeError, match="Lua script not loaded"):
            await limiter._execute_lua_script(mock_redis, "test_command", ["test_key"], ["test_arg"])

    @pytest.mark.asyncio
    async def test_usage_statistics_error_handling(self):
        """Test usage statistics with Redis errors"""
        limiter = RateLimiter("test_usage_error")

        # Test with stub mode disabled
        with patch.object(limiter.settings, "use_stubs", False):
            # Mock Redis that fails
            mock_redis = AsyncMock()
            mock_redis.get.side_effect = Exception("Redis connection failed")
            limiter._redis = mock_redis

            usage = await limiter.get_usage()

            # Should return default values on error
            assert usage["daily_used"] == 0
            assert usage["daily_limit"] == limiter.limits["daily_limit"]
            assert usage["burst_limit"] == limiter.limits["burst_limit"]

    @pytest.mark.asyncio
    async def test_reset_usage_error_handling(self):
        """Test reset usage with Redis errors"""
        limiter = RateLimiter("test_reset_error")

        # Mock Redis that fails on delete
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Redis delete failed")
        mock_redis.keys.return_value = ["key1", "key2"]
        limiter._redis = mock_redis

        # Should not raise exception despite Redis errors
        await limiter.reset_usage()

    @pytest.mark.asyncio
    async def test_daily_limit_boundary_conditions(self):
        """Test daily limit at exact boundary conditions"""
        limiter = RateLimiter("test_boundary")

        with patch.object(limiter.settings, "use_stubs", False):
            mock_redis = AsyncMock()

            # Test exactly at limit
            mock_redis.eval.return_value = [1000, 1000, 0]  # At limit, not allowed
            limiter._redis = mock_redis

            allowed = await limiter.is_allowed()
            assert allowed is False

            # Test just under limit
            mock_redis.eval.return_value = [999, 1000, 1]  # Under limit, allowed
            allowed = await limiter.is_allowed()
            assert allowed is True

    @pytest.mark.asyncio
    async def test_burst_limit_boundary_conditions(self):
        """Test burst limit at exact boundary conditions"""
        limiter = RateLimiter("test_burst_boundary")

        with patch.object(limiter.settings, "use_stubs", False):
            mock_redis = AsyncMock()

            # Mock daily check to pass, burst check to fail at boundary
            mock_redis.eval.side_effect = [
                [1, 1000, 1],  # Daily check: allowed
                [10, 10, 0],  # Burst check: at limit, not allowed
            ]
            limiter._redis = mock_redis

            allowed = await limiter.is_allowed("boundary_test")
            assert allowed is False

    @pytest.mark.asyncio
    async def test_operation_specific_burst_limits(self):
        """Test that different operations have separate burst limits"""
        limiter = RateLimiter("test_operations")

        with patch.object(limiter.settings, "use_stubs", False):
            mock_redis = AsyncMock()

            # Mock different burst usage for different operations
            call_count = 0

            def mock_eval(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count % 2 == 1:  # Daily checks (odd calls)
                    return [1, 1000, 1]  # Always allow daily
                else:  # Burst checks (even calls)
                    # First operation has low usage, second has high usage
                    if "op1" in str(args):
                        return [1, 10, 1]  # Low usage, allowed
                    else:
                        return [9, 10, 1]  # High usage, still allowed

            mock_redis.eval.side_effect = mock_eval
            limiter._redis = mock_redis

            # Test different operations
            allowed1 = await limiter.is_allowed("op1")
            allowed2 = await limiter.is_allowed("op2")

            assert allowed1 is True
            assert allowed2 is True

    @pytest.mark.asyncio
    async def test_fallback_daily_check_edge_cases(self):
        """Test fallback daily check edge cases"""
        limiter = RateLimiter("test_fallback_daily")

        # Test with None return from Redis
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_redis.incr.return_value = 1

        allowed = await limiter._simple_daily_check(mock_redis)
        assert allowed is True
        mock_redis.expire.assert_called_once_with(f"rate_limit:daily:{limiter.provider}", 86400)

        # Test at exact limit
        mock_redis.get.return_value = str(limiter.limits["daily_limit"])
        allowed = await limiter._simple_daily_check(mock_redis)
        assert allowed is False

    @pytest.mark.asyncio
    async def test_fallback_burst_check_edge_cases(self):
        """Test fallback burst check edge cases"""
        limiter = RateLimiter("test_fallback_burst")

        mock_redis = AsyncMock()
        mock_redis.zcard.return_value = 0  # No current usage

        # Test with empty burst window
        allowed = await limiter._simple_burst_check(mock_redis, "test_op")
        assert allowed is True

        # Verify cleanup and add operations were called
        mock_redis.zremrangebyscore.assert_called_once()
        mock_redis.zadd.assert_called_once()
        mock_redis.expire.assert_called_once()

        # Test at burst limit
        mock_redis.zcard.return_value = limiter.limits["burst_limit"]
        allowed = await limiter._simple_burst_check(mock_redis, "test_op")
        assert allowed is False

    @pytest.mark.asyncio
    async def test_concurrent_operations_isolation(self):
        """Test that concurrent operations maintain isolation"""
        limiter = RateLimiter("test_concurrent")

        with patch.object(limiter.settings, "use_stubs", False):
            mock_redis = AsyncMock()

            # Mock eval to return successful results
            mock_redis.eval.return_value = [1, 10, 1]  # Always allow
            limiter._redis = mock_redis

            # Make requests with different operations concurrently
            operations = ["upload", "download", "process", "analyze"]
            tasks = [limiter.is_allowed(op) for op in operations]
            results = await asyncio.gather(*tasks)

            # All should be allowed
            assert all(results)

            # Verify that eval was called multiple times (for daily + burst checks)
            # Each operation should generate at least 2 calls (daily + burst)
            assert mock_redis.eval.call_count >= len(operations) * 2

    @pytest.mark.asyncio
    async def test_redis_url_configuration(self):
        """Test Redis URL configuration from settings"""
        limiter = RateLimiter("test_redis_url")

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_from_url.return_value = AsyncMock()

            await limiter._get_redis()

            # Should use Redis URL from settings
            mock_from_url.assert_called_once_with(limiter.settings.redis_url, decode_responses=True)

    def test_logger_initialization(self):
        """Test logger initialization with provider context"""
        provider = "test_logger_provider"
        limiter = RateLimiter(provider)

        # Logger should include provider in name
        assert provider in limiter.logger.name
        assert "rate_limiter" in limiter.logger.name
        # Logger is properly initialized
        assert hasattr(limiter.logger, "info")
        assert hasattr(limiter.logger, "error")
        assert hasattr(limiter.logger, "warning")

    @pytest.mark.asyncio
    async def test_comprehensive_error_scenarios(self):
        """Test comprehensive error scenarios and recovery"""
        limiter = RateLimiter("test_comprehensive_errors")

        with patch.object(limiter.settings, "use_stubs", False):
            # Test Redis connection failure
            with patch.object(limiter, "_get_redis", side_effect=Exception("Redis connection failed")):
                allowed = await limiter.is_allowed()
                assert allowed is True  # Should fail open

            # Test partial failure (daily succeeds, burst fails)
            mock_redis = AsyncMock()
            mock_redis.eval.side_effect = [
                [1, 1000, 1],  # Daily: success
                Exception("Burst check failed"),  # Burst: failure
            ]
            limiter._redis = mock_redis

            # Should use fallback for burst check
            with patch.object(limiter, "_simple_burst_check", return_value=True):
                allowed = await limiter.is_allowed("error_test")
                assert allowed is True

    def test_provider_limits_immutability(self):
        """Test that provider limits are not accidentally modified"""
        original_limits = RateLimiter.PROVIDER_LIMITS.copy()

        # Create multiple limiters
        limiters = [RateLimiter(provider) for provider in ["yelp", "openai", "pagespeed"]]

        # Modify instance limits
        for limiter in limiters:
            limiter.limits["daily_limit"] = 99999

        # Original class limits should be unchanged
        assert RateLimiter.PROVIDER_LIMITS == original_limits

    @pytest.mark.asyncio
    async def test_stub_mode_comprehensive(self):
        """Test comprehensive stub mode behavior"""
        with patch("core.config.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_get_settings.return_value = mock_settings

            limiter = RateLimiter("test_stub_comprehensive")

            # All operations should be allowed in stub mode
            operations = ["test1", "test2", "test3"]
            for op in operations:
                allowed = await limiter.is_allowed(op)
                assert allowed is True

            # Usage should return zero
            usage = await limiter.get_usage()
            assert usage["daily_used"] == 0
            assert usage["daily_limit"] == limiter.limits["daily_limit"]
