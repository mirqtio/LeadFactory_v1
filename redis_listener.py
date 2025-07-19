#!/usr/bin/env python3
"""
Redis Listener for Orchestrator Agent Coordination
Real-time monitoring of agent status updates and coordination events
"""
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import redis


class OrchestratorRedisListener:
    def __init__(self, host="localhost", port=6379, db=0):
        """Initialize Redis listener for orchestrator coordination."""
        self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        self.agent_status = {}
        self.last_update = {}

    def test_connection(self) -> bool:
        """Test Redis connection."""
        try:
            response = self.redis_client.ping()
            print(f"✅ Redis connection successful: {response}")
            return True
        except Exception as e:
            print(f"❌ Redis connection failed: {e}")
            return False

    def update_agent_status(self, agent_id: str, status_data: Dict[str, Any]) -> None:
        """Update agent status in Redis using universal format."""
        timestamp = datetime.now(timezone.utc).isoformat()

        # Store in universal format
        status_key = f"agent:status:{agent_id}"
        activity_key = f"agent:activity:{agent_id}"
        heartbeat_key = f"agent:heartbeat:{agent_id}"

        try:
            # Universal status format
            universal_status = f"{agent_id} {status_data.get('symbol', '🔄')} {status_data.get('task', 'unknown')}({status_data.get('progress', '0%')}) | {status_data.get('activity', 'unknown')} | {status_data.get('blockers', 'unknown')} | ⏱️{status_data.get('time', timestamp[-8:-3])} | ETA:{status_data.get('eta', 'unknown')}"

            self.redis_client.set(status_key, universal_status)
            self.redis_client.set(activity_key, status_data.get("activity", "unknown"))
            self.redis_client.set(heartbeat_key, timestamp)

            # Store local cache
            self.agent_status[agent_id] = status_data
            self.last_update[agent_id] = timestamp

            print(f"📊 Updated {agent_id}: {universal_status}")
            return True

        except Exception as e:
            print(f"❌ Failed to update {agent_id} status: {e}")
            return False

    def get_agent_status(self, agent_id: str) -> Optional[str]:
        """Get current agent status from Redis."""
        try:
            status_key = f"agent:status:{agent_id}"
            status = self.redis_client.get(status_key)
            return status
        except Exception as e:
            print(f"❌ Failed to get {agent_id} status: {e}")
            return None

    def get_all_agent_status(self) -> Dict[str, str]:
        """Get all agent statuses from Redis."""
        agents = {}
        try:
            pattern = "agent:status:*"
            keys = self.redis_client.keys(pattern)

            for key in keys:
                agent_id = key.split(":")[-1]
                status = self.redis_client.get(key)
                if status:
                    agents[agent_id] = status

            return agents
        except Exception as e:
            print(f"❌ Failed to get all agent statuses: {e}")
            return {}

    def check_agent_health(self) -> Dict[str, Any]:
        """Check agent health based on last heartbeat."""
        health_report = {"healthy": [], "stale": [], "missing": []}

        current_time = datetime.now(timezone.utc)
        stale_threshold = 30 * 60  # 30 minutes in seconds

        try:
            heartbeat_keys = self.redis_client.keys("agent:heartbeat:*")

            for key in heartbeat_keys:
                agent_id = key.split(":")[-1]
                last_heartbeat = self.redis_client.get(key)

                if last_heartbeat:
                    last_time = datetime.fromisoformat(last_heartbeat.replace("Z", "+00:00"))
                    age_seconds = (current_time - last_time).total_seconds()

                    if age_seconds < stale_threshold:
                        health_report["healthy"].append(agent_id)
                    else:
                        health_report["stale"].append({"agent": agent_id, "age_minutes": int(age_seconds / 60)})
                else:
                    health_report["missing"].append(agent_id)

            return health_report

        except Exception as e:
            print(f"❌ Failed to check agent health: {e}")
            return health_report

    def monitor_coordination_events(self, duration_seconds: int = 10) -> None:
        """Monitor coordination events for specified duration."""
        print(f"🔍 Monitoring Redis coordination events for {duration_seconds} seconds...")

        start_time = time.time()
        last_check = time.time()

        while time.time() - start_time < duration_seconds:
            current_time = time.time()

            # Check every 2 seconds
            if current_time - last_check >= 2:
                # Get all current agent statuses
                statuses = self.get_all_agent_status()

                if statuses:
                    print(f"\n📊 Agent Status Summary ({datetime.now().strftime('%H:%M:%S')}):")
                    for agent_id, status in statuses.items():
                        print(f"  {status}")
                else:
                    print(f"📭 No agent statuses found at {datetime.now().strftime('%H:%M:%S')}")

                # Check agent health
                health = self.check_agent_health()
                if health["stale"]:
                    print(f"⚠️  Stale agents: {health['stale']}")

                last_check = current_time

            time.sleep(0.5)  # Small sleep to prevent high CPU usage

    def setup_test_data(self) -> None:
        """Setup test agent data for demonstration."""
        test_agents = [
            {
                "agent_id": "PM-1",
                "symbol": "🔄",
                "task": "P0-022",
                "progress": "60%",
                "activity": "implementing bulk validation tests",
                "blockers": "✅ no blockers",
                "time": "05:30",
                "eta": "15m",
            },
            {
                "agent_id": "PM-3",
                "symbol": "🔄",
                "task": "P2-040",
                "progress": "40%",
                "activity": "analyzing budget stop requirements",
                "blockers": "✅ no blockers",
                "time": "05:30",
                "eta": "25m",
            },
            {
                "agent_id": "Validator",
                "symbol": "🟢",
                "task": "STANDBY",
                "progress": "100%",
                "activity": "waiting for PM handoffs",
                "blockers": "🚧 blocked on handoff",
                "time": "05:30",
                "eta": "0m",
            },
            {
                "agent_id": "Integration",
                "symbol": "🔄",
                "task": "CI_MONITOR",
                "progress": "ongoing",
                "activity": "monitoring 3 commits ahead",
                "blockers": "✅ no blockers",
                "time": "05:30",
                "eta": "10m",
            },
        ]

        print("🧪 Setting up test agent data...")
        for agent_data in test_agents:
            agent_id = agent_data.pop("agent_id")
            self.update_agent_status(agent_id, agent_data)

        print("✅ Test data setup complete")


def main():
    """Main function to test Redis listener functionality."""
    print("🚀 Starting Orchestrator Redis Listener Test")

    # Initialize listener
    listener = OrchestratorRedisListener()

    # Test connection
    if not listener.test_connection():
        print("❌ Cannot proceed without Redis connection")
        return

    # Setup test data
    listener.setup_test_data()

    # Test individual agent status retrieval
    print("\n🔍 Testing individual agent status retrieval:")
    for agent in ["PM-1", "PM-3", "Validator", "Integration"]:
        status = listener.get_agent_status(agent)
        if status:
            print(f"  {agent}: {status}")
        else:
            print(f"  {agent}: No status found")

    # Test health checking
    print("\n🏥 Testing agent health check:")
    health = listener.check_agent_health()
    print(f"  Healthy: {health['healthy']}")
    print(f"  Stale: {health['stale']}")
    print(f"  Missing: {health['missing']}")

    # Monitor for real-time updates
    print("\n🔄 Starting real-time monitoring (10 seconds)...")
    listener.monitor_coordination_events(10)

    print("\n✅ Redis listener test completed successfully!")


if __name__ == "__main__":
    main()
