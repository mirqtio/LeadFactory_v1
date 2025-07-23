#!/usr/bin/env python3
"""
Main Orchestrator - Manages all agents and coordinates the system
"""
import argparse
import json
import logging
import signal
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

import redis
from roles.integration_agent import IntegrationAgent
from roles.pm_agent import PMAgent
from roles.validator_agent import ValidatorAgent

from core.qa_orchestrator import QAOrchestrator


class MainOrchestrator:
    """Main orchestrator that manages all agents"""

    def __init__(self, pm_count: int = 3):
        self.redis_client = redis.from_url("redis://localhost:6379/0")

        # Setup logging
        self.logger = logging.getLogger("orchestrator")
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Initialize agents
        self.pm_agents = [PMAgent(f"pm-{i+1}") for i in range(pm_count)]
        self.validator = ValidatorAgent("validator-1")
        self.integrator = IntegrationAgent("integrator-1")
        self.qa_orchestrator = QAOrchestrator()

        # Thread pool for running agents
        self.executor = ThreadPoolExecutor(max_workers=pm_count + 3)
        self.agent_futures: Dict[str, Future] = {}

        # Shutdown handling
        self.running = True
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def start(self):
        """Start all agents"""
        self.logger.info("Starting LeadFactory Agent System")

        # Start PM agents
        for agent in self.pm_agents:
            future = self.executor.submit(agent.run)
            self.agent_futures[agent.agent_id] = future
            self.logger.info(f"Started {agent.agent_id}")

        # Start validator
        future = self.executor.submit(self.validator.run)
        self.agent_futures[self.validator.agent_id] = future
        self.logger.info(f"Started {self.validator.agent_id}")

        # Start integrator
        future = self.executor.submit(self.integrator.run)
        self.agent_futures[self.integrator.agent_id] = future
        self.logger.info(f"Started {self.integrator.agent_id}")

        # Start Q&A orchestrator
        future = self.executor.submit(self.qa_orchestrator.run)
        self.agent_futures["qa_orchestrator"] = future
        self.logger.info("Started Q&A Orchestrator")

        # Run monitoring loop
        self.monitor_loop()

    def monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                # Check agent health
                self.check_agent_health()

                # Monitor queues
                self.monitor_queues()

                # Check for stuck PRPs
                self.check_stuck_prps()

                # Generate metrics
                self.update_metrics()

                # Sleep before next check
                time.sleep(10)

            except Exception as e:
                self.logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(5)

        # Shutdown
        self.shutdown()

    def check_agent_health(self):
        """Check if all agents are healthy"""
        current_time = datetime.utcnow()

        # Check each agent future
        for agent_id, future in self.agent_futures.items():
            if future.done():
                # Agent crashed
                exception = future.exception()
                if exception:
                    self.logger.error(f"Agent {agent_id} crashed: {exception}")
                else:
                    self.logger.warning(f"Agent {agent_id} exited unexpectedly")

                # Restart agent
                self.restart_agent(agent_id)

        # Check agent activity in Redis
        for agent_id in self.agent_futures.keys():
            if agent_id == "qa_orchestrator":
                continue

            agent_data = self.redis_client.hgetall(f"agent:{agent_id}")
            if agent_data:
                last_activity = agent_data.get(b"last_activity", b"").decode()
                if last_activity:
                    try:
                        last_time = datetime.fromisoformat(last_activity)
                        if (current_time - last_time).total_seconds() > 300:  # 5 minutes
                            self.logger.warning(f"Agent {agent_id} inactive for >5 minutes")
                    except:
                        pass

    def restart_agent(self, agent_id: str):
        """Restart a crashed agent"""
        self.logger.info(f"Restarting agent {agent_id}")

        # Remove old future
        self.agent_futures.pop(agent_id, None)

        # Create and start new agent
        if agent_id.startswith("pm-"):
            agent = PMAgent(agent_id)
        elif agent_id.startswith("validator"):
            agent = ValidatorAgent(agent_id)
        elif agent_id.startswith("integrator"):
            agent = IntegrationAgent(agent_id)
        elif agent_id == "qa_orchestrator":
            agent = self.qa_orchestrator
        else:
            self.logger.error(f"Unknown agent type: {agent_id}")
            return

        future = self.executor.submit(agent.run)
        self.agent_futures[agent_id] = future
        self.logger.info(f"Restarted {agent_id}")

    def monitor_queues(self):
        """Monitor queue depths and log status"""
        queues = ["dev_queue", "validation_queue", "integration_queue", "qa_queue"]

        status = []
        for queue in queues:
            pending = self.redis_client.llen(queue)
            inflight = self.redis_client.llen(f"{queue}:inflight")
            status.append(f"{queue}: {pending} pending, {inflight} inflight")

        self.logger.info(f"Queue status: {' | '.join(status)}")

        # Check for queue backup
        dev_pending = self.redis_client.llen("dev_queue")
        if dev_pending > 20:
            self.logger.warning(f"Dev queue backing up: {dev_pending} PRPs pending")

    def check_stuck_prps(self):
        """Check for PRPs stuck in inflight queues"""
        queues = ["dev_queue", "validation_queue", "integration_queue"]

        for queue in queues:
            inflight_key = f"{queue}:inflight"
            inflight_prps = self.redis_client.lrange(inflight_key, 0, -1)

            for prp_bytes in inflight_prps:
                prp_id = prp_bytes.decode() if isinstance(prp_bytes, bytes) else prp_bytes

                # Check how long it's been inflight
                inflight_since = self.redis_client.hget(f"prp:{prp_id}", "inflight_since")
                if inflight_since:
                    try:
                        inflight_time = datetime.fromisoformat(
                            inflight_since.decode() if isinstance(inflight_since, bytes) else inflight_since
                        )
                        if (datetime.utcnow() - inflight_time).total_seconds() > 1800:  # 30 minutes
                            self.logger.warning(f"PRP {prp_id} stuck in {queue} for >30 minutes")
                    except:
                        pass

    def update_metrics(self):
        """Update system metrics"""
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "queues": {},
            "agents": {},
            "prps": {"total": len(self.redis_client.keys("prp:*")), "complete": 0, "failed": 0},
        }

        # Queue metrics
        for queue in ["dev_queue", "validation_queue", "integration_queue"]:
            metrics["queues"][queue] = {
                "pending": self.redis_client.llen(queue),
                "inflight": self.redis_client.llen(f"{queue}:inflight"),
            }

        # Agent metrics
        for agent_id in self.agent_futures.keys():
            if agent_id == "qa_orchestrator":
                continue
            agent_data = self.redis_client.hgetall(f"agent:{agent_id}")
            if agent_data:
                metrics["agents"][agent_id] = {
                    "status": agent_data.get(b"status", b"unknown").decode(),
                    "current_prp": agent_data.get(b"current_prp", b"").decode(),
                }

        # PRP completion metrics
        prp_keys = self.redis_client.keys("prp:*")
        for key in prp_keys:
            if key.decode().endswith(":history:pm"):
                continue
            state = self.redis_client.hget(key, "state")
            if state:
                state = state.decode() if isinstance(state, bytes) else state
                if state == "complete":
                    metrics["prps"]["complete"] += 1
                elif state == "failed":
                    metrics["prps"]["failed"] += 1

        # Store metrics
        self.redis_client.setex("metrics:latest", 300, json.dumps(metrics))

        # Log summary
        self.logger.info(
            f"System metrics: "
            f"PRPs total={metrics['prps']['total']}, "
            f"complete={metrics['prps']['complete']}, "
            f"failed={metrics['prps']['failed']}"
        )

    def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down orchestrator...")

        # Cancel all agent futures
        for agent_id, future in self.agent_futures.items():
            if not future.done():
                future.cancel()
                self.logger.info(f"Cancelled {agent_id}")

        # Shutdown executor
        self.executor.shutdown(wait=True, timeout=30)

        self.logger.info("Orchestrator shutdown complete")


def main():
    parser = argparse.ArgumentParser(description="LeadFactory Agent Orchestrator")
    parser.add_argument("--pm-agents", type=int, default=3, help="Number of PM agents")
    parser.add_argument("--reset", action="store_true", help="Reset all queues before starting")

    args = parser.parse_args()

    if args.reset:
        # Clear all queues
        r = redis.from_url("redis://localhost:6379/0")
        for queue in ["dev_queue", "validation_queue", "integration_queue", "qa_queue"]:
            r.delete(queue)
            r.delete(f"{queue}:inflight")
        print("Queues reset")

    # Start orchestrator
    orchestrator = MainOrchestrator(pm_count=args.pm_agents)
    orchestrator.start()


if __name__ == "__main__":
    main()
