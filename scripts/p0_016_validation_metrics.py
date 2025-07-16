#!/usr/bin/env python
"""
P0-016 Validation Metrics Script

Collects and reports on the success criteria for P0-016 completion.
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path


def run_command(cmd):
    """Run a command and return the output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1


def check_collection_errors():
    """Check for pytest collection errors."""
    print("🔍 Checking for collection errors...")
    stdout, stderr, code = run_command("python -m pytest --collect-only -q")
    try:
        # Count actual collection errors/failures
        error_count = (
            stderr.count("ERROR")
            + stderr.count("FAILED")
            + stderr.count("ImportError")
            + stderr.count("ModuleNotFoundError")
        )
        collected_count = stdout.count("::test_")
        print(f"   Collection errors: {error_count}")
        print(f"   Tests collected: {collected_count}")
        return error_count == 0, error_count
    except:
        print("   ❌ Failed to check collection errors")
        return False, -1


def check_test_markers():
    """Check if test markers are properly configured."""
    print("🔍 Checking test markers...")
    stdout, stderr, code = run_command("find tests -name '*.py' -exec grep -l '@pytest.mark.' {} \\; | wc -l")
    try:
        marker_files = int(stdout.strip())
        # Also check total markers
        stdout2, stderr2, code2 = run_command("find tests -name '*.py' -exec grep -h '@pytest.mark.' {} \\; | wc -l")
        total_markers = int(stdout2.strip())
        print(f"   Files with markers: {marker_files}")
        print(f"   Total markers: {total_markers}")
        return total_markers > 100, total_markers
    except:
        print("   ❌ Failed to check test markers")
        return False, -1


def check_parallelization():
    """Check if pytest-xdist is configured."""
    print("🔍 Checking parallelization configuration...")

    # Check if pytest-xdist is installed
    stdout, stderr, code = run_command("pip show pytest-xdist")
    xdist_installed = code == 0

    # Check if pytest.ini has xdist configuration
    pytest_ini = Path("pytest.ini")
    has_xdist_config = False
    if pytest_ini.exists():
        content = pytest_ini.read_text()
        has_xdist_config = "-n" in content or "xdist" in content.lower()

    print(f"   pytest-xdist installed: {xdist_installed}")
    print(f"   xdist configured: {has_xdist_config}")

    return xdist_installed and has_xdist_config, {"installed": xdist_installed, "configured": has_xdist_config}


def check_flaky_test_detection():
    """Check if flaky test detection tools exist."""
    print("🔍 Checking flaky test detection tools...")

    detection_script = Path("scripts/analyze_test_issues.py")
    detection_docs = Path("scripts/FLAKY_TEST_DETECTION.md")
    flaky_report = Path("FLAKY_TEST_ANALYSIS_REPORT.md")

    script_exists = detection_script.exists()
    docs_exist = detection_docs.exists()
    report_exists = flaky_report.exists()

    print(f"   Detection script: {script_exists}")
    print(f"   Documentation: {docs_exist}")
    print(f"   Analysis report: {report_exists}")

    return all([script_exists, docs_exist, report_exists]), {
        "script": script_exists,
        "docs": docs_exist,
        "report": report_exists,
    }


def check_documentation():
    """Check if all required documentation exists."""
    print("🔍 Checking documentation...")

    required_docs = [
        ("FLAKY_TEST_ANALYSIS_REPORT.md", "Flaky test analysis"),
        ("docs/test_performance_profiling.md", "Performance profiling guide"),
        ("docs/ci_job_optimization_proposal.md", "CI optimization proposal"),
        ("scripts/FLAKY_TEST_DETECTION.md", "Detection tool guide"),
    ]

    docs_status = {}
    all_exist = True

    for doc_path, description in required_docs:
        exists = Path(doc_path).exists()
        docs_status[doc_path] = exists
        all_exist &= exists
        print(f"   {description}: {'✅' if exists else '❌'}")

    return all_exist, docs_status


def check_makefile_commands():
    """Check if new Makefile commands exist."""
    print("🔍 Checking Makefile enhancements...")

    makefile = Path("Makefile")
    if not makefile.exists():
        print("   ❌ Makefile not found")
        return False, []

    content = makefile.read_text()

    # Check for key test commands
    commands = ["test-unit", "test-integration", "test-parallel", "test-slow", "quick-check", "bpci"]

    found_commands = []
    for cmd in commands:
        if f"{cmd}:" in content:
            found_commands.append(cmd)

    print(f"   Found {len(found_commands)}/{len(commands)} expected commands")
    for cmd in commands:
        print(f"   {cmd}: {'✅' if cmd in found_commands else '❌'}")

    return len(found_commands) >= 4, found_commands


def generate_validation_report():
    """Generate comprehensive validation report."""
    print("\n" + "=" * 60)
    print("P0-016 Validation Metrics Report")
    print("=" * 60)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    results = {}

    # Run all checks
    results["collection_errors"] = check_collection_errors()
    print()

    results["test_markers"] = check_test_markers()
    print()

    results["parallelization"] = check_parallelization()
    print()

    results["flaky_detection"] = check_flaky_test_detection()
    print()

    results["documentation"] = check_documentation()
    print()

    results["makefile"] = check_makefile_commands()
    print()

    # Calculate success rate
    total_checks = 6
    passed_checks = sum(1 for r in results.values() if r[0])
    success_rate = (passed_checks / total_checks) * 100

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Success Rate: {success_rate:.1f}% ({passed_checks}/{total_checks} checks passed)")
    print()

    # Success criteria assessment
    print("Success Criteria Assessment:")
    print(f"✅ Collection Success: {'PASS' if results['collection_errors'][0] else 'FAIL'}")
    print(f"✅ Test Categorization: {'PASS' if results['test_markers'][0] else 'FAIL'}")
    print(f"✅ Parallelization: {'PASS' if results['parallelization'][0] else 'FAIL'}")
    print(f"✅ Flaky Test Detection: {'PASS' if results['flaky_detection'][0] else 'FAIL'}")
    print(f"✅ Documentation: {'PASS' if results['documentation'][0] else 'FAIL'}")
    print(f"✅ Infrastructure: {'PASS' if results['makefile'][0] else 'FAIL'}")

    # Save results
    output_file = Path("p0_016_validation_results.json")
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "success_rate": success_rate,
                "results": {k: {"passed": v[0], "details": v[1]} for k, v in results.items()},
            },
            f,
            indent=2,
        )

    print(f"\n📄 Detailed results saved to: {output_file}")

    return success_rate >= 80


if __name__ == "__main__":
    success = generate_validation_report()
    exit(0 if success else 1)
