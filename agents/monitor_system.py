#!/usr/bin/env python3
"""
Multi-Agent System Monitor
"""
import redis
import json
import time
from datetime import datetime

def monitor_system():
    r = redis.from_url("redis://localhost:6379/0")
    
    print("=" * 60)
    print("🤖 MULTI-AGENT SYSTEM STATUS")
    print("=" * 60)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Queue Status
    print("📋 QUEUE STATUS:")
    queues = ["new_queue", "dev_queue", "validation_queue", "integration_queue"]
    for queue in queues:
        length = r.llen(queue)
        print(f"  {queue:20} : {length:3d} items")
    print()
    
    # Active PRPs
    print("📄 ACTIVE PRPS:")
    prp_keys = r.keys("prp:*")
    if prp_keys:
        for key in sorted(prp_keys):
            prp_data = r.hgetall(key)
            if prp_data:
                prp_id = key.decode().split(":")[-1]
                state = prp_data.get(b'state', b'unknown').decode()
                owner = prp_data.get(b'owner', b'unassigned').decode()
                print(f"  {prp_id:15} : {state:12} | {owner}")
    else:
        print("  No active PRPs")
    print()
    
    # Agent Status  
    print("🤖 AGENT STATUS:")
    agent_keys = r.keys("agent:*")
    if agent_keys:
        for key in sorted(agent_keys):
            agent_data = r.hgetall(key)
            if agent_data:
                agent_id = key.decode().split(":")[-1]
                status = agent_data.get(b'status', b'unknown').decode()
                current_prp = agent_data.get(b'current_prp', b'none').decode()
                last_update = agent_data.get(b'last_update', b'never').decode()
                print(f"  {agent_id:15} : {status:12} | PRP: {current_prp:10} | {last_update}")
    else:
        print("  No agent status found")
    print()
    
    # Recent Activity (if we have activity logs)
    activity_keys = r.keys("activity:*")
    if activity_keys:
        print("📊 RECENT ACTIVITY:")
        # Get last 5 activities
        activities = []
        for key in activity_keys:
            activity = r.get(key)
            if activity:
                activities.append(activity.decode())
        
        for activity in sorted(activities)[-5:]:
            print(f"  {activity}")
    
    print("=" * 60)

if __name__ == "__main__":
    try:
        monitor_system()
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
    except Exception as e:
        print(f"Error: {e}")