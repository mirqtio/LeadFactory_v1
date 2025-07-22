#!/usr/bin/env python3
"""
Test validator with fixed evidence handling
"""
import json
import logging
import os
import sys

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_validator")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.validator_agent import ValidatorAgent

# Clear Redis
r = redis.from_url(config.redis_url)
r.flushdb()
logger.info("Cleared Redis")

# Create a simple PRP that already passed PM
prp_id = "VAL-TEST-001"
r.hset(f"prp:{prp_id}", mapping={
    "id": prp_id,
    "title": "Test validation",
    "content": "Simple test for validator",
    "priority": "P3",
    "state": "validation",
    # PM evidence
    "tests_passed": "true",
    "coverage_pct": "85",
    "lint_passed": "true",
    "implementation_complete": "true",
    "files_modified": json.dumps(["file1.py", "file2.py"]),  # List as JSON string
    "pm_completed_at": "2025-01-01T00:00:00Z",
    "pm_completed_by": "pm-test"
})

# Add to validator queue
r.lpush("validator_queue", prp_id)
logger.info(f"Created PRP {prp_id} and added to validator_queue")

# Create validator agent
agent = ValidatorAgent("validator-fix-test")

# Process
moved = r.blmove("validator_queue", "validator_queue:inflight", timeout=1.0)
if moved:
    prp_id_moved = moved.decode() if isinstance(moved, bytes) else moved
    logger.info(f"Processing {prp_id_moved}")
    
    try:
        agent.process_prp(prp_id_moved)
        logger.info("✅ Validator processing succeeded!")
    except Exception as e:
        logger.error(f"❌ Validator processing failed: {e}", exc_info=True)

# Check results
prp_data = r.hgetall(f"prp:{prp_id}")
val_evidence = {
    k.decode() if isinstance(k, bytes) else k: 
    v.decode() if isinstance(v, bytes) else v
    for k, v in prp_data.items()
    if (k.decode() if isinstance(k, bytes) else k) in [
        "validation_passed", "quality_score", "security_review"
    ]
}

if val_evidence:
    logger.info("\nValidator evidence:")
    for k, v in val_evidence.items():
        logger.info(f"  {k}: {v}")

# Check queues
int_queue = r.lrange("integration_queue", 0, -1)
val_queue = r.lrange("validator_queue", 0, -1)
logger.info(f"\nintegration_queue: {int_queue}")
logger.info(f"validator_queue: {val_queue}")