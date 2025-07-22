#!/usr/bin/env python3
"""
Orchestrator Agent - Main system orchestration logic
Handles PRP assignment, agent monitoring, and system coordination
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import messaging integration
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orchestrator_messaging import OrchestratorMessaging


class OrchestratorAgent:
    """Main orchestrator agent for multi-agent system"""

    def __init__(self):
        self.redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        self.session = os.getenv("TMUX_SESSION", "leadstack")
        self.running = True

        # Agent configuration
        self.pm_agents = ["pm-1", "pm-2", "pm-3"]
        self.validator_agent = "validator"
        self.integration_agent = "integrator"

        # Thresholds
        self.idle_threshold = timedelta(minutes=10)
        self.timeout_threshold = timedelta(minutes=30)

        # Initialize messaging
        self.messaging = OrchestratorMessaging(self.session)

    def get_agent_status(self, agent: str) -> Dict:
        """Get current status of an agent"""
        agent_data = self.redis_client.hgetall(f"agent:{agent}")
        if not agent_data:
            return {"status": "unknown", "current_prp": None, "last_update": None}

        return {
            "status": agent_data.get(b"status", b"unknown").decode(),
            "current_prp": agent_data.get(b"current_prp", b"").decode() or None,
            "last_update": agent_data.get(b"last_update", b"").decode() or None,
        }

    def find_available_pm(self) -> Optional[str]:
        """Find an available PM agent"""
        for pm in self.pm_agents:
            status = self.get_agent_status(pm)
            if status["status"] in ["idle", "unknown"] and not status["current_prp"]:
                return pm
        return None

    def get_next_prp_for_assignment(self) -> Optional[str]:
        """Get next validated PRP ready for assignment"""
        # Check dev queue first
        prp_id = self.redis_client.lpop("dev_queue")
        if prp_id:
            return prp_id.decode() if isinstance(prp_id, bytes) else prp_id

        # Otherwise check for validated PRPs in tracking system
        # This would require loading the YAML file or using the PRP state manager
        # For now, we'll rely on the queue system
        return None

    def assign_prp_to_pm(self, prp_id: str, pm_agent: str) -> bool:
        """Assign a PRP to a PM agent"""
        try:
            # Update agent status
            self.redis_client.hset(
                f"agent:{pm_agent}",
                mapping={
                    "current_prp": prp_id,
                    "status": "assigned",
                    "last_update": datetime.utcnow().isoformat(),
                },
            )

            # Update PRP status
            self.redis_client.hset(
                f"prp:{prp_id}",
                mapping={
                    "state": "assigned",
                    "owner": pm_agent,
                    "assigned_at": datetime.utcnow().isoformat(),
                },
            )

            # Send notification message
            message = {
                "type": "prp_assignment",
                "prp_id": prp_id,
                "agent": pm_agent,
                "message": f"Assigned {prp_id}. Please check Redis for PRP details and begin development.",
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Add to dev queue for enterprise shim to deliver
            self.redis_client.lpush("dev_queue", json.dumps(message))

            print(f"✅ Assigned {prp_id} to {pm_agent}")
            return True

        except Exception as e:
            print(f"❌ Failed to assign {prp_id} to {pm_agent}: {e}")
            return False

    def check_agent_health(self) -> Dict[str, bool]:
        """Check health of all agents"""
        health_status = {}

        for agent in self.pm_agents + [self.validator_agent, self.integration_agent]:
            status = self.get_agent_status(agent)

            if status["last_update"]:
                last_update = datetime.fromisoformat(status["last_update"])
                time_since_update = datetime.utcnow() - last_update
                health_status[agent] = time_since_update < self.idle_threshold
            else:
                health_status[agent] = False

        return health_status

    def handle_timeouts(self):
        """Check for timed-out PRPs and reassign"""
        # Check all PM agents for timeouts
        for pm in self.pm_agents:
            status = self.get_agent_status(pm)

            if status["current_prp"] and status["last_update"]:
                last_update = datetime.fromisoformat(status["last_update"])
                time_since_update = datetime.utcnow() - last_update

                if time_since_update > self.timeout_threshold:
                    prp_id = status["current_prp"]
                    print(f"⏱️ Timeout detected for {prp_id} on {pm}")

                    # Reset agent
                    self.redis_client.hset(
                        f"agent:{pm}",
                        mapping={
                            "current_prp": "",
                            "status": "idle",
                            "last_update": datetime.utcnow().isoformat(),
                        },
                    )

                    # Find new PM and reassign
                    new_pm = self.find_available_pm()
                    if new_pm:
                        self.assign_prp_to_pm(prp_id, new_pm)
                    else:
                        # Put back in queue for later
                        self.redis_client.lpush("dev_queue", prp_id)

    def process_orchestrator_messages(self):
        """Process messages from orchestrator queue"""
        # Process up to 10 messages per cycle
        for _ in range(10):
            message = self.redis_client.lpop("orchestrator_queue")
            if not message:
                break

            try:
                data = json.loads(message.decode() if isinstance(message, bytes) else message)
                msg_type = data.get("type")

                if msg_type == "new_prp":
                    # New PRP notification - check if it needs assignment
                    prp_id = data.get("prp_id")
                    print(f"📋 New PRP notification: {prp_id}")

                elif msg_type == "prp_timeout":
                    # Timeout notification from orchestrator loop
                    prp_id = data.get("prp_id")
                    print(f"⏱️ PRP timeout notification: {prp_id}")

                elif msg_type == "progress_report":
                    # Progress report from orchestrator loop
                    report = data.get("report", {})
                    active_count = len(report.get("active_prps", []))
                    print(f"📊 Progress report: {active_count} active PRPs")

                elif msg_type == "shim_health_warning":
                    # Shim health warning
                    running = data.get("running", 0)
                    expected = data.get("expected", 5)
                    print(f"⚠️ Shim health warning: {running}/{expected} running")

                else:
                    print(f"Unknown message type: {msg_type}")

            except Exception as e:
                print(f"Error processing message: {e}")

    def assignment_cycle(self):
        """Main assignment cycle - match PRPs to available PMs"""
        # Find available PMs
        available_pms = []
        for pm in self.pm_agents:
            status = self.get_agent_status(pm)
            if status["status"] in ["idle", "unknown"] and not status["current_prp"]:
                available_pms.append(pm)

        if not available_pms:
            return

        # Assign PRPs to available PMs
        for pm in available_pms:
            prp_id = self.get_next_prp_for_assignment()
            if prp_id:
                self.assign_prp_to_pm(prp_id, pm)
            else:
                break

    def generate_status_report(self) -> str:
        """Generate current system status report"""
        lines = ["📊 ORCHESTRATOR STATUS REPORT", ""]

        # Queue status
        dev_queue_len = self.redis_client.llen("dev_queue")
        val_queue_len = self.redis_client.llen("validation_queue")
        int_queue_len = self.redis_client.llen("integration_queue")

        lines.append("QUEUES:")
        lines.append(f"  Dev Queue: {dev_queue_len}")
        lines.append(f"  Validation Queue: {val_queue_len}")
        lines.append(f"  Integration Queue: {int_queue_len}")
        lines.append("")

        # Agent status
        lines.append("AGENTS:")
        health_status = self.check_agent_health()

        for agent in self.pm_agents + [self.validator_agent, self.integration_agent]:
            status = self.get_agent_status(agent)
            health = "✅" if health_status.get(agent, False) else "❌"
            prp = status["current_prp"] or "none"
            lines.append(f"  {agent}: {health} {status['status']} ({prp})")

        return "\n".join(lines)

    def run_cycle(self):
        """Run one orchestration cycle"""
        # Process incoming messages
        self.process_orchestrator_messages()

        # Check for timeouts and reassign
        self.handle_timeouts()

        # Assign new PRPs to available agents
        self.assignment_cycle()

        # Generate and print status
        if int(time.time()) % 300 == 0:  # Every 5 minutes
            print(self.generate_status_report())

    def run(self):
        """Main orchestrator loop"""
        print("🎯 Starting Orchestrator Agent")
        print(f"Session: {self.session}")
        print(f"Redis: {os.getenv('REDIS_URL', 'redis://localhost:6379/0')}")
        print("Monitoring PM agents:", ", ".join(self.pm_agents))
        print("")

        while self.running:
            try:
                self.run_cycle()
                time.sleep(10)  # Run every 10 seconds

            except KeyboardInterrupt:
                print("\nShutting down orchestrator agent...")
                self.running = False

            except Exception as e:
                print(f"❌ Orchestrator error: {e}")
                time.sleep(5)


def main():
    """Main entry point"""
    agent = OrchestratorAgent()
    agent.run()


if __name__ == "__main__":
    main()
