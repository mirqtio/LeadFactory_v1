#!/usr/bin/env python3
"""
Script to establish baseline metrics for test suite performance
Part of P0-016: Test Suite Stabilization and Performance Optimization
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path


def run_test_metrics():
    """Run tests and collect baseline metrics"""

    print("🔍 Establishing baseline test metrics...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("-" * 60)

    metrics = {"timestamp": datetime.now().isoformat(), "collection": {}, "execution": {}, "categories": {}}

    # 1. Collection metrics
    print("\n📊 Collection Metrics:")
    start = time.time()
    result = subprocess.run(["pytest", "--collect-only", "-q"], capture_output=True, text=True)
    collection_time = time.time() - start

    # Parse collection output
    output_lines = result.stdout.strip().split("\n")
    if output_lines:
        last_line = output_lines[-1]
        if "collected" in last_line:
            total_tests = int(last_line.split()[0])
            metrics["collection"]["total_tests"] = total_tests
            metrics["collection"]["collection_time"] = round(collection_time, 2)
            metrics["collection"]["errors"] = 0 if result.returncode == 0 else result.returncode

            print(f"  - Total tests collected: {total_tests}")
            print(f"  - Collection time: {collection_time:.2f}s")
            print(f"  - Collection errors: {metrics['collection']['errors']}")

    # 2. Test count by directory
    print("\n📁 Tests by Directory:")
    test_dirs = {}
    for test_file in Path("tests").rglob("test_*.py"):
        dir_name = test_file.parent.name
        test_dirs[dir_name] = test_dirs.get(dir_name, 0) + 1

    for dir_name, count in sorted(test_dirs.items()):
        print(f"  - {dir_name}: {count} files")
        metrics["categories"][dir_name] = count

    # 3. Quick performance check (unit tests only, limited time)
    print("\n⚡ Quick Performance Check (unit tests, 30s timeout):")
    start = time.time()
    result = subprocess.run(
        ["pytest", "tests/unit", "-x", "--tb=no", "--timeout=30", "-q"],
        capture_output=True,
        text=True,
        timeout=35,  # Give 5 extra seconds before hard timeout
    )
    unit_time = time.time() - start

    # Parse results
    if "passed" in result.stdout:
        parts = result.stdout.strip().split()
        for i, part in enumerate(parts):
            if "passed" in part and i > 0:
                passed_count = int(parts[i - 1])
                metrics["execution"]["unit_tests_passed"] = passed_count
                break

    metrics["execution"]["unit_test_time"] = round(unit_time, 2)
    metrics["execution"]["unit_test_status"] = "timeout" if unit_time > 30 else "completed"

    print(f"  - Unit test execution time: {unit_time:.2f}s")
    print(f"  - Status: {metrics['execution']['unit_test_status']}")

    # 4. Check for xfail markers
    print("\n🚫 Tests with xfail markers:")
    result = subprocess.run(
        ["grep", "-r", "@pytest.mark.xfail", "tests/", "--include=*.py"], capture_output=True, text=True
    )
    xfail_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
    metrics["collection"]["xfail_markers"] = xfail_count
    print(f"  - Total xfail markers: {xfail_count}")

    # 5. Check for skip markers
    print("\n⏭️  Tests with skip markers:")
    result = subprocess.run(
        ["grep", "-r", "@pytest.mark.skip", "tests/", "--include=*.py"], capture_output=True, text=True
    )
    skip_count = len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
    metrics["collection"]["skip_markers"] = skip_count
    print(f"  - Total skip markers: {skip_count}")

    # Save metrics
    metrics_file = Path("test_metrics_baseline.json")
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n✅ Baseline metrics saved to: {metrics_file}")
    print("\n📋 Summary:")
    print(f"  - Total tests: {metrics['collection']['total_tests']}")
    print(f"  - Collection time: {metrics['collection']['collection_time']}s")
    print(f"  - xfail markers: {xfail_count}")
    print(f"  - skip markers: {skip_count}")
    print(f"  - Unit test time: {metrics['execution']['unit_test_time']}s")

    return metrics


if __name__ == "__main__":
    run_test_metrics()
