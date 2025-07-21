"""
Redis Lua Script Loader with SHA caching and EVALSHA fallback
Implements optimized script loading following d0_gateway patterns
"""
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import redis
from core.config import get_settings
from core.logging import get_logger
from redis.exceptions import NoScriptError, RedisError


class ScriptLoader:
    """
    Redis Lua script loader with SHA caching and automatic EVALSHA fallback.

    Features:
    - Boot-time script loading with SHA1 caching
    - Automatic EVALSHA with EVAL fallback on NOSCRIPT errors
    - Script reloading for development
    - Connection pooling integration with existing Redis patterns
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        """
        Initialize script loader.

        Args:
            redis_client: Optional Redis client (uses default connection if None)
        """
        self.settings = get_settings()
        self.logger = get_logger("script_loader", domain="redis")

        # Use provided client or create new one following d0_gateway patterns
        if redis_client:
            self.redis = redis_client
        else:
            redis_url = getattr(self.settings, "redis_url", "redis://localhost:6379/0")
            self.redis = redis.from_url(redis_url, decode_responses=True)

        # SHA cache for loaded scripts
        self._script_shas: Dict[str, str] = {}
        self._script_contents: Dict[str, str] = {}

        # Script directory
        self.script_dir = Path(__file__).parent

        self.logger.info("Redis script loader initialized")

    def load_script(self, script_name: str, reload: bool = False) -> str:
        """
        Load Lua script and cache SHA.

        Args:
            script_name: Script filename (without .lua extension)
            reload: Force reload even if already cached

        Returns:
            SHA1 hash of loaded script

        Raises:
            FileNotFoundError: If script file doesn't exist
            RedisError: If script loading fails
        """
        script_key = script_name

        # Return cached SHA if available and not forcing reload
        if not reload and script_key in self._script_shas:
            return self._script_shas[script_key]

        # Load script content
        script_path = self.script_dir / f"{script_name}.lua"
        if not script_path.exists():
            raise FileNotFoundError(f"Script file not found: {script_path}")

        try:
            with open(script_path, "r") as f:
                script_content = f.read()

            # Load script into Redis and get SHA
            sha = self.redis.script_load(script_content)

            # Cache SHA and content
            self._script_shas[script_key] = sha
            self._script_contents[script_key] = script_content

            self.logger.debug(f"Loaded script {script_name} with SHA: {sha}")
            return sha

        except (IOError, OSError) as e:
            self.logger.error(f"Failed to read script {script_name}: {e}")
            raise
        except RedisError as e:
            self.logger.error(f"Failed to load script {script_name} into Redis: {e}")
            raise

    def execute_script(self, script_name: str, keys: List[str], args: List[Any], reload_on_error: bool = True) -> Any:
        """
        Execute Lua script using EVALSHA with automatic EVAL fallback.

        Args:
            script_name: Script name to execute
            keys: Redis keys for the script
            args: Script arguments
            reload_on_error: Reload script if NOSCRIPT error occurs

        Returns:
            Script execution result

        Raises:
            FileNotFoundError: If script not found
            RedisError: If execution fails after fallback attempts
        """
        # Ensure script is loaded
        sha = self.load_script(script_name)

        try:
            # Try EVALSHA first (fastest path)
            return self.redis.evalsha(sha, len(keys), *keys, *args)

        except NoScriptError:
            self.logger.debug(f"NOSCRIPT error for {script_name}, falling back to EVAL")

            if reload_on_error:
                # Reload script and try EVALSHA again
                sha = self.load_script(script_name, reload=True)
                try:
                    return self.redis.evalsha(sha, len(keys), *keys, *args)
                except NoScriptError:
                    # If EVALSHA still fails, use EVAL as final fallback
                    self.logger.warning(f"EVALSHA failed after reload for {script_name}, using EVAL")

            # Fallback to EVAL with cached script content
            script_content = self._script_contents.get(script_name)
            if not script_content:
                # Re-read script if not in cache
                script_path = self.script_dir / f"{script_name}.lua"
                with open(script_path, "r") as f:
                    script_content = f.read()

            return self.redis.eval(script_content, len(keys), *keys, *args)

        except RedisError as e:
            self.logger.error(f"Script execution failed for {script_name}: {e}")
            raise

    def load_all_scripts(self, reload: bool = False) -> Dict[str, str]:
        """
        Load all Lua scripts in the script directory.

        Args:
            reload: Force reload all scripts

        Returns:
            Dictionary of script_name -> SHA mappings
        """
        script_shas = {}

        # Find all .lua files
        for script_path in self.script_dir.glob("*.lua"):
            script_name = script_path.stem

            try:
                sha = self.load_script(script_name, reload=reload)
                script_shas[script_name] = sha

            except (FileNotFoundError, RedisError) as e:
                self.logger.error(f"Failed to load script {script_name}: {e}")
                continue

        self.logger.info(f"Loaded {len(script_shas)} Lua scripts")
        return script_shas

    def get_script_sha(self, script_name: str) -> Optional[str]:
        """
        Get cached SHA for script.

        Args:
            script_name: Script name

        Returns:
            SHA if cached, None otherwise
        """
        return self._script_shas.get(script_name)

    def script_exists(self, script_name: str) -> bool:
        """
        Check if script exists and is loaded.

        Args:
            script_name: Script name to check

        Returns:
            True if script exists and is loaded
        """
        sha = self._script_shas.get(script_name)
        if not sha:
            return False

        try:
            # Use SCRIPT EXISTS to verify SHA is still valid in Redis
            exists = self.redis.script_exists(sha)[0]
            return exists == 1

        except RedisError:
            return False

    def flush_scripts(self) -> None:
        """
        Flush all scripts from Redis and clear local cache.

        Warning: This affects all Redis clients using the same server.
        """
        try:
            self.redis.script_flush()
            self._script_shas.clear()
            self._script_contents.clear()
            self.logger.info("Flushed all Redis scripts and cleared cache")

        except RedisError as e:
            self.logger.error(f"Failed to flush Redis scripts: {e}")
            raise

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on script loader.

        Returns:
            Health check results
        """
        try:
            # Test Redis connection
            self.redis.ping()

            # Count loaded scripts
            loaded_count = len(self._script_shas)

            # Verify a few scripts still exist in Redis
            verified_count = 0
            for script_name, sha in list(self._script_shas.items())[:3]:  # Check first 3
                if self.redis.script_exists(sha)[0]:
                    verified_count += 1

            return {
                "status": "healthy",
                "loaded_scripts": loaded_count,
                "verified_scripts": verified_count,
                "redis_connected": True,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "loaded_scripts": len(self._script_shas),
                "redis_connected": False,
            }


