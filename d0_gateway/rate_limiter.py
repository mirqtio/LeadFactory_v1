"""
Token bucket rate limiter with Redis backing for distributed rate limiting
"""
import asyncio
import time
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path

import redis.asyncio as aioredis
from core.config import get_settings
from core.logging import get_logger


class RateLimiter:
    """Token bucket rate limiter with Redis backing"""

    # Provider-specific rate limits
    PROVIDER_LIMITS = {
        'yelp': {
            'daily_limit': 5000,
            'burst_limit': 10,
            'window_seconds': 1
        },
        'pagespeed': {
            'daily_limit': 25000,
            'burst_limit': 50,
            'window_seconds': 1
        },
        'openai': {
            'daily_limit': 10000,
            'burst_limit': 20,
            'window_seconds': 1
        },
        'sendgrid': {
            'daily_limit': 100000,
            'burst_limit': 100,
            'window_seconds': 1
        },
        'stripe': {
            'daily_limit': 50000,
            'burst_limit': 25,
            'window_seconds': 1
        }
    }

    def __init__(self, provider: str):
        self.provider = provider
        self.settings = get_settings()
        self.logger = get_logger(f"rate_limiter.{provider}", domain="d0")

        # Get provider limits or use defaults
        self.limits = self.PROVIDER_LIMITS.get(provider, {
            'daily_limit': 1000,
            'burst_limit': 10,
            'window_seconds': 1
        })

        # Redis connection for distributed rate limiting
        self._redis: Optional[aioredis.Redis] = None
        self._lua_script: Optional[str] = None

        # Load Lua script
        self._load_lua_script()

    def _load_lua_script(self):
        """Load the Lua script for atomic rate limiting operations"""
        script_path = Path(__file__).parent / "lua_scripts" / "rate_limit.lua"
        try:
            with open(script_path, 'r') as f:
                self._lua_script = f.read()
            self.logger.debug("Loaded rate limiting Lua script")
        except Exception as e:
            self.logger.error(f"Failed to load Lua script: {e}")
            self._lua_script = None

    async def _get_redis(self) -> aioredis.Redis:
        """Get Redis connection"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                self.settings.redis_url,
                decode_responses=True
            )
        return self._redis

    async def _execute_lua_script(self, redis: aioredis.Redis, command: str, keys: list, args: list):
        """Execute Lua script with given command and parameters"""
        if not self._lua_script:
            raise RuntimeError("Lua script not loaded")

        # Command is the first argument
        script_args = [command] + args

        return await redis.eval(self._lua_script, len(keys), *keys, *script_args)

    async def is_allowed(self, operation: str = "default") -> bool:
        """
        Check if request is allowed within rate limits

        Args:
            operation: Specific operation being rate limited

        Returns:
            True if request is allowed, False if rate limited
        """
        # Skip rate limiting when using stubs
        if self.settings.use_stubs:
            return True

        try:
            redis = await self._get_redis()

            # Check both daily and burst limits
            daily_allowed = await self._check_daily_limit(redis)
            burst_allowed = await self._check_burst_limit(redis, operation)

            return daily_allowed and burst_allowed

        except Exception as e:
            self.logger.error(f"Rate limiter error: {e}")
            # Fail open - allow request if rate limiter fails
            return True

    async def _check_daily_limit(self, redis: aioredis.Redis) -> bool:
        """Check daily rate limit using external Lua script"""
        daily_key = f"rate_limit:daily:{self.provider}"

        try:
            # Use external Lua script for atomic check-and-increment
            result = await self._execute_lua_script(
                redis,
                "check_daily",
                [daily_key],
                [str(self.limits['daily_limit']), "86400"]  # 24 hours
            )

            current, limit, allowed = result

            if not allowed:
                self.logger.warning(
                    f"Daily rate limit exceeded: {current}/{limit} for {self.provider}"
                )

            return bool(allowed)

        except Exception as e:
            self.logger.error(f"Daily rate limit check failed: {e}")
            # Fallback to simple check without Lua script
            return await self._simple_daily_check(redis)

    async def _check_burst_limit(self, redis: aioredis.Redis, operation: str) -> bool:
        """Check burst rate limit using external Lua script"""
        burst_key = f"rate_limit:burst:{self.provider}:{operation}"
        window_seconds = self.limits['window_seconds']
        burst_limit = self.limits['burst_limit']

        try:
            # Use external Lua script for sliding window burst limiting
            now = time.time()
            result = await self._execute_lua_script(
                redis,
                "check_burst",
                [burst_key],
                [str(window_seconds), str(burst_limit), str(now)]
            )

            current, limit, allowed = result

            if not allowed:
                self.logger.warning(
                    f"Burst rate limit exceeded: {current}/{limit} for {self.provider}:{operation}"
                )

            return bool(allowed)

        except Exception as e:
            self.logger.error(f"Burst rate limit check failed: {e}")
            # Fallback to simple check without Lua script
            return await self._simple_burst_check(redis, operation)

    async def get_usage(self) -> Dict[str, int]:
        """Get current usage statistics"""
        if self.settings.use_stubs:
            return {
                'daily_used': 0,
                'daily_limit': self.limits['daily_limit'],
                'burst_limit': self.limits['burst_limit']
            }

        try:
            redis = await self._get_redis()

            # Get daily usage
            daily_key = f"rate_limit:daily:{self.provider}"
            daily_used = await redis.get(daily_key) or 0
            daily_used = int(daily_used)

            return {
                'daily_used': daily_used,
                'daily_limit': self.limits['daily_limit'],
                'burst_limit': self.limits['burst_limit'],
                'window_seconds': self.limits['window_seconds']
            }

        except Exception as e:
            self.logger.error(f"Failed to get usage: {e}")
            return {
                'daily_used': 0,
                'daily_limit': self.limits['daily_limit'],
                'burst_limit': self.limits['burst_limit']
            }

    async def reset_usage(self) -> None:
        """Reset usage counters (for testing)"""
        try:
            redis = await self._get_redis()

            # Reset daily counter
            daily_key = f"rate_limit:daily:{self.provider}"
            await redis.delete(daily_key)

            # Reset all burst counters for this provider
            pattern = f"rate_limit:burst:{self.provider}:*"
            keys = await redis.keys(pattern)
            if keys:
                await redis.delete(*keys)

            self.logger.info(f"Reset rate limits for {self.provider}")

        except Exception as e:
            self.logger.error(f"Failed to reset usage: {e}")

    async def _simple_daily_check(self, redis: aioredis.Redis) -> bool:
        """Fallback daily rate limit check without Lua script"""
        daily_key = f"rate_limit:daily:{self.provider}"

        try:
            current = await redis.get(daily_key) or 0
            current = int(current)

            if current >= self.limits['daily_limit']:
                return False

            # Simple increment (not atomic, but better than nothing)
            new_value = await redis.incr(daily_key)
            if new_value == 1:
                await redis.expire(daily_key, 86400)  # 24 hours

            return True

        except Exception as e:
            self.logger.error(f"Fallback daily check failed: {e}")
            return True  # Fail open

    async def _simple_burst_check(self, redis: aioredis.Redis, operation: str) -> bool:
        """Fallback burst rate limit check without Lua script"""
        burst_key = f"rate_limit:burst:{self.provider}:{operation}"

        try:
            now = time.time()
            window_start = now - self.limits['window_seconds']

            # Remove expired entries (not atomic)
            await redis.zremrangebyscore(burst_key, 0, window_start)

            # Check current count
            current = await redis.zcard(burst_key)

            if current >= self.limits['burst_limit']:
                return False

            # Add current request
            await redis.zadd(burst_key, {str(now): now})
            await redis.expire(burst_key, self.limits['window_seconds'] + 1)

            return True

        except Exception as e:
            self.logger.error(f"Fallback burst check failed: {e}")
            return True  # Fail open

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
