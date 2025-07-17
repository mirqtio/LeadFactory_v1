#!/usr/bin/env python3
"""
List all tests with xfail markers using AST parsing.
"""
import ast
import re
from pathlib import Path


def find_xfail_tests_in_file(file_path):
    """Find all tests with xfail markers in a file."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Check for module-level xfail
        module_xfail = False
        if "pytestmark" in content and "@pytest.mark.xfail" in content:
            # Check if it's a module-level xfail
            for line in content.split("\n"):
                if "pytestmark" in line and "xfail" in line:
                    module_xfail = True
                    break

        # Parse AST to find test functions
        tree = ast.parse(content)
        xfail_tests = []

        # Helper to check if a function has xfail decorator
        def has_xfail_decorator(decorators):
            for decorator in decorators:
                if isinstance(decorator, ast.Attribute):
                    if (
                        hasattr(decorator.value, "attr")
                        and decorator.value.attr == "mark"
                        and decorator.attr == "xfail"
                    ):
                        return True
                elif isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Attribute):
                        if (
                            hasattr(decorator.func.value, "attr")
                            and decorator.func.value.attr == "mark"
                            and decorator.func.attr == "xfail"
                        ):
                            return True
            return False

        # Find all test functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                if module_xfail or has_xfail_decorator(node.decorator_list):
                    xfail_tests.append(node.name)
            elif isinstance(node, ast.ClassDef):
                # Check test methods in classes
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                        if module_xfail or has_xfail_decorator(item.decorator_list):
                            xfail_tests.append(f"{node.name}::{item.name}")

        return xfail_tests, module_xfail

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return [], False


def main():
    """Main function."""
    all_xfail_tests = {}
    module_xfail_files = []

    # Find all test files
    test_files = []
    for pattern in ["test_*.py", "*_test.py"]:
        test_files.extend(Path("tests").rglob(pattern))

    print(f"Found {len(test_files)} test files")
    print("=" * 80)

    # Analyze each file
    total_xfail = 0
    for test_file in sorted(test_files):
        xfail_tests, module_xfail = find_xfail_tests_in_file(test_file)

        if xfail_tests:
            all_xfail_tests[str(test_file)] = xfail_tests
            total_xfail += len(xfail_tests)

            if module_xfail:
                module_xfail_files.append(str(test_file))

    # Print results
    print(f"\nTotal tests with xfail markers: {total_xfail}")
    print(f"Files with module-level xfail: {len(module_xfail_files)}")

    if module_xfail_files:
        print("\nFiles with module-level xfail:")
        for file_path in module_xfail_files:
            print(f"  - {file_path}")

    print("\n" + "=" * 80)
    print("All xfail tests by file:")
    print("=" * 80)

    for file_path, tests in sorted(all_xfail_tests.items()):
        print(f"\n{file_path} ({len(tests)} tests):")
        for test in tests:
            print(f"  - {test}")

    # Save to file for reference
    with open("all_xfail_tests.txt", "w") as f:
        f.write(f"Total xfail tests: {total_xfail}\n")
        f.write("=" * 80 + "\n\n")

        for file_path, tests in sorted(all_xfail_tests.items()):
            f.write(f"{file_path} ({len(tests)} tests):\n")
            for test in tests:
                f.write(f"  - {test}\n")
            f.write("\n")

    print(f"\nResults saved to all_xfail_tests.txt")

    # Group by directory
    print("\n" + "=" * 80)
    print("Summary by directory:")
    print("=" * 80)

    by_dir = {}
    for file_path, tests in all_xfail_tests.items():
        dir_path = str(Path(file_path).parent)
        if dir_path not in by_dir:
            by_dir[dir_path] = 0
        by_dir[dir_path] += len(tests)

    for dir_path, count in sorted(by_dir.items(), key=lambda x: x[1], reverse=True):
        print(f"{dir_path}: {count} xfail tests")


if __name__ == "__main__":
    main()
