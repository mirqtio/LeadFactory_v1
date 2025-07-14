#!/usr/bin/env python3
"""Check CI status and update dashboard accordingly."""

import subprocess
import json
from datetime import datetime

def check_ci_status():
    """Check the actual CI status from git and local tests."""
    
    print("🔍 Checking CI Status...")
    print("=" * 60)
    
    # Get latest commit
    try:
        latest_commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%H %s"], 
            text=True
        ).strip()
        print(f"Latest commit: {latest_commit}")
    except Exception as e:
        print(f"Error getting commit: {e}")
        latest_commit = "Unknown"
    
    # Check if we're on main and up to date
    try:
        status = subprocess.check_output(["git", "status", "-sb"], text=True)
        print(f"Git status: {status.strip()}")
    except Exception as e:
        print(f"Error getting status: {e}")
    
    # Run local tests to verify
    print("\n🧪 Running local tests...")
    print("-" * 60)
    
    test_results = {
        "unit_tests": False,
        "integration_tests": False,
        "linting": False,
        "overall": False
    }
    
    # Run unit tests
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/unit/test_prerequisites.py", "-v"],
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, "STUB_BASE_URL": "http://localhost:5010"}
        )
        test_results["unit_tests"] = result.returncode == 0
        print(f"Unit tests: {'✅ PASSED' if test_results['unit_tests'] else '❌ FAILED'}")
        if not test_results["unit_tests"]:
            print(f"Error output: {result.stderr[-500:]}")
    except Exception as e:
        print(f"Unit test error: {e}")
    
    # Check linting
    try:
        result = subprocess.run(
            ["ruff", "check", ".", "--statistics"],
            capture_output=True,
            text=True
        )
        # Linting passes if there are no errors (warnings are ok)
        test_results["linting"] = "error" not in result.stdout.lower()
        print(f"Linting: {'✅ PASSED' if test_results['linting'] else '❌ FAILED'}")
        if not test_results["linting"]:
            print(f"Linting issues: {result.stdout[-500:]}")
    except Exception as e:
        print(f"Linting error: {e}")
    
    # Overall status
    test_results["overall"] = all([
        test_results["unit_tests"],
        test_results["linting"]
    ])
    
    print("\n📊 Summary")
    print("-" * 60)
    print(f"Overall CI Status: {'✅ PASSING' if test_results['overall'] else '❌ FAILING'}")
    print(f"- Unit Tests: {'✅' if test_results['unit_tests'] else '❌'}")
    print(f"- Linting: {'✅' if test_results['linting'] else '❌'}")
    
    # Create status report
    status_report = {
        "timestamp": datetime.utcnow().isoformat(),
        "commit": latest_commit,
        "test_results": test_results,
        "tasks_complete": 0 if not test_results["overall"] else "TBD"
    }
    
    with open("ci_status.json", "w") as f:
        json.dump(status_report, f, indent=2)
    
    print("\n💾 Status saved to ci_status.json")
    
    return test_results["overall"]

if __name__ == "__main__":
    ci_passing = check_ci_status()
    
    if ci_passing:
        print("\n🎉 CI is passing! Tasks can be marked as complete.")
    else:
        print("\n⚠️  CI is failing. No tasks can be marked as complete.")
        print("Fix the failing tests and linting issues before proceeding.")