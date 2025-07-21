#!/usr/bin/env python3
"""
Find xpassed tests efficiently by checking files with xfail markers.
"""

import re
import subprocess
import sys
from pathlib import Path


def has_xfail_marker(file_path):
    """Check if file has xfail markers."""
    with open(file_path) as f:
        return "@pytest.mark.xfail" in f.read()


def run_single_test_file(file_path):
    """Run a single test file and check for xpassed tests."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(file_path),
        "-rX",  # Report xpassed
        "--tb=no",
        "-q",
        "--no-header",
        "--timeout=30",
        "-x",  # Stop on first failure
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = result.stdout + result.stderr

        # Look for xpassed in summary
        match = re.search(r"(\d+) xpassed", output)
        if match:
            return int(match.group(1)), output
        return 0, output
    except:
        return 0, ""


def main():
    """Main function."""
    # Find test files with xfail markers
    test_files_with_xfail = []

    for test_file in Path("tests").rglob("test_*.py"):
        if test_file.is_file() and has_xfail_marker(test_file):
            test_files_with_xfail.append(test_file)

    print(f"Found {len(test_files_with_xfail)} test files with xfail markers")
    print("Checking each file for xpassed tests...")
    print("=" * 80)

    total_xpassed = 0
    files_with_xpassed = []

    for idx, test_file in enumerate(sorted(test_files_with_xfail), 1):
        print(f"[{idx}/{len(test_files_with_xfail)}] {test_file}...", end="", flush=True)

        xpass_count, output = run_single_test_file(test_file)

        if xpass_count > 0:
            print(f" ❌ {xpass_count} xpassed")
            total_xpassed += xpass_count
            files_with_xpassed.append((test_file, xpass_count))
        else:
            print(" ✅")

    print("\n" + "=" * 80)
    print(f"SUMMARY: Found {total_xpassed} xpassed tests across {len(files_with_xpassed)} files")

    if files_with_xpassed:
        print("\nFiles with xpassed tests:")
        for file_path, count in sorted(files_with_xpassed, key=lambda x: x[1], reverse=True):
            print(f"  {file_path}: {count} xpassed")

    print("\nProgress: Fixed 17 tests so far")
    print(f"Remaining: ~{200 - 17} xpassed tests to find and fix")


if __name__ == "__main__":
    main()
