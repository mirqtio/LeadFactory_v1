#!/usr/bin/env python3
"""
Simple test profiler that analyzes pytest-json-report output.

This script runs pytest with JSON output to get accurate timing data,
then identifies tests that take more than 1 second.
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def run_tests_with_json_report(test_path: str = "tests") -> Dict:
    """Run pytest with JSON report output."""
    print(f"Running pytest on {test_path} to collect timing information...")

    report_file = Path(__file__).parent / "test_report.json"

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        "--json-report",
        f"--json-report-file={report_file}",
        "-q",
        "--tb=no",
        "--no-header",
        "-x",  # Stop on first failure to speed up
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).parent.parent)

        # Read the JSON report
        if report_file.exists():
            with open(report_file, "r") as f:
                return json.load(f)
        else:
            print("No JSON report file generated")
            return {}

    except Exception as e:
        print(f"Error running pytest: {e}")
        return {}
    finally:
        # Clean up report file
        if report_file.exists():
            report_file.unlink()


def analyze_test_durations(report: Dict, threshold: float = 1.0) -> Dict[str, List[Tuple[str, float]]]:
    """Analyze test durations from JSON report."""
    slow_tests = defaultdict(list)

    if "tests" not in report:
        return slow_tests

    for test in report["tests"]:
        if test.get("call", {}).get("duration", 0) >= threshold:
            duration = test["call"]["duration"]
            nodeid = test["nodeid"]

            # Extract file path
            if "::" in nodeid:
                file_path = nodeid.split("::")[0]
            else:
                file_path = nodeid

            slow_tests[file_path].append((nodeid, duration))

    return slow_tests


def generate_report(slow_tests: Dict[str, List[Tuple[str, float]]], threshold: float) -> str:
    """Generate a report of slow tests."""
    lines = []
    lines.append(f"\n{'='*80}")
    lines.append(f"SLOW TEST REPORT (threshold: {threshold}s)")
    lines.append(f"{'='*80}\n")

    total_slow_tests = sum(len(tests) for tests in slow_tests.values())
    lines.append(f"Total slow tests found: {total_slow_tests}")
    lines.append(f"Affected files: {len(slow_tests)}\n")

    if not slow_tests:
        lines.append("No slow tests found!")
        return "\n".join(lines)

    # Sort files by total time spent in slow tests
    file_times = {}
    for file_path, tests in slow_tests.items():
        file_times[file_path] = sum(duration for _, duration in tests)

    sorted_files = sorted(file_times.items(), key=lambda x: x[1], reverse=True)

    for file_path, total_time in sorted_files:
        lines.append(f"\n{file_path} (total: {total_time:.2f}s)")
        lines.append("-" * len(file_path))

        # Sort tests in file by duration
        tests = sorted(slow_tests[file_path], key=lambda x: x[1], reverse=True)
        for test_nodeid, duration in tests:
            test_name = test_nodeid.split("::")[-1] if "::" in test_nodeid else test_nodeid
            lines.append(f"  {duration:6.2f}s  {test_name}")

    return "\n".join(lines)


def generate_marker_commands(slow_tests: Dict[str, List[Tuple[str, float]]]) -> str:
    """Generate commands to add @pytest.mark.slow markers."""
    lines = []
    lines.append(f"\n{'='*80}")
    lines.append("FILES TO UPDATE WITH @pytest.mark.slow")
    lines.append(f"{'='*80}\n")

    for file_path in sorted(slow_tests.keys()):
        lines.append(f"\n# File: {file_path}")
        lines.append("# Tests to mark:")

        tests = sorted(slow_tests[file_path], key=lambda x: x[1], reverse=True)
        for test_nodeid, duration in tests:
            # Extract test name parts
            parts = test_nodeid.split("::")
            if len(parts) >= 2:
                test_identifier = "::".join(parts[1:])
                lines.append(f"#   {test_identifier} ({duration:.2f}s)")

        lines.append("# Add @pytest.mark.slow decorator to the above tests\n")

    return "\n".join(lines)


def save_detailed_results(slow_tests: Dict[str, List[Tuple[str, float]]], threshold: float) -> None:
    """Save detailed results to a JSON file."""
    results = {"threshold": threshold, "slow_tests": []}

    for file_path, tests in slow_tests.items():
        for test_nodeid, duration in tests:
            results["slow_tests"].append({"test": test_nodeid, "duration": duration, "file": file_path})

    # Sort by duration
    results["slow_tests"].sort(key=lambda x: x["duration"], reverse=True)

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
    parser.add_argument(
        "--test-path", type=str, default="tests/unit", help="Path to test directory (default: tests/unit)"
    )
    args = parser.parse_args()

    # Run tests and get report
    report = run_tests_with_json_report(args.test_path)

    if not report:
        print("Failed to generate test report")
        return 1

    # Analyze durations
    slow_tests = analyze_test_durations(report, args.threshold)

    # Generate and print report
    report_text = generate_report(slow_tests, args.threshold)
    print(report_text)

    if slow_tests:
        # Generate marker commands
        commands = generate_marker_commands(slow_tests)
        print(commands)

        # Save detailed results
        save_detailed_results(slow_tests, args.threshold)

        print(f"\n{'='*80}")
        print("NEXT STEPS:")
        print(f"{'='*80}")
        print("1. Review the slow tests identified above")
        print("2. Add @pytest.mark.slow decorator to each slow test")
        print("3. Run 'pytest -m \"not slow\"' to exclude slow tests in quick runs")
        print("4. Consider optimizing or mocking expensive operations in these tests")

    return 0


if __name__ == "__main__":
    sys.exit(main())
