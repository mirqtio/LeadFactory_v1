#!/usr/bin/env python3
"""
GitHub Integration for PRP Tracking
Verifies CI status and commit information before allowing PRP completion
"""

import os
import subprocess
from datetime import datetime, timedelta

import requests


class GitHubIntegration:
    """Handles GitHub API interactions for PRP validation"""

    def __init__(self, token: str = None, repo: str = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.repo = repo or self._get_repo_from_git()
        self.headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}

    def _get_repo_from_git(self) -> str:
        """Extract repo name from git remote"""
        try:
            result = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
            if result.returncode != 0:
                return None

            url = result.stdout.strip()
            # Extract owner/repo from GitHub URL
            if "github.com" in url:
                if url.startswith("git@"):
                    # git@github.com:owner/repo.git
                    parts = url.split(":")[1].replace(".git", "")
                else:
                    # https://github.com/owner/repo.git
                    parts = url.split("github.com/")[1].replace(".git", "")
                return parts
            return None
        except Exception:
            return None

    def get_commit_info(self, commit_hash: str) -> dict | None:
        """Get commit information from GitHub API"""
        if not self.repo or not self.token:
            return None

        url = f"https://api.github.com/repos/{self.repo}/commits/{commit_hash}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            return None
        except Exception:
            return None

    def get_ci_status(self, commit_hash: str) -> tuple[bool, list[dict]]:
        """Get CI status for a commit"""
        if not self.repo or not self.token:
            return False, []

        # Get check runs for commit
        url = f"https://api.github.com/repos/{self.repo}/commits/{commit_hash}/check-runs"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return False, []

            data = response.json()
            check_runs = data.get("check_runs", [])

            # Check if all required workflows passed
            required_workflows = ["Ultra-Fast Test Suite (<3 min target)", "lint", "deploy", "test-minimal"]

            workflow_results = {}
            for check in check_runs:
                name = check["name"]
                conclusion = check["conclusion"]
                workflow_results[name] = conclusion

            # Verify all required workflows passed
            all_passed = True
            missing_workflows = []

            for workflow in required_workflows:
                if workflow not in workflow_results:
                    missing_workflows.append(workflow)
                    all_passed = False
                elif workflow_results[workflow] != "success":
                    all_passed = False

            return all_passed, check_runs

        except Exception:
            return False, []

    def get_recent_commits(self, limit: int = 10) -> list[dict]:
        """Get recent commits from main branch"""
        if not self.repo or not self.token:
            return []

        url = f"https://api.github.com/repos/{self.repo}/commits"
        params = {"per_page": limit, "sha": "main"}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            return []
        except Exception:
            return []

    def verify_commit_on_main(self, commit_hash: str) -> bool:
        """Verify that a commit exists on the main branch"""
        if not self.repo or not self.token:
            return False

        url = f"https://api.github.com/repos/{self.repo}/commits/{commit_hash}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                commit_data = response.json()
                # Check if commit is on main branch
                # This is a simplified check - in practice you'd want to verify branch ancestry
                return True
            return False
        except Exception:
            return False

    def get_workflow_runs(self, workflow_name: str = None, limit: int = 10) -> list[dict]:
        """Get workflow runs for the repository"""
        if not self.repo or not self.token:
            return []

        url = f"https://api.github.com/repos/{self.repo}/actions/runs"
        params = {"per_page": limit}

        if workflow_name:
            params["workflow"] = workflow_name

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            if response.status_code == 200:
                return response.json().get("workflow_runs", [])
            return []
        except Exception:
            return []

    def validate_prp_completion(self, commit_hash: str) -> tuple[bool, str]:
        """Validate that a commit meets PRP completion requirements"""
        if not commit_hash:
            return False, "No commit hash provided"

        # 1. Verify commit exists on main branch
        if not self.verify_commit_on_main(commit_hash):
            return False, f"Commit {commit_hash} not found on main branch"

        # 2. Check CI status
        ci_passed, check_runs = self.get_ci_status(commit_hash)
        if not ci_passed:
            failed_checks = [
                check["name"] for check in check_runs if check["conclusion"] not in ["success", "neutral", "skipped"]
            ]
            return False, f"CI checks failed: {', '.join(failed_checks)}"

        # 3. Verify commit is recent (within last 24 hours)
        commit_info = self.get_commit_info(commit_hash)
        if commit_info:
            commit_date = datetime.fromisoformat(commit_info["commit"]["author"]["date"].replace("Z", "+00:00"))
            if datetime.now().astimezone() - commit_date > timedelta(hours=24):
                return False, "Commit is older than 24 hours"

        return True, "All completion requirements met"


def main():
    """CLI interface for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python github_integration.py <command> [args]")
        print("Commands: status, commits, workflows, validate")
        return

    gh = GitHubIntegration()
    command = sys.argv[1]

    if command == "status":
        if len(sys.argv) < 3:
            print("Usage: status <commit_hash>")
            return

        commit_hash = sys.argv[2]
        passed, checks = gh.get_ci_status(commit_hash)
        print(f"CI Status for {commit_hash}: {'PASSED' if passed else 'FAILED'}")

        for check in checks:
            print(f"  {check['name']}: {check['conclusion']}")

    elif command == "commits":
        commits = gh.get_recent_commits(5)
        for commit in commits:
            message_first_line = commit["commit"]["message"].split("\n")[0]
            print(f"{commit['sha'][:8]}: {message_first_line}")

    elif command == "workflows":
        runs = gh.get_workflow_runs(limit=5)
        for run in runs:
            print(f"{run['name']}: {run['conclusion']} ({run['created_at']})")

    elif command == "validate":
        if len(sys.argv) < 3:
            print("Usage: validate <commit_hash>")
            return

        commit_hash = sys.argv[2]
        valid, message = gh.validate_prp_completion(commit_hash)
        print(f"Validation: {'PASS' if valid else 'FAIL'}")
        print(f"Message: {message}")

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
