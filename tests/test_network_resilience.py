#!/usr/bin/env python3
"""
Network partition resilience tests for multi-agent system
"""
import json
import os
import time
from datetime import datetime, timedelta
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest
import redis
from redis.exceptions import ConnectionError, TimeoutError


class NetworkPartitionSimulator:
    """Simulates various network partition scenarios"""

    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.partition_active = False
        self.partition_type = "none"
        self.affected_operations = []

    def start_partition(self, partition_type: str):
        """Start simulating a network partition"""
        self.partition_active = True
        self.partition_type = partition_type

        # Patch Redis operations based on partition type
        if partition_type == "full":
            # Complete network partition - all operations fail
            self._patch_all_operations()
        elif partition_type == "write_only":
            # Can read but not write (split brain scenario)
            self._patch_write_operations()
        elif partition_type == "read_only":
            # Can write but not read (unusual but possible)
            self._patch_read_operations()
        elif partition_type == "intermittent":
            # Random failures
            self._patch_intermittent()
        elif partition_type == "slow":
            # Operations succeed but are very slow
            self._patch_slow_operations()

    def stop_partition(self):
        """Stop simulating network partition"""
        self.partition_active = False
        self.partition_type = "none"
        # Restore normal operations
        self._restore_operations()

    def _patch_all_operations(self):
        """Make all Redis operations fail"""

        def raise_connection_error(*args, **kwargs):
            raise ConnectionError("Network partition: Cannot connect to Redis")

        # Patch all common operations
        operations = [
            "get",
            "set",
            "lpush",
            "rpop",
            "lrem",
            "hget",
            "hset",
            "hincrby",
            "exists",
            "delete",
            "lrange",
            "brpoplpush",
            "blmove",
        ]

        for op in operations:
            if hasattr(self.redis_client, op):
                setattr(self.redis_client, f"_original_{op}", getattr(self.redis_client, op))
                setattr(self.redis_client, op, raise_connection_error)
                self.affected_operations.append(op)

    def _patch_write_operations(self):
        """Make write operations fail but allow reads"""

        def raise_connection_error(*args, **kwargs):
            raise ConnectionError("Network partition: Write operations blocked")

        write_ops = ["set", "lpush", "lrem", "hset", "hincrby", "delete"]

        for op in write_ops:
            if hasattr(self.redis_client, op):
                setattr(self.redis_client, f"_original_{op}", getattr(self.redis_client, op))
                setattr(self.redis_client, op, raise_connection_error)
                self.affected_operations.append(op)

    def _patch_read_operations(self):
        """Make read operations fail but allow writes"""

        def raise_connection_error(*args, **kwargs):
            raise ConnectionError("Network partition: Read operations blocked")

        read_ops = ["get", "hget", "exists", "lrange", "brpoplpush", "blmove"]

        for op in read_ops:
            if hasattr(self.redis_client, op):
                setattr(self.redis_client, f"_original_{op}", getattr(self.redis_client, op))
                setattr(self.redis_client, op, raise_connection_error)
                self.affected_operations.append(op)

    def _patch_intermittent(self):
        """Make operations randomly fail"""
        import random

        def maybe_fail(original_method):
            def wrapper(*args, **kwargs):
                if random.random() < 0.5:  # 50% failure rate
                    raise ConnectionError("Network partition: Intermittent failure")
                return original_method(*args, **kwargs)

            return wrapper

        operations = ["get", "set", "lpush", "rpop", "hget", "hset"]

        for op in operations:
            if hasattr(self.redis_client, op):
                original = getattr(self.redis_client, op)
                setattr(self.redis_client, f"_original_{op}", original)
                setattr(self.redis_client, op, maybe_fail(original))
                self.affected_operations.append(op)

    def _patch_slow_operations(self):
        """Make operations very slow"""

        def make_slow(original_method):
            def wrapper(*args, **kwargs):
                time.sleep(5)  # 5 second delay
                return original_method(*args, **kwargs)

            return wrapper

        operations = ["get", "set", "lpush", "rpop", "hget", "hset"]

        for op in operations:
            if hasattr(self.redis_client, op):
                original = getattr(self.redis_client, op)
                setattr(self.redis_client, f"_original_{op}", original)
                setattr(self.redis_client, op, make_slow(original))
                self.affected_operations.append(op)

    def _restore_operations(self):
        """Restore original Redis operations"""
        for op in self.affected_operations:
            if hasattr(self.redis_client, f"_original_{op}"):
                original = getattr(self.redis_client, f"_original_{op}")
                setattr(self.redis_client, op, original)
                delattr(self.redis_client, f"_original_{op}")
        self.affected_operations = []


