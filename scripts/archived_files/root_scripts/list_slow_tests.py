#!/usr/bin/env python3
"""
List all tests marked with @pytest.mark.slow in the codebase.
"""

import re
from pathlib import Path
from typing import List, Tuple


def find_slow_tests(test_dir: Path) -> list[tuple[str, str, int]]:
    """Find all tests marked with @pytest.mark.slow."""
    slow_tests = []

    for test_file in test_dir.rglob("test_*.py"):
        with open(test_file) as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if "@pytest.mark.slow" in line:
                # Look for the test function in the next few lines
                for j in range(i, min(i + 5, len(lines))):
                    match = re.match(r"^\s*(async\s+)?def\s+(test_\w+)", lines[j])
                    if match:
                        test_name = match.group(2)
                        slow_tests.append((str(test_file), test_name, i + 1))
                        break

    return slow_tests


def main():
    """Main entry point."""
    test_dir = Path(__file__).parent.parent / "tests"

    # Find all slow tests
    slow_tests = find_slow_tests(test_dir)

    print(f"{'=' * 80}")
    print("TESTS MARKED AS SLOW")
    print(f"{'=' * 80}\n")

    if not slow_tests:
        print("No tests marked with @pytest.mark.slow found.")
        return 0

    print(f"Total slow tests: {len(slow_tests)}\n")

    # Group by file
    by_file = {}
    for file_path, test_name, line_num in slow_tests:
        if file_path not in by_file:
            by_file[file_path] = []
        by_file[file_path].append((test_name, line_num))

    # Print grouped by file
    for file_path in sorted(by_file.keys()):
        rel_path = Path(file_path).relative_to(test_dir.parent)
        print(f"\n{rel_path}:")
        print("-" * len(str(rel_path)))

        for test_name, line_num in sorted(by_file[file_path], key=lambda x: x[1]):
            print(f"  Line {line_num:4}: {test_name}")

    # Print summary
    print(f"\n{'=' * 80}")
    print("SUMMARY")
    print(f"{'=' * 80}")
    print(f"Total files with slow tests: {len(by_file)}")
    print(f"Total slow tests marked: {len(slow_tests)}")
    print("\nTo run tests excluding slow ones:")
    print('  pytest -m "not slow"')
    print("\nTo run only slow tests:")
    print("  pytest -m slow")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
