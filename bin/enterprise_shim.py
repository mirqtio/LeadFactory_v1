#!/usr/bin/env python3
"""
Enterprise Redis-Tmux Bridge Shim
Integrates working tmux notification system with enterprise Redis queue infrastructure
"""

import os
import sys

# Ensure we can import from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from core.config import get_settings
from infra.agent_coordinator import AgentCoordinator, AgentType, PRPState
from infra.redis_queue import QueueMessage, RedisQueueBroker

# Project root already added above


class EnterpriseShim:
    """
    Bridge between enterprise Redis queue system and tmux Claude instances
    Combines the reliability of the enterprise architecture with tmux push notifications
    """

    def __init__(self, agent_type: AgentType, tmux_session: str = "leadstack"):
        self.agent_type = agent_type
        self.tmux_session = tmux_session
        self.agent_id = f"{agent_type.value}_{os.getpid()}"

        # Initialize enterprise components
        self.settings = get_settings()
        self.queue_broker = RedisQueueBroker()
        self.agent_coordinator = AgentCoordinator(broker=self.queue_broker)

        # Queue names based on agent type
        self.queue_names = self._get_queue_names()
        self.tmux_pane = self._get_tmux_pane_name()

        # Logging
        self.logger = logging.getLogger(f"enterprise_shim_{agent_type.value}")
        logging.basicConfig(level=logging.INFO)

        # Running flag and evidence monitoring
        self.running = False
        self.current_prp = None
        self.evidence_timeout = 30 * 60  # 30 minutes
        self.last_activity = time.time()

        self.logger.info(f"Enterprise shim initialized for {agent_type.value} -> {self.tmux_pane}")
        self.logger.info(f"Watching queue names: {self.queue_names}")
        self.logger.info(f"Redis URL: {self.settings.redis_url}")

    def _get_queue_names(self) -> list[str]:
        """Get queue names based on agent type"""
        queue_map = {
            AgentType.ORCHESTRATOR: ["orchestrator_queue"],
            AgentType.PM: ["dev_queue"],  # PM handles development tasks
            AgentType.VALIDATOR: ["validation_queue"],
            AgentType.INTEGRATOR: ["integration_queue"],
        }
        return queue_map.get(self.agent_type, ["general_queue"])

    def _get_tmux_pane_name(self) -> str:
        """Get tmux pane name based on agent type"""
        pane_map = {
            AgentType.ORCHESTRATOR: "orchestrator",
            AgentType.PM: "dev-1",  # Default to dev-1, can be overridden
            AgentType.VALIDATOR: "validator",
            AgentType.INTEGRATOR: "integrator",
        }
        return pane_map.get(self.agent_type, "unknown")

    async def send_to_tmux(self, message: str):
        """Send message to tmux pane using enterprise-aware formatting"""
        try:
            # Enhanced message with enterprise context
            timestamp = datetime.utcnow().strftime("%H:%M:%S")
            formatted_message = f"""🏢 ENTERPRISE QUEUE MESSAGE [{timestamp}]

{message}

Agent: {self.agent_id} | Type: {self.agent_type.value}
Queue System: Redis Enterprise | Mode: Reliable BLMOVE
Use Redis commands for queue management:
- Check status: redis-cli HGET agent:{self.agent_id} status
- Update evidence: redis-cli HSET prp:{{id}} {{key}} {{value}}
- Promote PRP: Use promote.lua script for atomic transitions"""

            # Send message content
            proc1 = subprocess.run(
                ["tmux", "send-keys", "-t", f"{self.tmux_session}:{self.tmux_pane}", formatted_message],
                capture_output=True,
                text=True,
            )

            if proc1.returncode != 0:
                self.logger.error(f"Failed to send message to tmux: {proc1.stderr}")
                return

            # Small delay to ensure message is processed before Enter
            await asyncio.sleep(0.2)

            # Send Enter key separately - try multiple approaches
            enter_success = False
            for enter_method in ["C-m", "Enter", "Return"]:
                proc2 = subprocess.run(
                    ["tmux", "send-keys", "-t", f"{self.tmux_session}:{self.tmux_pane}", enter_method],
                    capture_output=True,
                    text=True,
                )

                if proc2.returncode == 0:
                    enter_success = True
                    self.logger.info(f"Sent message to {self.tmux_pane} using {enter_method}")
                    break
                else:
                    self.logger.warning(f"Enter method {enter_method} failed: {proc2.stderr}")

            if not enter_success:
                self.logger.error(f"All Enter methods failed for pane {self.tmux_pane}")

                # Try to send a second Enter after additional delay as final attempt
                await asyncio.sleep(0.3)
                proc3 = subprocess.run(
                    ["tmux", "send-keys", "-t", f"{self.tmux_session}:{self.tmux_pane}", "C-m"],
                    capture_output=True,
                    text=True,
                )
                if proc3.returncode == 0:
                    self.logger.info(f"Final retry Enter successful for {self.tmux_pane}")
                else:
                    self.logger.error(f"Final retry failed: {proc3.stderr}")

        except Exception as e:
            self.logger.error(f"Error sending to tmux: {e}")

    def capture_tmux_pane_output(self) -> str:
        """Capture recent output from tmux pane for evidence detection"""
        try:
            # Capture last 1000 lines from tmux pane
            proc = subprocess.run(
                ["tmux", "capture-pane", "-pJS", "-1000", "-t", f"{self.tmux_session}:{self.tmux_pane}"],
                capture_output=True,
                text=True,
            )

            if proc.returncode == 0:
                return proc.stdout
            else:
                self.logger.error(f"Failed to capture tmux pane: {proc.stderr}")
                return ""

        except Exception as e:
            self.logger.error(f"Error capturing tmux pane: {e}")
            return ""

    def detect_evidence_footer(self, pane_output: str) -> tuple[bool, dict, list]:
        """
        Detect EVIDENCE_COMPLETE footer in tmux pane output

        Returns:
            (footer_found, evidence_data, questions)
        """
        if not pane_output:
            return False, {}, []

        lines = pane_output.strip().split("\n")
        questions = []
        evidence_data = {}
        footer_found = False

        # Process lines in reverse to find the most recent footer
        for i in range(len(lines) - 1, -1, -1):
            line = lines[i].strip()

            # Check for EVIDENCE_COMPLETE footer
            if line.startswith("EVIDENCE_COMPLETE "):
                try:
                    json_part = line[len("EVIDENCE_COMPLETE ") :].strip()
                    evidence_data = json.loads(json_part)
                    footer_found = True

                    # Look for questions above the footer (in preceding lines)
                    for j in range(max(0, i - 10), i):  # Check up to 10 lines before
                        prev_line = lines[j].strip()
                        if prev_line.startswith("QUESTION:"):
                            question_text = prev_line[len("QUESTION:") :].strip()
                            if question_text:
                                questions.append(question_text)

                    break

                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse evidence JSON: {e}")
                    self.logger.error(f"Raw footer line: {line}")
                    # Treat as malformed footer - still found but no data
                    footer_found = True
                    break

        return footer_found, evidence_data, questions

    async def handle_evidence_completion(self, evidence_data: dict, questions: list):
        """Handle evidence completion and PRP promotion"""
        if not self.current_prp:
            self.logger.warning("Evidence footer detected but no current PRP")
            return

        try:
            prp_key = f"prp:{self.current_prp}"

            # Store evidence in Redis
            evidence_fields = {}
            for key in evidence_data.get("keys", []):
                evidence_fields[key] = "true"

            # Add metadata
            evidence_fields.update(
                {
                    "stage": evidence_data.get("stage", "unknown"),
                    "success": str(evidence_data.get("success", False)),
                    "completed_at": datetime.utcnow().isoformat(),
                    "agent_id": self.agent_id,
                    "agent_type": self.agent_type.value,
                }
            )

            # Store evidence
            for field, value in evidence_fields.items():
                subprocess.run(
                    ["redis-cli", "-u", self.settings.redis_url, "HSET", prp_key, field, value], capture_output=True
                )

            # Handle questions
            if questions:
                for question in questions:
                    question_payload = json.dumps(
                        {
                            "prp_id": self.current_prp,
                            "question": question,
                            "from_agent": self.agent_id,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                    subprocess.run(
                        ["redis-cli", "-u", self.settings.redis_url, "LPUSH", "qa_questions", question_payload],
                        capture_output=True,
                    )

            # Promote PRP using promote.lua script
            stage = evidence_data.get("stage", "dev")
            next_queue = self._get_next_queue(stage)

            if next_queue:
                # Load and execute promote.lua script
                promote_script = Path(__file__).parent.parent / "redis_scripts/promote.lua"
                if promote_script.exists():
                    # Execute promotion
                    promote_result = subprocess.run(
                        [
                            "redis-cli",
                            "-u",
                            self.settings.redis_url,
                            "EVAL",
                            promote_script.read_text(),
                            "3",  # Number of keys
                            f"prp_{stage}_queue",  # Source queue
                            next_queue,  # Destination queue
                            prp_key,  # Evidence key
                            "promote_prp",  # Command
                            json.dumps(evidence_data.get("keys", [])),  # Required fields
                            "strict",  # Validation mode
                            self.current_prp,  # PRP ID
                        ],
                        capture_output=True,
                        text=True,
                    )

                    if promote_result.returncode == 0:
                        self.logger.info(f"PRP {self.current_prp} promoted from {stage} to {next_queue}")
                    else:
                        self.logger.error(f"Promotion failed: {promote_result.stderr}")
                else:
                    self.logger.error("promote.lua script not found")

            # Clear current PRP
            self.current_prp = None
            self.last_activity = time.time()

            self.logger.info(f"Evidence processing completed for PRP {self.current_prp}")

        except Exception as e:
            self.logger.error(f"Error handling evidence completion: {e}")

    def _get_next_queue(self, current_stage: str) -> str:
        """Get next queue based on current stage"""
        stage_map = {"dev": "validation_queue", "validation": "integration_queue", "integration": "completion_queue"}
        return stage_map.get(current_stage, "completion_queue")

    async def process_prp_id(self, prp_id: str, queue_name: str):
        """Process PRP ID using enterprise patterns and send to tmux"""
        try:
            # Get PRP data from Redis hash
            prp_key = f"prp:{prp_id}"
            prp_data = {}

            # Try to get PRP data from hash
            try:
                raw_data = subprocess.run(
                    ["redis-cli", "-u", self.settings.redis_url, "HGETALL", prp_key], capture_output=True, text=True
                ).stdout.strip()

                if raw_data:
                    # Parse Redis HGETALL output (key1 value1 key2 value2...)
                    lines = raw_data.split("\n")
                    for i in range(0, len(lines), 2):
                        if i + 1 < len(lines):
                            prp_data[lines[i]] = lines[i + 1]
            except Exception as e:
                self.logger.warning(f"Could not fetch PRP data for {prp_id}: {e}")

            # Use PRP data or defaults
            description = prp_data.get("description", f"Process PRP {prp_id}")
            priority = prp_data.get("priority", "normal")

            # Track current PRP for evidence monitoring
            self.current_prp = prp_id
            self.last_activity = time.time()

            # Update agent status
            await self.agent_coordinator.update_agent_heartbeat(agent_id=self.agent_id, status="processing")

            # Format message based on agent type
            if self.agent_type == AgentType.ORCHESTRATOR:
                # Shorter format for orchestrator to avoid paste mode issues
                tmux_message = f"🎯 ORCHESTRATOR: Process PRP {prp_id} | Task: {description} | Priority: {priority} | Assign to appropriate queue and monitor progress."

            elif self.agent_type == AgentType.PM:
                tmux_message = f"""🔥 PRP DEVELOPMENT ASSIGNMENT: {prp_id}

Task: {description}
Priority: {priority}

Please implement this PRP using enterprise workflow:
- Set evidence key 'development_started=true'
- Follow CLAUDE.md implementation guidelines  
- Run validation: make quick-check
- Update progress: redis-cli HSET prp:{prp_id} progress_pct {{percentage}}
- Mark complete with evidence footer

PRP Details: {json.dumps(prp_data, indent=2)}"""

            elif self.agent_type == AgentType.VALIDATOR:
                tmux_message = f"""✅ PRP VALIDATION REQUEST: {prp_id}

Task: {description}
Priority: {priority}

Please validate this PRP using enterprise quality gates:
- Check evidence: redis-cli HGETALL prp:{prp_id}
- Run comprehensive tests: make bpci
- Verify coverage ≥80%: check coverage reports
- Update evidence: redis-cli HSET prp:{prp_id} validation_passed true
- Use promote.lua to advance to integration queue

PRP Details: {json.dumps(prp_data, indent=2)}"""

            elif self.agent_type == AgentType.INTEGRATOR:
                tmux_message = f"""🚀 PRP INTEGRATION REQUEST: {prp_id}

Task: {description}
Priority: {priority}

Please integrate this validated PRP:
- Verify validation evidence complete
- Deploy to VPS: ssh deploy commands
- Run integration tests
- Update evidence: redis-cli HSET prp:{prp_id} deploy_ok true
- Use promote.lua for final completion

SSH Access: {os.getenv('VPS_SSH_USER', 'user')}@{os.getenv('VPS_SSH_HOST', 'host')}
PRP Details: {json.dumps(prp_data, indent=2)}"""

            else:
                tmux_message = f"📋 TASK: {prp_id}\n{json.dumps(prp_data, indent=2)}"

            # Send to tmux
            await self.send_to_tmux(tmux_message)

            # Mark as processing in Redis
            subprocess.run(
                [
                    "redis-cli",
                    "-u",
                    self.settings.redis_url,
                    "HSET",
                    prp_key,
                    "stage_started_at",
                    datetime.utcnow().isoformat(),
                    "processing_agent",
                    self.agent_id,
                ],
                capture_output=True,
            )

        except Exception as e:
            self.logger.error(f"Error processing PRP {prp_id}: {e}")
            # Mark as failed in Redis
            subprocess.run(
                [
                    "redis-cli",
                    "-u",
                    self.settings.redis_url,
                    "HSET",
                    f"prp:{prp_id}",
                    "processing_error",
                    str(e),
                    "error_timestamp",
                    datetime.utcnow().isoformat(),
                ],
                capture_output=True,
            )

    async def run(self):
        """Main loop using enterprise queue patterns"""
        self.running = True
        print(f"🚀 STARTING SHIM: {self.agent_type.value}")
        self.logger.info(f"Starting enterprise shim for {self.agent_type.value}")

        # Register agent with coordinator
        print(f"📋 REGISTERING AGENT: {self.agent_id}")
        await self.agent_coordinator.register_agent(agent_id=self.agent_id, agent_type=self.agent_type, capacity=1.0)
        print(f"✅ AGENT REGISTERED - STARTING MAIN LOOP")

        try:
            while self.running:
                # Use BLMOVE pattern for reliable queue processing
                prp_id = None
                queue_name = None

                # Debug logging
                print(f"🔍 LOOP: Checking queues {self.queue_names}")
                print(f"🔗 Using Redis URL: {self.settings.redis_url}")

                # Check queue lengths
                for q_name in self.queue_names:
                    # Use localhost URL if settings points to docker container
                    redis_url = (
                        self.settings.redis_url.replace("redis://redis:", "redis://localhost:")
                        if "redis://redis:" in self.settings.redis_url
                        else self.settings.redis_url
                    )
                    try:
                        result = subprocess.run(
                            ["redis-cli", "-u", redis_url, "LLEN", q_name], capture_output=True, text=True, timeout=2
                        )
                        length = result.stdout.strip()
                        print(f"📊 Queue {q_name}: '{length}' items (returncode: {result.returncode})")
                        if result.stderr:
                            print(f"  stderr: {result.stderr}")
                    except Exception as e:
                        print(f"❌ Error checking {q_name}: {e}")

                # Try to get PRP from any of our queues using BLMOVE to inflight
                for q_name in self.queue_names:
                    inflight_queue = f"{q_name}:inflight"

                    try:
                        # BLMOVE queue_name inflight_queue RIGHT LEFT timeout
                        # Use localhost URL if settings points to docker container
                        redis_url = (
                            self.settings.redis_url.replace("redis://redis:", "redis://localhost:")
                            if "redis://redis:" in self.settings.redis_url
                            else self.settings.redis_url
                        )
                        result = subprocess.run(
                            ["redis-cli", "-u", redis_url, "BLMOVE", q_name, inflight_queue, "RIGHT", "LEFT", "1"],
                            capture_output=True,
                            text=True,
                            timeout=3,
                        )

                        if result.returncode == 0 and result.stdout.strip():
                            prp_id = result.stdout.strip()
                            queue_name = q_name
                            break

                    except Exception as e:
                        self.logger.error(f"Error in BLMOVE from {q_name}: {e}")
                        continue

                if prp_id and queue_name:
                    self.logger.info(f"Received PRP {prp_id} from {queue_name}")
                    print(f"🔥 PROCESSING: {prp_id} from {queue_name}")
                    await self.process_prp_id(prp_id, queue_name)
                else:
                    # Check for evidence completion if we have a current PRP
                    if self.current_prp:
                        pane_output = self.capture_tmux_pane_output()
                        if pane_output:
                            footer_found, evidence_data, questions = self.detect_evidence_footer(pane_output)

                            if footer_found:
                                self.logger.info(f"Evidence footer detected for PRP {self.current_prp}")
                                await self.handle_evidence_completion(evidence_data, questions)
                            elif time.time() - self.last_activity > self.evidence_timeout:
                                # Evidence timeout - re-queue PRP and log timeout
                                self.logger.warning(f"Evidence timeout for PRP {self.current_prp}")

                                timeout_payload = json.dumps(
                                    {
                                        "prp_id": self.current_prp,
                                        "error": "evidence_timeout",
                                        "timeout_seconds": self.evidence_timeout,
                                        "agent_id": self.agent_id,
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }
                                )

                                subprocess.run(
                                    [
                                        "redis-cli",
                                        "-u",
                                        self.settings.redis_url,
                                        "LPUSH",
                                        "timeout_queue",
                                        timeout_payload,
                                    ],
                                    capture_output=True,
                                )

                                self.current_prp = None
                                self.last_activity = time.time()

                    # Heartbeat during idle periods
                    await self.agent_coordinator.update_agent_heartbeat(
                        agent_id=self.agent_id, status="idle" if not self.current_prp else "processing"
                    )

        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            # Unregister agent
            await self.agent_coordinator.unregister_agent(self.agent_id)
            self.logger.info(f"Enterprise shim stopped for {self.agent_type.value}")

    def stop(self):
        """Stop the shim"""
        self.running = False
        self.logger.info("Stopping enterprise shim...")


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python enterprise_shim.py <agent_type> [tmux_session]")
        print("Agent types: orchestrator, pm, validator, integrator")
        sys.exit(1)

    agent_type_str = sys.argv[1].lower()
    tmux_session = sys.argv[2] if len(sys.argv) > 2 else "leadstack"

    # Map string to AgentType
    type_map = {
        "orchestrator": AgentType.ORCHESTRATOR,
        "pm": AgentType.PM,
        "dev": AgentType.PM,  # Alias
        "validator": AgentType.VALIDATOR,
        "integrator": AgentType.INTEGRATOR,
    }

    agent_type = type_map.get(agent_type_str)
    if not agent_type:
        print(f"Unknown agent type: {agent_type_str}")
        print(f"Valid types: {list(type_map.keys())}")
        sys.exit(1)

    # Create and run shim
    shim = EnterpriseShim(agent_type=agent_type, tmux_session=tmux_session)

    # Handle graceful shutdown
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down...")
        shim.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the shim
    await shim.run()


if __name__ == "__main__":
    asyncio.run(main())
