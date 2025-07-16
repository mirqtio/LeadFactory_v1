"""
CI Health Check - Comprehensive Test Status Report

This test module runs all tests and generates a report of failures
to guide systematic fixing.
"""

import json
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytest

# Mark entire module as smoke test - runs in CI to check test health
pytestmark = pytest.mark.smoke


def run_pytest_json():
    """Run pytest with JSON output to capture all test results."""
    cmd = [
        "python3",
        "-m",
        "pytest",
        "--json-report",
        "--json-report-file=test_results.json",
        "--tb=short",
        "-q",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode


def analyze_test_results():
    """Analyze test results and categorize failures."""
    try:
        with open("test_results.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No test results found. Running tests first...")
        run_pytest_json()
        with open("test_results.json", "r") as f:
            data = json.load(f)

    summary = data.get("summary", {})
    tests = data.get("tests", [])

    # Categorize failures
    failures_by_module = defaultdict(list)
    failures_by_type = defaultdict(list)
    skipped_tests = []

    for test in tests:
        if test["outcome"] == "failed":
            module = test["nodeid"].split("::")[0]
            failures_by_module[module].append(test)

            # Categorize by error type
            if "call" in test and "longrepr" in test["call"]:
                error_msg = str(test["call"]["longrepr"])
                if "AsyncMock" in error_msg or "coroutine" in error_msg:
                    failures_by_type["async_mock"].append(test)
                elif "dependency_overrides" in error_msg:
                    failures_by_type["fastapi_dependency"].append(test)
                elif "Missing" in error_msg and "environment" in error_msg:
                    failures_by_type["env_vars"].append(test)
                elif "timeout" in error_msg.lower():
                    failures_by_type["timeout"].append(test)
                else:
                    failures_by_type["other"].append(test)

        elif test["outcome"] == "skipped":
            skipped_tests.append(test)

    return {
        "summary": summary,
        "failures_by_module": dict(failures_by_module),
        "failures_by_type": dict(failures_by_type),
        "skipped_tests": skipped_tests,
    }


def generate_fix_report():
    """Generate a comprehensive report of what needs fixing."""
    results = analyze_test_results()

    report_path = Path("CI_TEST_STATUS_REPORT.md")

    with open(report_path, "w") as f:
        f.write("# CI Test Status Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")

        # Summary
        summary = results["summary"]
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)

        f.write("## Summary\n")
        f.write(f"- Total Tests: {total}\n")
        if total > 0:
            f.write(f"- Passed: {passed} ({passed/total*100:.1f}%)\n")
            f.write(f"- Failed: {failed} ({failed/total*100:.1f}%)\n")
            f.write(f"- Skipped: {skipped} ({skipped/total*100:.1f}%)\n\n")
        else:
            f.write("- No test results found\n\n")

        # Failures by module
        f.write("## Failures by Module\n")
        for module, tests in sorted(results["failures_by_module"].items()):
            f.write(f"\n### {module} ({len(tests)} failures)\n")
            for test in tests:
                test_name = test["nodeid"].split("::")[-1]
                f.write(f"- [ ] {test_name}\n")

        # Failures by type
        f.write("\n## Failures by Type\n")
        for error_type, tests in sorted(results["failures_by_type"].items()):
            f.write(f"\n### {error_type.replace('_', ' ').title()} ({len(tests)} failures)\n")
            for test in tests[:5]:  # Show first 5 examples
                f.write(f"- {test['nodeid']}\n")
            if len(tests) > 5:
                f.write(f"- ... and {len(tests) - 5} more\n")

        # Skipped tests
        if results["skipped_tests"]:
            f.write(f"\n## Skipped Tests ({len(results['skipped_tests'])})\n")
            for test in results["skipped_tests"][:10]:
                f.write(f"- {test['nodeid']}\n")
            if len(results["skipped_tests"]) > 10:
                f.write(f"- ... and {len(results['skipped_tests']) - 10} more\n")

        # Fix priority
        f.write("\n## Fix Priority Order\n")
        f.write("1. **Async Mock Issues** - Create standard async mocking pattern\n")
        f.write("2. **FastAPI Dependencies** - Use dependency override helper\n")
        f.write("3. **Environment Variables** - Use env mock helper\n")
        f.write("4. **Test Isolation** - Add proper cleanup fixtures\n")
        f.write("5. **Timeouts** - Adjust timeouts and add retries\n")

    print(f"Report generated: {report_path}")
    return results


if __name__ == "__main__":
    print("Running comprehensive CI health check...")
    results = generate_fix_report()

    print("\nTest Status:")
    print(f"- Failed: {results['summary'].get('failed', 0)}")
    print(f"- Skipped: {results['summary'].get('skipped', 0)}")
    print(f"- Total issues to fix: {results['summary'].get('failed', 0) + results['summary'].get('skipped', 0)}")
