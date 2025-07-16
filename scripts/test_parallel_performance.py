#!/usr/bin/env python3
"""
Test Parallel Performance Measurement

This script measures the performance improvement from test parallelization.
"""

import subprocess
import sys
import time
from pathlib import Path


def run_tests(args, description):
    """Run pytest with given arguments and measure time."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: pytest {' '.join(args)}")
    print(f"{'='*60}")

    start_time = time.time()

    result = subprocess.run(["pytest"] + args, capture_output=True, text=True)

    end_time = time.time()
    duration = end_time - start_time

    # Count tests
    test_count = 0
    if "passed" in result.stdout:
        import re

        match = re.search(r"(\d+) passed", result.stdout)
        if match:
            test_count = int(match.group(1))

    return {
        "description": description,
        "duration": duration,
        "returncode": result.returncode,
        "test_count": test_count,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main():
    """Run performance comparison tests."""
    print("Test Parallelization Performance Comparison")
    print("==========================================")

    # Test configurations
    test_configs = [
        # Unit tests
        {"args": ["-m", "unit", "--tb=no", "-q"], "description": "Unit tests - Serial execution"},
        {
            "args": ["-m", "unit", "-n", "auto", "--dist", "worksteal", "--tb=no", "-q"],
            "description": "Unit tests - Parallel execution (auto)",
        },
        {
            "args": ["-m", "unit", "-n", "2", "--dist", "worksteal", "--tb=no", "-q"],
            "description": "Unit tests - Parallel execution (2 workers)",
        },
        {
            "args": ["-m", "unit", "-n", "4", "--dist", "worksteal", "--tb=no", "-q"],
            "description": "Unit tests - Parallel execution (4 workers)",
        },
    ]

    # Add integration test configs if requested
    if "--include-integration" in sys.argv:
        test_configs.extend(
            [
                {"args": ["-m", "integration", "--tb=no", "-q"], "description": "Integration tests - Serial execution"},
                {
                    "args": ["-m", "integration", "-n", "2", "--dist", "worksteal", "--tb=no", "-q"],
                    "description": "Integration tests - Parallel execution (2 workers)",
                },
            ]
        )

    # Run tests and collect results
    results = []
    for config in test_configs:
        result = run_tests(config["args"], config["description"])
        results.append(result)

        # Quick summary
        status = "PASSED" if result["returncode"] == 0 else "FAILED"
        print(f"\nStatus: {status}")
        print(f"Duration: {result['duration']:.2f}s")
        print(f"Tests run: {result['test_count']}")

    # Performance summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)

    # Find baseline (serial) results
    unit_serial = next((r for r in results if "Unit tests - Serial" in r["description"]), None)

    print(f"\n{'Test Configuration':<50} {'Duration':>10} {'Tests':>8} {'Speedup':>10}")
    print("-" * 80)

    for result in results:
        speedup = ""
        if unit_serial and "Serial" not in result["description"] and "Unit" in result["description"]:
            if result["duration"] > 0:
                speedup_factor = unit_serial["duration"] / result["duration"]
                speedup = f"{speedup_factor:.2f}x"

        print(f"{result['description']:<50} {result['duration']:>8.2f}s {result['test_count']:>8} {speedup:>10}")

    # Calculate overall improvement
    if unit_serial:
        best_parallel = min(
            (r for r in results if "Unit" in r["description"] and "Parallel" in r["description"]),
            key=lambda x: x["duration"],
            default=None,
        )

        if best_parallel:
            improvement = ((unit_serial["duration"] - best_parallel["duration"]) / unit_serial["duration"]) * 100
            print(f"\nBest parallel performance improvement: {improvement:.1f}%")
            print(f"Time saved: {unit_serial['duration'] - best_parallel['duration']:.2f}s")


if __name__ == "__main__":
    main()
