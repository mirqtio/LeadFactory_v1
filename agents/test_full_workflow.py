#!/usr/bin/env python3
"""
Test full agent workflow with proper queue handling
"""
import json
import logging
import os
import sys
import time

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_full_workflow")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.integration_agent import IntegrationAgent
from agents.roles.pm_agent import PMAgent
from agents.roles.validator_agent import ValidatorAgent


def test_full_workflow():
    """Test full workflow from PM through validator to integration"""
    logger.info("=== Full Agent Workflow Test ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")

    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")

    # Create PRP
    prp_id = "FULL-TEST-001"
    r.hset(
        f"prp:{prp_id}",
        mapping={
            "id": prp_id,
            "title": "Simple math function",
            "content": "Create a function that multiplies two numbers. Include comprehensive tests.",
            "priority": "high",
            "state": "dev",
        },
    )

    # Put PRP in pm queue
    r.lpush("pm_queue", prp_id)
    logger.info(f"Created PRP {prp_id} and added to pm_queue")

    # Create agents
    pm_agent = PMAgent("pm-test")
    validator_agent = ValidatorAgent("validator-test")
    integration_agent = IntegrationAgent("integration-test")

    # Stage 1: PM processes the PRP
    logger.info("\n=== Stage 1: PM Agent ===")

    # Use the agent's own queue processing (blmove)
    moved_prp = r.blmove("pm_queue", "pm_queue:inflight", timeout=1.0)
    if moved_prp:
        logger.info(f"PM agent processing: {moved_prp}")
        pm_agent.process_prp(moved_prp.decode() if isinstance(moved_prp, bytes) else moved_prp)

    # Check PM results
    validation_queue = r.lrange("validation_queue", 0, -1)
    logger.info(f"After PM: validation_queue = {[v.decode() if isinstance(v, bytes) else v for v in validation_queue]}")

    # Also check if it accidentally ended up in inflight
    validation_inflight = r.lrange("validation_queue:inflight", 0, -1)
    if validation_inflight:
        logger.warning(f"Found in validation_queue:inflight: {validation_inflight}")
        # Move it to the regular queue for the validator to process
        for item in validation_inflight:
            r.lrem("validation_queue:inflight", 0, item)
            r.lpush("validation_queue", item)
        validation_queue = r.lrange("validation_queue", 0, -1)
        logger.info(f"Fixed - moved to validation_queue: {validation_queue}")

    if not validation_queue:
        logger.error("PM agent failed to promote to validation queue")
        return False

    # Stage 2: Validator processes the PRP
    logger.info("\n=== Stage 2: Validator Agent ===")

    moved_prp = r.blmove("validation_queue", "validation_queue:inflight", timeout=1.0)
    if moved_prp:
        logger.info(f"Validator agent processing: {moved_prp}")
        validator_agent.process_prp(moved_prp.decode() if isinstance(moved_prp, bytes) else moved_prp)

    # Check validator results
    integration_queue = r.lrange("integration_queue", 0, -1)
    logger.info(
        f"After Validator: integration_queue = {[v.decode() if isinstance(v, bytes) else v for v in integration_queue]}"
    )

    # Check if validation failed and went back to PM
    pm_queue = r.lrange("pm_queue", 0, -1)
    if pm_queue:
        logger.warning(f"Validation failed, PRP back in pm_queue: {pm_queue}")
        prp_data = r.hgetall(f"prp:{prp_id}")
        validation_issues = prp_data.get(b"validation_issues", b"").decode()
        logger.warning(f"Validation issues: {validation_issues}")
        return False

    if not integration_queue:
        logger.error("Validator failed to promote to integration queue")
        return False

    # Stage 3: Integration processes the PRP
    logger.info("\n=== Stage 3: Integration Agent ===")

    moved_prp = r.blmove("integration_queue", "integration_queue:inflight", timeout=1.0)
    if moved_prp:
        logger.info(f"Integration agent processing: {moved_prp}")
        integration_agent.process_prp(moved_prp.decode() if isinstance(moved_prp, bytes) else moved_prp)

    # Check final state
    logger.info("\n=== Final State ===")
    prp_data = r.hgetall(f"prp:{prp_id}")
    final_state = {
        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
        for k, v in prp_data.items()
    }

    # Check completion
    is_complete = final_state.get("state") == "complete"
    has_pm_completion = "pm_completed_at" in final_state
    has_validator_completion = "validator_completed_at" in final_state
    has_integration_completion = "integration_completed_at" in final_state

    logger.info(f"State: {final_state.get('state')}")
    logger.info(f"PM completed: {has_pm_completion}")
    logger.info(f"Validator completed: {has_validator_completion}")
    logger.info(f"Integration completed: {has_integration_completion}")

    if is_complete and has_pm_completion and has_validator_completion and has_integration_completion:
        logger.info("\n✅ TEST PASSED: Full workflow completed successfully!")
        return True
    else:
        logger.error("\n❌ TEST FAILED: Workflow did not complete")

        # Show evidence collected
        logger.info("\nEvidence collected:")
        for k, v in sorted(final_state.items()):
            if k not in ["content", "title", "id"] and (
                "evidence" in k.lower() or "complete" in k.lower() or "passed" in k.lower()
            ):
                logger.info(f"  {k}: {v[:100]}..." if len(v) > 100 else f"  {k}: {v}")

        return False


if __name__ == "__main__":
    success = test_full_workflow()
    sys.exit(0 if success else 1)
