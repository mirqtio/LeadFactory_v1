#!/usr/bin/env python3
"""
Clean test of queue operations
"""
import redis
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

r = redis.from_url("redis://localhost:6379/0")

# REALLY clear everything
r.flushdb()
logger.info("Flushed Redis completely")

# Double check it's empty
all_keys = r.keys("*")
logger.info(f"All keys after flush: {all_keys}")

# Now test
prp_id = "CLEAN-001"

# Step 1: Add to pm_queue:inflight (simulating it's being processed)
r.lpush("pm_queue:inflight", prp_id)
logger.info(f"\n1. Added {prp_id} to pm_queue:inflight")

# Step 2: Simulate handle_completion
removed = r.lrem("pm_queue:inflight", 0, prp_id)
logger.info(f"2. Removed from pm_queue:inflight: {removed}")

pushed = r.lpush("validation_queue", prp_id)
logger.info(f"3. Pushed to validation_queue: {pushed}")

# Check final state
logger.info("\nFinal state:")
for queue in ["pm_queue", "pm_queue:inflight", "validation_queue", "validation_queue:inflight"]:
    contents = r.lrange(queue, 0, -1)
    logger.info(f"  {queue}: {contents}")

# Verify
val_queue = r.lrange("validation_queue", 0, -1)
if val_queue and val_queue[0].decode() == prp_id:
    logger.info(f"\n✅ SUCCESS: {prp_id} is in validation_queue")
else:
    logger.error(f"\n❌ FAILED: {prp_id} not in validation_queue")