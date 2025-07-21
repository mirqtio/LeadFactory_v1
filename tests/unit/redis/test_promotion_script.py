"""
Unit tests for Redis Lua promotion script
Tests the atomic promotion logic with evidence validation
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
import redis as pyredis

from lua_scripts.script_loader import ScriptLoader


@pytest.fixture
def redis_mock():
    """Mock Redis client for testing"""
    mock = MagicMock()
    mock.script_load = MagicMock(return_value="test_sha_hash")
    mock.evalsha = MagicMock()
    mock.eval = MagicMock()
    mock.script_exists = MagicMock(return_value=[1])
    return mock


@pytest.fixture
def script_loader(redis_mock):
    """Script loader with mocked Redis"""
    loader = ScriptLoader(redis_mock)
    return loader


@pytest.fixture
def valid_evidence():
    """Valid evidence structure for testing"""
    return {
        "timestamp": "2025-07-21T10:00:00Z",
        "agent_id": "pm-1",
        "transition_type": "pending_to_development",
        "requirements_analysis": "Complete requirements analysis performed",
        "acceptance_criteria": [
            "Feature must handle atomic operations",
            "Evidence validation required",
            "Performance <50μs at 1K RPS",
        ],
    }


class TestScriptLoader:
    """Test script loading and caching functionality"""

    def test_load_script_success(self, script_loader, redis_mock):
        """Test successful script loading"""
        script_path = Path(__file__).parent.parent.parent.parent / "redis_scripts" / "promote.lua"

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                sha_hash = script_loader.load_script("promote")

                assert sha_hash == "test_sha_hash"
                assert script_loader.get_script_sha("promote") == "test_sha_hash"
                redis_mock.script_load.assert_called_once()

    def test_load_script_file_not_found(self, script_loader):
        """Test script loading with missing file"""
        with pytest.raises(FileNotFoundError):
            script_loader.load_script("nonexistent")

    def test_execute_script_evalsha_success(self, script_loader, redis_mock):
        """Test successful script execution with EVALSHA"""
        # Load script first
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock successful EVALSHA
        redis_mock.evalsha.return_value = [1, "development", "evidence:test:123"]

        result = script_loader.execute_script("promote", ["key1", "key2"], ["arg1", "arg2"])

        assert result == [1, "development", "evidence:test:123"]
        redis_mock.evalsha.assert_called_once_with("test_sha_hash", 2, "key1", "key2", "arg1", "arg2")

    def test_execute_script_evalsha_fallback(self, script_loader, redis_mock):
        """Test EVALSHA fallback to EVAL on NOSCRIPT error"""
        # Load script first
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock NOSCRIPT error, then successful EVAL
        redis_mock.evalsha.side_effect = pyredis.exceptions.NoScriptError("NOSCRIPT No matching script")
        redis_mock.eval.return_value = [1, "development", "evidence:test:123"]

        result = script_loader.execute_script("promote", ["key1"], ["arg1"])

        assert result == [1, "development", "evidence:test:123"]
        # Should have tried EVALSHA twice (initial + after reload) then EVAL
        assert redis_mock.evalsha.call_count == 2
        redis_mock.eval.assert_called_once()

    def test_script_exists_check(self, script_loader, redis_mock):
        """Test script existence checking"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        redis_mock.script_exists.return_value = [1]
        exists = script_loader.script_exists("promote")

        assert exists is True
        redis_mock.script_exists.assert_called_once_with("test_sha_hash")

    def test_cached_script_retrieval(self, script_loader, redis_mock):
        """Test cached script SHA retrieval"""
        script_loader._script_shas["test"] = "cached_sha_hash"

        sha = script_loader.get_script_sha("test")

        assert sha == "cached_sha_hash"

    def test_script_not_in_cache(self, script_loader):
        """Test behavior when script not in cache"""
        sha = script_loader.get_script_sha("nonexistent")

        assert sha is None


class TestPromotionScript:
    """Test promotion script logic through mocked Redis calls"""

    def test_single_prp_promotion_success(self, script_loader, redis_mock, valid_evidence):
        """Test successful single PRP promotion"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock successful promotion
        redis_mock.evalsha.return_value = [1, "development", "evidence:PRP-1059:1642774800"]

        keys = [
            "queue:pending",  # source queue
            "queue:development",  # dest queue
            "prp:PRP-1059:metadata",  # metadata key
        ]
        args = [
            "promote",  # command
            "PRP-1059",  # PRP ID
            json.dumps(valid_evidence),  # evidence
            "pending_to_development",  # transition type
            "1642774800",  # timestamp
        ]

        result = script_loader.execute_script("promote", keys, args)

        assert result[0] == 1  # success
        assert result[1] == "development"  # new state
        assert "evidence:PRP-1059" in result[2]  # evidence key

    def test_batch_promotion_success(self, script_loader, redis_mock, valid_evidence):
        """Test successful batch PRP promotion"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock successful batch promotion
        redis_mock.evalsha.return_value = [2, []]  # 2 promoted, 0 failed

        batch_evidence = [valid_evidence, valid_evidence]

        keys = ["queue:pending", "queue:development"]
        args = [
            "batch_promote",
            "pending_to_development",
            "1642774800",
            json.dumps(batch_evidence),
            "PRP-1059",
            "PRP-1060",
        ]

        result = script_loader.execute_script("promote", keys, args)

        assert result[0] == 2  # 2 PRPs promoted
        assert result[1] == []  # no failures

    def test_prp_status_check(self, script_loader, redis_mock):
        """Test PRP status checking"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock status response
        redis_mock.evalsha.return_value = ["development", "1642774800", "pending_to_development", 2]

        keys = ["prp:PRP-1059:metadata"]
        args = ["status", "PRP-1059"]

        result = script_loader.execute_script("promote", keys, args)

        assert result[0] == "development"
        assert result[1] == "1642774800"  # last transition
        assert result[2] == "pending_to_development"  # transition type
        assert result[3] == 2  # queue position

    def test_evidence_history_retrieval(self, script_loader, redis_mock, valid_evidence):
        """Test evidence history retrieval"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock evidence history
        evidence_entry = {
            "key": "evidence:PRP-1059:1642774800",
            "transition_type": "pending_to_development",
            "evidence_data": json.dumps(valid_evidence),
            "created_at": "1642774800",
        }
        redis_mock.evalsha.return_value = [evidence_entry]

        keys = []
        args = ["evidence", "PRP-1059", "5"]  # limit to 5 entries

        result = script_loader.execute_script("promote", keys, args)

        assert len(result) == 1
        assert result[0]["key"] == "evidence:PRP-1059:1642774800"
        assert result[0]["transition_type"] == "pending_to_development"


