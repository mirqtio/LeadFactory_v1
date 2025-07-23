#!/usr/bin/env python3
"""
Test real PRP with enhanced persona workers
"""
import logging
import os
import sys
import time
from datetime import datetime

import redis
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.roles.integration_agent_v2 import IntegrationAgentV2
from agents.roles.pm_agent_v2 import PMAgentV2
from agents.roles.validator_agent_v2 import ValidatorAgentV2

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("/tmp/real_prp_deployment_v4.log"), logging.StreamHandler()],
)
logger = logging.getLogger("test_real_prp")

# Load environment
load_dotenv()


def load_prp_file(filepath: str) -> dict:
    """Load and parse PRP file"""
    with open(filepath, "r") as f:
        content = f.read()

    # Parse the PRP format
    prp_data = {
        "content": content,
        "id": "P3-003",  # From filename
        "title": "Fix Lead Explorer Audit Trail",
        "requirements": "",
        "success_criteria": "",
    }

    # Extract sections
    if "## Problem Statement" in content:
        problem_start = content.find("## Problem Statement")
        problem_end = content.find("##", problem_start + 1)
        prp_data["problem"] = content[problem_start:problem_end].strip()

    if "## Requirements" in content:
        req_start = content.find("## Requirements")
        req_end = content.find("##", req_start + 1)
        prp_data["requirements"] = content[req_start:req_end].strip()

    if "## Success Criteria" in content:
        criteria_start = content.find("## Success Criteria")
        criteria_end = (
            content.find("##", criteria_start + 1) if content.find("##", criteria_start + 1) != -1 else len(content)
        )
        prp_data["success_criteria"] = content[criteria_start:criteria_end].strip()

    return prp_data


