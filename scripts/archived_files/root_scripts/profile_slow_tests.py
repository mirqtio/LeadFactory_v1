#!/usr/bin/env python3
"""
Profile test execution times and identify slow tests.

This script runs pytest with timing information, identifies tests that take
more than 1 second, and generates commands to add @pytest.mark.slow markers.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


class TestProfiler:
    """Profile test execution times and identify slow tests."""

    def __init__(self, threshold: float = 1.0):
        self.threshold = threshold
        self.slow_tests: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def run_tests_with_timing(self) -> str:
        """Run pytest with timing information."""
        print("Running pytest to collect timing information...")
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "--durations=0",  # Show all test durations
            "--tb=short",  # Short traceback format
            "-v",  # Verbose output
            "--no-header",  # Skip pytest header
            "-q",  # Less verbose output
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)
            return result.stdout + result.stderr
        except Exception as e:
            print(f"Error running pytest: {e}")
            return ""

    def parse_test_durations(self, output: str) -> Dict[str, float]:
        """Parse test durations from pytest output."""
        durations = {}

        # Pattern to match duration lines
        # Example: "0.52s call     tests/unit/test_example.py::TestClass::test_method"
        duration_pattern = r"(\d+\.\d+)s\s+call\s+(.+?)(?:\[|$)"

        for match in re.finditer(duration_pattern, output):
            duration = float(match.group(1))
            test_path = match.group(2).strip()
            durations[test_path] = duration

        return durations

    def categorize_slow_tests(self, durations: Dict[str, float]) -> None:
        """Categorize tests by module and identify slow ones."""
        for test_path, duration in durations.items():
            if duration >= self.threshold:
                # Extract module path from test path
                if "::" in test_path:
                    module_path = test_path.split("::")[0]
                else:
                    module_path = test_path

                self.slow_tests[module_path].append((test_path, duration))

    def generate_report(self) -> str:
        """Generate a report of slow tests."""
        report = []
        report.append(f"\n{'='*80}")
        report.append(f"SLOW TEST REPORT (threshold: {self.threshold}s)")
        report.append(f"{'='*80}\n")

        total_slow_tests = sum(len(tests) for tests in self.slow_tests.values())
        report.append(f"Total slow tests found: {total_slow_tests}")
        report.append(f"Affected modules: {len(self.slow_tests)}\n")

        # Sort modules by total time spent in slow tests
        module_times = {}
        for module, tests in self.slow_tests.items():
            module_times[module] = sum(duration for _, duration in tests)

        sorted_modules = sorted(module_times.items(), key=lambda x: x[1], reverse=True)

        for module, total_time in sorted_modules:
            report.append(f"\n{module} (total: {total_time:.2f}s)")
            report.append("-" * len(module))

            # Sort tests in module by duration
            tests = sorted(self.slow_tests[module], key=lambda x: x[1], reverse=True)
            for test_path, duration in tests:
                test_name = test_path.split("::")[-1] if "::" in test_path else test_path
                report.append(f"  {duration:6.2f}s  {test_name}")

        return "\n".join(report)

    def generate_marker_commands(self) -> str:
        """Generate commands to add @pytest.mark.slow markers."""
        commands = []
        commands.append(f"\n{'='*80}")
        commands.append("COMMANDS TO ADD SLOW MARKERS")
        commands.append(f"{'='*80}\n")

        # Group tests by file
        file_tests = defaultdict(list)
        for tests in self.slow_tests.values():
            for test_path, duration in tests:
                if "::" in test_path:
                    file_path = test_path.split("::")[0]
                    test_identifier = "::".join(test_path.split("::")[1:])
                    file_tests[file_path].append((test_identifier, duration))

        commands.append("# Manual approach - add @pytest.mark.slow to each test:\n")

        for file_path in sorted(file_tests.keys()):
            commands.append(f"\n# File: {file_path}")
            tests = sorted(file_tests[file_path], key=lambda x: x[1], reverse=True)
            for test_id, duration in tests:
                commands.append(f"# {test_id} ({duration:.2f}s)")
            commands.append(f"# Add @pytest.mark.slow decorator to the above tests")

        return "\n".join(commands)

    def save_results(self, durations: Dict[str, float]) -> None:
        """Save detailed results to a JSON file."""
        results = {"threshold": self.threshold, "total_tests": len(durations), "slow_tests": []}

        for test_path, duration in sorted(durations.items(), key=lambda x: x[1], reverse=True):
            if duration >= self.threshold:
                results["slow_tests"].append(
                    {
                        "test": test_path,
                        "duration": duration,
                        "file": test_path.split("::")[0] if "::" in test_path else test_path,
                    }
                )

        output_file = Path(__file__).parent / "slow_tests_report.json"
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\nDetailed results saved to: {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Profile test execution times")
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Time threshold in seconds for marking tests as slow (default: 1.0)",
    )
    args = parser.parse_args()

    profiler = TestProfiler(threshold=args.threshold)

    # Run tests and collect timing
    output = profiler.run_tests_with_timing()

    if not output:
        print("Failed to run tests or collect timing information")
        return 1

    # Parse durations
    durations = profiler.parse_test_durations(output)

    if not durations:
        print("No test duration information found in output")
        return 1

    print(f"\nFound timing information for {len(durations)} tests")

    # Categorize slow tests
    profiler.categorize_slow_tests(durations)

    # Generate and print report
    report = profiler.generate_report()
    print(report)

    # Generate marker commands
    commands = profiler.generate_marker_commands()
    print(commands)

    # Save detailed results
    profiler.save_results(durations)

    # Summary
    total_slow = sum(len(tests) for tests in profiler.slow_tests.values())
    if total_slow > 0:
        print(f"\n{'='*80}")
        print(f"SUMMARY: Found {total_slow} tests slower than {args.threshold}s")
        print(f"{'='*80}")
        print("\nNext steps:")
        print("1. Review the slow tests identified above")
        print("2. Add @pytest.mark.slow to each slow test")
        print("3. Update tests/markers.py to include 'slow' in OTHER_MARKERS")
        print("4. Run 'pytest -m \"not slow\"' to exclude slow tests")
    else:
        print(f"\nNo tests found slower than {args.threshold}s")

    return 0


if __name__ == "__main__":
    sys.exit(main())
