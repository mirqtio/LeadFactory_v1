#!/usr/bin/env python3
"""
Flaky Test Detection Script

This script runs tests multiple times to identify flaky tests that fail intermittently.
It analyzes failure patterns and generates a comprehensive report.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple


class FlakyTestDetector:
    """Detects flaky tests by running them multiple times and analyzing results."""

    def __init__(self, iterations: int = 5, test_path: str = "tests/", verbose: bool = False):
        self.iterations = iterations
        self.test_path = test_path
        self.verbose = verbose
        self.test_results = defaultdict(list)
        self.test_timings = defaultdict(list)
        self.failure_patterns = defaultdict(list)
        self.port_conflicts = defaultdict(int)
        self.async_warnings = defaultdict(int)
        self.timing_issues = defaultdict(int)

    def run_tests(self, test_filter: str = None) -> Tuple[bool, str, float]:
        """Run pytest and capture results."""
        cmd = [
            "python",
            "-m",
            "pytest",
            "-v",
            "--tb=short",
            "--junit-xml=test_results.xml",
            "-W",
            "ignore::DeprecationWarning",
        ]

        if test_filter:
            cmd.extend(["-k", test_filter])
        else:
            cmd.append(self.test_path)

        # Add timeout to prevent hanging tests
        cmd.extend(["--timeout=300"])

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600  # 10 minute timeout for entire test run
            )
            duration = time.time() - start_time

            # Parse XML results if available
            if os.path.exists("test_results.xml"):
                self._parse_junit_xml("test_results.xml")

            return result.returncode == 0, result.stdout + result.stderr, duration
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return False, "Test run timed out after 10 minutes", duration
        except Exception as e:
            duration = time.time() - start_time
            return False, f"Error running tests: {str(e)}", duration

    def _parse_junit_xml(self, xml_path: str):
        """Parse JUnit XML for detailed test results."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            for testcase in root.findall(".//testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_taken = float(testcase.get("time", "0"))

                test_id = f"{classname}::{name}"
                self.test_timings[test_id].append(time_taken)

                # Check for failures
                failure = testcase.find("failure")
                if failure is not None:
                    self._analyze_failure(test_id, failure.text or "")

                # Check for errors
                error = testcase.find("error")
                if error is not None:
                    self._analyze_failure(test_id, error.text or "")

        except Exception as e:
            if self.verbose:
                print(f"Error parsing XML: {e}")

    def _analyze_failure(self, test_id: str, error_text: str):
        """Analyze failure messages for patterns."""
        # Port conflict detection
        if re.search(r"(port|address|bind|EADDRINUSE|already in use)", error_text, re.I):
            self.port_conflicts[test_id] += 1
            self.failure_patterns[test_id].append("port_conflict")

        # Async/await issues
        if re.search(r"(asyncio|RuntimeWarning.*coroutine|await|async)", error_text, re.I):
            self.async_warnings[test_id] += 1
            self.failure_patterns[test_id].append("async_issue")

        # Timing issues
        if re.search(r"(timeout|timed out|sleep|delay|wait)", error_text, re.I):
            self.timing_issues[test_id] += 1
            self.failure_patterns[test_id].append("timing_issue")

        # Database/connection issues
        if re.search(r"(connection|database|postgres|sqlite|pool)", error_text, re.I):
            self.failure_patterns[test_id].append("database_issue")

        # External service issues
        if re.search(r"(http|request|api|stub|mock|external)", error_text, re.I):
            self.failure_patterns[test_id].append("external_service")

    def detect_flaky_tests(self) -> Dict:
        """Run tests multiple times and identify flaky ones."""
        print(f"Running tests {self.iterations} times to detect flaky behavior...")

        all_test_names = set()
        iteration_results = []

        for i in range(self.iterations):
            print(f"\nIteration {i + 1}/{self.iterations}...")

            success, output, duration = self.run_tests()

            # Extract test results from output
            test_results = self._extract_test_results(output)
            iteration_results.append(
                {
                    "iteration": i + 1,
                    "success": success,
                    "duration": duration,
                    "test_results": test_results,
                    "output": output if self.verbose else "",
                }
            )

            all_test_names.update(test_results.keys())

            # Update test results
            for test_name, result in test_results.items():
                self.test_results[test_name].append(result)

            # Small delay between runs to avoid resource conflicts
            if i < self.iterations - 1:
                time.sleep(2)

        # Analyze results
        flaky_tests = self._analyze_flakiness(all_test_names)

        return {
            "summary": self._generate_summary(flaky_tests),
            "flaky_tests": flaky_tests,
            "iteration_results": iteration_results,
            "patterns": self._analyze_patterns(),
        }

    def _extract_test_results(self, output: str) -> Dict[str, str]:
        """Extract individual test results from pytest output."""
        results = {}

        # Pattern for pytest verbose output
        pattern = r"(tests/[^\s]+::[^\s]+)\s+(PASSED|FAILED|SKIPPED|XFAIL|XPASS|ERROR)"

        for match in re.finditer(pattern, output):
            test_name = match.group(1)
            result = match.group(2)
            results[test_name] = result

        return results

    def _analyze_flakiness(self, all_test_names: Set[str]) -> List[Dict]:
        """Analyze which tests are flaky based on inconsistent results."""
        flaky_tests = []

        for test_name in all_test_names:
            results = self.test_results.get(test_name, [])

            if len(results) < 2:
                continue

            # Count different outcomes
            outcome_counts = defaultdict(int)
            for result in results:
                outcome_counts[result] += 1

            # Test is flaky if it has multiple different outcomes
            if len(outcome_counts) > 1:
                total_runs = len(results)
                failure_rate = (outcome_counts.get("FAILED", 0) + outcome_counts.get("ERROR", 0)) / total_runs

                # Calculate timing variance if available
                timings = self.test_timings.get(test_name, [])
                timing_variance = 0
                if len(timings) > 1:
                    avg_time = sum(timings) / len(timings)
                    timing_variance = max(timings) - min(timings)

                flaky_tests.append(
                    {
                        "test_name": test_name,
                        "failure_rate": failure_rate,
                        "outcomes": dict(outcome_counts),
                        "total_runs": total_runs,
                        "timing_variance": timing_variance,
                        "patterns": list(set(self.failure_patterns.get(test_name, []))),
                        "port_conflicts": self.port_conflicts.get(test_name, 0),
                        "async_warnings": self.async_warnings.get(test_name, 0),
                        "timing_issues": self.timing_issues.get(test_name, 0),
                    }
                )

        # Sort by failure rate
        flaky_tests.sort(key=lambda x: x["failure_rate"], reverse=True)

        return flaky_tests

    def _analyze_patterns(self) -> Dict:
        """Analyze common patterns across all flaky tests."""
        patterns = {
            "port_conflicts": sum(self.port_conflicts.values()),
            "async_warnings": sum(self.async_warnings.values()),
            "timing_issues": sum(self.timing_issues.values()),
            "pattern_distribution": defaultdict(int),
        }

        for test_patterns in self.failure_patterns.values():
            for pattern in test_patterns:
                patterns["pattern_distribution"][pattern] += 1

        return patterns

    def _generate_summary(self, flaky_tests: List[Dict]) -> Dict:
        """Generate summary statistics."""
        total_tests = len(self.test_results)
        flaky_count = len(flaky_tests)

        return {
            "total_tests_analyzed": total_tests,
            "flaky_tests_found": flaky_count,
            "flakiness_rate": flaky_count / total_tests if total_tests > 0 else 0,
            "iterations_run": self.iterations,
            "timestamp": datetime.now().isoformat(),
        }

    def generate_report(self, results: Dict, output_file: str = "flaky_tests_report.md"):
        """Generate a markdown report of findings."""
        report = []
        report.append("# Flaky Test Detection Report")
        report.append(f"\nGenerated: {results['summary']['timestamp']}")
        report.append(f"\n## Summary")
        report.append(f"- Total tests analyzed: {results['summary']['total_tests_analyzed']}")
        report.append(f"- Flaky tests found: {results['summary']['flaky_tests_found']}")
        report.append(f"- Flakiness rate: {results['summary']['flakiness_rate']:.1%}")
        report.append(f"- Test iterations: {results['summary']['iterations_run']}")

        # Pattern analysis
        if results["patterns"]["pattern_distribution"]:
            report.append(f"\n## Common Failure Patterns")
            for pattern, count in sorted(
                results["patterns"]["pattern_distribution"].items(), key=lambda x: x[1], reverse=True
            ):
                report.append(f"- {pattern.replace('_', ' ').title()}: {count} occurrences")

        # Flaky tests details
        if results["flaky_tests"]:
            report.append(f"\n## Flaky Tests (Sorted by Failure Rate)")
            report.append("\n### High Priority (>50% failure rate)")
            high_priority = [t for t in results["flaky_tests"] if t["failure_rate"] > 0.5]
            self._add_test_details(report, high_priority)

            report.append("\n### Medium Priority (20-50% failure rate)")
            medium_priority = [t for t in results["flaky_tests"] if 0.2 <= t["failure_rate"] <= 0.5]
            self._add_test_details(report, medium_priority)

            report.append("\n### Low Priority (<20% failure rate)")
            low_priority = [t for t in results["flaky_tests"] if t["failure_rate"] < 0.2]
            self._add_test_details(report, low_priority)

        # Recommendations
        report.append("\n## Recommendations")
        self._add_recommendations(report, results)

        # Write report
        with open(output_file, "w") as f:
            f.write("\n".join(report))

        print(f"\nReport written to {output_file}")

        # Also generate JSON report for programmatic access
        json_file = output_file.replace(".md", ".json")
        with open(json_file, "w") as f:
            json.dump(results, f, indent=2)
        print(f"JSON data written to {json_file}")

    def _add_test_details(self, report: List[str], tests: List[Dict]):
        """Add test details to report."""
        for test in tests:
            report.append(f"\n#### `{test['test_name']}`")
            report.append(f"- Failure rate: {test['failure_rate']:.1%}")
            report.append(f"- Outcomes: {test['outcomes']}")

            if test["patterns"]:
                report.append(f"- Identified issues: {', '.join(test['patterns'])}")

            if test["timing_variance"] > 1:
                report.append(f"- High timing variance: {test['timing_variance']:.2f}s")

            if test["port_conflicts"] > 0:
                report.append(f"- Port conflicts detected: {test['port_conflicts']} times")

            if test["async_warnings"] > 0:
                report.append(f"- Async warnings: {test['async_warnings']} times")

    def _add_recommendations(self, report: List[str], results: Dict):
        """Add recommendations based on findings."""
        patterns = results["patterns"]["pattern_distribution"]

        if patterns.get("port_conflict", 0) > 0:
            report.append("\n### Port Conflict Issues")
            report.append("- Use dynamic port allocation instead of hardcoded ports")
            report.append("- Ensure proper cleanup in test teardown")
            report.append("- Consider using pytest-xdist with --dist loadscope")

        if patterns.get("async_issue", 0) > 0:
            report.append("\n### Async/Await Issues")
            report.append("- Use pytest-asyncio consistently")
            report.append("- Ensure proper event loop cleanup")
            report.append("- Avoid mixing sync and async test patterns")

        if patterns.get("timing_issue", 0) > 0:
            report.append("\n### Timing Issues")
            report.append("- Replace time.sleep() with proper wait conditions")
            report.append("- Use mocks for time-sensitive operations")
            report.append("- Implement proper retry logic with backoff")

        if patterns.get("database_issue", 0) > 0:
            report.append("\n### Database Issues")
            report.append("- Ensure database isolation between tests")
            report.append("- Use transactions and rollback")
            report.append("- Check for connection pool exhaustion")

        if patterns.get("external_service", 0) > 0:
            report.append("\n### External Service Issues")
            report.append("- Mock external services consistently")
            report.append("- Implement proper stub server fixtures")
            report.append("- Add retry logic for network operations")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Detect flaky tests by running them multiple times")
    parser.add_argument("-n", "--iterations", type=int, default=5, help="Number of times to run tests (default: 5)")
    parser.add_argument("-p", "--path", default="tests/", help="Path to test directory (default: tests/)")
    parser.add_argument("-f", "--filter", help="Filter tests by pattern (pytest -k)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-o", "--output", default="flaky_tests_report.md", help="Output report file (default: flaky_tests_report.md)"
    )

    args = parser.parse_args()

    # Create detector and run analysis
    detector = FlakyTestDetector(iterations=args.iterations, test_path=args.path, verbose=args.verbose)

    # Run detection
    results = detector.detect_flaky_tests()

    # Generate report
    detector.generate_report(results, args.output)

    # Exit with error code if flaky tests found
    if results["summary"]["flaky_tests_found"] > 0:
        print(f"\n⚠️  Found {results['summary']['flaky_tests_found']} flaky tests!")
        sys.exit(1)
    else:
        print("\n✅ No flaky tests detected!")
        sys.exit(0)


if __name__ == "__main__":
    main()
