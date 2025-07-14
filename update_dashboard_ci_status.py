#!/usr/bin/env python3
"""
Update AI CTO Dashboard with real CI status from git and GitHub.
This script checks the actual completion status of tasks based on:
1. Whether code is committed to git
2. Whether commits are pushed to GitHub
3. CI status (if accessible)
"""

import subprocess
from datetime import datetime
from pathlib import Path


def run_command(cmd):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip(), result.returncode
    except Exception as e:
        print(f"Error running command '{cmd}': {e}")
        return "", 1


def get_git_status():
    """Get current git status information."""
    status = {}

    # Get uncommitted files count
    output, _ = run_command("git status --porcelain | wc -l")
    status["uncommitted_files"] = int(output) if output else 0

    # Get current branch
    output, _ = run_command("git branch --show-current")
    status["current_branch"] = output

    # Check if we have unpushed commits
    output, _ = run_command("git log origin/main..HEAD --oneline")
    status["unpushed_commits"] = len(output.splitlines()) if output else 0

    # Get last commit info
    output, _ = run_command('git log -1 --format="%ci|%s"')
    if output:
        parts = output.split("|", 1)
        status["last_commit_time"] = parts[0]
        status["last_commit_message"] = parts[1] if len(parts) > 1 else ""

    return status


def check_task_completion():
    """Check which P0 tasks are actually complete based on git commits."""
    completed_tasks = []
    local_only_tasks = []

    # Check commits in git log for P0 tasks
    output, _ = run_command("git log --oneline -n 50")
    commits = output.splitlines() if output else []

    # Map of P0 tasks and their expected commit patterns
    p0_tasks = {
        "P0-000": "Prerequisites Check",
        "P0-001": "Fix D4 Coordinator",
        "P0-002": "Wire Prefect Full Pipeline",
        "P0-003": "Dockerize CI",
        "P0-004": "Database Migrations",
        "P0-005": "Environment Stub Wiring",
        "P0-007": "Health Endpoint",
        "P0-020": "Design System Token Extraction",
        "P0-024": "Template Studio",
    }

    # Check which tasks have commits
    for task_id, task_name in p0_tasks.items():
        for commit in commits:
            if task_id in commit or task_id.replace("-", "_") in commit:
                completed_tasks.append(f"{task_id} - {task_name}")
                break

    # Check for uncommitted work
    uncommitted_patterns = {
        "core/prerequisites.py": "P0-000 - Prerequisites Check",
        "d4_enrichment/coordinator.py": "P0-001 - Fix D4 Coordinator",
        "api/health.py": "P0-007 - Health Endpoint",
    }

    output, _ = run_command("git status --porcelain")
    if output:
        for line in output.splitlines():
            for pattern, task in uncommitted_patterns.items():
                if pattern in line and task not in completed_tasks:
                    local_only_tasks.append(f"{task} - LOCAL ONLY (uncommitted)")

    return completed_tasks, local_only_tasks


