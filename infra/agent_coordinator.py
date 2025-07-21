"""
Agent Coordination Layer for PRP workflow orchestration.

Provides agent-specific queue management with isolation, queue routing for 
PRP state transitions, queue-based workflow orchestration, and seamless
integration with existing Redis pub/sub system for broadcast messages.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from core.config import get_settings
from core.logging import get_logger
from infra.dead_letter_queue import DeadLetterQueue
from infra.queue_patterns import ReliableQueuePattern, queue_worker_context
from infra.redis_queue import QueueMessage, RedisQueueBroker, get_queue_broker


class PRPState(str, Enum):
    """PRP state enumeration"""

    NEW = "new"
    VALIDATED = "validated"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


class AgentType(str, Enum):
    """Agent type enumeration"""

    PM = "pm"
    INTEGRATOR = "integrator"
    VALIDATOR = "validator"
    ORCHESTRATOR = "orchestrator"
    SECURITY = "security"


class PRPTransition(BaseModel):
    """PRP state transition request"""

    prp_id: str
    from_state: PRPState
    to_state: PRPState
    agent_id: str
    transition_data: Dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0)


class AgentMessage(BaseModel):
    """Agent coordination message"""

    id: str = Field(default_factory=lambda: f"msg_{datetime.utcnow().timestamp()}")
    agent_id: str
    agent_type: AgentType
    message_type: str  # 'prp_transition', 'task_assignment', 'status_update', etc.
    payload: Dict[str, Any]
    priority: int = Field(default=0)
    requires_response: bool = Field(default=False)
    correlation_id: Optional[str] = Field(default=None)


class AgentStatus(BaseModel):
    """Agent status information"""

    agent_id: str
    agent_type: AgentType
    status: str  # 'active', 'busy', 'idle', 'offline'
    current_prp: Optional[str] = Field(default=None)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    queue_backlog: int = Field(default=0)
    processing_capacity: float = Field(default=1.0)


class AgentCoordinator:
    """
    Agent coordination system for PRP workflow orchestration.

    Features:
    - Agent-specific queue management with isolation
    - PRP state transition routing and validation
    - Workload distribution and capacity management
    - Integration with existing Redis pub/sub for broadcasts
    - Agent health monitoring and failover
    """

    def __init__(self, broker: Optional[RedisQueueBroker] = None):
        """
        Initialize agent coordinator.

        Args:
            broker: Redis queue broker instance
        """
        self.broker = broker or get_queue_broker()
        self.settings = get_settings()
        self.logger = get_logger("agent_coordinator", domain="infra")

        # Initialize components
        self.dlq = DeadLetterQueue(self.broker)
        self.reliable_pattern = ReliableQueuePattern(self.broker)

        # Agent management
        self.agents: Dict[str, AgentStatus] = {}
        self.agent_assignments: Dict[str, Set[str]] = {}  # agent_id -> set of PRPs

        # Queue configuration
        self.coordination_mode = os.getenv("AGENT_COORDINATION_MODE", "tmux")
        self.queue_routing = self._initialize_queue_routing()

        self.logger.info(f"Agent coordinator initialized in {self.coordination_mode} mode")

    def _initialize_queue_routing(self) -> Dict[str, str]:
        """Initialize queue routing for different workflows"""
        return {
            # PRP workflow queues
            "prp_validation": "validation_queue",
            "prp_integration": "integration_queue",
            "prp_development": "dev_queue",
            "prp_completion": "completion_queue",
            # Agent-specific queues
            "pm_tasks": "pm_queue",
            "integrator_tasks": "integrator_queue",
            "validator_tasks": "validator_queue",
            "security_tasks": "security_queue",
            # Broadcast and coordination
            "broadcast": "broadcast_queue",
            "coordination": "coordination_queue",
        }

    def get_agent_queue_name(self, agent_id: str, agent_type: AgentType) -> str:
        """Get queue name for specific agent"""
        return f"{agent_type.value}_{agent_id}_queue"

    def get_workflow_queue_name(self, workflow_type: str) -> str:
        """Get queue name for workflow type"""
        return self.queue_routing.get(workflow_type, "default_queue")

    async def register_agent(self, agent_id: str, agent_type: AgentType, capacity: float = 1.0) -> bool:
        """
        Register an agent with the coordination system.

        Args:
            agent_id: Unique agent identifier
            agent_type: Type of agent
            capacity: Processing capacity (0.0 to 1.0)

        Returns:
            True if registered successfully
        """
        try:
            agent_status = AgentStatus(
                agent_id=agent_id, agent_type=agent_type, status="idle", processing_capacity=capacity
            )

            self.agents[agent_id] = agent_status
            self.agent_assignments[agent_id] = set()

            # Create agent-specific queue if using Redis coordination
            if self.coordination_mode == "redis":
                queue_name = self.get_agent_queue_name(agent_id, agent_type)
                # Queue is created automatically when first message is enqueued

            self.logger.info(f"Registered agent {agent_id} ({agent_type.value}) with capacity {capacity}")

            # Send welcome message
            await self._send_agent_message(
                agent_id,
                AgentMessage(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    message_type="registration_confirmed",
                    payload={"status": "registered", "coordination_mode": self.coordination_mode},
                ),
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to register agent {agent_id}: {e}")
            return False

    async def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent and handle cleanup.

        Args:
            agent_id: Agent to unregister

        Returns:
            True if unregistered successfully
        """
        try:
            if agent_id not in self.agents:
                self.logger.warning(f"Agent {agent_id} not found for unregistration")
                return False

            agent = self.agents[agent_id]

            # Handle ongoing PRPs
            assigned_prps = self.agent_assignments.get(agent_id, set())
            if assigned_prps:
                self.logger.warning(f"Agent {agent_id} has {len(assigned_prps)} assigned PRPs during unregistration")

                # Reassign PRPs to other agents
                for prp_id in assigned_prps:
                    await self._reassign_prp(prp_id, agent_id)

            # Cleanup queues if using Redis coordination
            if self.coordination_mode == "redis":
                queue_name = self.get_agent_queue_name(agent_id, agent.agent_type)
                # Move any pending messages back to workflow queues
                await self._cleanup_agent_queue(agent_id, queue_name)

            # Remove from tracking
            del self.agents[agent_id]
            del self.agent_assignments[agent_id]

            self.logger.info(f"Unregistered agent {agent_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to unregister agent {agent_id}: {e}")
            return False

    async def assign_prp_to_agent(self, prp_id: str, prp_transition: PRPTransition) -> Optional[str]:
        """
        Assign PRP to the best available agent.

        Args:
            prp_id: PRP identifier
            prp_transition: PRP transition details

        Returns:
            Assigned agent ID or None if no agent available
        """
        try:
            # Determine required agent type based on transition
            required_agent_type = self._get_required_agent_type(prp_transition)

            # Find best available agent
            best_agent = self._find_best_agent(required_agent_type)

            if not best_agent:
                self.logger.warning(f"No available agent of type {required_agent_type} for PRP {prp_id}")

                # Queue for later assignment
                await self._queue_for_assignment(prp_id, prp_transition, required_agent_type)
                return None

            # Assign PRP to agent
            self.agent_assignments[best_agent].add(prp_id)
            self.agents[best_agent].status = "busy"
            self.agents[best_agent].current_prp = prp_id

            # Send assignment message
            assignment_message = AgentMessage(
                agent_id=best_agent,
                agent_type=self.agents[best_agent].agent_type,
                message_type="prp_assignment",
                payload={
                    "prp_id": prp_id,
                    "transition": prp_transition.model_dump(),
                    "assigned_at": datetime.utcnow().isoformat(),
                },
                priority=prp_transition.priority,
                requires_response=True,
            )

            await self._send_agent_message(best_agent, assignment_message)

            # Ask-for-Questions handshake patch (PRP-1060 requirement)
            question_payload = json.dumps({
                "from": "orchestrator", 
                "prp_id": prp_id,
                "question": (
                    "Please review the PRP and list ANY clarifying questions "
                    "needed before you begin coding. Respond with numbered bullets."
                )
            })
            self.broker.redis.lpush("questions:orchestrator", question_payload)

            self.logger.info(f"Assigned PRP {prp_id} to agent {best_agent}")
            return best_agent

        except Exception as e:
            self.logger.error(f"Failed to assign PRP {prp_id}: {e}")
            return None

    def _get_required_agent_type(self, prp_transition: PRPTransition) -> AgentType:
        """Determine required agent type for PRP transition"""
        if prp_transition.to_state == PRPState.VALIDATED:
            return AgentType.VALIDATOR
        elif prp_transition.to_state == PRPState.IN_PROGRESS:
            if "integration" in prp_transition.transition_data.get("work_type", ""):
                return AgentType.INTEGRATOR
            else:
                return AgentType.PM
        elif prp_transition.to_state == PRPState.COMPLETE:
            return AgentType.VALIDATOR
        else:
            return AgentType.PM  # Default

    def _find_best_agent(self, agent_type: AgentType) -> Optional[str]:
        """Find best available agent of specified type"""
        available_agents = [
            (agent_id, agent)
            for agent_id, agent in self.agents.items()
            if agent.agent_type == agent_type and agent.status in ["idle", "active"]
        ]

        if not available_agents:
            return None

        # Sort by capacity and current load
        available_agents.sort(key=lambda x: (x[1].processing_capacity, -x[1].queue_backlog), reverse=True)

        return available_agents[0][0]

    async def _queue_for_assignment(self, prp_id: str, prp_transition: PRPTransition, required_agent_type: AgentType):
        """Queue PRP for later assignment when agent becomes available"""
        queue_name = f"pending_{required_agent_type.value}_assignments"

        assignment_request = {
            "prp_id": prp_id,
            "transition": prp_transition.model_dump(),
            "required_agent_type": required_agent_type.value,
            "queued_at": datetime.utcnow().isoformat(),
        }

        self.broker.enqueue(queue_name, assignment_request, priority=prp_transition.priority)

    async def complete_prp_assignment(self, agent_id: str, prp_id: str, completion_data: Dict[str, Any]) -> bool:
        """
        Complete PRP assignment and update agent status.

        Args:
            agent_id: Agent completing the PRP
            prp_id: PRP identifier
            completion_data: Completion details

        Returns:
            True if completed successfully
        """
        try:
            if agent_id not in self.agents:
                self.logger.error(f"Agent {agent_id} not found for PRP completion")
                return False

            if prp_id not in self.agent_assignments.get(agent_id, set()):
                self.logger.error(f"PRP {prp_id} not assigned to agent {agent_id}")
                return False

            # Update agent status
            self.agent_assignments[agent_id].remove(prp_id)

            if not self.agent_assignments[agent_id]:
                self.agents[agent_id].status = "idle"
                self.agents[agent_id].current_prp = None
            else:
                # Agent has other assignments
                next_prp = next(iter(self.agent_assignments[agent_id]))
                self.agents[agent_id].current_prp = next_prp

            self.logger.info(f"Agent {agent_id} completed PRP {prp_id}")

            # Check for pending assignments
            await self._process_pending_assignments(self.agents[agent_id].agent_type)

            return True

        except Exception as e:
            self.logger.error(f"Failed to complete PRP assignment: {e}")
            return False

    async def _process_pending_assignments(self, agent_type: AgentType):
        """Process pending assignments for agent type"""
        queue_name = f"pending_{agent_type.value}_assignments"

        # Check for pending assignments
        pending_messages = []
        for _ in range(10):  # Process up to 10 pending assignments
            result = self.broker.dequeue([queue_name], timeout=0.1)
            if result:
                queue_name_result, message = result
                pending_messages.append(message)
            else:
                break

        for message in pending_messages:
            assignment_data = message.payload
            prp_transition = PRPTransition.model_validate(assignment_data["transition"])

            assigned_agent = await self.assign_prp_to_agent(assignment_data["prp_id"], prp_transition)

            if not assigned_agent:
                # Re-queue if still no agent available
                self.broker.enqueue(queue_name, assignment_data, priority=prp_transition.priority)

    async def _send_agent_message(self, agent_id: str, message: AgentMessage) -> bool:
        """Send message to agent via appropriate channel"""
        try:
            if self.coordination_mode == "redis":
                # Use Redis queue for reliable delivery
                queue_name = self.get_agent_queue_name(agent_id, message.agent_type)
                message_id = self.broker.enqueue(queue_name, message.model_dump(), priority=message.priority)
                return message_id is not None

            elif self.coordination_mode == "tmux":
                # Fall back to existing tmux messaging (backward compatibility)
                return await self._send_tmux_message(agent_id, message)

            else:
                self.logger.error(f"Unknown coordination mode: {self.coordination_mode}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to send message to agent {agent_id}: {e}")
            return False

    async def _send_tmux_message(self, agent_id: str, message: AgentMessage) -> bool:
        """Send message via tmux (backward compatibility)"""
        try:
            # Import existing Redis message bus for tmux compatibility
            from redis_message_bus import RedisMessageBus

            bus = RedisMessageBus()

            # Format message for tmux compatibility
            tmux_message = f"[{message.message_type}] {json.dumps(message.payload)}"

            result = bus.publish_to_agent(agent_id, tmux_message, priority="high" if message.priority > 5 else "normal")
            return result > 0

        except Exception as e:
            self.logger.error(f"Failed to send tmux message: {e}")
            return False

    async def _cleanup_agent_queue(self, agent_id: str, queue_name: str) -> int:
        """Clean up agent queue during unregistration"""
        moved_count = 0

        try:
            # Move messages back to workflow queues
            while True:
                result = self.broker.dequeue([queue_name], timeout=0.1)
                if not result:
                    break

                _, message = result
                message_data = message.payload

                if isinstance(message_data, dict) and "message_type" in message_data:
                    # Route to appropriate workflow queue
                    workflow_queue = self._get_workflow_queue_for_message(message_data)
                    self.broker.enqueue(workflow_queue, message_data)
                    moved_count += 1

            if moved_count > 0:
                self.logger.info(f"Moved {moved_count} messages from {agent_id} queue to workflow queues")

        except Exception as e:
            self.logger.error(f"Error cleaning up agent queue: {e}")

        return moved_count

    def _get_workflow_queue_for_message(self, message_data: Dict[str, Any]) -> str:
        """Determine appropriate workflow queue for message"""
        message_type = message_data.get("message_type", "")

        if "prp" in message_type:
            return self.get_workflow_queue_name("prp_development")
        elif "validation" in message_type:
            return self.get_workflow_queue_name("prp_validation")
        elif "integration" in message_type:
            return self.get_workflow_queue_name("prp_integration")
        else:
            return self.get_workflow_queue_name("coordination")

    async def update_agent_heartbeat(self, agent_id: str, status: Optional[str] = None) -> bool:
        """Update agent heartbeat and status"""
        try:
            if agent_id not in self.agents:
                self.logger.warning(f"Heartbeat from unregistered agent {agent_id}")
                return False

            self.agents[agent_id].last_heartbeat = datetime.utcnow()

            if status:
                self.agents[agent_id].status = status

            return True

        except Exception as e:
            self.logger.error(f"Failed to update heartbeat for agent {agent_id}: {e}")
            return False

    async def check_agent_health(self) -> Dict[str, Any]:
        """Check health of all registered agents"""
        health_status = {
            "total_agents": len(self.agents),
            "healthy_agents": 0,
            "unhealthy_agents": 0,
            "agent_details": {},
        }

        current_time = datetime.utcnow()
        heartbeat_timeout = timedelta(minutes=5)  # 5 minute timeout

        for agent_id, agent in self.agents.items():
            time_since_heartbeat = current_time - agent.last_heartbeat
            is_healthy = time_since_heartbeat < heartbeat_timeout

            if is_healthy:
                health_status["healthy_agents"] += 1
            else:
                health_status["unhealthy_agents"] += 1

            health_status["agent_details"][agent_id] = {
                "agent_type": agent.agent_type.value,
                "status": agent.status,
                "healthy": is_healthy,
                "last_heartbeat": agent.last_heartbeat.isoformat(),
                "assigned_prps": len(self.agent_assignments.get(agent_id, set())),
                "queue_backlog": agent.queue_backlog,
            }

        return health_status

    async def _reassign_prp(self, prp_id: str, failed_agent_id: str) -> bool:
        """Reassign PRP from failed agent to another agent"""
        try:
            # Create a basic transition for reassignment
            prp_transition = PRPTransition(
                prp_id=prp_id,
                from_state=PRPState.IN_PROGRESS,
                to_state=PRPState.IN_PROGRESS,  # Keep same state, just reassign
                agent_id=failed_agent_id,
                transition_data={"reassignment": True, "original_agent": failed_agent_id},
                priority=10,  # High priority for reassignments
            )

            new_agent = await self.assign_prp_to_agent(prp_id, prp_transition)

            if new_agent:
                self.logger.info(f"Reassigned PRP {prp_id} from {failed_agent_id} to {new_agent}")
                return True
            else:
                self.logger.error(f"Failed to reassign PRP {prp_id} from {failed_agent_id}")
                return False

        except Exception as e:
            self.logger.error(f"Error reassigning PRP {prp_id}: {e}")
            return False


