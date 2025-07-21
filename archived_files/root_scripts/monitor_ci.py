#!/usr/bin/env python3
"""Monitor CI status"""

import json
import subprocess
import time


def check_ci_status():
    """Check current CI status"""
    try:
        result = subprocess.run(
            ["curl", "-s", "https://api.github.com/repos/mirqtio/LeadFactory_v1/actions/runs?per_page=1"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            if data.get("workflow_runs"):
                run = data["workflow_runs"][0]
                status = run.get("status", "unknown")
                conclusion = run.get("conclusion", "null")
                url = run.get("html_url", "")

                print(f"CI Status: {status}")
                print(f"CI Conclusion: {conclusion}")
                print(f"CI URL: {url}")

                return status, conclusion

        return "unknown", "null"

    except Exception as e:
        print(f"Error checking CI: {e}")
        return "error", "null"


def main():
    """Monitor CI until completion"""
    print("🔍 Monitoring CI status...")

    for i in range(20):  # Check for up to 10 minutes
        status, conclusion = check_ci_status()

        if status == "completed":
            if conclusion == "success":
                print("✅ CI PASSED! All checks are green!")
                return True
            print(f"❌ CI FAILED with conclusion: {conclusion}")
            return False

        print(f"⏳ CI still running... (check {i + 1}/20)")
        time.sleep(30)  # Wait 30 seconds between checks

    print("⏰ Timeout waiting for CI completion")
    return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
