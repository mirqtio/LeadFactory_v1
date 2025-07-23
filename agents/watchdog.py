#!/usr/bin/env python3
"""
Watchdog for stuck jobs - moves timed out jobs back to queue
"""
import logging
import time
from datetime import datetime

import redis

from agents.core.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("watchdog")


class Watchdog:
    def __init__(self, timeout_seconds=1800):  # 30 minutes default
        self.redis_client = redis.from_url(config.redis_url)
        self.timeout = timeout_seconds
        self.queues = ["pm_queue", "dev_queue", "validator_queue", "validation_queue", "integration_queue"]

    def check_stuck_jobs(self):
        """Check all inflight queues for stuck jobs"""
        current_time = time.time()
        recovered = 0

        for queue in self.queues:
            inflight_key = f"{queue}:inflight"
            items = self.redis_client.lrange(inflight_key, 0, -1)

            for item in items:
                prp_id = item.decode() if isinstance(item, bytes) else item
                prp_key = f"prp:{prp_id}"

                # Check when it started processing
                started_at = self.redis_client.hget(prp_key, "started_at")
                if not started_at:
                    continue

                started_at = float(started_at)
                age = current_time - started_at

                if age > self.timeout:
                    logger.warning(f"Found stuck job {prp_id} in {inflight_key}, age: {age:.0f}s")

                    # Move back to source queue
                    self.redis_client.lrem(inflight_key, 0, prp_id)
                    self.redis_client.lpush(queue, prp_id)

                    # Update retry count and clear processing info
                    self.redis_client.hincrby(prp_key, "retry_count", 1)
                    self.redis_client.hdel(prp_key, "started_at", "processing_by")
                    self.redis_client.hset(
                        prp_key,
                        mapping={
                            "last_retry_at": datetime.utcnow().isoformat(),
                            "last_retry_reason": f"Timeout after {age:.0f}s",
                        },
                    )

                    recovered += 1
                    logger.info(f"Recovered {prp_id} back to {queue}")

        return recovered

    def check_failed_agents(self):
        """Check for agents that haven't reported status recently"""
        current_time = time.time()
        stale_threshold = 300  # 5 minutes

        # Check all known agents
        agent_keys = self.redis_client.keys("agent:*")
        for key in agent_keys:
            agent_data = self.redis_client.hgetall(key)
            if not agent_data:
                continue

            last_activity = agent_data.get(b"last_activity", b"").decode()
            if not last_activity:
                continue

            # Parse ISO timestamp
            try:
                last_time = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
                age = current_time - last_time.timestamp()

                if age > stale_threshold:
                    agent_id = key.decode().split(":")[-1]
                    logger.warning(f"Agent {agent_id} hasn't reported in {age:.0f}s")

            except Exception as e:
                logger.error(f"Error checking agent {key}: {e}")

    def run_forever(self, check_interval=60):
        """Run watchdog checks forever"""
        logger.info(f"Starting watchdog with {self.timeout}s timeout, checking every {check_interval}s")

        while True:
            try:
                # Check for stuck jobs
                recovered = self.check_stuck_jobs()
                if recovered > 0:
                    logger.info(f"Recovered {recovered} stuck jobs")

                # Check for failed agents
                self.check_failed_agents()

                # Also clean up old conversation histories (>24 hours)
                self.cleanup_old_histories()

            except Exception as e:
                logger.error(f"Watchdog error: {e}", exc_info=True)

            time.sleep(check_interval)

    def cleanup_old_histories(self, max_age_hours=24):
        """Clean up old conversation histories to save memory"""
        cutoff_time = time.time() - (max_age_hours * 3600)

        # Find all PRP history keys
        history_keys = self.redis_client.keys("prp:*:history:*")
        cleaned = 0

        for key in history_keys:
            # Get the first entry to check age
            first_entry = self.redis_client.lindex(key, 0)
            if not first_entry:
                continue

            try:
                import json

                entry = json.loads(first_entry)
                timestamp = datetime.fromisoformat(entry.get("timestamp", ""))

                if timestamp.timestamp() < cutoff_time:
                    # This history is old, delete it
                    self.redis_client.delete(key)
                    cleaned += 1

            except Exception:
                pass

        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old conversation histories")


if __name__ == "__main__":
    import sys

    # Allow timeout override from command line
    timeout = int(sys.argv[1]) if len(sys.argv) > 1 else 1800

    watchdog = Watchdog(timeout_seconds=timeout)
    watchdog.run_forever()
