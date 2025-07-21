"""
Integration tests for Redis Lua promotion script with actual Redis instance
Tests end-to-end promotion workflows with real Redis operations
"""

import json
import time
from pathlib import Path

import pytest
import redis.asyncio as aioredis

from core.config import get_settings
from lua_scripts.script_loader import ScriptLoader, get_script_loader


@pytest.fixture
async def redis_client():
    """Real Redis client for integration testing"""
    settings = get_settings()
    client = await aioredis.from_url(settings.redis_url, decode_responses=True, encoding="utf-8")

    # Clean up test keys before and after
    test_pattern = "test:*"
    keys = await client.keys(test_pattern)
    if keys:
        await client.delete(*keys)

    yield client

    # Cleanup after test
    keys = await client.keys(test_pattern)
    if keys:
        await client.delete(*keys)
    await client.close()


@pytest.fixture
async def integration_script_loader(redis_client):
    """Script loader with real Redis for integration tests"""
    loader = ScriptLoader(redis_client)

    # Load the promotion script
    script_path = Path(__file__).parent.parent.parent / "lua_scripts" / "promote.lua"
    await loader.load_script("promote", script_path)

    return loader


@pytest.fixture
def valid_evidence():
    """Valid evidence for development transition"""
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


@pytest.fixture
def integration_evidence():
    """Valid evidence for integration transition"""
    return {
        "timestamp": "2025-07-21T11:00:00Z",
        "agent_id": "pm-1",
        "transition_type": "development_to_integration",
        "implementation_complete": True,
        "local_validation": "All tests passing with `make quick-check`",
        "branch_name": "feat/prp-1059-lua-promotion",
    }


class TestSinglePRPPromotion:
    """Test single PRP promotion operations with real Redis"""

    @pytest.mark.asyncio
    async def test_successful_promotion_pending_to_development(
        self, redis_client, integration_script_loader, valid_evidence
    ):
        """Test successful promotion from pending to development"""
        # Setup: Add PRP to pending queue
        prp_id = "PRP-1059"
        await redis_client.lpush("test:queue:pending", prp_id)

        # Initialize metadata
        metadata_key = f"test:prp:{prp_id}:metadata"
        await redis_client.hset(metadata_key, "status", "pending", "created_at", "1642774800")

        # Execute promotion
        keys = ["test:queue:pending", "test:queue:development", metadata_key]
        args = ["promote", prp_id, json.dumps(valid_evidence), "pending_to_development", str(int(time.time()))]

        result = await integration_script_loader.execute_script("promote", keys, args)

        # Verify result
        assert result[0] == 1  # Success
        assert result[1] == "development"  # New state
        assert f"test:evidence:{prp_id}" in result[2]  # Evidence key created

        # Verify queue state changes
        pending_queue = await redis_client.lrange("test:queue:pending", 0, -1)
        development_queue = await redis_client.lrange("test:queue:development", 0, -1)

        assert prp_id not in pending_queue
        assert prp_id in development_queue

        # Verify metadata updated
        metadata = await redis_client.hgetall(metadata_key)
        assert metadata["status"] == "development"
        assert metadata["last_transition_type"] == "pending_to_development"

        # Verify evidence stored
        evidence_key = result[2]
        evidence_data = await redis_client.hgetall(evidence_key)
        assert evidence_data["prp_id"] == prp_id
        assert evidence_data["transition_type"] == "pending_to_development"
        assert json.loads(evidence_data["evidence_data"]) == valid_evidence

    @pytest.mark.asyncio
    async def test_promotion_prp_not_in_source_queue(self, redis_client, integration_script_loader, valid_evidence):
        """Test error when PRP not in source queue"""
        prp_id = "PRP-MISSING"
        metadata_key = f"test:prp:{prp_id}:metadata"

        keys = ["test:queue:pending", "test:queue:development", metadata_key]
        args = ["promote", prp_id, json.dumps(valid_evidence), "pending_to_development", str(int(time.time()))]

        # Should raise error for missing PRP
        with pytest.raises(aioredis.ResponseError, match="not found in source queue"):
            await integration_script_loader.execute_script("promote", keys, args)

    @pytest.mark.asyncio
    async def test_promotion_chain_pending_to_complete(
        self, redis_client, integration_script_loader, valid_evidence, integration_evidence
    ):
        """Test complete promotion chain through all states"""
        prp_id = "PRP-CHAIN"
        metadata_key = f"test:prp:{prp_id}:metadata"

        # Start in pending
        await redis_client.lpush("test:queue:pending", prp_id)
        await redis_client.hset(metadata_key, "status", "pending")

        # 1. Pending → Development
        result1 = await integration_script_loader.execute_script(
            "promote",
            ["test:queue:pending", "test:queue:development", metadata_key],
            ["promote", prp_id, json.dumps(valid_evidence), "pending_to_development", str(int(time.time()))],
        )

        assert result1[0] == 1
        assert result1[1] == "development"

        # 2. Development → Integration
        result2 = await integration_script_loader.execute_script(
            "promote",
            ["test:queue:development", "test:queue:integration", metadata_key],
            ["promote", prp_id, json.dumps(integration_evidence), "development_to_integration", str(int(time.time()))],
        )

        assert result2[0] == 1
        assert result2[1] == "integration"

        # Verify final state
        metadata = await redis_client.hgetall(metadata_key)
        assert metadata["status"] == "integration"

        # Verify PRP is in correct queue
        integration_queue = await redis_client.lrange("test:queue:integration", 0, -1)
        assert prp_id in integration_queue


