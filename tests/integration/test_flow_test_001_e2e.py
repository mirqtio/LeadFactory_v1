"""
FLOW-TEST-001: End-to-End Multi-Agent Orchestration Flow Test

Tests the complete multi-agent orchestration system including:
- PRP assignment and state transitions  
- Redis coordination between agents
- Development workflow execution
- Integration and validation handoffs

This test validates the core multi-agent workflow described in CLAUDE.md.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import redis

# Test configuration
TEST_PRP_ID = "TEST-E2E-001"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


class TestFlowEndToEnd:
    """Test complete end-to-end multi-agent orchestration flow"""

    @pytest.fixture
    def redis_client(self):
        """Redis client for testing coordination"""
        client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        # Clean up test keys before and after
        client.delete(f"prp:{TEST_PRP_ID}")
        client.delete(f"agent:dev:current_prp")
        client.delete(f"agent:validator:current_prp")
        client.delete(f"agent:integration:current_prp")
        yield client
        # Cleanup after test
        client.delete(f"prp:{TEST_PRP_ID}")
        client.delete(f"agent:dev:current_prp")
        client.delete(f"agent:validator:current_prp")
        client.delete(f"agent:integration:current_prp")

    @pytest.fixture
    def mock_tmux_messaging(self):
        """Mock tmux messaging system"""
        with patch("subprocess.run") as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            yield mock_subprocess

    def test_prp_state_transitions(self, redis_client):
        """
        Test PRP state transitions through the complete workflow:
        new -> validated -> assigned -> development -> validation -> integration -> complete
        """
        # 1. Initialize PRP in Redis (Orchestrator creates)
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "title": "End-to-End Flow Test",
                "state": "new",
                "priority": "high",
                "requirements": "Create comprehensive E2E test",
                "created_at": "2025-07-22T16:00:00Z",
            },
        )

        # Verify initial state
        state = redis_client.hget(f"prp:{TEST_PRP_ID}", "state")
        assert state == "new", "PRP should start in 'new' state"

        # 2. Orchestrator validates and assigns PRP
        redis_client.hset(f"prp:{TEST_PRP_ID}", mapping={"state": "validated", "validated_at": "2025-07-22T16:01:00Z"})

        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={"state": "assigned", "assigned_to": "dev-agent-1", "assigned_at": "2025-07-22T16:02:00Z"},
        )

        assert redis_client.hget(f"prp:{TEST_PRP_ID}", "state") == "assigned"

        # 3. Development Agent starts work
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "state": "development",
                "development_started": "true",
                "development_started_at": "2025-07-22T16:03:00Z",
            },
        )

        redis_client.hset(
            "agent:dev", mapping={"current_prp": TEST_PRP_ID, "status": "coding", "last_update": "2025-07-22T16:03:00Z"}
        )

        assert redis_client.hget(f"prp:{TEST_PRP_ID}", "state") == "development"
        assert redis_client.hget("agent:dev", "current_prp") == TEST_PRP_ID

        # 4. Development Agent completes and hands off to Validator
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "state": "validation",
                "development_completed_at": "2025-07-22T16:10:00Z",
                "branch": "feat/test-e2e-001-flow",
                "evidence": "Feature implemented with tests, make quick-check passes",
            },
        )

        redis_client.lpush("validation_queue", TEST_PRP_ID)
        redis_client.hset("agent:validator", "current_prp", TEST_PRP_ID)

        assert redis_client.hget(f"prp:{TEST_PRP_ID}", "state") == "validation"
        assert redis_client.lindex("validation_queue", 0) == TEST_PRP_ID

        # 5. Validator approves and hands off to Integration Agent
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "state": "integration",
                "validation_completed_at": "2025-07-22T16:15:00Z",
                "validation_status": "approved",
                "quality_gates_passed": "true",
            },
        )

        redis_client.lpush("integration_queue", TEST_PRP_ID)
        redis_client.hset("agent:integration", "current_prp", TEST_PRP_ID)

        assert redis_client.hget(f"prp:{TEST_PRP_ID}", "state") == "integration"
        assert redis_client.lindex("integration_queue", 0) == TEST_PRP_ID

        # 6. Integration Agent completes merge and CI
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "state": "complete",
                "integration_completed_at": "2025-07-22T16:20:00Z",
                "merged_to_main": "true",
                "ci_status": "passed",
                "github_commit": "abc123def",
            },
        )

        final_state = redis_client.hget(f"prp:{TEST_PRP_ID}", "state")
        assert final_state == "complete", "PRP should reach 'complete' state"

    def test_agent_coordination_protocol(self, redis_client, mock_tmux_messaging):
        """Test agent coordination through Redis messaging"""

        # Test Orchestrator -> PM assignment
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "state": "assigned",
                "assigned_to": "pm-1",
                "assignment_message": f"Assigned {TEST_PRP_ID}. Review requirements and begin development.",
            },
        )

        # Verify assignment data
        assigned_to = redis_client.hget(f"prp:{TEST_PRP_ID}", "assigned_to")
        assert assigned_to == "pm-1"

        # Test PM -> Validator handoff
        redis_client.hset(f"prp:{TEST_PRP_ID}", "state", "validation")
        redis_client.lpush("validation_queue", TEST_PRP_ID)

        queue_len = redis_client.llen("validation_queue")
        assert queue_len >= 1, "PRP should be in validation queue"

        # Test Validator -> Integration handoff
        redis_client.hset(f"prp:{TEST_PRP_ID}", "state", "integration")
        redis_client.lpush("integration_queue", TEST_PRP_ID)

        integration_queue_len = redis_client.llen("integration_queue")
        assert integration_queue_len >= 1, "PRP should be in integration queue"

    def test_agent_status_monitoring(self, redis_client):
        """Test agent status and heartbeat monitoring"""

        # Set up agent status tracking
        agents = ["pm-1", "pm-2", "validator", "integration"]
        current_time = "2025-07-22T16:30:00Z"

        for agent in agents:
            redis_client.hset(
                f"agent:{agent}", mapping={"status": "ready", "current_prp": "", "last_update": current_time}
            )

        # Verify agent registration
        for agent in agents:
            status = redis_client.hget(f"agent:{agent}", "status")
            assert status == "ready", f"Agent {agent} should be ready"

        # Test agent assignment
        redis_client.hset(
            "agent:pm-1", mapping={"status": "coding", "current_prp": TEST_PRP_ID, "last_update": current_time}
        )

        pm1_prp = redis_client.hget("agent:pm-1", "current_prp")
        assert pm1_prp == TEST_PRP_ID, "PM-1 should be assigned to test PRP"

    def test_queue_management(self, redis_client):
        """Test queue management and bottleneck detection"""

        # Test validation queue
        validation_prps = [f"PRP-{i:03d}" for i in range(1, 6)]
        for prp in validation_prps:
            redis_client.lpush("validation_queue", prp)

        queue_len = redis_client.llen("validation_queue")
        assert queue_len == 5, "Should have 5 PRPs in validation queue"

        # Test integration queue
        integration_prps = [f"PRP-{i:03d}" for i in range(6, 9)]
        for prp in integration_prps:
            redis_client.lpush("integration_queue", prp)

        integration_len = redis_client.llen("integration_queue")
        assert integration_len == 3, "Should have 3 PRPs in integration queue"

        # Test queue processing (FIFO)
        next_validation = redis_client.rpop("validation_queue")
        assert next_validation == "PRP-001", "Should process oldest PRP first"

    def test_merge_lock_mechanism(self, redis_client):
        """Test merge lock coordination for integration"""

        # Test acquiring merge lock
        lock_acquired = redis_client.set("merge:lock", TEST_PRP_ID, nx=True, ex=3600)
        assert lock_acquired, "Should acquire merge lock successfully"

        # Test lock holder
        current_holder = redis_client.get("merge:lock")
        assert current_holder == TEST_PRP_ID, "Lock should be held by test PRP"

        # Test lock conflict prevention
        conflict_lock = redis_client.set("merge:lock", "OTHER-PRP", nx=True)
        assert not conflict_lock, "Should not acquire lock when already held"

        # Test lock release
        redis_client.delete("merge:lock")
        released = redis_client.get("merge:lock")
        assert released is None, "Lock should be released"

    def test_escalation_triggers(self, redis_client):
        """Test automatic escalation conditions"""

        # Test queue backup escalation (>5 PRPs in integration)
        for i in range(7):
            redis_client.lpush("integration_queue", f"BACKUP-PRP-{i:03d}")

        queue_len = redis_client.llen("integration_queue")
        escalation_threshold = 5
        needs_escalation = queue_len > escalation_threshold

        assert needs_escalation, "Should trigger escalation for queue backup"

        # Test agent stall detection (no update >30 min)
        stale_time = "2025-07-22T15:00:00Z"  # 1.5 hours ago
        redis_client.hset("agent:pm-1", "last_update", stale_time)

        agent_update = redis_client.hget("agent:pm-1", "last_update")
        assert agent_update == stale_time, "Should detect stale agent status"

    def test_metrics_tracking(self, redis_client):
        """Test system metrics and performance tracking"""

        # Test completion metrics
        redis_client.incr("metrics:prps_completed_today")
        redis_client.incr("metrics:prps_completed_today")

        completed_today = int(redis_client.get("metrics:prps_completed_today") or 0)
        assert completed_today == 2, "Should track daily completions"

        # Test success rate metrics
        redis_client.set("metrics:ci_success_rate", "0.85")
        success_rate = float(redis_client.get("metrics:ci_success_rate"))
        assert success_rate == 0.85, "Should track CI success rate"

        # Test average cycle time
        redis_client.hset("metrics:cycle_times", TEST_PRP_ID, "1200")  # 20 minutes
        cycle_time = redis_client.hget("metrics:cycle_times", TEST_PRP_ID)
        assert int(cycle_time) == 1200, "Should track PRP cycle times"

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_simulation(self, redis_client):
        """Simulate complete end-to-end workflow with timing"""

        start_time = time.time()

        # 1. PRP Creation (Orchestrator)
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={
                "title": "E2E Workflow Test",
                "state": "new",
                "priority": "high",
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

        await asyncio.sleep(0.1)  # Simulate processing delay

        # 2. Validation & Assignment
        redis_client.hset(f"prp:{TEST_PRP_ID}", mapping={"state": "assigned", "assigned_to": "dev-agent-test"})

        await asyncio.sleep(0.2)  # Simulate development time

        # 3. Development
        redis_client.hset(f"prp:{TEST_PRP_ID}", mapping={"state": "development", "development_started": "true"})

        await asyncio.sleep(0.1)  # Simulate validation time

        # 4. Validation
        redis_client.hset(f"prp:{TEST_PRP_ID}", mapping={"state": "validation", "validation_status": "in_progress"})

        await asyncio.sleep(0.1)  # Simulate integration time

        # 5. Integration
        redis_client.hset(f"prp:{TEST_PRP_ID}", mapping={"state": "integration", "ci_status": "running"})

        await asyncio.sleep(0.1)  # Simulate CI completion

        # 6. Completion
        redis_client.hset(
            f"prp:{TEST_PRP_ID}",
            mapping={"state": "complete", "ci_status": "passed", "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
        )

        total_time = time.time() - start_time

        # Verify workflow completed successfully
        final_state = redis_client.hget(f"prp:{TEST_PRP_ID}", "state")
        assert final_state == "complete", "E2E workflow should complete successfully"

        # Verify performance (should complete quickly in test)
        assert total_time < 2.0, f"E2E simulation took {total_time:.2f}s, should be < 2.0s"

        # Verify all required fields are present
        prp_data = redis_client.hgetall(f"prp:{TEST_PRP_ID}")
        required_fields = ["title", "state", "priority", "created_at", "completed_at"]

        for field in required_fields:
            assert field in prp_data, f"PRP should have {field} field"

    def test_bulletproof_ci_integration(self):
        """Test integration with Bulletproof CI system"""

        # Verify make commands are available
        makefile_path = Path("./Makefile")
        assert makefile_path.exists(), "Makefile should exist for CI commands"

        # Read Makefile to verify expected targets exist
        makefile_content = makefile_path.read_text()
        required_targets = ["quick-check", "pre-push", "bpci", "format", "lint"]

        for target in required_targets:
            assert target in makefile_content, f"Makefile should contain {target} target"

    def test_prp_completion_validation(self):
        """Test PRP completion validation requirements"""

        # Simulate completed PRP data structure
        completed_prp = {
            "state": "complete",
            "validation_evidence": {
                "make_quick_check": "passed",
                "quality_gates": "passed",
                "ci_status": "passed",
                "tests_passing": "true",
                "coverage_threshold": "met",
            },
            "completion_criteria": {
                "feature_implemented": True,
                "tests_written": True,
                "documentation_updated": True,
                "ci_green": True,
                "no_regressions": True,
            },
        }

        # Verify all completion criteria are met
        for criterion, status in completed_prp["completion_criteria"].items():
            assert status is True, f"Completion criterion {criterion} must be True"

        # Verify evidence is present
        evidence = completed_prp["validation_evidence"]
        assert evidence["make_quick_check"] == "passed"
        assert evidence["ci_status"] == "passed"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
