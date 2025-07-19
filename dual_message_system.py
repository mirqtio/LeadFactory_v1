#!/usr/bin/env python3
"""
Dual Message System: Redis + Tmux Parallel Messaging
Sends same messages to both Redis pub/sub and tmux for redundancy
"""
import json
import subprocess
import time
from datetime import datetime
from typing import List, Optional


class DualMessageSystem:
    def __init__(self):
        self.agent_windows = {"PM-1": 1, "PM-2": 2, "PM-3": 3, "Validator": 4, "Integration": 5}

    def send_to_agent(self, agent_id: str, message: str, priority: str = "normal"):
        """Send message via both Redis and tmux"""
        print(f"📤 DUAL SEND to {agent_id}: {message[:50]}...")

        # 1. Redis pub/sub
        redis_success = self._send_redis(agent_id, message, priority)

        # 2. Tmux send-keys (existing method)
        tmux_success = self._send_tmux(agent_id, message)

        return {
            "redis": redis_success,
            "tmux": tmux_success,
            "agent": agent_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def broadcast_to_all(self, message: str, priority: str = "normal"):
        """Broadcast message to all agents via both channels"""
        print(f"📢 DUAL BROADCAST: {message[:50]}...")

        results = []

        # Redis broadcast
        redis_result = self._send_redis_broadcast(message, priority)

        # Tmux to all windows
        for agent_id in self.agent_windows.keys():
            tmux_result = self._send_tmux(agent_id, message)
            results.append({"agent": agent_id, "redis": redis_result, "tmux": tmux_result})

        return results

    def _send_redis(self, agent_id: str, message: str, priority: str = "normal") -> bool:
        """Send message via Redis pub/sub"""
        try:
            channel = f"agent:{agent_id.lower().replace('-', '')}"
            message_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "from": "orchestrator",
                "to": agent_id,
                "message": message,
                "priority": priority,
                "type": "direct",
                "channel": "redis",
            }

            cmd = ["redis-cli", "PUBLISH", channel, json.dumps(message_data)]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            subscribers = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

            print(f"  📨 Redis→{agent_id}: {subscribers} subscribers")
            return result.returncode == 0

        except Exception as e:
            print(f"  ❌ Redis→{agent_id} FAILED: {e}")
            return False

    def _send_redis_broadcast(self, message: str, priority: str = "normal") -> bool:
        """Send broadcast via Redis"""
        try:
            message_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "from": "orchestrator",
                "to": "all",
                "message": message,
                "priority": priority,
                "type": "broadcast",
                "channel": "redis",
            }

            cmd = ["redis-cli", "PUBLISH", "agent:broadcast", json.dumps(message_data)]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            subscribers = int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0

            print(f"  📢 Redis Broadcast: {subscribers} subscribers")
            return result.returncode == 0

        except Exception as e:
            print(f"  ❌ Redis Broadcast FAILED: {e}")
            return False

    def _send_tmux(self, agent_id: str, message: str) -> bool:
        """Send message via tmux (existing method)"""
        try:
            if agent_id not in self.agent_windows:
                print(f"  ❌ Tmux→{agent_id}: Unknown agent")
                return False

            window_num = self.agent_windows[agent_id]

            # Send message
            cmd_message = ["tmux", "send-keys", "-t", f"orchestrator:{window_num}", message]

            result_msg = subprocess.run(cmd_message, capture_output=True, text=True, timeout=5)

            # Send Enter
            cmd_enter = ["tmux", "send-keys", "-t", f"orchestrator:{window_num}", "Enter"]

            result_enter = subprocess.run(cmd_enter, capture_output=True, text=True, timeout=5)

            success = result_msg.returncode == 0 and result_enter.returncode == 0
            print(f"  📺 Tmux→{agent_id} (window {window_num}): {'✅' if success else '❌'}")

            return success

        except Exception as e:
            print(f"  ❌ Tmux→{agent_id} FAILED: {e}")
            return False


def test_dual_system():
    """Test the dual messaging system"""
    messenger = DualMessageSystem()

    print("🧪 TESTING DUAL MESSAGE SYSTEM\n")

    # Test 1: Individual agent messages
    print("1. Testing individual agent messages:")
    result = messenger.send_to_agent("PM-1", "🎯 DUAL TEST: This message sent via both Redis and tmux!")
    print(f"   Result: {result}\n")

    # Test 2: Broadcast to all
    print("2. Testing broadcast to all agents:")
    results = messenger.broadcast_to_all("🎯 DUAL BROADCAST: This broadcast sent via both Redis and tmux!")
    print(f"   Results: {len(results)} agents contacted\n")

    # Test 3: Priority message
    print("3. Testing high priority message:")
    result = messenger.send_to_agent(
        "Validator", "🚨 HIGH PRIORITY DUAL TEST: Critical message via both channels!", "high"
    )
    print(f"   Result: {result}\n")

    print("✅ Dual messaging system test complete!")

    return messenger


if __name__ == "__main__":
    messenger = test_dual_system()
