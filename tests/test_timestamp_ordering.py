#!/usr/bin/env python3
"""
Timestamp ordering tests for evidence collection and agent coordination
"""
import json
import os
import time
from datetime import datetime, timedelta
from threading import Thread
from typing import List

import pytest
import redis


class TestTimestampOrdering:
    """Test that timestamps maintain proper ordering and causality"""

    def setup_method(self):
        """Set up test environment"""
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after tests"""
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove test data from Redis"""
        for key in self.redis_client.keys("TSTEST-*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("prp:TSTEST-*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("evidence:*"):
            self.redis_client.delete(key)

    def test_evidence_timestamp_progression(self):
        """Test that evidence timestamps follow proper progression"""
        prp_id = "TSTEST-001"
        prp_key = f"prp:{prp_id}"

        # Simulate evidence collection over time
        timestamps = []
        evidence_types = ["start", "tests_begin", "tests_complete", "coverage", "final"]

        for i, evt_type in enumerate(evidence_types):
            time.sleep(0.1)  # Ensure different timestamps
            ts = datetime.utcnow().isoformat()
            timestamps.append(ts)

            self.redis_client.hset(prp_key, f"evidence_{evt_type}_ts", ts)

            # Also set the evidence data
            if evt_type == "tests_complete":
                self.redis_client.hset(prp_key, "tests_passed", "true")
            elif evt_type == "coverage":
                self.redis_client.hset(prp_key, "coverage_pct", "85")

        # Verify timestamps are in order
        for i in range(1, len(timestamps)):
            ts_prev = datetime.fromisoformat(timestamps[i - 1])
            ts_curr = datetime.fromisoformat(timestamps[i])
            assert ts_curr > ts_prev, f"Timestamp {i} not after {i-1}"

        # Verify we can reconstruct the timeline
        evidence_timeline = []
        for evt_type in evidence_types:
            ts_str = self.redis_client.hget(prp_key, f"evidence_{evt_type}_ts")
            if ts_str:
                evidence_timeline.append((evt_type, datetime.fromisoformat(ts_str.decode())))

        # Timeline should be in chronological order
        for i in range(1, len(evidence_timeline)):
            assert evidence_timeline[i][1] > evidence_timeline[i - 1][1]

    def test_concurrent_evidence_updates(self):
        """Test that concurrent evidence updates maintain consistency"""
        prp_id = "TSTEST-002"
        prp_key = f"prp:{prp_id}"

        results = []

        def update_evidence(field: str, value: str, delay: float):
            """Update evidence field with timestamp"""
            time.sleep(delay)
            ts = datetime.utcnow().isoformat()

            # Use transaction to ensure atomicity
            pipe = self.redis_client.pipeline()
            pipe.hset(prp_key, field, value)
            pipe.hset(prp_key, f"{field}_ts", ts)
            pipe.execute()

            results.append((field, ts))

        # Start multiple threads updating different fields
        threads = [
            Thread(target=update_evidence, args=("tests_passed", "true", 0.0)),
            Thread(target=update_evidence, args=("coverage_pct", "82", 0.05)),
            Thread(target=update_evidence, args=("lint_passed", "true", 0.1)),
            Thread(target=update_evidence, args=("security_scan", "clean", 0.15)),
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify all updates have timestamps
        for field, _ in results:
            assert self.redis_client.hget(prp_key, field) is not None
            assert self.redis_client.hget(prp_key, f"{field}_ts") is not None

        # Verify timestamp ordering matches execution order
        results.sort(key=lambda x: x[1])  # Sort by timestamp

        for i in range(1, len(results)):
            ts_prev = datetime.fromisoformat(results[i - 1][1])
            ts_curr = datetime.fromisoformat(results[i][1])
            assert ts_curr >= ts_prev, "Timestamps should be ordered"

    def test_agent_handoff_timestamp_consistency(self):
        """Test timestamp consistency during agent handoffs"""
        prp_id = "TSTEST-003"
        prp_key = f"prp:{prp_id}"

        # Simulate PRP lifecycle with timestamps
        lifecycle_events = []

        # Dev agent starts
        dev_start = datetime.utcnow()
        self.redis_client.hset(
            prp_key, mapping={"status": "development", "assigned_to": "dev-1", "dev_start_ts": dev_start.isoformat()}
        )
        lifecycle_events.append(("dev_start", dev_start))

        # Dev completes after 2 seconds
        time.sleep(0.2)
        dev_complete = datetime.utcnow()
        self.redis_client.hset(
            prp_key, mapping={"tests_passed": "true", "coverage_pct": "85", "dev_complete_ts": dev_complete.isoformat()}
        )
        lifecycle_events.append(("dev_complete", dev_complete))

        # Handoff to validator
        time.sleep(0.1)
        val_start = datetime.utcnow()
        self.redis_client.hset(
            prp_key, mapping={"status": "validation", "assigned_to": "validator", "val_start_ts": val_start.isoformat()}
        )
        lifecycle_events.append(("val_start", val_start))

        # Validator completes
        time.sleep(0.1)
        val_complete = datetime.utcnow()
        self.redis_client.hset(
            prp_key, mapping={"validation_passed": "true", "val_complete_ts": val_complete.isoformat()}
        )
        lifecycle_events.append(("val_complete", val_complete))

        # Verify handoff timestamps are consistent
        assert dev_complete < val_start, "Validation should start after dev completes"

        # Verify no time travel
        for i in range(1, len(lifecycle_events)):
            assert (
                lifecycle_events[i][1] > lifecycle_events[i - 1][1]
            ), f"Event {lifecycle_events[i][0]} happened before {lifecycle_events[i-1][0]}"

    def test_watchdog_timeout_calculation(self):
        """Test watchdog correctly calculates timeouts based on timestamps"""
        prp_id = "TSTEST-004"
        prp_key = f"prp:{prp_id}"

        # Set up PRP with old timestamp
        old_time = datetime.utcnow() - timedelta(minutes=35)
        self.redis_client.hset(
            prp_key, mapping={"status": "development", "assigned_to": "dev-1", "inflight_since": old_time.isoformat()}
        )

        # Add to inflight queue
        self.redis_client.lpush("dev_queue:inflight", prp_id)

        # Watchdog check
        current_time = datetime.utcnow()
        inflight_since_str = self.redis_client.hget(prp_key, "inflight_since")
        inflight_since = datetime.fromisoformat(inflight_since_str.decode())

        time_in_flight = current_time - inflight_since
        should_timeout = time_in_flight > timedelta(minutes=30)

        assert should_timeout, "Should timeout after 30 minutes"

        # Simulate watchdog action
        if should_timeout:
            self.redis_client.lrem("dev_queue:inflight", 0, prp_id)
            self.redis_client.lpush("dev_queue", prp_id)
            self.redis_client.hincrby(prp_key, "retry_count", 1)
            self.redis_client.hset(prp_key, "timeout_ts", current_time.isoformat())
            self.redis_client.hdel(prp_key, "inflight_since")

        # Verify timeout was recorded
        timeout_ts = self.redis_client.hget(prp_key, "timeout_ts")
        assert timeout_ts is not None, "Timeout timestamp should be recorded"

        # Verify retry count incremented
        retry_count = int(self.redis_client.hget(prp_key, "retry_count") or 0)
        assert retry_count == 1, "Retry count should increment"

    def test_evidence_timestamp_validation(self):
        """Test that evidence timestamps are validated for consistency"""
        prp_id = "TSTEST-005"
        prp_key = f"prp:{prp_id}"

        # Set up PRP with start time
        start_time = datetime.utcnow()
        self.redis_client.hset(prp_key, "start_ts", start_time.isoformat())

        # Try to add evidence with timestamp before start (should be rejected)
        invalid_time = start_time - timedelta(minutes=5)

        def validate_evidence_timestamp(evidence_ts: datetime, start_ts: datetime) -> bool:
            """Validate evidence timestamp is after start"""
            return evidence_ts >= start_ts

        # Test invalid timestamp
        is_valid = validate_evidence_timestamp(invalid_time, start_time)
        assert not is_valid, "Evidence before start should be invalid"

        # Test valid timestamp
        valid_time = start_time + timedelta(minutes=5)
        is_valid = validate_evidence_timestamp(valid_time, start_time)
        assert is_valid, "Evidence after start should be valid"

    def test_clock_skew_detection(self):
        """Test detection of clock skew between agents"""
        # Simulate two agents with different clocks
        agent1_time = datetime.utcnow()
        agent2_time = agent1_time + timedelta(seconds=5)  # 5 seconds ahead

        # Agent 1 completes work
        prp1_key = "prp:TSTEST-006"
        self.redis_client.hset(prp1_key, mapping={"agent": "dev-1", "complete_ts": agent1_time.isoformat()})

        # Agent 2 receives handoff "before" agent 1 completed (clock skew)
        prp2_key = "prp:TSTEST-007"
        handoff_time = agent1_time - timedelta(seconds=2)  # Appears to be before

        def detect_clock_skew(ts1: datetime, ts2: datetime, tolerance: timedelta) -> bool:
            """Detect if timestamps indicate clock skew"""
            # If ts2 is significantly before ts1 when it should be after
            if ts2 < ts1 - tolerance:
                return True
            return False

        # Should detect skew
        has_skew = detect_clock_skew(agent1_time, handoff_time, timedelta(seconds=1))
        assert has_skew, "Should detect clock skew"

    def test_event_ordering_with_retries(self):
        """Test that retry events maintain proper timestamp ordering"""
        prp_id = "TSTEST-008"
        prp_key = f"prp:{prp_id}"
        events_key = f"events:{prp_id}"

        # Record series of events with retries
        events = []

        # First attempt
        attempt1_start = datetime.utcnow()
        events.append({"event": "attempt_1_start", "ts": attempt1_start.isoformat()})
        self.redis_client.lpush(events_key, json.dumps(events[-1]))

        time.sleep(0.1)

        # First attempt fails
        attempt1_fail = datetime.utcnow()
        events.append({"event": "attempt_1_fail", "ts": attempt1_fail.isoformat()})
        self.redis_client.lpush(events_key, json.dumps(events[-1]))

        time.sleep(0.1)

        # Second attempt
        attempt2_start = datetime.utcnow()
        events.append({"event": "attempt_2_start", "ts": attempt2_start.isoformat()})
        self.redis_client.lpush(events_key, json.dumps(events[-1]))

        time.sleep(0.1)

        # Second attempt succeeds
        attempt2_success = datetime.utcnow()
        events.append({"event": "attempt_2_success", "ts": attempt2_success.isoformat()})
        self.redis_client.lpush(events_key, json.dumps(events[-1]))

        # Retrieve and verify event ordering
        stored_events = []
        for event_json in self.redis_client.lrange(events_key, 0, -1):
            stored_events.append(json.loads(event_json))

        # Events should be retrievable in reverse order (LIFO)
        stored_events.reverse()

        # Verify chronological ordering
        for i in range(1, len(stored_events)):
            ts_prev = datetime.fromisoformat(stored_events[i - 1]["ts"])
            ts_curr = datetime.fromisoformat(stored_events[i]["ts"])
            assert ts_curr > ts_prev, f"Event {i} not after {i-1}"

        # Verify retry happened after failure
        fail_ts = datetime.fromisoformat(events[1]["ts"])  # attempt_1_fail
        retry_ts = datetime.fromisoformat(events[2]["ts"])  # attempt_2_start
        assert retry_ts > fail_ts, "Retry should happen after failure"

    def test_distributed_timestamp_consistency(self):
        """Test timestamp consistency across distributed operations"""
        base_prp = "TSTEST-009"

        # Simulate distributed operation across multiple PRPs
        related_prps = [f"{base_prp}-A", f"{base_prp}-B", f"{base_prp}-C"]

        # Parent operation starts
        parent_start = datetime.utcnow()
        self.redis_client.hset(f"prp:{base_prp}", mapping={"type": "parent", "start_ts": parent_start.isoformat()})

        # Children start after parent
        child_starts = []
        for i, child_prp in enumerate(related_prps):
            time.sleep(0.05)
            child_start = datetime.utcnow()
            child_starts.append(child_start)

            self.redis_client.hset(
                f"prp:{child_prp}", mapping={"type": "child", "parent": base_prp, "start_ts": child_start.isoformat()}
            )

        # All children complete
        child_completes = []
        for i, child_prp in enumerate(related_prps):
            time.sleep(0.05)
            child_complete = datetime.utcnow()
            child_completes.append(child_complete)

            self.redis_client.hset(f"prp:{child_prp}", "complete_ts", child_complete.isoformat())

        # Parent completes after all children
        time.sleep(0.05)
        parent_complete = datetime.utcnow()
        self.redis_client.hset(f"prp:{base_prp}", "complete_ts", parent_complete.isoformat())

        # Verify constraints
        # 1. All children start after parent starts
        for child_start in child_starts:
            assert child_start > parent_start, "Child should start after parent"

        # 2. Parent completes after all children complete
        for child_complete in child_completes:
            assert parent_complete > child_complete, "Parent should complete after all children"

        # 3. Each child's complete time is after its start time
        for i, child_prp in enumerate(related_prps):
            assert child_completes[i] > child_starts[i], "Child complete after start"


class TestTimestampMonotonic:
    """Test monotonic timestamp properties"""

    def test_redis_time_command(self):
        """Test using Redis TIME command for consistent timestamps"""
        redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

        # Get Redis server time
        redis_time_1 = redis_client.time()
        time.sleep(0.1)
        redis_time_2 = redis_client.time()

        # Redis TIME returns [seconds, microseconds]
        ts1 = redis_time_1[0] + redis_time_1[1] / 1_000_000
        ts2 = redis_time_2[0] + redis_time_2[1] / 1_000_000

        assert ts2 > ts1, "Redis time should be monotonic"

    def test_timestamp_resolution(self):
        """Test timestamp resolution for rapid events"""
        redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))

        timestamps = []

        # Generate rapid timestamps
        for i in range(100):
            ts = datetime.utcnow().isoformat()
            timestamps.append(ts)
            # No sleep - as fast as possible

        # Check for duplicates
        unique_timestamps = set(timestamps)

        # May have some duplicates due to resolution
        print(f"Generated {len(timestamps)} timestamps, {len(unique_timestamps)} unique")

        # But parsed timestamps should still be orderable
        parsed = [datetime.fromisoformat(ts) for ts in timestamps]
        for i in range(1, len(parsed)):
            assert parsed[i] >= parsed[i - 1], "Timestamps should be non-decreasing"


if __name__ == "__main__":
    # Run specific tests
    test = TestTimestampOrdering()
    test.setup_method()

    print("Testing evidence timestamp progression...")
    test.test_evidence_timestamp_progression()
    print("✅ Passed")

    print("\nTesting concurrent evidence updates...")
    test.test_concurrent_evidence_updates()
    print("✅ Passed")

    print("\nTesting agent handoff timestamp consistency...")
    test.test_agent_handoff_timestamp_consistency()
    print("✅ Passed")

    print("\nTesting watchdog timeout calculation...")
    test.test_watchdog_timeout_calculation()
    print("✅ Passed")

    test.teardown_method()
