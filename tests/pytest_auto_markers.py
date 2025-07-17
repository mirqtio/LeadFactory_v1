"""
Pytest plugin to automatically apply markers based on test location.

This plugin uses the existing marker infrastructure to ensure consistent
marker application across all tests.
"""
import pytest

from tests.markers import MarkerValidator, apply_auto_markers, generate_marker_report


def pytest_collection_modifyitems(config, items):
    """
    Hook to modify test items after collection.

    Automatically applies markers based on test file location.
    """
    # Apply auto markers to all items
    for item in items:
        apply_auto_markers(item)

    # Only validate if requested
    if config.getoption("--validate-markers", default=False):
        validator = MarkerValidator()
        errors = []
        warnings = []

        for item in items:
            item_errors, item_warnings = validator.validate_item(item)
            errors.extend(item_errors)
            warnings.extend(item_warnings)

        if errors:
            print("\n" + "=" * 80)
            print("MARKER VALIDATION ERRORS:")
            print("=" * 80)
            for error in errors:
                print(f"  ❌ {error}")
            print("=" * 80)
            pytest.exit(f"Found {len(errors)} marker validation errors", 1)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--validate-markers",
        action="store_true",
        default=False,
        help="Validate that all tests have appropriate markers",
    )
    parser.addoption(
        "--show-marker-report",
        action="store_true",
        default=False,
        help="Show detailed marker usage report",
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Add marker report to terminal summary if requested."""
    if config.getoption("--show-marker-report", default=False):
        items = [item for item in terminalreporter.stats.get("passed", [])]
        items.extend(terminalreporter.stats.get("failed", []))
        items.extend(terminalreporter.stats.get("skipped", []))
        items.extend(terminalreporter.stats.get("xfailed", []))
        items.extend(terminalreporter.stats.get("xpassed", []))

        if items:
            # Extract the actual test items
            test_items = []
            for report in items:
                if hasattr(report, "item"):
                    test_items.append(report.item)

            if test_items:
                report = generate_marker_report(test_items)
                terminalreporter.write("\n" + report + "\n")

