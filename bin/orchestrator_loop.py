#!/usr/bin/env python3
"""
Orchestrator Loop - External monitoring and coordination
Based on Tmux-Orchestrator pattern
"""
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta

import redis


class OrchestratorLoop:
    def __init__(self, redis_url: str, session: str = "leadstack"):
        self.redis_client = redis.from_url(redis_url)
        self.session = session
        self.running = True
        self.last_heartbeat = {}
        self.timeout_threshold = timedelta(minutes=30)

        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}, shutting down orchestrator loop...")
        self.running = False

    def ensure_panes_alive(self, panes: list):
        """Check if tmux panes are alive and restart if needed"""
        try:
            # List all windows in the session to check if they exist
            result = subprocess.run(
                ["tmux", "list-windows", "-t", self.session, "-F", "#{window_name}"],
                capture_output=True,
                text=True,
                check=True,
            )
            active_windows = set(result.stdout.strip().split("\n"))

            for window in panes:
                if window not in active_windows:
                    print(f"⚠️  Window {window} is missing! Notifying orchestrator...")
                    self.redis_client.lpush(
                        "orchestrator_queue",
                        json.dumps(
                            {"type": "pane_crashed", "pane": window, "timestamp": datetime.utcnow().isoformat()}
                        ),
                    )
        except subprocess.CalledProcessError:
            print(f"❌ Session {self.session} not found!")

    def drain_timeouts(self):
        """Check for timed-out PRPs and re-queue them"""
        # Check all inflight queues
        for queue in ["dev_queue", "validation_queue", "integration_queue"]:
            inflight_queue = f"{queue}:inflight"

            # Get all items in inflight queue
            inflight_items = self.redis_client.lrange(inflight_queue, 0, -1)

            for item in inflight_items:
                prp_id = item.decode() if isinstance(item, bytes) else item
                prp_key = f"prp:{prp_id}"

                # Check last activity timestamp
                last_activity = self.redis_client.hget(prp_key, "last_activity")
                if last_activity:
                    last_time = datetime.fromisoformat(last_activity.decode())
                    if datetime.utcnow() - last_time > self.timeout_threshold:
                        print(f"⏱️  Timeout detected for {prp_id} in {inflight_queue}")

                        # Remove from inflight and re-queue
                        self.redis_client.lrem(inflight_queue, 1, prp_id)
                        self.redis_client.lpush(queue, prp_id)

                        # Notify orchestrator
                        self.redis_client.lpush(
                            "orchestrator_queue",
                            json.dumps(
                                {
                                    "type": "prp_timeout",
                                    "prp_id": prp_id,
                                    "queue": queue,
                                    "timestamp": datetime.utcnow().isoformat(),
                                }
                            ),
                        )

    def generate_progress_report(self):
        """Generate system progress report"""
        report = {"timestamp": datetime.utcnow().isoformat(), "queues": {}, "agents": {}, "active_prps": []}

        # Queue depths
        for queue in ["dev_queue", "validation_queue", "integration_queue", "orchestrator_queue"]:
            report["queues"][queue] = self.redis_client.llen(queue)
            report["queues"][f"{queue}:inflight"] = self.redis_client.llen(f"{queue}:inflight")

        # Agent status
        for agent in ["pm-1", "pm-2", "validator", "integrator"]:
            agent_data = self.redis_client.hgetall(f"agent:{agent}")
            if agent_data:
                report["agents"][agent] = {k.decode(): v.decode() for k, v in agent_data.items()}

        # Active PRPs
        prp_keys = self.redis_client.keys("prp:*")
        for key in prp_keys[:10]:  # Limit to 10 for brevity
            prp_data = self.redis_client.hgetall(key)
            if prp_data:
                status = prp_data.get(b"status", b"unknown").decode()
                if status not in ["complete", "failed"]:
                    report["active_prps"].append(
                        {
                            "id": key.decode().replace("prp:", ""),
                            "status": status,
                            "title": prp_data.get(b"title", b"").decode(),
                        }
                    )

        # Send to orchestrator
        self.redis_client.lpush("orchestrator_queue", json.dumps({"type": "progress_report", "report": report}))

        print(f"📊 Progress report generated: {len(report['active_prps'])} active PRPs")

    def check_shim_health(self):
        """Verify enterprise shims are running and restart if needed"""
        try:
            # Define expected shims
            expected_shims = [
                {"agent_type": "orchestrator", "window": "orchestrator", "queue": "orchestrator_queue"},
                {"agent_type": "pm", "window": "dev-1", "queue": "dev_queue"},
                {"agent_type": "pm", "window": "dev-2", "queue": "dev_queue"},
                {"agent_type": "validator", "window": "validator", "queue": "validation_queue"},
                {"agent_type": "integrator", "window": "integrator", "queue": "integration_queue"},
            ]

            # Check which shims are running
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            running_shims = []
            restarted_shims = []

            for shim in expected_shims:
                if f"--window={shim['window']}" in result.stdout:
                    running_shims.append(shim["window"])
                else:
                    # Restart missing shim
                    print(f"🔧 Restarting missing shim for {shim['window']}")

                    log_file = f"/tmp/enterprise_shim_{shim['agent_type']}_{shim['window']}.log"
                    cmd = [
                        "python3",
                        "bin/enterprise_shim.py",
                        f"--agent-type={shim['agent_type']}",
                        f"--session={self.session}",
                        f"--window={shim['window']}",
                        f"--queue={shim['queue']}",
                        f"--redis-url={os.environ.get('REDIS_URL', 'redis://localhost:6379/0')}",
                    ]

                    with open(log_file, "a") as log:
                        subprocess.Popen(cmd, stdout=log, stderr=log)

                    restarted_shims.append(shim["window"])
                    print(f"✅ Restarted {shim['window']} shim")

            shim_count = len(running_shims)
            if shim_count < 5:
                print(f"⚠️  Only {shim_count}/5 shims were running, restarted {len(restarted_shims)}")
                self.redis_client.lpush(
                    "orchestrator_queue",
                    json.dumps(
                        {
                            "type": "shim_health_warning",
                            "running": shim_count,
                            "expected": 5,
                            "restarted": restarted_shims,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                )
        except Exception as e:
            print(f"Error checking shim health: {e}")

    def heartbeat(self):
        """Send heartbeat and check agent health"""
        timestamp = datetime.utcnow().isoformat()

        # Update orchestrator heartbeat
        self.redis_client.hset(
            "orchestrator:status", mapping={"heartbeat": timestamp, "loop_status": "running", "pid": str(os.getpid())}
        )

        # Check each agent's last update
        for agent in ["pm-1", "pm-2", "validator", "integrator"]:
            last_update = self.redis_client.hget(f"agent:{agent}", "last_update")
            if last_update:
                last_time = datetime.fromisoformat(last_update.decode())
                if datetime.utcnow() - last_time > timedelta(minutes=10):
                    print(f"⚠️  Agent {agent} hasn't updated in >10 minutes")

        print(f"💓 Heartbeat sent at {timestamp}")

    def run(self):
        """Main orchestrator loop"""
        print("🎯 Starting Orchestrator Loop")
        print(f"Session: {self.session}")
        print(f"Redis: {os.environ.get('REDIS_URL', 'redis://localhost:6379')}")

        # Initial setup
        self.ensure_panes_alive(["orchestrator", "dev-1", "dev-2", "validator", "integrator"])
        self.generate_progress_report()

        last_report = time.time()
        last_heartbeat = time.time()

        while self.running:
            try:
                # Every minute
                self.ensure_panes_alive(["dev-1", "dev-2", "validator", "integrator"])
                self.drain_timeouts()
                self.check_shim_health()

                # Every 10 minutes - heartbeat
                if time.time() - last_heartbeat > 600:
                    self.heartbeat()
                    last_heartbeat = time.time()

                # Every 30 minutes - progress report
                if time.time() - last_report > 1800:
                    self.generate_progress_report()
                    last_report = time.time()

                # Check for empty dev queue
                if self.redis_client.llen("dev_queue") == 0:
                    idle_devs = []
                    for agent in ["pm-1", "pm-2"]:
                        status = self.redis_client.hget(f"agent:{agent}", "status")
                        if status and status.decode() == "idle":
                            idle_devs.append(agent)

                    if idle_devs:
                        print(f"📭 Dev queue empty, {len(idle_devs)} idle devs")

                # Sleep for 60 seconds
                time.sleep(60)

            except Exception as e:
                print(f"❌ Loop error: {e}")
                time.sleep(5)  # Brief pause before retrying

        print("Orchestrator loop shutting down")


def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
    session = os.environ.get("TMUX_SESSION", "leadstack")

    loop = OrchestratorLoop(redis_url, session)

    try:
        loop.run()
    except KeyboardInterrupt:
        print("\nShutting down orchestrator loop...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