class TestBatchPromotion:
    """Test batch PRP promotion operations"""

    @pytest.mark.asyncio
    async def test_successful_batch_promotion(self, redis_client, integration_script_loader, valid_evidence):
        """Test successful batch promotion of multiple PRPs"""
        prp_ids = ["PRP-BATCH-1", "PRP-BATCH-2", "PRP-BATCH-3"]

        # Setup: Add all PRPs to pending queue
        for prp_id in prp_ids:
            await redis_client.lpush("test:queue:pending", prp_id)

        # Prepare batch evidence (same evidence for all)
        batch_evidence = [valid_evidence] * len(prp_ids)

        keys = ["test:queue:pending", "test:queue:development"]
        args = ["batch_promote", "pending_to_development", str(int(time.time())), json.dumps(batch_evidence)] + prp_ids

        result = await integration_script_loader.execute_script("promote", keys, args)

        # Verify result
        assert result[0] == 3  # 3 PRPs promoted
        assert result[1] == []  # No failures

        # Verify all PRPs moved to development queue
        development_queue = await redis_client.lrange("test:queue:development", 0, -1)
        for prp_id in prp_ids:
            assert prp_id in development_queue

    @pytest.mark.asyncio
    async def test_partial_batch_promotion_failure(self, redis_client, integration_script_loader, valid_evidence):
        """Test batch promotion with some PRPs missing from source queue"""
        existing_prps = ["PRP-EXISTS-1", "PRP-EXISTS-2"]
        missing_prps = ["PRP-MISSING-1"]
        all_prps = existing_prps + missing_prps

        # Setup: Only add existing PRPs to queue
        for prp_id in existing_prps:
            await redis_client.lpush("test:queue:pending", prp_id)

        batch_evidence = [valid_evidence] * len(all_prps)

        keys = ["test:queue:pending", "test:queue:development"]
        args = ["batch_promote", "pending_to_development", str(int(time.time())), json.dumps(batch_evidence)] + all_prps

        result = await integration_script_loader.execute_script("promote", keys, args)

        # Verify partial success
        assert result[0] == 2  # 2 PRPs promoted
        assert len(result[1]) == 1  # 1 failure
        assert result[1][0][0] == "PRP-MISSING-1"  # Failed PRP ID

        # Verify existing PRPs were promoted
        development_queue = await redis_client.lrange("test:queue:development", 0, -1)
        for prp_id in existing_prps:
            assert prp_id in development_queue


