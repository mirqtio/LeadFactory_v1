"""
Unit tests for Redis script loader functionality
Tests script management, caching, and execution patterns
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import redis as pyredis

from lua_scripts.script_loader import ScriptLoader, execute_promote_script, get_script_loader


@pytest.fixture
def mock_redis():
    """Mock async Redis client"""
    mock = AsyncMock()
    mock.script_load.return_value = "test_sha_12345"
    mock.evalsha.return_value = [1, "success"]
    mock.eval.return_value = [1, "success"]
    mock.script_exists.return_value = [1]
    return mock


@pytest.fixture
async def script_loader(mock_redis):
    """Script loader instance with mocked Redis"""
    loader = ScriptLoader(mock_redis)
    return loader


class TestScriptLoader:
    """Test core script loader functionality"""

    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test script loader initialization"""
        loader = ScriptLoader()

        assert loader._redis is None
        assert loader._script_cache == {}
        assert loader._script_source == {}

    @pytest.mark.asyncio
    async def test_redis_lazy_initialization(self):
        """Test lazy Redis connection initialization"""
        with patch("lua_scripts.script_loader.aioredis.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis

            loader = ScriptLoader()
            redis_client = await loader.get_redis()

            assert redis_client == mock_redis
            mock_from_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_script_from_file(self, script_loader, mock_redis):
        """Test loading script from file system"""
        script_content = "-- Test Lua script\nreturn 'test'"

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                sha_hash = await script_loader.load_script("test_script", Path("/fake/path.lua"))

                assert sha_hash == "test_sha_12345"
                assert script_loader.get_script_sha("test_script") == "test_sha_12345"
                assert script_loader._script_source["test_script"] == script_content
                mock_redis.script_load.assert_called_once_with(script_content)

    @pytest.mark.asyncio
    async def test_load_script_file_not_found(self, script_loader):
        """Test handling of missing script files"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Script not found"):
                await script_loader.load_script("missing", Path("/fake/missing.lua"))

    @pytest.mark.asyncio
    async def test_load_script_read_error(self, script_loader):
        """Test handling of file read errors"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                with pytest.raises(FileNotFoundError, match="Failed to read script"):
                    await script_loader.load_script("error", Path("/fake/error.lua"))

    @pytest.mark.asyncio
    async def test_load_script_redis_error(self, script_loader, mock_redis):
        """Test handling of Redis script loading errors"""
        script_content = "return 'test'"
        mock_redis.script_load.side_effect = Exception("Redis connection failed")

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(Exception, match="Redis connection failed"):
                    await script_loader.load_script("error_script")

    @pytest.mark.asyncio
    async def test_script_caching(self, script_loader, mock_redis):
        """Test script SHA caching behavior"""
        script_content = "return 'cached'"

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                # First load
                sha1 = await script_loader.load_script("cached_script")

                # Second load should use cache
                sha2 = await script_loader.load_script("cached_script")

                assert sha1 == sha2 == "test_sha_12345"
                # Redis script_load should only be called once
                mock_redis.script_load.assert_called_once()


class TestScriptExecution:
    """Test script execution with EVALSHA and fallback"""

    @pytest.mark.asyncio
    async def test_execute_script_success(self, script_loader, mock_redis):
        """Test successful script execution with EVALSHA"""
        # Load script first
        script_loader._script_cache["test"] = "test_sha_12345"
        mock_redis.evalsha.return_value = [1, "development", "evidence_key"]

        result = await script_loader.execute_script("test", ["key1", "key2"], ["arg1", "arg2"])

        assert result == [1, "development", "evidence_key"]
        mock_redis.evalsha.assert_called_once_with("test_sha_12345", 2, "key1", "key2", "arg1", "arg2")

    @pytest.mark.asyncio
    async def test_execute_script_not_loaded(self, script_loader):
        """Test execution error when script not loaded"""
        with pytest.raises(ValueError, match="Script 'unknown' not loaded"):
            await script_loader.execute_script("unknown", [], [])

    @pytest.mark.asyncio
    async def test_execute_script_evalsha_fallback(self, script_loader, mock_redis):
        """Test EVALSHA fallback to EVAL on NOSCRIPT error"""
        script_content = "return 'fallback'"
        script_loader._script_cache["fallback_test"] = "test_sha_12345"
        script_loader._script_source["fallback_test"] = script_content

        # Mock NOSCRIPT error, then successful EVAL
        mock_redis.evalsha.side_effect = pyredis.ResponseError("NOSCRIPT No matching script")
        mock_redis.eval.return_value = [1, "fallback_success"]
        mock_redis.script_load.return_value = "new_sha_67890"

        result = await script_loader.execute_script("fallback_test", ["key1"], ["arg1"])

        assert result == [1, "fallback_success"]
        mock_redis.evalsha.assert_called_once()
        mock_redis.eval.assert_called_once_with(script_content, 1, "key1", "arg1")
        # Script should be reloaded
        mock_redis.script_load.assert_called_once_with(script_content)
        assert script_loader.get_script_sha("fallback_test") == "new_sha_67890"

    @pytest.mark.asyncio
    async def test_execute_script_evalsha_fallback_no_source(self, script_loader, mock_redis):
        """Test fallback failure when source not cached"""
        script_loader._script_cache["no_source"] = "test_sha_12345"
        # No source cached

        mock_redis.evalsha.side_effect = pyredis.ResponseError("NOSCRIPT No matching script")

        with pytest.raises(ValueError, match="Script source not cached"):
            await script_loader.execute_script("no_source", [], [])

    @pytest.mark.asyncio
    async def test_execute_script_non_noscript_error(self, script_loader, mock_redis):
        """Test handling of non-NOSCRIPT Redis errors"""
        script_loader._script_cache["error_test"] = "test_sha_12345"

        mock_redis.evalsha.side_effect = pyredis.ResponseError("WRONGTYPE Operation against a key")

        with pytest.raises(pyredis.ResponseError, match="WRONGTYPE"):
            await script_loader.execute_script("error_test", [], [])

    @pytest.mark.asyncio
    async def test_argument_type_conversion(self, script_loader, mock_redis):
        """Test conversion of different argument types to strings"""
        script_loader._script_cache["type_test"] = "test_sha_12345"
        mock_redis.evalsha.return_value = "success"

        # Test various argument types
        await script_loader.execute_script("type_test", ["key"], [123, 45.67, True, "string"])

        mock_redis.evalsha.assert_called_once_with("test_sha_12345", 1, "key", "123", "45.67", "True", "string")


class TestScriptManagement:
    """Test script management features"""

    @pytest.mark.asyncio
    async def test_script_exists_true(self, script_loader, mock_redis):
        """Test checking script existence when it exists"""
        script_loader._script_cache["exists_test"] = "test_sha_12345"
        mock_redis.script_exists.return_value = [1]

        exists = await script_loader.script_exists("exists_test")

        assert exists is True
        mock_redis.script_exists.assert_called_once_with("test_sha_12345")

    @pytest.mark.asyncio
    async def test_script_exists_false(self, script_loader, mock_redis):
        """Test checking script existence when it doesn't exist"""
        script_loader._script_cache["missing_test"] = "test_sha_12345"
        mock_redis.script_exists.return_value = [0]

        exists = await script_loader.script_exists("missing_test")

        assert exists is False

    @pytest.mark.asyncio
    async def test_script_exists_not_loaded(self, script_loader):
        """Test checking existence of unloaded script"""
        exists = await script_loader.script_exists("not_loaded")

        assert exists is False

    @pytest.mark.asyncio
    async def test_script_exists_error(self, script_loader, mock_redis):
        """Test error handling in script existence check"""
        script_loader._script_cache["error_test"] = "test_sha_12345"
        mock_redis.script_exists.side_effect = Exception("Redis error")

        exists = await script_loader.script_exists("error_test")

        assert exists is False

    @pytest.mark.asyncio
    async def test_reload_all_scripts(self, script_loader, mock_redis):
        """Test reloading all cached scripts"""
        script_loader._script_source = {"script1": "return 1", "script2": "return 2"}
        script_loader._script_cache = {"script1": "old_sha_1", "script2": "old_sha_2"}

        mock_redis.script_load.side_effect = ["new_sha_1", "new_sha_2"]

        reloaded = await script_loader.reload_all_scripts()

        assert reloaded == {"script1": "new_sha_1", "script2": "new_sha_2"}
        assert script_loader.get_script_sha("script1") == "new_sha_1"
        assert script_loader.get_script_sha("script2") == "new_sha_2"
        assert mock_redis.script_load.call_count == 2

    @pytest.mark.asyncio
    async def test_reload_scripts_partial_failure(self, script_loader, mock_redis):
        """Test script reloading with partial failures"""
        script_loader._script_source = {"good_script": "return 1", "bad_script": "return 2"}

        def mock_script_load(script):
            if "return 1" in script:
                return "new_good_sha"
            else:
                raise Exception("Script load failed")

        mock_redis.script_load.side_effect = mock_script_load

        reloaded = await script_loader.reload_all_scripts()

        assert reloaded == {"good_script": "new_good_sha"}
        assert script_loader.get_script_sha("good_script") == "new_good_sha"

    def test_get_loaded_scripts(self, script_loader):
        """Test getting list of loaded script names"""
        script_loader._script_cache = {"script1": "sha1", "script2": "sha2", "script3": "sha3"}

        loaded = script_loader.get_loaded_scripts()

        assert set(loaded) == {"script1", "script2", "script3"}

    def test_calculate_source_hash(self, script_loader):
        """Test source hash calculation"""
        script_loader._script_source["test"] = "return 'test'"

        hash_value = script_loader.calculate_source_hash("test")

        assert hash_value is not None
        assert len(hash_value) == 40  # SHA1 hash is 40 characters
        assert hash_value == script_loader.calculate_source_hash("test")  # Consistent

    def test_calculate_source_hash_missing(self, script_loader):
        """Test source hash calculation for missing script"""
        hash_value = script_loader.calculate_source_hash("missing")

        assert hash_value is None


class TestGlobalFunctions:
    """Test global convenience functions"""

    @pytest.mark.asyncio
    async def test_get_script_loader_singleton(self):
        """Test global script loader singleton behavior"""
        # Reset global state
        import lua_scripts.script_loader

        lua_scripts.script_loader._script_loader = None

        with patch.object(ScriptLoader, "load_script", new_callable=AsyncMock) as mock_load:
            loader1 = await get_script_loader()
            loader2 = await get_script_loader()

            assert loader1 is loader2  # Same instance
            mock_load.assert_called_once_with("promote")  # Auto-loads promote script

    @pytest.mark.asyncio
    async def test_execute_promote_script_convenience(self):
        """Test convenience function for promoting scripts"""
        with patch("lua_scripts.script_loader.get_script_loader") as mock_get_loader:
            mock_loader = AsyncMock()
            mock_loader.execute_script.return_value = [1, "success"]
            mock_get_loader.return_value = mock_loader

            result = await execute_promote_script(["key1", "key2"], ["arg1", "arg2"])

            assert result == [1, "success"]
            mock_loader.execute_script.assert_called_once_with("promote", ["key1", "key2"], ["arg1", "arg2"])


class TestResourceManagement:
    """Test resource management and cleanup"""

    @pytest.mark.asyncio
    async def test_close_redis_connection(self, script_loader, mock_redis):
        """Test proper Redis connection cleanup"""
        await script_loader.close()

        mock_redis.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_when_no_connection(self, script_loader):
        """Test closing when no Redis connection exists"""
        script_loader._redis = None

        # Should not raise exception
        await script_loader.close()