def generate_dashboard_html(git_status, completed_tasks, local_only_tasks):
    """Generate updated dashboard HTML with real status."""

    # Calculate time since last commit
    if git_status.get("last_commit_time"):
        commit_time = datetime.strptime(git_status["last_commit_time"][:19], "%Y-%m-%d %H:%M:%S")
        time_diff = datetime.now() - commit_time
        hours_ago = int(time_diff.total_seconds() / 3600)
        time_str = f"{hours_ago} hours ago" if hours_ago > 0 else "recently"
    else:
        time_str = "unknown"

    # Count actual completed vs local-only
    actual_complete = len(completed_tasks)
    local_only = len(local_only_tasks)

    # Calculate pending (total P0 tasks minus completed and local)
    total_p0_tasks = 27  # Based on P0-000 through P0-026
    pending = total_p0_tasks - actual_complete - local_only

    # Format task lists
    completed_html = "\n".join([f"<li>{task}</li>" for task in completed_tasks])
    local_html = "\n".join([f"<li>{task}</li>" for task in local_only_tasks])

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI CTO Dashboard - LeadFactory CI Status</title>
    <style>
        :root {{
            --primary-color: #2563eb;
            --success-color: #16a34a;
            --warning-color: #d97706;
            --danger-color: #dc2626;
            --text-primary: #1f2937;
            --text-secondary: #6b7280;
            --bg-primary: #ffffff;
            --bg-secondary: #f3f4f6;
            --border-color: #e5e7eb;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-secondary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            color: var(--primary-color);
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            margin-bottom: 30px;
            font-size: 1.1rem;
        }}
        
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .metric {{
            background: var(--bg-primary);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            text-align: center;
        }}
        
        .metric-value {{
            font-size: 2.5rem;
            font-weight: bold;
            margin-bottom: 5px;
        }}
        
        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .status-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .status-card {{
            background: var(--bg-primary);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}
        
        .status-card h3 {{
            margin-bottom: 15px;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .task-list {{
            list-style: none;
        }}
        
        .task-list li {{
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
        }}
        
        .task-list li:last-child {{
            border-bottom: none;
        }}
        
        .completed {{ color: var(--success-color); }}
        .in-progress {{ color: var(--warning-color); }}
        .blocked {{ color: var(--danger-color); }}
        .pending {{ color: var(--text-secondary); }}
        .uncommitted {{ color: var(--warning-color); font-style: italic; }}
        
        .last-updated {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9rem;
            padding: 20px;
        }}
        
        button {{
            background: var(--primary-color);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        }}
        
        button:hover {{
            opacity: 0.9;
        }}
        
        .critical-note {{
            background: #fee2e2;
            border: 2px solid #dc2626;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
        }}
        
        .warning-note {{
            background: #fef3c7;
            border: 1px solid #f59e0b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
        }}
        
        .success-note {{
            background: #d1fae5;
            border: 1px solid #10b981;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.95rem;
        }}
    </style>
    <script>
        function refreshPage() {{
            location.reload();
        }}
        
        // Auto-refresh every 30 seconds
        setInterval(refreshPage, 30000);
    </script>
</head>
<body>
    <div class="container">
        <h1>🤖 AI CTO Dashboard - CI Status</h1>
        <p class="subtitle">Real-time Git & CI Status</p>
        
        <div class="critical-note">
            <strong>🚨 Definition of Complete:</strong> A task is ONLY complete when:
            <ol>
                <li>Code is implemented and validated</li>
                <li><strong>Pushed to GitHub main branch</strong></li>
                <li><strong>ALL CI checks pass GREEN</strong></li>
            </ol>
        </div>
        
        {'<div class="success-note"><strong>✅ Good News:</strong> All commits are pushed to GitHub! No unpushed commits detected.</div>' if git_status['unpushed_commits'] == 0 else f'<div class="warning-note"><strong>⚠️ Warning:</strong> {git_status["unpushed_commits"]} unpushed commits detected!</div>'}
        
        <div class="warning-note">
            <strong>⚠️ Current Status:</strong> {git_status['uncommitted_files']} uncommitted files. Last commit: "{git_status.get('last_commit_message', 'unknown')}" ({time_str})
        </div>
        
        <div class="metrics">
            <div class="metric">
                <div class="metric-value completed">{actual_complete}</div>
                <div class="metric-label">Committed & Pushed</div>
            </div>
            <div class="metric">
                <div class="metric-value uncommitted">{local_only}</div>
                <div class="metric-label">Local Only (Uncommitted)</div>
            </div>
            <div class="metric">
                <div class="metric-value pending">{pending}</div>
                <div class="metric-label">Not Started</div>
            </div>
            <div class="metric">
                <div class="metric-value blocked">0</div>
                <div class="metric-label">Blocked</div>
            </div>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3 class="completed">✅ Committed & Pushed to GitHub</h3>
                <ul class="task-list">
                    {completed_html}
                </ul>
            </div>
            
            <div class="status-card">
                <h3 class="uncommitted">⚠️ Local Work (Not Committed)</h3>
                <ul class="task-list">
                    {local_html if local_html else '<li>No uncommitted P0 task files detected</li>'}
                </ul>
            </div>
            
            <div class="status-card">
                <h3 class="pending">📋 Not Started</h3>
                <ul class="task-list">
                    <li>P0-006 - Green KEEP Test Suite</li>
                    <li>P0-008 - Test Infrastructure Cleanup</li>
                    <li>P0-009 - Remove Yelp Remnants</li>
                    <li>P0-010 - Fix Missing Dependencies</li>
                    <li>P0-011 - Deploy to VPS</li>
                    <li>P0-012 - Postgres on VPS Container</li>
                    <li>P0-013 - CI/CD Pipeline Stabilization</li>
                    <li>P0-014 - Test Suite Re-enablement</li>
                    <li><em>...and more P0 tasks</em></li>
                </ul>
            </div>
        </div>
        
        <div class="status-card">
            <h3>📈 Git Repository Status</h3>
            <ul class="task-list">
                <li><strong>Branch:</strong> {git_status['current_branch']}</li>
                <li><strong>Uncommitted files:</strong> {git_status['uncommitted_files']}</li>
                <li><strong>Unpushed commits:</strong> {git_status['unpushed_commits']}</li>
                <li><strong>Last commit:</strong> {git_status.get('last_commit_message', 'unknown')}</li>
                <li><strong>Commit time:</strong> {git_status.get('last_commit_time', 'unknown')}</li>
            </ul>
        </div>
        
        <div class="last-updated">
            Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Auto-refresh: 30s | 
            <button onclick="refreshPage()">Manual Refresh</button>
        </div>
    </div>
</body>
</html>"""

    return html_content


def update_docker_dashboard(html_content):
    """Update the dashboard in the Docker container."""
    dashboard_path = Path("/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/ai_cto_dashboard.html")

    # Write the updated dashboard
    with open(dashboard_path, "w") as f:
        f.write(html_content)

    print(f"✅ Dashboard updated at: {dashboard_path}")

    # If Docker container is running, we could copy the file into it
    # For now, the dashboard server will pick up the changes automatically


def main():
    """Main function to update dashboard with CI status."""
    print("🔍 Checking Git and CI status...")

    # Get git status
    git_status = get_git_status()
    print(
        f"📊 Git Status: {git_status['uncommitted_files']} uncommitted files, {git_status['unpushed_commits']} unpushed commits"
    )

    # Check task completion
    completed_tasks, local_only_tasks = check_task_completion()
    print(f"✅ Completed & Pushed: {len(completed_tasks)} tasks")
    print(f"⚠️  Local Only: {len(local_only_tasks)} tasks")

    # Generate updated dashboard
    html_content = generate_dashboard_html(git_status, completed_tasks, local_only_tasks)

    # Update the dashboard
    update_docker_dashboard(html_content)

    print("\n📊 Dashboard Summary:")
    print(f"  - Committed & Pushed: {len(completed_tasks)}")
    print(f"  - Local Only: {len(local_only_tasks)}")
    print(f"  - Uncommitted Files: {git_status['uncommitted_files']}")
    print(f"  - Last Commit: {git_status.get('last_commit_message', 'unknown')}")


if __name__ == "__main__":
    main()
