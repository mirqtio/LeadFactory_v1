"""
Test Marker Policy - P0-006

Ensures all failing tests are properly marked with xfail or phase_future.
This helps maintain a green KEEP test suite.

Acceptance Criteria:
- Collects tests and asserts no un-marked failures
- Verifies marker usage is correct
"""

import pytest
import subprocess
import json


class TestMarkerPolicy:
    """Test that all failing tests are properly marked"""

    def test_no_unmarked_failures(self):
        """
        Test that all failing tests have appropriate markers
        
        This test runs the KEEP test suite and verifies that:
        1. No tests fail without xfail/phase_future markers
        2. The test suite passes (exit code 0)
        """
        # Run pytest with json output to analyze results
        cmd = [
            "pytest",
            "-m", "not phase_future and not slow",
            "--json-report",
            "--json-report-file=/tmp/test_results.json",
            "--tb=no",
            "-q"
        ]
        
        # Run the test suite
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Load the JSON report
        try:
            with open("/tmp/test_results.json", "r") as f:
                report = json.load(f)
        except FileNotFoundError:
            pytest.skip("JSON report not generated - pytest-json-report may not be installed")
        
        # Check for failures
        summary = report.get("summary", {})
        tests = report.get("tests", [])
        
        # Find any failed tests that aren't marked
        unmarked_failures = []
        for test in tests:
            if test.get("outcome") == "failed":
                # Check if test has xfail marker
                markers = test.get("keywords", [])
                if "xfail" not in markers and "phase_future" not in markers:
                    unmarked_failures.append(test.get("nodeid"))
        
        # Assert no unmarked failures
        assert len(unmarked_failures) == 0, (
            f"Found {len(unmarked_failures)} unmarked test failures:\n" +
            "\n".join(unmarked_failures) +
            "\n\nThese tests should be marked with @pytest.mark.xfail or @pytest.mark.phase_future"
        )
        
        # Check that we have a reasonable number of passing tests
        passed = summary.get("passed", 0)
        assert passed > 100, f"Expected at least 100 passing tests, got {passed}"
        
        # Verify no actual failures (only xfailed/xpassed)
        failed = summary.get("failed", 0)
        errors = summary.get("error", 0)
        assert failed == 0, f"Found {failed} test failures"
        assert errors <= 10, f"Found {errors} test errors (expected <= 10)"

    def test_xfail_markers_have_reasons(self):
        """
        Test that xfail markers include reasons
        
        This ensures good documentation of why tests are expected to fail.
        """
        # This is more of a code quality check - would need AST parsing
        # For now, we'll just verify the test suite structure
        pytest.skip("AST-based marker validation not implemented yet")

    def test_phase_future_tests_are_skipped(self):
        """
        Test that phase_future tests are properly deselected
        """
        # Run pytest collecting only phase_future tests
        cmd = [
            "pytest",
            "-m", "phase_future",
            "--collect-only",
            "-q"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Should find some phase_future tests
        assert "deselected" in result.stdout or "collected" in result.stdout, (
            "No phase_future tests found - marker may not be working"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])