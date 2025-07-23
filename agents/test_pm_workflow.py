#!/usr/bin/env python3
"""
Test PM agent workflow with real API
"""
import json
import logging
import os
import sys
import time
import threading

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_pm_workflow")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.pm_agent import PMAgent


def test_pm_workflow():
    """Test PM agent completing a simple task"""
    logger.info("=== PM Agent Workflow Test ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")
    
    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")
    
    # Create PRP
    prp_id = "PM-TEST-001"
    r.hset(f"prp:{prp_id}", mapping={
        "id": prp_id,
        "title": "Add numbers function",
        "content": "Create a function that adds two numbers. Include tests.",
        "priority": "high",
        "state": "dev"
    })
    
    # Put PRP in pm queue (based on role="pm" in PMAgent)
    r.lpush("pm_queue", prp_id)
    logger.info(f"Created PRP {prp_id} and added to pm_queue")
    
    # Create PM agent
    agent = PMAgent("pm-test")
    
    # Run agent in thread for one iteration
    def run_agent():
        try:
            # Process one PRP
            agent.logger.info("Starting PM agent for one iteration")
            prp_id = agent.redis_client.blmove(
                agent.queue, 
                f"{agent.queue}:inflight",
                timeout=5.0
            )
            
            if prp_id:
                prp_id = prp_id.decode() if isinstance(prp_id, bytes) else prp_id
                agent.logger.info(f"Processing PRP: {prp_id}")
                agent.process_prp(prp_id)
            else:
                agent.logger.warning("No PRP found in queue")
                
        except Exception as e:
            agent.logger.error(f"Error in agent: {e}", exc_info=True)
    
    # Run agent
    agent_thread = threading.Thread(target=run_agent)
    agent_thread.start()
    
    # Wait for completion (max 60 seconds)
    logger.info("Waiting for agent to process PRP...")
    start_time = time.time()
    timeout = 60
    
    while time.time() - start_time < timeout:
        # Check if PRP moved to validator queue
        validator_queue = r.lrange("validator_queue", 0, -1)
        if prp_id.encode() in validator_queue or prp_id in [v.decode() if isinstance(v, bytes) else v for v in validator_queue]:
            logger.info("✅ SUCCESS: PRP promoted to validator_queue!")
            break
            
        # Check PRP state
        prp_data = r.hgetall(f"prp:{prp_id}")
        evidence = {
            k.decode() if isinstance(k, bytes) else k: 
            v.decode() if isinstance(v, bytes) else v
            for k, v in prp_data.items()
        }
        
        if "pm_completed_at" in evidence:
            logger.info(f"PM marked task complete at: {evidence['pm_completed_at']}")
            
        # Log evidence collected
        pm_evidence = {k: v for k, v in evidence.items() if k in [
            "tests_passed", "coverage_pct", "lint_passed", "implementation_complete"
        ]}
        if pm_evidence:
            logger.info(f"Evidence collected: {json.dumps(pm_evidence, indent=2)}")
            
        time.sleep(2)
    
    # Wait for thread
    agent_thread.join(timeout=5)
    
    # Final check
    logger.info("\n=== Final State ===")
    
    # Check queues
    pm_queue = r.lrange("pm_queue", 0, -1)
    pm_inflight = r.lrange("pm_queue:inflight", 0, -1)
    validator_queue = r.lrange("validator_queue", 0, -1)
    
    logger.info(f"pm_queue: {[v.decode() if isinstance(v, bytes) else v for v in pm_queue]}")
    logger.info(f"pm_queue:inflight: {[v.decode() if isinstance(v, bytes) else v for v in pm_inflight]}")
    logger.info(f"validator_queue: {[v.decode() if isinstance(v, bytes) else v for v in validator_queue]}")
    
    # Check PRP data
    prp_data = r.hgetall(f"prp:{prp_id}")
    evidence = {
        k.decode() if isinstance(k, bytes) else k: 
        v.decode() if isinstance(v, bytes) else v
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
    if prp_id.encode() in validator_queue or prp_id in [v.decode() if isinstance(v, bytes) else v for v in validator_queue]:
        logger.info("\n✅ TEST PASSED: PM agent successfully completed task and promoted to validator!")
    else:
        logger.error("\n❌ TEST FAILED: PRP not promoted to validator queue")


if __name__ == "__main__":
    test_pm_workflow()