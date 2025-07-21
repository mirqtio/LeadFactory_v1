#!/usr/bin/env python3
"""
Pre-commit Hook for PRP Status Validation
Prevents commits that would violate PRP state management rules
"""

import os
import re
import subprocess
import sys

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prp_state_manager import PRPStateManager, PRPStatus


class PRPPreCommitHook:
    """Pre-commit hook for PRP validation"""

    def __init__(self):
        self.prp_manager = PRPStateManager()
        self.commit_message = self._get_commit_message()
        self.modified_files = self._get_modified_files()

    def _get_commit_message(self) -> str:
        """Get the commit message from git"""
        try:
            # Check if this is an amend commit
            if os.path.exists(".git/COMMIT_EDITMSG"):
                with open(".git/COMMIT_EDITMSG") as f:
                    return f.read().strip()

            # Fallback to git log
            result = subprocess.run(["git", "log", "-1", "--pretty=%B"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()

            return ""
        except Exception:
            return ""

    def _get_modified_files(self) -> list[str]:
        """Get list of modified files in this commit"""
        try:
            result = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split("\n")
            return []
        except Exception:
            return []

    def _extract_prp_from_commit(self) -> str | None:
        """Extract PRP ID from commit message"""
        # Look for patterns like "feat(P1-020):" or "fix(P2-000):"
        patterns = [
            r"\\b(P[0-9]+-[0-9]+)\\b",  # P1-020, P2-000, etc.
            r"feat\\((P[0-9]+-[0-9]+)\\):",  # feat(P1-020):
            r"fix\\((P[0-9]+-[0-9]+)\\):",  # fix(P1-020):
        ]

        for pattern in patterns:
            match = re.search(pattern, self.commit_message, re.IGNORECASE)
            if match:
                return match.group(1).upper()

        return None

    def _validate_prp_status_file_changes(self) -> tuple[bool, str]:
        """Validate changes to PRP status file"""
        status_file = ".claude/prp_tracking/prp_status.yaml"

        if status_file in self.modified_files:
            # PRP status file is being modified
            # This should only happen through our managed commands

            # Check if this is a system commit (automated)
            if "PRP Status Update:" in self.commit_message:
                return True, "Automated PRP status update"

            # Manual changes to status file are not allowed
            return False, (
                "Manual changes to prp_status.yaml are not allowed. Use 'claude-prp' commands to update PRP status."
            )

        return True, "No PRP status file changes"

    def _validate_prp_completion_commit(self, prp_id: str) -> tuple[bool, str]:
        """Validate that a PRP completion commit meets requirements"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            return False, f"PRP {prp_id} not found"

        # Check if PRP is in the right state for completion
        if prp.status != PRPStatus.IN_PROGRESS:
            return False, f"PRP {prp_id} must be in 'in_progress' state to complete"

        # Validate commit message format for completion
        completion_patterns = [
            r"feat\\(" + prp_id + r"\\):.*complete",
            r"fix\\(" + prp_id + r"\\):.*complete",
            r"Complete " + prp_id,
        ]

        is_completion_commit = any(
            re.search(pattern, self.commit_message, re.IGNORECASE) for pattern in completion_patterns
        )

        if is_completion_commit:
            # This looks like a completion commit
            # Validate that BPCI passes
            if not self._validate_bpci():
                return False, (
                    f"PRP {prp_id} completion commit blocked: BPCI validation failed. "
                    "Run 'make bpci' to fix issues before committing."
                )

        return True, "PRP commit validation passed"

    def _validate_bpci(self) -> bool:
        """Validate that BPCI passes"""
        try:
            # Run quick validation first
            result = subprocess.run(["make", "quick-check"], capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def _validate_work_on_in_progress_prp(self, prp_id: str) -> tuple[bool, str]:
        """Validate that work is being done on a PRP that's in progress"""
        prp = self.prp_manager.get_prp(prp_id)
        if not prp:
            return False, f"PRP {prp_id} not found"

        # Only allow commits on PRPs that are in progress
        if prp.status != PRPStatus.IN_PROGRESS:
            return False, (
                f"Cannot commit work on PRP {prp_id} (status: {prp.status.value}). "
                f"PRP must be in 'in_progress' state. "
                f"Use 'claude-prp start {prp_id}' to begin work."
            )

        return True, f"Work on PRP {prp_id} is allowed"

    def run_validation(self) -> tuple[bool, str]:
        """Run all pre-commit validations"""
        # 1. Check PRP status file changes
        valid, message = self._validate_prp_status_file_changes()
        if not valid:
            return False, message

        # 2. Extract PRP from commit message
        prp_id = self._extract_prp_from_commit()
        if not prp_id:
            # No PRP in commit message - allow commit
            return True, "No PRP detected in commit message"

        # 3. Validate PRP exists and is in correct state
        valid, message = self._validate_work_on_in_progress_prp(prp_id)
        if not valid:
            return False, message

        # 4. If this looks like a completion commit, validate completion requirements
        valid, message = self._validate_prp_completion_commit(prp_id)
        if not valid:
            return False, message

        return True, f"Pre-commit validation passed for PRP {prp_id}"


def main():
    """Main entry point for pre-commit hook"""
    try:
        hook = PRPPreCommitHook()
        valid, message = hook.run_validation()

        if valid:
            print(f"✅ PRP Pre-commit Hook: {message}")
            sys.exit(0)
        else:
            print(f"❌ PRP Pre-commit Hook BLOCKED: {message}")
            print("\\nTo fix this issue:")
            print("1. Check PRP status with: python .claude/prp_tracking/prp_state_manager.py status <prp_id>")
            print("2. Start PRP if needed: python .claude/prp_tracking/cli_commands.py start <prp_id>")
            print("3. Run validation: make quick-check")
            sys.exit(1)

    except Exception as e:
        print(f"❌ PRP Pre-commit Hook ERROR: {e}")
        print("Hook failed - allowing commit to proceed (fail-safe mode)")
        sys.exit(0)  # Fail-safe: allow commit if hook errors


if __name__ == "__main__":
    main()
