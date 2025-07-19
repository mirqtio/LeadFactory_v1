#!/usr/bin/env python3
"""
Redis Message Bus for Agent Communication
Replaces unreliable tmux send-keys with robust Redis pub/sub
"""
import json
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List

import redis


class RedisMessageBus:
    def __init__(self, host="localhost", port=6379):
        self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.subscribers = {}
        self.running = False

    def publish_to_agent(self, agent_id: str, message: str, priority: str = "normal"):
        """Send message to specific agent"""
        channel = f"agent:{agent_id.lower()}"
        message_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "from": "orchestrator",
            "to": agent_id,
            "message": message,
            "priority": priority,
            "type": "direct",
        }

        result = self.redis_client.publish(channel, json.dumps(message_data))
        print(f"📤 Sent to {agent_id}: {result} subscribers")
        return result

    def broadcast_to_all(self, message: str, priority: str = "normal"):
        """Broadcast message to all agents"""
        message_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "from": "orchestrator",
            "to": "all",
            "message": message,
            "priority": priority,
            "type": "broadcast",
        }

        result = self.redis_client.publish("agent:broadcast", json.dumps(message_data))
        print(f"📢 Broadcast: {result} subscribers")
        return result

    def agent_to_agent(self, from_agent: str, to_agent: str, message: str):
        """Enable agent-to-agent communication"""
        channel = f"agent:{to_agent.lower()}"
        message_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "priority": "normal",
            "type": "agent_to_agent",
        }

        result = self.redis_client.publish(channel, json.dumps(message_data))
        print(f"🔄 {from_agent} → {to_agent}: {result} subscribers")
        return result

    def create_agent_subscriber(self, agent_id: str):
        """Generate subscription command for agents"""
        return f"""
# Add this to {agent_id} startup:
redis-cli PSUBSCRIBE agent:{agent_id.lower()} agent:broadcast | while read line; do
    echo "📨 Redis Message: $line"
    # Process message in agent's Claude Code session
done &
"""


def test_message_bus():
    """Test the Redis message bus system"""
    bus = RedisMessageBus()

    print("🧪 Testing Redis Message Bus...")

    # Test individual agent messaging
    print("1. Testing individual agent messages:")
    bus.publish_to_agent("PM-1", "🎯 TEST: Direct message to PM-1 via Redis")
    bus.publish_to_agent("Validator", "🎯 TEST: Direct message to Validator via Redis")

    # Test broadcast
    print("2. Testing broadcast:")
    bus.broadcast_to_all("🎯 TEST: Broadcast message to all agents via Redis")

    # Test agent-to-agent
    print("3. Testing agent-to-agent:")
    bus.agent_to_agent("PM-1", "Validator", "🎯 TEST: PM-1 requesting validation status")

    print("✅ Message bus test complete!")

    # Generate subscriber setup for agents
    print("\n📋 Agent Subscription Setup:")
    agents = ["PM-1", "PM-2", "PM-3", "Validator", "Integration"]
    for agent in agents:
        print(f"\n{agent}:")
        print(bus.create_agent_subscriber(agent))


if __name__ == "__main__":
    test_message_bus()
