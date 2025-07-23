#!/usr/bin/env python3
"""
Test actual deployment of the PRP with focused file changes
"""
import json
import logging
import os
import sys
import time

import redis

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("deployment_test")

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from agents.core.config import config
from agents.roles.integration_agent import IntegrationAgent


def test_actual_deployment():
    """Test deployment with focus on specific PRP files only"""
    logger.info("=== Focused Deployment Test ===")
    logger.info(f"Using API key ending in: ...{config.anthropic_api_key[-4:]}")

    # Clear Redis
    r = redis.from_url(config.redis_url)
    r.flushdb()
    logger.info("Cleared Redis")

    # Create PRP with specific file list
    prp_id = "P3-003"
    prp_files = ["lead_explorer/audit.py", "database/session.py", "tests/unit/lead_explorer/test_audit.py"]

    r.hset(
        f"prp:{prp_id}",
        mapping={
            "id": prp_id,
            "title": "Fix Lead Explorer Audit Trail",
            "content": "Session-level event listeners for audit logging",
            "priority": "P3",
            "state": "integration",
            # PM evidence
            "tests_passed": "true",
            "coverage_pct": "85",
            "lint_passed": "true",
            "implementation_complete": "true",
            "files_modified": json.dumps(prp_files),
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

    # Create integration agent
    agent = IntegrationAgent("integration-deploy")

    # Get PRP data
    prp_data = {k.decode(): v.decode() for k, v in r.hgetall(f"prp:{prp_id}").items()}

    # Override the context to focus on specific files
    system_prompt = f"""You are a senior DevOps engineer handling the deployment of PRP {prp_id}.

Your task: Deploy the audit trail fix for Lead Explorer.

PRP SPECIFIC FILES TO DEPLOY:
- lead_explorer/audit.py (session-level event listeners)
- database/session.py (event registration)  
- tests/unit/lead_explorer/test_audit.py (updated tests)

IGNORE all other files in git status - focus ONLY on these PRP files.

Your responsibilities:
1. Create feature branch: feat/p3-003-audit-trail-fix
2. Add ONLY the PRP files listed above
3. Commit with message: "PRP-P3-003: Fix Lead Explorer audit trail with session-level events"
4. Push to GitHub
5. Create PR
6. Monitor CI and verify deployment

IMPORTANT: 
- IGNORE agent development files
- Focus ONLY on lead_explorer/ and database/session.py files
- Use git add with specific file paths, not git add .

When deployment succeeds, output:
```json
{{"key": "ci_passed", "value": "true"}}
{{"key": "deployed", "value": "true"}}
{{"key": "commit_sha", "value": "actual_sha"}}
{{"key": "pr_number", "value": "123"}}
```

Start by creating the feature branch and adding only the PRP-specific files."""

    user_prompt = f"""Deploy PRP {prp_id} with these specific files:
{chr(10).join('- ' + f for f in prp_files)}

Start with:
1. git checkout -b feat/p3-003-audit-trail-fix  
2. git add lead_explorer/audit.py database/session.py tests/unit/lead_explorer/test_audit.py
3. git commit -m "PRP-P3-003: Fix Lead Explorer audit trail with session-level events"

Proceed with deployment."""

    context = {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]}

    logger.info("Making focused deployment API call...")
    start_time = time.time()
    response = agent.get_claude_response(context)
    api_time = time.time() - start_time

    if response:
        logger.info(f"✅ Got response in {api_time:.2f}s")
        logger.info("=" * 50)
        logger.info("DEPLOYMENT RESPONSE:")
        logger.info("=" * 50)
        logger.info(response)
        logger.info("=" * 50)

        # Extract evidence
        evidence = agent.extract_evidence(response)
        logger.info(f"Evidence: {json.dumps(evidence, indent=2)}")

        # Enhanced evidence extraction for deployment indicators
        enhanced_evidence = agent.extract_evidence_multi_strategy(response)
        logger.info(f"Enhanced Evidence: {json.dumps(enhanced_evidence, indent=2)}")

        # Check completion
        is_complete = agent.check_completion_criteria(prp_id, enhanced_evidence)
        logger.info(f"Is complete: {is_complete}")

        if is_complete:
            logger.info("✅ DEPLOYMENT SUCCESSFUL!")

            # Save final state
            r.hset(f"prp:{prp_id}", "state", "complete")
            r.hset(f"prp:{prp_id}", "integration_completed_at", time.time())

            for key, value in enhanced_evidence.items():
                r.hset(f"prp:{prp_id}", key, value)

            logger.info("✅ PRP marked as complete in Redis")

        else:
            logger.info("🔄 Deployment in progress or needs continuation")

    else:
        logger.error("❌ No response from Claude API")

    # Show final state
    final_state = {k.decode(): v.decode() for k, v in r.hgetall(f"prp:{prp_id}").items()}
    logger.info(f"Final PRP state: {final_state.get('state', 'unknown')}")


if __name__ == "__main__":
    test_actual_deployment()
