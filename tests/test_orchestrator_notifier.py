#!/usr/bin/env python3
"""
Tests for orchestrator notifier functionality
"""
import json
import os

# Import the notifier class directly
import sys
import time
from datetime import datetime
from unittest.mock import Mock, call, patch

import pytest
import redis

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "bin"))
from orchestrator_notifier import OrchestratorNotifier


class TestOrchestratorNotifier:
    """Test orchestrator notifier message delivery"""

    def setup_method(self):
        """Set up test environment"""
        self.redis_client = redis.from_url("redis://localhost:6379/0")
        self.cleanup_test_data()

    def teardown_method(self):
        """Clean up after tests"""
        self.cleanup_test_data()

    def cleanup_test_data(self):
        """Remove all test data"""
        self.redis_client.delete("orchestrator:pending_notifications")

    @patch("subprocess.run")
    def test_notifier_delivers_system_notifications(self, mock_subprocess):
        """Test that notifier delivers system notifications to tmux"""
        # Create notifier instance
        notifier = OrchestratorNotifier(session="test-session", redis_url="redis://localhost:6379/0")

        # Add a notification to pending queue
        notification = {
            "id": "test-001",
            "type": "system_notification",
            "message": "Test system notification",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

        # Process notifications
        notifier.check_for_notifications()

        # Verify tmux command was called
        assert mock_subprocess.called
        # Check that the message was sent
        calls = mock_subprocess.call_args_list
        sent_messages = []
        for call_args in calls:
            if len(call_args[0]) > 0 and len(call_args[0][0]) > 4:
                sent_messages.append(call_args[0][0][4])  # Get the message content

        # Should contain the formatted notification
        assert any("SYSTEM: Test system notification" in msg for msg in sent_messages)

        # Notification should be marked as delivered
        assert "test-001" in notifier.delivered_notifications

    @patch("subprocess.run")
    def test_notifier_formats_different_notification_types(self, mock_subprocess):
        """Test that notifier correctly formats different notification types"""
        notifier = OrchestratorNotifier(session="test-session", redis_url="redis://localhost:6379/0")

        # Test different notification types
        notifications = [
            {
                "id": "new-prp-001",
                "type": "new_prp",
                "prp_id": "TEST-PRP-001",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "id": "agent-down-001",
                "type": "agent_down",
                "agent": "test-dev-1",
                "last_activity": datetime.utcnow().isoformat(),
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "id": "bulk-001",
                "type": "bulk_prps_queued",
                "prp_ids": ["PRP-1", "PRP-2", "PRP-3"],
                "queue": "dev_queue",
                "timestamp": datetime.utcnow().isoformat(),
            },
        ]

        # Add all notifications
        for notif in notifications:
            self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notif))

        # Process notifications
        notifier.check_for_notifications()

        # Verify all were processed
        assert len(notifier.delivered_notifications) == 3
        assert "new-prp-001" in notifier.delivered_notifications
        assert "agent-down-001" in notifier.delivered_notifications
        assert "bulk-001" in notifier.delivered_notifications

    def test_notifier_clears_processed_notifications(self):
        """Test that notifier clears notifications after processing"""
        # Ensure queue is empty before test
        self.redis_client.delete("orchestrator:pending_notifications")

        notifier = OrchestratorNotifier(session="test-session", redis_url="redis://localhost:6379/0")

        # Add notifications
        for i in range(5):
            notification = {
                "id": f"test-clear-{i}",
                "type": "system_notification",
                "message": f"Test message {i}",
                "timestamp": datetime.utcnow().isoformat(),
            }
            self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

        # Verify they're queued
        assert self.redis_client.llen("orchestrator:pending_notifications") == 5

        # Process notifications
        with patch("subprocess.run"):
            notifier.check_for_notifications()

        # Queue should be cleared
        assert self.redis_client.llen("orchestrator:pending_notifications") == 0

    @patch("subprocess.run")
    def test_notifier_formats_progress_report(self, mock_subprocess):
        """Test progress report formatting"""
        notifier = OrchestratorNotifier(session="test-session", redis_url="redis://localhost:6379/0")

        # Create a progress report notification
        notification = {
            "id": "progress-001",
            "type": "progress_report",
            "report": {
                "queues": {
                    "dev_queue": {"depth": 5, "inflight": 2},
                    "validation_queue": {"depth": 3, "inflight": 1},
                    "integration_queue": {"depth": 0, "inflight": 0},
                },
                "active_prps": [
                    {"id": "PRP-001", "status": "development", "title": "Test PRP 1"},
                    {"id": "PRP-002", "status": "validation", "title": "Test PRP 2"},
                ],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

        # Process notification
        notifier.check_for_notifications()

        # Verify tmux was called
        assert mock_subprocess.called

        # Check that progress report format was sent
        calls = mock_subprocess.call_args_list
        sent_messages = []
        for call_args in calls:
            if len(call_args[0]) > 0 and len(call_args[0][0]) > 4:
                sent_messages.append(call_args[0][0][4])

        # Should contain progress report elements
        assert any("PROGRESS REPORT" in msg for msg in sent_messages)
        assert any("Queue Status:" in msg for msg in sent_messages)
        assert any("Active PRPs: 2" in msg for msg in sent_messages)

    def test_notifier_avoids_duplicate_delivery(self):
        """Test that notifier doesn't deliver the same notification twice"""
        notifier = OrchestratorNotifier(session="test-session", redis_url="redis://localhost:6379/0")

        # Add same notification multiple times
        notification = {
            "id": "duplicate-001",
            "type": "system_notification",
            "message": "Duplicate test",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Process first time
        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))
        with patch("subprocess.run") as mock_subprocess:
            notifier.check_for_notifications()
            first_call_count = mock_subprocess.call_count

        # Add same notification again
        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))
        with patch("subprocess.run") as mock_subprocess:
            notifier.check_for_notifications()
            # Should not send again
            assert mock_subprocess.call_count == 0

    def test_notifier_handles_malformed_notifications(self):
        """Test that notifier handles malformed notifications gracefully"""
        notifier = OrchestratorNotifier(session="test-session", redis_url="redis://localhost:6379/0")

        # Add malformed notification
        self.redis_client.lpush("orchestrator:pending_notifications", "not valid json")

        # Should not crash
        with patch("subprocess.run"):
            notifier.check_for_notifications()

        # Queue should be cleared even if notification was invalid
        assert self.redis_client.llen("orchestrator:pending_notifications") == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
