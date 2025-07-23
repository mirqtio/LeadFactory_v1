#!/usr/bin/env python3
"""
Simple real test with actual API call
"""
import json
import logging
import os
import sys
import time

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("test_simple")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.pm_agent import PMAgent


def test_single_response():
    """Test a single Claude API response"""
    logger.info("=== Simple Real API Test ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")

    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")

    # Create simple PRP
    prp_id = "SIMPLE-001"
    r.hset(
        f"prp:{prp_id}",
        mapping={
            "id": prp_id,
            "title": "Simple test",
            "content": "Create a function that adds two numbers.",
            "priority": "high",
        },
    )

    # Create agent
    agent = PMAgent("pm-test")

    # Get initial context
    prp_data = {k.decode(): v.decode() for k, v in r.hgetall(f"prp:{prp_id}").items()}
    context = agent.build_context(prp_id, prp_data)

    logger.info("Sending request to Claude API...")
    logger.info(f"System prompt length: {len(context['messages'][0]['content'])} chars")
    logger.info(f"User prompt length: {len(context['messages'][1]['content'])} chars")

    # Make API call
    start_time = time.time()
    response = agent.get_claude_response(context)
    api_time = time.time() - start_time

    if response:
        logger.info(f"✅ Got response in {api_time:.2f}s")
        logger.info(f"Response length: {len(response)} chars")
        logger.info(f"Response preview: {response[:200]}...")

        # Log full response for debugging
        logger.info("=== FULL RESPONSE ===")
        logger.info(response)
        logger.info("=== END RESPONSE ===")

        # Check for evidence
        evidence = agent.extract_evidence(response)
        if evidence:
            logger.info(f"Evidence found: {json.dumps(evidence, indent=2)}")
        else:
            logger.info("No evidence found in response")

        # Check for questions
        question = agent.extract_question(response)
        if question:
            logger.info(f"Question found: {question}")

    else:
        logger.error("❌ No response from Claude API")

    # Check conversation history
    history = r.lrange(f"prp:{prp_id}:history:pm", 0, -1)
    logger.info(f"Conversation history entries: {len(history)}")

    # Save conversation
    if response:
        agent.save_conversation_turn(prp_id, context, response)
        logger.info("Saved conversation to history")


if __name__ == "__main__":
    test_single_response()
