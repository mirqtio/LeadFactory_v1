#!/usr/bin/env python3
"""
Find xpassed tests by running each domain separately.
"""
import re
import subprocess
import sys
from pathlib import Path


def run_tests_for_domain(domain_path):
    """Run tests for a specific domain and extract xpassed tests."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(domain_path),
        "-v",
        "-rX",  # Show xpassed
        "--tb=no",
        "--no-header",
        "-x",  # Stop on first failure
        "-m",
        "not slow and not integration",  # Skip slow tests
        "--timeout=60",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr

        # Extract xpassed test info
        xpassed_tests = []
        for line in output.split("\n"):
            if "XPASS" in line:
                # Extract full test path
                match = re.search(r"(\S+::\S+)\s+XPASS", line)
                if match:
                    xpassed_tests.append(match.group(1))

        # Also check summary
        match = re.search(r"(\d+) xpassed", output)
        xpass_count = int(match.group(1)) if match else 0

        return xpassed_tests, xpass_count
    except subprocess.TimeoutExpired:
        return [], 0
    except Exception as e:
        print(f"Error running tests for {domain_path}: {e}")
        return [], 0


def main():
    """Main function."""
    total_xpassed = 0
    all_xpassed_tests = []

    # Test directories to check
    test_dirs = [
        Path("tests/unit"),
        Path("tests/smoke"),
        Path("tests/integration"),
        Path("tests/performance"),
    ]

    print("Searching for xpassed tests by domain...")
    print("=" * 80)

    for test_dir in test_dirs:
        if not test_dir.exists():
            continue

        print(f"\n{test_dir}:")

        # Run tests for each subdirectory
        subdirs = [d for d in test_dir.iterdir() if d.is_dir() and not d.name.startswith("__")]

        if not subdirs:
            # Run tests for the directory itself
            xpassed_tests, count = run_tests_for_domain(test_dir)
            if count > 0:
                print(f"  Found {count} xpassed tests")
                all_xpassed_tests.extend(xpassed_tests)
                total_xpassed += count
        else:
            for subdir in sorted(subdirs):
                xpassed_tests, count = run_tests_for_domain(subdir)
                if count > 0:
                    print(f"  {subdir.name}: {count} xpassed tests")
                    all_xpassed_tests.extend(xpassed_tests)
                    total_xpassed += count

    # Also check files in root test directories
    for test_dir in test_dirs:
        if test_dir.exists():
            test_files = list(test_dir.glob("test_*.py"))
            if test_files:
                for test_file in test_files:
                    xpassed_tests, count = run_tests_for_domain(test_file)
                    if count > 0:
                        print(f"  {test_file.name}: {count} xpassed tests")
                        all_xpassed_tests.extend(xpassed_tests)
                        total_xpassed += count

    print("\n" + "=" * 80)
    print(f"Total xpassed tests found: {total_xpassed}")

    if all_xpassed_tests:
        print("\nXpassed tests by file:")
        by_file = {}
        for test in all_xpassed_tests:
            file_path = test.split("::")[0]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(test)

        for file_path, tests in sorted(by_file.items()):
            print(f"\n{file_path} ({len(tests)} tests):")
            for test in tests:
                test_name = "::".join(test.split("::")[1:])
                print(f"  - {test_name}")


if __name__ == "__main__":
    main()
