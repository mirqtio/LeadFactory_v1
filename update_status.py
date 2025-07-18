#!/usr/bin/env python3
"""
Orchestrator Status Update Script
Updates the status dashboard with current agent and system status
"""

import datetime
import json
import os
import subprocess
import sys


def get_tmux_output(window):
    """Get recent output from a tmux window"""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", f"orchestrator:{window}", "-p"], capture_output=True, text=True
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            return "\n".join(lines[-10:])  # Last 10 lines
        return "No output available"
    except Exception as e:
        return f"Error: {str(e)}"


def get_prp_status():
    """Get P0-016 PRP status"""
    try:
        result = subprocess.run(
            ["python", ".claude/prp_tracking/cli_commands.py", "status", "P0-016"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "PRP status unavailable"
    except Exception as e:
        return f"Error: {str(e)}"


def get_github_status():
    """Get GitHub CI status"""
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--repo", "mirqtio/LeadFactory_v1", "--limit", "5"], capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return "GitHub status unavailable"
    except Exception as e:
        return f"Error: {str(e)}"


def update_html_status():
    """Update the HTML status page with current data"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get data
    test_engineer_output = get_tmux_output(1)
    coverage_engineer_output = get_tmux_output(3)
    validation_engineer_output = get_tmux_output(4)
    prp_status = get_prp_status()
    github_status = get_github_status()

    # Read template
    with open("orchestrator_status.html", "r") as f:
        html_content = f.read()

    # Update timestamp
    html_content = html_content.replace(
        '<span id="timestamp">2025-07-17 18:29:35</span>', f'<span id="timestamp">{timestamp}</span>'
    )

    # Update test engineer output
    test_engineer_section = test_engineer_output.replace("\n", "\\n").replace('"', '\\"')
    html_content = html_content.replace(
        '⏺ Examining GBP test failures and root causes\n⏺ Search(pattern: "gbp|GBP|google.*business", path: "tests")\n  ⎿  Found 21 files\n⏺ Read(tests/smoke/test_smoke_gbp.py)\n  ⎿  Read 167 lines\n✳ Herding… (240s · ↑ 921 tokens)',
        test_engineer_output[-300:] if len(test_engineer_output) > 300 else test_engineer_output,
    )

    # Update coverage engineer output
    html_content = html_content.replace(
        "Bash(pytest --cov=d9_delivery --cov=d10_analytics --cov=d11_orchestration\n     --cov-report=term-missing --cov-report=html:coverage_d9_d10_d11 -v)\nWaiting…\n✳ Divining… (233s · ⚒ 416 tokens)",
        coverage_engineer_output[-300:] if len(coverage_engineer_output) > 300 else coverage_engineer_output,
    )

    # Update validation engineer output
    html_content = html_content.replace(
        "- No changes detected from other agents\n- All validation gates remain green\n- Ready to validate any new changes immediately\n\nNext Actions:\n- Continue monitoring for agent changes\n- Run make quick-check after each change\n- Report validation status every 30 minutes as scheduled",
        validation_engineer_output[-300:] if len(validation_engineer_output) > 300 else validation_engineer_output,
    )

    # Write updated HTML
    with open("orchestrator_status.html", "w") as f:
        f.write(html_content)

    # Update Docker container
    try:
        subprocess.run(["docker", "exec", "orchestrator-status", "/update_status.sh"], capture_output=True)
    except Exception as e:
        print(f"Error updating container: {e}")

    print(f"Status updated at {timestamp}")


if __name__ == "__main__":
    update_html_status()
