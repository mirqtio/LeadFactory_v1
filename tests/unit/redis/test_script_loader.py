"""
Unit tests for Redis script loader functionality
Tests script management, caching, and execution patterns
"""

from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
import redis as pyredis

from lua_scripts.script_loader import ScriptLoader


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    mock = MagicMock()
    mock.script_load.return_value = "test_sha_12345"
    mock.evalsha.return_value = [1, "success"]
    mock.eval.return_value = [1, "success"]
    mock.script_exists.return_value = [1]
    mock.ping.return_value = True
    return mock


@pytest.fixture
def script_loader(mock_redis):
    """Script loader instance with mocked Redis"""
    loader = ScriptLoader(mock_redis)
    return loader


class TestScriptLoader:
    """Test core script loader functionality"""

    def test_initialization_with_redis_instance(self, mock_redis):
        """Test script loader initialization with provided Redis instance"""
        loader = ScriptLoader(mock_redis)

        assert loader.redis == mock_redis
        assert loader._script_shas == {}
        assert loader._script_contents == {}

    def test_initialization_without_redis(self):
        """Test script loader initialization with default Redis connection"""
        with patch("redis.from_url") as mock_from_url:
            mock_redis = MagicMock()
            mock_from_url.return_value = mock_redis

            loader = ScriptLoader()

            assert loader.redis == mock_redis
            mock_from_url.assert_called_once()

    def test_load_script_from_file(self, script_loader, mock_redis):
        """Test loading script from file system"""
        script_content = "-- Test Lua script\nreturn 'test'"

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                sha_hash = script_loader.load_script("test_script")

                assert sha_hash == "test_sha_12345"
                assert script_loader.get_script_sha("test_script") == "test_sha_12345"
                assert script_loader._script_contents["test_script"] == script_content
                mock_redis.script_load.assert_called_once_with(script_content)

    def test_load_script_file_not_found(self, script_loader):
        """Test handling of missing script files"""
        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="Script file not found"):
                script_loader.load_script("missing")

    def test_load_script_read_error(self, script_loader):
        """Test handling of file read errors"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", side_effect=IOError("Permission denied")):
                with pytest.raises(IOError):
                    script_loader.load_script("error")

    def test_load_script_redis_error(self, script_loader, mock_redis):
        """Test handling of Redis script loading errors"""
        script_content = "return 'test'"
        mock_redis.script_load.side_effect = pyredis.RedisError("Redis connection failed")

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(pyredis.RedisError):
                    script_loader.load_script("error_script")

    def test_script_caching(self, script_loader, mock_redis):
        """Test script SHA caching behavior"""
        script_content = "return 'cached'"

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                # First load
                sha1 = script_loader.load_script("cached_script")

                # Second load should use cache
                sha2 = script_loader.load_script("cached_script")

                assert sha1 == sha2 == "test_sha_12345"
                # Redis script_load should only be called once
                mock_redis.script_load.assert_called_once()

    def test_script_force_reload(self, script_loader, mock_redis):
        """Test forced script reloading"""
        script_content = "return 'test'"

        with patch("builtins.open", mock_open(read_data=script_content)):
            with patch("pathlib.Path.exists", return_value=True):
                # First load
                sha1 = script_loader.load_script("test_script")

                # Force reload
                mock_redis.script_load.return_value = "new_sha_67890"
                sha2 = script_loader.load_script("test_script", reload=True)

                assert sha1 == "test_sha_12345"
                assert sha2 == "new_sha_67890"
                assert mock_redis.script_load.call_count == 2


class TestScriptExecution:
    """Test script execution with EVALSHA and fallback"""

    def test_execute_script_success(self, script_loader, mock_redis):
        """Test successful script execution with EVALSHA"""
        # Load script first
        script_loader._script_shas["test"] = "test_sha_12345"
        mock_redis.evalsha.return_value = [1, "development", "evidence_key"]

        result = script_loader.execute_script("test", ["key1", "key2"], ["arg1", "arg2"])

        assert result == [1, "development", "evidence_key"]
        mock_redis.evalsha.assert_called_once_with("test_sha_12345", 2, "key1", "key2", "arg1", "arg2")

    def test_execute_script_evalsha_fallback(self, script_loader, mock_redis):
        """Test EVALSHA fallback to EVAL on NOSCRIPT error"""
        script_content = "return 'fallback'"
        script_loader._script_shas["fallback_test"] = "test_sha_12345"
        script_loader._script_contents["fallback_test"] = script_content

        # Mock NOSCRIPT error, then successful EVAL
        mock_redis.evalsha.side_effect = [
            pyredis.exceptions.NoScriptError("NOSCRIPT No matching script"),
            pyredis.exceptions.NoScriptError("NOSCRIPT No matching script"),  # Second EVALSHA also fails
        ]
        mock_redis.eval.return_value = [1, "fallback_success"]
        mock_redis.script_load.return_value = "new_sha_67890"

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data=script_content)):
                result = script_loader.execute_script("fallback_test", ["key1"], ["arg1"])

        assert result == [1, "fallback_success"]
        # Should try EVALSHA twice (initial + after reload), then fall back to EVAL
        assert mock_redis.evalsha.call_count == 2
        mock_redis.eval.assert_called_once_with(script_content, 1, "key1", "arg1")

    def test_execute_script_no_script_loaded(self, script_loader, mock_redis):
        """Test execution when script not loaded"""
        with pytest.raises(FileNotFoundError, match="Script file not found"):
            script_loader.execute_script("unknown", [], [])

    def test_execute_script_non_noscript_error(self, script_loader, mock_redis):
        """Test handling of non-NOSCRIPT Redis errors"""
        script_loader._script_shas["error_test"] = "test_sha_12345"

        mock_redis.evalsha.side_effect = pyredis.RedisError("WRONGTYPE Operation against a key")

        with pytest.raises(pyredis.RedisError, match="WRONGTYPE"):
            script_loader.execute_script("error_test", [], [])


class TestScriptManagement:
    """Test script management features"""

    def test_script_exists_true(self, script_loader, mock_redis):
        """Test checking script existence when it exists"""
        script_loader._script_shas["exists_test"] = "test_sha_12345"
        mock_redis.script_exists.return_value = [1]

        exists = script_loader.script_exists("exists_test")

        assert exists is True
        mock_redis.script_exists.assert_called_once_with("test_sha_12345")

    def test_script_exists_false(self, script_loader, mock_redis):
        """Test checking script existence when it doesn't exist"""
        script_loader._script_shas["missing_test"] = "test_sha_12345"
        mock_redis.script_exists.return_value = [0]

        exists = script_loader.script_exists("missing_test")

        assert exists is False

    def test_script_exists_not_loaded(self, script_loader):
        """Test checking existence of unloaded script"""
        exists = script_loader.script_exists("not_loaded")

        assert exists is False

    def test_script_exists_error(self, script_loader, mock_redis):
        """Test error handling in script existence check"""
        script_loader._script_shas["error_test"] = "test_sha_12345"
        mock_redis.script_exists.side_effect = Exception("Redis error")

        exists = script_loader.script_exists("error_test")

        assert exists is False

    def test_load_all_scripts(self, script_loader, mock_redis):
        """Test loading all scripts from directory"""
        with patch("pathlib.Path.glob") as mock_glob:
            mock_script1 = MagicMock()
            mock_script1.stem = "script1"
            mock_script2 = MagicMock()
            mock_script2.stem = "script2"
            mock_glob.return_value = [mock_script1, mock_script2]

            with patch.object(script_loader, "load_script") as mock_load:
                mock_load.side_effect = ["sha1", "sha2"]

                result = script_loader.load_all_scripts()

                assert result == {"script1": "sha1", "script2": "sha2"}
                assert mock_load.call_count == 2

    def test_get_script_sha_exists(self, script_loader):
        """Test getting SHA for existing script"""
        script_loader._script_shas["test"] = "test_sha"

        sha = script_loader.get_script_sha("test")

        assert sha == "test_sha"

    def test_get_script_sha_missing(self, script_loader):
        """Test getting SHA for non-existent script"""
        sha = script_loader.get_script_sha("missing")

        assert sha is None

    def test_flush_scripts(self, script_loader, mock_redis):
        """Test flushing all scripts from Redis"""
        script_loader._script_shas = {"test": "sha1"}
        script_loader._script_contents = {"test": "content"}

        script_loader.flush_scripts()

        mock_redis.script_flush.assert_called_once()
        assert script_loader._script_shas == {}
        assert script_loader._script_contents == {}

    def test_health_check_healthy(self, script_loader, mock_redis):
        """Test health check when system is healthy"""
        script_loader._script_shas = {"script1": "sha1", "script2": "sha2"}
        mock_redis.ping.return_value = True
        mock_redis.script_exists.return_value = [1]

        health = script_loader.health_check()

        assert health["status"] == "healthy"
        assert health["loaded_scripts"] == 2
        assert health["redis_connected"] is True

    def test_health_check_unhealthy(self, script_loader, mock_redis):
        """Test health check when Redis is down"""
        mock_redis.ping.side_effect = Exception("Connection failed")

        health = script_loader.health_check()

        assert health["status"] == "unhealthy"
        assert "error" in health
        assert health["redis_connected"] is False


