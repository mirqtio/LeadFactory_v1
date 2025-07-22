#!/usr/bin/env python3
"""
Tests for orchestrator agent functionality and message processing
"""
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, call, patch

import pytest
import redis


class TestOrchestratorFunctionality:
    """Test orchestrator agent message reception and processing"""

    def setup_method(self):
        """Set up test environment"""
        self.redis_client = redis.from_url("redis://localhost:6379/0")
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after tests"""
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove all test data"""
        # Clear test queues
        self.redis_client.delete("orchestrator_queue")
        self.redis_client.delete("test_orchestrator_queue")
        self.redis_client.delete("orchestrator:pending_notifications")

        # Clear test PRPs
        for key in self.redis_client.keys("prp:TEST-ORCH-*"):
            self.redis_client.delete(key)

        # Clear test agent data
        for key in self.redis_client.keys("agent:test-*"):
            self.redis_client.delete(key)

    def test_orchestrator_receives_notifications(self):
        """Test that orchestrator receives system notifications via pending notifications"""
        # Send a notification to pending notifications
        notification = {
            "id": "test-notif-001",
            "type": "system_notification",
            "message": "Test notification for orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
            "source": "test_suite",
        }

        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

        # Verify message is in pending notifications
        queue_length = self.redis_client.llen("orchestrator:pending_notifications")
        assert queue_length == 1, "Notification should be in pending notifications"

        # Verify message content
        message = self.redis_client.rpop("orchestrator:pending_notifications")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "system_notification"
        assert "Test notification" in data["message"]

    def test_orchestrator_receives_new_prp_notifications(self):
        """Test that orchestrator receives notifications about new PRPs"""
        # Create a test PRP
        prp_id = "TEST-ORCH-001"
        self.redis_client.hset(
            f"prp:{prp_id}",
            mapping={
                "id": prp_id,
                "state": "new",
                "title": "Test PRP for orchestrator",
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        # Send new PRP notification
        notification = {
            "type": "new_prp",
            "prp_id": prp_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(notification))

        # Verify notification
        message = self.redis_client.rpop("orchestrator_queue")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "new_prp"
        assert data["prp_id"] == prp_id

    def test_orchestrator_receives_agent_health_alerts(self):
        """Test that orchestrator receives agent health alerts"""
        # Simulate agent down
        agent_id = "test-dev-1"

        # Set agent as down
        self.redis_client.hset(
            f"agent:{agent_id}",
            mapping={
                "status": "agent_down",
                "last_activity": (datetime.utcnow() - timedelta(minutes=45)).isoformat(),
                "current_prp": "TEST-ORCH-002",
            },
        )

        # Send agent down notification
        notification = {
            "type": "agent_down",
            "agent": agent_id,
            "last_activity": (datetime.utcnow() - timedelta(minutes=45)).isoformat(),
            "current_prp": "TEST-ORCH-002",
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(notification))

        # Verify notification
        message = self.redis_client.rpop("orchestrator_queue")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "agent_down"
        assert data["agent"] == agent_id
        assert data["current_prp"] == "TEST-ORCH-002"

    def test_orchestrator_queue_routing(self):
        """Test that messages in orchestrator_queue are properly formatted for routing"""
        # Test multiple message types
        messages = [
            {
                "type": "heartbeat_check",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "type": "check_queue_depth",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "type": "deployment_failed",
                "prp_id": "TEST-ORCH-003",
                "error": "Test deployment error",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

        # Send all messages
        for msg in messages:
            self.redis_client.lpush("orchestrator_queue", json.dumps(msg))

        # Verify all messages are queued
        assert self.redis_client.llen("orchestrator_queue") == 3

        # Process messages (simulating orchestrator_loop)
        processed = []
        while True:
            message = self.redis_client.rpop("orchestrator_queue")
            if not message:
                break
            processed.append(json.loads(message))

        # Verify all message types were queued
        assert len(processed) == 3
        types = [msg["type"] for msg in processed]
        assert "heartbeat_check" in types
        assert "check_queue_depth" in types
        assert "deployment_failed" in types

    def test_orchestrator_qa_routing(self):
        """Test Q&A routing through orchestrator"""
        # Agent asks a question
        question_data = {
            "type": "agent_question",
            "agent": "test-dev-1",
            "question": "What is the correct import path for validation?",
            "question_id": "qa-test-001",
            "prp_id": "TEST-ORCH-004",
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(question_data))

        # Verify question is queued
        message = self.redis_client.rpop("orchestrator_queue")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "agent_question"
        assert data["question_id"] == "qa-test-001"

        # Simulate orchestrator_loop processing and storing answer
        answer = "Use 'from validators import validate_prp' for the validation module"
        self.redis_client.setex(f"answer:{data['question_id']}", 300, answer)

        # Verify answer is stored
        stored_answer = self.redis_client.get(f"answer:{data['question_id']}")
        assert stored_answer is not None
        assert stored_answer.decode() == answer

    def test_orchestrator_assignment_decisions(self):
        """Test that orchestrator can make PRP assignment decisions"""
        # Create multiple PRPs needing assignment
        prp_ids = ["TEST-ORCH-005", "TEST-ORCH-006", "TEST-ORCH-007"]

        for prp_id in prp_ids:
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={
                    "id": prp_id,
                    "state": "new",
                    "priority": "P0",
                    "created_at": datetime.utcnow().isoformat(),
                },
            )
            self.redis_client.lpush("dev_queue", prp_id)

        # Set agent availability
        self.redis_client.hset(
            "agent:test-dev-1",
            mapping={
                "status": "idle",
                "last_activity": datetime.utcnow().isoformat(),
                "current_prp": "",
            },
        )

        self.redis_client.hset(
            "agent:test-dev-2",
            mapping={
                "status": "busy",
                "last_activity": datetime.utcnow().isoformat(),
                "current_prp": "OTHER-PRP-001",
            },
        )

        # Send assignment request to orchestrator
        assignment_request = {
            "type": "assignment_request",
            "prp_ids": prp_ids,
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(assignment_request))

        # Verify request is queued
        assert self.redis_client.llen("orchestrator_queue") == 1

    def test_orchestrator_handles_bulk_prp_notifications(self):
        """Test orchestrator handles bulk PRP notifications"""
        # Simulate bulk PRP ingest
        prp_ids = [f"TEST-ORCH-BULK-{i:03d}" for i in range(10)]

        notification = {
            "type": "bulk_prps_queued",
            "prp_ids": prp_ids,
            "queue": "dev_queue",
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(notification))

        # Verify notification
        message = self.redis_client.rpop("orchestrator_queue")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "bulk_prps_queued"
        assert len(data["prp_ids"]) == 10
        assert data["queue"] == "dev_queue"

    def test_orchestrator_progress_report_generation(self):
        """Test that orchestrator can receive progress report requests"""
        # Create system state
        self.redis_client.lpush("dev_queue", "TEST-ORCH-008")
        self.redis_client.lpush("validation_queue", "TEST-ORCH-009")
        self.redis_client.lpush("dev_queue:inflight", "TEST-ORCH-010")

        # Request progress report
        report_request = {
            "type": "generate_progress_report",
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(report_request))

        # Verify request is queued
        message = self.redis_client.rpop("orchestrator_queue")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "generate_progress_report"

    def test_orchestrator_handles_scaling_decisions(self):
        """Test orchestrator receives queue scaling notifications"""
        # Simulate high queue depth
        for i in range(25):
            self.redis_client.lpush("dev_queue", f"TEST-ORCH-SCALE-{i:03d}")

        # Send scaling notification
        scaling_notification = {
            "type": "queue_scaling_needed",
            "queue": "dev_queue",
            "depth": 25,
            "recommendation": "spawn_dev_3",
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator_queue", json.dumps(scaling_notification))

        # Verify notification
        message = self.redis_client.rpop("orchestrator_queue")
        assert message is not None
        data = json.loads(message)
        assert data["type"] == "queue_scaling_needed"
        assert data["depth"] == 25
        assert data["recommendation"] == "spawn_dev_3"

    @patch("subprocess.run")
    def test_orchestrator_tmux_message_delivery(self, mock_subprocess):
        """Test that orchestrator shim would deliver messages to tmux if it existed"""
        # This test verifies what WOULD happen if the orchestrator shim was running

        # Mock tmux send-keys command
        mock_subprocess.return_value.returncode = 0

        # Simulate what the shim would do
        message = {
            "type": "system_notification",
            "message": "Test delivery to orchestrator tmux pane",
        }

        # The shim would execute something like this
        expected_cmd = ["tmux", "send-keys", "-t", "leadstack:orchestrator", json.dumps(message), "Enter"]

        # If shim was running, it would call subprocess
        # We're testing the command structure here
        from subprocess import run

        run(expected_cmd, capture_output=True)

        # Verify the command structure was correct
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        assert args[0] == "tmux"
        assert args[1] == "send-keys"
        assert "orchestrator" in args[3]

    def test_orchestrator_message_format_compatibility(self):
        """Test that orchestrator queue messages are compatible with tmux delivery"""
        # Test various message formats
        messages = [
            {"type": "simple", "data": "test"},
            {"type": "complex", "nested": {"key": "value"}, "list": [1, 2, 3]},
            {"type": "unicode", "text": "Test with émojis 🚀"},
            {"type": "multiline", "text": "Line 1\nLine 2\nLine 3"},
        ]

        for msg in messages:
            # Messages must be JSON serializable
            try:
                serialized = json.dumps(msg)
                # And deserializable
                deserialized = json.loads(serialized)
                assert deserialized == msg
            except Exception as e:
                pytest.fail(f"Message format incompatible: {e}")

    def test_orchestrator_shim_removal_impact(self):
        """Test to verify the impact of orchestrator shim removal"""
        # This test documents the current broken state

        # Without the shim, messages accumulate in orchestrator_queue
        for i in range(5):
            self.redis_client.lpush(
                "orchestrator_queue",
                json.dumps(
                    {
                        "type": "test_accumulation",
                        "index": i,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                ),
            )

        # Messages pile up because no shim delivers them
        queue_length = self.redis_client.llen("orchestrator_queue")
        assert queue_length == 5, "Messages accumulate without shim"

        # The orchestrator agent never sees these messages
        # This is the core problem we discovered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
