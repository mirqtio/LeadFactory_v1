"""
Integration tests for Redis Lua promotion script
Tests the actual script execution against staging Redis
"""

import json
import os

# Use the redis_scripts package
import time
from pathlib import Path

import pytest
import redis

from redis_scripts.script_loader import ScriptLoader


@pytest.fixture(scope="module")
def redis_client():
    """Redis client for staging server"""
    redis_url = "redis://staging-infra-redis:6379/0"
    client = redis.from_url(redis_url, decode_responses=True)

    # Verify connection
    try:
        client.ping()
    except redis.ConnectionError:
        pytest.skip("Staging Redis server not available")

    yield client

    # Cleanup after tests
    client.flushdb()


@pytest.fixture
def script_loader_integration(redis_client):
    """Script loader with real Redis connection"""
    loader = ScriptLoader(redis_client)

    # Load the promotion script
    loader.load_script("promote")

    yield loader

    # Cleanup
    redis_client.flushdb()


@pytest.fixture
def valid_evidence():
    """Valid evidence for testing"""
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


class TestPromotionIntegration:
    """Integration tests with real Redis server"""

    def test_single_prp_promotion_real_redis(self, script_loader_integration, redis_client, valid_evidence):
        """Test single PRP promotion with real Redis"""
        # Setup test queues
        redis_client.lpush("queue:pending", "PRP-1059")

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
            str(int(time.time())),  # timestamp
        ]

        result = script_loader_integration.execute_script("promote", keys, args)

        # Verify successful promotion
        assert result[0] == 1  # success
        assert result[1] == "development"  # new state
        assert "evidence:PRP-1059" in result[2]  # evidence key created

        # Verify queue state changes
        assert redis_client.llen("queue:pending") == 0  # removed from source
        assert redis_client.llen("queue:development") == 1  # added to destination
        assert redis_client.lpop("queue:development") == "PRP-1059"

        # Verify metadata was created
        metadata = redis_client.hgetall("prp:PRP-1059:metadata")
        assert metadata["current_state"] == "development"
        assert metadata["transition_type"] == "pending_to_development"

    def test_batch_promotion_real_redis(self, script_loader_integration, redis_client, valid_evidence):
        """Test batch promotion with real Redis"""
        # Setup multiple PRPs in pending queue
        redis_client.lpush("queue:pending", "PRP-1059", "PRP-1060")

        batch_evidence = [valid_evidence, valid_evidence]

        keys = ["queue:pending", "queue:development"]
        args = [
            "batch_promote",
            "pending_to_development",
            str(int(time.time())),
            json.dumps(batch_evidence),
            "PRP-1059",
            "PRP-1060",
        ]

        result = script_loader_integration.execute_script("promote", keys, args)

        # Verify batch promotion results
        assert result[0] == 2  # 2 PRPs promoted
        assert result[1] == []  # no failures

        # Verify queue states
        assert redis_client.llen("queue:pending") == 0
        assert redis_client.llen("queue:development") == 2

    def test_prp_status_real_redis(self, script_loader_integration, redis_client):
        """Test PRP status retrieval with real Redis"""
        # Setup PRP metadata
        prp_id = "PRP-1059"
        metadata = {
            "current_state": "development",
            "last_transition": str(int(time.time())),
            "transition_type": "pending_to_development",
        }
        redis_client.hset(f"prp:{prp_id}:metadata", mapping=metadata)
        redis_client.lpush("queue:development", prp_id)

        keys = [f"prp:{prp_id}:metadata", "queue:development"]
        args = ["status", prp_id]

        result = script_loader_integration.execute_script("promote", keys, args)

        assert result[0] == "development"  # current state
        assert result[1] == metadata["last_transition"]  # last transition time
        assert result[2] == "pending_to_development"  # transition type
        assert result[3] >= 0  # queue position

    def test_evidence_validation_failure(self, script_loader_integration, redis_client):
        """Test evidence validation failure with real Redis"""
        redis_client.lpush("queue:pending", "PRP-1059")

        # Invalid evidence - missing required fields
        invalid_evidence = {
            "timestamp": "2025-07-21T10:00:00Z",
            "agent_id": "pm-1",
            "transition_type": "pending_to_development",
            # Missing requirements_analysis and acceptance_criteria
        }

        keys = [
            "queue:pending",
            "queue:development",
            "prp:PRP-1059:metadata",
        ]
        args = [
            "promote",
            "PRP-1059",
            json.dumps(invalid_evidence),
            "pending_to_development",
            str(int(time.time())),
        ]

        # Should raise error for missing required fields
        with pytest.raises(redis.ResponseError, match="requires"):
            script_loader_integration.execute_script("promote", keys, args)

        # Verify PRP remains in original queue
        assert redis_client.llen("queue:pending") == 1
        assert redis_client.llen("queue:development") == 0

    def test_transition_type_mismatch_error(self, script_loader_integration, redis_client, valid_evidence):
        """Test error when evidence transition type doesn't match"""
        redis_client.lpush("queue:pending", "PRP-1059")

        # Evidence has wrong transition type
        wrong_evidence = valid_evidence.copy()
        wrong_evidence["transition_type"] = "wrong_transition"

        keys = [
            "queue:pending",
            "queue:development",
            "prp:PRP-1059:metadata",
        ]
        args = [
            "promote",
            "PRP-1059",
            json.dumps(wrong_evidence),
            "pending_to_development",
            str(int(time.time())),
        ]

        with pytest.raises(redis.ResponseError, match="transition_type must match"):
            script_loader_integration.execute_script("promote", keys, args)

    def test_prp_not_in_queue_error(self, script_loader_integration, redis_client, valid_evidence):
        """Test error when PRP is not in source queue"""
        # Don't add PRP to queue

        keys = [
            "queue:pending",
            "queue:development",
            "prp:PRP-1059:metadata",
        ]
        args = [
            "promote",
            "PRP-1059",
            json.dumps(valid_evidence),
            "pending_to_development",
            str(int(time.time())),
        ]

        with pytest.raises(redis.ResponseError, match="not found in queue"):
            script_loader_integration.execute_script("promote", keys, args)

    def test_evidence_history_storage(self, script_loader_integration, redis_client, valid_evidence):
        """Test that evidence is properly stored for history"""
        redis_client.lpush("queue:pending", "PRP-1059")

        keys = [
            "queue:pending",
            "queue:development",
            "prp:PRP-1059:metadata",
        ]
        args = [
            "promote",
            "PRP-1059",
            json.dumps(valid_evidence),
            "pending_to_development",
            str(int(time.time())),
        ]

        result = script_loader_integration.execute_script("promote", keys, args)
        evidence_key = result[2]  # evidence key returned

        # Verify evidence was stored
        stored_evidence = redis_client.hgetall(evidence_key)
        assert stored_evidence["transition_type"] == "pending_to_development"
        assert stored_evidence["evidence_data"] == json.dumps(valid_evidence)

        # Test evidence retrieval
        keys = []
        args = ["evidence", "PRP-1059", "10"]  # get last 10 entries

        evidence_history = script_loader_integration.execute_script("promote", keys, args)

        assert len(evidence_history) == 1
        assert evidence_history[0]["transition_type"] == "pending_to_development"


