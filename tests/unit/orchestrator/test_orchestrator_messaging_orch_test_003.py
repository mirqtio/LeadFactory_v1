"""
ORCH-TEST-003: Orchestrator Messaging System Test

Tests the OrchestratorMessaging class functionality including:
- Tmux-based messaging between orchestrator and agents
- PRP assignment notifications
- Agent handoff coordination
- Status requests and escalations

This test validates the orchestrator messaging system integration.
"""

import json
import subprocess
from unittest.mock import Mock, call, patch

import pytest

# Import the orchestrator messaging
from bin.orchestrator_messaging import OrchestratorMessaging


class TestOrchestratorMessaging:
    """Test orchestrator messaging system"""

    @pytest.fixture
    def messaging(self):
        """Create messaging instance with test session"""
        return OrchestratorMessaging(session="test-session")

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess for tmux commands"""
        with patch("bin.orchestrator_messaging.subprocess") as mock_sub:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stderr = ""
            mock_sub.run.return_value = mock_result
            yield mock_sub

    def test_messaging_initialization(self, messaging):
        """Test messaging system initialization"""
        assert messaging.session == "test-session"
        assert messaging.send_script == "/Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh"

    def test_send_to_agent_success(self, messaging, mock_subprocess):
        """Test successful message sending to agent"""
        test_message = "Test message for agent"

        success = messaging.send_to_agent("dev-1", "0", test_message)

        assert success is True

        # Verify send script was called
        expected_cmd = [messaging.send_script, "dev-1:0", test_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

        # Verify Enter key was sent
        expected_enter_cmd = ["tmux", "send-keys", "-t", "test-session:dev-1.0", "Enter"]
        mock_subprocess.run.assert_any_call(expected_enter_cmd)

        assert mock_subprocess.run.call_count == 2

    def test_send_to_agent_script_failure(self, messaging, mock_subprocess):
        """Test message sending when script fails"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Script execution failed"
        mock_subprocess.run.return_value = mock_result

        success = messaging.send_to_agent("dev-1", "0", "Test message")

        assert success is False
        # Enter key should not be sent if script fails
        assert mock_subprocess.run.call_count == 1

    def test_send_to_agent_exception(self, messaging):
        """Test message sending when exception occurs"""
        with patch("bin.orchestrator_messaging.subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Subprocess error")

            success = messaging.send_to_agent("dev-1", "0", "Test message")

            assert success is False

    def test_notify_pm_assignment(self, messaging, mock_subprocess):
        """Test PM assignment notification"""
        success = messaging.notify_pm_assignment("dev-2", "P0-123")

        assert success is True

        expected_message = (
            "📋 ASSIGNMENT: You have been assigned PRP P0-123. Check Redis for details and begin development."
        )
        expected_cmd = [messaging.send_script, "dev-2:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_notify_validator_handoff(self, messaging, mock_subprocess):
        """Test validator handoff notification"""
        success = messaging.notify_validator_handoff("P0-456", "pm-1")

        assert success is True

        expected_message = "✅ HANDOFF: PRP P0-456 from pm-1 is ready for validation. Please review."
        expected_cmd = [messaging.send_script, "validator:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_notify_integrator_handoff(self, messaging, mock_subprocess):
        """Test integrator handoff notification"""
        success = messaging.notify_integrator_handoff("P0-789")

        assert success is True

        expected_message = "🔄 INTEGRATION: PRP P0-789 passed validation and is ready for integration to main."
        expected_cmd = [messaging.send_script, "integrator:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_request_agent_status(self, messaging, mock_subprocess):
        """Test agent status request"""
        success = messaging.request_agent_status("dev-3")

        assert success is True

        expected_message = "📊 STATUS REQUEST: Please provide your current status and PRP progress."
        expected_cmd = [messaging.send_script, "dev-3:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_notify_timeout_warning(self, messaging, mock_subprocess):
        """Test timeout warning notification"""
        success = messaging.notify_timeout_warning("dev-1", "P0-TIMEOUT", 5)

        assert success is True

        expected_message = "⏰ TIMEOUT WARNING: PRP P0-TIMEOUT has 5 minutes before timeout. Please update status."
        expected_cmd = [messaging.send_script, "dev-1:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_escalate_to_orchestrator(self, messaging, mock_subprocess):
        """Test escalation to orchestrator"""
        test_issue = "Agent not responding"
        test_context = {"agent": "pm-1", "prp": "P0-STUCK", "last_update": "30 minutes ago"}

        success = messaging.escalate_to_orchestrator(test_issue, test_context)

        assert success is True

        expected_message = f"🚨 ESCALATION: {test_issue}\nContext: {json.dumps(test_context, indent=2)}"
        expected_cmd = [messaging.send_script, "orchestrator:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_broadcast_system_status(self, messaging, mock_subprocess):
        """Test broadcasting system status to all agents"""
        test_status = "System running normally. All queues healthy."

        success = messaging.broadcast_system_status(test_status)

        assert success is True

        # Should send to all agents
        expected_agents = ["dev-1", "dev-2", "dev-3", "validator", "integrator"]
        expected_message = f"📊 SYSTEM STATUS:\n{test_status}"

        for agent in expected_agents:
            expected_cmd = [messaging.send_script, f"{agent}:0", expected_message]
            mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

        # 5 agents × 2 calls each (send + enter) = 10 total calls
        assert mock_subprocess.run.call_count == 10

    def test_broadcast_system_status_partial_failure(self, messaging, mock_subprocess):
        """Test broadcast with partial failures"""

        # Mock to fail for dev-2 but succeed for others
        def side_effect(*args, **kwargs):
            if "dev-2:0" in args[0]:
                result = Mock()
                result.returncode = 1
                result.stderr = "Failed to send"
                return result
            else:
                result = Mock()
                result.returncode = 0
                result.stderr = ""
                return result

        mock_subprocess.run.side_effect = side_effect

        success = messaging.broadcast_system_status("Test status")

        # Should return False due to partial failure
        assert success is False

    def test_coordinate_handoff_success(self, messaging, mock_subprocess):
        """Test successful handoff coordination"""
        test_evidence = {"branch": "feat/test-feature", "tests_passing": True, "ci_status": "green"}

        success = messaging.coordinate_handoff("pm-1", "validator", "P0-HANDOFF", test_evidence)

        assert success is True

        expected_message = (
            f"📦 HANDOFF: Receiving PRP P0-HANDOFF from pm-1\nEvidence: {json.dumps(test_evidence, indent=2)}"
        )
        expected_cmd = [messaging.send_script, "validator:0", expected_message]
        mock_subprocess.run.assert_any_call(expected_cmd, capture_output=True, text=True)

    def test_coordinate_handoff_unknown_agent(self, messaging, mock_subprocess):
        """Test handoff coordination with unknown receiving agent"""
        test_evidence = {"test": "data"}

        success = messaging.coordinate_handoff("pm-1", "unknown-agent", "P0-FAIL", test_evidence)

        assert success is False
        # Should not make any subprocess calls
        mock_subprocess.run.assert_not_called()

    def test_agent_to_window_mapping(self, messaging):
        """Test agent name to window mapping"""
        mappings = {
            "pm-1": "dev-1",
            "pm-2": "dev-2",
            "pm-3": "dev-3",
            "validator": "validator",
            "integrator": "integrator",
            "orchestrator": "orchestrator",
        }

        for agent, expected_window in mappings.items():
            window = messaging._agent_to_window(agent)
            assert window == expected_window

        # Test unknown agent
        unknown_window = messaging._agent_to_window("unknown")
        assert unknown_window is None

    def test_messaging_integration_workflow(self, messaging, mock_subprocess):
        """Test complete messaging workflow for PRP lifecycle"""

        # 1. PM Assignment
        messaging.notify_pm_assignment("dev-1", "P0-WORKFLOW")

        # 2. Status Check
        messaging.request_agent_status("dev-1")

        # 3. Validator Handoff
        messaging.notify_validator_handoff("P0-WORKFLOW", "pm-1")

        # 4. Integration Handoff
        messaging.notify_integrator_handoff("P0-WORKFLOW")

        # 5. System Status Broadcast
        messaging.broadcast_system_status("Workflow test completed")

        # Verify all messages were sent successfully
        # Assignment (2 calls) + Status (2) + Validator (2) + Integrator (2) + Broadcast (5×2) = 18
        assert mock_subprocess.run.call_count == 18

        # Verify specific message content was sent correctly
        calls = mock_subprocess.run.call_args_list

        # Check PM assignment message
        pm_assign_call = calls[0]
        assert "P0-WORKFLOW" in pm_assign_call[0][0][1]
        assert "ASSIGNMENT" in pm_assign_call[0][0][1]

        # Check validator handoff message
        validator_calls = [call for call in calls if "validator:0" in str(call)]
        assert len(validator_calls) >= 1

        # Check integrator handoff message
        integrator_calls = [call for call in calls if "integrator:0" in str(call)]
        assert len(integrator_calls) >= 1

    def test_error_handling_robustness(self, messaging):
        """Test error handling robustness across different failure modes"""

        # Test with script not found
        with patch("bin.orchestrator_messaging.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("Script not found")

            success = messaging.send_to_agent("dev-1", "0", "test")
            assert success is False

        # Test with permission denied
        with patch("bin.orchestrator_messaging.subprocess.run") as mock_run:
            mock_run.side_effect = PermissionError("Permission denied")

            success = messaging.notify_pm_assignment("dev-1", "P0-FAIL")
            assert success is False

        # Test with timeout
        with patch("bin.orchestrator_messaging.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("tmux", 30)

            success = messaging.escalate_to_orchestrator("Test issue", {})
            assert success is False

    def test_message_formatting_and_encoding(self, messaging, mock_subprocess):
        """Test proper message formatting and encoding"""

        # Test with special characters
        special_message = "Test with émojis 🚀 and spécial chars"
        success = messaging.send_to_agent("dev-1", "0", special_message)

        assert success is True
        call_args = mock_subprocess.run.call_args_list[0][0][0]
        assert special_message in call_args

        # Test with JSON-like content
        json_like_message = '{"test": "value", "array": [1,2,3]}'
        success = messaging.send_to_agent("dev-2", "0", json_like_message)

        assert success is True

        # Test with multiline content
        multiline_message = "Line 1\nLine 2\nLine 3"
        success = messaging.send_to_agent("dev-3", "0", multiline_message)

        assert success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
