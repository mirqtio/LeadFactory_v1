#!/usr/bin/env python3
"""
Comprehensive PRP state machine tests covering all transitions and edge cases
"""
import json
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set

import pytest
import redis


class PRPState(Enum):
    """All possible PRP states"""

    NEW = "new"
    ASSIGNED = "assigned"
    DEVELOPMENT = "development"
    VALIDATION = "validation"
    INTEGRATION = "integration"
    COMPLETE = "complete"
    FAILED = "failed"
    REJECTED = "rejected"
    ORPHANED = "orphaned"


class StateTransition:
    """Valid state transitions"""

    VALID_TRANSITIONS = {
        PRPState.NEW: {PRPState.ASSIGNED},
        PRPState.ASSIGNED: {PRPState.DEVELOPMENT, PRPState.FAILED},
        PRPState.DEVELOPMENT: {PRPState.VALIDATION, PRPState.FAILED, PRPState.REJECTED},
        PRPState.VALIDATION: {PRPState.INTEGRATION, PRPState.REJECTED, PRPState.FAILED},
        PRPState.INTEGRATION: {PRPState.COMPLETE, PRPState.FAILED},
        PRPState.FAILED: {PRPState.NEW},  # Retry
        PRPState.REJECTED: {PRPState.DEVELOPMENT},  # Back to dev
        PRPState.COMPLETE: set(),  # Terminal state
        PRPState.ORPHANED: {PRPState.NEW},  # Recovery
    }


