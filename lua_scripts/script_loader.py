"""
Redis Lua Script Loader with SHA caching and EVALSHA fallback
Implements optimized script loading and execution patterns for PRP promotion system
"""

import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

try:
    import redis.asyncio as aioredis
except ImportError:
    import redis as aioredis  # Fallback

from core.config import get_settings


class ScriptLoader:
    """Redis Lua script loader with SHA caching and automatic fallback"""

    def __init__(self, redis_client: Optional[aioredis.Redis] = None):
        self.settings = get_settings()
        self.logger = logging.getLogger(__name__)
        self._redis: Optional[aioredis.Redis] = redis_client
        self._script_cache: Dict[str, str] = {}  # script_name -> SHA hash
        self._script_source: Dict[str, str] = {}  # script_name -> Lua source

    async def get_redis(self) -> aioredis.Redis:
        """Get Redis connection (lazy initialization)"""
        if self._redis is None:
            self._redis = await aioredis.from_url(self.settings.redis_url, decode_responses=True, encoding="utf-8")
        return self._redis

    async def load_script(self, script_name: str, script_path: Optional[Path] = None) -> str:
        """
        Load Lua script and cache SHA hash

        Args:
            script_name: Name identifier for the script
            script_path: Optional path to script file. If None, uses redis/{script_name}.lua

        Returns:
            SHA hash of loaded script

        Raises:
            FileNotFoundError: If script file doesn't exist
            redis.RedisError: If script loading fails
        """
        # Use cached SHA if available
        if script_name in self._script_cache:
            return self._script_cache[script_name]

        # Determine script path
        if script_path is None:
            script_path = Path(__file__).parent / f"{script_name}.lua"

        # Load script source
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        try:
            with open(script_path, "r", encoding="utf-8") as f:
                script_source = f.read()
        except IOError as e:
            raise FileNotFoundError(f"Failed to read script {script_path}: {e}")

        # Cache source for fallback
        self._script_source[script_name] = script_source

        # Load script into Redis and get SHA
        redis = await self.get_redis()
        try:
            script_sha = await redis.script_load(script_source)
            script_sha_str = str(script_sha)
            self._script_cache[script_name] = script_sha_str

            self.logger.debug(f"Loaded script '{script_name}' with SHA: {script_sha_str}")
            return script_sha_str

        except Exception as e:
            self.logger.error(f"Failed to load script '{script_name}': {e}")
            raise

    async def execute_script(
        self, script_name: str, keys: List[str], args: List[Union[str, int, float]]
    ) -> Union[List, Dict, str, int]:
        """
        Execute Lua script with EVALSHA and automatic EVAL fallback

        Args:
            script_name: Name of the script to execute
            keys: Redis keys for the script
            args: Arguments for the script

        Returns:
            Script execution result

        Raises:
            ValueError: If script not loaded
            redis.RedisError: If execution fails
        """
        if script_name not in self._script_cache:
            raise ValueError(f"Script '{script_name}' not loaded. Call load_script() first.")

        script_sha = self._script_cache[script_name]
        redis = await self.get_redis()

        # Convert all args to strings for Redis
        str_args = [str(arg) for arg in args]

        try:
            # Attempt EVALSHA first (optimized)
            result = await redis.evalsha(script_sha, len(keys), *keys, *str_args)
            return result  # type: ignore[no-any-return]

        except aioredis.ResponseError as e:
            # Check if it's a NOSCRIPT error
            if "NOSCRIPT" in str(e):
                self.logger.warning(f"Script SHA not found, falling back to EVAL for '{script_name}'")

                # Fallback to EVAL with source code
                if script_name not in self._script_source:
                    raise ValueError(f"Script source not cached for '{script_name}'")

                script_source = self._script_source[script_name]
                try:
                    result = await redis.eval(script_source, len(keys), *keys, *str_args)

                    # Reload script for future use
                    try:
                        new_sha = await redis.script_load(script_source)
                        self._script_cache[script_name] = str(new_sha)
                        self.logger.info(f"Reloaded script '{script_name}' with new SHA: {new_sha}")
                    except Exception as reload_error:
                        self.logger.error(f"Failed to reload script '{script_name}': {reload_error}")

                    return result  # type: ignore[no-any-return]

                except Exception as eval_error:
                    self.logger.error(f"EVAL fallback failed for '{script_name}': {eval_error}")
                    raise
            else:
                # Re-raise other Redis errors
                raise

        except Exception as e:
            self.logger.error(f"Script execution failed for '{script_name}': {e}")
            raise

    async def reload_all_scripts(self) -> Dict[str, str]:
        """
        Reload all cached scripts and return new SHA hashes

        Returns:
            Dictionary mapping script names to new SHA hashes
        """
        reloaded = {}
        redis = await self.get_redis()

        for script_name, script_source in self._script_source.items():
            try:
                new_sha = await redis.script_load(script_source)
                new_sha_str = str(new_sha)
                self._script_cache[script_name] = new_sha_str
                reloaded[script_name] = new_sha_str
                self.logger.debug(f"Reloaded script '{script_name}' -> {new_sha_str}")

            except Exception as e:
                self.logger.error(f"Failed to reload script '{script_name}': {e}")

        return reloaded

    async def script_exists(self, script_name: str) -> bool:
        """
        Check if script exists in Redis

        Args:
            script_name: Name of script to check

        Returns:
            True if script exists in Redis
        """
        if script_name not in self._script_cache:
            return False

        redis = await self.get_redis()
        script_sha = self._script_cache[script_name]

        try:
            exists_result = await redis.script_exists(script_sha)
            # Redis returns list of 1/0 for each SHA
            if isinstance(exists_result, list):
                return exists_result[0] == 1
            return bool(exists_result)

        except Exception as e:
            self.logger.error(f"Failed to check script existence '{script_name}': {e}")
            return False

    def get_script_sha(self, script_name: str) -> Optional[str]:
        """Get cached SHA hash for script"""
        return self._script_cache.get(script_name)

    def get_loaded_scripts(self) -> List[str]:
        """Get list of loaded script names"""
        return list(self._script_cache.keys())

    def calculate_source_hash(self, script_name: str) -> Optional[str]:
        """Calculate SHA1 hash of script source for integrity checking"""
        if script_name not in self._script_source:
            return None

        source = self._script_source[script_name]
        return hashlib.sha1(source.encode("utf-8")).hexdigest()

    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()


# Global script loader instance
_script_loader: Optional[ScriptLoader] = None


async def get_script_loader() -> ScriptLoader:
    """Get global script loader instance (singleton pattern)"""
    global _script_loader

    if _script_loader is None:
        _script_loader = ScriptLoader()

        # Load promote.lua script at startup
        try:
            await _script_loader.load_script("promote")
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load promote script at startup: {e}")

    return _script_loader


async def execute_promote_script(keys: List[str], args: List[Union[str, int, float]]) -> Union[List, Dict, str, int]:
    """
    Convenience function to execute promotion script

    Args:
        keys: Redis keys for the promotion operation
        args: Arguments for the promotion script

    Returns:
        Script execution result
    """
    loader = await get_script_loader()
    return await loader.execute_script("promote", keys, args)
