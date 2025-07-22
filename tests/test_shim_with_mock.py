#!/usr/bin/env python3
"""
Test shim interactions using mock Claude panes
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.mock_claude_pane import MockClaudePane, MockTmuxServer, create_test_environment


class TestShimWithMock:
    """Test shim behaviors with deterministic mock Claude panes"""

    def setup_method(self):
        """Set up test environment"""
        self.server = create_test_environment()
        self.redis_mock = MagicMock()

        # Mock Redis responses
        self.redis_mock.from_url.return_value = self.redis_mock
        self.redis_mock.brpoplpush.return_value = None  # Default no messages
        self.redis_mock.lrem.return_value = 1
        self.redis_mock.lpush.return_value = 1
        self.redis_mock.hget.return_value = None
        self.redis_mock.hset.return_value = True
        self.redis_mock.hincrby.return_value = 1

    def create_shim(self, agent_type: str, window_name: str, queue_name: str):
        """Create a shim instance with mocked dependencies"""
        # Import here to avoid circular imports
        from bin.enterprise_shim_v2 import AgentType, EnterpriseShimV2

        # Parse session and window from window_name
        if ":" in window_name:
            session, window = window_name.split(":")
        else:
            session = "main"
            window = window_name

        # Convert agent_type string to AgentType enum
        agent_type_map = {
            "pm": AgentType.PM,
            "validator": AgentType.VALIDATOR,
            "integrator": AgentType.INTEGRATOR,
            "orchestrator": AgentType.ORCHESTRATOR,
        }
        agent_type_enum = agent_type_map.get(agent_type, AgentType.PM)

        # Mock subprocess to use our mock server
        def mock_subprocess_run(cmd, *args, **kwargs):
            result = MagicMock()
            if "capture-pane" in cmd:
                # Extract window name from command
                for i, arg in enumerate(cmd):
                    if arg == "-t":
                        target = cmd[i + 1]
                        sess, win = target.split(":")
                        result.stdout = self.server.capture_pane(sess, win).encode()
                        result.returncode = 0
                        return result
            elif "send-keys" in cmd:
                # Extract window and text
                for i, arg in enumerate(cmd):
                    if arg == "-t":
                        target = cmd[i + 1]
                        sess, win = target.split(":")
                        text = cmd[i + 2] if i + 2 < len(cmd) else ""
                        self.server.send_keys(sess, win, text)
                        result.returncode = 0
                        return result
            result.returncode = 0
            result.stdout = b""
            return result

        # Create the shim with mocked subprocess
        with patch("subprocess.run", side_effect=mock_subprocess_run):
            shim = EnterpriseShimV2(agent_type_enum, session, window, queue_name, "redis://localhost:6379/0")
            shim.redis_client = self.redis_mock

            # Also patch subprocess.run in the shim's module
            import bin.enterprise_shim_v2

            bin.enterprise_shim_v2.subprocess.run = mock_subprocess_run

            return shim

    def test_normal_evidence_completion(self):
        """Test shim handles normal evidence completion correctly"""
        # Set up dev-1 pane with normal behavior
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("normal")

        # Create shim
        shim = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim.current_prp = "P0-001"

        # Simulate PRP assignment
        self.server.send_keys("main", "dev-1", "Please work on P0-001")

        # Check for evidence
        # First let's see what output we have
        output = shim.capture_tmux_output(50)
        print(f"Captured output: {output}")

        evidence = shim.check_evidence_complete()
        print(f"Evidence found: {evidence}")

        assert evidence is not None, f"Should detect evidence. Output was: {output}"
        assert evidence["tests_passed"] == "true"
        assert evidence["coverage_pct"] == "85"
        assert evidence["lint_passed"] == "true"

    def test_malformed_evidence_detection(self):
        """Test shim handles malformed evidence JSON"""
        # Set up dev-1 with malformed evidence
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("malformed_evidence")

        # Create shim
        shim = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim.current_prp = "P0-002"

        # Simulate PRP assignment
        self.server.send_keys("main", "dev-1", "Please work on P0-002")

        # Check for evidence - should return None due to parse error
        evidence = shim.check_evidence_complete()

        assert evidence is None, "Should not parse malformed JSON"

    def test_incomplete_evidence_rejection(self):
        """Test shim rejects incomplete evidence"""
        # Set up dev-1 with incomplete evidence
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("incomplete_evidence")

        # Create shim
        shim = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim.current_prp = "P0-003"

        # Simulate PRP assignment
        self.server.send_keys("main", "dev-1", "Please work on P0-003")

        # Check for evidence
        evidence = shim.check_evidence_complete()

        # Evidence should be detected but validation should fail
        assert evidence is not None, "Should detect evidence footer"
        assert evidence["tests_passed"] == "false", "Tests should have failed"
        assert "coverage_pct" not in evidence, "Coverage should be missing"

    def test_question_answer_flow(self):
        """Test Q&A communication between agent and shim"""
        # Set up validator with question-asking behavior
        validator = self.server.get_pane("main", "validator")
        validator.set_behavior("question_asking")

        # Create shim
        shim = self.create_shim("validator", "main:validator", "validation_queue")

        # Mock orchestrator queue for Q&A
        self.redis_mock.llen.return_value = 0  # No messages initially

        # Simulate PRP assignment
        self.server.send_keys("main", "validator", "Please validate P0-004")

        # Check for questions
        output = shim.capture_tmux_output(50)

        assert "❓ QUESTION:" in output, "Should detect question marker"
        assert "PostgreSQL or SQLite" in output, "Should contain the actual question"

        # Simulate answer
        shim.send_to_tmux("ANSWER: Use PostgreSQL for better performance")

        # Check that answer was received
        output_after = shim.capture_tmux_output(50)
        assert "Thank you for the clarification" in output_after

    def test_agent_crash_detection(self):
        """Test shim detects when agent crashes"""
        # Set up dev-1 with crash behavior
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("crash")

        # Create shim
        shim = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim.current_prp = "P0-005"

        # Simulate PRP assignment
        self.server.send_keys("main", "dev-1", "Please work on P0-005")

        # Check output
        output = shim.capture_tmux_output(50)

        assert "Segmentation fault" in output, "Should detect crash"

        # Evidence should not be found
        evidence = shim.check_evidence_complete()
        assert evidence is None, "No evidence after crash"

    def test_timeout_behavior(self):
        """Test shim handles agent timeout"""
        # Set up dev-1 with timeout behavior
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("timeout")

        # Create shim
        shim = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim.current_prp = "P0-006"

        # Set up Redis to indicate old inflight time
        prp_key = f"prp:{shim.current_prp}"
        old_time = datetime.utcnow() - timedelta(minutes=35)
        self.redis_mock.hget.side_effect = (
            lambda key, field: old_time.isoformat().encode() if field == "inflight_since" else None
        )

        # Simulate PRP assignment
        self.server.send_keys("main", "dev-1", "Please work on P0-006")

        # The shim should detect no evidence (timeout behavior)
        evidence = shim.check_evidence_complete()
        assert evidence is None, "Should not find evidence during timeout"

        # In real implementation, the watchdog would handle timeout
        # Here we just verify the agent didn't respond

    def test_rapid_output_buffer_handling(self):
        """Test shim handles rapid output without losing data"""
        # Set up dev-1 with rapid output
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("rapid_output")

        # Create shim
        shim = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim.current_prp = "P0-007"

        # Simulate PRP assignment
        self.server.send_keys("main", "dev-1", "Please work on P0-007")

        # Despite lots of output, should still find evidence
        evidence = shim.check_evidence_complete()

        assert evidence is not None, "Should find evidence even with lots of output"
        assert evidence["tests_passed"] == "true"

    def test_concurrent_pane_access(self):
        """Test multiple shims accessing different panes concurrently"""
        # Set up multiple panes
        dev1 = self.server.get_pane("main", "dev-1")
        dev2 = self.server.get_pane("main", "dev-2")
        dev1.set_behavior("normal")
        dev2.set_behavior("normal")

        # Create multiple shims
        shim1 = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim2 = self.create_shim("pm", "main:dev-2", "dev_queue")

        shim1.current_prp = "P0-008"
        shim2.current_prp = "P0-009"

        # Send work to both
        self.server.send_keys("main", "dev-1", "Please work on P0-008")
        self.server.send_keys("main", "dev-2", "Please work on P0-009")

        # Check both independently
        evidence1 = shim1.check_evidence_complete()
        evidence2 = shim2.check_evidence_complete()

        assert evidence1 is not None, "Shim 1 should find evidence"
        assert evidence2 is not None, "Shim 2 should find evidence"
        assert evidence1 != evidence2, "Evidence should be independent"

    def test_shim_recovery_after_restart(self):
        """Test shim can recover state after restart"""
        # Set up dev-1
        dev1 = self.server.get_pane("main", "dev-1")
        dev1.set_behavior("normal")

        # Create initial shim
        shim1 = self.create_shim("pm", "main:dev-1", "dev_queue")
        shim1.current_prp = "P0-010"

        # Simulate work in progress
        self.server.send_keys("main", "dev-1", "Please work on P0-010")

        # "Restart" shim (create new instance)
        shim2 = self.create_shim("pm", "main:dev-1", "dev_queue")

        # New shim should be able to detect existing evidence
        output = shim2.capture_tmux_output(50)
        assert "P0-010" in output, "Should see work from before restart"

        # Should detect evidence
        evidence = shim2.check_evidence_complete()
        assert evidence is not None, "Should find evidence after restart"


class TestIntegrationWithMock:
    """Integration tests using mock Claude panes"""

    def test_full_prp_lifecycle(self):
        """Test complete PRP lifecycle through all agents"""
        server = create_test_environment()
        redis_mock = MagicMock()

        # Set all agents to normal behavior
        for window in ["dev-1", "validator", "integrator"]:
            pane = server.get_pane("main", window)
            pane.set_behavior("normal")

        # Simulate PRP flow
        prp_id = "P0-100"

        # 1. Dev agent works on PRP
        server.send_keys("main", "dev-1", f"Please work on {prp_id}")
        dev_output = server.capture_pane("main", "dev-1")
        assert "EVIDENCE_COMPLETE" in dev_output

        # 2. Validator validates
        server.send_keys("main", "validator", f"Please validate {prp_id}")
        val_output = server.capture_pane("main", "validator")
        assert "EVIDENCE_COMPLETE" in val_output

        # 3. Integrator deploys
        server.send_keys("main", "integrator", f"Please integrate {prp_id}")
        int_output = server.capture_pane("main", "integrator")
        assert "EVIDENCE_COMPLETE" in int_output

        # All stages should complete successfully
        assert all("EVIDENCE_COMPLETE" in output for output in [dev_output, val_output, int_output])


if __name__ == "__main__":
    # Run specific test for debugging
    test = TestShimWithMock()
    test.setup_method()
    test.test_normal_evidence_completion()
    print("✅ Normal evidence test passed")

    test.test_malformed_evidence_detection()
    print("✅ Malformed evidence test passed")

    test.test_question_answer_flow()
    print("✅ Q&A flow test passed")
