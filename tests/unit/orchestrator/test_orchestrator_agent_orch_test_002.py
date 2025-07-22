"""
ORCH-TEST-002: Orchestrator Agent Core Functions Test

Tests the OrchestratorAgent class core functionality including:
- Agent status monitoring and health checks
- PRP assignment to PM agents
- Timeout detection and handling
- Queue management and processing

This test validates the orchestrator agent's core operational functions.
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import redis

# Import the orchestrator agent
from bin.orchestrator_agent import OrchestratorAgent


class TestOrchestratorAgentCore:
    """Test core orchestrator agent functionality"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client for testing"""
        mock_client = Mock()
        mock_client.from_url = Mock(return_value=mock_client)
        mock_client.hgetall = Mock(return_value={})
        mock_client.hset = Mock(return_value=1)
        mock_client.llen = Mock(return_value=0)
        mock_client.lpop = Mock(return_value=None)
        mock_client.lpush = Mock(return_value=1)
        return mock_client

    @pytest.fixture
    def mock_messaging(self):
        """Mock orchestrator messaging"""
        with patch("bin.orchestrator_agent.OrchestratorMessaging") as mock_msg:
            mock_instance = Mock()
            mock_msg.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def orchestrator(self, mock_redis, mock_messaging):
        """Create orchestrator instance with mocked dependencies"""
        with patch("bin.orchestrator_agent.redis.from_url", return_value=mock_redis):
            with patch.dict(os.environ, {"REDIS_URL": "redis://localhost:6379/0", "TMUX_SESSION": "test-session"}):
                orchestrator = OrchestratorAgent()
                orchestrator.redis_client = mock_redis
                return orchestrator

    def test_orchestrator_initialization(self, orchestrator):
        """Test orchestrator agent initialization"""
        assert orchestrator.session == "test-session"
        assert orchestrator.pm_agents == ["pm-1", "pm-2", "pm-3"]
        assert orchestrator.validator_agent == "validator"
        assert orchestrator.integration_agent == "integrator"
        assert orchestrator.running is True

        # Verify thresholds are set correctly
        assert orchestrator.idle_threshold == timedelta(minutes=10)
        assert orchestrator.timeout_threshold == timedelta(minutes=30)

    def test_get_agent_status_existing_agent(self, orchestrator):
        """Test getting status of existing agent"""
        # Mock Redis data for active agent
        mock_data = {b"status": b"coding", b"current_prp": b"P0-001", b"last_update": b"2025-07-22T16:00:00"}
        orchestrator.redis_client.hgetall.return_value = mock_data

        status = orchestrator.get_agent_status("pm-1")

        assert status["status"] == "coding"
        assert status["current_prp"] == "P0-001"
        assert status["last_update"] == "2025-07-22T16:00:00"
        orchestrator.redis_client.hgetall.assert_called_with("agent:pm-1")

    def test_get_agent_status_unknown_agent(self, orchestrator):
        """Test getting status of unknown agent"""
        orchestrator.redis_client.hgetall.return_value = {}

        status = orchestrator.get_agent_status("unknown-agent")

        assert status["status"] == "unknown"
        assert status["current_prp"] is None
        assert status["last_update"] is None

    def test_find_available_pm_with_available_agent(self, orchestrator):
        """Test finding available PM when one is available"""

        # Mock status for multiple agents
        def mock_get_agent_status(agent):
            if agent == "pm-1":
                return {"status": "coding", "current_prp": "P0-001"}
            elif agent == "pm-2":
                return {"status": "idle", "current_prp": None}
            elif agent == "pm-3":
                return {"status": "coding", "current_prp": "P0-002"}

        orchestrator.get_agent_status = mock_get_agent_status

        available_pm = orchestrator.find_available_pm()

        assert available_pm == "pm-2"

    def test_find_available_pm_none_available(self, orchestrator):
        """Test finding available PM when none are available"""

        # Mock all agents as busy
        def mock_get_agent_status(agent):
            return {"status": "coding", "current_prp": f"P0-{agent[-1]}"}

        orchestrator.get_agent_status = mock_get_agent_status

        available_pm = orchestrator.find_available_pm()

        assert available_pm is None

    def test_get_next_prp_for_assignment_with_queue_item(self, orchestrator):
        """Test getting next PRP when dev queue has items"""
        orchestrator.redis_client.lpop.return_value = b"P0-005"

        prp_id = orchestrator.get_next_prp_for_assignment()

        assert prp_id == "P0-005"
        orchestrator.redis_client.lpop.assert_called_with("dev_queue")

    def test_get_next_prp_for_assignment_empty_queue(self, orchestrator):
        """Test getting next PRP when dev queue is empty"""
        orchestrator.redis_client.lpop.return_value = None

        prp_id = orchestrator.get_next_prp_for_assignment()

        assert prp_id is None

    def test_assign_prp_to_pm_success(self, orchestrator):
        """Test successful PRP assignment to PM"""
        test_prp = "P0-010"
        test_pm = "pm-2"

        # Mock current time
        with patch("bin.orchestrator_agent.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2025-07-22T16:30:00"

            success = orchestrator.assign_prp_to_pm(test_prp, test_pm)

            assert success is True

            # Verify agent status was updated
            expected_agent_mapping = {
                "current_prp": test_prp,
                "status": "assigned",
                "last_update": "2025-07-22T16:30:00",
            }
            orchestrator.redis_client.hset.assert_any_call(f"agent:{test_pm}", mapping=expected_agent_mapping)

            # Verify PRP status was updated
            expected_prp_mapping = {"state": "assigned", "owner": test_pm, "assigned_at": "2025-07-22T16:30:00"}
            orchestrator.redis_client.hset.assert_any_call(f"prp:{test_prp}", mapping=expected_prp_mapping)

            # Verify message was queued
            orchestrator.redis_client.lpush.assert_called()

    def test_assign_prp_to_pm_redis_error(self, orchestrator):
        """Test PRP assignment when Redis fails"""
        orchestrator.redis_client.hset.side_effect = Exception("Redis connection error")

        success = orchestrator.assign_prp_to_pm("P0-010", "pm-2")

        assert success is False

    def test_check_agent_health_healthy_agents(self, orchestrator):
        """Test agent health check with healthy agents"""
        current_time = datetime.utcnow()
        recent_time = (current_time - timedelta(minutes=5)).isoformat()

        def mock_get_agent_status(agent):
            return {"status": "coding", "current_prp": "P0-001", "last_update": recent_time}

        orchestrator.get_agent_status = mock_get_agent_status

        health_status = orchestrator.check_agent_health()

        # All agents should be healthy (updated within 10 minutes)
        for agent in orchestrator.pm_agents + [orchestrator.validator_agent, orchestrator.integration_agent]:
            assert health_status[agent] is True

    def test_check_agent_health_unhealthy_agents(self, orchestrator):
        """Test agent health check with unhealthy agents"""
        current_time = datetime.utcnow()
        stale_time = (current_time - timedelta(minutes=15)).isoformat()

        def mock_get_agent_status(agent):
            return {"status": "coding", "current_prp": "P0-001", "last_update": stale_time}

        orchestrator.get_agent_status = mock_get_agent_status

        health_status = orchestrator.check_agent_health()

        # All agents should be unhealthy (not updated within 10 minutes)
        for agent in orchestrator.pm_agents + [orchestrator.validator_agent, orchestrator.integration_agent]:
            assert health_status[agent] is False

    def test_handle_timeouts_with_timed_out_prp(self, orchestrator):
        """Test timeout handling when PRP has timed out"""
        current_time = datetime.utcnow()
        timeout_time = (current_time - timedelta(minutes=45)).isoformat()

        def mock_get_agent_status(agent):
            if agent == "pm-1":
                return {"status": "coding", "current_prp": "P0-TIMEOUT", "last_update": timeout_time}
            return {"status": "idle", "current_prp": None, "last_update": None}

        orchestrator.get_agent_status = mock_get_agent_status

        # Mock find_available_pm to return pm-2
        orchestrator.find_available_pm = Mock(return_value="pm-2")
        orchestrator.assign_prp_to_pm = Mock(return_value=True)

        with patch("bin.orchestrator_agent.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value.isoformat.return_value = "2025-07-22T16:45:00"
            mock_datetime.fromisoformat.return_value = current_time - timedelta(minutes=45)
            mock_datetime.utcnow.return_value = current_time

            orchestrator.handle_timeouts()

            # Verify agent was reset
            expected_reset_mapping = {"current_prp": "", "status": "idle", "last_update": "2025-07-22T16:45:00"}
            orchestrator.redis_client.hset.assert_any_call("agent:pm-1", mapping=expected_reset_mapping)

            # Verify PRP was reassigned
            orchestrator.assign_prp_to_pm.assert_called_with("P0-TIMEOUT", "pm-2")

    def test_process_orchestrator_messages_new_prp(self, orchestrator):
        """Test processing new PRP message"""
        message = {"type": "new_prp", "prp_id": "P0-NEW", "timestamp": "2025-07-22T16:00:00"}
        orchestrator.redis_client.lpop.return_value = json.dumps(message).encode()

        with patch("builtins.print") as mock_print:
            orchestrator.process_orchestrator_messages()

            mock_print.assert_called_with("📋 New PRP notification: P0-NEW")

    def test_process_orchestrator_messages_empty_queue(self, orchestrator):
        """Test processing messages when queue is empty"""
        orchestrator.redis_client.lpop.return_value = None

        # Should not raise any exceptions
        orchestrator.process_orchestrator_messages()

        # Verify only one lpop call was made (queue was empty)
        assert orchestrator.redis_client.lpop.call_count == 1

    def test_assignment_cycle_with_available_pm_and_prp(self, orchestrator):
        """Test assignment cycle with available PM and PRP"""

        # Mock available PM
        def mock_get_agent_status(agent):
            if agent == "pm-1":
                return {"status": "idle", "current_prp": None}
            return {"status": "coding", "current_prp": "P0-BUSY"}

        orchestrator.get_agent_status = mock_get_agent_status
        orchestrator.get_next_prp_for_assignment = Mock(return_value="P0-AVAILABLE")
        orchestrator.assign_prp_to_pm = Mock(return_value=True)

        orchestrator.assignment_cycle()

        orchestrator.assign_prp_to_pm.assert_called_with("P0-AVAILABLE", "pm-1")

    def test_assignment_cycle_no_available_pms(self, orchestrator):
        """Test assignment cycle when no PMs are available"""

        # Mock all PMs as busy
        def mock_get_agent_status(agent):
            return {"status": "coding", "current_prp": "P0-BUSY"}

        orchestrator.get_agent_status = mock_get_agent_status

        # Should not call assignment methods
        orchestrator.get_next_prp_for_assignment = Mock()
        orchestrator.assign_prp_to_pm = Mock()

        orchestrator.assignment_cycle()

        orchestrator.get_next_prp_for_assignment.assert_not_called()
        orchestrator.assign_prp_to_pm.assert_not_called()

    def test_generate_status_report(self, orchestrator):
        """Test status report generation"""
        # Mock queue lengths
        orchestrator.redis_client.llen.side_effect = [2, 1, 3]  # dev, validation, integration

        # Mock agent status and health
        def mock_get_agent_status(agent):
            return {"status": "coding" if "pm" in agent else "validating", "current_prp": f"P0-{agent.upper()}"}

        def mock_check_agent_health():
            return {
                agent: True
                for agent in orchestrator.pm_agents + [orchestrator.validator_agent, orchestrator.integration_agent]
            }

        orchestrator.get_agent_status = mock_get_agent_status
        orchestrator.check_agent_health = mock_check_agent_health

        report = orchestrator.generate_status_report()

        assert "📊 ORCHESTRATOR STATUS REPORT" in report
        assert "Dev Queue: 2" in report
        assert "Validation Queue: 1" in report
        assert "Integration Queue: 3" in report
        assert "pm-1: ✅ coding (P0-PM-1)" in report
        assert "validator: ✅ validating (P0-VALIDATOR)" in report

    def test_run_cycle_integration(self, orchestrator):
        """Test complete run cycle integration"""
        orchestrator.process_orchestrator_messages = Mock()
        orchestrator.handle_timeouts = Mock()
        orchestrator.assignment_cycle = Mock()
        orchestrator.generate_status_report = Mock(return_value="Test report")

        # Mock time to trigger status report
        with patch("bin.orchestrator_agent.time.time", return_value=300):
            with patch("builtins.print") as mock_print:
                orchestrator.run_cycle()

                orchestrator.process_orchestrator_messages.assert_called_once()
                orchestrator.handle_timeouts.assert_called_once()
                orchestrator.assignment_cycle.assert_called_once()
                mock_print.assert_called_with("Test report")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
