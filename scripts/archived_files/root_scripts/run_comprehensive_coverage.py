#!/usr/bin/env python3
"""
Script to run comprehensive coverage tests.
Part of PRP-014: Strategic CI Test Re-enablement

This script runs the slow comprehensive test suite to achieve maximum coverage.
"""
import subprocess
import sys
import time
from pathlib import Path


def run_comprehensive_coverage():
    """Run comprehensive test suite for maximum coverage"""
    print("=" * 80)
    print("PRP-014: Running Comprehensive Coverage Test Suite")
    print("=" * 80)
    print("\nThis will run ALL tests including slow ones to maximize coverage.")
    print("Expected runtime: 10-20 minutes\n")

    start_time = time.time()

    # Ensure we're in the project root
    project_root = Path(__file__).parent.parent

    # Run the comprehensive test
    cmd = [
        "pytest",
        "tests/comprehensive/test_full_coverage.py",
        "-v",
        "-s",
        "--cov=.",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-report=xml",
        "--cov-config=.coveragerc",
        "--tb=short",
        "--no-header",
    ]

    print(f"Running command: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True)

    # Print output
    print(result.stdout)
    if result.stderr:
        print("\nErrors:")
        print(result.stderr)

    # Calculate runtime
    runtime = time.time() - start_time
    minutes = int(runtime // 60)
    seconds = int(runtime % 60)

    print("\n" + "=" * 80)
    print(f"Total runtime: {minutes}m {seconds}s")

    # Parse coverage from output
    coverage_line = None
    for line in result.stdout.split("\n"):
        if "TOTAL" in line and "%" in line:
            coverage_line = line
            break

    if coverage_line:
        # Extract percentage
        parts = coverage_line.split()
        for part in parts:
            if part.endswith("%"):
                coverage = part
                print(f"Total coverage achieved: {coverage}")
                break

    print("=" * 80)

    # Also run regular test suite to compare
    print("\nRunning regular test suite for comparison...")

    regular_cmd = [
        "pytest",
        "tests/unit",
        "tests/integration",
        "tests/smoke",
        "-m",
        "not slow and not flaky and not external",
        "--cov=.",
        "--cov-report=term",
        "--tb=no",
        "-q",
    ]

    regular_result = subprocess.run(regular_cmd, cwd=project_root, capture_output=True, text=True)

    # Extract regular coverage
    for line in regular_result.stdout.split("\n"):
        if "TOTAL" in line and "%" in line:
            parts = line.split()
            for part in parts:
                if part.endswith("%"):
                    print(f"Regular test suite coverage: {part}")
                    break

    print("\nCoverage reports:")
    print("- HTML: htmlcov/index.html")
    print("- XML: coverage.xml")
    print("=" * 80)

    return result.returncode


if __name__ == "__main__":
    sys.exit(run_comprehensive_coverage())
