#!/usr/bin/env python3
"""
Test the Python agent system with a real PRP
"""
import json
import logging
import os
import sys
import threading
import time

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_real_prp")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.integration_agent import IntegrationAgent
from agents.roles.pm_agent import PMAgent
from agents.roles.validator_agent import ValidatorAgent


def load_prp_content():
    """Load the real PRP content"""
    prp_file = "/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/.claude/PRPs/Completed/PRP-1001_P0-001_Fix_D4_Coordinator.md"
    with open(prp_file, "r") as f:
        content = f.read()

    # Extract key information
    lines = content.split("\n")
    title = lines[0].replace("# ", "").strip()

    # Find the goal section
    goal_start = content.find("## Goal & Success Criteria")
    goal_end = content.find("## Context & Background")
    goal_section = content[goal_start:goal_end].strip()

    # Find the technical approach
    tech_start = content.find("## Technical Approach")
    tech_end = content.find("## Acceptance Criteria")
    tech_section = content[tech_start:tech_end].strip()

    # Create a simplified version for testing
    simplified_content = f"""
{goal_section}

{tech_section}

Key Requirements:
1. Replace mapper events with session events in lead_explorer/audit.py
2. Use before_flush, after_flush, and after_commit session events
3. Fix environment check - add ENABLE_AUDIT_LOGGING feature flag
4. Ensure all Lead CRUD operations create audit logs
5. Maintain SHA-256 checksums for tamper detection
6. Handle exceptions gracefully
7. Achieve minimum 80% test coverage on audit module

Files to modify:
- lead_explorer/audit.py - Main implementation
- tests/unit/lead_explorer/test_audit.py - Test updates if needed
"""

    return title, simplified_content


