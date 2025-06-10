#!/usr/bin/env python3
"""
Script to get the next gap remediation task to work on.
Follows the same pattern as get_next_task.py but for gap remediation.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Color codes for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


class GapTaskManager:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.gap_plan_path = self.project_root / "taskmaster_gap_remediation.json"
        self.status_path = Path(__file__).parent / "gap_remediation_status.json"

    def load_gap_plan(self) -> Dict:
        """Load the gap remediation plan"""
        with open(self.gap_plan_path, "r") as f:
            return json.load(f)

    def load_status(self) -> Dict:
        """Load current status of gap tasks"""
        with open(self.status_path, "r") as f:
            return json.load(f)

    def save_status(self, status: Dict):
        """Save updated status"""
        status["last_updated"] = datetime.utcnow().isoformat()
        with open(self.status_path, "w") as f:
            json.dump(status, f, indent=2)

    def get_task_details(self, task_id: str) -> Optional[Dict]:
        """Get details for a specific task from the plan"""
        plan = self.load_gap_plan()
        for phase in plan["phases"]:
            for task in phase["tasks"]:
                if task["id"] == task_id:
                    return task
        return None

    def check_dependencies(self, task: Dict, status: Dict) -> Tuple[bool, List[str]]:
        """Check if all dependencies are completed"""
        unmet_deps = []
        for dep_id in task.get("dependencies", []):
            if dep_id in status["tasks"]:
                if status["tasks"][dep_id]["status"] != "completed":
                    unmet_deps.append(dep_id)
        return len(unmet_deps) == 0, unmet_deps

    def get_next_task(self) -> Optional[str]:
        """Get the next task to work on based on priority and dependencies"""
        status = self.load_status()
        plan = self.load_gap_plan()

        # Group tasks by priority
        p0_tasks = []
        p1_tasks = []
        p2_tasks = []

        for phase in plan["phases"]:
            for task in phase["tasks"]:
                task_id = task["id"]
                task_status = status["tasks"].get(task_id, {})

                # Skip completed or in-progress tasks
                if task_status.get("status") in ["completed", "in_progress"]:
                    continue

                # Check dependencies
                deps_met, unmet_deps = self.check_dependencies(task, status)
                if not deps_met:
                    continue

                # Add to appropriate priority list
                priority = task.get("priority", "P2")
                if priority == "P0":
                    p0_tasks.append(task_id)
                elif priority == "P1":
                    p1_tasks.append(task_id)
                else:
                    p2_tasks.append(task_id)

        # Return highest priority task
        if p0_tasks:
            return p0_tasks[0]
        elif p1_tasks:
            return p1_tasks[0]
        elif p2_tasks:
            return p2_tasks[0]
        else:
            return None

    def print_task_details(self, task_id: str):
        """Print detailed information about a task"""
        task = self.get_task_details(task_id)
        if not task:
            print(f"{RED}Task {task_id} not found!{RESET}")
            return

        print(f"\n{BOLD}Task Details:{RESET}")
        print(f"ID: {BLUE}{task['id']}{RESET}")
        print(f"Title: {task['title']}")
        print(f"Domain: {task['domain']}")
        print(
            f"Priority: {RED if task['priority'] == 'P0' else YELLOW}{task['priority']}{RESET}"
        )
        print(f"Complexity: {task['complexity']}")
        print(f"Estimated Hours: {task['estimated_hours']}")

        if task.get("dependencies"):
            print(f"\nDependencies: {', '.join(task['dependencies'])}")

        print(f"\n{BOLD}Acceptance Criteria:{RESET}")
        for criterion in task["acceptance_criteria"]:
            print(f"  • {criterion}")

        if task.get("files_to_create"):
            print(f"\n{BOLD}Files to Create:{RESET}")
            for file in task["files_to_create"]:
                print(f"  • {file}")

        if task.get("files_to_modify"):
            print(f"\n{BOLD}Files to Modify:{RESET}")
            for file in task["files_to_modify"]:
                print(f"  • {file}")

        if task.get("test_requirements"):
            print(f"\n{BOLD}Test Requirements:{RESET}")
            test_req = task["test_requirements"]
            print(
                f"  Docker Test: {GREEN if test_req.get('docker_test') else RED}{'Yes' if test_req.get('docker_test') else 'No'}{RESET}"
            )
            if test_req.get("files"):
                print(f"  Test Files: {', '.join(test_req['files'])}")
            if test_req.get("commands"):
                print(f"  Test Commands:")
                for cmd in test_req["commands"]:
                    print(f"    $ {cmd}")

    def print_progress(self):
        """Print overall progress"""
        status = self.load_status()

        total = len(status["tasks"])
        completed = sum(
            1 for t in status["tasks"].values() if t["status"] == "completed"
        )
        in_progress = sum(
            1 for t in status["tasks"].values() if t["status"] == "in_progress"
        )
        pending = total - completed - in_progress

        print(f"\n{BOLD}Gap Remediation Progress:{RESET}")
        print(f"Total Tasks: {total}")
        print(f"Completed: {GREEN}{completed}{RESET}")
        print(f"In Progress: {YELLOW}{in_progress}{RESET}")
        print(f"Pending: {RED}{pending}{RESET}")
        print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)")

        # Show breakdown by priority
        p0_complete = sum(
            1
            for t in status["tasks"].values()
            if t["status"] == "completed" and t["priority"] == "P0"
        )
        p0_total = status["summary"]["P0_tasks"]

        print(f"\n{BOLD}Priority Breakdown:{RESET}")
        print(f"P0 (Critical): {p0_complete}/{p0_total} complete")
        print(
            f"P1 (High): {sum(1 for t in status['tasks'].values() if t['status'] == 'completed' and t['priority'] == 'P1')}/{status['summary']['P1_tasks']} complete"
        )
        print(
            f"P2 (Medium): {sum(1 for t in status['tasks'].values() if t['status'] == 'completed' and t['priority'] == 'P2')}/{status['summary']['P2_tasks']} complete"
        )

    def update_task_status(self, task_id: str, new_status: str):
        """Update the status of a task"""
        status = self.load_status()

        if task_id not in status["tasks"]:
            print(f"{RED}Task {task_id} not found!{RESET}")
            return

        old_status = status["tasks"][task_id]["status"]
        status["tasks"][task_id]["status"] = new_status

        # Update timestamps
        if new_status == "in_progress" and old_status != "in_progress":
            status["tasks"][task_id]["started_at"] = datetime.utcnow().isoformat()
        elif new_status == "completed":
            status["tasks"][task_id]["completed_at"] = datetime.utcnow().isoformat()

        # Set remediation started flag
        if new_status == "in_progress" and not status.get("remediation_started"):
            status["remediation_started"] = True

        self.save_status(status)
        print(f"{GREEN}Updated {task_id} from '{old_status}' to '{new_status}'{RESET}")


def main():
    manager = GapTaskManager()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--progress":
            manager.print_progress()
        elif sys.argv[1] == "--update" and len(sys.argv) == 4:
            task_id = sys.argv[2]
            new_status = sys.argv[3]
            if new_status not in ["pending", "in_progress", "completed", "blocked"]:
                print(
                    f"{RED}Invalid status. Use: pending, in_progress, completed, or blocked{RESET}"
                )
                return
            manager.update_task_status(task_id, new_status)
        elif sys.argv[1] == "--details" and len(sys.argv) == 3:
            task_id = sys.argv[2]
            manager.print_task_details(task_id)
        else:
            print("Usage:")
            print(
                "  python get_next_gap_task.py              - Get next task to work on"
            )
            print("  python get_next_gap_task.py --progress   - Show overall progress")
            print(
                "  python get_next_gap_task.py --update TASK_ID STATUS - Update task status"
            )
            print("  python get_next_gap_task.py --details TASK_ID - Show task details")
    else:
        # Get next task
        next_task = manager.get_next_task()
        if next_task:
            print(f"\n{BOLD}Next Gap Remediation Task:{RESET}")
            manager.print_task_details(next_task)
            print(f"\n{YELLOW}To start this task, run:{RESET}")
            print(
                f"  python planning/get_next_gap_task.py --update {next_task} in_progress"
            )
        else:
            print(
                f"{GREEN}All gap remediation tasks are either completed or blocked!{RESET}"
            )
            manager.print_progress()


if __name__ == "__main__":
    main()
