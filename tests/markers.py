"""
Marker validation utilities for pytest.

This module provides utilities for validating and enforcing marker usage
across the test suite.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pytest

# Primary test type markers (required - every test must have at least one)
PRIMARY_MARKERS = {"unit", "integration", "e2e", "smoke"}

# Domain markers (auto-applied based on directory structure)
DOMAIN_MARKERS = {
    "d0_gateway": "Gateway/API integration tests",
    "d1_targeting": "Targeting and filtering tests",
    "d2_sourcing": "Data sourcing tests",
    "d3_assessment": "Assessment and evaluation tests",
    "d4_enrichment": "Data enrichment tests",
    "d5_scoring": "Scoring and ranking tests",
    "d6_reports": "Reporting tests",
    "d7_storefront": "Storefront API tests",
    "d8_personalization": "Personalization tests",
    "d9_delivery": "Delivery and notification tests",
    "d10_analytics": "Analytics tests",
    "d11_orchestration": "Orchestration and workflow tests",
}

# Other allowed markers
OTHER_MARKERS = {
    "slow",
    "performance",
    "security",
    "timeout",
    "phase05",
    "phase_future",
    "critical",
    "flaky",
    "no_stubs",
    "minimal",
    "asyncio",
    "parametrize",
}

# All valid markers
VALID_MARKERS = PRIMARY_MARKERS | set(DOMAIN_MARKERS.keys()) | OTHER_MARKERS


class MarkerValidator:
    """Validates marker usage on test items."""

    def __init__(self):
        self.validation_errors: list[str] = []
        self.validation_warnings: list[str] = []

    def validate_item(self, item: pytest.Item) -> tuple[list[str], list[str]]:
        """
        Validate markers on a test item.

        Args:
            item: The pytest test item to validate

        Returns:
            Tuple of (errors, warnings) as lists of strings
        """
        errors = []
        warnings = []

        # Get all markers on the item
        markers = {mark.name for mark in item.iter_markers()}

        # Check for at least one primary marker
        primary_markers_found = markers & PRIMARY_MARKERS
        if not primary_markers_found:
            errors.append(
                f"{item.nodeid}: Missing required primary marker. "
                f"Must have at least one of: {', '.join(sorted(PRIMARY_MARKERS))}"
            )

        # Check for multiple primary markers (warning)
        if len(primary_markers_found) > 1:
            warnings.append(
                f"{item.nodeid}: Multiple primary markers found: "
                f"{', '.join(sorted(primary_markers_found))}. Consider using only one."
            )

        # Check for unknown markers
        unknown_markers = markers - VALID_MARKERS
        if unknown_markers:
            errors.append(f"{item.nodeid}: Unknown markers found: {', '.join(sorted(unknown_markers))}")

        return errors, warnings

    def get_expected_markers(self, item: pytest.Item) -> set[str]:
        """
        Get the expected markers for a test item based on its location.

        Args:
            item: The pytest test item

        Returns:
            Set of expected marker names
        """
        expected = set()

        # Determine test type from path
        test_path = str(item.fspath)
        if "/unit/" in test_path:
            expected.add("unit")
        elif "/integration/" in test_path:
            expected.add("integration")
        elif "/e2e/" in test_path:
            expected.add("e2e")
        elif "/smoke/" in test_path:
            expected.add("smoke")

        # Add domain markers based on directory
        for domain in DOMAIN_MARKERS:
            if f"/{domain}/" in test_path:
                expected.add(domain)

        return expected

    def suggest_markers(self, item: pytest.Item) -> list[str]:
        """
        Suggest markers that should be applied to a test item.

        Args:
            item: The pytest test item

        Returns:
            List of suggested marker names
        """
        current_markers = {mark.name for mark in item.iter_markers()}
        expected_markers = self.get_expected_markers(item)

        # Suggest missing expected markers
        suggestions = list(expected_markers - current_markers)

        return suggestions


def apply_auto_markers(item: pytest.Item) -> None:
    """
    Automatically apply markers to a test item based on its location.

    Args:
        item: The pytest test item to apply markers to
    """
    test_path = str(item.fspath)

    # Skip if already has a primary marker
    existing_markers = {mark.name for mark in item.iter_markers()}
    if existing_markers & PRIMARY_MARKERS:
        # Already has a primary marker, only apply domain markers
        pass
    else:
        # Apply primary marker based on path
        if "/unit/" in test_path:
            item.add_marker(pytest.mark.unit)
        elif "/integration/" in test_path:
            item.add_marker(pytest.mark.integration)
        elif "/e2e/" in test_path:
            item.add_marker(pytest.mark.e2e)
        elif "/smoke/" in test_path:
            item.add_marker(pytest.mark.smoke)

    # Apply domain markers
    for domain in DOMAIN_MARKERS:
        if f"/{domain}/" in test_path and domain not in existing_markers:
            item.add_marker(getattr(pytest.mark, domain))


def get_marker_statistics(items: list[pytest.Item]) -> dict[str, int]:
    """
    Get statistics about marker usage across test items.

    Args:
        items: List of pytest test items

    Returns:
        Dictionary mapping marker names to counts
    """
    stats = {}

    for item in items:
        for mark in item.iter_markers():
            stats[mark.name] = stats.get(mark.name, 0) + 1

    return stats


def generate_marker_report(items: list[pytest.Item]) -> str:
    """
    Generate a report about marker usage and validation issues.

    Args:
        items: List of pytest test items

    Returns:
        Formatted report string
    """
    validator = MarkerValidator()
    all_errors = []
    all_warnings = []

    # Validate all items
    for item in items:
        errors, warnings = validator.validate_item(item)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    # Get statistics
    stats = get_marker_statistics(items)

    # Build report
    lines = ["=" * 80]
    lines.append("MARKER VALIDATION REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Statistics
    lines.append("Marker Usage Statistics:")
    lines.append("-" * 40)
    for marker, count in sorted(stats.items()):
        lines.append(f"  {marker}: {count} tests")
    lines.append("")

    # Errors
    if all_errors:
        lines.append(f"Validation Errors ({len(all_errors)}):")
        lines.append("-" * 40)
        for error in all_errors:
            lines.append(f"  ERROR: {error}")
        lines.append("")

    # Warnings
    if all_warnings:
        lines.append(f"Validation Warnings ({len(all_warnings)}):")
        lines.append("-" * 40)
        for warning in all_warnings:
            lines.append(f"  WARNING: {warning}")
        lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append("-" * 40)
    lines.append(f"  Total tests: {len(items)}")
    lines.append(f"  Validation errors: {len(all_errors)}")
    lines.append(f"  Validation warnings: {len(all_warnings)}")

    if not all_errors and not all_warnings:
        lines.append("  ✓ All tests have valid markers!")

    lines.append("=" * 80)

    return "\n".join(lines)