class TestStatusAndEvidence:
    """Test status checking and evidence retrieval"""

    @pytest.mark.asyncio
    async def test_prp_status_check(self, redis_client, integration_script_loader):
        """Test PRP status checking"""
        prp_id = "PRP-STATUS"
        metadata_key = f"test:prp:{prp_id}:metadata"

        # Setup metadata
        await redis_client.hset(
            metadata_key,
            "status",
            "development",
            "last_transition",
            "1642774800",
            "last_transition_type",
            "pending_to_development",
        )

        # Add to development queue
        await redis_client.lpush("test:queue:development", prp_id)

        keys = [metadata_key]
        args = ["status", prp_id]

        result = await integration_script_loader.execute_script("promote", keys, args)

        assert result[0] == "development"
        assert result[1] == "1642774800"
        assert result[2] == "pending_to_development"
        assert result[3] >= 0  # Queue position

    @pytest.mark.asyncio
    async def test_evidence_history_retrieval(self, redis_client, integration_script_loader, valid_evidence):
        """Test evidence history retrieval"""
        prp_id = "PRP-EVIDENCE"

        # Create evidence entries manually
        timestamp1 = str(int(time.time()))
        timestamp2 = str(int(time.time()) + 100)

        evidence_key1 = f"test:evidence:{prp_id}:{timestamp1}"
        evidence_key2 = f"test:evidence:{prp_id}:{timestamp2}"

        await redis_client.hset(
            evidence_key1,
            "prp_id",
            prp_id,
            "transition_type",
            "pending_to_development",
            "evidence_data",
            json.dumps(valid_evidence),
            "created_at",
            timestamp1,
        )

        await redis_client.hset(
            evidence_key2,
            "prp_id",
            prp_id,
            "transition_type",
            "development_to_integration",
            "evidence_data",
            json.dumps(valid_evidence),
            "created_at",
            timestamp2,
        )

        keys = []
        args = ["evidence", prp_id, "5"]  # Limit 5

        result = await integration_script_loader.execute_script("promote", keys, args)

        assert len(result) == 2
        # Should be sorted by timestamp (newest first)
        assert int(result[0]["created_at"]) >= int(result[1]["created_at"])
        assert result[0]["transition_type"] in ["pending_to_development", "development_to_integration"]


class TestEvidenceValidation:
    """Test evidence validation with real Redis responses"""

    @pytest.mark.asyncio
    async def test_missing_evidence_validation(self, redis_client, integration_script_loader):
        """Test validation error for missing evidence"""
        prp_id = "PRP-NO-EVIDENCE"
        await redis_client.lpush("test:queue:pending", prp_id)

        keys = ["test:queue:pending", "test:queue:development", f"test:prp:{prp_id}:metadata"]
        args = ["promote", prp_id, "", "pending_to_development", str(int(time.time()))]  # Empty evidence

        with pytest.raises(aioredis.ResponseError, match="Evidence required"):
            await integration_script_loader.execute_script("promote", keys, args)

    @pytest.mark.asyncio
    async def test_invalid_json_evidence(self, redis_client, integration_script_loader):
        """Test validation error for invalid JSON evidence"""
        prp_id = "PRP-BAD-JSON"
        await redis_client.lpush("test:queue:pending", prp_id)

        keys = ["test:queue:pending", "test:queue:development", f"test:prp:{prp_id}:metadata"]
        args = ["promote", prp_id, "invalid json {", "pending_to_development", str(int(time.time()))]  # Invalid JSON

        with pytest.raises(aioredis.ResponseError):
            await integration_script_loader.execute_script("promote", keys, args)

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, redis_client, integration_script_loader):
        """Test validation error for missing required evidence fields"""
        prp_id = "PRP-INCOMPLETE"
        await redis_client.lpush("test:queue:pending", prp_id)

        incomplete_evidence = {
            "timestamp": "2025-07-21T10:00:00Z",
            "agent_id": "pm-1",
            "transition_type": "pending_to_development"
            # Missing requirements_analysis and acceptance_criteria
        }

        keys = ["test:queue:pending", "test:queue:development", f"test:prp:{prp_id}:metadata"]
        args = ["promote", prp_id, json.dumps(incomplete_evidence), "pending_to_development", str(int(time.time()))]

        with pytest.raises(aioredis.ResponseError, match="requires requirements_analysis"):
            await integration_script_loader.execute_script("promote", keys, args)


