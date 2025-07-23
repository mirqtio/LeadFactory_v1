#!/usr/bin/env python3
"""
Reliable queue worker - builds on base_worker with BRPOPLPUSH pattern
"""
import logging
import os
import time
from typing import Optional

from .base_worker import AgentWorker


class ReliableWorker(AgentWorker):
    """Enhanced worker with reliable queue pattern and Lua promotions"""

    def __init__(self, role: str, agent_id: str, model: str = None):
        super().__init__(role, agent_id, model)

        # Load and register Lua script
        lua_path = os.path.join(os.path.dirname(__file__), "promote.lua")
        with open(lua_path, "r") as f:
            lua_script = f.read()
        self.promote_sha = self.redis_client.script_load(lua_script)

        # Map roles to next queues
        self.next_queue_map = {
            "pm": "validation_queue",
            "dev": "validation_queue",
            "validator": "integration_queue",
            "validation": "integration_queue",
            "integration": "complete",
            "integrator": "complete",
        }

    def run(self):
        """Main worker loop with reliable queue pattern"""
        self.logger.info(f"Starting {self.agent_id} reliable worker")

        # Set up evidence requirements
        self.setup_evidence_schema()

        while True:
            try:
                # Atomic blocking move from queue to inflight
                prp_id = self.redis_client.brpoplpush(
                    self.queue, f"{self.queue}:inflight", timeout=10  # Timeout in seconds
                )

                if prp_id:
                    prp_id = prp_id.decode() if isinstance(prp_id, bytes) else prp_id
                    self.logger.info(f"Processing PRP: {prp_id}")

                    # Mark start time for watchdog
                    self.redis_client.hset(
                        f"prp:{prp_id}", mapping={"started_at": time.time(), "processing_by": self.agent_id}
                    )

                    # Process using existing base_worker logic
                    self.process_prp(prp_id)
                else:
                    # No work available
                    self.update_agent_status("idle")

            except Exception as e:
                self.logger.error(f"Error in worker loop: {e}", exc_info=True)
                time.sleep(5)

    def handle_completion(self, prp_id: str, evidence: dict):
        """Override to use Lua script for atomic promotion"""
        self.logger.info(f"Completing PRP {prp_id} with evidence: {evidence}")

        # Call parent to update Redis hash
        super().handle_completion(prp_id, evidence)

        # Use Lua script for atomic promotion
        next_queue = self.next_queue_map.get(self.role, None)
        if next_queue:
            try:
                result = self.redis_client.evalsha(
                    self.promote_sha,
                    2,  # number of keys
                    f"{self.queue}:inflight",  # KEYS[1]
                    f"prp:{prp_id}",  # KEYS[2]
                    next_queue,  # ARGV[1]
                    self.role,  # ARGV[2]
                )

                if isinstance(result, dict) and result.get("ok"):
                    self.logger.info(f"Promoted {prp_id} to {result.get('next', next_queue)}")
                elif isinstance(result, dict) and result.get("err"):
                    self.logger.error(f"Promotion failed: {result['err']}")
                    self.requeue_prp(prp_id, result["err"])

            except Exception as e:
                self.logger.error(f"Lua script error: {e}")
                self.requeue_prp(prp_id, str(e))

    def setup_evidence_schema(self):
        """Set up evidence requirements for each stage"""
        schemas = {
            "dev": ["tests_passed", "coverage_pct", "lint_passed", "implementation_complete"],
            "pm": ["tests_passed", "coverage_pct", "lint_passed", "implementation_complete"],
            "validation": ["validation_passed", "quality_score"],
            "validator": ["validation_passed", "quality_score"],
            "integration": ["ci_passed", "deployed"],
            "integrator": ["ci_passed", "deployed"],
        }

        for stage, keys in schemas.items():
            schema_key = f"cfg:evidence_schema:{stage}"
            # Use SADD for set of required keys
            self.redis_client.delete(schema_key)
            if keys:
                self.redis_client.sadd(schema_key, *keys)
