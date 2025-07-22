#!/usr/bin/env python3
"""
Enterprise Shim v2 - Enhanced Redis to Tmux Bridge with Evidence Monitoring
Monitors tmux output for EVIDENCE_COMPLETE footers and handles atomic promotions
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

import redis


class AgentType(Enum):
    ORCHESTRATOR = "orchestrator"
    PM = "pm"
    VALIDATOR = "validator"
    INTEGRATOR = "integrator"


class EnterpriseShimV2:
    def __init__(self, agent_type: AgentType, session: str, window: str, queue_name: str, redis_url: str):
        self.agent_type = agent_type
        self.session = session
        self.window = window
        self.queue_name = queue_name
        self.redis_client = redis.from_url(redis_url)
        self.running = True
        self.current_prp = None
        self.last_activity = datetime.now()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down...")
        self.running = False

    def send_to_tmux(self, message: str):
        """Send message to the tmux pane"""
        try:
            # Split message into lines
            lines = message.split("\n")
            for line in lines:
                # Escape special characters
                escaped_line = line.replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")
                cmd = ["tmux", "send-keys", "-t", f"{self.session}:{self.window}", f'"{escaped_line}"', "Enter"]
                subprocess.run(cmd, check=False, capture_output=True)
            print(f"Message sent to {self.window}: {message[:100]}...")
        except Exception as e:
            print(f"Error sending to tmux: {e}")

    def capture_tmux_output(self, lines: int = 50) -> str:
        """Capture recent output from tmux pane"""
        try:
            cmd = ["tmux", "capture-pane", "-t", f"{self.session}:{self.window}", "-p", "-S", f"-{lines}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            return ""
        except Exception as e:
            print(f"Error capturing tmux output: {e}")
            return ""

    def check_evidence_complete(self) -> Optional[Dict[str, Any]]:
        """Check tmux output for EVIDENCE_COMPLETE footer"""
        if not self.current_prp:
            return None

        output = self.capture_tmux_output(100)
        lines = output.split("\n")

        # Look for EVIDENCE_COMPLETE footer
        for i, line in enumerate(lines):
            if "EVIDENCE_COMPLETE" in line:
                # Try to parse JSON from following lines
                if i + 1 < len(lines):
                    try:
                        # Collect potential JSON lines
                        json_text = ""
                        for j in range(i + 1, min(i + 10, len(lines))):
                            json_text += lines[j]
                            try:
                                evidence = json.loads(json_text)
                                return evidence
                            except json.JSONDecodeError:
                                continue
                    except Exception as e:
                        print(f"Error parsing evidence JSON: {e}")

        return None

    def promote_prp(self, prp_id: str, from_queue: str, to_queue: str) -> bool:
        """Atomically promote PRP using Lua script"""
        try:
            # Load promote.lua script
            with open("scripts/promote.lua", "r") as f:
                lua_script = f.read()

            promote_script = self.redis_client.register_script(lua_script)
            result = promote_script(keys=[f"{from_queue}:inflight", to_queue, f"prp:{prp_id}"], args=[prp_id])

            if result == b"PROMOTED" or result == "PROMOTED":
                print(f"Successfully promoted {prp_id} to {to_queue}")
                return True
            else:
                print(f"Promotion failed for {prp_id}: {result}")
                return False

        except Exception as e:
            print(f"Error promoting PRP: {e}")
            return False

    def handle_prp_assignment(self, prp_id: str):
        """Handle PRP assignment to agent"""
        self.current_prp = prp_id
        self.last_activity = datetime.now()

        # Get PRP details
        prp_data = self.redis_client.hgetall(f"prp:{prp_id}")
        if not prp_data:
            print(f"Warning: No data found for prp:{prp_id}")
            return

        # Decode bytes to strings
        prp_data = {
            k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v
            for k, v in prp_data.items()
        }

        # Send assignment message based on agent type
        if self.agent_type == AgentType.PM:
            self.send_dev_assignment(prp_id, prp_data)
        elif self.agent_type == AgentType.VALIDATOR:
            self.send_validator_assignment(prp_id, prp_data)
        elif self.agent_type == AgentType.INTEGRATOR:
            self.send_integrator_assignment(prp_id, prp_data)

    def send_dev_assignment(self, prp_id: str, prp_data: Dict[str, str]):
        """Send development assignment to PM agent"""
        title = prp_data.get("title", "No title")
        description = prp_data.get("description", "No description")
        priority = prp_data.get("priority", "medium")

        message = f"""🔥 PRP ASSIGNMENT: {prp_id}