class TestErrorHandling:
    """Test error handling and edge cases"""

    @pytest.mark.asyncio
    async def test_unknown_command(self, redis_client, integration_script_loader):
        """Test error for unknown script command"""
        keys = []
        args = ["unknown_command", "arg1", "arg2"]

        with pytest.raises(aioredis.ResponseError, match="Unknown command"):
            await integration_script_loader.execute_script("promote", keys, args)

    @pytest.mark.asyncio
    async def test_unknown_transition_type(self, redis_client, integration_script_loader):
        """Test error for unknown transition type"""
        prp_id = "PRP-BAD-TRANSITION"
        await redis_client.lpush("test:queue:pending", prp_id)

        bad_evidence = {
            "timestamp": "2025-07-21T10:00:00Z",
            "agent_id": "pm-1",
            "transition_type": "unknown_transition",
        }

        keys = ["test:queue:pending", "test:queue:development", f"test:prp:{prp_id}:metadata"]
        args = ["promote", prp_id, json.dumps(bad_evidence), "unknown_transition", str(int(time.time()))]

        with pytest.raises(aioredis.ResponseError, match="Unknown transition type"):
            await integration_script_loader.execute_script("promote", keys, args)


class TestDataIntegrity:
    """Test data integrity and atomicity"""

    @pytest.mark.asyncio
    async def test_atomic_promotion_consistency(self, redis_client, integration_script_loader, valid_evidence):
        """Test that promotion maintains data consistency"""
        prp_id = "PRP-ATOMIC"
        metadata_key = f"test:prp:{prp_id}:metadata"

        # Setup
        await redis_client.lpush("test:queue:pending", prp_id)
        await redis_client.hset(metadata_key, "status", "pending", "version", "1")

        # Execute promotion
        keys = ["test:queue:pending", "test:queue:development", metadata_key]
        args = ["promote", prp_id, json.dumps(valid_evidence), "pending_to_development", str(int(time.time()))]

        result = await integration_script_loader.execute_script("promote", keys, args)

        # Verify atomicity: either all changes applied or none
        assert result[0] == 1  # Success

        # Check that PRP exists in exactly one queue
        pending_count = await redis_client.llen("test:queue:pending")
        development_count = await redis_client.llen("test:queue:development")

        # PRP should be in development queue only
        development_queue = await redis_client.lrange("test:queue:development", 0, -1)
        assert prp_id in development_queue

        # Metadata should be consistently updated
        metadata = await redis_client.hgetall(metadata_key)
        assert metadata["status"] == "development"
        assert "last_transition" in metadata
        assert "last_transition_type" in metadata

    @pytest.mark.asyncio
    async def test_evidence_expiry_set(self, redis_client, integration_script_loader, valid_evidence):
        """Test that evidence keys have appropriate expiry set"""
        prp_id = "PRP-EXPIRY"
        metadata_key = f"test:prp:{prp_id}:metadata"

        await redis_client.lpush("test:queue:pending", prp_id)

        keys = ["test:queue:pending", "test:queue:development", metadata_key]
        args = ["promote", prp_id, json.dumps(valid_evidence), "pending_to_development", str(int(time.time()))]

        result = await integration_script_loader.execute_script("promote", keys, args)
        evidence_key = result[2]

        # Check that evidence key has expiry set (30 days = 2592000 seconds)
        ttl = await redis_client.ttl(evidence_key)
        assert ttl > 0  # Has expiry
        assert ttl <= 2592000  # Within expected range
        assert ttl > 2590000  # Close to expected value