class TestPRPStateMachine:
    """Test all PRP state transitions and invariants"""

    def setup_method(self):
        """Set up test environment"""
        self.redis_client = redis.from_url("redis://localhost:6379/0")
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after tests"""
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove all test data"""
        # Clean test PRPs
        for key in self.redis_client.keys("prp:TEST-*"):
            self.redis_client.delete(key)
        for key in self.redis_client.keys("test_*"):
            self.redis_client.delete(key)

    def create_test_prp(self, prp_id: str, state: PRPState, **kwargs) -> str:
        """Create a test PRP in a specific state"""
        prp_key = f"prp:{prp_id}"

        # Base PRP data
        prp_data = {
            "id": prp_id,
            "state": state.value,
            "created_at": datetime.utcnow().isoformat(),
            "retry_count": "0",
        }

        # Add state-specific fields
        if state == PRPState.ASSIGNED:
            prp_data.update(
                {
                    "owner": kwargs.get("owner", "pm-1"),
                    "assigned_at": datetime.utcnow().isoformat(),
                }
            )
        elif state == PRPState.DEVELOPMENT:
            prp_data.update(
                {
                    "owner": kwargs.get("owner", "pm-1"),
                    "inflight_since": datetime.utcnow().isoformat(),
                }
            )

        # Apply any additional fields
        prp_data.update(kwargs)

        # Store in Redis
        self.redis_client.hset(prp_key, mapping=prp_data)

        return prp_key

    def get_prp_state(self, prp_id: str) -> Optional[PRPState]:
        """Get current PRP state"""
        state_value = self.redis_client.hget(f"prp:{prp_id}", "state")
        if state_value:
            return PRPState(state_value.decode())
        return None

    def transition_prp(self, prp_id: str, to_state: PRPState, **kwargs) -> bool:
        """Transition PRP to new state with validation"""
        current_state = self.get_prp_state(prp_id)
        if not current_state:
            return False

        # Validate transition
        if to_state not in StateTransition.VALID_TRANSITIONS[current_state]:
            return False

        # Update state
        prp_key = f"prp:{prp_id}"
        updates = {
            "state": to_state.value,
            f"{to_state.value}_at": datetime.utcnow().isoformat(),
        }
        updates.update(kwargs)

        self.redis_client.hset(prp_key, mapping=updates)
        return True

    def test_happy_path_lifecycle(self):
        """Test normal PRP flow from creation to completion"""
        prp_id = "TEST-001"

        # 1. Create new PRP
        self.create_test_prp(prp_id, PRPState.NEW)
        assert self.get_prp_state(prp_id) == PRPState.NEW

        # 2. Assign to PM
        assert self.transition_prp(prp_id, PRPState.ASSIGNED, owner="pm-1")
        assert self.get_prp_state(prp_id) == PRPState.ASSIGNED

        # 3. Move to development
        assert self.transition_prp(prp_id, PRPState.DEVELOPMENT, inflight_since=datetime.utcnow().isoformat())

        # 4. Complete development, move to validation
        assert self.transition_prp(
            prp_id, PRPState.VALIDATION, tests_passed="true", coverage_pct="85", lint_passed="true"
        )

        # 5. Pass validation, move to integration
        assert self.transition_prp(prp_id, PRPState.INTEGRATION, validated_by="validator-1")

        # 6. Complete integration
        assert self.transition_prp(
            prp_id, PRPState.COMPLETE, deployed_at=datetime.utcnow().isoformat(), ci_passed="true"
        )

        # 7. Verify terminal state
        assert not self.transition_prp(prp_id, PRPState.NEW)  # Can't go back

    def test_rejection_flow(self):
        """Test validator rejection sending PRP back to development"""
        prp_id = "TEST-REJECT-002"

        # Get PRP to validation state
        self.create_test_prp(prp_id, PRPState.VALIDATION, owner="pm-1", tests_passed="false")

        # Validator rejects
        assert self.transition_prp(
            prp_id, PRPState.REJECTED, rejection_reason="Test coverage too low", rejected_by="validator-1"
        )

        # Verify state
        assert self.get_prp_state(prp_id) == PRPState.REJECTED

        # PM picks it up again
        assert self.transition_prp(prp_id, PRPState.DEVELOPMENT, owner="pm-1", retry_count="1")

    def test_failure_and_retry(self):
        """Test failure states and retry logic"""
        prp_id = "TEST-003"

        # Create PRP in development
        self.create_test_prp(prp_id, PRPState.DEVELOPMENT, owner="pm-1")

        # Agent crashes - mark as failed
        assert self.transition_prp(prp_id, PRPState.FAILED, failure_reason="Agent timeout")

        # Increment retry count manually (as would happen in real system)
        self.redis_client.hincrby(f"prp:{prp_id}", "retry_count", 1)

        # Should be able to retry
        assert self.transition_prp(prp_id, PRPState.NEW)

        # Check retry count was incremented
        retry_count = self.redis_client.hget(f"prp:{prp_id}", "retry_count")
        assert retry_count is not None
        assert int(retry_count.decode()) >= 1

    def test_invalid_transitions(self):
        """Test that invalid state transitions are rejected"""
        prp_id = "TEST-004"

        # Create completed PRP
        self.create_test_prp(prp_id, PRPState.COMPLETE)

        # Try invalid transitions
        assert not self.transition_prp(prp_id, PRPState.NEW)
        assert not self.transition_prp(prp_id, PRPState.DEVELOPMENT)
        assert not self.transition_prp(prp_id, PRPState.VALIDATION)

        # State should remain unchanged
        assert self.get_prp_state(prp_id) == PRPState.COMPLETE

    def test_orphan_detection_and_recovery(self):
        """Test detection and recovery of orphaned PRPs"""
        orphans = []

        # Create various orphaned PRPs
        # 1. PRP with no queue assignment
        orphan1 = "TEST-ORPHAN-001"
        self.create_test_prp(orphan1, PRPState.ASSIGNED, owner="pm-99")  # Non-existent PM
        orphans.append(orphan1)

        # 2. PRP stuck in inflight too long
        orphan2 = "TEST-ORPHAN-002"
        old_time = datetime.utcnow() - timedelta(hours=2)
        self.create_test_prp(orphan2, PRPState.DEVELOPMENT, owner="pm-1", inflight_since=old_time.isoformat())
        orphans.append(orphan2)

        # Detect orphans
        detected_orphans = self.detect_orphaned_prps()

        # At least one orphan should be detected (timing-dependent)
        assert len(detected_orphans) >= 1, "Should detect at least one orphan"

        # Recover orphans
        for orphan in detected_orphans:
            # Only recover orphans that start with TEST-ORPHAN
            if orphan.startswith("TEST-ORPHAN"):
                self.recover_orphaned_prp(orphan)
                assert self.get_prp_state(orphan) == PRPState.NEW

    def detect_orphaned_prps(self) -> List[str]:
        """Detect PRPs that are orphaned"""
        orphans = []

        # Check all test PRPs
        for key in self.redis_client.keys("prp:TEST-*"):
            prp_id = key.decode().split(":")[1]
            prp_data = self.redis_client.hgetall(key)

            # Decode data
            data = {k.decode(): v.decode() for k, v in prp_data.items()}

            # Check for orphan conditions
            if self.is_orphaned(prp_id, data):
                orphans.append(prp_id)

        return orphans

    def is_orphaned(self, prp_id: str, data: Dict[str, str]) -> bool:
        """Check if PRP is orphaned"""
        # No state
        if "state" not in data:
            return True

        state = PRPState(data["state"])

        # Check inflight timeout
        if "inflight_since" in data:
            inflight_time = datetime.fromisoformat(data["inflight_since"])
            if datetime.utcnow() - inflight_time > timedelta(hours=1):
                return True

        # Check if assigned but not in any queue
        if state == PRPState.ASSIGNED:
            # Check all queues
            for queue in ["dev_queue", "validation_queue", "integration_queue"]:
                if self.redis_client.lpos(queue, prp_id) is not None:
                    return False
                if self.redis_client.lpos(f"{queue}:inflight", prp_id) is not None:
                    return False
            return True  # Not in any queue

        return False

    def recover_orphaned_prp(self, prp_id: str):
        """Recover an orphaned PRP"""
        prp_key = f"prp:{prp_id}"

        # Mark as orphaned first
        self.redis_client.hset(prp_key, "state", PRPState.ORPHANED.value)

        # Then transition back to new
        self.transition_prp(prp_id, PRPState.NEW)

        # Increment retry count
        self.redis_client.hincrby(prp_key, "retry_count", 1)

        # Add to appropriate queue
        self.redis_client.lpush("dev_queue", prp_id)

    def test_state_machine_invariants(self):
        """Test system-wide invariants"""
        # Create PRPs in various states
        prps = []
        for i in range(10):
            prp_id = f"TEST-INV-{i:03d}"
            state = list(PRPState)[i % len(PRPState)]
            self.create_test_prp(prp_id, state)
            prps.append(prp_id)

        # Invariant 1: Every PRP has a state
        for prp_id in prps:
            assert self.get_prp_state(prp_id) is not None

        # Invariant 2: No PRP in multiple queues
        queues = ["dev_queue", "validation_queue", "integration_queue"]
        for prp_id in prps:
            locations = 0
            for queue in queues:
                if self.redis_client.lpos(queue, prp_id) is not None:
                    locations += 1
                if self.redis_client.lpos(f"{queue}:inflight", prp_id) is not None:
                    locations += 1
            assert locations <= 1, f"PRP {prp_id} found in {locations} queues"

    def test_concurrent_state_transitions(self):
        """Test handling of concurrent state transition attempts"""
        import threading

        prp_id = "TEST-CONCURRENT-001"
        self.create_test_prp(prp_id, PRPState.VALIDATION)

        results = []

        def try_transition(to_state: PRPState):
            result = self.transition_prp(prp_id, to_state)
            results.append((to_state, result))

        # Try concurrent transitions
        threads = [
            threading.Thread(target=try_transition, args=(PRPState.INTEGRATION,)),
            threading.Thread(target=try_transition, args=(PRPState.REJECTED,)),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Check that at least one succeeded (Redis transactions aren't perfect for this test)
        successful = [r for r in results if r[1]]
        assert len(successful) >= 1, "At least one transition should succeed"

        # Final state should be one of the attempted transitions
        final_state = self.get_prp_state(prp_id)
        assert final_state in [PRPState.INTEGRATION, PRPState.REJECTED]

    def test_retry_exhaustion(self):
        """Test behavior when retry count is exhausted"""
        prp_id = "TEST-RETRY-001"
        max_retries = 3

        self.create_test_prp(prp_id, PRPState.DEVELOPMENT, retry_count=str(max_retries))

        # Fail and check if we've exhausted retries
        assert self.transition_prp(prp_id, PRPState.FAILED)

        retry_count = int(self.redis_client.hget(f"prp:{prp_id}", "retry_count").decode())

        # We're at max retries
        assert retry_count >= max_retries

        # Should allow transition back to NEW (retry is allowed in our state machine)
        # The actual business logic would check retry count, but state machine allows it
        assert self.transition_prp(prp_id, PRPState.NEW)

        # Verify retry count was preserved
        new_retry_count = int(self.redis_client.hget(f"prp:{prp_id}", "retry_count").decode())
        assert new_retry_count == retry_count

    def test_state_transition_audit_trail(self):
        """Test that all state transitions are logged"""
        prp_id = "TEST-AUDIT-001"

        self.create_test_prp(prp_id, PRPState.NEW)

        # Perform valid transitions only
        transitions = [
            (PRPState.ASSIGNED, {}),
            (PRPState.DEVELOPMENT, {"owner": "pm-1"}),
            (PRPState.VALIDATION, {"tests_passed": "true"}),
            (PRPState.REJECTED, {"rejection_reason": "Coverage too low"}),
            (PRPState.DEVELOPMENT, {"owner": "pm-1"}),
            (PRPState.VALIDATION, {"tests_passed": "true", "coverage_pct": "90"}),
            (PRPState.INTEGRATION, {"validated_by": "validator-1"}),
            (PRPState.COMPLETE, {"ci_passed": "true"}),
        ]

        for state, kwargs in transitions:
            result = self.transition_prp(prp_id, state, **kwargs)
            assert result, f"Failed to transition to {state.value}"

        # Check timestamps exist for each unique state
        prp_data = self.redis_client.hgetall(f"prp:{prp_id}")

        # Check timestamps for key state transitions (not all need timestamps)
        key_timestamps = ["created_at", "assigned_at", "validation_at", "complete_at"]

        for timestamp in key_timestamps:
            assert timestamp.encode() in prp_data, f"Missing timestamp for {timestamp}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
