#!/usr/bin/env python3
"""
Add Phase 0.5 tasks to the task planning system
"""

import json
from datetime import datetime
from pathlib import Path


def add_phase_05_tasks():
    """Add Phase 0.5 tasks to task_status.json"""

    # Read current task status
    status_file = Path("planning/task_status.json")
    with open(status_file) as f:
        task_status = json.load(f)

    # Read Phase 0.5 tasks
    phase_05_file = Path("planning/phase_0.5_tasks.json")
    with open(phase_05_file) as f:
        phase_05 = json.load(f)

    # Add new tasks to status
    new_tasks = {}
    for phase in phase_05["phases"]:
        for task in phase["tasks"]:
            task_id = task["id"]
            new_tasks[task_id] = {
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "actual_hours": None,
                "phase": "0.5",
                "title": task["title"],
                "domain": task["domain"],
                "estimated_hours": task["estimated_hours"],
            }

    # Update task status
    task_status["tasks"].update(new_tasks)
    task_status["last_updated"] = datetime.utcnow().isoformat()
    task_status["phase_0.5_added"] = True

    # Write back
    with open(status_file, "w") as f:
        json.dump(task_status, f, indent=2)

    print(f"✅ Added {len(new_tasks)} Phase 0.5 tasks to task_status.json")

    # Create a summary
    print("\n📋 Phase 0.5 Task Summary:")
    print("-" * 50)
    for task_id, task in new_tasks.items():
        print(f"{task_id}: {task['title']} ({task['estimated_hours']}h)")
    print("-" * 50)
    print(f"Total estimated hours: {phase_05['summary']['total_estimated_hours']}")

    # Update taskmaster_plan.json to include Phase 0.5
    taskmaster_file = Path("taskmaster_plan.json")
    if taskmaster_file.exists():
        with open(taskmaster_file) as f:
            taskmaster = json.load(f)

        # Add Phase 0.5 as a new phase
        phase_05_phase = {
            "phase": "0.5",
            "name": "Delta Enhancements",
            "description": "Close functional gaps with new providers, cost tracking, and bucket intelligence",
            "tasks": [],
        }

        # Convert tasks to taskmaster format
        for task in phase_05["phases"][0]["tasks"]:
            tm_task = {
                "id": task["id"],
                "title": task["title"],
                "domain": task["domain"],
                "complexity": task["complexity"],
                "dependencies": task["dependencies"],
                "estimated_hours": task["estimated_hours"],
                "acceptance_criteria": task["acceptance_criteria"],
            }

            # Add test requirements if present
            if "test_requirements" in task:
                tm_task["test_requirements"] = task["test_requirements"]

            # Add file information
            if "files_to_create" in task:
                tm_task["files_to_create"] = task["files_to_create"]
            if "files_to_update" in task:
                tm_task["files_to_update"] = task["files_to_update"]

            phase_05_phase["tasks"].append(tm_task)

        # Insert Phase 0.5 after Phase 15 (deployment)
        taskmaster["phases"].append(phase_05_phase)
        taskmaster["total_tasks"] += len(phase_05_phase["tasks"])

        with open(taskmaster_file, "w") as f:
            json.dump(taskmaster, f, indent=2)

        print("\n✅ Updated taskmaster_plan.json with Phase 0.5")


def create_phase_05_tracker():
    """Create a separate tracker for Phase 0.5 progress"""
    tracker = {
        "phase": "0.5",
        "name": "Delta Enhancements",
        "started_at": datetime.utcnow().isoformat(),
        "status": "ready",
        "progress": {
            "total_tasks": 12,
            "completed": 0,
            "in_progress": 0,
            "pending": 12,
        },
        "key_milestones": [
            {
                "milestone": "Providers Integrated",
                "tasks": ["DX-01", "GW-02", "GW-03"],
                "status": "pending",
            },
            {
                "milestone": "Cost Tracking Live",
                "tasks": ["GW-04", "AN-08", "OR-09"],
                "status": "pending",
            },
            {
                "milestone": "Bucket Intelligence",
                "tasks": ["TG-06", "ET-07"],
                "status": "pending",
            },
            {
                "milestone": "Full Testing",
                "tasks": ["TS-10", "DOC-11", "NB-12"],
                "status": "pending",
            },
        ],
    }

    tracker_file = Path("planning/phase_05_progress.json")
    with open(tracker_file, "w") as f:
        json.dump(tracker, f, indent=2)

    print("\n✅ Created phase_05_progress.json tracker")


if __name__ == "__main__":
    add_phase_05_tasks()
    create_phase_05_tracker()

    print("\n🎯 Next Steps:")
    print("1. Run 'python planning/get_next_task.py' to see Phase 0.5 tasks")
    print("2. Start with DX-01 (config setup)")
    print("3. Update .env with new provider keys when ready")
