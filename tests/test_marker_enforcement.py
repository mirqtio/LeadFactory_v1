"""
Test marker enforcement and validation system.

This module tests the marker inheritance and validation functionality.
"""
import os
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

from tests.markers import (
    DOMAIN_MARKERS,
    PRIMARY_MARKERS,
    VALID_MARKERS,
    MarkerValidator,
    apply_auto_markers,
    generate_marker_report,
    get_marker_statistics,
)

# Mark entire module as unit test - tests the test infrastructure
pytestmark = pytest.mark.unit


class TestMarkerValidator:
    """Test the MarkerValidator class."""

    def test_validate_item_missing_primary_marker(self):
        """Test validation catches missing primary markers."""

        # Create a mock test item without primary markers
        class MockItem:
            nodeid = "tests/some_test.py::test_function"

            def iter_markers(self):
                # Return markers that don't include primary ones
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("asyncio"), MockMarker("timeout")]

        validator = MarkerValidator()
        errors, warnings = validator.validate_item(MockItem())

        assert len(errors) == 1
        assert "Missing required primary marker" in errors[0]
        assert len(warnings) == 0

    def test_validate_item_with_primary_marker(self):
        """Test validation passes with primary marker."""

        class MockItem:
            nodeid = "tests/unit/test_something.py::test_function"

            def iter_markers(self):
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("unit"), MockMarker("asyncio")]

        validator = MarkerValidator()
        errors, warnings = validator.validate_item(MockItem())

        assert len(errors) == 0
        assert len(warnings) == 0

    def test_validate_item_multiple_primary_markers(self):
        """Test validation warns about multiple primary markers."""

        class MockItem:
            nodeid = "tests/test_something.py::test_function"

            def iter_markers(self):
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("unit"), MockMarker("integration")]

        validator = MarkerValidator()
        errors, warnings = validator.validate_item(MockItem())

        assert len(errors) == 0
        assert len(warnings) == 1
        assert "Multiple primary markers found" in warnings[0]

    def test_validate_item_unknown_marker(self):
        """Test validation catches unknown markers."""

        class MockItem:
            nodeid = "tests/unit/test_something.py::test_function"

            def iter_markers(self):
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("unit"), MockMarker("unknown_marker")]

        validator = MarkerValidator()
        errors, warnings = validator.validate_item(MockItem())

        assert len(errors) == 1
        assert "Unknown markers found: unknown_marker" in errors[0]
        assert len(warnings) == 0

    def test_get_expected_markers_unit_test(self):
        """Test expected markers for unit test."""

        class MockItem:
            fspath = Path("/project/tests/unit/test_something.py")

        validator = MarkerValidator()
        expected = validator.get_expected_markers(MockItem())

        assert "unit" in expected

    def test_get_expected_markers_integration_test(self):
        """Test expected markers for integration test."""

        class MockItem:
            fspath = Path("/project/tests/integration/test_something.py")

        validator = MarkerValidator()
        expected = validator.get_expected_markers(MockItem())

        assert "integration" in expected

    def test_get_expected_markers_domain_test(self):
        """Test expected markers for domain-specific test."""

        class MockItem:
            fspath = Path("/project/tests/unit/d0_gateway/test_api.py")

        validator = MarkerValidator()
        expected = validator.get_expected_markers(MockItem())

        assert "unit" in expected
        assert "d0_gateway" in expected

    def test_suggest_markers(self):
        """Test marker suggestions."""

        class MockItem:
            fspath = Path("/project/tests/unit/d1_targeting/test_targeting.py")

            def iter_markers(self):
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("unit")]  # Missing d1_targeting

        validator = MarkerValidator()
        suggestions = validator.suggest_markers(MockItem())

        assert "d1_targeting" in suggestions
        assert "unit" not in suggestions  # Already has it


