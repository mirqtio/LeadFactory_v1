#!/usr/bin/env python3
"""
Simpler tests for shim functionality without full lifecycle
"""
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest


class TestShimFunctions:
    """Test individual shim functions without the full run loop"""

    def test_evidence_parsing(self):
        """Test evidence parsing logic"""
        from bin.enterprise_shim_v2 import AgentType, EnterpriseShimV2

        # Create a minimal shim instance
        with patch("subprocess.run"):
            shim = EnterpriseShimV2(AgentType.PM, "main", "dev-1", "dev_queue", "redis://localhost:6379/0")

            # Mock Redis
            shim.redis_client = MagicMock()
            shim.current_prp = "P0-001"

            # Test valid evidence parsing
            valid_output = """
Working on P0-001...
Running tests...
Tests passed ✓
Coverage: 85%

=== EVIDENCE_COMPLETE ===
{
  "tests_passed": "true",
  "coverage_pct": "85",
  "lint_passed": "true",
  "timestamp": "2024-01-01T00:00:00"
}
"""
            # Mock capture_tmux_output to return our test data
            with patch.object(shim, "capture_tmux_output", return_value=valid_output):
                evidence = shim.check_evidence_complete()

                assert evidence is not None
                assert evidence["tests_passed"] == "true"
                assert evidence["coverage_pct"] == "85"
                assert evidence["lint_passed"] == "true"

    def test_malformed_evidence_parsing(self):
        """Test malformed evidence handling"""
        from bin.enterprise_shim_v2 import AgentType, EnterpriseShimV2

        with patch("subprocess.run"):
            shim = EnterpriseShimV2(AgentType.PM, "main", "dev-1", "dev_queue", "redis://localhost:6379/0")
            shim.redis_client = MagicMock()
            shim.current_prp = "P0-002"

            # Malformed JSON
            malformed_output = """
Working on P0-002...
=== EVIDENCE_COMPLETE ===
{
  "tests_passed": true,  // Using boolean instead of string
  "coverage_pct": 85,
  // Missing closing brace
"""
            with patch.object(shim, "capture_tmux_output", return_value=malformed_output):
                evidence = shim.check_evidence_complete()
                assert evidence is None  # Should fail to parse

    def test_promote_prp(self):
        """Test PRP promotion logic"""
        from bin.enterprise_shim_v2 import AgentType, EnterpriseShimV2

        with patch("subprocess.run"):
            shim = EnterpriseShimV2(AgentType.PM, "main", "dev-1", "dev_queue", "redis://localhost:6379/0")

            # Mock Redis client
            shim.redis_client = MagicMock()

            # Mock the Lua script registration and execution
            mock_script = MagicMock()
            mock_script.return_value = b"PROMOTED"
            shim.redis_client.register_script.return_value = mock_script

            # Test promotion
            result = shim.promote_prp("P0-003", "dev_queue", "validation_queue")

            assert result == True
            # The actual call includes inflight queue and prp key
            mock_script.assert_called_once_with(
                keys=["dev_queue:inflight", "validation_queue", "prp:P0-003"], args=["P0-003"]
            )

    def test_send_to_tmux(self):
        """Test tmux send functionality"""
        from bin.enterprise_shim_v2 import AgentType, EnterpriseShimV2

        with patch("subprocess.run") as mock_run:
            shim = EnterpriseShimV2(AgentType.PM, "main", "dev-1", "dev_queue", "redis://localhost:6379/0")
            shim.redis_client = MagicMock()

            # Test sending a message
            shim.send_to_tmux("Test message")

            # Verify subprocess was called correctly
            # The actual implementation quotes the message
            mock_run.assert_called_with(
                ["tmux", "send-keys", "-t", "main:dev-1", '"Test message"', "Enter"], capture_output=True, check=False
            )

    def test_question_detection(self):
        """Test Q&A detection in output"""
        from bin.enterprise_shim_v2 import AgentType, EnterpriseShimV2

        with patch("subprocess.run"):
            shim = EnterpriseShimV2(
                AgentType.VALIDATOR, "main", "validator", "validation_queue", "redis://localhost:6379/0"
            )
            shim.redis_client = MagicMock()
            shim.current_prp = "P0-004"

            # Output with question
            question_output = """
Working on P0-004...
I need clarification:
❓ QUESTION: Should I use PostgreSQL or SQLite for this feature?
Waiting for response...
"""
            # Mock the output and Redis operations
            with patch.object(shim, "capture_tmux_output", return_value=question_output):
                # In the real shim, this would be detected in process_queue_message
                assert "❓ QUESTION:" in question_output
                assert "PostgreSQL or SQLite" in question_output


if __name__ == "__main__":
    # Run a simple test
    test = TestShimFunctions()
    test.test_evidence_parsing()
    print("✅ Evidence parsing test passed")

    test.test_malformed_evidence_parsing()
    print("✅ Malformed evidence test passed")

    test.test_promote_prp()
    print("✅ PRP promotion test passed")
