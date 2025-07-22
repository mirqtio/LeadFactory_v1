#!/usr/bin/env python3
"""
Test script for enterprise Redis-tmux integration
Verifies that the enterprise shim can connect to Redis and handle basic queue operations
"""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import get_settings
from infra.agent_coordinator import AgentCoordinator, AgentType
from infra.redis_queue import QueueMessage, RedisQueueBroker


async def test_enterprise_integration():
    """Test enterprise Redis integration"""
    print("🚀 Testing Enterprise Redis-Tmux Integration...")

    try:
        # Initialize components
        settings = get_settings()
        broker = RedisQueueBroker()
        coordinator = AgentCoordinator(broker=broker)

        print("✅ Initialized enterprise components")

        # Test Redis connection
        health = broker.health_check()
        if health["status"] != "healthy":
            print(f"❌ Redis health check failed: {health}")
            return False

        print(f"✅ Redis connected: {health['redis_version']}")

        # Test queue operations
        test_queue = "test_enterprise_queue"
        test_payload = {
            "prp_id": "TEST-001",
            "description": "Test PRP for enterprise integration",
            "priority_stage": "development",
        }

        # Enqueue test message
        message_id = broker.enqueue(test_queue, test_payload, priority=5)
        print(f"✅ Enqueued test message: {message_id}")

        # Dequeue test message
        result = broker.dequeue([test_queue], timeout=1.0)
        if result:
            queue_name, message = result
            print(f"✅ Dequeued message from {queue_name}: {message.id}")

            # Acknowledge message
            success = broker.acknowledge(queue_name, message)
            print(f"✅ Message acknowledged: {success}")
        else:
            print("❌ Failed to dequeue message")
            return False

        # Test agent registration
        agent_id = "test_agent_001"
        success = await coordinator.register_agent(agent_id=agent_id, agent_type=AgentType.PM, capacity=1.0)
        print(f"✅ Agent registration: {success}")

        # Test agent health check
        health_status = await coordinator.check_agent_health()
        print(f"✅ Agent health check - Total agents: {health_status['total_agents']}")

        # Cleanup
        await coordinator.unregister_agent(agent_id)
        broker.purge_queue(test_queue)
        print("✅ Cleanup completed")

        print("\n🎉 Enterprise integration test PASSED!")
        return True

    except Exception as e:
        print(f"❌ Enterprise integration test FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_imports():
    """Test that all required imports work"""
    print("🔍 Testing imports...")

    try:
        from infra.redis_queue import QueueMessage, RedisQueueBroker

        print("✅ redis_queue imports OK")

        from infra.agent_coordinator import AgentCoordinator, AgentType, PRPState

        print("✅ agent_coordinator imports OK")

        from core.config import get_settings

        print("✅ config imports OK")

        return True

    except Exception as e:
        print(f"❌ Import test FAILED: {e}")
        return False


async def main():
    """Main test runner"""
    print("🧪 Enterprise Redis-Tmux Integration Test Suite")
    print("=" * 60)

    # Test 1: Imports
    if not test_imports():
        sys.exit(1)

    print("")

    # Test 2: Enterprise integration
    if not await test_enterprise_integration():
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ All tests PASSED! Enterprise integration ready.")


if __name__ == "__main__":
    asyncio.run(main())