class TestApplyAutoMarkers:
    """Test the apply_auto_markers function."""

    def test_apply_unit_marker(self):
        """Test automatic application of unit marker."""
        markers_added = []

        class MockItem:
            fspath = Path("/project/tests/unit/test_something.py")

            def iter_markers(self):
                return []

            def add_marker(self, marker):
                markers_added.append(marker)

        class MockMark:
            unit = "unit_marker"

        # Patch pytest.mark
        original_mark = pytest.mark
        pytest.mark = MockMark()

        try:
            apply_auto_markers(MockItem())
            assert "unit_marker" in markers_added
        finally:
            pytest.mark = original_mark

    def test_apply_domain_marker(self):
        """Test automatic application of domain markers."""
        markers_added = []

        class MockItem:
            fspath = Path("/project/tests/unit/d2_sourcing/test_source.py")

            def iter_markers(self):
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("unit")]  # Already has unit

            def add_marker(self, marker):
                markers_added.append(marker)

        class MockMark:
            d2_sourcing = "d2_sourcing_marker"

        # Patch pytest.mark
        original_mark = pytest.mark
        pytest.mark = MockMark()

        try:
            apply_auto_markers(MockItem())
            assert "d2_sourcing_marker" in markers_added
        finally:
            pytest.mark = original_mark

    def test_skip_existing_primary_marker(self):
        """Test that existing primary markers are not overridden."""
        markers_added = []

        class MockItem:
            fspath = Path("/project/tests/unit/test_something.py")

            def iter_markers(self):
                class MockMarker:
                    def __init__(self, name):
                        self.name = name

                return [MockMarker("integration")]  # Different primary marker

            def add_marker(self, marker):
                markers_added.append(marker)

        apply_auto_markers(MockItem())

        # Should not add unit marker since it already has integration
        assert len(markers_added) == 0


class TestMarkerStatistics:
    """Test marker statistics functionality."""

    def test_get_marker_statistics(self):
        """Test getting marker statistics."""

        class MockMarker:
            def __init__(self, name):
                self.name = name

        class MockItem:
            def __init__(self, markers):
                self._markers = markers

            def iter_markers(self):
                return [MockMarker(m) for m in self._markers]

        items = [
            MockItem(["unit", "asyncio"]),
            MockItem(["unit", "d0_gateway"]),
            MockItem(["integration", "slow"]),
            MockItem(["unit"]),
        ]

        stats = get_marker_statistics(items)

        assert stats["unit"] == 3
        assert stats["integration"] == 1
        assert stats["asyncio"] == 1
        assert stats["d0_gateway"] == 1
        assert stats["slow"] == 1


class TestMarkerReport:
    """Test marker report generation."""

    def test_generate_marker_report(self):
        """Test generating a marker report."""

        class MockMarker:
            def __init__(self, name):
                self.name = name

        class MockItem:
            def __init__(self, nodeid, markers):
                self.nodeid = nodeid
                self._markers = markers

            def iter_markers(self):
                return [MockMarker(m) for m in self._markers]

        items = [
            MockItem("test_a.py::test_1", ["unit"]),
            MockItem("test_b.py::test_2", ["integration", "slow"]),
            MockItem("test_c.py::test_3", ["unknown_marker"]),  # Will cause error
            MockItem("test_d.py::test_4", []),  # Missing primary marker
        ]

        report = generate_marker_report(items)

        # Check report contains expected sections
        assert "MARKER VALIDATION REPORT" in report
        assert "Marker Usage Statistics:" in report
        assert "Validation Errors" in report
        assert "Total tests: 4" in report
        assert "unit: 1 tests" in report
        assert "integration: 1 tests" in report


@pytest.mark.unit
class TestMarkerEnforcementIntegration:
    """Integration tests for marker enforcement in pytest runs."""

    def test_validate_markers_flag(self, tmp_path):
        """Test that --validate-markers flag works."""
        # Create a test file without markers
        test_file = tmp_path / "test_no_markers.py"
        test_file.write_text(
            dedent(
                """
            def test_something():
                assert True
        """
            )
        )

        # Run pytest with validation
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "--validate-markers", "-v"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),  # Run from project root
        )

        # Should fail due to missing markers
        assert result.returncode != 0
        assert "Missing required primary marker" in result.stdout

    def test_show_marker_report_flag(self, tmp_path):
        """Test that --show-marker-report flag works."""
        # Create a test file with markers
        test_file = tmp_path / "test_with_markers.py"
        test_file.write_text(
            dedent(
                """
            import pytest
            
            @pytest.mark.unit
            def test_something():
                assert True
        """
            )
        )

        # Run pytest with report
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "--show-marker-report", "-v"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),  # Run from project root
        )

        # Should show marker report
        assert "MARKER VALIDATION REPORT" in result.stdout
        assert "Marker Usage Statistics:" in result.stdout


@pytest.mark.unit
def test_marker_constants():
    """Test that marker constants are properly defined."""
    assert PRIMARY_MARKERS == {"unit", "integration", "e2e", "smoke"}
    assert "d0_gateway" in DOMAIN_MARKERS
    assert "d1_targeting" in DOMAIN_MARKERS
    assert len(VALID_MARKERS) > len(PRIMARY_MARKERS)  # Should include all types
