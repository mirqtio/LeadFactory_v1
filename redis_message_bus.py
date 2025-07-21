#!/usr/bin/env python3
"""
Redis Message Bus for Agent Communication - Extended for backward compatibility.

Replaces unreliable tmux send-keys with robust Redis pub/sub while maintaining
compatibility with existing tmux-based agent communication during transition period.

DEPRECATION NOTICE: tmux helper methods will be marked @deprecated after P0-100 merges.
Use infra.redis_queue for new reliable queue-based messaging.
"""
import json
import os
import threading
import time
from datetime import datetime
from typing import Callable, Dict, List, Optional

import redis


class RedisMessageBus:
    def __init__(self, host="localhost", port=6379):
        self.redis_client = redis.Redis(host=host, port=port, decode_responses=True)
        self.pubsub = self.redis_client.pubsub()
        self.subscribers = {}
        self.running = False

        # Check coordination mode for compatibility
        self.coordination_mode = os.getenv("AGENT_COORDINATION_MODE", "tmux")

        # Queue broker integration (lazy initialization)
        self._queue_broker = None

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

        # If using Redis coordination mode, also send via queue for reliability
        if self.coordination_mode == "redis":
            self._send_via_queue(agent_id, message_data)

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

        # Broadcasts still use pub/sub even in Redis coordination mode
        # since they're not critical for delivery guarantees

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

        # If using Redis coordination mode, also send via queue for reliability
        if self.coordination_mode == "redis":
            self._send_via_queue(to_agent, message_data)

        return result

    def create_agent_subscriber(self, agent_id: str):
        """Generate subscription command for agents (backward compatibility)"""

        if self.coordination_mode == "redis":
            return f"""
# Modern Redis Queue-based subscription for {agent_id}:
# Use infra.agent_coordinator.register_agent() in your agent startup
# Queue-based messaging provides reliable delivery with retry and DLQ

from infra.agent_coordinator import get_agent_coordinator, AgentType
coordinator = get_agent_coordinator()
await coordinator.register_agent("{agent_id}", AgentType.PM)  # or appropriate type
"""
        else:
            return f"""
# Legacy pub/sub subscription for {agent_id} (DEPRECATED):
redis-cli PSUBSCRIBE agent:{agent_id.lower()} agent:broadcast | while read line; do
    echo "📨 Redis Message: $line"
    # Process message in agent's Claude Code session
done &

# MIGRATION NOTE: Switch to Redis queue mode by setting:
# export AGENT_COORDINATION_MODE=redis
"""

    def _get_queue_broker(self):
        """Get queue broker instance (lazy initialization)"""
        if self._queue_broker is None:
            try:
                from infra.redis_queue import get_queue_broker

                self._queue_broker = get_queue_broker()
            except ImportError:
                # Fallback if infra module not available
                print("Warning: Redis queue broker not available, using pub/sub only")
                return None
        return self._queue_broker

    def _send_via_queue(self, agent_id: str, message_data: Dict):
        """Send message via reliable queue system"""
        try:
            broker = self._get_queue_broker()
            if broker:
                # Determine queue name based on agent type
                queue_name = f"agent_{agent_id.lower()}_queue"

                # Convert message for queue format
                queue_payload = {
                    "message_type": "tmux_compatibility",
                    "original_message": message_data,
                    "agent_id": agent_id,
                }

                # Enqueue with appropriate priority
                priority = 10 if message_data.get("priority") == "high" else 0
                broker.enqueue(queue_name, queue_payload, priority=priority)

                print(f"📦 Queued for {agent_id} via reliable delivery")
        except Exception as e:
            print(f"Warning: Failed to send via queue, using pub/sub only: {e}")

    # DEPRECATED: Methods below will be marked @deprecated after P0-100
    # Use infra.agent_coordinator for new implementations

    def send_tmux_keystroke(self, pane: str, keystroke: str):
        """
        DEPRECATED: Send keystroke to tmux pane.

        Use infra.agent_coordinator.register_agent() and queue-based messaging instead.
        This method is maintained for backward compatibility only.
        """
        print(f"⚠️  DEPRECATED: send_tmux_keystroke will be removed after P0-100")
        print(f"⚠️  Use AGENT_COORDINATION_MODE=redis and infra.agent_coordinator instead")

        import subprocess

        try:
            subprocess.run(["tmux", "send-keys", "-t", pane, keystroke, "Enter"], capture_output=True, check=True)
            return True
        except subprocess.CalledProcessError:
            return False


def test_message_bus():
    """Test the Redis message bus system with backward compatibility"""
    bus = RedisMessageBus()

    print(f"🧪 Testing Redis Message Bus in {bus.coordination_mode} mode...")

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

    # Show coordination mode info
    print(f"\n🔧 Current coordination mode: {bus.coordination_mode}")
    print("💡 To switch to reliable queue mode: export AGENT_COORDINATION_MODE=redis")


if __name__ == "__main__":
    test_message_bus()
