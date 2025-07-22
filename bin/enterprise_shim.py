#!/usr/bin/env python3
"""
Enterprise Shim - Redis to Tmux Message Bridge
Monitors Redis queues and pushes messages to tmux panes for AI agents
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import redis


class AgentType(Enum):
    ORCHESTRATOR = "orchestrator"
    PM = "pm"
    VALIDATOR = "validator"
    INTEGRATOR = "integrator"


class EnterpriseShim:
    def __init__(self, agent_type: AgentType, session: str, window: str, queue_name: str, redis_url: str):
        self.agent_type = agent_type
        self.session = session
        self.window = window
        self.queue_name = queue_name
        self.redis_client = redis.from_url(redis_url)
        self.running = True

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        print(f"Enterprise Shim initialized for {agent_type.value} agent")
        print(f"Session: {session}, Window: {window}, Queue: {queue_name}")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False

    def send_to_tmux(self, message: str):
        """Send message to tmux pane"""
        try:
            # First send the message
            cmd = ["tmux", "send-keys", "-t", f"{self.session}:{self.window}", message]
            subprocess.run(cmd, check=True)

            # Then send Enter key separately
            enter_cmd = ["tmux", "send-keys", "-t", f"{self.session}:{self.window}", "Enter"]
            subprocess.run(enter_cmd, check=True)

            print(f"Message sent to {self.window}: {message[:100]}...")
        except subprocess.CalledProcessError as e:
            print(f"Failed to send message to tmux: {e}")

    def process_prp_id(self, prp_id: str, queue_name: str):
        """Process a PRP ID from the queue"""
        print(f"Processing PRP ID: {prp_id} from {queue_name}")

        # Retrieve PRP data from Redis hash
        prp_key = f"prp:{prp_id}"
        prp_data = self.redis_client.hgetall(prp_key)

        if not prp_data:
            print(f"Warning: No data found for {prp_key}")
            return

        # Decode bytes to strings
        prp_data = {k.decode(): v.decode() for k, v in prp_data.items()}

        # Extract key fields
        title = prp_data.get("title", "Unknown")
        description = prp_data.get("description", "No description")
        priority = prp_data.get("priority", "medium")
        status = prp_data.get("status", "unknown")

        # Format message based on agent type
        if self.agent_type == AgentType.ORCHESTRATOR:
            tmux_message = f"""📋 ORCHESTRATOR UPDATE: {prp_id}
Status: {status} | Priority: {priority}
Title: {title}

System notification: PRP {prp_id} requires attention.
Review queue status and assign to appropriate PM agent."""

        elif self.agent_type == AgentType.PM:
            # CRITICAL: Minimal message to prevent context overflow
            tmux_message = f"""🔥 PRP ASSIGNMENT: {prp_id}

Task: {description}
Priority: {priority}

Development workflow (NO GitHub push):
- redis-cli HSET prp:{prp_id} development_started true
- Follow CLAUDE.md guidelines  
- Run: make quick-check (local validation only)
- Complete with EVIDENCE_COMPLETE footer
- DO NOT push to GitHub - that's integrator's job

Source: redis-cli HGET prp:{prp_id} source_file
Full details: redis-cli HGETALL prp:{prp_id}"""

        elif self.agent_type == AgentType.VALIDATOR:
            tmux_message = f"""✅ VALIDATION REQUEST: {prp_id}

PM has completed development. Please review:
Title: {title}
Priority: {priority}

Validation checklist:
- Review implementation quality
- Run PRP completion validator (must score 100/100)
- Check test coverage and CI readiness
- Verify all acceptance criteria met

Evidence: redis-cli HGETALL prp:{prp_id}
If approved: Update status to 'integration'
If rejected: Return to PM with feedback"""

        elif self.agent_type == AgentType.INTEGRATOR:
            tmux_message = f"""🚀 INTEGRATION REQUEST: {prp_id}

Validator approved. Ready for CI/CD:
Title: {title}
Priority: {priority}

Integration workflow:
- Acquire merge lock: redis-cli SET merge:lock {prp_id}
- Merge feature branch to main
- Run GitHub Actions CI workflows
- Monitor all workflows for success
- If all pass: Update status to 'complete'
- If any fail: Diagnose and fix errors

Branch: feat/{prp_id}-*
Evidence: redis-cli HGETALL prp:{prp_id}"""

        else:
            tmux_message = f"Unknown agent type: {self.agent_type}"

        self.send_to_tmux(tmux_message)

    def process_json_message(self, message: dict):
        """Process JSON messages from orchestrator loop"""
        msg_type = message.get("type", "unknown")

        if self.agent_type == AgentType.ORCHESTRATOR:
            if msg_type == "pane_crashed":
                pane = message.get("pane", "unknown")
                tmux_message = f"""🚨 PANE CRASH DETECTED: {pane}
                
