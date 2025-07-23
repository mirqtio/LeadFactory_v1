#!/usr/bin/env python3
"""
Debug integration agent deployment process
"""
import json
import logging
import os
import sys
import time

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("integration_debug")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.integration_agent import IntegrationAgent


def test_integration_agent():
    """Test integration agent with the completed PRP"""
    logger.info("=== Integration Agent Debug Test ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")

    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")

    # Create PRP with completed PM and Validator stages
    prp_id = "P3-003"
    r.hset(
        f"prp:{prp_id}",
        mapping={
            "id": prp_id,
            "title": "Fix Lead Explorer Audit Trail",
            "content": "P3-003 - Fix Lead Explorer Audit Trail\n\nImplement session-level event listeners to replace unreliable mapper-level events for audit logging. Ensure all Lead CRUD operations create audit log entries with proper change tracking and checksums.",
            "priority": "P3",
            "state": "integration",
            # PM evidence
            "tests_passed": "true",
            "coverage_pct": "85",
            "lint_passed": "true",
            "implementation_complete": "true",
            "files_modified": "lead_explorer/audit.py,database/session.py,tests/unit/lead_explorer/test_audit.py",
            "pm_completed_at": "2025-07-22T20:00:00Z",
            "pm_completed_by": "pm-test",
            # Validator evidence
            "validation_passed": "true",
            "quality_score": "95",
            "security_review": "passed",
            "performance_review": "passed",
            "validator_completed_at": "2025-07-22T20:05:00Z",
            "validator_completed_by": "validator-test",
        },
    )

    # Add to integration queue
    r.lpush("integration_queue", prp_id)
    logger.info(f"Created PRP {prp_id} in integration stage")

    # Create integration agent
    agent = IntegrationAgent("integration-debug")

    # Get PRP data
    prp_data = {k.decode(): v.decode() for k, v in r.hgetall(f"prp:{prp_id}").items()}

    logger.info("Building context...")
    context = agent.build_context(prp_id, prp_data)

    logger.info("System prompt:")
    logger.info("=" * 50)
    logger.info(context["messages"][0]["content"])
    logger.info("=" * 50)

    logger.info("User prompt:")
    logger.info("=" * 50)
    logger.info(context["messages"][1]["content"])
    logger.info("=" * 50)

    # Make single API call to see what Claude responds with
    logger.info("Making single API call to Claude...")
    start_time = time.time()
    response = agent.get_claude_response(context)
    api_time = time.time() - start_time

    if response:
        logger.info(f"✅ Got response in {api_time:.2f}s")
        logger.info("=" * 50)
        logger.info("CLAUDE RESPONSE:")
        logger.info("=" * 50)
        logger.info(response)
        logger.info("=" * 50)

        # Extract evidence
        evidence = agent.extract_evidence(response)
        logger.info(f"Evidence extracted: {json.dumps(evidence, indent=2)}")

        # Check completion
        is_complete = agent.check_completion_criteria(prp_id, evidence)
        logger.info(f"Is complete: {is_complete}")

        # Check for questions
        question = agent.extract_question(response)
        if question:
            logger.info(f"Question found: {question}")

    else:
        logger.error("❌ No response from Claude API")


if __name__ == "__main__":
    test_integration_agent()
