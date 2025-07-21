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
    with patch("lua_scripts.script_loader.aioredis.from_url", return_value=redis_mock):
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

    @pytest.mark.asyncio
    async def test_load_script_success(self, script_loader, redis_mock):
        """Test successful script loading"""
        script_path = Path(__file__).parent.parent.parent.parent / "lua_scripts" / "promote.lua"

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                sha_hash = await script_loader.load_script("promote", script_path)

                assert sha_hash == "test_sha_hash"
                assert script_loader.get_script_sha("promote") == "test_sha_hash"
                redis_mock.script_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_script_file_not_found(self, script_loader):
        """Test script loading with missing file"""
        with pytest.raises(FileNotFoundError):
            await script_loader.load_script("nonexistent", Path("/fake/path.lua"))

    @pytest.mark.asyncio
    async def test_execute_script_evalsha_success(self, script_loader, redis_mock):
        """Test successful script execution with EVALSHA"""
        # Load script first
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        # Mock successful EVALSHA
        redis_mock.evalsha.return_value = [1, "development", "evidence:test:123"]

        result = await script_loader.execute_script("promote", ["key1", "key2"], ["arg1", "arg2"])

        assert result == [1, "development", "evidence:test:123"]
        redis_mock.evalsha.assert_called_once_with("test_sha_hash", 2, "key1", "key2", "arg1", "arg2")

    @pytest.mark.asyncio
    async def test_execute_script_evalsha_fallback(self, script_loader, redis_mock):
        """Test EVALSHA fallback to EVAL on NOSCRIPT error"""
        # Load script first
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        # Mock NOSCRIPT error, then successful EVAL
        redis_mock.evalsha.side_effect = pyredis.ResponseError("NOSCRIPT No matching script")
        redis_mock.eval.return_value = [1, "development", "evidence:test:123"]

        result = await script_loader.execute_script("promote", ["key1"], ["arg1"])

        assert result == [1, "development", "evidence:test:123"]
        redis_mock.evalsha.assert_called_once()
        redis_mock.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_script_exists_check(self, script_loader, redis_mock):
        """Test script existence checking"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        redis_mock.script_exists.return_value = [1]
        exists = await script_loader.script_exists("promote")

        assert exists is True
        redis_mock.script_exists.assert_called_once_with("test_sha_hash")

    def test_calculate_source_hash(self, script_loader):
        """Test source code hash calculation"""
        script_loader._script_source["test"] = "return 1"

        hash_value = script_loader.calculate_source_hash("test")

        assert hash_value is not None
        assert len(hash_value) == 40  # SHA1 hash length


class TestPromotionScript:
    """Test promotion script logic through mocked Redis calls"""

    @pytest.mark.asyncio
    async def test_single_prp_promotion_success(self, script_loader, redis_mock, valid_evidence):
        """Test successful single PRP promotion"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

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

        result = await script_loader.execute_script("promote", keys, args)

        assert result[0] == 1  # success
        assert result[1] == "development"  # new state
        assert "evidence:PRP-1059" in result[2]  # evidence key

    @pytest.mark.asyncio
    async def test_batch_promotion_success(self, script_loader, redis_mock, valid_evidence):
        """Test successful batch PRP promotion"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

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

        result = await script_loader.execute_script("promote", keys, args)

        assert result[0] == 2  # 2 PRPs promoted
        assert result[1] == []  # no failures

    @pytest.mark.asyncio
    async def test_prp_status_check(self, script_loader, redis_mock):
        """Test PRP status checking"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        # Mock status response
        redis_mock.evalsha.return_value = ["development", "1642774800", "pending_to_development", 2]

        keys = ["prp:PRP-1059:metadata"]
        args = ["status", "PRP-1059"]

        result = await script_loader.execute_script("promote", keys, args)

        assert result[0] == "development"
        assert result[1] == "1642774800"  # last transition
        assert result[2] == "pending_to_development"  # transition type
        assert result[3] == 2  # queue position

    @pytest.mark.asyncio
    async def test_evidence_history_retrieval(self, script_loader, redis_mock, valid_evidence):
        """Test evidence history retrieval"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

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

        result = await script_loader.execute_script("promote", keys, args)

        assert len(result) == 1
        assert result[0]["key"] == "evidence:PRP-1059:1642774800"
        assert result[0]["transition_type"] == "pending_to_development"


class TestEvidenceValidation:
    """Test evidence validation logic through error responses"""

    @pytest.mark.asyncio
    async def test_missing_evidence_error(self, script_loader, redis_mock):
        """Test error when evidence is missing"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        # Mock Lua error for missing evidence
        redis_mock.evalsha.side_effect = pyredis.ResponseError("Evidence required for PRP promotion")

        keys = ["queue:pending", "queue:development", "prp:PRP-1059:metadata"]
        args = ["promote", "PRP-1059", "", "pending_to_development", "1642774800"]

        with pytest.raises(pyredis.ResponseError, match="Evidence required"):
            await script_loader.execute_script("promote", keys, args)

    @pytest.mark.asyncio
    async def test_invalid_transition_type_error(self, script_loader, redis_mock):
        """Test error for invalid transition type"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        invalid_evidence = {"timestamp": "2025-07-21T10:00:00Z", "agent_id": "pm-1", "transition_type": "wrong_type"}

        redis_mock.evalsha.side_effect = pyredis.ResponseError("Evidence transition_type must match")

        keys = ["queue:pending", "queue:development", "prp:PRP-1059:metadata"]
        args = ["promote", "PRP-1059", json.dumps(invalid_evidence), "pending_to_development", "1642774800"]

        with pytest.raises(pyredis.ResponseError, match="transition_type must match"):
            await script_loader.execute_script("promote", keys, args)

    @pytest.mark.asyncio
    async def test_missing_required_fields_error(self, script_loader, redis_mock):
        """Test error for missing required evidence fields"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        incomplete_evidence = {
            "timestamp": "2025-07-21T10:00:00Z",
            "agent_id": "pm-1",
            "transition_type": "pending_to_development"
            # Missing requirements_analysis and acceptance_criteria
        }

        redis_mock.evalsha.side_effect = pyredis.ResponseError("Development requires requirements_analysis in evidence")

        keys = ["queue:pending", "queue:development", "prp:PRP-1059:metadata"]
        args = ["promote", "PRP-1059", json.dumps(incomplete_evidence), "pending_to_development", "1642774800"]

        with pytest.raises(pyredis.ResponseError, match="requires requirements_analysis"):
            await script_loader.execute_script("promote", keys, args)