Action required: Check and restart the {pane} pane/shim if needed.
Timestamp: {message.get('timestamp', 'unknown')}"""

            elif msg_type == "progress_report":
                report = message.get("report", {})
                active_prps = report.get("active_prps", [])
                queues = report.get("queues", {})

                tmux_message = f"""📊 SYSTEM PROGRESS REPORT
                
Active PRPs: {len(active_prps)}
Dev Queue: {queues.get('dev_queue', 0)} (inflight: {queues.get('dev_queue:inflight', 0)})
Validation Queue: {queues.get('validation_queue', 0)} (inflight: {queues.get('validation_queue:inflight', 0)})
Integration Queue: {queues.get('integration_queue', 0)} (inflight: {queues.get('integration_queue:inflight', 0)})

Review active PRPs and assign as needed."""

            elif msg_type == "prp_timeout":
                prp_id = message.get("prp_id", "unknown")
                queue = message.get("queue", "unknown")
                tmux_message = f"""⏱️ PRP TIMEOUT: {prp_id}
                
PRP timed out in {queue} and has been re-queued.
Consider checking the agent handling this PRP."""

            elif msg_type == "shim_health_warning":
                running = message.get("running", 0)
                expected = message.get("expected", 5)
                tmux_message = f"""⚠️ SHIM HEALTH WARNING
                
Only {running}/{expected} enterprise shims are running.
Some agents may not be receiving messages properly."""

            elif msg_type == "system_broadcast":
                broadcast_msg = message.get("message", "No message")
                tmux_message = f"""📢 SYSTEM BROADCAST
                
{broadcast_msg}"""
            else:
                # Unknown message type
                tmux_message = f"Unknown message type: {msg_type}\nMessage: {json.dumps(message, indent=2)}"
        else:
            # Non-orchestrator agents shouldn't receive JSON messages normally
            tmux_message = f"Received unexpected JSON message: {json.dumps(message, indent=2)}"

        self.send_to_tmux(tmux_message)

    def blmove_process(self):
        """Use BLMOVE to reliably process queue items"""
        inflight_queue = f"{self.queue_name}:inflight"

        while self.running:
            try:
                # Use redis-cli BLMOVE via subprocess for compatibility
                cmd = [
                    "redis-cli",
                    "-u",
                    os.environ.get("REDIS_URL", "redis://localhost:6379"),
                    "BLMOVE",
                    self.queue_name,
                    inflight_queue,
                    "RIGHT",
                    "LEFT",
                    "5",
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0 and result.stdout.strip():
                    item = result.stdout.strip()

                    # Check if it's JSON or a simple PRP ID
                    try:
                        # Try to parse as JSON first
                        message = json.loads(item)
                        self.process_json_message(message)
                    except json.JSONDecodeError:
                        # Not JSON, treat as PRP ID
                        self.process_prp_id(item, self.queue_name)

                    # Remove from inflight after successful processing
                    remove_cmd = [
                        "redis-cli",
                        "-u",
                        os.environ.get("REDIS_URL", "redis://localhost:6379"),
                        "LREM",
                        inflight_queue,
                        "1",
                        item,
                    ]
                    subprocess.run(remove_cmd)

                    print(f"Successfully processed: {item}")

            except Exception as e:
                print(f"Error in BLMOVE process: {e}")
                time.sleep(5)  # Wait before retrying

    def run(self):
        """Main run loop"""
        print(f"Starting enterprise shim for {self.agent_type.value}...")
        print(f"Monitoring queue: {self.queue_name}")

        # Send startup notification
        self.send_to_tmux(f"Enterprise shim connected. Monitoring {self.queue_name}...")

        # Start BLMOVE processing
        self.blmove_process()

        print("Enterprise shim shutting down.")


def main():
    parser = argparse.ArgumentParser(description="Enterprise Shim - Redis to Tmux Bridge")
    parser.add_argument(
        "--agent-type", required=True, choices=["orchestrator", "pm", "validator", "integrator"], help="Type of agent"
    )
    parser.add_argument("--session", required=True, help="Tmux session name")
    parser.add_argument("--window", required=True, help="Tmux window name")
    parser.add_argument("--queue", required=True, help="Redis queue name to monitor")
    parser.add_argument("--redis-url", required=True, help="Redis connection URL")

    args = parser.parse_args()

    # Set Redis URL in environment for subprocess calls
    os.environ["REDIS_URL"] = args.redis_url

    agent_type = AgentType(args.agent_type)
    shim = EnterpriseShim(
        agent_type=agent_type, session=args.session, window=args.window, queue_name=args.queue, redis_url=args.redis_url
    )

    try:
        shim.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
