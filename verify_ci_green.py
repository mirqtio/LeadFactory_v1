#!/usr/bin/env python3
"""
Verify that all CI workflows are passing
"""

import json
import subprocess
import sys
import time


def check_workflows():
    """Check status of all workflows"""
    print("🔍 Checking all CI workflows...")

    # Get the latest run for each workflow
    workflows = [
        "CI/CD Pipeline",
        "Test Suite",
        "Docker Build",
        "Linting and Code Quality",
        "Validate Setup",
        "Deploy to VPS",
    ]

    all_passing = True
    results = {}

    for workflow in workflows:
        cmd = f'gh run list --workflow="{workflow}" --limit=1 --json status,conclusion,headBranch'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if data:
                    run = data[0]
                    status = run.get("status", "unknown")
                    conclusion = run.get("conclusion", "pending")
                    branch = run.get("headBranch", "unknown")

                    if branch == "main":
                        if status == "completed" and conclusion == "success":
                            results[workflow] = "✅ PASSED"
                        elif status == "in_progress":
                            results[workflow] = "⏳ IN PROGRESS"
                            all_passing = False
                        else:
                            results[workflow] = f"❌ FAILED ({conclusion})"
                            all_passing = False
                    else:
                        results[workflow] = f"⚠️  Different branch ({branch})"
                else:
                    results[workflow] = "❓ No runs found"
            except json.JSONDecodeError:
                results[workflow] = "❓ Error parsing result"
        else:
            results[workflow] = "❓ Workflow not found"

    # Display results
    print("\n" + "=" * 60)
    print("📊 CI Workflow Status Summary")
    print("=" * 60)

    for workflow, status in results.items():
        print(f"{workflow}: {status}")

    print("=" * 60)

    if all_passing:
        print("\n✅ All workflows are passing!")
        return True
    else:
        print("\n⚠️  Some workflows are not passing yet")
        return False


def wait_for_ci_completion(max_wait=300):
    """Wait for CI to complete"""
    start_time = time.time()

    while time.time() - start_time < max_wait:
        print(f"\n⏰ Checking CI status... (elapsed: {int(time.time() - start_time)}s)")

        # Check if CI/CD Pipeline is still running
        cmd = 'gh run list --workflow="CI/CD Pipeline" --limit=1 --json status'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout.strip():
            try:
                data = json.loads(result.stdout)
                if data and data[0].get("status") != "in_progress":
                    print("✅ CI/CD Pipeline completed!")
                    break
            except json.JSONDecodeError:
                pass

        time.sleep(10)

    # Final check
    return check_workflows()


if __name__ == "__main__":
    # First check
    if not check_workflows():
        print("\n⏳ Waiting for CI to complete...")
        wait_for_ci_completion()

    # Final verdict
    if check_workflows():
        sys.exit(0)
    else:
        sys.exit(1)