class TestGlobalFunctions:
    """Test module-level functions"""

    def test_get_script_loader_creates_instance(self):
        """Test that get_script_loader creates and caches instance"""
        from lua_scripts.script_loader import get_script_loader

        # Reset any existing instance
        reset_script_loader()

        with patch.object(ScriptLoader, "__init__", return_value=None) as mock_init:
            loader1 = get_script_loader()
            loader2 = get_script_loader()

            # Should be the same instance
            assert loader1 is loader2
            # Should only initialize once
            mock_init.assert_called_once()

    def test_module_level_functions(self):
        """Test module-level convenience functions"""
        from lua_scripts.script_loader import execute_promote_script

        with patch("redis_scripts.script_loader.get_script_loader") as mock_get_loader:
            mock_loader = MagicMock()
            mock_loader.load_script.return_value = "test_sha"
            mock_loader.get_script_sha.return_value = "test_sha"
            mock_loader.execute_script.return_value = [1, "success"]
            mock_get_loader.return_value = mock_loader

            # Test load_script
            result = load_script("test")
            assert result == "test_sha"
            mock_loader.load_script.assert_called_once_with("test", reload=False)

            # Test get_script_sha
            result = get_script_sha("test")
            assert result == "test_sha"
            mock_loader.get_script_sha.assert_called_once_with("test")

            # Test execute_script
            result = execute_script("test", ["key1"], ["arg1"])
            assert result == [1, "success"]
            mock_loader.execute_script.assert_called_once_with("test", ["key1"], ["arg1"])
