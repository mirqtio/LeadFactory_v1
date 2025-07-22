#!/usr/bin/env python3
"""
Debug heartbeat processing
"""
import json
import time
from datetime import datetime, timedelta

import redis

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0")

print("🔍 Testing Heartbeat Processing\n")

# Step 1: Set up agent with old activity
print("Step 1: Setting up agent with 35-minute old activity")
agent_id = "dev-1"
last_activity = datetime.utcnow() - timedelta(minutes=35)

r.hset(
    f"agent:{agent_id}",
    mapping={"status": "active", "last_activity": last_activity.isoformat(), "current_prp": "DEBUG-TEST-001"},
)

# Check what we set
agent_data = r.hgetall(f"agent:{agent_id}")
print(f"Agent data set:")
for key, value in agent_data.items():
    print(f"  {key.decode()}: {value.decode()}")

# Step 2: Send heartbeat check message
print("\nStep 2: Sending heartbeat check message")
msg = {"type": "heartbeat_check", "timestamp": datetime.utcnow().isoformat()}
r.lpush("orchestrator_queue", json.dumps(msg))
print(f"Queue depth after push: {r.llen('orchestrator_queue')}")

# Step 3: Wait for processing
print("\nStep 3: Waiting for processing (5 seconds)...")
time.sleep(5)

# Step 4: Check results
print("\nStep 4: Checking results")
queue_depth = r.llen("orchestrator_queue")
print(f"Queue depth after wait: {queue_depth}")

# Check if heartbeat was processed
last_heartbeat = r.get("orchestrator:last_heartbeat_check")
if last_heartbeat:
    print(f"✅ Heartbeat processed at: {last_heartbeat.decode()}")
else:
    print("❌ No heartbeat processing marker found")

# Check agent status
agent_data_after = r.hgetall(f"agent:{agent_id}")
print(f"\nAgent data after processing:")
for key, value in agent_data_after.items():
    print(f"  {key.decode()}: {value.decode()}")

# Check if status changed
status = agent_data_after.get(b"status")
if status == b"agent_down":
    print("\n✅ SUCCESS: Agent marked as down")
else:
    print(f"\n❌ FAILED: Agent status is still '{status.decode() if status else 'None'}'")

# Step 5: Check orchestrator logs
print("\nStep 5: Checking orchestrator logs")
with open("/tmp/orchestrator_loop.log", "r") as f:
    lines = f.readlines()
    recent_lines = lines[-50:]  # Last 50 lines

    print("Recent orchestrator log entries:")
    for line in recent_lines:
        if "heartbeat" in line.lower() or "agent" in line.lower() or "down" in line.lower():
            print(f"  {line.strip()}")

# Cleanup
r.delete(f"agent:{agent_id}")
print("\n✅ Debug complete")
