#!/usr/bin/env python3
"""
Gap Remediation Planning Tool

This tool manages the execution of gap remediation tasks identified in the
gap analysis. It follows the same workflow as the main task system but
focuses on closing implementation gaps.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Load gap remediation tasks
GAP_TASKS_FILE = Path(__file__).parent.parent / "gap_remediation_tasks.json"
STATUS_FILE = Path(__file__).parent / "gap_remediation_status.json"


def load_gap_tasks() -> dict:
    """Load gap remediation tasks from JSON file"""
    with open(GAP_TASKS_FILE) as f:
        return json.load(f)


def load_status() -> dict:
    """Load current status of gap tasks"""
    if STATUS_FILE.exists():
        with open(STATUS_FILE) as f:
            return json.load(f)
    else:
        # Initialize status file
        gap_tasks = load_gap_tasks()
        status = {"last_updated": datetime.now().isoformat(), "tasks": {}}

        for phase in gap_tasks["phases"]:
            for task in phase["tasks"]:
                status["tasks"][task["id"]] = {
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "actual_hours": None,
                }

        save_status(status)
        return status


def save_status(status: dict) -> None:
    """Save status to file"""
    status["last_updated"] = datetime.now().isoformat()
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)


def get_next_task() -> dict | None:
    """Get the next task to work on based on priority and dependencies"""
    gap_tasks = load_gap_tasks()
    status = load_status()

    # Priority order: critical > high > medium > low
    priority_order = ["critical", "high", "medium", "low"]

    for priority in priority_order:
        for phase in gap_tasks["phases"]:
            for task in phase["tasks"]:
                if task["priority"] != priority:
                    continue

                task_status = status["tasks"].get(task["id"], {})
                if task_status.get("status") == "pending":
                    # Check if any dependencies exist (could be extended)
                    # For now, we'll process tasks in order within priority
                    return task

    return None


def mark_task_status(task_id: str, new_status: str) -> None:
    """Update task status"""
    status = load_status()

    if task_id not in status["tasks"]:
        print(f"Error: Task {task_id} not found")
        return

    task_status = status["tasks"][task_id]
    task_status["status"] = new_status

    if new_status == "in_progress":
        task_status["started_at"] = datetime.now().isoformat()
    elif new_status == "completed":
        task_status["completed_at"] = datetime.now().isoformat()
        if task_status["started_at"]:
            start = datetime.fromisoformat(task_status["started_at"])
            end = datetime.now()
            task_status["actual_hours"] = (end - start).total_seconds() / 3600

    save_status(status)
    print(f"Task {task_id} marked as {new_status}")


def get_progress_summary() -> dict:
    """Get summary of gap remediation progress"""
    gap_tasks = load_gap_tasks()
    status = load_status()

    total_tasks = len(status["tasks"])
    completed = sum(1 for t in status["tasks"].values() if t["status"] == "completed")
    in_progress = sum(1 for t in status["tasks"].values() if t["status"] == "in_progress")
    pending = sum(1 for t in status["tasks"].values() if t["status"] == "pending")

    # Calculate by priority
    by_priority = {
        "critical": {"total": 0, "completed": 0},
        "high": {"total": 0, "completed": 0},
        "medium": {"total": 0, "completed": 0},
        "low": {"total": 0, "completed": 0},
    }

    for phase in gap_tasks["phases"]:
        for task in phase["tasks"]:
            priority = task["priority"]
            by_priority[priority]["total"] += 1
            if status["tasks"][task["id"]]["status"] == "completed":
                by_priority[priority]["completed"] += 1

    return {
        "total_tasks": total_tasks,
        "completed": completed,
        "in_progress": in_progress,
        "pending": pending,
        "completion_percentage": round((completed / total_tasks) * 100, 1),
        "by_priority": by_priority,
    }


def display_next_task(task: dict) -> None:
    """Display task details in a formatted way"""
    print("\n" + "=" * 80)
    print(f"NEXT GAP REMEDIATION TASK: {task['id']}")
    print("=" * 80)
    print(f"\nTitle: {task['title']}")
    print(f"Domain: {task['domain']}")
    print(f"Priority: {task['priority'].upper()}")
    print(f"Estimated Hours: {task['estimated_hours']}")

    print("\nGap Description:")
    print(f"  {task['gap_description']}")

    print("\nCurrent State:")
    print(f"  {task['current_state']}")

    print("\nSuccess Criteria:")
    for criterion in task["success_criteria"]:
        print(f"  - {criterion}")

    if "files_to_create" in task:
        print("\nFiles to Create:")
        for file in task["files_to_create"]:
            print(f"  - {file}")

    if "files_to_modify" in task:
        print("\nFiles to Modify:")
        for file in task["files_to_modify"]:
            print(f"  - {file}")

    print("\nImplementation Notes:")
    print(f"  {task['implementation_notes']}")

    print("\nTest Commands:")
    for cmd in task["test_commands"]:
        print(f"  - {cmd}")

    print("\n" + "=" * 80)
    print("To start this task, run:")
    print(f"  python3 planning/gap_remediation_plan.py --update {task['id']} in_progress")
    print("=" * 80 + "\n")


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--progress":
            summary = get_progress_summary()
            print("\nGAP REMEDIATION PROGRESS")
            print("=" * 50)
            print(f"Total Tasks: {summary['total_tasks']}")
            print(f"Completed: {summary['completed']} ({summary['completion_percentage']}%)")
            print(f"In Progress: {summary['in_progress']}")
            print(f"Pending: {summary['pending']}")
            print("\nBy Priority:")
            for priority, stats in summary["by_priority"].items():
                print(f"  {priority.capitalize()}: {stats['completed']}/{stats['total']}")

        elif sys.argv[1] == "--update" and len(sys.argv) == 4:
            task_id = sys.argv[2]
            new_status = sys.argv[3]
            if new_status in ["pending", "in_progress", "completed"]:
                mark_task_status(task_id, new_status)
            else:
                print(f"Error: Invalid status '{new_status}'")
                print("Valid statuses: pending, in_progress, completed")

        elif sys.argv[1] == "--show" and len(sys.argv) == 3:
            task_id = sys.argv[2]
            gap_tasks = load_gap_tasks()
            found = False
            for phase in gap_tasks["phases"]:
                for task in phase["tasks"]:
                    if task["id"] == task_id:
                        display_next_task(task)
                        found = True
                        break
                if found:
                    break
            if not found:
                print(f"Error: Task {task_id} not found")

        else:
            print("Invalid command")
            print("Usage:")
            print("  python3 gap_remediation_plan.py              # Get next task")
            print("  python3 gap_remediation_plan.py --progress   # Show progress")
            print("  python3 gap_remediation_plan.py --update TASK_ID STATUS")
            print("  python3 gap_remediation_plan.py --show TASK_ID")
    else:
        # Get next task
        next_task = get_next_task()
        if next_task:
            display_next_task(next_task)
        else:
            print("\nAll gap remediation tasks completed! 🎉")
            summary = get_progress_summary()
            print(f"Total tasks completed: {summary['completed']}/{summary['total_tasks']}")


if __name__ == "__main__":
    main()