# Global coordinator instance (lazy initialization)
_coordinator_instance: Optional[AgentCoordinator] = None


def get_agent_coordinator() -> AgentCoordinator:
    """Get global agent coordinator instance"""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = AgentCoordinator()
    return _coordinator_instance


def reset_agent_coordinator():
    """Reset global coordinator instance (mainly for testing)"""
    global _coordinator_instance
    _coordinator_instance = None


async def coordination_worker(coordinator: AgentCoordinator, queue_names: List[str]):
    """
    Background worker for processing coordination messages.

    Args:
        coordinator: Agent coordinator instance
        queue_names: List of queue names to monitor
    """
    logger = get_logger("coordination_worker", domain="infra")

    async with queue_worker_context(coordinator.broker) as pattern:
        logger.info(f"Starting coordination worker for queues: {queue_names}")

        while True:
            try:
                # Process messages from coordination queues
                result = coordinator.broker.dequeue(queue_names, timeout=5.0)

                if result:
                    queue_name, message = result

                    # Process coordination message
                    success = await _process_coordination_message(coordinator, queue_name, message)

                    if success:
                        coordinator.broker.acknowledge(queue_name, message)
                    else:
                        coordinator.broker.nack(queue_name, message, "processing_failed")

                # Process scheduled retries
                for queue_name in queue_names:
                    await coordinator.dlq.process_scheduled_retries(queue_name)

            except Exception as e:
                logger.error(f"Error in coordination worker: {e}")
                await asyncio.sleep(1)  # Brief pause on error


async def _process_coordination_message(coordinator: AgentCoordinator, queue_name: str, message: QueueMessage) -> bool:
    """Process coordination message"""
    try:
        payload = message.payload
        message_type = payload.get("message_type")

        if message_type == "prp_assignment":
            prp_id = payload.get("prp_id")
            prp_transition = PRPTransition.model_validate(payload.get("transition"))

            assigned_agent = await coordinator.assign_prp_to_agent(prp_id, prp_transition)
            return assigned_agent is not None

        elif message_type == "agent_heartbeat":
            agent_id = payload.get("agent_id")
            status = payload.get("status")

            return await coordinator.update_agent_heartbeat(agent_id, status)

        elif message_type == "prp_completion":
            agent_id = payload.get("agent_id")
            prp_id = payload.get("prp_id")
            completion_data = payload.get("completion_data", {})

            return await coordinator.complete_prp_assignment(agent_id, prp_id, completion_data)

        else:
            coordinator.logger.warning(f"Unknown coordination message type: {message_type}")
            return False

    except Exception as e:
        coordinator.logger.error(f"Error processing coordination message: {e}")
        return False
