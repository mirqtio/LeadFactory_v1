"""
Unified Redis helper for agent coordination and state management
Based on GPT o3's recommendation for simple Redis helper with get/set/blpop functionality
"""
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import redis.asyncio as aioredis

from core.config import get_settings
from core.logging import get_logger


class RedisCoordinator:
    """
    Unified Redis interface for agent coordination and state management
    Provides simple set/get/blpop operations for all agents
    """

    def __init__(self, namespace: str = "leadfactory"):
        self.namespace = namespace
        self.settings = get_settings()
        self.logger = get_logger(f"redis.{namespace}", domain="coordination")

        # Redis connection
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        """Get Redis connection"""
        if self._redis is None:
            self._redis = aioredis.from_url(self.settings.redis_url, decode_responses=True)
        return self._redis

    def _key(self, key: str) -> str:
        """Add namespace prefix to key"""
        return f"{self.namespace}:{key}"

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a key-value pair in Redis

        Args:
            key: Redis key (will be namespaced)
            value: Value to store (will be JSON serialized)
            ttl: Time to live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        try:
            redis = await self._get_redis()
            serialized_value = json.dumps(value, default=str)

            if ttl:
                result = await redis.setex(self._key(key), ttl, serialized_value)
            else:
                result = await redis.set(self._key(key), serialized_value)

            self.logger.debug(f"Set key: {key} (TTL: {ttl})")
            return bool(result)

        except Exception as e:
            self.logger.error(f"Redis set error for key {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from Redis

        Args:
            key: Redis key (will be namespaced)

        Returns:
            Deserialized value or None if not found
        """
        try:
            redis = await self._get_redis()
            value = await redis.get(self._key(key))

            if value is None:
                return None

            return json.loads(value)

        except Exception as e:
            self.logger.error(f"Redis get error for key {key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """
        Delete a key from Redis

        Args:
            key: Redis key (will be namespaced)

        Returns:
            True if key was deleted, False otherwise
        """
        try:
            redis = await self._get_redis()
            result = await redis.delete(self._key(key))
            self.logger.debug(f"Deleted key: {key}")
            return bool(result)

        except Exception as e:
            self.logger.error(f"Redis delete error for key {key}: {e}")
            return False

    async def blpop(self, key: str, timeout: int = 0) -> Optional[Any]:
        """
        Blocking left pop from Redis list

        Args:
            key: Redis key (will be namespaced)
            timeout: Timeout in seconds (0 = block indefinitely)

        Returns:
            Popped value or None if timeout
        """
        try:
            redis = await self._get_redis()
            result = await redis.blpop(self._key(key), timeout=timeout)

            if result is None:
                return None

            # result is (key, value) tuple
            _, value = result
            return json.loads(value)

        except Exception as e:
            self.logger.error(f"Redis blpop error for key {key}: {e}")
            return None

    async def lpush(self, key: str, value: Any) -> int:
        """
        Left push to Redis list

        Args:
            key: Redis key (will be namespaced)
            value: Value to push (will be JSON serialized)

        Returns:
            Length of list after push
        """
        try:
            redis = await self._get_redis()
            serialized_value = json.dumps(value, default=str)
            result = await redis.lpush(self._key(key), serialized_value)

            self.logger.debug(f"Pushed to list {key}, new length: {result}")
            return result

        except Exception as e:
            self.logger.error(f"Redis lpush error for key {key}: {e}")
            return 0

    async def setnx(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set key if not exists (distributed lock pattern)

        Args:
            key: Redis key (will be namespaced)
            value: Value to store (will be JSON serialized)
            ttl: Time to live in seconds (optional)

        Returns:
            True if key was set, False if already exists
        """
        try:
            redis = await self._get_redis()
            serialized_value = json.dumps(value, default=str)

            # Use SET with NX option
            result = await redis.set(self._key(key), serialized_value, nx=True, ex=ttl if ttl else None)

            success = result is not None
            if success:
                self.logger.debug(f"Acquired lock: {key} (TTL: {ttl})")
            else:
                self.logger.debug(f"Lock already held: {key}")

            return success

        except Exception as e:
            self.logger.error(f"Redis setnx error for key {key}: {e}")
            return False

    async def keys(self, pattern: str) -> List[str]:
        """
        Get keys matching pattern

        Args:
            pattern: Redis key pattern (will be namespaced)

        Returns:
            List of matching keys (without namespace prefix)
        """
        try:
            redis = await self._get_redis()
            namespaced_pattern = self._key(pattern)
            keys = await redis.keys(namespaced_pattern)

            # Remove namespace prefix from returned keys
            prefix = f"{self.namespace}:"
            return [key.replace(prefix, "", 1) for key in keys]

        except Exception as e:
            self.logger.error(f"Redis keys error for pattern {pattern}: {e}")
            return []

    async def exists(self, key: str) -> bool:
        """
        Check if key exists

        Args:
            key: Redis key (will be namespaced)

        Returns:
            True if key exists, False otherwise
        """
        try:
            redis = await self._get_redis()
            result = await redis.exists(self._key(key))
            return bool(result)

        except Exception as e:
            self.logger.error(f"Redis exists error for key {key}: {e}")
            return False

    async def ttl(self, key: str) -> int:
        """
        Get time to live for key

        Args:
            key: Redis key (will be namespaced)

        Returns:
            TTL in seconds (-1 if no expiry, -2 if key doesn't exist)
        """
        try:
            redis = await self._get_redis()
            result = await redis.ttl(self._key(key))
            return result

        except Exception as e:
            self.logger.error(f"Redis ttl error for key {key}: {e}")
            return -2

    async def ping(self) -> bool:
        """
        Ping Redis to check connectivity

        Returns:
            True if Redis responds, False otherwise
        """
        try:
            redis = await self._get_redis()
            result = await redis.ping()
            return result

        except Exception as e:
            self.logger.error(f"Redis ping error: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self.logger.debug("Closed Redis connection")


# Convenience functions for specific coordination patterns
class PRPStateRedis(RedisCoordinator):
    """Redis helper for PRP state management"""

    def __init__(self):
        super().__init__("prp")

    async def set_prp_state(self, prp_id: str, state: str, owner: str = None) -> bool:
        """Set PRP state and owner"""
        timestamp = datetime.now(timezone.utc).isoformat()
        prp_data = {"state": state, "owner": owner, "updated_at": timestamp}
        return await self.set(f"{prp_id}:state", prp_data)

    async def get_prp_state(self, prp_id: str) -> Optional[Dict[str, Any]]:
        """Get PRP state data"""
        return await self.get(f"{prp_id}:state")

    async def add_to_integration_queue(self, prp_id: str) -> int:
        """Add PRP to integration queue"""
        return await self.lpush("integration:queue", prp_id)

    async def get_next_for_integration(self, timeout: int = 0) -> Optional[str]:
        """Get next PRP from integration queue (blocking)"""
        return await self.blpop("integration:queue", timeout)

    async def acquire_merge_lock(self, prp_id: str, ttl: int = 3600) -> bool:
        """Acquire merge lock for PRP"""
        return await self.setnx("merge:lock", prp_id, ttl)

    async def release_merge_lock(self) -> bool:
        """Release merge lock"""
        return await self.delete("merge:lock")

    async def get_merge_lock_owner(self) -> Optional[str]:
        """Get current merge lock owner"""
        return await self.get("merge:lock")


class AgentStateRedis(RedisCoordinator):
    """Redis helper for agent state management"""

    def __init__(self):
        super().__init__("agent")

    async def set_agent_status(self, agent_id: str, status: str, current_prp: str = None) -> bool:
        """Set agent status and current PRP"""
        timestamp = datetime.now(timezone.utc).isoformat()
        agent_data = {"status": status, "current_prp": current_prp, "updated_at": timestamp}
        return await self.set(f"{agent_id}:status", agent_data)

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent status data"""
        return await self.get(f"{agent_id}:status")

    async def heartbeat(self, agent_id: str) -> bool:
        """Send agent heartbeat"""
        timestamp = datetime.now(timezone.utc).isoformat()
        return await self.set(f"{agent_id}:heartbeat", timestamp, ttl=300)  # 5 min TTL

    async def get_all_agents(self) -> List[Dict[str, Any]]:
        """Get status of all agents"""
        agent_keys = await self.keys("*:status")
        agents = []

        for key in agent_keys:
            agent_id = key.replace(":status", "")
            status = await self.get_agent_status(agent_id)
            if status:
                status["agent_id"] = agent_id
                agents.append(status)

        return agents


# Singleton instances for easy import
prp_redis = PRPStateRedis()
agent_redis = AgentStateRedis()


# Simple synchronous wrapper for non-async contexts
class SyncRedisHelper:
    """
    Synchronous wrapper for Redis operations
    For use in scripts and non-async contexts
    """

    def __init__(self, namespace: str = "leadfactory"):
        self.namespace = namespace
        self.settings = get_settings()
        self.redis = None

    def _get_redis(self):
        """Get synchronous Redis connection"""
        if self.redis is None:
            import redis

            self.redis = redis.from_url(self.settings.redis_url, decode_responses=True)
        return self.redis

    def _key(self, key: str) -> str:
        """Add namespace prefix to key"""
        return f"{self.namespace}:{key}"

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set key-value pair"""
        try:
            redis = self._get_redis()
            serialized_value = json.dumps(value, default=str)

            if ttl:
                result = redis.setex(self._key(key), ttl, serialized_value)
            else:
                result = redis.set(self._key(key), serialized_value)

            return bool(result)
        except Exception:
            return False

    def get(self, key: str) -> Optional[Any]:
        """Get value from Redis"""
        try:
            redis = self._get_redis()
            value = redis.get(self._key(key))

            if value is None:
                return None

            return json.loads(value)
        except Exception:
            return None

    def blpop(self, key: str, timeout: int = 0) -> Optional[Any]:
        """Blocking left pop"""
        try:
            redis = self._get_redis()
            result = redis.blpop(self._key(key), timeout=timeout)

            if result is None:
                return None

            _, value = result
            return json.loads(value)
        except Exception:
            return None

    def lpush(self, key: str, value: Any) -> int:
        """Left push to list"""
        try:
            redis = self._get_redis()
            serialized_value = json.dumps(value, default=str)
            return redis.lpush(self._key(key), serialized_value)
        except Exception:
            return 0

    def setnx(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set if not exists"""
        try:
            redis = self._get_redis()
            serialized_value = json.dumps(value, default=str)

            result = redis.set(self._key(key), serialized_value, nx=True, ex=ttl if ttl else None)

            return result is not None
        except Exception:
            return False


# Singleton for sync operations
sync_redis = SyncRedisHelper()