def test_real_prp():
    """Test the agent system with a real PRP"""
    logger.info("=== Real PRP Test - P3-003 Fix Lead Explorer Audit Trail ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")

    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")

    # Load PRP content
    title, content = load_prp_content()
    logger.info(f"Loaded PRP: {title}")
    logger.info(f"Content length: {len(content)} characters")

    # Create PRP in Redis
    prp_id = "P3-003"
    r.hset(
        f"prp:{prp_id}",
        mapping={"id": prp_id, "title": title, "content": content, "priority": "P3", "state": "validated"},
    )

    # Put PRP in pm queue
    r.lpush("pm_queue", prp_id)
    logger.info(f"Created PRP {prp_id} and added to pm_queue")

    # Create agents
    agents = {
        "pm": PMAgent("pm-real-test"),
        "validator": ValidatorAgent("validator-real-test"),
        "integration": IntegrationAgent("integration-real-test"),
    }

    # Stage 1: PM processes the PRP
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 1: PM AGENT PROCESSING")
    logger.info("=" * 60)

    start_time = time.time()

    # Use the agent's queue processing
    moved_prp = r.blmove("pm_queue", "pm_queue:inflight", timeout=1.0)
    if moved_prp:
        prp_to_process = moved_prp.decode() if isinstance(moved_prp, bytes) else moved_prp
        logger.info(f"PM agent starting work on: {prp_to_process}")
        logger.info("This will take 30-60 seconds for Claude API call...")

        try:
            agents["pm"].process_prp(prp_to_process)
        except Exception as e:
            logger.error(f"PM agent error: {e}", exc_info=True)

    pm_time = time.time() - start_time
    logger.info(f"PM agent completed in {pm_time:.1f}s")

    # Check PM results
    prp_data = r.hgetall(f"prp:{prp_id}")
    pm_evidence = {
        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
        for k, v in prp_data.items()
        if (k.decode() if isinstance(k, bytes) else k)
        in ["tests_passed", "coverage_pct", "lint_passed", "implementation_complete", "files_modified"]
    }

    if pm_evidence:
        logger.info("\nPM Evidence collected:")
        for k, v in pm_evidence.items():
            logger.info(f"  {k}: {v}")
    else:
        logger.warning("No PM evidence collected!")

    # Check if promoted to validator queue
    # First check if it's in the regular queue (accounting for running validator agents)
    val_queue = r.lrange("validator_queue", 0, -1)
    val_inflight = r.lrange("validator_queue:inflight", 0, -1)

    if not val_queue and val_inflight:
        # Move from inflight back to regular queue for our test
        for item in val_inflight:
            if item == prp_id.encode() or item.decode() == prp_id:
                r.lrem("validator_queue:inflight", 0, item)
                r.lpush("validator_queue", item)
                logger.info("Moved PRP from validator inflight back to queue")

    # Stage 2: Validator processes the PRP
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 2: VALIDATOR AGENT PROCESSING")
    logger.info("=" * 60)

    start_time = time.time()

    moved_prp = r.blmove("validator_queue", "validator_queue:inflight", timeout=1.0)
    if moved_prp:
        prp_to_process = moved_prp.decode() if isinstance(moved_prp, bytes) else moved_prp
        logger.info(f"Validator agent reviewing: {prp_to_process}")
        logger.info("This will take 30-60 seconds for Claude API call...")

        try:
            agents["validator"].process_prp(prp_to_process)
        except Exception as e:
            logger.error(f"Validator agent error: {e}", exc_info=True)
    else:
        logger.warning("No PRP found in validator queue!")

    val_time = time.time() - start_time
    logger.info(f"Validator completed in {val_time:.1f}s")

    # Check validator results
    prp_data = r.hgetall(f"prp:{prp_id}")
    val_evidence = {
        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
        for k, v in prp_data.items()
        if (k.decode() if isinstance(k, bytes) else k)
        in [
            "validation_passed",
            "quality_score",
            "security_review",
            "performance_review",
            "validation_issues",
            "required_changes",
        ]
    }

    if val_evidence:
        logger.info("\nValidator Evidence:")
        for k, v in val_evidence.items():
            logger.info(f"  {k}: {v}")

    # Check if validation passed or failed
    if val_evidence.get("validation_passed") == "false":
        logger.warning("Validation FAILED - PRP sent back to PM queue")
        logger.info(f"Issues: {val_evidence.get('validation_issues', 'None')}")
        return

    # Stage 3: Integration agent (only if validation passed)
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 3: INTEGRATION AGENT PROCESSING")
    logger.info("=" * 60)

    # Check integration queue
    int_queue = r.lrange("integration_queue", 0, -1)
    int_inflight = r.lrange("integration_queue:inflight", 0, -1)

    if not int_queue and int_inflight:
        # Move from inflight back to regular queue
        for item in int_inflight:
            if item == prp_id.encode() or item.decode() == prp_id:
                r.lrem("integration_queue:inflight", 0, item)
                r.lpush("integration_queue", item)
                logger.info("Moved PRP from integration inflight back to queue")

    start_time = time.time()

    moved_prp = r.blmove("integration_queue", "integration_queue:inflight", timeout=1.0)
    if moved_prp:
        prp_to_process = moved_prp.decode() if isinstance(moved_prp, bytes) else moved_prp
        logger.info(f"Integration agent deploying: {prp_to_process}")
        logger.info("This will take 30-60 seconds for Claude API call...")

        try:
            agents["integration"].process_prp(prp_to_process)
        except Exception as e:
            logger.error(f"Integration agent error: {e}", exc_info=True)
    else:
        logger.warning("No PRP found in integration queue!")

    int_time = time.time() - start_time
    logger.info(f"Integration completed in {int_time:.1f}s")

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)

    # Get final PRP state
    final_data = r.hgetall(f"prp:{prp_id}")
    final_state = {
        k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
        for k, v in final_data.items()
    }

    # Check completion status
    is_complete = final_state.get("state") == "complete"
    has_pm_completion = "pm_completed_at" in final_state
    has_validator_completion = "validator_completed_at" in final_state
    has_integration_completion = "integration_completed_at" in final_state

    logger.info(f"PRP State: {final_state.get('state', 'unknown')}")
    logger.info(f"PM Completed: {'✅' if has_pm_completion else '❌'}")
    logger.info(f"Validator Completed: {'✅' if has_validator_completion else '❌'}")
    logger.info(f"Integration Completed: {'✅' if has_integration_completion else '❌'}")

    # Show key evidence
    logger.info("\nKey Evidence Collected:")
    for k in [
        "implementation_complete",
        "tests_passed",
        "lint_passed",
        "coverage_pct",
        "validation_passed",
        "quality_score",
        "ci_passed",
        "deployed",
    ]:
        if k in final_state:
            logger.info(f"  {k}: {final_state[k]}")

    # Timing summary
    total_time = pm_time + val_time + int_time
    logger.info(f"\nTotal execution time: {total_time:.1f}s")
    logger.info(f"  PM: {pm_time:.1f}s")
    logger.info(f"  Validator: {val_time:.1f}s")
    logger.info(f"  Integration: {int_time:.1f}s")

    # Cost estimate (rough)
    # Assuming ~8K tokens per request (4K in, 4K out) x 3 agents
    # Sonnet 4: $3/$15 per 1M tokens
    input_cost = (8000 * 3 / 1_000_000) * 3  # $0.072
    output_cost = (8000 * 3 / 1_000_000) * 15  # $0.36
    total_cost = input_cost + output_cost
    logger.info(f"\nEstimated cost: ${total_cost:.3f}")

    # Success check
    if is_complete:
        logger.info("\n✅ SUCCESS: PRP completed full workflow!")
    else:
        logger.error("\n❌ FAILED: PRP did not complete workflow")
        logger.info("Check conversation history for details:")
        for role in ["pm", "validator", "integration"]:
            history_key = f"prp:{prp_id}:history:{role}"
            history_count = r.llen(history_key)
            logger.info(f"  {role} history: {history_count} entries")


if __name__ == "__main__":
    test_real_prp()
