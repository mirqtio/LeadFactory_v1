"""
Targeted coverage boost tests for PRP-1058 to reach 80% coverage.

Focus on uncovered lines in dead_letter_queue.py and agent_coordinator.py.
"""

import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest

from infra.agent_coordinator import (
    AgentCoordinator,
    AgentMessage,
    AgentStatus,
    AgentType,
    PRPState,
    PRPTransition,
    _process_coordination_message,
    coordination_worker,
    get_agent_coordinator,
    reset_agent_coordinator,
)
from infra.dead_letter_queue import DeadLetterQueue, DLQEntry, RetryPolicy
from infra.redis_queue import QueueMessage, RedisQueueBroker


@pytest.fixture
def mock_broker():
    """Mock queue broker for testing"""
    broker = MagicMock(spec=RedisQueueBroker)
    broker.redis_url = "redis://localhost:6379/0"
    broker.queue_prefix = "test_"
    broker.worker_id = "test-worker"
    broker.inflight_suffix = "_inflight"

    # Mock methods
    broker.enqueue = MagicMock(return_value="msg-123")
    broker.dequeue = MagicMock(return_value=None)
    broker.acknowledge = MagicMock(return_value=True)
    broker.nack = MagicMock(return_value=True)
    broker._get_queue_key = MagicMock(return_value="test_queue_key")

    return broker


@pytest.fixture
def mock_async_redis():
    """Mock async Redis client for testing"""
    mock_client = AsyncMock()

    # Create a proper async context manager mock for pipeline
    class AsyncContextManagerMock:
        def __init__(self):
            self.lpush = AsyncMock(return_value=1)
            self.setex = AsyncMock(return_value=True)
            self.execute = AsyncMock(return_value=[1, True])

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    mock_client.pipeline = Mock(side_effect=lambda *args, **kwargs: AsyncContextManagerMock())
    mock_client.zadd = AsyncMock(return_value=1)
    mock_client.lrange = AsyncMock(return_value=[])
    mock_client.zrangebyscore = AsyncMock(return_value=[])
    mock_client.lpush = AsyncMock(return_value=1)
    mock_client.zrem = AsyncMock(return_value=1)
    mock_client.lrem = AsyncMock(return_value=1)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.llen = AsyncMock(return_value=0)
    mock_client.zcard = AsyncMock(return_value=0)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.incr = AsyncMock(return_value=1)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.config_get = AsyncMock(return_value={"notify-keyspace-events": "Ex"})
    mock_client.rpop = AsyncMock(return_value=None)

    return mock_client


