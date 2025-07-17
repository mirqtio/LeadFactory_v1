#!/usr/bin/env python3
"""
Script to find all xpassed tests in the test suite.
"""
import re
import subprocess
import sys
from pathlib import Path


def find_xpassed_tests():
    """Run pytest to identify all xpassed tests."""
    print("Running pytest to find xpassed tests...")

    # Run pytest with minimal output to get xpassed tests
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-rX",  # Show extra test summary for xpassed
        "--tb=no",  # No traceback
        "-q",  # Quiet mode
        "--no-header",  # No header
        "-m",
        "not slow",  # Skip slow tests
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        output = result.stdout + result.stderr

        # Parse xpassed tests from output
        xpassed_tests = []
        for line in output.split("\n"):
            if "XPASS" in line:
                # Extract test path
                match = re.match(r"XPASS\s+(\S+)", line)
                if match:
                    xpassed_tests.append(match.group(1))

        return xpassed_tests, output

    except subprocess.TimeoutExpired:
        print("Test run timed out after 5 minutes")
        return [], ""


def analyze_xpassed_by_file(xpassed_tests):
    """Group xpassed tests by file."""
    by_file = {}

    for test in xpassed_tests:
        # Extract file path from test name
        parts = test.split("::")
        if parts:
            file_path = parts[0]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(test)

    return by_file


def main():
    """Main function."""
    xpassed_tests, output = find_xpassed_tests()

    if not xpassed_tests:
        # Try to extract count from summary
        match = re.search(r"(\d+)\s+xpassed", output)
        if match:
            count = int(match.group(1))
            print(f"\nFound {count} xpassed tests in summary but couldn't extract individual tests.")
            print("This might be because they're in integration or slow tests.")
        else:
            print("\nNo xpassed tests found.")
        return

    print(f"\nFound {len(xpassed_tests)} xpassed tests:")

    # Group by file
    by_file = analyze_xpassed_by_file(xpassed_tests)

    # Sort by number of xpassed tests per file
    sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)

    print("\nXpassed tests by file:")
    print("=" * 80)

    for file_path, tests in sorted_files:
        print(f"\n{file_path} ({len(tests)} xpassed):")
        for test in tests:
            # Extract just the test name
            test_name = test.split("::")[-1] if "::" in test else test
            print(f"  - {test_name}")

    print("\n" + "=" * 80)
    print(f"Total xpassed tests: {len(xpassed_tests)}")

    # Save to file for reference
    with open("xpassed_tests_report.txt", "w") as f:
        f.write(f"Xpassed Tests Report\n")
        f.write(f"{'=' * 80}\n\n")
        f.write(f"Total xpassed tests: {len(xpassed_tests)}\n\n")

        for file_path, tests in sorted_files:
            f.write(f"\n{file_path} ({len(tests)} xpassed):\n")
            for test in tests:
                f.write(f"  {test}\n")

    print("\nReport saved to xpassed_tests_report.txt")


if __name__ == "__main__":
    main()
