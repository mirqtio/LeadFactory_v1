"""
Response caching for external API calls with Redis backing
"""
import hashlib
import json
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from core.config import get_settings
from core.logging import get_logger


class ResponseCache:
    """Redis-backed response cache for API calls"""

    # Provider-specific cache TTL (time to live) in seconds
    CACHE_TTL = {
        "pagespeed": 7200,  # 2 hours for performance data
        "openai": 86400,  # 24 hours for AI insights
        "sendgrid": 300,  # 5 minutes for email status
        "stripe": 300,  # 5 minutes for payment data
        "places": 3600,  # 1 hour for place data
    }

    def __init__(self, provider: str):
        self.provider = provider
        self.settings = get_settings()
        self.logger = get_logger(f"cache.{provider}", domain="d0")

        # Get provider-specific TTL or use default
        self.ttl = self.CACHE_TTL.get(provider, 1800)  # 30 min default

        # Redis connection
        self._redis: Optional[aioredis.Redis] = None

        # Hit/miss tracking
        self._hits = 0
        self._misses = 0

    async def _get_redis(self) -> aioredis.Redis:
        """Get Redis connection"""
        if self._redis is None:
            self._redis = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    def generate_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """
        Generate a cache key from endpoint and parameters

        Args:
            endpoint: API endpoint path
            params: Request parameters

        Returns:
            Cache key string
        """
        # Create a deterministic hash from endpoint and sorted params
        params_str = json.dumps(params, sort_keys=True, separators=(",", ":"))
        content = f"{self.provider}:{endpoint}:{params_str}"

        # Use SHA-256 hash for consistent key length
        cache_key = hashlib.sha256(content.encode()).hexdigest()

        return f"api_cache:{cache_key}"

    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Get cached response

        Args:
            cache_key: Cache key

        Returns:
            Cached response data or None if not found
        """
        # Skip caching when using stubs for testing
        if self.settings.use_stubs:
            return None

        try:
            redis = await self._get_redis()
            cached_data = await redis.get(cache_key)

            if cached_data:
                response = json.loads(cached_data)
                self._hits += 1
                self.logger.debug(f"Cache hit for key: {cache_key[:16]}...")
                return response
            else:
                self._misses += 1
                self.logger.debug(f"Cache miss for key: {cache_key[:16]}...")
                return None

        except Exception as e:
            self.logger.error(f"Cache get error: {e}")
            self._misses += 1
            return None

    async def set(self, cache_key: str, response_data: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Cache response data

        Args:
            cache_key: Cache key
            response_data: Response data to cache
            ttl: Time to live in seconds (uses provider default if None)
        """
        # Skip caching when using stubs
        if self.settings.use_stubs:
            return

        try:
            redis = await self._get_redis()

            # Serialize response data
            cached_data = json.dumps(response_data, separators=(",", ":"))

            # Use provided TTL or provider default
            cache_ttl = ttl or self.ttl

            # Store in Redis with expiration
            await redis.setex(cache_key, cache_ttl, cached_data)

            self.logger.debug(f"Cached response for key: {cache_key[:16]}... (TTL: {cache_ttl}s)")

        except Exception as e:
            self.logger.error(f"Cache set error: {e}")

    async def delete(self, cache_key: str) -> None:
        """
        Delete cached response

        Args:
            cache_key: Cache key to delete
        """
        try:
            redis = await self._get_redis()
            await redis.delete(cache_key)
            self.logger.debug(f"Deleted cache key: {cache_key[:16]}...")

        except Exception as e:
            self.logger.error(f"Cache delete error: {e}")

    async def clear_provider_cache(self) -> int:
        """
        Clear all cache entries for this provider

        Returns:
            Number of keys deleted
        """
        try:
            redis = await self._get_redis()

            # Find all keys for this provider
            pattern = f"api_cache:*{self.provider}*"
            keys = await redis.keys(pattern)

            if keys:
                deleted = await redis.delete(*keys)
                self.logger.info(f"Cleared {deleted} cache entries for {self.provider}")
                return deleted
            else:
                self.logger.debug(f"No cache entries found for {self.provider}")
                return 0

        except Exception as e:
            self.logger.error(f"Cache clear error: {e}")
            return 0

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics for this provider

        Returns:
            Cache statistics
        """
        try:
            redis = await self._get_redis()

            # Count keys for this provider
            pattern = f"api_cache:*{self.provider}*"
            keys = await redis.keys(pattern)

            # Get memory usage info
            info = await redis.info("memory")

            # Calculate hit rate
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0

            return {
                "provider": self.provider,
                "cached_keys": len(keys),
                "ttl_seconds": self.ttl,
                "redis_memory_used": info.get("used_memory_human", "unknown"),
                "redis_connected": True,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 3),
                "total_requests": total_requests,
            }

        except Exception as e:
            self.logger.error(f"Cache stats error: {e}")
            return {
                "provider": self.provider,
                "cached_keys": 0,
                "ttl_seconds": self.ttl,
                "redis_connected": False,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": 0,
                "total_requests": self._hits + self._misses,
                "error": str(e),
            }

    def reset_stats(self) -> None:
        """Reset hit/miss statistics"""
        self._hits = 0
        self._misses = 0
        self.logger.debug(f"Reset cache statistics for {self.provider}")

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