# Global script loader instance
_script_loader: Optional[ScriptLoader] = None


def get_script_loader() -> ScriptLoader:
    """Get global script loader instance."""
    global _script_loader
    if _script_loader is None:
        _script_loader = ScriptLoader()
    return _script_loader


def load_script(script_name: str, reload: bool = False) -> str:
    """Load script using global loader."""
    return get_script_loader().load_script(script_name, reload=reload)


def get_script_sha(script_name: str) -> Optional[str]:
    """Get script SHA using global loader."""
    return get_script_loader().get_script_sha(script_name)


def execute_script(script_name: str, keys: List[str], args: List[Any]) -> Any:
    """Execute script using global loader."""
    return get_script_loader().execute_script(script_name, keys, args)


# Boot-time script loading
def initialize_scripts():
    """Initialize all scripts at application boot."""
    loader = get_script_loader()

    try:
        # Load all scripts
        script_shas = loader.load_all_scripts()

        # Store SHAs in environment variables for rollback
        for script_name, sha in script_shas.items():
            env_var = f"REDIS_SCRIPT_{script_name.upper()}_SHA"
            os.environ[env_var] = sha

        return script_shas

    except Exception as e:
        loader.logger.error(f"Failed to initialize scripts: {e}")
        raise


# Cleanup function for testing
def reset_script_loader():
    """Reset global script loader (mainly for testing)."""
    global _script_loader
    _script_loader = None
