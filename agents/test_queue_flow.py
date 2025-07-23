#!/usr/bin/env python3
"""
Test queue flow step by step
"""
import logging
import os
import sys

import redis

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_queue_flow")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.pm_agent import PMAgent

# Clear Redis
r = redis.from_url(config.redis_url)
r.flushdb()
logger.info("Cleared Redis")

# Create PRP
prp_id = "QUEUE-TEST-001"
r.hset(
    f"prp:{prp_id}", mapping={"id": prp_id, "title": "Queue test", "content": "Create add function", "priority": "high"}
)

# Step 1: Add to pm_queue
r.lpush("pm_queue", prp_id)
logger.info(f"Step 1: Added {prp_id} to pm_queue")
logger.info(f"  pm_queue: {r.lrange('pm_queue', 0, -1)}")

# Step 2: Create agent and let it process
agent = PMAgent("pm-test")

# Manually do what the agent's run() would do
logger.info(f"\nStep 2: Agent blmove from queue to inflight")
moved = r.blmove("pm_queue", "pm_queue:inflight", 1.0)
logger.info(f"  Moved: {moved}")
logger.info(f"  pm_queue: {r.lrange('pm_queue', 0, -1)}")
logger.info(f"  pm_queue:inflight: {r.lrange('pm_queue:inflight', 0, -1)}")

# Step 3: Process the PRP
if moved:
    prp_id_moved = moved.decode() if isinstance(moved, bytes) else moved
    logger.info(f"\nStep 3: Processing PRP {prp_id_moved}")

    # Add logging to see Redis operations
    original_lrem = r.lrem
    original_lpush = r.lpush

    def logged_lrem(key, count, value):
        logger.info(f"  Redis lrem('{key}', {count}, '{value}')")
        result = original_lrem(key, count, value)
        logger.info(f"    -> Result: {result}")
        return result

    def logged_lpush(key, *values):
        logger.info(f"  Redis lpush('{key}', {values})")
        result = original_lpush(key, *values)
        logger.info(f"    -> Result: {result}")
        return result

    # Temporarily replace Redis methods
    agent.redis_client.lrem = logged_lrem
    agent.redis_client.lpush = logged_lpush

    try:
        agent.process_prp(prp_id_moved)
    except Exception as e:
        logger.error(f"Error processing: {e}")

    # Restore original methods
    agent.redis_client.lrem = original_lrem
    agent.redis_client.lpush = original_lpush

# Step 4: Check final state
logger.info(f"\nStep 4: Final state")
logger.info(f"  pm_queue: {r.lrange('pm_queue', 0, -1)}")
logger.info(f"  pm_queue:inflight: {r.lrange('pm_queue:inflight', 0, -1)}")
logger.info(f"  validation_queue: {r.lrange('validation_queue', 0, -1)}")
logger.info(f"  validation_queue:inflight: {r.lrange('validation_queue:inflight', 0, -1)}")

# Check PRP evidence
prp_data = r.hgetall(f"prp:{prp_id}")
evidence = {
    k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in prp_data.items()
}
logger.info(f"\nEvidence collected:")
for k in ["tests_passed", "coverage_pct", "lint_passed", "implementation_complete"]:
    if k in evidence:
        logger.info(f"  {k}: {evidence[k]}")
