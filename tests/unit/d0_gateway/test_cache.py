"""
Test response cache system
"""
import pytest
import json
import time
from unittest.mock import AsyncMock, Mock, patch

from d0_gateway.cache import ResponseCache


class TestResponseCache:
    
    @pytest.fixture
    def cache(self):
        """Create cache for testing"""
        return ResponseCache("test_provider")
    
    def test_redis_based_caching_config(self, cache):
        """Test that Redis-based caching is configured"""
        # Should have Redis connection capability
        assert hasattr(cache, '_redis')
        assert hasattr(cache, '_get_redis')
        
        # Should have provider-specific configuration
        assert cache.provider == "test_provider"
        assert hasattr(cache, 'ttl')
        assert cache.ttl > 0
    
    def test_ttl_configuration_per_provider(self):
        """Test TTL configuration per provider"""
        # Test specific provider TTL configurations
        yelp_cache = ResponseCache("yelp")
        assert yelp_cache.ttl == 3600  # 1 hour
        
        pagespeed_cache = ResponseCache("pagespeed")
        assert pagespeed_cache.ttl == 7200  # 2 hours
        
        openai_cache = ResponseCache("openai")
        assert openai_cache.ttl == 86400  # 24 hours
        
        sendgrid_cache = ResponseCache("sendgrid")
        assert sendgrid_cache.ttl == 300  # 5 minutes
        
        stripe_cache = ResponseCache("stripe")
        assert stripe_cache.ttl == 300  # 5 minutes
        
        # Test default TTL for unknown provider
        unknown_cache = ResponseCache("unknown_provider")
        assert unknown_cache.ttl == 1800  # 30 minutes default
    
    def test_cache_key_generation(self, cache):
        """Test cache key generation"""
        # Test deterministic key generation
        params1 = {"term": "restaurant", "location": "90210"}
        params2 = {"location": "90210", "term": "restaurant"}  # Different order
        
        key1 = cache.generate_key("/search", params1)
        key2 = cache.generate_key("/search", params2)
        
        # Keys should be identical despite parameter order
        assert key1 == key2
        
        # Keys should be consistent
        key3 = cache.generate_key("/search", params1)
        assert key1 == key3
        
        # Different parameters should generate different keys
        params3 = {"term": "restaurant", "location": "10001"}
        key4 = cache.generate_key("/search", params3)
        assert key1 != key4
        
        # Key should be prefixed and have expected format
        assert key1.startswith("api_cache:")
        assert len(key1) > 20  # Should be reasonably long hash
    
    @pytest.mark.asyncio
    async def test_hit_miss_tracking_cache_get(self, cache):
        """Test cache get operation and hit/miss tracking"""
        # Mock settings to disable stubs
        with patch.object(cache.settings, 'use_stubs', False):
            # Mock Redis
            mock_redis = AsyncMock()
            cache._redis = mock_redis
            
            # Test cache miss
            mock_redis.get.return_value = None
            result = await cache.get("test_key")
            assert result is None
            mock_redis.get.assert_called_once_with("test_key")
            assert cache._misses == 1
            assert cache._hits == 0
            
            # Test cache hit
            mock_redis.reset_mock()
            cached_data = {"status": "success", "data": "test_value"}
            mock_redis.get.return_value = json.dumps(cached_data)
            
            result = await cache.get("test_key")
            assert result == cached_data
            mock_redis.get.assert_called_once_with("test_key")
            assert cache._hits == 1
            assert cache._misses == 1
    
    @pytest.mark.asyncio
    async def test_cache_set_operation(self, cache):
        """Test cache set operation"""
        # Mock settings to disable stubs
        with patch.object(cache.settings, 'use_stubs', False):
            # Mock Redis
            mock_redis = AsyncMock()
            cache._redis = mock_redis
            
            # Test setting cache with default TTL
            response_data = {"status": "success", "data": "test_value"}
            await cache.set("test_key", response_data)
            
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            
            # Verify key, ttl, and serialized data
            assert call_args[0][0] == "test_key"
            assert call_args[0][1] == cache.ttl  # Default TTL
            assert json.loads(call_args[0][2]) == response_data
            
            # Test setting cache with custom TTL
            mock_redis.reset_mock()
            custom_ttl = 7200
            await cache.set("test_key_2", response_data, ttl=custom_ttl)
            
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == custom_ttl
    
    @pytest.mark.asyncio
    async def test_cache_delete_operation(self, cache):
        """Test cache delete operation"""
        # Mock Redis
        mock_redis = AsyncMock()
        cache._redis = mock_redis
        
        await cache.delete("test_key")
        mock_redis.delete.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_provider_cache_clearing(self, cache):
        """Test clearing all cache entries for provider"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["key1", "key2", "key3"]
        mock_redis.delete.return_value = 3
        cache._redis = mock_redis
        
        deleted_count = await cache.clear_provider_cache()
        
        # Should search for provider-specific keys
        mock_redis.keys.assert_called_once()
        pattern = mock_redis.keys.call_args[0][0]
        assert "test_provider" in pattern
        
        # Should delete found keys
        mock_redis.delete.assert_called_once_with("key1", "key2", "key3")
        assert deleted_count == 3
    
    @pytest.mark.asyncio
    async def test_cache_stats_retrieval(self, cache):
        """Test cache statistics retrieval"""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["key1", "key2"]
        mock_redis.info.return_value = {"used_memory_human": "1.5M"}
        cache._redis = mock_redis
        
        stats = await cache.get_cache_stats()
        
        # Verify stats structure
        assert stats['provider'] == "test_provider"
        assert stats['cached_keys'] == 2
        assert stats['ttl_seconds'] == cache.ttl
        assert stats['redis_memory_used'] == "1.5M"
        assert stats['redis_connected'] is True
    
    @pytest.mark.asyncio
    async def test_stub_mode_bypass(self):
        """Test that stub mode bypasses caching"""
        with patch('core.config.get_settings') as mock_get_settings:
            mock_settings = Mock()
            mock_settings.use_stubs = True
            mock_get_settings.return_value = mock_settings
            
            cache = ResponseCache("test")
            
            # Get should return None in stub mode
            result = await cache.get("any_key")
            assert result is None
            
            # Set should do nothing in stub mode (no exception)
            await cache.set("any_key", {"data": "test"})
    
    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self, cache):
        """Test handling of Redis connection errors"""
        # Mock Redis to raise connection error
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis connection failed")
        cache._redis = mock_redis
        
        # Should handle error gracefully and return None
        result = await cache.get("test_key")
        assert result is None
        
        # Set should handle error gracefully (no exception)
        await cache.set("test_key", {"data": "test"})
        
        # Stats should handle error and include error info
        mock_redis.info.side_effect = Exception("Redis connection failed")
        stats = await cache.get_cache_stats()
        assert stats['redis_connected'] is False
        assert 'error' in stats
    
    @pytest.mark.asyncio
    async def test_redis_connection_lifecycle(self, cache):
        """Test Redis connection lifecycle"""
        # Initially no connection
        assert cache._redis is None
        
        # Mock Redis connection
        with patch('d0_gateway.cache.aioredis.from_url') as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis
            
            # Getting Redis should create connection
            redis = await cache._get_redis()
            assert redis == mock_redis
            assert cache._redis == mock_redis
            
            # Subsequent calls should reuse connection
            redis2 = await cache._get_redis()
            assert redis2 == mock_redis
            assert mock_from_url.call_count == 1
    
    @pytest.mark.asyncio
    async def test_cache_close_connection(self, cache):
        """Test closing Redis connection"""
        # Mock Redis connection
        mock_redis = AsyncMock()
        cache._redis = mock_redis
        
        await cache.close()
        mock_redis.close.assert_called_once()
    
    def test_reset_stats(self, cache):
        """Test resetting hit/miss statistics"""
        # Set some stats
        cache._hits = 10
        cache._misses = 5
        
        # Reset stats
        cache.reset_stats()
        
        # Should be reset to zero
        assert cache._hits == 0
        assert cache._misses == 0


class TestCacheKeyGeneration:
    
    @pytest.fixture
    def cache(self):
        return ResponseCache("test_provider")
    
    def test_deterministic_key_generation(self, cache):
        """Test that key generation is deterministic"""
        params = {"term": "restaurant", "location": "90210", "limit": 20}
        
        # Generate key multiple times
        key1 = cache.generate_key("/search", params)
        key2 = cache.generate_key("/search", params)
        key3 = cache.generate_key("/search", params)
        
        # All keys should be identical
        assert key1 == key2 == key3
    
    def test_parameter_order_independence(self, cache):
        """Test that parameter order doesn't affect key"""
        params1 = {"a": 1, "b": 2, "c": 3}
        params2 = {"c": 3, "a": 1, "b": 2}
        params3 = {"b": 2, "c": 3, "a": 1}
        
        key1 = cache.generate_key("/test", params1)
        key2 = cache.generate_key("/test", params2)
        key3 = cache.generate_key("/test", params3)
        
        assert key1 == key2 == key3
    
    def test_different_endpoints_different_keys(self, cache):
        """Test that different endpoints generate different keys"""
        params = {"term": "restaurant"}
        
        key1 = cache.generate_key("/search", params)
        key2 = cache.generate_key("/details", params)
        
        assert key1 != key2
    
    def test_different_params_different_keys(self, cache):
        """Test that different parameters generate different keys"""
        key1 = cache.generate_key("/search", {"term": "restaurant"})
        key2 = cache.generate_key("/search", {"term": "cafe"})
        key3 = cache.generate_key("/search", {"term": "restaurant", "limit": 10})
        
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3
    
    def test_provider_specific_keys(self):
        """Test that different providers generate different keys"""
        params = {"term": "restaurant"}
        endpoint = "/search"
        
        cache1 = ResponseCache("yelp")
        cache2 = ResponseCache("places")
        
        key1 = cache1.generate_key(endpoint, params)
        key2 = cache2.generate_key(endpoint, params)
        
        assert key1 != key2
    
    def test_key_format_consistency(self, cache):
        """Test cache key format is consistent"""
        key = cache.generate_key("/test", {"param": "value"})
        
        # Should start with expected prefix
        assert key.startswith("api_cache:")
        
        # Should be hex string after prefix
        hash_part = key.replace("api_cache:", "")
        assert len(hash_part) == 64  # SHA-256 produces 64 char hex string
        assert all(c in "0123456789abcdef" for c in hash_part)


