#!/usr/bin/env python3
"""
Multi-Agent System Live Dashboard
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List

import redis


def clear_screen():
    os.system("clear" if os.name == "posix" else "cls")


def get_system_status() -> Dict[str, Any]:
    """Get complete system status from Redis"""
    r = redis.from_url("redis://localhost:6379/0")

    # Queue status
    queues = {
        "new_queue": r.llen("new_queue"),
        "dev_queue": r.llen("dev_queue"),
        "validation_queue": r.llen("validation_queue"),
        "integration_queue": r.llen("integration_queue"),
    }

    # Get queue contents
    queue_contents = {}
    for queue_name in queues.keys():
        items = r.lrange(queue_name, 0, -1)
        queue_contents[queue_name] = [item.decode() for item in items]

    # PRP status
    prps = {}
    prp_keys = r.keys("prp:*")
    for key in prp_keys:
        prp_data = r.hgetall(key)
        if prp_data:
            prp_id = key.decode().split(":")[-1]
            prps[prp_id] = {k.decode(): v.decode() for k, v in prp_data.items()}

    # Agent status
    agents = {}
    agent_keys = r.keys("agent:*")
    for key in agent_keys:
        agent_data = r.hgetall(key)
        if agent_data:
            agent_id = key.decode().split(":")[-1]
            agents[agent_id] = {k.decode(): v.decode() for k, v in agent_data.items()}

    return {
        "queues": queues,
        "queue_contents": queue_contents,
        "prps": prps,
        "agents": agents,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def format_pipeline_visual(queues: Dict[str, int], queue_contents: Dict[str, List[str]]) -> str:
    """Create ASCII pipeline visualization"""
    pipeline = f"""
    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
    │  NEW QUEUE  │───▶│  DEV QUEUE  │───▶│ VALIDATION  │───▶│INTEGRATION  │
    │     {queues['new_queue']:2d}      │    │     {queues['dev_queue']:2d}      │    │     {queues['validation_queue']:2d}       │    │     {queues['integration_queue']:2d}       │
    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
    """

    # Add queue contents below
    content_lines = ["", "Queue Contents:", ""]
    max_items = max(len(items) for items in queue_contents.values()) if queue_contents else 0

    if max_items > 0:
        queue_names = ["new_queue", "dev_queue", "validation_queue", "integration_queue"]
        headers = ["NEW", "DEV", "VALIDATION", "INTEGRATION"]

        # Header row
        content_lines.append("  ".join(f"{header:12}" for header in headers))
        content_lines.append("  ".join("─" * 12 for _ in headers))

        # Content rows
        for i in range(max_items):
            row = []
            for queue_name in queue_names:
                items = queue_contents.get(queue_name, [])
                if i < len(items):
                    item = items[i][:10]  # Truncate long names
                    row.append(f"{item:12}")
                else:
                    row.append(" " * 12)
            content_lines.append("  ".join(row))

    return pipeline + "\n".join(content_lines)


def format_agent_status(agents: Dict[str, Dict[str, str]]) -> str:
    """Format agent status table"""
    if not agents:
        return "No agents found"

    lines = ["AGENT STATUS:", "═" * 60]
    lines.append(f"{'Agent':15} {'Status':12} {'Current PRP':12} {'Activity':20}")
    lines.append("─" * 60)

    # Sort agents by type
    agent_order = ["pm", "validator", "integration"]
    sorted_agents = sorted(
        agents.items(), key=lambda x: (next((i for i, t in enumerate(agent_order) if t in x[0]), 999), x[0])
    )

    for agent_id, data in sorted_agents:
        status = data.get("status", "unknown")
        current_prp = data.get("current_prp", "none")
        activity = data.get("activity", data.get("last_activity", "idle"))

        # Color coding
        status_icon = {"active": "🟢", "busy": "🟡", "error": "🔴", "idle": "⚪"}.get(status, "❓")

        lines.append(f"{agent_id:15} {status_icon} {status:10} {current_prp:12} {activity:20}")

    return "\n".join(lines)


def format_prp_backlog(prps: Dict[str, Dict[str, str]]) -> str:
    """Format PRP backlog and status"""
    if not prps:
        return "No PRPs found"

    lines = ["PRP BACKLOG & STATUS:", "═" * 50]

    # Group by state
    states = {}
    for prp_id, data in prps.items():
        state = data.get("state", "unknown")
        if state not in states:
            states[state] = []
        states[state].append((prp_id, data))

    # Show states in order
    state_order = ["new", "assigned", "development", "validation", "integration", "complete"]

    for state in state_order:
        if state in states:
            state_icon = {
                "new": "📋",
                "assigned": "👤",
                "development": "💻",
                "validation": "🔍",
                "integration": "🚀",
                "complete": "✅",
            }.get(state, "❓")

            lines.append(f"\n{state_icon} {state.upper()}:")
            for prp_id, data in states[state]:
                owner = data.get("owner", "unassigned")
                title = data.get("title", "No title")[:30]
                progress = data.get("progress", "0%")
                lines.append(f"  {prp_id:12} | {owner:12} | {progress:6} | {title}")

    return "\n".join(lines)


def render_dashboard():
    """Render the complete dashboard"""
    status = get_system_status()

    clear_screen()

    print("🤖 MULTI-AGENT ORCHESTRATION DASHBOARD")
    print("═" * 80)
    print(f"⏰ {status['timestamp']}")
    print()

    # Pipeline visualization
    print("📊 PROCESSING PIPELINE:")
    print(format_pipeline_visual(status["queues"], status["queue_contents"]))
    print()

    # Split into two columns
    print("📋 SYSTEM STATUS:")
    print("─" * 80)

    # Left column: Agent status
    agent_lines = format_agent_status(status["agents"]).split("\n")

    # Right column: PRP backlog
    prp_lines = format_prp_backlog(status["prps"]).split("\n")

    # Print side by side
    max_lines = max(len(agent_lines), len(prp_lines))
    for i in range(max_lines):
        left = agent_lines[i] if i < len(agent_lines) else ""
        right = prp_lines[i] if i < len(prp_lines) else ""
        print(f"{left:40} | {right}")

    print()
    print("─" * 80)
    print("Press Ctrl+C to exit | Refreshes every 2 seconds")


def main():
    """Main dashboard loop"""
    try:
        while True:
            render_dashboard()
            time.sleep(2)
    except KeyboardInterrupt:
        clear_screen()
        print("Dashboard stopped.")
    except Exception as e:
        print(f"Dashboard error: {e}")


if __name__ == "__main__":
    main()
