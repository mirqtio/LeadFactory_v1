#!/usr/bin/env python3
"""
Real system test with actual Claude API calls
"""
import json
import logging
import os
import sys
import time
from datetime import datetime

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_real_system")

# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config


def setup_test_prp():
    """Create a test PRP in Redis"""
    r = redis.from_url(config.redis_url)
    
    prp_id = "TEST-REAL-001"
    prp_data = {
        "id": prp_id,
        "title": "Test Real Agent System",
        "content": """# Test PRP for Real Agent System

## Overview
This is a test PRP to validate the agent system with real Claude API calls.

## Requirements
1. Create a simple Python function that calculates factorial
2. Add unit tests with at least 80% coverage
3. Include proper error handling for negative numbers
4. Add docstring documentation

## Acceptance Criteria
- [ ] Function correctly calculates factorial for positive integers
- [ ] Raises ValueError for negative inputs
- [ ] Has comprehensive unit tests
- [ ] All tests pass with >80% coverage

## Technical Notes
- Use Python's built-in capabilities
- Follow PEP 8 style guidelines
- Include type hints""",
        "priority": "high",
        "status": "new",
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Clear any existing data
    r.delete(f"prp:{prp_id}")
    r.delete(f"prp:{prp_id}:history:pm")
    r.delete(f"prp:{prp_id}:history:validator")
    r.delete(f"prp:{prp_id}:history:integration")
    
    # Set PRP data
    r.hset(f"prp:{prp_id}", mapping=prp_data)
    
    # Add to dev queue
    r.lpush("dev_queue", prp_id)
    
    logger.info(f"Created test PRP: {prp_id}")
    return prp_id


def monitor_prp_progress(prp_id: str, timeout: int = 300):
    """Monitor PRP progress through the system"""
    r = redis.from_url(config.redis_url)
    start_time = time.time()
    last_state = None
    
    logger.info(f"Monitoring PRP {prp_id} (timeout: {timeout}s)")
    
    while time.time() - start_time < timeout:
        # Get PRP state
        prp_data = r.hgetall(f"prp:{prp_id}")
        if not prp_data:
            logger.error(f"PRP {prp_id} not found!")
            break
        
        # Decode state
        current_state = prp_data.get(b'state', b'unknown').decode()
        
        # Check which queue it's in
        queue_location = "unknown"
        if r.lpos("dev_queue", prp_id) is not None:
            queue_location = "dev_queue (pending)"
        elif r.lpos("dev_queue:inflight", prp_id) is not None:
            queue_location = "dev_queue:inflight (PM working)"
        elif r.lpos("validation_queue", prp_id) is not None:
            queue_location = "validation_queue (pending)"
        elif r.lpos("validation_queue:inflight", prp_id) is not None:
            queue_location = "validation_queue:inflight (Validator working)"
        elif r.lpos("integration_queue", prp_id) is not None:
            queue_location = "integration_queue (pending)"
        elif r.lpos("integration_queue:inflight", prp_id) is not None:
            queue_location = "integration_queue:inflight (Integration working)"
        
        # Log state changes
        if current_state != last_state or queue_location != "unknown":
            logger.info(f"PRP State: {current_state}, Location: {queue_location}")
            last_state = current_state
            
            # Log evidence if available
            evidence_keys = [
                'tests_passed', 'coverage_pct', 'implementation_complete',
                'validation_passed', 'quality_score',
                'deployed', 'ci_passed'
            ]
            
            evidence = {}
            for key in evidence_keys:
                value = prp_data.get(key.encode())
                if value:
                    evidence[key] = value.decode()
            
            if evidence:
                logger.info(f"Evidence: {json.dumps(evidence, indent=2)}")
        
        # Check if complete
        if current_state == "complete":
            logger.info("✅ PRP completed successfully!")
            
            # Show final evidence
            final_evidence = {}
            for k, v in prp_data.items():
                key = k.decode() if isinstance(k, bytes) else k
                value = v.decode() if isinstance(v, bytes) else v
                if any(term in key for term in ['complete', 'passed', 'score', 'deployed']):
                    final_evidence[key] = value
            
            logger.info(f"Final Evidence:\n{json.dumps(final_evidence, indent=2)}")
            return True
        
        elif current_state == "failed":
            logger.error("❌ PRP failed!")
            reason = prp_data.get(b'failed_reason', b'Unknown').decode()
            logger.error(f"Failure reason: {reason}")
            return False
        
        # Sleep before next check
        time.sleep(5)
    
    logger.error(f"Timeout waiting for PRP {prp_id} to complete")
    return False


def check_agent_activity():
    """Check which agents are active"""
    r = redis.from_url(config.redis_url)
    
    logger.info("\n=== Agent Status ===")
    agent_keys = r.keys("agent:*")
    
    for key in agent_keys:
        agent_data = r.hgetall(key)
        if agent_data:
            agent_id = key.decode().replace("agent:", "")
            status = agent_data.get(b'status', b'unknown').decode()
            current_prp = agent_data.get(b'current_prp', b'').decode()
            last_activity = agent_data.get(b'last_activity', b'').decode()
            
            logger.info(f"{agent_id}: status={status}, prp={current_prp}, last_activity={last_activity}")


def test_single_agent():
    """Test with a single PM agent"""
    logger.info("\n=== Testing Single PM Agent ===")
    
    from agents.roles.pm_agent import PMAgent
    
    # Create and run agent in background
    agent = PMAgent("test-pm-single")
    
    # Process one PRP
    prp_id = setup_test_prp()
    
    logger.info("Processing PRP with single agent...")
    agent.process_prp(prp_id)
    
    # Check results
    r = redis.from_url(config.redis_url)
    prp_data = r.hgetall(f"prp:{prp_id}")
    
    if prp_data.get(b'implementation_complete') == b'true':
        logger.info("✅ PM Agent completed implementation!")
        
        # Check what was implemented
        history = r.lrange(f"prp:{prp_id}:history:pm", 0, -1)
        if history:
            last_entry = json.loads(history[-1])
            logger.info(f"Implementation preview:\n{last_entry['response'][:500]}...")
    else:
        logger.error("❌ PM Agent did not complete implementation")


def test_full_system():
    """Test the full orchestrator system"""
    logger.info("\n=== Testing Full Orchestrator System ===")
    
    # Import here to avoid early initialization
    from agents.orchestrator import MainOrchestrator
    
    # Create PRP first
    prp_id = setup_test_prp()
    
    # Start orchestrator with 1 PM agent for testing
    orchestrator = MainOrchestrator(pm_count=1)
    
    logger.info("Starting orchestrator in background...")
    
    # Start in a thread
    import threading
    orchestrator_thread = threading.Thread(target=orchestrator.start)
    orchestrator_thread.daemon = True
    orchestrator_thread.start()
    
    # Give it time to start
    time.sleep(5)
    
    # Monitor progress
    success = monitor_prp_progress(prp_id, timeout=120)  # 2 minute timeout
    
    # Check agent activity
    check_agent_activity()
    
    # Shutdown
    orchestrator.running = False
    
    return success


def main():
    """Run the real system tests"""
    logger.info("=== Real Agent System Test ===")
    logger.info(f"Using Anthropic API key: sk-...{config.anthropic_api_key[-4:]}")
    logger.info(f"Redis URL: {config.redis_url}")
    
    # Check Redis connection
    try:
        r = redis.from_url(config.redis_url)
        r.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return
    
    # Test 1: Single agent test
    try:
        test_single_agent()
    except Exception as e:
        logger.error(f"Single agent test failed: {e}", exc_info=True)
    
    # Test 2: Full system test
    logger.info("\nWaiting 10 seconds before full system test...")
    time.sleep(10)
    
    try:
        success = test_full_system()
        if success:
            logger.info("\n🎉 Full system test PASSED!")
        else:
            logger.error("\n❌ Full system test FAILED!")
    except Exception as e:
        logger.error(f"Full system test error: {e}", exc_info=True)


if __name__ == "__main__":
    main()