def test_real_deployment():
    """Test real PRP deployment with persona workers"""
    # Redis connection
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))

    # Load the real PRP
    prp_file = "/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/.claude/PRPs/Completed/PRP-1001_P0-001_Fix_D4_Coordinator.md"
    prp_data = load_prp_file(prp_file)
    prp_id = prp_data["id"]

    logger.info(f"=== Real PRP Test - {prp_id} {prp_data['title']} ===")
    logger.info(f"Using API key ending in: ...{os.getenv('ANTHROPIC_API_KEY', '')[-4:]}")

    # Clear any existing data
    redis_client.flushall()
    logger.info("Cleared Redis")

    # Create PRP in Redis
    redis_client.hset(
        f"prp:{prp_id}",
        mapping={
            "id": prp_id,
            "title": prp_data["title"],
            "content": prp_data["content"],
            "requirements": prp_data["requirements"],
            "success_criteria": prp_data["success_criteria"],
            "state": "new",
            "created_at": datetime.utcnow().isoformat(),
        },
    )

    # Add to PM queue
    redis_client.lpush("pm_queue", prp_id)

    logger.info(f"Loaded PRP: {prp_id} - {prp_data['title']}")
    logger.info(f"Content length: {len(prp_data['content'])} characters")
    logger.info(f"Created PRP {prp_id} and added to pm_queue")

    # Stage 1: PM Agent
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 1: PM AGENT PROCESSING")
    logger.info("=" * 60)

    pm_agent = PMAgentV2("pm-real-test")

    logger.info(f"PM agent starting work on: {prp_id}")
    logger.info("This will take 30-60 seconds for Claude API call...")

    start_time = time.time()

    # Process one PRP
    pm_agent.process_prp(prp_id)

    pm_time = time.time() - start_time
    logger.info(f"PM agent completed in {pm_time:.1f}s")

    # Check PM results
    prp_state = redis_client.hgetall(f"prp:{prp_id}")
    prp_state = {k.decode(): v.decode() for k, v in prp_state.items()}

    logger.info("\nPM Evidence collected:")
    for key in ["tests_passed", "coverage_pct", "lint_passed", "implementation_complete", "files_modified"]:
        if key in prp_state:
            logger.info(f"  {key}: {prp_state[key]}")

    # Stage 2: Validator Agent
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 2: VALIDATOR AGENT PROCESSING")
    logger.info("=" * 60)

    # Move from validator inflight back to queue (since we're doing synchronous test)
    redis_client.lrem("validator_queue:inflight", 0, prp_id)
    redis_client.lpush("validator_queue", prp_id)

    validator_agent = ValidatorAgentV2("validator-real-test")

    logger.info(f"Validator agent reviewing: {prp_id}")
    logger.info("This will take 30-60 seconds for Claude API call...")

    start_time = time.time()
    validator_agent.process_prp(prp_id)
    val_time = time.time() - start_time

    logger.info(f"Validator completed in {val_time:.1f}s")

    # Check validator results
    prp_state = redis_client.hgetall(f"prp:{prp_id}")
    prp_state = {k.decode(): v.decode() for k, v in prp_state.items()}

    logger.info("\nValidator Evidence:")
    for key in ["validation_passed", "quality_score", "security_review", "performance_review"]:
        if key in prp_state:
            logger.info(f"  {key}: {prp_state[key]}")

    # Stage 3: Integration Agent
    logger.info("\n" + "=" * 60)
    logger.info("STAGE 3: INTEGRATION AGENT PROCESSING")
    logger.info("=" * 60)

    # Move from integration inflight back to queue
    redis_client.lrem("integration_queue:inflight", 0, prp_id)
    redis_client.lpush("integration_queue", prp_id)
    logger.info("Moved PRP from integration inflight back to queue")

    integration_agent = IntegrationAgentV2("integration-real-test")

    logger.info(f"Integration agent deploying: {prp_id}")
    logger.info("This will take 30-60 seconds for CI/CD...")

    start_time = time.time()
    integration_agent.process_prp(prp_id)
    int_time = time.time() - start_time

    logger.info(f"Integration completed in {int_time:.1f}s")

    # Final results
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)

    prp_state = redis_client.hgetall(f"prp:{prp_id}")
    prp_state = {k.decode(): v.decode() for k, v in prp_state.items()}

    logger.info(f"PRP State: {prp_state.get('state', 'unknown')}")
    logger.info(f"PM Completed: {'✅' if prp_state.get('pm_completed_at') else '❌'}")
    logger.info(f"Validator Completed: {'✅' if prp_state.get('validator_completed_at') else '❌'}")
    logger.info(f"Integration Completed: {'✅' if prp_state.get('integration_completed_at') else '❌'}")

    logger.info("\nKey Evidence Collected:")
    important_keys = [
        "implementation_complete",
        "tests_passed",
        "lint_passed",
        "coverage_pct",
        "validation_passed",
        "quality_score",
        "ci_passed",
        "deployed",
        "deployment_url",
        "commit_sha",
    ]

    for key in important_keys:
        if key in prp_state:
            logger.info(f"  {key}: {prp_state[key]}")

    total_time = pm_time + val_time + int_time
    logger.info(f"\nTotal execution time: {total_time:.1f}s")
    logger.info(f"  PM: {pm_time:.1f}s")
    logger.info(f"  Validator: {val_time:.1f}s")
    logger.info(f"  Integration: {int_time:.1f}s")

    # Estimate cost (rough)
    # ~10K tokens per agent call at $0.015 per 1K = $0.15 per call
    # 3 agents with ~4 calls each = 12 * $0.15 = $1.80
    # But we're using less calls now, so ~$0.50
    logger.info(f"\nEstimated cost: ${total_time * 0.004:.3f}")

    # Check conversation histories
    pm_history = redis_client.llen(f"prp:{prp_id}:history:pm")
    val_history = redis_client.llen(f"prp:{prp_id}:history:validator")
    int_history = redis_client.llen(f"prp:{prp_id}:history:integration")

    # Success check
    if prp_state.get("state") == "complete":
        logger.info("\n✅ SUCCESS: PRP completed full workflow and deployed!")
    else:
        logger.error("\n❌ FAILED: PRP did not complete workflow")
        logger.info("Check conversation history for details:")
        logger.info(f"  pm history: {pm_history} entries")
        logger.info(f"  validator history: {val_history} entries")
        logger.info(f"  integration history: {int_history} entries")

        # Show integration conversation to debug
        if int_history > 0:
            logger.info("\nIntegration conversation (last turn):")
            last_turn = redis_client.lindex(f"prp:{prp_id}:history:integration", -1)
            if last_turn:
                import json

                entry = json.loads(last_turn)
                logger.info(f"Role: {entry.get('role')}")
                logger.info(f"Content preview: {entry.get('content', '')[:500]}...")


if __name__ == "__main__":
    test_real_deployment()
