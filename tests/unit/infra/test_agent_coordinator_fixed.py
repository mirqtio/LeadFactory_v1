"""
Fixed unit tests for infra.agent_coordinator - Essential functionality tests.

Focus on core agent coordination features to achieve coverage requirements.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from infra.agent_coordinator import (
    AgentCoordinator,
    AgentMessage,
    AgentStatus,
    AgentType,
    PRPState,
    PRPTransition,
    get_agent_coordinator,
    reset_agent_coordinator,
)
from infra.redis_queue import RedisQueueBroker


@pytest.fixture
def mock_broker():
    """Mock queue broker for testing"""
    mock_broker = MagicMock(spec=RedisQueueBroker)
    mock_broker.enqueue.return_value = "msg_123"
    mock_broker.dequeue.return_value = None
    mock_broker.redis_url = "redis://localhost:6379/0"
    mock_broker.queue_prefix = "test_"
    mock_broker.worker_id = "test-worker"
    return mock_broker


@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Mock()
    settings.redis_url = "redis://localhost:6379/0"
    settings.environment = "test"
    return settings


@pytest.fixture
def coordinator(mock_broker, mock_settings):
    """Create AgentCoordinator instance with mocked dependencies"""
    with patch("infra.agent_coordinator.get_settings", return_value=mock_settings):
        coordinator = AgentCoordinator(mock_broker)
        yield coordinator


class TestPRPState:
    """Test PRP state enumeration"""

    def test_prp_states(self):
        """Test PRP state values"""
        assert PRPState.NEW == "new"
        assert PRPState.VALIDATED == "validated"
        assert PRPState.IN_PROGRESS == "in_progress"
        assert PRPState.COMPLETE == "complete"


class TestAgentType:
    """Test Agent type enumeration"""

    def test_agent_types(self):
        """Test agent type values"""
        assert AgentType.PM == "pm"
        assert AgentType.INTEGRATOR == "integrator"
        assert AgentType.VALIDATOR == "validator"
        assert AgentType.ORCHESTRATOR == "orchestrator"
        assert AgentType.SECURITY == "security"


class TestPRPTransition:
    """Test PRP transition model"""

    def test_prp_transition_creation(self):
        """Test creating PRP transition"""
        transition = PRPTransition(
            prp_id="P1-001", from_state=PRPState.NEW, to_state=PRPState.VALIDATED, agent_id="agent-1"
        )

        assert transition.prp_id == "P1-001"
        assert transition.from_state == PRPState.NEW
        assert transition.to_state == PRPState.VALIDATED
        assert transition.agent_id == "agent-1"


class TestAgentMessage:
    """Test Agent message model"""

    def test_agent_message_creation(self):
        """Test creating agent message"""
        message = AgentMessage(
            agent_id="agent-1",
            agent_type=AgentType.PM,
            message_type="task_assignment",
            payload={"task": "validate_prp"},
        )

        assert message.agent_id == "agent-1"
        assert message.agent_type == AgentType.PM
        assert message.message_type == "task_assignment"
        assert message.payload == {"task": "validate_prp"}
        assert message.priority == 0
        assert message.requires_response is False


class TestAgentStatus:
    """Test Agent status model"""

    def test_agent_status_creation(self):
        """Test creating agent status"""
        status = AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="active")

        assert status.agent_id == "agent-1"
        assert status.agent_type == AgentType.PM
        assert status.status == "active"
        assert status.current_prp is None
        assert status.processing_capacity == 1.0


class TestAgentCoordinator:
    """Test AgentCoordinator class"""

    def test_initialization(self, coordinator, mock_broker, mock_settings):
        """Test coordinator initialization"""
        assert coordinator.broker == mock_broker
        assert coordinator.settings == mock_settings
        assert len(coordinator.agents) == 0

    def test_get_agent_queue_name(self, coordinator):
        """Test agent queue name generation"""
        queue_name = coordinator.get_agent_queue_name("agent-1", AgentType.PM)
        assert queue_name == "pm_agent-1_queue"

    def test_get_workflow_queue_name(self, coordinator):
        """Test workflow queue name lookup"""
        queue_name = coordinator.get_workflow_queue_name("prp_validation")
        assert queue_name == "validation_queue"

    @pytest.mark.asyncio
    async def test_register_agent_success(self, coordinator):
        """Test successful agent registration"""
        result = await coordinator.register_agent("agent-1", AgentType.PM, capacity=0.8)

        assert result is True
        assert "agent-1" in coordinator.agents
        assert coordinator.agents["agent-1"].agent_type == AgentType.PM
        assert coordinator.agents["agent-1"].processing_capacity == 0.8

    @pytest.mark.asyncio
    async def test_register_agent_duplicate(self, coordinator):
        """Test registering duplicate agent"""
        # Register first time
        await coordinator.register_agent("agent-1", AgentType.PM)

        # Register again - should update
        result = await coordinator.register_agent("agent-1", AgentType.VALIDATOR)
        assert result is True
        assert coordinator.agents["agent-1"].agent_type == AgentType.VALIDATOR

    @pytest.mark.asyncio
    async def test_unregister_agent(self, coordinator):
        """Test agent unregistration"""
        # Register first
        await coordinator.register_agent("agent-1", AgentType.PM)
        assert "agent-1" in coordinator.agents

        # Unregister
        result = await coordinator.unregister_agent("agent-1")
        assert result is True
        assert "agent-1" not in coordinator.agents

    @pytest.mark.asyncio
    async def test_unregister_agent_not_found(self, coordinator):
        """Test unregistering non-existent agent"""
        result = await coordinator.unregister_agent("nonexistent")
        assert result is False

    def test_get_required_agent_type(self, coordinator):
        """Test determining required agent type for PRP transition"""
        # Test validation transition
        transition = PRPTransition(
            prp_id="P1-001", from_state=PRPState.NEW, to_state=PRPState.VALIDATED, agent_id="agent-1"
        )
        agent_type = coordinator._get_required_agent_type(transition)
        assert agent_type == AgentType.VALIDATOR

        # Test in_progress transition
        transition.to_state = PRPState.IN_PROGRESS
        agent_type = coordinator._get_required_agent_type(transition)
        assert agent_type == AgentType.PM

        # Test complete transition
        transition.to_state = PRPState.COMPLETE
        agent_type = coordinator._get_required_agent_type(transition)
        assert agent_type == AgentType.VALIDATOR

    def test_find_best_agent(self, coordinator):
        """Test finding best available agent"""
        # No agents available
        best = coordinator._find_best_agent(AgentType.PM)
        assert best is None

        # Add some agents
        coordinator.agents = {
            "agent-1": AgentStatus(agent_id="agent-1", agent_type=AgentType.PM, status="idle", processing_capacity=0.8),
            "agent-2": AgentStatus(agent_id="agent-2", agent_type=AgentType.PM, status="idle", processing_capacity=1.0),
            "agent-3": AgentStatus(
                agent_id="agent-3", agent_type=AgentType.VALIDATOR, status="idle", processing_capacity=0.9
            ),
        }

        # Should return highest capacity PM agent
        best = coordinator._find_best_agent(AgentType.PM)
        assert best == "agent-2"  # Highest capacity

        # Should return validator
        best = coordinator._find_best_agent(AgentType.VALIDATOR)
        assert best == "agent-3"

    @pytest.mark.asyncio
    async def test_update_agent_heartbeat(self, coordinator):
        """Test updating agent heartbeat"""
        # Register agent first
        await coordinator.register_agent("agent-1", AgentType.PM)

        # Update heartbeat
        result = await coordinator.update_agent_heartbeat("agent-1", "active")
        assert result is True
        assert coordinator.agents["agent-1"].status == "active"

    @pytest.mark.asyncio
    async def test_update_agent_heartbeat_not_found(self, coordinator):
        """Test updating heartbeat for non-existent agent"""
        result = await coordinator.update_agent_heartbeat("nonexistent", "active")
        assert result is False


class TestGlobalCoordinatorFunctions:
    """Test global coordinator management functions"""

    def test_get_agent_coordinator(self):
        """Test getting global coordinator instance"""
        reset_agent_coordinator()  # Ensure clean state

        with (
            patch("infra.agent_coordinator.get_queue_broker") as mock_get_broker,
            patch("infra.agent_coordinator.get_settings") as mock_get_settings,
            patch("infra.agent_coordinator.DeadLetterQueue") as mock_dlq,
        ):
            mock_broker = MagicMock(spec=RedisQueueBroker)
            mock_broker.redis_url = "redis://localhost:6379/0"
            mock_broker.queue_prefix = "test_"
            mock_broker.worker_id = "test-worker"
            mock_get_broker.return_value = mock_broker
            mock_settings = Mock()
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.environment = "test"
            mock_get_settings.return_value = mock_settings

            coordinator1 = get_agent_coordinator()
            coordinator2 = get_agent_coordinator()

            assert coordinator1 is coordinator2  # Same instance
            assert isinstance(coordinator1, AgentCoordinator)

    def test_reset_agent_coordinator(self):
        """Test resetting global coordinator instance"""
        with (
            patch("infra.agent_coordinator.get_queue_broker") as mock_get_broker,
            patch("infra.agent_coordinator.get_settings") as mock_get_settings,
            patch("infra.agent_coordinator.DeadLetterQueue") as mock_dlq,
        ):
            mock_broker = MagicMock(spec=RedisQueueBroker)
            mock_broker.redis_url = "redis://localhost:6379/0"
            mock_broker.queue_prefix = "test_"
            mock_broker.worker_id = "test-worker"
            mock_get_broker.return_value = mock_broker
            mock_settings = Mock()
            mock_settings.redis_url = "redis://localhost:6379/0"
            mock_settings.environment = "test"
            mock_get_settings.return_value = mock_settings

            coordinator1 = get_agent_coordinator()
            reset_agent_coordinator()
            coordinator2 = get_agent_coordinator()

            assert coordinator1 is not coordinator2  # Different instances


class TestAgentCoordinatorEdgeCases:
    """Test edge cases and error scenarios"""

    @pytest.mark.asyncio
    async def test_assign_prp_no_agents(self, coordinator):
        """Test assigning PRP when no agents available"""
        transition = PRPTransition(
            prp_id="P1-001", from_state=PRPState.NEW, to_state=PRPState.VALIDATED, agent_id="agent-1"
        )

        result = await coordinator.assign_prp_to_agent("P1-001", transition)
        assert result is None

    @pytest.mark.asyncio
    async def test_register_agent_exception_handling(self, coordinator):
        """Test agent registration with exception"""
        with patch.object(coordinator, "_send_agent_message", side_effect=Exception("Network error")):
            # Should handle exception gracefully
            result = await coordinator.register_agent("agent-1", AgentType.PM)
            assert result is False

    @pytest.mark.asyncio
    async def test_assignment_with_capacity_consideration(self, coordinator):
        """Test PRP assignment considering agent capacity"""
        # Register agents with different capacities
        await coordinator.register_agent("agent-low", AgentType.PM, capacity=0.3)
        await coordinator.register_agent("agent-high", AgentType.PM, capacity=0.9)

        # Should prefer high capacity agent
        best = coordinator._find_best_agent(AgentType.PM)
        assert best == "agent-high"