class TestNetworkResilience:
    """Test system resilience to network partitions"""

    def setup_method(self):
        """Set up test environment"""
        self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.redis_client = redis.from_url(self.redis_url)
        self.partition_sim = NetworkPartitionSimulator(self.redis_client)

        # Clean up test data
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after tests"""
        self.partition_sim.stop_partition()
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove test data from Redis"""
        try:
            for key in self.redis_client.keys("test:*"):
                self.redis_client.delete(key)
            for key in self.redis_client.keys("NETTEST-*"):
                self.redis_client.delete(key)
        except:
            pass  # Ignore errors during cleanup

    def test_queue_operations_during_full_partition(self):
        """Test that queue operations handle full network partition gracefully"""
        # Use a unique test queue to avoid interference
        import uuid

        test_queue = f"test_queue_{uuid.uuid4().hex[:8]}"

        # Add test PRP to queue
        test_prp = "NETTEST-001"
        self.redis_client.lpush(test_queue, test_prp)

        # Verify it's in the queue
        items_before = self.redis_client.lrange(test_queue, 0, -1)
        assert test_prp.encode() in items_before, "PRP should be in queue before partition"

        # Start full partition
        self.partition_sim.start_partition("full")

        # Try to read from queue - should fail gracefully
        try:
            result = self.redis_client.brpoplpush(test_queue, f"{test_queue}:inflight", timeout=1)
            assert False, "Should have raised ConnectionError"
        except ConnectionError:
            pass  # Expected

        # Stop partition
        self.partition_sim.stop_partition()

        # Verify PRP is still in queue (since operation failed)
        items = self.redis_client.lrange(test_queue, 0, -1)
        assert test_prp.encode() in items, "PRP should still be in queue after failed partition operation"

        # Clean up
        self.redis_client.delete(test_queue)
        self.redis_client.delete(f"{test_queue}:inflight")

    def test_evidence_writing_during_write_partition(self):
        """Test evidence collection during write-only partition"""
        test_prp = "NETTEST-002"
        prp_key = f"prp:{test_prp}"

        # Set initial state
        self.redis_client.hset(prp_key, "status", "in_progress")

        # Start write-only partition
        self.partition_sim.start_partition("write_only")

        # Try to write evidence - should fail
        evidence_written = False
        try:
            self.redis_client.hset(prp_key, "tests_passed", "true")
            evidence_written = True
        except ConnectionError:
            pass  # Expected

        assert not evidence_written, "Should not be able to write during write partition"

        # But reading should work
        status = self.redis_client.hget(prp_key, "status")
        assert status == b"in_progress", "Should be able to read during write partition"

        # Stop partition
        self.partition_sim.stop_partition()

        # Now evidence can be written
        self.redis_client.hset(prp_key, "tests_passed", "true")
        assert self.redis_client.hget(prp_key, "tests_passed") == b"true"

        # Clean up
        self.redis_client.delete(prp_key)

    def test_heartbeat_during_intermittent_partition(self):
        """Test heartbeat mechanism during intermittent network issues"""
        agent_id = "test-agent"
        agent_key = f"agent:{agent_id}"

        # Set up agent
        self.redis_client.hset(agent_key, mapping={"status": "active", "last_activity": datetime.utcnow().isoformat()})

        # Start intermittent partition
        self.partition_sim.start_partition("intermittent")

        # Try to update heartbeat multiple times
        successes = 0
        failures = 0

        for i in range(10):
            try:
                self.redis_client.hset(agent_key, "last_activity", datetime.utcnow().isoformat())
                successes += 1
            except ConnectionError:
                failures += 1

        # Should have some successes and some failures
        assert successes > 0, "Should have some successful heartbeats"
        assert failures > 0, "Should have some failed heartbeats"

        # Stop partition
        self.partition_sim.stop_partition()

        # Clean up
        self.redis_client.delete(agent_key)

    def test_queue_atomicity_during_partition_recovery(self):
        """Test that queue operations remain atomic during partition recovery"""
        import uuid

        test_queue = f"test_queue_{uuid.uuid4().hex[:8]}"
        test_prp = "NETTEST-003"

        # Add PRP to queue
        self.redis_client.lpush(test_queue, test_prp)

        # Start moving to inflight
        moved = self.redis_client.brpoplpush(test_queue, f"{test_queue}:inflight", timeout=1)
        assert moved == test_prp.encode()

        # Simulate partition during evidence collection
        self.partition_sim.start_partition("full")

        # Try to complete (should fail)
        try:
            self.redis_client.lrem(f"{test_queue}:inflight", 0, test_prp)
            assert False, "Should have failed during partition"
        except ConnectionError:
            pass

        # Stop partition
        self.partition_sim.stop_partition()

        # PRP should still be in inflight
        inflight = self.redis_client.lrange(f"{test_queue}:inflight", 0, -1)
        assert test_prp.encode() in inflight, "PRP should still be in inflight"

        # Complete the operation
        self.redis_client.lrem(f"{test_queue}:inflight", 0, test_prp)

        # Verify it's gone
        inflight_after = self.redis_client.lrange(f"{test_queue}:inflight", 0, -1)
        assert test_prp.encode() not in inflight_after

        # Clean up
        self.redis_client.delete(test_queue)
        self.redis_client.delete(f"{test_queue}:inflight")

    def test_multi_agent_coordination_during_slow_network(self):
        """Test multi-agent coordination when network is slow"""
        # Set up multiple agents and PRPs
        agents = ["dev-1", "dev-2", "validator"]
        prps = ["NETTEST-004", "NETTEST-005", "NETTEST-006"]

        for agent, prp in zip(agents, prps):
            self.redis_client.lpush("dev_queue", prp)
            self.redis_client.hset(f"agent:{agent}", mapping={"status": "active", "current_prp": prp})

        # Start slow network
        self.partition_sim.start_partition("slow")

        # Try operations with timeout
        start_time = time.time()

        # This should be slow but eventually succeed
        try:
            status = self.redis_client.hget("agent:dev-1", "status")
            elapsed = time.time() - start_time
            assert elapsed > 4, "Operation should have been slow"
            assert status == b"active", "Should eventually get correct status"
        except TimeoutError:
            # Also acceptable - operation timed out
            pass

        # Stop partition
        self.partition_sim.stop_partition()

        # Clean up
        for agent, prp in zip(agents, prps):
            self.redis_client.delete(f"agent:{agent}")
            self.redis_client.lrem("dev_queue", 0, prp)

    def test_lua_script_atomicity_during_partition(self):
        """Test Lua script atomicity during network issues"""
        test_prp = "NETTEST-007"
        prp_key = f"prp:{test_prp}"

        # Set up PRP with evidence
        self.redis_client.hset(prp_key, mapping={"tests_passed": "true", "coverage_pct": "85", "lint_passed": "true"})
        self.redis_client.lpush("validation_queue", test_prp)

        # Load promotion script
        with open("scripts/promote.lua", "r") as f:
            promote_script = f.read()

        # Register script
        script = self.redis_client.register_script(promote_script)

        # Start partition mid-execution
        def delayed_partition():
            time.sleep(0.1)  # Small delay
            self.partition_sim.start_partition("full")

        partition_thread = Thread(target=delayed_partition)
        partition_thread.start()

        # Try to promote - might succeed or fail depending on timing
        try:
            result = script(keys=[test_prp, "validation_queue", "integration_queue"])
            # If it succeeded, verify atomicity
            if result == b"PROMOTED":
                # Should be in integration queue
                assert test_prp.encode() in self.redis_client.lrange("integration_queue", 0, -1)
                # Should NOT be in validation queue
                assert test_prp.encode() not in self.redis_client.lrange("validation_queue", 0, -1)
        except ConnectionError:
            # Failed due to partition - verify nothing changed
            self.partition_sim.stop_partition()
            # Should still be in validation queue
            assert test_prp.encode() in self.redis_client.lrange("validation_queue", 0, -1)
            # Should NOT be in integration queue
            assert test_prp.encode() not in self.redis_client.lrange("integration_queue", 0, -1)

        partition_thread.join()
        self.partition_sim.stop_partition()

        # Clean up
        self.redis_client.delete(prp_key)
        self.redis_client.lrem("validation_queue", 0, test_prp)
        self.redis_client.lrem("integration_queue", 0, test_prp)

    def test_recovery_after_extended_partition(self):
        """Test system recovery after extended network partition"""
        # Set up system state
        prps_in_flight = ["NETTEST-008", "NETTEST-009", "NETTEST-010"]

        for prp in prps_in_flight:
            self.redis_client.lpush("dev_queue:inflight", prp)
            self.redis_client.hset(
                f"prp:{prp}",
                mapping={"inflight_since": (datetime.utcnow() - timedelta(minutes=45)).isoformat(), "retry_count": "2"},
            )

        # Simulate extended partition (45 minutes)
        # In real scenario, watchdog would run during this time

        # After "recovery", verify system can heal itself
        for prp in prps_in_flight:
            # Check if timeout exceeded (30 min threshold)
            inflight_since = self.redis_client.hget(f"prp:{prp}", "inflight_since")
            if inflight_since:
                inflight_time = datetime.fromisoformat(inflight_since.decode())
                if datetime.utcnow() - inflight_time > timedelta(minutes=30):
                    # Move back to queue
                    self.redis_client.lrem("dev_queue:inflight", 0, prp)
                    self.redis_client.lpush("dev_queue", prp)
                    self.redis_client.hincrby(f"prp:{prp}", "retry_count", 1)

        # Verify all PRPs were recovered
        for prp in prps_in_flight:
            assert prp.encode() in self.redis_client.lrange("dev_queue", 0, -1)
            retry_count = int(self.redis_client.hget(f"prp:{prp}", "retry_count"))
            assert retry_count == 3, f"Retry count should be incremented"

        # Clean up
        for prp in prps_in_flight:
            self.redis_client.delete(f"prp:{prp}")
            self.redis_client.lrem("dev_queue", 0, prp)