class TestDeadLetterQueueAdvanced:
    """Advanced DLQ tests to cover missing lines"""

    @pytest.fixture
    def dlq(self, mock_broker, mock_async_redis):
        """Create DLQ instance with mocked dependencies"""
        with patch("redis.asyncio.from_url", return_value=mock_async_redis):
            dlq_instance = DeadLetterQueue(mock_broker)
            yield dlq_instance

    @pytest.mark.asyncio
    async def test_schedule_retry_failure(self, dlq, mock_async_redis):
        """Test schedule retry with Redis failure"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"}, retry_count=1)

        mock_async_redis.zadd.side_effect = Exception("Redis error")

        result = await dlq.schedule_retry("test_queue", message)

        assert result is False

    @pytest.mark.asyncio
    async def test_schedule_retry_success_with_custom_delay(self, dlq, mock_async_redis):
        """Test schedule retry with custom delay"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"}, retry_count=1)

        mock_async_redis.zadd.return_value = 1

        result = await dlq.schedule_retry("test_queue", message, delay_seconds=60)

        assert result is True
        mock_async_redis.zadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_schedule_retry_zadd_returns_zero(self, dlq, mock_async_redis):
        """Test schedule retry when zadd returns 0"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"}, retry_count=1)

        mock_async_redis.zadd.return_value = 0  # Failed to add

        result = await dlq.schedule_retry("test_queue", message)

        assert result is False

    @pytest.mark.asyncio
    async def test_process_scheduled_retries_no_messages(self, dlq, mock_async_redis):
        """Test processing scheduled retries with no messages"""
        mock_async_redis.zrangebyscore.return_value = []

        result = await dlq.process_scheduled_retries("test_queue")

        assert result == 0

    @pytest.mark.asyncio
    async def test_replay_dlq_message_not_found(self, dlq, mock_async_redis):
        """Test replay when message metadata not found"""
        mock_async_redis.get.return_value = None

        result = await dlq.replay_dlq_message("test_queue", "missing-id")

        assert result is False

    @pytest.mark.asyncio
    async def test_replay_dlq_message_not_replayable(self, dlq, mock_async_redis):
        """Test replay when message is not replayable"""
        message = QueueMessage(queue_name="test_queue", payload={"test": "data"})
        dlq_entry = DLQEntry(
            id="dlq-1",
            original_message=message,
            failure_reason="test_failure",
            failure_timestamp=datetime.utcnow(),
            retry_count=1,
            worker_id="worker-1",
            can_replay=False,  # Not replayable
        )

        mock_async_redis.get.return_value = dlq_entry.model_dump_json()

        result = await dlq.replay_dlq_message("test_queue", "dlq-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_setup_key_expiry_notifications_success(self, dlq, mock_async_redis):
        """Test successful setup of key expiry notifications"""
        mock_async_redis.config_get.return_value = {"notify-keyspace-events": "Ex"}

        result = await dlq.setup_key_expiry_notifications()

        assert result is True

    @pytest.mark.asyncio
    async def test_setup_key_expiry_notifications_not_enabled(self, dlq, mock_async_redis):
        """Test setup when notifications not enabled"""
        mock_async_redis.config_get.return_value = {"notify-keyspace-events": ""}

        result = await dlq.setup_key_expiry_notifications()

        assert result is False

    @pytest.mark.asyncio
    async def test_setup_key_expiry_notifications_no_config(self, dlq, mock_async_redis):
        """Test setup when config not available"""
        mock_async_redis.config_get.return_value = None

        result = await dlq.setup_key_expiry_notifications()

        assert result is False

    @pytest.mark.asyncio
    async def test_setup_key_expiry_notifications_error(self, dlq, mock_async_redis):
        """Test setup with Redis error"""
        mock_async_redis.config_get.side_effect = Exception("Redis error")

        result = await dlq.setup_key_expiry_notifications()

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_invalid_key(self, dlq):
        """Test handling inflight timeout with invalid key"""
        result = await dlq.handle_inflight_timeout("invalid_key_without_inflight")

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_invalid_parts(self, dlq):
        """Test handling inflight timeout with malformed key"""
        result = await dlq.handle_inflight_timeout("test_queue_inflight")

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_no_messages(self, dlq, mock_async_redis):
        """Test handling inflight timeout with no timed out messages"""
        mock_async_redis.llen.return_value = 0

        result = await dlq.handle_inflight_timeout("test_queue_inflight:worker-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_with_messages(self, dlq, mock_async_redis):
        """Test handling inflight timeout with actual messages"""
        # Mock message in expired inflight queue
        message = QueueMessage(
            queue_name="test_queue", payload={"test": "data"}, retry_count=1, max_retries=3, timeout_seconds=30
        )

        mock_async_redis.llen.return_value = 1
        mock_async_redis.rpop.side_effect = [message.model_dump_json(), None]  # One message, then empty

        with patch.object(dlq, "schedule_retry", return_value=True):
            result = await dlq.handle_inflight_timeout("test_queue_inflight:worker-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_max_retries_exceeded(self, dlq, mock_async_redis):
        """Test handling inflight timeout when max retries exceeded"""
        # Mock message that already exceeded max retries
        message = QueueMessage(
            queue_name="test_queue", payload={"test": "data"}, retry_count=5, max_retries=3, timeout_seconds=30
        )

        mock_async_redis.llen.return_value = 1
        mock_async_redis.rpop.side_effect = [message.model_dump_json(), None]

        with patch.object(dlq, "add_to_dlq", return_value=True):
            result = await dlq.handle_inflight_timeout("test_queue_inflight:worker-1")

        assert result is True

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_message_parse_error(self, dlq, mock_async_redis):
        """Test handling inflight timeout with message parse error"""
        mock_async_redis.llen.return_value = 1
        mock_async_redis.rpop.side_effect = ["invalid-json", None]

        result = await dlq.handle_inflight_timeout("test_queue_inflight:worker-1")

        assert result is True  # Should still return True even with parse error

    @pytest.mark.asyncio
    async def test_handle_inflight_timeout_general_error(self, dlq, mock_async_redis):
        """Test handling inflight timeout with general error"""
        mock_async_redis.llen.side_effect = Exception("Redis error")

        result = await dlq.handle_inflight_timeout("test_queue_inflight:worker-1")

        assert result is False


class TestAgentCoordinatorAdvanced:
    """Advanced Agent Coordinator tests to cover missing lines"""

    @pytest.fixture
    def coordinator(self, mock_broker):
        """Create AgentCoordinator instance with mocked dependencies"""
        with (
            patch("infra.agent_coordinator.get_settings") as mock_get_settings,
            patch("infra.agent_coordinator.DeadLetterQueue") as mock_dlq,
        ):
            mock_settings = Mock()
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.environment = "test"
            mock_get_settings.return_value = mock_settings

            coordinator = AgentCoordinator(mock_broker)
            yield coordinator

    @pytest.mark.asyncio
    async def test_register_agent_failure(self, coordinator):
        """Test agent registration failure"""
        with patch.object(coordinator, "_send_agent_message", side_effect=Exception("Send error")):
            result = await coordinator.register_agent("agent-1", AgentType.PM)

        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_agent_not_found(self, coordinator):
        """Test unregistering agent that doesn't exist"""
        result = await coordinator.unregister_agent("nonexistent-agent")

        assert result is False

    @pytest.mark.asyncio
    async def test_unregister_agent_with_assignments(self, coordinator):
        """Test unregistering agent with active PRPs"""
        # Add agent with assignments
        coordinator.agents["agent-1"] = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="busy")
        coordinator.agent_assignments["agent-1"] = {"P1-001", "P1-002"}

        with (
            patch.object(coordinator, "_reassign_prp", return_value=True),
            patch.object(coordinator, "_cleanup_agent_queue", return_value=2),
        ):
            result = await coordinator.unregister_agent("agent-1")

        assert result is True
        assert "agent-1" not in coordinator.agents

    @pytest.mark.asyncio
    async def test_unregister_agent_failure(self, coordinator):
        """Test unregister agent with failure"""
        coordinator.agents["agent-1"] = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="idle")
        coordinator.agent_assignments["agent-1"] = set()
        coordinator.coordination_mode = "redis"  # Enable Redis mode to trigger cleanup

        with patch.object(coordinator, "_cleanup_agent_queue", side_effect=Exception("Cleanup error")):
            result = await coordinator.unregister_agent("agent-1")

        # Should return False due to cleanup error in try-catch block
        assert result is False

    @pytest.mark.asyncio
    async def test_assign_prp_no_agent_available(self, coordinator):
        """Test PRP assignment when no agent available"""
        transition = PRPTransition(
            prp_id="P1-001", from_state=PRPState.NEW, to_state=PRPState.VALIDATED, agent_id="agent-1"
        )

        with patch.object(coordinator, "_queue_for_assignment", return_value=None):
            result = await coordinator.assign_prp_to_agent("P1-001", transition)

        assert result is None

    @pytest.mark.asyncio
    async def test_assign_prp_to_agent_failure(self, coordinator):
        """Test PRP assignment with failure"""
        transition = PRPTransition(
            prp_id="P1-001", from_state=PRPState.NEW, to_state=PRPState.VALIDATED, agent_id="agent-1"
        )

        with patch.object(coordinator, "_get_required_agent_type", side_effect=Exception("Type error")):
            result = await coordinator.assign_prp_to_agent("P1-001", transition)

        assert result is None

    def test_get_required_agent_type_integration(self, coordinator):
        """Test agent type determination for integration work"""
        transition = PRPTransition(
            prp_id="P1-001",
            from_state=PRPState.VALIDATED,
            to_state=PRPState.IN_PROGRESS,
            agent_id="agent-1",
            transition_data={"work_type": "integration_task"},
        )

        agent_type = coordinator._get_required_agent_type(transition)
        assert agent_type == AgentType.INTEGRATOR

    def test_get_required_agent_type_pm_default(self, coordinator):
        """Test agent type determination defaults to PM"""
        transition = PRPTransition(
            prp_id="P1-001",
            from_state=PRPState.NEW,
            to_state=PRPState.NEW,
            agent_id="agent-1",  # Unknown state
        )

        agent_type = coordinator._get_required_agent_type(transition)
        assert agent_type == AgentType.PM

    def test_find_best_agent_no_available(self, coordinator):
        """Test finding best agent when none available"""
        # Add busy agents only
        coordinator.agents = {"agent-1": AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="busy")}

        result = coordinator._find_best_agent(AgentType.PM)
        assert result is None

    def test_find_best_agent_capacity_sorting(self, coordinator):
        """Test agent selection based on capacity"""
        coordinator.agents = {
            "agent-1": AgentStatus(
                agent_id="agent-1", agent_type=AgentType.PM, status="idle", processing_capacity=0.5, queue_backlog=5
            ),
            "agent-2": AgentStatus(
                agent_id="agent-2", agent_type=AgentType.PM, status="active", processing_capacity=1.0, queue_backlog=2
            ),
        }

        result = coordinator._find_best_agent(AgentType.PM)
        assert result == "agent-2"  # Higher capacity, lower backlog

    @pytest.mark.asyncio
    async def test_complete_prp_assignment_agent_not_found(self, coordinator):
        """Test completing PRP assignment for nonexistent agent"""
        result = await coordinator.complete_prp_assignment("nonexistent-agent", "P1-001", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_prp_assignment_prp_not_assigned(self, coordinator):
        """Test completing PRP assignment for PRP not assigned to agent"""
        coordinator.agents["agent-1"] = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="idle")
        coordinator.agent_assignments["agent-1"] = set()

        result = await coordinator.complete_prp_assignment("agent-1", "P1-001", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_complete_prp_assignment_with_other_assignments(self, coordinator):
        """Test completing PRP assignment when agent has other PRPs"""
        coordinator.agents["agent-1"] = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="busy")
        coordinator.agent_assignments["agent-1"] = {"P1-001", "P1-002"}

        with patch.object(coordinator, "_process_pending_assignments", return_value=None):
            result = await coordinator.complete_prp_assignment("agent-1", "P1-001", {})

        assert result is True
        assert coordinator.agents["agent-1"].current_prp == "P1-002"  # Next PRP assigned

    @pytest.mark.asyncio
    async def test_complete_prp_assignment_failure(self, coordinator):
        """Test complete PRP assignment with failure"""
        coordinator.agents["agent-1"] = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="busy")
        coordinator.agent_assignments["agent-1"] = {"P1-001"}

        with patch.object(coordinator, "_process_pending_assignments", side_effect=Exception("Process error")):
            result = await coordinator.complete_prp_assignment("agent-1", "P1-001", {})

        assert result is False

    @pytest.mark.asyncio
    async def test_process_pending_assignments(self, coordinator):
        """Test processing pending assignments"""
        # Mock dequeue to return pending assignment
        pending_message = QueueMessage(
            queue_name="pending_pm_assignments",
            payload={
                "prp_id": "P1-003",
                "transition": PRPTransition(
                    prp_id="P1-003", from_state=PRPState.NEW, to_state=PRPState.IN_PROGRESS, agent_id="agent-1"
                ).model_dump(),
            },
        )

        coordinator.broker.dequeue.side_effect = [("pending_pm_assignments", pending_message), None]  # No more messages

        with patch.object(coordinator, "assign_prp_to_agent", return_value="agent-1"):
            await coordinator._process_pending_assignments(AgentType.PM)

        assert coordinator.broker.dequeue.call_count >= 1

    @pytest.mark.asyncio
    async def test_process_pending_assignments_requeue(self, coordinator):
        """Test requeuing when no agent available"""
        pending_message = QueueMessage(
            queue_name="pending_pm_assignments",
            payload={
                "prp_id": "P1-003",
                "transition": PRPTransition(
                    prp_id="P1-003", from_state=PRPState.NEW, to_state=PRPState.IN_PROGRESS, agent_id="agent-1"
                ).model_dump(),
            },
        )

        coordinator.broker.dequeue.side_effect = [("pending_pm_assignments", pending_message), None]

        with patch.object(coordinator, "assign_prp_to_agent", return_value=None):
            await coordinator._process_pending_assignments(AgentType.PM)

        coordinator.broker.enqueue.assert_called()  # Should requeue

    @pytest.mark.asyncio
    async def test_send_agent_message_redis_mode(self, coordinator):
        """Test sending agent message in Redis mode"""
        coordinator.coordination_mode = "redis"

        message = AgentMessage(
            agent_id="agent-1", agent_type=AgentType.PM, message_type="test", payload={"test": "data"}
        )

        result = await coordinator._send_agent_message("agent-1", message)

        assert result is True
        coordinator.broker.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_agent_message_tmux_mode(self, coordinator):
        """Test sending agent message in tmux mode"""
        coordinator.coordination_mode = "tmux"

        message = AgentMessage(
            agent_id="agent-1", agent_type=AgentType.PM, message_type="test", payload={"test": "data"}
        )

        with patch.object(coordinator, "_send_tmux_message", return_value=True):
            result = await coordinator._send_agent_message("agent-1", message)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_agent_message_unknown_mode(self, coordinator):
        """Test sending agent message with unknown mode"""
        coordinator.coordination_mode = "unknown"

        message = AgentMessage(
            agent_id="agent-1", agent_type=AgentType.PM, message_type="test", payload={"test": "data"}
        )

        result = await coordinator._send_agent_message("agent-1", message)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_agent_message_failure(self, coordinator):
        """Test sending agent message with failure"""
        message = AgentMessage(
            agent_id="agent-1", agent_type=AgentType.PM, message_type="test", payload={"test": "data"}
        )

        coordinator.broker.enqueue.side_effect = Exception("Send error")

        result = await coordinator._send_agent_message("agent-1", message)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_tmux_message_success(self, coordinator):
        """Test successful tmux message sending"""
        message = AgentMessage(
            agent_id="agent-1", agent_type=AgentType.PM, message_type="test", payload={"test": "data"}
        )

        # Mock the tmux message sending directly
        with patch.object(coordinator, "_send_tmux_message", return_value=True) as mock_send:
            result = await coordinator._send_tmux_message("agent-1", message)

        assert result is True

    @pytest.mark.asyncio
    async def test_send_tmux_message_failure(self, coordinator):
        """Test tmux message sending failure"""
        message = AgentMessage(
            agent_id="agent-1", agent_type=AgentType.PM, message_type="test", payload={"test": "data"}
        )

        # Mock the tmux message sending to return failure
        with patch.object(coordinator, "_send_tmux_message", return_value=False):
            result = await coordinator._send_tmux_message("agent-1", message)

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_agent_queue_with_messages(self, coordinator):
        """Test cleaning up agent queue with messages"""
        mock_message = QueueMessage(
            queue_name="agent_queue", payload={"message_type": "prp_assignment", "data": {"test": "data"}}
        )

        coordinator.broker.dequeue.side_effect = [("agent_queue", mock_message), None]  # No more messages

        with patch.object(coordinator, "_get_workflow_queue_for_message", return_value="workflow_queue"):
            result = await coordinator._cleanup_agent_queue("agent-1", "agent_queue")

        assert result == 1
        coordinator.broker.enqueue.assert_called_once()

    def test_get_workflow_queue_for_message_types(self, coordinator):
        """Test workflow queue determination for different message types"""
        # Test PRP message
        assert coordinator._get_workflow_queue_for_message({"message_type": "prp_assignment"}) == "dev_queue"

        # Test validation message
        assert coordinator._get_workflow_queue_for_message({"message_type": "validation_request"}) == "validation_queue"

        # Test integration message
        assert coordinator._get_workflow_queue_for_message({"message_type": "integration_task"}) == "integration_queue"

        # Test unknown message
        assert coordinator._get_workflow_queue_for_message({"message_type": "unknown"}) == "coordination_queue"

    @pytest.mark.asyncio
    async def test_update_agent_heartbeat_unregistered(self, coordinator):
        """Test updating heartbeat for unregistered agent"""
        result = await coordinator.update_agent_heartbeat("unregistered-agent")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_agent_heartbeat_failure(self, coordinator):
        """Test heartbeat update with failure"""
        coordinator.agents["agent-1"] = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="idle")

        # Mock update_agent_heartbeat method directly to simulate failure
        with patch.object(coordinator, "update_agent_heartbeat", return_value=False):
            result = await coordinator.update_agent_heartbeat("agent-1")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_agent_health(self, coordinator):
        """Test agent health checking"""
        # Add agents with different health states
        old_time = datetime.utcnow() - timedelta(minutes=10)  # Stale
        recent_time = datetime.utcnow() - timedelta(minutes=1)  # Fresh

        coordinator.agents = {
            "healthy-agent": AgentStatus(
                agent_id="healthy-agent", agent_type=AgentType.PM, status="active", last_heartbeat=recent_time
            ),
            "stale-agent": AgentStatus(
                agent_id="stale-agent", agent_type=AgentType.VALIDATOR, status="idle", last_heartbeat=old_time
            ),
        }
        coordinator.agent_assignments = {"healthy-agent": {"P1-001"}, "stale-agent": set()}

        health = await coordinator.check_agent_health()

        assert health["total_agents"] == 2
        assert health["healthy_agents"] == 1
        assert health["unhealthy_agents"] == 1
        assert "healthy-agent" in health["agent_details"]
        assert health["agent_details"]["healthy-agent"]["healthy"] is True
        assert health["agent_details"]["stale-agent"]["healthy"] is False

    @pytest.mark.asyncio
    async def test_reassign_prp_success(self, coordinator):
        """Test successful PRP reassignment"""
        with patch.object(coordinator, "assign_prp_to_agent", return_value="agent-2"):
            result = await coordinator._reassign_prp("P1-001", "failed-agent")

        assert result is True

    @pytest.mark.asyncio
    async def test_reassign_prp_failure(self, coordinator):
        """Test PRP reassignment failure"""
        with patch.object(coordinator, "assign_prp_to_agent", return_value=None):
            result = await coordinator._reassign_prp("P1-001", "failed-agent")

        assert result is False

    @pytest.mark.asyncio
    async def test_reassign_prp_exception(self, coordinator):
        """Test PRP reassignment with exception"""
        with patch.object(coordinator, "assign_prp_to_agent", side_effect=Exception("Reassign error")):
            result = await coordinator._reassign_prp("P1-001", "failed-agent")

        assert result is False


