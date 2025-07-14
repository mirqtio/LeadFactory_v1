#!/usr/bin/env python3
"""
Convenience script for AI CTO to update dashboard status.
"""

import sys

from dashboard_updater import DashboardUpdater


def main():
    if len(sys.argv) < 4:
        print("Usage: python update_dashboard.py <action> <task_id> <title> [details]")
        print("Actions: complete, progress, blocked")
        print("Example: python update_dashboard.py complete P0-007 'Health Endpoint' 'All tests passing'")
        return

    action = sys.argv[1]
    task_id = sys.argv[2]
    title = sys.argv[3]
    details = sys.argv[4] if len(sys.argv) > 4 else ""

    updater = DashboardUpdater()
    updater.load_current_status()

    if action == "complete":
        updater.add_task_complete(task_id, title, details)
        print(f"✅ Marked {task_id} as complete")
    elif action == "progress":
        updater.add_task_in_progress(task_id, title, details)
        print(f"🔄 Marked {task_id} as in progress")
    elif action == "blocked":
        updater.add_task_blocked(task_id, title, details)
        print(f"⚠️ Marked {task_id} as blocked")
    else:
        print(f"Unknown action: {action}")
        return

    updater.update_dashboard()
    print("📊 Dashboard updated - http://localhost:8502/ai_cto_dashboard.html")


if __name__ == "__main__":
    main()