class TestPerformanceMetrics:
    """Test performance-related aspects of the script loader"""

    @pytest.mark.asyncio
    async def test_script_caching_efficiency(self, script_loader, redis_mock):
        """Test that scripts are cached and not reloaded unnecessarily"""
        # Load script once
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")
        initial_calls = redis_mock.script_load.call_count

        # Subsequent loads should use cache
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                sha1 = await script_loader.load_script("promote")
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                sha2 = await script_loader.load_script("promote")

        assert sha1 == sha2 == "test_sha_hash"
        assert redis_mock.script_load.call_count == initial_calls  # No additional calls

    @pytest.mark.asyncio
    async def test_bulk_script_reloading(self, script_loader, redis_mock):
        """Test bulk script reloading functionality"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data="-- Test Lua script")):
                await script_loader.load_script("promote")

        # Mock reloading with new SHA
        redis_mock.script_load.return_value = "new_test_sha_hash"

        reloaded = await script_loader.reload_all_scripts()

        assert reloaded["promote"] == "new_test_sha_hash"
        assert script_loader.get_script_sha("promote") == "new_test_sha_hash"

    def test_get_loaded_scripts_list(self, script_loader):
        """Test getting list of loaded scripts"""
        script_loader._script_cache = {"promote": "sha1", "test_script": "sha2"}

        loaded = script_loader.get_loaded_scripts()

        assert "promote" in loaded
        assert "test_script" in loaded
        assert len(loaded) == 2