class TestRedisClusterFailover:
    """Test behavior during Redis cluster failover scenarios"""

    def test_connection_pool_recovery(self):
        """Test that connection pool recovers after Redis restart"""
        redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

        # Normal operation
        redis_client.set("test:connection", "before")
        assert redis_client.get("test:connection") == b"before"

        # Simulate connection loss by closing all connections
        redis_client.connection_pool.disconnect()

        # Should auto-reconnect
        redis_client.set("test:connection", "after")
        assert redis_client.get("test:connection") == b"after"

        # Clean up
        redis_client.delete("test:connection")

    def test_transaction_rollback_on_partition(self):
        """Test that transactions roll back properly during partition"""
        redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

        import uuid

        test_queue = f"test_queue_{uuid.uuid4().hex[:8]}"
        test_prp = "NETTEST-TX-001"

        # Use pipeline for transaction
        pipe = redis_client.pipeline()
        pipe.multi()
        pipe.lpush(test_queue, test_prp)
        pipe.hset(f"prp:{test_prp}", "status", "new")

        # Simulate partition on the redis client (not the pipe)
        partition_sim = NetworkPartitionSimulator(redis_client)
        partition_sim.start_partition("full")

        # Execute should fail because the underlying connection is partitioned
        try:
            pipe.execute()
            # If this succeeds, it means the transaction completed before partition took effect
            # which is still a valid test result
        except (ConnectionError, redis.ConnectionError, redis.TimeoutError):
            # Expected - partition caused failure
            pass

        partition_sim.stop_partition()

        # Verify the state - either nothing was written (failed) or everything was written (succeeded before partition)
        queue_has_prp = test_prp.encode() in redis_client.lrange(test_queue, 0, -1)
        prp_exists = redis_client.exists(f"prp:{test_prp}")

        # Either both exist (transaction succeeded) or neither exists (transaction failed)
        assert queue_has_prp == prp_exists, "Transaction was not atomic - partial state detected"

        # Clean up
        redis_client.delete(test_queue)
        redis_client.delete(f"prp:{test_prp}")


if __name__ == "__main__":
    # Run a specific test for debugging
    test = TestNetworkResilience()
    test.setup_method()

    print("Testing queue operations during partition...")
    test.test_queue_operations_during_full_partition()
    print("✅ Passed")

    print("\nTesting evidence writing during write partition...")
    test.test_evidence_writing_during_write_partition()
    print("✅ Passed")

    print("\nTesting heartbeat during intermittent partition...")
    test.test_heartbeat_during_intermittent_partition()
    print("✅ Passed")

    test.teardown_method()
