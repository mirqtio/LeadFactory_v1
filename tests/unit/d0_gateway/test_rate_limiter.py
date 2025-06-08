"""
Test token bucket rate limiter
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

from d0_gateway.rate_limiter import RateLimiter


class TestRateLimiter:
    
    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter for testing"""
        return RateLimiter("test_provider")
    
    def test_token_bucket_algorithm_config(self, rate_limiter):
        """Test that token bucket algorithm is configured correctly"""
        # Should have provider-specific limits
        assert hasattr(rate_limiter, 'limits')
        assert 'daily_limit' in rate_limiter.limits
        assert 'burst_limit' in rate_limiter.limits
        assert 'window_seconds' in rate_limiter.limits
        
        # Test default limits for unknown provider
        assert rate_limiter.limits['daily_limit'] == 1000
        assert rate_limiter.limits['burst_limit'] == 10
        assert rate_limiter.limits['window_seconds'] == 1
    
    def test_provider_specific_limits(self):
        """Test that provider-specific limits work"""
        # Test Yelp limits
        yelp_limiter = RateLimiter("yelp")
        assert yelp_limiter.limits['daily_limit'] == 5000
        assert yelp_limiter.limits['burst_limit'] == 10
        
        # Test PageSpeed limits
        pagespeed_limiter = RateLimiter("pagespeed")
        assert pagespeed_limiter.limits['daily_limit'] == 25000
        assert pagespeed_limiter.limits['burst_limit'] == 50
        
        # Test OpenAI limits
        openai_limiter = RateLimiter("openai")
        assert openai_limiter.limits['daily_limit'] == 10000
        assert openai_limiter.limits['burst_limit'] == 20
    
    def test_redis_based_implementation(self, rate_limiter):
        """Test that Redis-based implementation is configured"""
        # Should have Redis connection capability
        assert hasattr(rate_limiter, '_redis')
        assert hasattr(rate_limiter, '_get_redis')
        
        # Should be able to get Redis connection
        assert asyncio.iscoroutinefunction(rate_limiter._get_redis)
    
    def test_lua_script_loading(self, rate_limiter):
        """Test that Lua script is loaded"""
        # Should have Lua script loaded
        assert hasattr(rate_limiter, '_lua_script')
        assert rate_limiter._lua_script is not None
        assert isinstance(rate_limiter._lua_script, str)
        
        # Script should contain expected functions
        assert 'check_daily_limit' in rate_limiter._lua_script
        assert 'check_burst_limit' in rate_limiter._lua_script
        assert 'check_combined_limits' in rate_limiter._lua_script
    
    @pytest.mark.asyncio
    async def test_atomic_operations_via_lua(self, rate_limiter):
        """Test that atomic operations work via Lua"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.eval.return_value = [1, 10, 1]  # current, limit, allowed
        
        rate_limiter._redis = mock_redis
        
        # Test executing Lua script
        result = await rate_limiter._execute_lua_script(
            mock_redis,
            "check_daily",
            ["test_key"],
            ["10", "86400"]
        )
        
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
        assert yelp_limiter.limits['daily_limit'] != pagespeed_limiter.limits['daily_limit']
        assert yelp_limiter.limits['burst_limit'] != openai_limiter.limits['burst_limit']
        
        # Verify specific expected values
        assert yelp_limiter.limits['daily_limit'] == 5000
        assert pagespeed_limiter.limits['daily_limit'] == 25000
        assert openai_limiter.limits['daily_limit'] == 10000
    
    @pytest.mark.asyncio
    async def test_daily_limit_enforcement(self, rate_limiter):
        """Test daily limit enforcement"""
        # Mock settings to disable stubs
        with patch.object(rate_limiter.settings, 'use_stubs', False):
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
        with patch.object(rate_limiter.settings, 'use_stubs', False):
            # Mock Redis: daily OK, burst exceeded
            mock_redis = AsyncMock()
            
            # First call (daily check) - allowed
            # Second call (burst check) - not allowed
            mock_redis.eval.side_effect = [
                [1, 1000, 1],    # Daily check: allowed
                [11, 10, 0]      # Burst check: exceeded
            ]
            rate_limiter._redis = mock_redis
            
            allowed = await rate_limiter.is_allowed("burst_test")
            assert allowed is False
    
    @pytest.mark.asyncio
    async def test_stub_mode_bypass(self):
        """Test that stub mode bypasses rate limiting"""
        with patch('core.config.get_settings') as mock_get_settings:
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
        with patch.object(rate_limiter.settings, 'use_stubs', False):
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
        with patch.object(rate_limiter.settings, 'use_stubs', False):
            # Mock Redis
            mock_redis = AsyncMock()
            mock_redis.get.return_value = "150"  # Current daily usage
            rate_limiter._redis = mock_redis
            
            usage = await rate_limiter.get_usage()
            
            assert 'daily_used' in usage
            assert 'daily_limit' in usage
            assert 'burst_limit' in usage
            assert usage['daily_used'] == 150
            assert usage['daily_limit'] == rate_limiter.limits['daily_limit']
            assert usage['burst_limit'] == rate_limiter.limits['burst_limit']
    
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
        with patch.object(rate_limiter.settings, 'use_stubs', False):
            # Mock Redis to return sequential counts
            mock_redis = AsyncMock()
            
            # Simulate multiple concurrent requests
            call_count = 0
            def mock_eval(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return [call_count, 5, 1 if call_count <= 3 else 0]  # Lower limit to ensure some fail
            
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
        mock_redis.incr.return_value = 1    # First request
        
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
        expected_providers = ['yelp', 'pagespeed', 'openai', 'sendgrid', 'stripe']
        
        for provider in expected_providers:
            assert provider in RateLimiter.PROVIDER_LIMITS
            limits = RateLimiter.PROVIDER_LIMITS[provider]
            assert 'daily_limit' in limits
            assert 'burst_limit' in limits
            assert 'window_seconds' in limits
            assert limits['daily_limit'] > 0
            assert limits['burst_limit'] > 0
            assert limits['window_seconds'] > 0
    
    def test_reasonable_limit_values(self):
        """Test that limit values are reasonable"""
        for provider, limits in RateLimiter.PROVIDER_LIMITS.items():
            # Daily limits should be reasonable (1000-100000)
            assert 1000 <= limits['daily_limit'] <= 100000
            
            # Burst limits should be reasonable (5-100)
            assert 5 <= limits['burst_limit'] <= 100
            
            # Window should be reasonable (1-60 seconds)
            assert 1 <= limits['window_seconds'] <= 60