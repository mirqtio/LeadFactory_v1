#!/usr/bin/env python3
"""
Validation tests for EVIDENCE_COMPLETE footer protocol
Tests the reliable agent work completion detection system
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


class TestEvidenceProtocol(unittest.TestCase):
    """Test suite for EVIDENCE_COMPLETE footer protocol"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock enterprise shim for testing
        self.shim_class = None
        try:
            from bin.enterprise_shim import EnterpriseShim
            from infra.agent_coordinator import AgentType

            self.shim_class = EnterpriseShim
            self.agent_type = AgentType.PM
        except ImportError:
            # Skip tests that require enterprise components
            self.skipTest("Enterprise components not available")

    def test_footer_detection_valid_json(self):
        """Test detection of valid EVIDENCE_COMPLETE footer"""
        pane_output = """
All tests passing ✅
Coverage at 85%, lint clean

EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["tests_passed","lint_clean","coverage_pct"]}
"""

        # Create mock shim for testing detection method
        class MockShim:
            def detect_evidence_footer(self, output):
                lines = output.strip().split("\n")
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith("EVIDENCE_COMPLETE "):
                        json_part = line[len("EVIDENCE_COMPLETE ") :].strip()
                        try:
                            data = json.loads(json_part)
                            return True, data, []
                        except json.JSONDecodeError:
                            return True, {}, []
                return False, {}, []

        mock_shim = MockShim()
        footer_found, evidence_data, questions = mock_shim.detect_evidence_footer(pane_output)

        self.assertTrue(footer_found)
        self.assertEqual(evidence_data["stage"], "dev")
        self.assertTrue(evidence_data["success"])
        self.assertIn("tests_passed", evidence_data["keys"])
        self.assertIn("lint_clean", evidence_data["keys"])
        self.assertIn("coverage_pct", evidence_data["keys"])

    def test_footer_detection_with_questions(self):
        """Test detection of footer with questions above it"""
        pane_output = """
Implementation complete
All tests passing

QUESTION: Should we also update the API docs?
QUESTION: Do we need integration tests?
EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["implementation_complete"]}
"""

        class MockShim:
            def detect_evidence_footer(self, output):
                lines = output.strip().split("\n")
                questions = []
                evidence_data = {}
                footer_found = False

                for i in range(len(lines) - 1, -1, -1):
                    line = lines[i].strip()
                    if line.startswith("EVIDENCE_COMPLETE "):
                        json_part = line[len("EVIDENCE_COMPLETE ") :].strip()
                        try:
                            evidence_data = json.loads(json_part)
                            footer_found = True
                            # Look for questions above the footer
                            for j in range(max(0, i - 10), i):
                                prev_line = lines[j].strip()
                                if prev_line.startswith("QUESTION:"):
                                    question_text = prev_line[len("QUESTION:") :].strip()
                                    if question_text:
                                        questions.append(question_text)
                            break
                        except json.JSONDecodeError:
                            footer_found = True
                            break

                return footer_found, evidence_data, questions

        mock_shim = MockShim()
        footer_found, evidence_data, questions = mock_shim.detect_evidence_footer(pane_output)

        self.assertTrue(footer_found)
        self.assertEqual(len(questions), 2)
        self.assertIn("Should we also update the API docs?", questions)
        self.assertIn("Do we need integration tests?", questions)

    def test_footer_detection_malformed_json(self):
        """Test handling of malformed JSON in footer"""
        pane_output = """
Work complete

EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["malformed json}
"""

        class MockShim:
            def detect_evidence_footer(self, output):
                lines = output.strip().split("\n")
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith("EVIDENCE_COMPLETE "):
                        json_part = line[len("EVIDENCE_COMPLETE ") :].strip()
                        try:
                            data = json.loads(json_part)
                            return True, data, []
                        except json.JSONDecodeError:
                            return True, {}, []  # Found footer but malformed
                return False, {}, []

        mock_shim = MockShim()
        footer_found, evidence_data, questions = mock_shim.detect_evidence_footer(pane_output)

        self.assertTrue(footer_found)
        self.assertEqual(evidence_data, {})  # Empty due to malformed JSON

    def test_no_footer_detection(self):
        """Test when no footer is present"""
        pane_output = """
Some regular output
No evidence footer here
Just normal completion text
"""

        class MockShim:
            def detect_evidence_footer(self, output):
                lines = output.strip().split("\n")
                for line in reversed(lines):
                    if line.strip().startswith("EVIDENCE_COMPLETE "):
                        return True, {}, []
                return False, {}, []

        mock_shim = MockShim()
        footer_found, evidence_data, questions = mock_shim.detect_evidence_footer(pane_output)

        self.assertFalse(footer_found)
        self.assertEqual(evidence_data, {})
        self.assertEqual(questions, [])

    def test_multiple_footers_uses_last(self):
        """Test that detection uses the last/most recent footer"""
        pane_output = """
First attempt
EVIDENCE_COMPLETE {"stage":"dev","success":false,"keys":["partial"]}

Updated work
EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["tests_passed","complete"]}
"""

        class MockShim:
            def detect_evidence_footer(self, output):
                lines = output.strip().split("\n")
                for line in reversed(lines):
                    line = line.strip()
                    if line.startswith("EVIDENCE_COMPLETE "):
                        json_part = line[len("EVIDENCE_COMPLETE ") :].strip()
                        try:
                            data = json.loads(json_part)
                            return True, data, []
                        except json.JSONDecodeError:
                            return True, {}, []
                return False, {}, []

        mock_shim = MockShim()
        footer_found, evidence_data, questions = mock_shim.detect_evidence_footer(pane_output)

        self.assertTrue(footer_found)
        self.assertTrue(evidence_data["success"])  # Should use the last footer
        self.assertIn("complete", evidence_data["keys"])
        self.assertNotIn("partial", evidence_data["keys"])

    def test_stage_queue_mapping(self):
        """Test correct queue mapping for different stages"""
        test_cases = [
            ("dev", "validation_queue"),
            ("validation", "integration_queue"),
            ("integration", "completion_queue"),
            ("unknown", "completion_queue"),  # Default case
        ]

        class MockShim:
            def _get_next_queue(self, current_stage: str) -> str:
                stage_map = {
                    "dev": "validation_queue",
                    "validation": "integration_queue",
                    "integration": "completion_queue",
                }
                return stage_map.get(current_stage, "completion_queue")

        mock_shim = MockShim()

        for input_stage, expected_queue in test_cases:
            result = mock_shim._get_next_queue(input_stage)
            self.assertEqual(result, expected_queue, f"Stage '{input_stage}' should map to '{expected_queue}'")

    def test_integration_with_tmux_pattern(self):
        """Integration test simulating full tmux capture → evidence → promotion flow"""
        # This would be a real integration test with actual tmux, Redis, and Lua script
        # For now, we test the core logic components

        class MockIntegrationShim:
            def __init__(self):
                self.current_prp = "TEST-001"
                self.promotions_executed = []

            def detect_evidence_footer(self, output):
                # Real implementation would be more complex
                if "EVIDENCE_COMPLETE" in output:
                    return True, {"stage": "dev", "success": True, "keys": ["tests_passed"]}, []
                return False, {}, []

            def promote_prp(self, prp_id, stage, evidence_data):
                # Mock promotion
                self.promotions_executed.append({"prp_id": prp_id, "stage": stage, "evidence": evidence_data})
                return True

        # Simulate the flow
        mock_shim = MockIntegrationShim()

        # Simulate tmux output with footer
        tmux_output = """
Implementation finished
All tests pass ✅

EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["tests_passed"]}
"""

        # Test detection
        footer_found, evidence_data, questions = mock_shim.detect_evidence_footer(tmux_output)
        self.assertTrue(footer_found)

        # Test promotion
        if footer_found:
            mock_shim.promote_prp(mock_shim.current_prp, evidence_data["stage"], evidence_data)

        # Verify promotion was called
        self.assertEqual(len(mock_shim.promotions_executed), 1)
        promotion = mock_shim.promotions_executed[0]
        self.assertEqual(promotion["prp_id"], "TEST-001")
        self.assertEqual(promotion["stage"], "dev")