Task: {title}
Priority: {priority}

Development workflow (NO GitHub push):
- redis-cli HSET prp:{prp_id} development_started true
- Follow CLAUDE.md guidelines  
- Run: make quick-check (local validation only)
- Complete with EVIDENCE_COMPLETE footer
- DO NOT push to GitHub - that's integrator's job

Source: redis-cli HGET prp:{prp_id} source_file
Full details: redis-cli HGETALL prp:{prp_id}"""

        self.send_to_tmux(message)

    def send_validator_assignment(self, prp_id: str, prp_data: Dict[str, str]):
        """Send validation assignment"""
        message = f"""🔍 VALIDATION REQUEST: {prp_id}

Review development work and validate:
- Check evidence: redis-cli HGETALL prp:{prp_id}
- Verify tests pass and coverage acceptable
- Set validation_complete=true if approved
- Complete with EVIDENCE_COMPLETE footer

Full details: redis-cli HGETALL prp:{prp_id}"""

        self.send_to_tmux(message)

    def send_integrator_assignment(self, prp_id: str, prp_data: Dict[str, str]):
        """Send integration assignment"""
        message = f"""🚀 INTEGRATION REQUEST: {prp_id}

Deploy validated changes:
- Merge to main branch
- Run CI/CD pipeline
- Verify deployment
- Set integration_complete=true
- Complete with EVIDENCE_COMPLETE footer

