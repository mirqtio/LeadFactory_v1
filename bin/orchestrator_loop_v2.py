#!/usr/bin/env python3
"""
Enhanced Orchestrator Loop with Q&A handling, heartbeat monitoring, and auto-scaling
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import redis

# Ensure stdout is unbuffered for real-time logging
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__


class OrchestratorLoopV2:
    def __init__(self, session: str = "leadstack"):
        self.session = session
        self.redis_client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379"))
        self.running = True

        # Track agent states
        self.agent_states = {}

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\nReceived signal {signum}, shutting down orchestrator loop...")
        self.running = False

    def send_notification(self, window: str, message: str):
        """Send notification to orchestrator agent via notifier system"""
        notification = {
            "id": f"notif-{int(time.time() * 1000)}",
            "type": "system_notification",
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "orchestrator_loop",
        }
        # Add to pending notifications for notifier to deliver
        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

    def process_orchestrator_queue(self):
        """Process messages in orchestrator queue"""
        processed = 0
        print("🔍 Checking orchestrator queue...")

        while True:
            # Non-blocking pop from orchestrator queue (LPUSH/RPOP = FIFO)
            message = self.redis_client.rpop("orchestrator_queue")
            if not message:
                break
            processed += 1

            try:
                data = json.loads(message.decode() if isinstance(message, bytes) else message)
                msg_type = data.get("type")

                print(f"📨 Processing message type: {msg_type}")
                print(f"   Data: {json.dumps(data, indent=2)}")

                if msg_type == "agent_question":
                    print("🔄 Handling agent question...")
                    self.handle_agent_question(data)
                elif msg_type == "heartbeat_check":
                    print("🔄 Checking agent heartbeats...")
                    self.check_agent_heartbeats()
                    # Confirm processing
                    self.redis_client.set("orchestrator:last_heartbeat_check", datetime.utcnow().isoformat())
                elif msg_type == "check_queue_depth":
                    self.check_queue_scaling()
                elif msg_type == "deployment_failed":
                    self.handle_deployment_failure(data)
                elif msg_type == "check_shim_health":
                    self.check_shim_health()
                elif msg_type == "new_prp":
                    self.handle_new_prp(data)
                elif msg_type == "bulk_prps_queued":
                    self.handle_bulk_prps(data)
                else:
                    print(f"⚠️  Unknown message type: {msg_type}")

            except Exception as e:
                print(f"Error processing orchestrator queue message: {e}")
                import traceback

                traceback.print_exc()

        if processed > 0:
            print(f"📬 Processed {processed} orchestrator messages")
        else:
            print("📭 No messages in orchestrator queue")

    def handle_agent_question(self, data: Dict):
        """Handle Q&A from agents"""
        agent = data.get("agent")
        question = data.get("question")
        question_id = data.get("question_id")
        prp_id = data.get("prp_id")

        print(f"📝 Q&A Request from {agent}: {question}")

        # Generate answer based on question context
        answer = self.generate_answer(question, prp_id)

        # Store answer for agent to retrieve
        self.redis_client.setex(f"answer:{question_id}", 300, answer)  # 5 min TTL

        # Confirm Q&A processing
        self.redis_client.set(
            "orchestrator:last_qa_processed",
            json.dumps({"question_id": question_id, "timestamp": datetime.utcnow().isoformat()}),
        )

        # Notify orchestrator agent
        self.send_notification("orchestrator", f"Q&A: {agent} asked: {question}\nAnswer: {answer}")

    def generate_answer(self, question: str, prp_id: str) -> str:
        """Generate answer for agent question"""
        # Simple pattern matching for common questions
        question_lower = question.lower()

        if "import path" in question_lower and "validation" in question_lower:
            return "Use 'from validators import validate_prp' for the validation module"
        elif "branch" in question_lower:
            return f"Use branch name: feat/{prp_id.lower()}-implementation"
        elif "test" in question_lower and "command" in question_lower:
            return "Run tests with: make quick-check"
        elif "deploy" in question_lower:
            return "Deployment is handled by the integrator agent only"
        else:
            return "Please check CLAUDE.md for guidelines or ask a more specific question"

    def check_agent_heartbeats(self):
        """Check agent heartbeats and mark down if inactive >30min"""
        print("💓 Checking agent heartbeats...")

        agents = ["dev-1", "dev-2", "validator", "integrator"]
        current_time = datetime.utcnow()

        for agent in agents:
            agent_data = self.redis_client.hgetall(f"agent:{agent}")
            if agent_data:
                last_activity = agent_data.get(b"last_activity")
                if last_activity:
                    last_time = datetime.fromisoformat(last_activity.decode())
                    if current_time - last_time > timedelta(minutes=30):
                        print(f"🚨 Agent {agent} is DOWN - no activity for >30min")
                        self.redis_client.hset(f"agent:{agent}", "status", "agent_down")

                        # Send alert
                        self.send_notification(
                            "orchestrator", f"🚨 AGENT DOWN: {agent} - Last activity: {last_time.isoformat()}"
                        )

                        # Check if agent has PRP inflight
                        current_prp = agent_data.get(b"current_prp")
                        if current_prp:
                            self.handle_stuck_prp(current_prp.decode(), agent)

    def handle_stuck_prp(self, prp_id: str, agent: str):
        """Handle PRP stuck with down agent"""
        print(f"🔄 Re-queueing stuck PRP {prp_id} from down agent {agent}")

        # Determine queue based on agent type
        if "dev" in agent:
            queue = "dev_queue"
        elif "validator" in agent:
            queue = "validation_queue"
        elif "integrator" in agent:
            queue = "integration_queue"
        else:
            return

        # Move from inflight back to queue
        self.redis_client.lrem(f"{queue}:inflight", 0, prp_id)
        self.redis_client.lpush(queue, prp_id)
        self.redis_client.hincrby(f"prp:{prp_id}", "retry_count", 1)

    def check_queue_scaling(self):
        """Check queue depth and trigger scaling if needed"""
        queue_depth = self.redis_client.llen("dev_queue")

        print(f"📊 Queue depth check: {queue_depth} PRPs in dev_queue")

        if queue_depth > 20:
            # Check if dev-3 already exists
            windows = self.get_tmux_windows()
            if "dev-3" not in windows:
                print(f"🚀 High queue depth ({queue_depth}), spawning dev-3")
                self.spawn_additional_dev()
                self.send_notification(
                    "orchestrator", f"🚀 AUTO-SCALING: Spawned dev-3 due to queue depth {queue_depth}"
                )

    def spawn_additional_dev(self):
        """Spawn additional dev agent"""
        try:
            # Create new tmux window
            subprocess.run(
                [
                    "tmux",
                    "new-window",
                    "-t",
                    f"{self.session}",
                    "-n",
                    "dev-3",
                    "echo 'Dev-3 agent ready for assignments'",
                ],
                check=True,
            )

            # Start enterprise shim for dev-3
            subprocess.Popen(
                [
                    "python3",
                    "bin/enterprise_shim_v2.py",
                    "--agent-type=pm",
                    f"--session={self.session}",
                    "--window=dev-3",
                    "--queue=dev_queue",
                    "--redis-url=redis://localhost:6379/0",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            print("✅ Successfully spawned dev-3")

        except Exception as e:
            print(f"❌ Error spawning dev-3: {e}")

    def handle_deployment_failure(self, data: Dict):
        """Handle deployment failure and trigger rollback"""
        prp_id = data.get("prp_id")
        error = data.get("error")

        print(f"🚨 Deployment failed for {prp_id}: {error}")

        # Pause integration queue
        self.redis_client.set("integration_queue:paused", "true")

        # Mark rollback initiated
        self.redis_client.set(
            f"rollback:{prp_id}", json.dumps({"initiated_at": datetime.utcnow().isoformat(), "reason": error})
        )

        # Send notification
        self.send_notification(
            "orchestrator",
            f"🚨 DEPLOYMENT FAILED: {prp_id}\nError: {error}\nIntegration queue paused, rollback initiated",
        )

    def handle_new_prp(self, data: Dict):
        """Handle new PRP notification"""
        prp_id = data.get("prp_id")
        notification = {
            "id": f"notif-{int(time.time() * 1000)}",
            "type": "new_prp",
            "prp_id": prp_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

    def handle_bulk_prps(self, data: Dict):
        """Handle bulk PRPs notification"""
        prp_ids = data.get("prp_ids", [])
        queue = data.get("queue")
        notification = {
            "id": f"notif-{int(time.time() * 1000)}",
            "type": "bulk_prps_queued",
            "prp_ids": prp_ids,
            "queue": queue,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.redis_client.lpush("orchestrator:pending_notifications", json.dumps(notification))

    def get_tmux_windows(self) -> List[str]:
        """Get list of tmux windows"""
        try:
            result = subprocess.run(
                ["tmux", "list-windows", "-t", self.session, "-F", "#{window_name}"], capture_output=True, text=True
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")
        except Exception:
            pass
        return []

    def ensure_panes_alive(self, required_panes: List[str]):
        """Ensure required panes exist"""
        try:
            windows = self.get_tmux_windows()

            for pane in required_panes:
                if pane not in windows:
                    print(f"❌ Missing pane: {pane}, creating...")
                    subprocess.run(
                        ["tmux", "new-window", "-t", self.session, "-n", pane, f"echo '{pane} agent ready'"],
                        check=False,
                    )

        except Exception as e:
            print(f"Error checking panes: {e}")

    def check_shim_health(self):
        """Check and restart dead shims"""
        shim_configs = [
            # Remove orchestrator shim - it shouldn't monitor its own queue
            # {"agent_type": "orchestrator", "window": "orchestrator", "queue": "orchestrator_queue"},
            {"agent_type": "pm", "window": "dev-1", "queue": "dev_queue"},
            {"agent_type": "pm", "window": "dev-2", "queue": "dev_queue"},
            {"agent_type": "validator", "window": "validator", "queue": "validation_queue"},
            {"agent_type": "integrator", "window": "integrator", "queue": "integration_queue"},
        ]

        for config in shim_configs:
            # Check if shim is running
            result = subprocess.run(["pgrep", "-f", f"enterprise_shim.*{config['window']}"], capture_output=True)

            if result.returncode != 0:
                print(f"🔧 Restarting dead shim for {config['window']}")
                subprocess.Popen(
                    [
                        "python3",
                        "bin/enterprise_shim_v2.py",
                        f"--agent-type={config['agent_type']}",
                        f"--session={self.session}",
                        f"--window={config['window']}",
                        f"--queue={config['queue']}",
                        "--redis-url=redis://localhost:6379/0",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    def check_feature_flags(self):
        """Check and apply feature flag configurations"""
        strict_mode = self.redis_client.get("config:QUALITY_GATE_STRICT_MODE")
        if strict_mode:
            mode = strict_mode.decode() if isinstance(strict_mode, bytes) else strict_mode
            print(f"⚙️  Quality Gate Strict Mode: {mode}")

    def generate_progress_report(self):
        """Generate and send progress report"""
        try:
            # Get queue depths
            queues = {
                "dev_queue": self.redis_client.llen("dev_queue"),
                "validation_queue": self.redis_client.llen("validation_queue"),
                "integration_queue": self.redis_client.llen("integration_queue"),
                "dev_queue:inflight": self.redis_client.llen("dev_queue:inflight"),
                "validation_queue:inflight": self.redis_client.llen("validation_queue:inflight"),
                "integration_queue:inflight": self.redis_client.llen("integration_queue:inflight"),
            }

            # Get active PRPs
            active_prps = []
            all_prp_keys = self.redis_client.keys("prp:*")
            for key in all_prp_keys[:10]:  # Limit to first 10
                prp_data = self.redis_client.hgetall(key)
                if prp_data:
                    prp_id = key.decode().split(":")[-1]
                    status = prp_data.get(b"status", b"unknown").decode()
                    if status != "complete":
                        active_prps.append(
                            {"id": prp_id, "status": status, "title": prp_data.get(b"title", b"").decode()[:50]}
                        )

            report = {
                "type": "progress_report",
                "report": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "queues": queues,
                    "active_prps": active_prps,
                    "total_active": len(active_prps),
                },
            }

            # Send to orchestrator
            self.redis_client.lpush("orchestrator_queue", json.dumps(report))

            print(f"📊 Progress Report Generated - Active PRPs: {len(active_prps)}")

        except Exception as e:
            print(f"Error generating progress report: {e}")

    def drain_timeouts(self):
        """Check and re-queue timed out PRPs"""
        timeout_threshold = timedelta(minutes=30)
        current_time = datetime.utcnow()

        for queue in ["dev_queue", "validation_queue", "integration_queue"]:
            inflight_key = f"{queue}:inflight"
            inflight_items = self.redis_client.lrange(inflight_key, 0, -1)

            for item in inflight_items:
                prp_id = item.decode() if isinstance(item, bytes) else item
                inflight_since = self.redis_client.hget(f"prp:{prp_id}", "inflight_since")

                if inflight_since:
                    inflight_time = datetime.fromisoformat(
                        inflight_since.decode() if isinstance(inflight_since, bytes) else inflight_since
                    )
                    if current_time - inflight_time > timeout_threshold:
                        print(f"⏱️  Timeout: {prp_id} in {queue} for >30min, re-queueing")

                        # Re-queue
                        self.redis_client.lrem(inflight_key, 0, prp_id)
                        self.redis_client.lpush(queue, prp_id)
                        self.redis_client.hincrby(f"prp:{prp_id}", "retry_count", 1)
                        self.redis_client.hdel(f"prp:{prp_id}", "inflight_since")

    def run(self):
        """Main orchestrator loop"""
        print("🎯 Starting Enhanced Orchestrator Loop v2")
        print(f"Session: {self.session}")
        print(f"Redis: {os.environ.get('REDIS_URL', 'redis://localhost:6379')}")

        # Initial setup
        self.ensure_panes_alive(["orchestrator", "dev-1", "dev-2", "validator", "integrator"])
        self.generate_progress_report()

        last_report = time.time()
        last_heartbeat = time.time()
        last_queue_check = time.time()

        while self.running:
            try:
                # Process orchestrator queue messages
                self.process_orchestrator_queue()

                # Every minute
                self.ensure_panes_alive(["dev-1", "dev-2", "validator", "integrator"])
                self.drain_timeouts()
                self.check_shim_health()
                self.check_feature_flags()

                # Every 5 minutes - check queue depth
                if time.time() - last_queue_check > 300:
                    self.check_queue_scaling()
                    last_queue_check = time.time()

                # Every 10 minutes - heartbeat
                if time.time() - last_heartbeat > 600:
                    self.check_agent_heartbeats()
                    last_heartbeat = time.time()

                # Every 30 minutes - progress report
                if time.time() - last_report > 1800:
                    self.generate_progress_report()
                    last_report = time.time()

                # Sleep for 1 second for faster message processing
                time.sleep(1)

            except Exception as e:
                print(f"Error in orchestrator loop: {e}")
                import traceback

                traceback.print_exc()
                time.sleep(30)

        print("🛑 Orchestrator loop stopped")


def main():
    # Set up environment
    os.environ["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Create and run orchestrator loop
    orchestrator = OrchestratorLoopV2()

    try:
        orchestrator.run()
    except KeyboardInterrupt:
        print("\nShutting down orchestrator loop...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
