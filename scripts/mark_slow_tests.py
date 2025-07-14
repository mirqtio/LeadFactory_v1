#!/usr/bin/env python3
"""
Script to mark slow tests based on pytest duration reports.
Part of PRP-014: Strategic CI Test Re-enablement
"""
import os
import re
import subprocess
import sys

# Threshold for marking tests as slow (in seconds)
SLOW_THRESHOLD = 1.0
CRITICAL_PATTERNS = [
    "test_health",
    "test_database",
    "test_authentication",
    "test_scoring",
    "test_report_generation",
]


def run_pytest_durations():
    """Run pytest to get test durations."""
    print("Running pytest to collect test durations...")
    cmd = ["pytest", "--durations=0", "--tb=no", "-q"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def parse_durations(output):
    """Parse pytest duration output."""
    durations = {}
    in_durations = False

    for line in output.split("\n"):
        if "slowest" in line and "durations" in line:
            in_durations = True
            continue

        if not in_durations:
            continue

        # Parse lines like: "0.05s call tests/unit/test_foo.py::TestClass::test_method"
        match = re.match(r"([\d.]+)s\s+\w+\s+(tests/.*)", line)
        if match:
            duration = float(match.group(1))
            test_path = match.group(2)
            durations[test_path] = duration

        # Stop at summary info
        if line.startswith("===") and "short test summary" in line:
            break

    return durations


def is_critical_test(test_path):
    """Check if test matches critical patterns."""
    for pattern in CRITICAL_PATTERNS:
        if pattern in test_path.lower():
            return True
    return False


def mark_test_in_file(file_path, test_name, marker):
    """Add pytest marker to a test in a file."""
    with open(file_path, "r") as f:
        content = f.read()

    # Find the test function/method
    test_pattern = rf"(\s*)(def\s+{test_name}\s*\([^)]*\)\s*:)"

    # Check if already marked
    if f"@pytest.mark.{marker}" in content:
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if test_name in line and "def" in line:
                # Check previous lines for the marker
                for j in range(max(0, i - 5), i):
                    if f"@pytest.mark.{marker}" in lines[j]:
                        print(f"  Already marked: {test_name}")
                        return False

    # Add marker
    replacement = rf"\1@pytest.mark.{marker}\n\1\2"
    new_content = re.sub(test_pattern, replacement, content)

    if new_content != content:
        # Ensure pytest is imported
        if "import pytest" not in new_content:
            new_content = "import pytest\n" + new_content

        with open(file_path, "w") as f:
            f.write(new_content)
        print(f"  Marked {test_name} as @pytest.mark.{marker}")
        return True

    return False


def process_test_durations(durations):
    """Process test durations and mark tests accordingly."""
    stats = {"slow": 0, "critical": 0, "total": len(durations)}

    for test_path, duration in sorted(durations.items(), key=lambda x: x[1], reverse=True):
        # Parse test location
        match = re.match(r"(.*\.py)::(.*)::(.*)$", test_path)
        if not match:
            continue

        file_path = match.group(1)
        class_name = match.group(2)
        test_name = match.group(3)

        if not os.path.exists(file_path):
            continue

        print(f"\nProcessing {test_path} ({duration:.2f}s)")

        # Mark slow tests
        if duration >= SLOW_THRESHOLD:
            if mark_test_in_file(file_path, test_name, "slow"):
                stats["slow"] += 1

        # Mark critical tests (even if slow)
        if is_critical_test(test_path):
            if mark_test_in_file(file_path, test_name, "critical"):
                stats["critical"] += 1

    return stats


def main():
    """Main function."""
    print("=== Test Duration Analysis for PRP-014 ===\n")

    # Get test durations
    output = run_pytest_durations()
    durations = parse_durations(output)

    if not durations:
        print("No test durations found!")
        sys.exit(1)

    print(f"Found {len(durations)} tests with duration data")

    # Show slowest tests
    print("\nSlowest 10 tests:")
    for test_path, duration in sorted(durations.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {duration:6.2f}s - {test_path}")

    # Process and mark tests
    print("\nMarking tests...")
    stats = process_test_durations(durations)

    print("\n=== Summary ===")
    print(f"Total tests analyzed: {stats['total']}")
    print(f"Tests marked as @pytest.mark.slow: {stats['slow']}")
    print(f"Tests marked as @pytest.mark.critical: {stats['critical']}")

    print("\nTo run only fast tests: pytest -m 'not slow'")
    print("To run only critical tests: pytest -m critical")
    print("To run critical tests excluding slow ones: pytest -m 'critical and not slow'")


if __name__ == "__main__":
    main()
