#!/usr/bin/env python3
"""
Dashboard updater utility for AI CTO to update status programmatically.
"""

import json
import re
from datetime import datetime
from pathlib import Path


class DashboardUpdater:
    def __init__(self, dashboard_path="ai_cto_dashboard.html"):
        self.dashboard_path = Path(dashboard_path)
        self.status = {
            "completed": [],
            "in_progress": [],
            "blocked": [],
            "pending": [],
            "recent_activity": [],
            "metrics": {"complete": 0, "in_progress": 0, "blocked": 0, "progress": 0},
        }

    def load_current_status(self):
        """Load current status from progress file if it exists."""
        progress_file = Path(".claude/prp_progress.json")
        if progress_file.exists():
            with open(progress_file) as f:
                progress_data = json.load(f)

            # Parse progress data into dashboard status
            for task_id, task_data in progress_data.items():
                if isinstance(task_data, dict):
                    status = task_data.get("status", "pending")
                    title = task_data.get("title", task_id)

                    if status in ["validated", "completed"]:
                        self.status["completed"].append(f"{task_id} - {title}")
                    elif status == "in_progress":
                        self.status["in_progress"].append(f"{task_id} - {title}")
                    elif status in ["failed_validation", "blocked"]:
                        self.status["blocked"].append(f"{task_id} - {title}")
                    else:
                        self.status["pending"].append(f"{task_id} - {title}")

    def add_task_complete(self, task_id, title, details=""):
        """Mark a task as complete."""
        task_entry = f"{task_id} - {title}"
        if details:
            task_entry += f" ({details})"

        # Remove from other lists
        self._remove_from_all_lists(task_id)

        # Add to completed
        self.status["completed"].append(task_entry)

        # Add to recent activity
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.status["recent_activity"].insert(0, f"{timestamp}: ✅ COMPLETED {task_id} - {title}")

        # Keep only last 10 activities
        self.status["recent_activity"] = self.status["recent_activity"][:10]

    def add_task_in_progress(self, task_id, title, progress=""):
        """Mark a task as in progress."""
        task_entry = f"{task_id} - {title}"
        if progress:
            task_entry += f" ({progress})"

        # Remove from other lists
        self._remove_from_all_lists(task_id)

        # Add to in progress
        self.status["in_progress"].append(task_entry)

        # Add to recent activity
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.status["recent_activity"].insert(0, f"{timestamp}: 🔄 STARTED {task_id} - {title}")

        # Keep only last 10 activities
        self.status["recent_activity"] = self.status["recent_activity"][:10]

    def add_task_blocked(self, task_id, title, reason=""):
        """Mark a task as blocked."""
        task_entry = f"{task_id} - {title}"
        if reason:
            task_entry += f" - {reason}"

        # Remove from other lists
        self._remove_from_all_lists(task_id)

        # Add to blocked
        self.status["blocked"].append(task_entry)

        # Add to recent activity
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.status["recent_activity"].insert(0, f"{timestamp}: ⚠️ BLOCKED {task_id} - {reason}")

        # Keep only last 10 activities
        self.status["recent_activity"] = self.status["recent_activity"][:10]

    def update_priority_queue(self, queue_text):
        """Update the priority queue text."""
        self.priority_queue = queue_text

    def _remove_from_all_lists(self, task_id):
        """Remove task from all status lists."""
        for status_key in ["completed", "in_progress", "blocked", "pending"]:
            self.status[status_key] = [task for task in self.status[status_key] if not task.startswith(task_id)]

    def _calculate_metrics(self):
        """Calculate dashboard metrics."""
        self.status["metrics"] = {
            "complete": len(self.status["completed"]),
            "in_progress": len(self.status["in_progress"]),
            "blocked": len(self.status["blocked"]),
            "progress": 0,  # Will calculate based on total tasks
        }

        total_tasks = sum(
            [
                len(self.status["completed"]),
                len(self.status["in_progress"]),
                len(self.status["blocked"]),
                len(self.status["pending"]),
            ]
        )

        if total_tasks > 0:
            self.status["metrics"]["progress"] = round((len(self.status["completed"]) / total_tasks) * 100)

    def generate_html_content(self):
        """Generate updated HTML content."""
        self._calculate_metrics()

        # Read current HTML
        with open(self.dashboard_path) as f:
            html_content = f.read()

        # Update metrics
        metrics = self.status["metrics"]
        html_content = re.sub(
            r'<div class="metric-value">0</div>\s*<div class="metric-label">Tasks Complete</div>',
            f'<div class="metric-value">{metrics["complete"]}</div>\n                <div class="metric-label">Tasks Complete</div>',
            html_content,
        )

        html_content = re.sub(
            r'<div class="metric-value">0</div>\s*<div class="metric-label">In Progress</div>',
            f'<div class="metric-value">{metrics["in_progress"]}</div>\n                <div class="metric-label">In Progress</div>',
            html_content,
        )

        html_content = re.sub(
            r'<div class="metric-value">0</div>\s*<div class="metric-label">Blocked</div>',
            f'<div class="metric-value">{metrics["blocked"]}</div>\n                <div class="metric-label">Blocked</div>',
            html_content,
        )

        html_content = re.sub(
            r'<div class="metric-value">0%</div>\s*<div class="metric-label">Wave A Progress</div>',
            f'<div class="metric-value">{metrics["progress"]}%</div>\n                <div class="metric-label">Wave A Progress</div>',
            html_content,
        )

        # Update completed tasks
        completed_html = "\n".join(
            [f'                    <li><span class="emoji">✅</span>{task}</li>' for task in self.status["completed"]]
        )
        if not completed_html:
            completed_html = "                    <li><em>No completed tasks yet</em></li>"

        html_content = re.sub(
            r'<h3>✅ Completed Tasks</h3>\s*<ul class="task-list">.*?</ul>',
            f'<h3>✅ Completed Tasks</h3>\n                <ul class="task-list">\n{completed_html}\n                </ul>',
            html_content,
            flags=re.DOTALL,
        )

        # Update in progress tasks
        in_progress_html = "\n".join(
            [f'                    <li><span class="emoji">🔄</span>{task}</li>' for task in self.status["in_progress"]]
        )
        if not in_progress_html:
            in_progress_html = "                    <li><em>No active tasks</em></li>"

        html_content = re.sub(
            r'<h3>🔄 In Progress</h3>\s*<ul class="task-list">.*?</ul>',
            f'<h3>🔄 In Progress</h3>\n                <ul class="task-list">\n{in_progress_html}\n                </ul>',
            html_content,
            flags=re.DOTALL,
        )

        # Update blocked tasks
        blocked_html = "\n".join(
            [f'                    <li><span class="emoji">⚠️</span>{task}</li>' for task in self.status["blocked"]]
        )
        if not blocked_html:
            blocked_html = "                    <li><em>No blocking issues</em></li>"

        html_content = re.sub(
            r'<h3>⚠️ Blocked \(Need CEO Decision\)</h3>\s*<ul class="task-list">.*?</ul>',
            f'<h3>⚠️ Blocked (Need CEO Decision)</h3>\n                <ul class="task-list">\n{blocked_html}\n                </ul>',
            html_content,
            flags=re.DOTALL,
        )

        # Update recent activity
        activity_html = "\n".join(
            [f"                <li><strong>{activity}</strong></li>" for activity in self.status["recent_activity"]]
        )
        if not activity_html:
            activity_html = "                <li><strong>No recent activity</strong></li>"

        html_content = re.sub(
            r'<h3>📈 Recent Activity</h3>\s*<ul class="task-list">.*?</ul>',
            f'<h3>📈 Recent Activity</h3>\n            <ul class="task-list">\n{activity_html}\n            </ul>',
            html_content,
            flags=re.DOTALL,
        )

        # Update priority queue if it exists
        if hasattr(self, "priority_queue"):
            html_content = re.sub(
                r'<div class="priority-queue">.*?</div>',
                f'<div class="priority-queue">\n            <h3>📋 Current Priority Queue</h3>\n            {self.priority_queue}\n        </div>',
                html_content,
                flags=re.DOTALL,
            )

        # Update last updated timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        html_content = re.sub(r"Last updated: [^|]+", f"Last updated: {timestamp}", html_content)

        return html_content

    def update_dashboard(self):
        """Update the dashboard file."""
        html_content = self.generate_html_content()
        with open(self.dashboard_path, "w") as f:
            f.write(html_content)


# Convenience functions for easy use
def mark_complete(task_id, title, details=""):
    updater = DashboardUpdater()
    updater.load_current_status()
    updater.add_task_complete(task_id, title, details)
    updater.update_dashboard()


def mark_in_progress(task_id, title, progress=""):
    updater = DashboardUpdater()
    updater.load_current_status()
    updater.add_task_in_progress(task_id, title, progress)
    updater.update_dashboard()


def mark_blocked(task_id, title, reason=""):
    updater = DashboardUpdater()
    updater.load_current_status()
    updater.add_task_blocked(task_id, title, reason)
    updater.update_dashboard()


if __name__ == "__main__":
    # Test the updater
    updater = DashboardUpdater()
    updater.load_current_status()
    updater.update_dashboard()
    print("✅ Dashboard updated successfully")
