#!/usr/bin/env python3
"""
Monitor GitHub workflows for a specific commit and wait for completion
"""
import json
import logging
import subprocess
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("workflow_monitor")


def run_command(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, check=False)
    return result


def wait_for_workflows_and_fix(commit_sha, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        logger.info(f"🔄 Monitoring workflows for {commit_sha} - attempt {attempt}/{max_attempts}")

        # Wait for workflows to start
        time.sleep(30)

        # Check workflow status
        result = run_command(f"gh run list --limit 10 --json status,conclusion,workflowName,databaseId,headSha")
        if result.returncode == 0:
            runs = json.loads(result.stdout)
            matching_runs = [run for run in runs if run.get("headSha") == commit_sha]

            if not matching_runs:
                logger.info("No workflows found yet, waiting...")
                continue

            logger.info(f"Found {len(matching_runs)} workflows for this commit")
            for run in matching_runs:
                logger.info(f'- {run["workflowName"]}: {run["status"]} ({run.get("conclusion", "pending")})')

            all_complete = all(run["status"] == "completed" for run in matching_runs)
            if not all_complete:
                logger.info("Workflows still running...")
                continue

            # Check results
            failed_runs = [run for run in matching_runs if run["conclusion"] != "success"]
            passed_runs = [run for run in matching_runs if run["conclusion"] == "success"]

            logger.info(f"✅ {len(passed_runs)} workflows passed")
            logger.info(f"❌ {len(failed_runs)} workflows failed")

            if not failed_runs:
                logger.info("🎉 ALL WORKFLOWS PASSED!")
                return True

            logger.warning(f"Some workflows failed, analyzing...")
            for run in failed_runs:
                logger.warning(f'FAILED: {run["workflowName"]} (ID: {run["databaseId"]})')

    return False


if __name__ == "__main__":
    commit = sys.argv[1] if len(sys.argv) > 1 else "028d7e8f86a7afaa09bd67b74a72ee1aca126159"
    logger.info(f"Starting workflow monitor for commit: {commit}")
    success = wait_for_workflows_and_fix(commit)
    logger.info(f'Final result: {"SUCCESS" if success else "FAILED"}')
    sys.exit(0 if success else 1)
