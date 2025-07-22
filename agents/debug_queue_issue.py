#!/usr/bin/env python3
"""
Debug queue handling issue
"""
import redis

r = redis.from_url("redis://localhost:6379/0")

print("Current Redis state:")
print("-" * 50)

# Check all queues
for queue in ["pm_queue", "validation_queue", "integration_queue"]:
    print(f"\n{queue}:")
    items = r.lrange(queue, 0, -1)
    print(f"  Items: {[i.decode() if isinstance(i, bytes) else i for i in items]}")
    
    inflight = r.lrange(f"{queue}:inflight", 0, -1)
    print(f"  Inflight: {[i.decode() if isinstance(i, bytes) else i for i in inflight]}")

# Let's manually fix and test
print("\n\nManual fix test:")
print("-" * 50)

# Clear everything
r.flushdb()
print("Cleared Redis")

# Create test PRP
prp_id = "DEBUG-001"
r.hset(f"prp:{prp_id}", mapping={"id": prp_id, "title": "Debug test"})

# Simulate what the agent does
print(f"\n1. Adding {prp_id} to pm_queue")
r.lpush("pm_queue", prp_id)

print(f"2. Moving to inflight with blmove")
moved = r.blmove("pm_queue", "pm_queue:inflight", 1.0)
print(f"   Moved: {moved}")

print(f"3. Simulating completion - removing from inflight and pushing to next queue")
removed = r.lrem("pm_queue:inflight", 0, prp_id)
print(f"   Removed from inflight: {removed}")

pushed = r.lpush("validation_queue", prp_id)
print(f"   Pushed to validation_queue: {pushed}")

print("\nFinal state:")
print(f"pm_queue: {r.lrange('pm_queue', 0, -1)}")
print(f"pm_queue:inflight: {r.lrange('pm_queue:inflight', 0, -1)}")
print(f"validation_queue: {r.lrange('validation_queue', 0, -1)}")
print(f"validation_queue:inflight: {r.lrange('validation_queue:inflight', 0, -1)}")