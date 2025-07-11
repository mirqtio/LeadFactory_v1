#!/usr/bin/env python3
"""
Get next task to work on based on dependencies and current progress
"""
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class TaskManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.plan_file = self.base_dir / "taskmaster_plan.json"
        self.status_file = self.base_dir / "planning" / "task_status.json"

        # Load task plan
        with open(self.plan_file, "r") as f:
            self.plan = json.load(f)

        # Load or initialize task status
        if self.status_file.exists():
            with open(self.status_file, "r") as f:
                self.status = json.load(f)
        else:
            self.status = self._initialize_status()
            self._save_status()

    def _initialize_status(self) -> Dict:
        """Initialize task status from plan"""
        status = {"last_updated": datetime.now().isoformat(), "tasks": {}}

        for phase in self.plan["phases"]:
            for task in phase["tasks"]:
                status["tasks"][task["id"]] = {
                    "status": "pending",
                    "started_at": None,
                    "completed_at": None,
                    "actual_hours": None,
                }

        return status

    def _save_status(self):
        """Save status to file"""
        self.status["last_updated"] = datetime.now().isoformat()
        with open(self.status_file, "w") as f:
            json.dump(self.status, f, indent=2)

    def get_task_by_id(self, task_id: str) -> Optional[Dict]:
        """Get task details by ID"""
        for phase in self.plan["phases"]:
            for task in phase["tasks"]:
                if task["id"] == task_id:
                    return task
        return None

    def get_task_status(self, task_id: str) -> str:
        """Get current status of a task"""
        return self.status["tasks"].get(task_id, {}).get("status", "pending")

    def update_task_status(self, task_id: str, status: str):
        """Update task status"""
        if task_id not in self.status["tasks"]:
            print(f"Error: Task {task_id} not found")
            return

        valid_statuses = ["pending", "ready", "in_progress", "completed", "blocked"]
        if status not in valid_statuses:
            print(f"Error: Invalid status. Must be one of: {', '.join(valid_statuses)}")
            return

        old_status = self.status["tasks"][task_id]["status"]
        self.status["tasks"][task_id]["status"] = status

        # Track timestamps
        if status == "in_progress" and old_status != "in_progress":
            self.status["tasks"][task_id]["started_at"] = datetime.now().isoformat()
        elif status == "completed":
            self.status["tasks"][task_id]["completed_at"] = datetime.now().isoformat()

        self._save_status()
        print(f"Updated task {task_id}: {old_status} -> {status}")

    def check_dependencies_met(self, task: Dict) -> bool:
        """Check if all dependencies for a task are completed"""
        deps = task.get("dependencies", [])
        for dep_id in deps:
            if self.get_task_status(dep_id) != "completed":
                return False
        return True

    def get_next_tasks(self, limit: int = 5) -> List[Dict]:
        """Get next tasks that can be worked on"""
        ready_tasks = []
        in_progress_tasks = []

        for phase in self.plan["phases"]:
            for task in phase["tasks"]:
                status = self.get_task_status(task["id"])

                if status == "in_progress":
                    in_progress_tasks.append(task)
                elif status == "pending" and self.check_dependencies_met(task):
                    task["phase_name"] = phase["name"]
                    ready_tasks.append(task)

        # Return in-progress tasks first, then ready tasks
        return in_progress_tasks + ready_tasks[:limit]

    def get_progress_stats(self) -> Dict:
        """Get overall progress statistics"""
        stats = {
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "ready": 0,
            "pending": 0,
            "blocked": 0,
            "by_phase": {},
            "by_domain": {},
        }

        for phase in self.plan["phases"]:
            phase_stats = {"total": 0, "completed": 0}

            for task in phase["tasks"]:
                stats["total"] += 1
                phase_stats["total"] += 1

                status = self.get_task_status(task["id"])
                stats[status] = stats.get(status, 0) + 1

                if status == "completed":
                    phase_stats["completed"] += 1

                # Track by domain
                domain = task.get("domain", "unknown")
                if domain not in stats["by_domain"]:
                    stats["by_domain"][domain] = {"total": 0, "completed": 0}
                stats["by_domain"][domain]["total"] += 1
                if status == "completed":
                    stats["by_domain"][domain]["completed"] += 1

            stats["by_phase"][phase["name"]] = phase_stats

        # Check ready tasks
        ready_count = 0
        for phase in self.plan["phases"]:
            for task in phase["tasks"]:
                if self.get_task_status(
                    task["id"]
                ) == "pending" and self.check_dependencies_met(task):
                    ready_count += 1
        stats["ready"] = ready_count
        stats["pending"] -= ready_count

        return stats

    def verify_dependencies(self) -> List[str]:
        """Verify all dependencies are valid"""
        issues = []
        all_task_ids = set()

        # Collect all task IDs
        for phase in self.plan["phases"]:
            for task in phase["tasks"]:
                all_task_ids.add(task["id"])

        # Check dependencies
        for phase in self.plan["phases"]:
            for task in phase["tasks"]:
                for dep_id in task.get("dependencies", []):
                    if dep_id not in all_task_ids:
                        issues.append(
                            f"Task {task['id']} has invalid dependency: {dep_id}"
                        )

        return issues

    def generate_report(self) -> str:
        """Generate a progress report"""
        stats = self.get_progress_stats()

        report = ["LeadFactory Development Progress Report"]
        report.append("=" * 40)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        # Overall progress
        completion_pct = (
            (stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        )
        report.append(
            f"Overall Progress: {stats['completed']}/{stats['total']} ({completion_pct:.1f}%)"
        )
        report.append("")

        # Status breakdown
        report.append("Status Breakdown:")
        report.append(f"  Completed:    {stats['completed']:3d}")
        report.append(f"  In Progress:  {stats['in_progress']:3d}")
        report.append(f"  Ready:        {stats['ready']:3d}")
        report.append(f"  Pending:      {stats['pending']:3d}")
        report.append(f"  Blocked:      {stats['blocked']:3d}")
        report.append("")

        # Phase progress
        report.append("Progress by Phase:")
        for phase_name, phase_stats in stats["by_phase"].items():
            phase_pct = (
                (phase_stats["completed"] / phase_stats["total"] * 100)
                if phase_stats["total"] > 0
                else 0
            )
            status = "✓" if phase_pct == 100 else "◯" if phase_pct == 0 else "◐"
            report.append(
                f"  {status} {phase_name:30s} {phase_stats['completed']:2d}/{phase_stats['total']:2d} ({phase_pct:5.1f}%)"
            )

        report.append("")

        # Domain progress
        report.append("Progress by Domain:")
        for domain, domain_stats in sorted(stats["by_domain"].items()):
            domain_pct = (
                (domain_stats["completed"] / domain_stats["total"] * 100)
                if domain_stats["total"] > 0
                else 0
            )
            report.append(
                f"  {domain:15s} {domain_stats['completed']:2d}/{domain_stats['total']:2d} ({domain_pct:5.1f}%)"
            )

        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="LeadFactory task management tool")
    parser.add_argument(
        "--update", nargs=2, metavar=("TASK_ID", "STATUS"), help="Update task status"
    )
    parser.add_argument(
        "--progress", action="store_true", help="Show progress statistics"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify task dependencies"
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate progress report"
    )
    parser.add_argument(
        "--task", metavar="TASK_ID", help="Show details for specific task"
    )

    args = parser.parse_args()

    manager = TaskManager()

    if args.update:
        task_id, status = args.update
        manager.update_task_status(task_id, status)

    elif args.progress:
        stats = manager.get_progress_stats()
        print(
            f"\nLeadFactory Progress: {stats['completed']}/{stats['total']} tasks completed ({stats['completed']/stats['total']*100:.1f}%)"
        )
        print(f"In Progress: {stats['in_progress']}")
        print(f"Ready to Start: {stats['ready']}")

    elif args.verify:
        issues = manager.verify_dependencies()
        if issues:
            print("Dependency issues found:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("All dependencies are valid ✓")

    elif args.report:
        print(manager.generate_report())

    elif args.task:
        task = manager.get_task_by_id(args.task)
        if task:
            print(f"\nTask {task['id']}: {task['title']}")
            print(f"Domain: {task['domain']}")
            print(f"Complexity: {task['complexity']}")
            print(f"Status: {manager.get_task_status(task['id'])}")
            print(f"Dependencies: {', '.join(task.get('dependencies', ['none']))}")
            print(f"Estimated Hours: {task['estimated_hours']}")
            print("\nAcceptance Criteria:")
            for criterion in task.get("acceptance_criteria", []):
                print(f"  - {criterion}")
        else:
            print(f"Task {args.task} not found")

    else:
        # Default: show next tasks
        next_tasks = manager.get_next_tasks()

        if not next_tasks:
            print("\nNo tasks ready to work on!")
            stats = manager.get_progress_stats()
            if stats["completed"] == stats["total"]:
                print("🎉 All tasks completed! 🎉")
            else:
                print("Check task dependencies or blocked tasks.")
        else:
            print("\nNext tasks to work on:")
            print("-" * 80)

            for i, task in enumerate(next_tasks, 1):
                status = manager.get_task_status(task["id"])
                status_icon = "🔄" if status == "in_progress" else "📋"

                print(f"\n{status_icon} {i}. Task {task['id']}: {task['title']}")
                print(
                    f"   Domain: {task['domain']} | Complexity: {task['complexity']} | Est. Hours: {task['estimated_hours']}"
                )

                if status == "in_progress":
                    print("   STATUS: IN PROGRESS")

                if task.get("dependencies"):
                    print(f"   Dependencies: {', '.join(task['dependencies'])} ✓")

                print("   Files to create:")
                for file in task.get("files_to_create", [])[:3]:
                    print(f"     - {file}")
                if len(task.get("files_to_create", [])) > 3:
                    print(f"     ... and {len(task['files_to_create']) - 3} more")


if __name__ == "__main__":
    main()