class TestPerformanceIntegration:
    """Performance testing with real Redis"""

    def test_promotion_performance_single(self, script_loader_integration, redis_client, valid_evidence):
        """Test single promotion performance"""
        # Setup
        redis_client.lpush("queue:pending", "PRP-1059")

        keys = [
            "queue:pending",
            "queue:development",
            "prp:PRP-1059:metadata",
        ]
        args = [
            "promote",
            "PRP-1059",
            json.dumps(valid_evidence),
            "pending_to_development",
            str(int(time.time())),
        ]

        # Measure execution time
        start_time = time.perf_counter()
        result = script_loader_integration.execute_script("promote", keys, args)
        end_time = time.perf_counter()

        execution_time = (end_time - start_time) * 1000 * 1000  # Convert to microseconds

        # Should be well under 50μs target (allowing for test environment overhead)
        assert execution_time < 1000  # 1ms is generous for test environment
        assert result[0] == 1  # Successful promotion

    def test_promotion_performance_batch(self, script_loader_integration, redis_client, valid_evidence):
        """Test batch promotion performance"""
        # Setup 10 PRPs
        prp_ids = [f"PRP-{1059 + i}" for i in range(10)]
        redis_client.lpush("queue:pending", *prp_ids)

        batch_evidence = [valid_evidence] * 10

        keys = ["queue:pending", "queue:development"]
        args = [
            "batch_promote",
            "pending_to_development",
            str(int(time.time())),
            json.dumps(batch_evidence),
        ] + prp_ids

        # Measure batch execution time
        start_time = time.perf_counter()
        result = script_loader_integration.execute_script("promote", keys, args)
        end_time = time.perf_counter()

        execution_time = (end_time - start_time) * 1000 * 1000  # microseconds
        per_prp_time = execution_time / 10

        # Should be under 50μs per PRP even in batch
        assert per_prp_time < 500  # 500μs per PRP is generous for test environment
        assert result[0] == 10  # All PRPs promoted
        assert result[1] == []  # No failures

    def test_script_caching_performance(self, script_loader_integration):
        """Test that script caching improves performance"""
        keys = ["test_queue"]
        args = ["check_queue", "test_queue"]

        # First execution (may need to load script)
        start1 = time.perf_counter()
        try:
            script_loader_integration.execute_script("promote", keys, args)
        except redis.ResponseError:
            pass  # Expected for invalid command
        end1 = time.perf_counter()

        # Second execution (should use cached script)
        start2 = time.perf_counter()
        try:
            script_loader_integration.execute_script("promote", keys, args)
        except redis.ResponseError:
            pass  # Expected for invalid command
        end2 = time.perf_counter()

        time1 = (end1 - start1) * 1000 * 1000
        time2 = (end2 - start2) * 1000 * 1000

        # Second execution should be faster or similar (cached)
        assert time2 <= time1 * 1.5  # Allow 50% variance for test environment
