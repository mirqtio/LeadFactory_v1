#!/usr/bin/env python3
"""Count test functions in all test files."""

import ast
import os
from pathlib import Path


def count_test_functions_in_file(filepath):
    """Count test functions in a single file."""
    try:
        with open(filepath, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        test_count = 0

        for node in ast.walk(tree):
            # Count test functions at module level
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_count += 1
            # Count test methods in classes
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        test_count += 1

        return test_count
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return 0


def main():
    """Count all test functions in the repository."""
    # Find all test files
    test_files = []
    for root, dirs, files in os.walk("."):
        # Skip venv and pycache
        dirs[:] = [d for d in dirs if d not in [".venv", "venv", "__pycache__", ".git"]]

        # Also skip if we're already in a venv directory
        if "venv" in root or ".venv" in root:
            continue

        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    # Count tests in each file
    total_tests = 0
    file_details = []

    for test_file in sorted(test_files):
        count = count_test_functions_in_file(test_file)
        total_tests += count
        if count > 0:
            file_details.append((test_file, count))

    # Print summary
    print(f"Total test files found: {len(test_files)}")
    print(f"Total test functions found: {total_tests}")
    print(f"\nPytest reports: 2,989 tests")
    print(f"Difference: {2989 - total_tests}")

    print("\n" + "=" * 80)
    print("Files with test counts:")
    print("=" * 80)

    for filepath, count in sorted(file_details, key=lambda x: x[1], reverse=True):
        print(f"{count:4d} tests in {filepath}")

    # Check for files with no tests
    print("\n" + "=" * 80)
    print("Files with NO tests:")
    print("=" * 80)

    for test_file in sorted(test_files):
        count = count_test_functions_in_file(test_file)
        if count == 0:
            print(f"  {test_file}")


if __name__ == "__main__":
    main()
