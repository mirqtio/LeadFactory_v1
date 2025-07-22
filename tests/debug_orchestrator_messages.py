#!/usr/bin/env python3
"""
Debug script to test orchestrator message processing
"""
import json
import time
from datetime import datetime

import redis

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0")

print("🔍 Testing Orchestrator Message Processing\n")

# Test 1: Direct message push and pop
print("Test 1: Direct Redis operations")
print("-" * 50)

# Push a test message
test_message = {"type": "heartbeat_check", "timestamp": datetime.utcnow().isoformat(), "source": "debug_test"}

print(f"Pushing message: {json.dumps(test_message, indent=2)}")
r.lpush("orchestrator_queue", json.dumps(test_message))
print(f"Queue length after push: {r.llen('orchestrator_queue')}")

# Try different pop methods
print("\nTrying RPOP (FIFO with LPUSH):")
msg = r.rpop("orchestrator_queue")
if msg:
    print(f"✅ Got message: {msg.decode()}")
else:
    print("❌ No message retrieved with RPOP")

# Push again and try LPOP
r.lpush("orchestrator_queue", json.dumps(test_message))
print("\nTrying LPOP (LIFO with LPUSH):")
msg = r.lpop("orchestrator_queue")
if msg:
    print(f"✅ Got message: {msg.decode()}")
else:
    print("❌ No message retrieved with LPOP")

# Test 2: Check if orchestrator loop is actually connected
print("\n\nTest 2: Check orchestrator loop Redis connection")
print("-" * 50)

# Set a marker
r.set("debug:orchestrator_test", "test_value")
val = r.get("debug:orchestrator_test")
print(f"Redis connection test: {'✅ Connected' if val else '❌ Not connected'}")

# Test 3: Send multiple message types
print("\n\nTest 3: Send multiple orchestrator messages")
print("-" * 50)

messages = [
    {"type": "heartbeat_check", "timestamp": datetime.utcnow().isoformat()},
    {
        "type": "agent_question",
        "agent": "dev-1",
        "question": "Test question?",
        "question_id": "test-123",
        "prp_id": "TEST-001",
    },
    {"type": "check_queue_depth", "timestamp": datetime.utcnow().isoformat()},
    {"type": "check_shim_health", "timestamp": datetime.utcnow().isoformat()},
]

for msg in messages:
    print(f"Pushing: {msg['type']}")
    r.lpush("orchestrator_queue", json.dumps(msg))

print(f"\nTotal messages in queue: {r.llen('orchestrator_queue')}")

# Test 4: Check orchestrator loop markers
print("\n\nTest 4: Check orchestrator loop activity markers")
print("-" * 50)

# Check if orchestrator loop is setting any markers
last_heartbeat = r.get("orchestrator:last_heartbeat_check")
if last_heartbeat:
    print(f"✅ Last heartbeat check: {last_heartbeat.decode()}")
else:
    print("❌ No heartbeat check marker found")

last_qa = r.get("orchestrator:last_qa_processed")
if last_qa:
    print(f"✅ Last Q&A processed: {last_qa.decode()}")
else:
    print("❌ No Q&A processing marker found")

# Test 5: Monitor queue for 5 seconds
print("\n\nTest 5: Monitor queue changes for 5 seconds")
print("-" * 50)

print("Pushing test message and monitoring...")
r.lpush("orchestrator_queue", json.dumps({"type": "test_monitor", "timestamp": datetime.utcnow().isoformat()}))

for i in range(5):
    length = r.llen("orchestrator_queue")
    print(f"Second {i+1}: Queue length = {length}")
    time.sleep(1)

# Test 6: Check for any blocking operations
print("\n\nTest 6: Check Redis info")
print("-" * 50)

info = r.info("clients")
print(f"Connected clients: {info['connected_clients']}")
print(f"Blocked clients: {info.get('blocked_clients', 0)}")

# Clean up
r.delete("debug:orchestrator_test")
print("\n✅ Debug tests complete")
