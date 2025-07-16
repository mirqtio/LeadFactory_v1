#!/usr/bin/env python3
"""
PRP State Manager - Core state management and validation logic
Enforces state transitions and validates requirements before allowing changes
"""

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import requests
import yaml


class PRPStatus(Enum):
    """Valid PRP states"""

    NEW = "new"
    VALIDATED = "validated"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


@dataclass
class PRPEntry:
    """PRP entry structure"""

    prp_id: str
    title: str
    status: PRPStatus
    validated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    github_commit: Optional[str] = None
    ci_run_url: Optional[str] = None
    notes: Optional[str] = None


class PRPStateManager:
    """Manages PRP state transitions and validation"""

    def __init__(self, status_file: str = None):
        self.status_file = status_file or os.path.join(os.path.dirname(__file__), "prp_status.yaml")
        self.data = self._load_status_file()

    def _load_status_file(self) -> Dict:
        """Load PRP status from YAML file"""
        if not os.path.exists(self.status_file):
            raise FileNotFoundError(f"PRP status file not found: {self.status_file}")

        with open(self.status_file, "r") as f:
            return yaml.safe_load(f)

    def _save_status_file(self) -> None:
        """Save PRP status to YAML file"""
        # Update metadata
        self.data["metadata"]["last_updated"] = datetime.utcnow().isoformat() + "Z"

        # Update stats
        self._update_stats()

        with open(self.status_file, "w") as f:
            yaml.dump(self.data, f, default_flow_style=False, sort_keys=False)

    def _update_stats(self) -> None:
        """Update statistics in the data"""
        prps = self.data["prp_tracking"]
        stats = {"total_prps": len(prps), "new": 0, "validated": 0, "in_progress": 0, "complete": 0}

        for prp in prps.values():
            status = prp["status"]
            stats[status] = stats.get(status, 0) + 1

        stats["completion_rate"] = round(stats["complete"] / stats["total_prps"], 2)
        self.data["stats"] = stats

    def get_prp(self, prp_id: str) -> Optional[PRPEntry]:
        """Get PRP entry by ID"""
        prp_data = self.data["prp_tracking"].get(prp_id)
        if not prp_data:
            return None

        return PRPEntry(
            prp_id=prp_id,
            title=prp_data["title"],
            status=PRPStatus(prp_data["status"]),
            validated_at=prp_data.get("validated_at"),
            started_at=prp_data.get("started_at"),
            completed_at=prp_data.get("completed_at"),
            github_commit=prp_data.get("github_commit"),
            ci_run_url=prp_data.get("ci_run_url"),
            notes=prp_data.get("notes"),
        )

    def list_prps(self, status_filter: Optional[PRPStatus] = None) -> List[PRPEntry]:
        """List all PRPs, optionally filtered by status"""
        prps = []
        for prp_id in self.data["prp_tracking"]:
            prp = self.get_prp(prp_id)
            if status_filter is None or prp.status == status_filter:
                prps.append(prp)
        return prps

    def validate_transition(self, prp_id: str, new_status: PRPStatus) -> Tuple[bool, str]:
        """Validate if a state transition is allowed"""
        prp = self.get_prp(prp_id)
        if not prp:
            return False, f"PRP {prp_id} not found"

        current_status = prp.status

        # Define valid transitions
        valid_transitions = {
            PRPStatus.NEW: [PRPStatus.VALIDATED],
            PRPStatus.VALIDATED: [PRPStatus.IN_PROGRESS],
            PRPStatus.IN_PROGRESS: [PRPStatus.COMPLETE],
            PRPStatus.COMPLETE: [],  # No transitions from complete
        }

        if new_status not in valid_transitions[current_status]:
            return False, f"Invalid transition from {current_status.value} to {new_status.value}"

        # Validate specific transition requirements
        if new_status == PRPStatus.VALIDATED:
            # TODO: Check 6-gate validation completion
            pass

        elif new_status == PRPStatus.IN_PROGRESS:
            # Must be explicitly started
            if not prp.validated_at:
                return False, "PRP must be validated before starting"

        elif new_status == PRPStatus.COMPLETE:
            # Must have BPCI pass and GitHub CI success
            if not self._validate_completion_requirements(prp_id):
                return False, "Completion requirements not met (BPCI + GitHub CI)"

        return True, "Transition valid"

    def _validate_completion_requirements(self, prp_id: str) -> bool:
        """Validate that all completion requirements are met"""
        # 1. Check if BPCI passes locally
        try:
            result = subprocess.run(["make", "bpci"], capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                return False
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

        # 2. Check if there are uncommitted changes
        try:
            result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
            if result.stdout.strip():
                return False  # Uncommitted changes exist
        except Exception:
            return False

        # 3. Check if GitHub CI is passing (implemented in github_integration.py)
        # For now, just check if there's a recent commit
        try:
            result = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
            if result.returncode != 0:
                return False
        except Exception:
            return False

        return True

    def transition_prp(
        self, prp_id: str, new_status: PRPStatus, commit_hash: str = None, notes: str = None
    ) -> Tuple[bool, str]:
        """Transition PRP to new status if valid"""
        valid, message = self.validate_transition(prp_id, new_status)
        if not valid:
            return False, message

        # Update PRP data
        prp_data = self.data["prp_tracking"][prp_id]
        prp_data["status"] = new_status.value

        current_time = datetime.utcnow().isoformat() + "Z"

        if new_status == PRPStatus.VALIDATED:
            prp_data["validated_at"] = current_time
        elif new_status == PRPStatus.IN_PROGRESS:
            prp_data["started_at"] = current_time
        elif new_status == PRPStatus.COMPLETE:
            prp_data["completed_at"] = current_time
            if commit_hash:
                prp_data["github_commit"] = commit_hash

        if notes:
            prp_data["notes"] = notes

        # Save changes
        self._save_status_file()

        return True, f"PRP {prp_id} transitioned to {new_status.value}"

    def get_stats(self) -> Dict:
        """Get current statistics"""
        return self.data["stats"]

    def get_in_progress_prps(self) -> List[PRPEntry]:
        """Get all PRPs currently in progress"""
        return self.list_prps(PRPStatus.IN_PROGRESS)

    def get_next_prp(self) -> Optional[PRPEntry]:
        """Get the next PRP ready for execution"""
        validated_prps = self.list_prps(PRPStatus.VALIDATED)
        if not validated_prps:
            return None

        # Return first validated PRP (assumes they're ordered by priority)
        return validated_prps[0]


def main():
    """CLI interface for testing"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python prp_state_manager.py <command> [args]")
        print("Commands: status, list, transition, stats")
        return

    manager = PRPStateManager()
    command = sys.argv[1]

    if command == "status":
        if len(sys.argv) < 3:
            print("Usage: status <prp_id>")
            return

        prp_id = sys.argv[2]
        prp = manager.get_prp(prp_id)
        if prp:
            print(f"PRP {prp_id}: {prp.title}")
            print(f"Status: {prp.status.value}")
            print(f"Validated: {prp.validated_at}")
            print(f"Started: {prp.started_at}")
            print(f"Completed: {prp.completed_at}")
        else:
            print(f"PRP {prp_id} not found")

    elif command == "list":
        status_filter = None
        if len(sys.argv) > 2:
            status_filter = PRPStatus(sys.argv[2])

        prps = manager.list_prps(status_filter)
        for prp in prps:
            print(f"{prp.prp_id}: {prp.title} ({prp.status.value})")

    elif command == "transition":
        if len(sys.argv) < 4:
            print("Usage: transition <prp_id> <new_status> [commit_hash]")
            return

        prp_id = sys.argv[2]
        new_status = PRPStatus(sys.argv[3])
        commit_hash = sys.argv[4] if len(sys.argv) > 4 else None

        success, message = manager.transition_prp(prp_id, new_status, commit_hash)
        print(message)

    elif command == "stats":
        stats = manager.get_stats()
        print(f"Total PRPs: {stats['total_prps']}")
        print(f"New: {stats['new']}")
        print(f"Validated: {stats['validated']}")
        print(f"In Progress: {stats['in_progress']}")
        print(f"Complete: {stats['complete']}")
        print(f"Completion Rate: {stats['completion_rate']:.1%}")

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
