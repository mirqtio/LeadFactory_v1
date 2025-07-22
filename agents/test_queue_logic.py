#!/usr/bin/env python3
"""
Test just the queue logic without API calls
"""
import redis
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_queue_logic")

# Connect to Redis
r = redis.from_url("redis://localhost:6379/0")
r.flushdb()

# Simulate what happens in handle_completion
prp_id = "TEST-001"
role = "pm"
agent_id = "pm-test"
queue = "pm_queue"
next_queue = "validation_queue"

# Setup: PRP is in inflight queue (as it would be during processing)
r.lpush(f"{queue}:inflight", prp_id)
logger.info(f"Setup: Added {prp_id} to {queue}:inflight")

# Simulate handle_completion
logger.info("\nSimulating handle_completion:")

# Update PRP state
completion_time = datetime.utcnow().isoformat()
r.hset(f"prp:{prp_id}", mapping={
    f"{role}_completed_at": completion_time,
    f"{role}_completed_by": agent_id
})
logger.info(f"1. Updated PRP metadata")

# Move to next queue
removed = r.lrem(f"{queue}:inflight", 0, prp_id)
logger.info(f"2. Removed from {queue}:inflight: {removed} items")

pushed = r.lpush(next_queue, prp_id)
logger.info(f"3. Pushed to {next_queue}: list now has {pushed} items")

# Check final state
logger.info("\nFinal state:")
logger.info(f"  {queue}: {r.lrange(queue, 0, -1)}")
logger.info(f"  {queue}:inflight: {r.lrange(f'{queue}:inflight', 0, -1)}")
logger.info(f"  {next_queue}: {r.lrange(next_queue, 0, -1)}")
logger.info(f"  {next_queue}:inflight: {r.lrange(f'{next_queue}:inflight', 0, -1)}")

# The issue might be if the agent's run() is doing another blmove
logger.info("\nIf validator agent does blmove:")
moved = r.blmove(next_queue, f"{next_queue}:inflight", 1.0)
logger.info(f"  Moved: {moved}")
logger.info(f"  {next_queue}: {r.lrange(next_queue, 0, -1)}")
logger.info(f"  {next_queue}:inflight: {r.lrange(f'{next_queue}:inflight', 0, -1)}")