#!/usr/bin/env python3
"""
Monitor all CI workflows until completion
"""

import json
import subprocess
import sys
import time


def get_workflow_status(commit_sha):
    """Get status of all workflows for a specific commit"""
    cmd = f"gh run list --json name,status,conclusion,headSha,workflowName,createdAt | jq '[.[] | select(.headSha == \"{commit_sha}\")]'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0 and result.stdout.strip():
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
    return []


def display_status(workflows):
    """Display workflow status"""
    print("\n" + "=" * 60)
    print("📊 CI Workflow Status")
    print("=" * 60)

    status_map = {}
    for w in workflows:
        name = w.get("workflowName", w.get("name", "Unknown"))
        status = w.get("status", "unknown")
        conclusion = w.get("conclusion", "")

        if status == "completed":
            if conclusion == "success":
                status_map[name] = "✅ PASSED"
            else:
                status_map[name] = f"❌ FAILED ({conclusion})"
        elif status == "in_progress":
            status_map[name] = "⏳ IN PROGRESS"
        else:
            status_map[name] = f"❓ {status}"

    # Display in consistent order
    workflow_order = [
        "Test Suite",
        "Docker Build",
        "Linting and Code Quality",
        "Validate Setup",
        "Deploy to VPS",
        "CI/CD Pipeline",
        "Minimal Test Suite",
    ]

    for workflow in workflow_order:
        if workflow in status_map:
            print(f"{workflow}: {status_map[workflow]}")

    # Show any other workflows not in the list
    for name, status in status_map.items():
        if name not in workflow_order:
            print(f"{name}: {status}")

    print("=" * 60)

    # Check if all are complete
    all_complete = all(w.get("status") == "completed" for w in workflows)
    all_success = all_complete and all(
        w.get("conclusion") == "success" for w in workflows if w.get("status") == "completed"
    )

    return all_complete, all_success


def monitor_ci(max_wait=600):
    """Monitor CI until all workflows complete"""
    # Get latest commit SHA
    result = subprocess.run("git rev-parse HEAD", shell=True, capture_output=True, text=True)
    commit_sha = result.stdout.strip()

    print(f"🔍 Monitoring CI for commit: {commit_sha[:7]}")

    start_time = time.time()
    check_count = 0

    while time.time() - start_time < max_wait:
        check_count += 1
        print(f"\n⏰ Check #{check_count} (elapsed: {int(time.time() - start_time)}s)")

        workflows = get_workflow_status(commit_sha)
        if not workflows:
            print("⏳ Waiting for workflows to start...")
            time.sleep(10)
            continue

        all_complete, all_success = display_status(workflows)

        if all_complete:
            if all_success:
                print("\n✅ ALL CI WORKFLOWS PASSED! 🎉")
                return True
            print("\n❌ Some workflows failed. Check the logs for details.")
            return False

        time.sleep(15)

    print(f"\n⏱️  Timeout after {max_wait} seconds")
    return False


if __name__ == "__main__":
    success = monitor_ci(max_wait=900)  # 15 minutes
    sys.exit(0 if success else 1)