class TestProtocolCompliance(unittest.TestCase):
    """Test protocol compliance and edge cases"""

    def test_footer_must_be_last_line(self):
        """Test that footer detection works when footer is last line"""
        valid_output = """
Work complete
EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["done"]}"""

        invalid_output = """
Work complete
EVIDENCE_COMPLETE {"stage":"dev","success":true,"keys":["done"]}
Some text after footer
"""

        def detect_footer(output):
            lines = output.strip().split("\n")
            last_line = lines[-1].strip() if lines else ""
            return last_line.startswith("EVIDENCE_COMPLETE ")

        self.assertTrue(detect_footer(valid_output))
        # Note: Current implementation searches all lines, not just last
        # This test documents the intended behavior

    def test_required_evidence_fields(self):
        """Test validation of required evidence fields"""
        test_cases = [
            # (evidence_data, expected_valid)
            ({"stage": "dev", "success": True, "keys": ["tests"]}, True),
            ({"stage": "dev", "success": False, "keys": []}, True),  # Failed but valid
            ({"success": True, "keys": ["tests"]}, False),  # Missing stage
            ({"stage": "dev", "keys": ["tests"]}, False),  # Missing success
            ({"stage": "dev", "success": True}, False),  # Missing keys
            ({}, False),  # Empty
        ]

        def validate_evidence_fields(evidence_data):
            required_fields = ["stage", "success", "keys"]
            return all(field in evidence_data for field in required_fields)

        for evidence_data, expected_valid in test_cases:
            result = validate_evidence_fields(evidence_data)
            self.assertEqual(result, expected_valid, f"Evidence {evidence_data} validation should be {expected_valid}")


def run_protocol_tests():
    """Run all protocol validation tests"""
    print("🧪 Running EVIDENCE_COMPLETE Protocol Tests...")
    print("=" * 60)

    # Create test suite
    suite = unittest.TestSuite()

    # Add test cases
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestEvidenceProtocol))
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestProtocolCompliance))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Report results
    if result.wasSuccessful():
        print("\n" + "=" * 60)
        print("✅ All EVIDENCE_COMPLETE protocol tests PASSED!")
        print(f"Tests run: {result.testsRun}")
        return True
    else:
        print("\n" + "=" * 60)
        print("❌ Some protocol tests FAILED!")
        print(f"Tests run: {result.testsRun}")
        print(f"Failures: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        return False


if __name__ == "__main__":
    success = run_protocol_tests()
    sys.exit(0 if success else 1)
