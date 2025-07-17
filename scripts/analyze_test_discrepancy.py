#!/usr/bin/env python3
"""Analyze test collection discrepancy between AST parsing and pytest."""

import ast
import json
import os
import subprocess
from collections import defaultdict
from pathlib import Path


def count_test_functions_in_file(filepath):
    """Count test functions in a single file using AST."""
    try:
        with open(filepath, "r") as f:
            content = f.read()

        tree = ast.parse(content)
        test_functions = []

        for node in ast.walk(tree):
            # Count test functions at module level
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_functions.append(("function", node.name))
            # Count test methods in classes
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        test_functions.append(("method", f"{node.name}::{item.name}"))

        return test_functions
    except Exception as e:
        return []


def get_pytest_collected_tests():
    """Get tests actually collected by pytest."""
    try:
        # Run pytest --collect-only in JSON format
        result = subprocess.run(
            ["pytest", "--collect-only", "-q", "--json-report", "-", "--json-report-summary=no"],
            capture_output=True,
            text=True,
        )

        # Parse JSON output
        json_data = json.loads(result.stdout)
        collected_tests = set()

        for test in json_data.get("tests", []):
            collected_tests.add(test["nodeid"])

        return collected_tests
    except Exception as e:
        print(f"Error getting pytest collection: {e}")
        # Fallback to simple collection
        result = subprocess.run(["pytest", "--collect-only", "-q"], capture_output=True, text=True)

        collected_tests = set()
        for line in result.stdout.splitlines():
            if "::" in line and not line.startswith(" "):
                collected_tests.add(line.strip())

        return collected_tests


def main():
    """Analyze test discrepancy."""
    # Get all test files
    test_files = []
    for root, dirs, files in os.walk("tests"):
        # Skip __pycache__
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                test_files.append(os.path.join(root, file))

    # Also check archived and other directories
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in [".venv", "venv", "__pycache__", ".git", "tests"]]

        if "venv" in root or ".venv" in root:
            continue

        for file in files:
            if file.startswith("test_") and file.endswith(".py"):
                filepath = os.path.join(root, file)
                if filepath not in test_files:
                    test_files.append(filepath)

    # Count tests using AST
    ast_tests = defaultdict(list)
    total_ast_tests = 0

    for test_file in sorted(test_files):
        tests = count_test_functions_in_file(test_file)
        if tests:
            ast_tests[test_file] = tests
            total_ast_tests += len(tests)

    # Get pytest collected tests
    print("Getting pytest collection (this may take a moment)...")
    pytest_tests = get_pytest_collected_tests()

    # Analyze discrepancies
    print(f"\n{'='*80}")
    print("TEST COLLECTION ANALYSIS")
    print(f"{'='*80}")
    print(f"Total test files found: {len(test_files)}")
    print(f"Total tests found by AST: {total_ast_tests}")
    print(f"Total tests collected by pytest: {len(pytest_tests)}")
    print(f"Discrepancy: {total_ast_tests - len(pytest_tests)}")

    # Find tests in AST but not in pytest
    print(f"\n{'='*80}")
    print("TESTS FOUND BY AST BUT NOT COLLECTED BY PYTEST")
    print(f"{'='*80}")

    uncollected_count = 0
    for filepath, tests in ast_tests.items():
        file_has_uncollected = False
        for test_type, test_name in tests:
            # Check if this test is in pytest collection
            found = False
            for pytest_test in pytest_tests:
                if test_name in pytest_test and filepath in pytest_test:
                    found = True
                    break

            if not found:
                if not file_has_uncollected:
                    print(f"\n{filepath}:")
                    file_has_uncollected = True
                print(f"  - {test_type}: {test_name}")
                uncollected_count += 1

    print(f"\nTotal uncollected tests: {uncollected_count}")

    # Check pytest.ini ignores
    print(f"\n{'='*80}")
    print("PYTEST.INI IGNORED FILES")
    print(f"{'='*80}")

    ignored_files = [
        "tests/e2e/",
        "tests/unit/d10_analytics/test_d10_models.py",
        "tests/unit/d10_analytics/test_warehouse.py",
        "tests/unit/d11_orchestration/test_bucket_flow.py",
        "tests/unit/d11_orchestration/test_pipeline.py",
        "tests/unit/d9_delivery/test_delivery_manager.py",
        "tests/unit/d9_delivery/test_sendgrid.py",
    ]

    ignored_test_count = 0
    for filepath, tests in ast_tests.items():
        for ignored in ignored_files:
            if ignored in filepath:
                print(f"\n{filepath}: {len(tests)} tests")
                ignored_test_count += len(tests)
                break

    print(f"\nTotal tests in ignored files: {ignored_test_count}")

    # Files outside tests directory
    print(f"\n{'='*80}")
    print("TEST FILES OUTSIDE 'tests' DIRECTORY")
    print(f"{'='*80}")

    outside_test_count = 0
    for filepath, tests in ast_tests.items():
        if not filepath.startswith("tests/"):
            print(f"\n{filepath}: {len(tests)} tests")
            outside_test_count += len(tests)

    print(f"\nTotal tests outside 'tests' directory: {outside_test_count}")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"AST found: {total_ast_tests}")
    print(f"Ignored by pytest.ini: {ignored_test_count}")
    print(f"Outside tests directory: {outside_test_count}")
    print(f"Expected after exclusions: {total_ast_tests - ignored_test_count - outside_test_count}")
    print(f"Actually collected by pytest: {len(pytest_tests)}")
    print(f"Still unexplained: {total_ast_tests - ignored_test_count - outside_test_count - len(pytest_tests)}")


if __name__ == "__main__":
    main()

