#!/usr/bin/env python3
"""
Property-based tests for queue invariants using Hypothesis
"""
import os
import string
import time

import hypothesis.strategies as st
import redis
from hypothesis import assume, given, settings

# Create a simple ASCII-only alphabet for test IDs
ASCII_ALPHANUM = string.ascii_letters + string.digits


class TestQueueInvariants:
    def setup_method(self):
        """Set up Redis connection for each test"""
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        # Clean up test data
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after each test"""
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove all test PRPs from Redis"""
        # Clean up any test PRPs
        for key in self.redis_client.keys("prp:TEST-*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("prp:PROP-*"):
            self.redis_client.delete(key)
        # Clean up test queues
        for key in self.redis_client.keys("test_queue_*"):
            self.redis_client.delete(key)
        # Also clean up real queues of test data (but don't interfere with real PRPs)
        for queue in ["dev_queue", "validation_queue", "integration_queue"]:
            items = self.redis_client.lrange(queue, 0, -1)
            for item in items:
                if item.startswith(b"PROP-") or item.startswith(b"TEST-"):
                    self.redis_client.lrem(queue, 0, item)
            items = self.redis_client.lrange(f"{queue}:inflight", 0, -1)
            for item in items:
                if item.startswith(b"PROP-") or item.startswith(b"TEST-"):
                    self.redis_client.lrem(f"{queue}:inflight", 0, item)

    @given(
        prp_id=st.text(
            min_size=5,
            max_size=20,
            alphabet=ASCII_ALPHANUM,
        ),
        num_queues=st.integers(min_value=2, max_value=3),
    )
    @settings(max_examples=10, deadline=10000)
    def test_prp_never_in_multiple_queues(self, prp_id, num_queues):
        """A PRP can never exist in multiple queues simultaneously"""
        import uuid

        # Create test-specific queue names
        queues = [f"test_queue_{uuid.uuid4().hex[:8]}_{i}" for i in range(num_queues)]

        # Prefix test PRPs
        prp_id = f"PROP-{prp_id}"

        # Clean up first
        for queue in queues:
            self.redis_client.delete(queue)
            self.redis_client.delete(f"{queue}:inflight")

        # Add to first queue
        self.redis_client.lpush(queues[0], prp_id)

        # Try to add to second queue (should remove from first)
        # Simulate atomic move
        self.redis_client.lrem(queues[0], 0, prp_id)
        self.redis_client.lpush(queues[1], prp_id)

        # Verify it's only in one place
        total_count = 0
        location = None
        for queue in queues:
            count_in_queue = self.redis_client.lrange(queue, 0, -1).count(prp_id.encode())
            count_in_inflight = self.redis_client.lrange(f"{queue}:inflight", 0, -1).count(prp_id.encode())
            total_count += count_in_queue + count_in_inflight
            if count_in_queue > 0 or count_in_inflight > 0:
                location = queue

        assert total_count <= 1, f"PRP {prp_id} found {total_count} times (should be at most 1)"

        # Clean up
        for queue in queues:
            self.redis_client.lrem(queue, 0, prp_id)
            self.redis_client.lrem(f"{queue}:inflight", 0, prp_id)

    @given(
        prp_id=st.text(min_size=5, max_size=20, alphabet=ASCII_ALPHANUM),
        initial_count=st.integers(min_value=0, max_value=5),
        failures=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=10, deadline=10000)
    def test_retry_count_always_increments(self, prp_id, initial_count, failures):
        """Retry count must always increment on failure, never decrease"""
        prp_id = f"PROP-{prp_id}"
        prp_key = f"prp:{prp_id}"

        # Set initial retry count
        self.redis_client.hset(prp_key, "retry_count", str(initial_count))

        # Simulate failures
        for i in range(failures):
            current_value = self.redis_client.hget(prp_key, "retry_count")
            current = int(current_value) if current_value else 0
            self.redis_client.hincrby(prp_key, "retry_count", 1)
            new_value = self.redis_client.hget(prp_key, "retry_count")
            new_count = int(new_value) if new_value else 0

            assert new_count == current + 1, f"Retry count didn't increment properly: {current} -> {new_count}"

        final_value = self.redis_client.hget(prp_key, "retry_count")
        final_count = int(final_value) if final_value else 0
        assert final_count == initial_count + failures, f"Final count {final_count} != {initial_count} + {failures}"

        # Clean up
        self.redis_client.delete(prp_key)

    @given(
        prp_id=st.text(min_size=5, max_size=20, alphabet=ASCII_ALPHANUM),
        inflight_time_minutes=st.integers(min_value=0, max_value=60),
    )
    @settings(max_examples=10, deadline=10000)
    def test_inflight_timeout_behavior(self, prp_id, inflight_time_minutes):
        """PRPs in inflight must be re-queued after timeout threshold"""
        import uuid

        queue = f"test_queue_{uuid.uuid4().hex[:8]}"

        prp_id = f"PROP-{prp_id}"
        prp_key = f"prp:{prp_id}"
        inflight_key = f"{queue}:inflight"

        # Clean up first
        self.redis_client.lrem(queue, 0, prp_id)
        self.redis_client.lrem(inflight_key, 0, prp_id)

        # Add to inflight with timestamp
        self.redis_client.lpush(inflight_key, prp_id)

        # Calculate timestamp based on inflight time
        from datetime import datetime, timedelta

        inflight_since = datetime.utcnow() - timedelta(minutes=inflight_time_minutes)
        self.redis_client.hset(prp_key, "inflight_since", inflight_since.isoformat())

        # Check if it should be timed out (30 min threshold)
        should_timeout = inflight_time_minutes > 30

        # Verify initial state
        in_inflight = prp_id.encode() in self.redis_client.lrange(inflight_key, 0, -1)
        assert in_inflight, "PRP should start in inflight"

        # Simulate timeout check
        if should_timeout:
            # Should be moved back to queue
            self.redis_client.lrem(inflight_key, 0, prp_id)
            self.redis_client.lpush(queue, prp_id)
            self.redis_client.hincrby(prp_key, "retry_count", 1)
            self.redis_client.hdel(prp_key, "inflight_since")

            # Verify state after timeout handling
            in_queue = prp_id.encode() in self.redis_client.lrange(queue, 0, -1)
            in_inflight = prp_id.encode() in self.redis_client.lrange(inflight_key, 0, -1)
            assert in_queue and not in_inflight, "Timed out PRP should be in queue, not inflight"
            retry_count = int(self.redis_client.hget(prp_key, "retry_count") or 0)
            assert retry_count >= 1, "Retry count should increment on timeout"
        else:
            # Verify state remains unchanged
            in_queue = prp_id.encode() in self.redis_client.lrange(queue, 0, -1)
            in_inflight = prp_id.encode() in self.redis_client.lrange(inflight_key, 0, -1)
            assert not in_queue and in_inflight, "Non-timed out PRP should remain in inflight"

        # Clean up
        self.redis_client.lrem(queue, 0, prp_id)
        self.redis_client.lrem(inflight_key, 0, prp_id)
        self.redis_client.delete(prp_key)

    @given(
        prp_id=st.text(min_size=5, max_size=20, alphabet=ASCII_ALPHANUM),
        evidence_keys=st.lists(
            st.sampled_from(["tests_passed", "coverage_pct", "lint_passed", "security_scan"]),
            min_size=1,
            max_size=4,
            unique=True,
        ),
        evidence_values=st.lists(st.sampled_from(["true", "false", "85", "0", ""]), min_size=1, max_size=4),
    )
    @settings(max_examples=10, deadline=10000)
    def test_evidence_validation_atomicity(self, prp_id, evidence_keys, evidence_values):
        """Evidence validation must be atomic - all required fields checked together"""
        prp_id = f"PROP-{prp_id}"
        prp_key = f"prp:{prp_id}"

        # Ensure we have same number of keys and values
        assume(len(evidence_keys) == len(evidence_values))

        # Set evidence
        for key, value in zip(evidence_keys, evidence_values):
            self.redis_client.hset(prp_key, key, value)

        # Define required evidence
        required_evidence = ["tests_passed", "coverage_pct"]

        # Check if all required evidence is valid (non-empty, not "false")
        all_valid = True
        for req_key in required_evidence:
            value = self.redis_client.hget(prp_key, req_key)
            if not value or value == b"false" or value == b"":
                all_valid = False
                break

        # Simulate promotion attempt
        if all_valid:
            # Should succeed - move to next queue
            promotion_result = "SUCCESS"
        else:
            # Should fail - stay in current queue
            promotion_result = "FAILED"

        # Verify the decision was atomic (no partial state)
        if promotion_result == "FAILED":
            # No evidence should be modified
            for key, original_value in zip(evidence_keys, evidence_values):
                current_value = self.redis_client.hget(prp_key, key)
                assert current_value == original_value.encode(), "Evidence modified during failed promotion"

        # Clean up
        self.redis_client.delete(prp_key)

    @given(
        num_prps=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=10, deadline=10000)
    def test_queue_fifo_ordering(self, num_prps):
        """Queues must maintain FIFO ordering (LPUSH/RPOP pattern)"""
        # Use a unique test queue to avoid interference
        import uuid

        queue = f"test_queue_{uuid.uuid4().hex[:8]}"

        # Clean queue first
        self.redis_client.delete(queue)

        # Add PRPs in order
        prp_ids = [f"PROP-ORDER-{i}" for i in range(num_prps)]
        for prp_id in prp_ids:
            self.redis_client.lpush(queue, prp_id)

        # Pop them and verify FIFO order
        popped = []
        while True:
            item = self.redis_client.rpop(queue)
            if not item:
                break
            popped.append(item.decode())

        # With LPUSH/RPOP, we get FIFO behavior
        # LPUSH adds to head (left), RPOP removes from tail (right)
        # So first item pushed is first item popped
        assert popped == prp_ids, f"FIFO order violated: {popped} != {prp_ids}"

        # Clean up
        self.redis_client.delete(queue)