class TestCacheIntegration:
    
    @pytest.mark.asyncio
    async def test_full_cache_workflow(self):
        """Test complete cache workflow"""
        cache = ResponseCache("test_provider")
        
        # Mock settings to disable stubs
        with patch.object(cache.settings, 'use_stubs', False):
            # Mock Redis for full workflow
            mock_redis = AsyncMock()
            cache._redis = mock_redis
            
            # 1. Generate cache key
            params = {"term": "restaurant", "location": "90210"}
            cache_key = cache.generate_key("/search", params)
            
            # 2. Initial cache miss
            mock_redis.get.return_value = None
            result = await cache.get(cache_key)
            assert result is None
            
            # 3. Set cache
            response_data = {"businesses": [{"name": "Test Restaurant"}]}
            await cache.set(cache_key, response_data)
            mock_redis.setex.assert_called_once()
            
            # 4. Cache hit
            mock_redis.get.return_value = json.dumps(response_data)
            result = await cache.get(cache_key)
            assert result == response_data
            
            # 5. Get stats
            mock_redis.keys.return_value = [cache_key]
            mock_redis.info.return_value = {"used_memory_human": "1M"}
            stats = await cache.get_cache_stats()
            assert stats['cached_keys'] == 1
            assert stats['provider'] == "test_provider"
            
            # 6. Clear cache
            mock_redis.delete.return_value = 1
            deleted = await cache.clear_provider_cache()
            assert deleted == 1
    
    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self):
        """Test concurrent cache operations"""
        import asyncio
        
        cache = ResponseCache("test_provider")
        
        # Mock settings to disable stubs
        with patch.object(cache.settings, 'use_stubs', False):
            mock_redis = AsyncMock()
            cache._redis = mock_redis
            
            # Mock responses for concurrent operations
            mock_redis.get.return_value = None
            mock_redis.setex.return_value = True
            
            # Simulate concurrent set operations
            tasks = []
            for i in range(10):
                task = cache.set(f"key_{i}", {"data": f"value_{i}"})
                tasks.append(task)
            
            # All should complete without error
            await asyncio.gather(*tasks)
            
            # Should have made 10 setex calls
            assert mock_redis.setex.call_count == 10
    
    @pytest.mark.asyncio
    async def test_cache_with_complex_data_types(self):
        """Test caching with complex data structures"""
        cache = ResponseCache("test_provider")
        
        # Mock settings to disable stubs
        with patch.object(cache.settings, 'use_stubs', False):
            mock_redis = AsyncMock()
            cache._redis = mock_redis
            
            # Complex data structure
            complex_data = {
                "businesses": [
                    {
                        "id": "abc123",
                        "name": "Test Restaurant",
                        "rating": 4.5,
                        "categories": ["restaurant", "italian"],
                        "location": {
                            "address": "123 Main St",
                            "coordinates": {"lat": 34.0522, "lng": -118.2437}
                        },
                        "reviews": [
                            {"text": "Great food!", "rating": 5},
                            {"text": "Good service", "rating": 4}
                        ]
                    }
                ],
                "total": 1,
                "region": {
                    "center": {"lat": 34.0522, "lng": -118.2437}
                }
            }
            
            # Set complex data
            await cache.set("complex_key", complex_data)
            
            # Verify serialization worked
            call_args = mock_redis.setex.call_args
            serialized_data = call_args[0][2]
            deserialized = json.loads(serialized_data)
            assert deserialized == complex_data
            
            # Test retrieval
            mock_redis.get.return_value = serialized_data
            result = await cache.get("complex_key")
            assert result == complex_data