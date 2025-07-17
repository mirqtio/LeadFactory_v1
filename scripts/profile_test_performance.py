#!/usr/bin/env python3
"""
Test performance profiler for optimizing CI pipeline.
Identifies fastest tests for ultra-fast CI configuration.
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple


def run_test_with_timing(test_path: str) -> Tuple[str, float, bool]:
    """Run a single test and measure its execution time."""
    start_time = time.time()

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", test_path, "--tb=no", "-q", "--disable-warnings", "--maxfail=1", "-x"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        end_time = time.time()
        duration = end_time - start_time
        success = result.returncode == 0

        return test_path, duration, success
    except subprocess.TimeoutExpired:
        return test_path, 30.0, False
    except Exception as e:
        print(f"Error running {test_path}: {e}")
        return test_path, 999.0, False


def find_fast_tests() -> List[Dict]:
    """Find the fastest unit tests for ultra-fast CI."""
    # Fast test candidates based on analysis
    fast_test_paths = [
        "tests/unit/design/test_token_extraction.py",
        "tests/unit/design/test_validation_module.py",
        "tests/unit/d5_scoring/test_engine.py",
        "tests/unit/d8_personalization/test_templates.py",
        "tests/unit/d8_personalization/test_subject_lines.py",
        "tests/unit/d5_scoring/test_impact_calculator.py",
        "tests/unit/d5_scoring/test_omega.py",
        "tests/unit/d5_scoring/test_tiers.py",
        "tests/unit/design/test_token_usage.py",
    ]

    results = []

    print("Profiling fast test candidates...")
    for test_path in fast_test_paths:
        if Path(test_path).exists():
            print(f"Testing {test_path}...")
            path, duration, success = run_test_with_timing(test_path)
            results.append({"path": path, "duration": duration, "success": success, "category": "fast_candidate"})
            print(f"  Duration: {duration:.2f}s, Success: {success}")
        else:
            print(f"Skipping {test_path} (not found)")

    # Sort by duration
    results.sort(key=lambda x: x["duration"])

    return results


def generate_performance_report(results: List[Dict]) -> Dict:
    """Generate performance analysis report."""
    successful_tests = [r for r in results if r["success"]]
    failed_tests = [r for r in results if not r["success"]]

    if successful_tests:
        fastest_tests = successful_tests[:5]
        avg_duration = sum(r["duration"] for r in successful_tests) / len(successful_tests)
    else:
        fastest_tests = []
        avg_duration = 0.0

    report = {
        "summary": {
            "total_tests": len(results),
            "successful_tests": len(successful_tests),
            "failed_tests": len(failed_tests),
            "average_duration": avg_duration,
        },
        "fastest_tests": fastest_tests,
        "recommendations": {
            "ultra_fast_ci_tests": [t["path"] for t in fastest_tests if t["duration"] < 5.0],
            "total_estimated_time": sum(t["duration"] for t in fastest_tests),
        },
    }

    return report


def main():
    """Main execution function."""
    print("🚀 Starting test performance profiling...")
    print("=" * 60)

    # Profile fast test candidates
    results = find_fast_tests()

    # Generate report
    report = generate_performance_report(results)

    # Output results
    print("\n📊 Performance Analysis Report")
    print("=" * 60)
    print(f"Total tests analyzed: {report['summary']['total_tests']}")
    print(f"Successful tests: {report['summary']['successful_tests']}")
    print(f"Failed tests: {report['summary']['failed_tests']}")
    print(f"Average duration: {report['summary']['average_duration']:.2f}s")

    print("\n⚡ Fastest Tests for Ultra-Fast CI:")
    for i, test in enumerate(report["fastest_tests"], 1):
        print(f"{i}. {test['path']} - {test['duration']:.2f}s")

    print(f"\n🎯 Recommended Ultra-Fast CI Tests:")
    for test_path in report["recommendations"]["ultra_fast_ci_tests"]:
        print(f"  - {test_path}")

    print(f"\n⏱️  Estimated Total Time: {report['recommendations']['total_estimated_time']:.2f}s")

    # Save detailed report
    with open("test_performance_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Detailed report saved to: test_performance_report.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
