#!/usr/bin/env python3
"""
Simple PM agent test without threading
"""
import json
import logging
import os
import sys
import time

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_pm_simple")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.pm_agent import PMAgent


def test_pm_simple():
    """Test PM agent completing a simple task"""
    logger.info("=== Simple PM Agent Test ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")

    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")

    # Create PRP
    prp_id = "PM-SIMPLE-001"
    r.hset(
        f"prp:{prp_id}",
        mapping={
            "id": prp_id,
            "title": "Add numbers function",
            "content": "Create a function that adds two numbers. Include tests with 100% coverage.",
            "priority": "high",
            "state": "dev",
        },
    )

    # Put PRP in pm queue
    r.lpush("pm_queue", prp_id)
    logger.info(f"Created PRP {prp_id} and added to pm_queue")

    # Create PM agent
    agent = PMAgent("pm-test")

    # Process the PRP directly
    logger.info("Processing PRP...")
    agent.process_prp(prp_id)

    # Check results
    logger.info("\n=== Results ===")

    # Check queues
    pm_queue = r.lrange("pm_queue", 0, -1)
    pm_inflight = r.lrange("pm_queue:inflight", 0, -1)
    validation_queue = r.lrange("validation_queue", 0, -1)

    logger.info(f"pm_queue: {[v.decode() if isinstance(v, bytes) else v for v in pm_queue]}")
    logger.info(f"pm_queue:inflight: {[v.decode() if isinstance(v, bytes) else v for v in pm_inflight]}")
    logger.info(f"validation_queue: {[v.decode() if isinstance(v, bytes) else v for v in validation_queue]}")

    # Check PRP data
    prp_data = r.hgetall(f"prp:{prp_id}")
    evidence = {
        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
        for k, v in prp_data.items()
    }

    logger.info(f"\nPRP Evidence:")
    for k, v in sorted(evidence.items()):
        if k not in ["content", "title", "id"]:  # Skip verbose fields
            logger.info(f"  {k}: {v}")

    # Check conversation history
    history = r.lrange(f"prp:{prp_id}:history:pm", 0, -1)
    logger.info(f"\nConversation turns: {len(history)}")

    # Verdict
    if prp_id.encode() in validation_queue or prp_id in [
        v.decode() if isinstance(v, bytes) else v for v in validation_queue
    ]:
        logger.info("\n✅ TEST PASSED: PM agent successfully completed task and promoted to validation!")
        return True
    else:
        logger.error("\n❌ TEST FAILED: PRP not promoted to validation queue")
        return False


if __name__ == "__main__":
    success = test_pm_simple()
    sys.exit(0 if success else 1)
