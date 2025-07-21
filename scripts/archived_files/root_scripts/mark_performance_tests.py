#!/usr/bin/env python3
"""
Automatically mark tests with performance-related markers.
Creates systematic test categorization for CI optimization.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set


class TestMarker:
    """Analyze and mark tests based on performance characteristics."""

    def __init__(self):
        self.ultra_fast_tests = {
            "tests/unit/d5_scoring/test_omega.py",
            "tests/unit/d5_scoring/test_impact_calculator.py",
            "tests/unit/d8_personalization/test_templates.py",
            "tests/unit/design/test_token_extraction.py",
            "tests/unit/design/test_validation_module.py",
            "tests/unit/d5_scoring/test_engine.py",
            "tests/unit/d5_scoring/test_tiers.py",
            "tests/unit/design/test_token_usage.py",
        }

        self.infrastructure_heavy_patterns = {
            "stub_server",
            "database",
            "postgres",
            "redis",
            "docker",
            "external_api",
            "http_client",
            "webhook",
            "integration",
        }

        self.io_heavy_patterns = {
            "file",
            "read",
            "write",
            "download",
            "upload",
            "screenshot",
            "image",
            "pdf",
            "csv",
            "json",
            "yaml",
        }

    def analyze_test_file(self, file_path: Path) -> dict[str, list[str]]:
        """Analyze test file for performance characteristics."""
        try:
            with open(file_path) as f:
                content = f.read()
        except Exception:
            return {"markers": [], "reasons": []}

        markers = []
        reasons = []

        # Check if it's already marked as ultra-fast
        if str(file_path) in self.ultra_fast_tests:
            markers.append("ultrafast")
            reasons.append("Profiled as ultra-fast test")

        # Check for infrastructure dependencies
        content_lower = content.lower()
        for pattern in self.infrastructure_heavy_patterns:
            if pattern in content_lower:
                markers.append("infrastructure_heavy")
                reasons.append(f"Uses infrastructure: {pattern}")
                break

        # Check for I/O operations
        for pattern in self.io_heavy_patterns:
            if pattern in content_lower:
                markers.append("io_heavy")
                reasons.append(f"Performs I/O: {pattern}")
                break

        # Check for async operations
        if "async" in content_lower or "await" in content_lower:
            markers.append("async_heavy")
            reasons.append("Contains async operations")

        # Check for external API calls
        if any(term in content_lower for term in ["requests.", "httpx.", "aiohttp."]):
            markers.append("api_heavy")
            reasons.append("Makes external API calls")

        # Check for database operations
        if any(term in content_lower for term in ["session.", "query", "select", "insert", "update"]):
            markers.append("database_heavy")
            reasons.append("Performs database operations")

        # Default to fast if no heavy patterns found
        if not any(m.endswith("_heavy") for m in markers):
            markers.append("fast")
            reasons.append("No heavy operations detected")

        return {"markers": markers, "reasons": reasons}

    def generate_marker_recommendations(self) -> dict[str, list[str]]:
        """Generate test marker recommendations for all test files."""
        test_files = list(Path("tests").rglob("test_*.py"))
        recommendations = {}

        for test_file in test_files:
            analysis = self.analyze_test_file(test_file)
            recommendations[str(test_file)] = analysis

        return recommendations

    def create_performance_test_groups(self) -> dict[str, list[str]]:
        """Create optimized test groups for different CI scenarios."""
        recommendations = self.generate_marker_recommendations()

        groups = {
            "ultra_fast_ci": [],  # <2 minutes - immediate feedback
            "fast_ci": [],  # <5 minutes - quick validation
            "standard_ci": [],  # <15 minutes - normal workflow
            "comprehensive_ci": [],  # <30 minutes - full validation
            "excluded_from_fast": [],  # Too slow for fast CI
        }

        for test_path, analysis in recommendations.items():
            markers = analysis["markers"]

            if "ultrafast" in markers:
                groups["ultra_fast_ci"].append(test_path)
            elif "fast" in markers and not any(m.endswith("_heavy") for m in markers):
                groups["fast_ci"].append(test_path)
            elif "infrastructure_heavy" in markers or "database_heavy" in markers:
                groups["comprehensive_ci"].append(test_path)
                groups["excluded_from_fast"].append(test_path)
            else:
                groups["standard_ci"].append(test_path)

        return groups

    def generate_pytest_marker_config(self) -> str:
        """Generate pytest marker configuration."""
        return """
# Performance-based test markers for CI optimization
markers =
    # Performance markers
    ultrafast: Ultra-fast tests (<30s total) for immediate feedback
    fast: Fast tests (<5min total) for quick validation  
    slow: Slow tests (>5min) requiring patient CI
    
    # Resource markers
    infrastructure_heavy: Tests requiring infrastructure (DB, services)
    io_heavy: Tests performing significant I/O operations
    api_heavy: Tests making external API calls
    database_heavy: Tests requiring database operations
    async_heavy: Tests with significant async operations
    
    # CI optimization markers
    ultra_fast_ci: Include in ultra-fast CI pipeline (<2min)
    fast_ci: Include in fast CI pipeline (<5min)  
    standard_ci: Include in standard CI pipeline (<15min)
    comprehensive_ci: Include in comprehensive CI pipeline (<30min)
    excluded_from_fast: Exclude from fast CI pipelines
"""


def main():
    """Generate performance-based test marking strategy."""
    marker = TestMarker()

    print("🔍 Analyzing test suite for performance characteristics...")

    # Generate recommendations
    recommendations = marker.generate_marker_recommendations()

    # Create performance groups
    groups = marker.create_performance_test_groups()

    # Output results
    print("\n📊 Test Performance Analysis")
    print("=" * 60)

    for group_name, tests in groups.items():
        print(f"\n{group_name.upper()}: {len(tests)} tests")
        if group_name == "ultra_fast_ci":
            for test in tests[:5]:  # Show first 5 ultra-fast tests
                print(f"  ✅ {test}")
        elif group_name == "excluded_from_fast":
            for test in tests[:3]:  # Show first 3 excluded tests
                print(f"  ❌ {test}")

    # Generate pytest config
    pytest_config = marker.generate_pytest_marker_config()

    print("\n📝 Pytest Marker Configuration:")
    print(pytest_config)

    # Save analysis
    import json

    with open("test_performance_analysis.json", "w") as f:
        json.dump({"recommendations": recommendations, "groups": groups, "pytest_config": pytest_config}, f, indent=2)

    print("\n💾 Analysis saved to: test_performance_analysis.json")

    # Output CI configuration recommendations
    print("\n🚀 CI Pipeline Recommendations:")
    print(f"Ultra-Fast CI: {len(groups['ultra_fast_ci'])} tests (~2-3 minutes)")
    print(f"Fast CI: {len(groups['fast_ci'])} tests (~5-8 minutes)")
    print(f"Standard CI: {len(groups['standard_ci'])} tests (~15-20 minutes)")
    print(f"Comprehensive CI: {len(groups['comprehensive_ci'])} tests (~30+ minutes)")


if __name__ == "__main__":
    main()