class TestEvidenceValidation:
    """Test evidence validation logic through error responses"""

    def test_missing_evidence_error(self, script_loader, redis_mock):
        """Test error when evidence is missing"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        # Mock Lua error for missing evidence
        redis_mock.evalsha.side_effect = pyredis.ResponseError("Evidence required for PRP promotion")

        keys = ["queue:pending", "queue:development", "prp:PRP-1059:metadata"]
        args = ["promote", "PRP-1059", "", "pending_to_development", "1642774800"]

        with pytest.raises(pyredis.ResponseError, match="Evidence required"):
            script_loader.execute_script("promote", keys, args)

    def test_invalid_transition_type_error(self, script_loader, redis_mock):
        """Test error for invalid transition type"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        invalid_evidence = {"timestamp": "2025-07-21T10:00:00Z", "agent_id": "pm-1", "transition_type": "wrong_type"}

        redis_mock.evalsha.side_effect = pyredis.ResponseError("Evidence transition_type must match")

        keys = ["queue:pending", "queue:development", "prp:PRP-1059:metadata"]
        args = ["promote", "PRP-1059", json.dumps(invalid_evidence), "pending_to_development", "1642774800"]

        with pytest.raises(pyredis.ResponseError, match="transition_type must match"):
            script_loader.execute_script("promote", keys, args)

    def test_missing_required_fields_error(self, script_loader, redis_mock):
        """Test error for missing required evidence fields"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")

        incomplete_evidence = {
            "timestamp": "2025-07-21T10:00:00Z",
            "agent_id": "pm-1",
            "transition_type": "pending_to_development",
            # Missing requirements_analysis and acceptance_criteria
        }

        redis_mock.evalsha.side_effect = pyredis.ResponseError("Development requires requirements_analysis in evidence")

        keys = ["queue:pending", "queue:development", "prp:PRP-1059:metadata"]
        args = ["promote", "PRP-1059", json.dumps(incomplete_evidence), "pending_to_development", "1642774800"]

        with pytest.raises(pyredis.ResponseError, match="requires requirements_analysis"):
            script_loader.execute_script("promote", keys, args)


class TestPerformanceMetrics:
    """Test performance-related aspects of the script loader"""

    def test_script_caching_efficiency(self, script_loader, redis_mock):
        """Test that scripts are cached and not reloaded unnecessarily"""
        # Load script once
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                script_loader.load_script("promote")
        initial_calls = redis_mock.script_load.call_count

        # Subsequent loads should use cache
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                sha1 = script_loader.load_script("promote")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                sha2 = script_loader.load_script("promote")

        assert sha1 == sha2 == "test_sha_hash"
        assert redis_mock.script_load.call_count == initial_calls  # No additional calls

    def test_script_reload_forced(self, script_loader, redis_mock):
        """Test forced script reloading"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                # Load script first time
                sha1 = script_loader.load_script("promote")

                # Mock reloading with new SHA
                redis_mock.script_load.return_value = "new_test_sha_hash"

                # Force reload
                sha2 = script_loader.load_script("promote", reload=True)

        assert sha1 == "test_sha_hash"
        assert sha2 == "new_test_sha_hash"
        assert script_loader.get_script_sha("promote") == "new_test_sha_hash"

    def test_health_check_healthy(self, script_loader, redis_mock):
        """Test health check when system is healthy"""
        redis_mock.ping.return_value = True
        script_loader._script_shas = {"promote": "sha1", "test_script": "sha2"}
        redis_mock.script_exists.return_value = [1]

        health = script_loader.health_check()

        assert health["status"] == "healthy"
        assert health["loaded_scripts"] == 2
        assert health["redis_connected"] is True

    def test_health_check_unhealthy(self, script_loader, redis_mock):
        """Test health check when Redis is down"""
        redis_mock.ping.side_effect = Exception("Connection failed")

        health = script_loader.health_check()

        assert health["status"] == "unhealthy"
        assert "error" in health
        assert health["redis_connected"] is False
