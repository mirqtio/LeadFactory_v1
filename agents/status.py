#!/usr/bin/env python3
"""
Quick System Status - Single snapshot
"""
from datetime import datetime

import redis


def quick_status():
    r = redis.from_url("redis://localhost:6379/0")

    print("🤖 SYSTEM SNAPSHOT")
    print("=" * 50)
    print(f"⏰ {datetime.now().strftime('%H:%M:%S')}")
    print()

    # Pipeline flow
    new = r.llen("new_queue")
    dev = r.llen("dev_queue")
    val = r.llen("validation_queue")
    int_q = r.llen("integration_queue")

    print("📊 PIPELINE:")
    print(f"  NEW → DEV → VALIDATION → INTEGRATION")
    print(f"   {new}     {dev}        {val}           {int_q}")
    print()

    # Active PRPs
    print("📄 ACTIVE PRPS:")
    prp_keys = r.keys("prp:*")
    if prp_keys:
        for key in sorted(prp_keys):
            prp_data = r.hgetall(key)
            if prp_data:
                prp_id = key.decode().split(":")[-1]
                state = prp_data.get(b"state", b"unknown").decode()
                owner = prp_data.get(b"owner", b"unassigned").decode()
                print(f"  {prp_id:12} : {state:12} ({owner})")
    else:
        print("  None")
    print()

    # Agents
    print("🤖 AGENTS:")
    agent_keys = r.keys("agent:*")
    if agent_keys:
        for key in sorted(agent_keys):
            agent_data = r.hgetall(key)
            if agent_data:
                agent_id = key.decode().split(":")[-1]
                status = agent_data.get(b"status", b"unknown").decode()
                current_prp = agent_data.get(b"current_prp", b"none").decode()
                icon = "🟢" if status == "active" else "🔴"
                print(f"  {icon} {agent_id:12} : {status:8} | {current_prp}")
    else:
        print("  None found")


if __name__ == "__main__":
    quick_status()