Full details: redis-cli HGETALL prp:{prp_id}"""

        self.send_to_tmux(message)

    def monitor_tmux_output(self):
        """Background thread to monitor tmux output"""
        while self.running:
            try:
                # Check for EVIDENCE_COMPLETE
                evidence = self.check_evidence_complete()
                if evidence and self.current_prp:
                    print(f"Found EVIDENCE_COMPLETE for {self.current_prp}")

                    # Determine promotion path
                    if self.agent_type == AgentType.PM:
                        if self.promote_prp(self.current_prp, "dev_queue", "validation_queue"):
                            self.current_prp = None
                    elif self.agent_type == AgentType.VALIDATOR:
                        if self.promote_prp(self.current_prp, "validation_queue", "integration_queue"):
                            self.current_prp = None
                    elif self.agent_type == AgentType.INTEGRATOR:
                        # Mark as complete
                        self.redis_client.hset(f"prp:{self.current_prp}", "status", "complete")
                        self.redis_client.lrem(f"{self.queue_name}:inflight", 0, self.current_prp)
                        self.current_prp = None

                # Check for Q&A questions
                output = self.capture_tmux_output(20)
                if "QUESTION:" in output and self.current_prp:
                    lines = output.split("\n")
                    for line in lines:
                        if "QUESTION:" in line:
                            question = line.split("QUESTION:", 1)[1].strip()
                            self.handle_question(question)
                            break

                # Update activity timestamp
                if self.current_prp:
                    self.last_activity = datetime.now()
                    self.redis_client.hset(
                        f"agent:{self.window}",
                        mapping={
                            "status": "active",
                            "last_activity": self.last_activity.isoformat(),
                            "current_prp": self.current_prp,
                        },
                    )

                time.sleep(5)  # Check every 5 seconds

            except Exception as e:
                print(f"Error in tmux monitor: {e}")
                time.sleep(5)

    def handle_question(self, question: str):
        """Handle Q&A question from agent"""
        question_id = f"QA-{self.window}-{int(time.time())}"

        # Send question to orchestrator
        self.redis_client.lpush(
            "orchestrator_queue",
            json.dumps(
                {
                    "type": "agent_question",
                    "agent": self.window,
                    "question": question,
                    "question_id": question_id,
                    "prp_id": self.current_prp,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
        )

        # Wait for answer (with timeout)
        start_time = time.time()
        while time.time() - start_time < 120:  # 2 minute timeout
            answer = self.redis_client.get(f"answer:{question_id}")
            if answer:
                answer_text = answer.decode() if isinstance(answer, bytes) else answer
                self.send_to_tmux(f"\n📝 ANSWER: {answer_text}\n")
                self.redis_client.delete(f"answer:{question_id}")
                break
            time.sleep(2)

    def watchdog_check(self):
        """Check for stuck PRPs and handle timeouts"""
        while self.running:
            try:
                # Check inflight queue for stuck PRPs
                inflight_key = f"{self.queue_name}:inflight"
                inflight_prps = self.redis_client.lrange(inflight_key, 0, -1)

                for prp_bytes in inflight_prps:
                    prp_id = prp_bytes.decode() if isinstance(prp_bytes, bytes) else prp_bytes

                    # Check how long it's been inflight
                    inflight_since = self.redis_client.hget(f"prp:{prp_id}", "inflight_since")
                    if inflight_since:
                        inflight_time = datetime.fromisoformat(
                            inflight_since.decode() if isinstance(inflight_since, bytes) else inflight_since
                        )
                        if datetime.utcnow() - inflight_time > timedelta(minutes=30):
                            print(f"Watchdog: {prp_id} stuck for >30min, re-queueing")

                            # Re-queue with retry count
                            self.redis_client.lrem(inflight_key, 0, prp_id)
                            self.redis_client.lpush(self.queue_name, prp_id)
                            self.redis_client.hincrby(f"prp:{prp_id}", "retry_count", 1)
                            self.redis_client.hdel(f"prp:{prp_id}", "inflight_since")

                time.sleep(60)  # Check every minute

            except Exception as e:
                print(f"Error in watchdog: {e}")
                time.sleep(60)

    def blmove_process(self):
        """Main BLMOVE processing loop"""
        inflight_key = f"{self.queue_name}:inflight"

        # Start monitoring threads
        monitor_thread = threading.Thread(target=self.monitor_tmux_output, daemon=True)
        monitor_thread.start()

        watchdog_thread = threading.Thread(target=self.watchdog_check, daemon=True)
        watchdog_thread.start()

        while self.running:
            try:
                # BLMOVE with 30 second timeout
                item = self.redis_client.blmove(self.queue_name, inflight_key, 30, "RIGHT", "LEFT")

                if item:
                    prp_id = item.decode() if isinstance(item, bytes) else item
                    print(f"Processing PRP ID: {prp_id} from {self.queue_name}")

                    # Mark when it went inflight
                    self.redis_client.hset(f"prp:{prp_id}", "inflight_since", datetime.utcnow().isoformat())

                    # Handle the assignment
                    self.handle_prp_assignment(prp_id)

            except Exception as e:
                print(f"Error in BLMOVE process: {e}")
                time.sleep(5)

    def run(self):
        """Main run loop"""
        print(f"Starting enterprise shim v2 for {self.agent_type.value}...")
        print(f"Monitoring queue: {self.queue_name}")

        # Send startup notification
        self.send_to_tmux(f"Enterprise shim v2 connected. Monitoring {self.queue_name}...")

        # Start BLMOVE processing
        self.blmove_process()

        print("Enterprise shim v2 shutting down.")


def main():
    parser = argparse.ArgumentParser(description="Enterprise Shim v2 - Enhanced Redis to Tmux Bridge")
    parser.add_argument("--agent-type", required=True, choices=["orchestrator", "pm", "validator", "integrator"])
    parser.add_argument("--session", required=True, help="Tmux session name")
    parser.add_argument("--window", required=True, help="Tmux window name")
    parser.add_argument("--queue", required=True, help="Redis queue name to monitor")
    parser.add_argument("--redis-url", required=True, help="Redis connection URL")

    args = parser.parse_args()

    # Set Redis URL in environment
    os.environ["REDIS_URL"] = args.redis_url

    agent_type = AgentType(args.agent_type)
    shim = EnterpriseShimV2(
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