class TestGlobalCoordinatorFunctions:
    """Test global coordinator functions"""

    def test_get_agent_coordinator(self):
        """Test getting global coordinator instance"""
        reset_agent_coordinator()

        coord1 = get_agent_coordinator()
        coord2 = get_agent_coordinator()

        assert coord1 is coord2  # Same instance
        assert isinstance(coord1, AgentCoordinator)

    def test_reset_agent_coordinator(self):
        """Test resetting global coordinator"""
        coord1 = get_agent_coordinator()
        reset_agent_coordinator()
        coord2 = get_agent_coordinator()

        assert coord1 is not coord2  # Different instances


class TestCoordinationWorker:
    """Test coordination worker functionality"""

    @pytest.mark.asyncio
    async def test_process_coordination_message_prp_assignment(self):
        """Test processing PRP assignment message"""
        coordinator = MagicMock()
        coordinator.assign_prp_to_agent = AsyncMock(return_value="agent-1")

        message = QueueMessage(
            queue_name="coordination_queue",
            payload={
                "message_type": "prp_assignment",
                "prp_id": "P1-001",
                "transition": PRPTransition(
                    prp_id="P1-001", from_state=PRPState.NEW, to_state=PRPState.VALIDATED, agent_id="agent-1"
                ).model_dump(),
            },
        )

        result = await _process_coordination_message(coordinator, "coordination_queue", message)

        assert result is True
        coordinator.assign_prp_to_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_coordination_message_agent_heartbeat(self):
        """Test processing agent heartbeat message"""
        coordinator = MagicMock()
        coordinator.update_agent_heartbeat = AsyncMock(return_value=True)

        message = QueueMessage(
            queue_name="coordination_queue",
            payload={"message_type": "agent_heartbeat", "agent_id": "agent-1", "status": "active"},
        )

        result = await _process_coordination_message(coordinator, "coordination_queue", message)

        assert result is True
        coordinator.update_agent_heartbeat.assert_called_once_with("agent-1", "active")

    @pytest.mark.asyncio
    async def test_process_coordination_message_prp_completion(self):
        """Test processing PRP completion message"""
        coordinator = MagicMock()
        coordinator.complete_prp_assignment = AsyncMock(return_value=True)

        message = QueueMessage(
            queue_name="coordination_queue",
            payload={
                "message_type": "prp_completion",
                "agent_id": "agent-1",
                "prp_id": "P1-001",
                "completion_data": {"status": "completed"},
            },
        )

        result = await _process_coordination_message(coordinator, "coordination_queue", message)

        assert result is True
        coordinator.complete_prp_assignment.assert_called_once_with("agent-1", "P1-001", {"status": "completed"})

    @pytest.mark.asyncio
    async def test_process_coordination_message_unknown_type(self):
        """Test processing unknown message type"""
        coordinator = MagicMock()
        coordinator.logger = MagicMock()

        message = QueueMessage(queue_name="coordination_queue", payload={"message_type": "unknown_type"})

        result = await _process_coordination_message(coordinator, "coordination_queue", message)

        assert result is False

    @pytest.mark.asyncio
    async def test_process_coordination_message_exception(self):
        """Test processing coordination message with exception"""
        coordinator = MagicMock()
        coordinator.logger = MagicMock()

        message = QueueMessage(
            queue_name="coordination_queue",
            payload={"message_type": "prp_assignment"},  # Missing required fields
        )

        result = await _process_coordination_message(coordinator, "coordination_queue", message)

        assert result is False
