"""
Agent Base Class for Kimi K2.5 Swarm
=====================================

Base class for all agents in the swarm with:
- Capability-based access control
- PARL integration for parallel execution
- State management
- Inter-agent communication
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent lifecycle states."""

    INITIALIZING = "initializing"
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


class CapabilityScope(Enum):
    """Scope of agent capability."""

    LOCAL = "local"  # Single node
    REGIONAL = "regional"  # Up to 100 nodes
    NETWORK = "network"  # All nodes


@dataclass
class AgentCapability:
    """Represents a specific capability for an agent."""

    name: str
    scope: CapabilityScope = CapabilityScope.LOCAL
    max_affected_nodes: int = 1
    max_affected_percentage: float = 0.01
    effective_until: Optional[float] = None
    required_approvals: List[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        """Check if capability is still valid."""
        if self.effective_until is None:
            return True
        return time.time() < self.effective_until

    def allows_nodes(self, node_count: int, network_size: int) -> bool:
        """Check if capability permits affecting this many nodes."""
        percentage = node_count / max(network_size, 1)
        return (
            node_count <= self.max_affected_nodes
            and percentage <= self.max_affected_percentage
        )


@dataclass
class AgentMessage:
    """Message for inter-agent communication."""

    message_id: str = field(default_factory=lambda: str(uuid4()))
    sender_id: str = ""
    recipient_id: str = ""  # Empty for broadcast
    message_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 5


@dataclass
class TaskResult:
    """Result of task execution."""

    task_id: str = ""
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    agent_id: str = ""


class Agent:
    """
    Base class for swarm agents.

    Each agent can:
    - Execute tasks independently
    - Communicate with other agents
    - Report metrics and status
    - Participate in PARL parallel execution

    Example:
        >>> agent = Agent(
        ...     agent_id="agent_001",
        ...     swarm_id="swarm_abc",
        ...     capabilities=[AgentCapability(name="monitoring")]
        ... )
        >>> await agent.initialize()
        >>> result = await agent.execute_task(task)
    """

    def __init__(
        self,
        agent_id: str,
        swarm_id: str,
        capabilities: List[AgentCapability],
        parl_controller: Optional[Any] = None,
    ):
        self.agent_id = agent_id
        self.swarm_id = swarm_id
        self.capabilities = {cap.name: cap for cap in capabilities}
        self.parl_controller = parl_controller

        self.state = AgentState.INITIALIZING
        self.created_at = time.time()
        self.last_activity = time.time()

        # Task tracking
        self.current_task: Optional[str] = None
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_execution_time = 0.0

        # Communication
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._message_handler_task: Optional[asyncio.Task] = None

        # Metrics
        self.metrics = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_execution_time_ms": 0.0,
            "success_rate": 1.0,
        }

        # Control
        self._running = False
        self._paused = False

        logger.debug(f"Agent created: {agent_id}")

    async def initialize(self) -> None:
        """Initialize the agent."""
        self._running = True
        self.state = AgentState.IDLE

        # Start message handler
        self._message_handler_task = asyncio.create_task(self._message_handler())

        logger.debug(f"Agent initialized: {self.agent_id}")

    async def execute_task(self, task: Dict[str, Any]) -> TaskResult:
        """
        Execute a task.

        Args:
            task: Task specification with 'task_type' and 'payload'

        Returns:
            TaskResult with execution results
        """
        start_time = time.time()
        task_id = task.get("task_id", str(uuid4()))

        self.state = AgentState.ACTIVE
        self.current_task = task_id
        self.last_activity = time.time()

        try:
            # Check capability
            task_type = task.get("task_type", "")
            if not self.has_capability(task_type):
                raise PermissionError(f"Agent lacks capability: {task_type}")

            # Execute task
            result = await self._execute_task_internal(task)

            # Update metrics
            execution_time = (time.time() - start_time) * 1000
            self.completed_tasks += 1
            self.total_execution_time += execution_time
            self._update_metrics()

            self.state = AgentState.IDLE
            self.current_task = None

            return TaskResult(
                task_id=task_id,
                success=True,
                result=result,
                execution_time_ms=execution_time,
                agent_id=self.agent_id,
            )

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            self.failed_tasks += 1
            self.state = AgentState.ERROR
            self._update_metrics()

            return TaskResult(
                task_id=task_id,
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
                agent_id=self.agent_id,
            )

    async def _execute_task_internal(self, task: Dict[str, Any]) -> Any:
        """Internal task execution - override in subclasses."""
        task_type = task.get("task_type")
        payload = task.get("payload", {})

        # Default implementations for common task types
        if task_type == "monitoring":
            return await self._execute_monitoring(payload)
        elif task_type == "analysis":
            return await self._execute_analysis(payload)
        elif task_type == "optimization":
            return await self._execute_optimization(payload)
        elif task_type == "route_optimization":
            return await self._execute_route_optimization(payload)
        else:
            # Generic task - simulate work
            await asyncio.sleep(0.1)
            return {"status": "completed", "task_type": task_type}

    async def _execute_monitoring(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute monitoring task."""
        node_id = payload.get("node_id", "unknown")
        # Simulate monitoring
        await asyncio.sleep(0.05)
        return {
            "node_id": node_id,
            "status": "healthy",
            "metrics": {"cpu": 45.2, "memory": 62.1, "latency": 23},
        }

    async def _execute_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute analysis task."""
        data = payload.get("data", {})
        # Simulate analysis
        await asyncio.sleep(0.15)
        return {"anomalies_detected": 0, "confidence": 0.95, "recommendations": []}

    async def _execute_optimization(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute optimization task."""
        target = payload.get("target", "")
        # Simulate optimization
        await asyncio.sleep(0.2)
        return {"target": target, "improvement": 0.15, "new_config": {}}

    async def _execute_route_optimization(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute route optimization task."""
        source = payload.get("source_node", "")
        target = payload.get("target_node", "")
        # Simulate route optimization
        await asyncio.sleep(0.1)
        return {
            "source": source,
            "target": target,
            "optimal_route": [source, "node_intermediate", target],
            "estimated_latency_ms": 45,
            "bandwidth_mbps": 150,
        }

    def has_capability(self, capability_name: str) -> bool:
        """Check if agent has a specific capability."""
        cap = self.capabilities.get(capability_name)
        if not cap:
            return False
        return cap.is_valid()

    async def send_message(self, message: AgentMessage) -> None:
        """Send a message to another agent or broadcast."""
        message.sender_id = self.agent_id
        # In real implementation, this would route through swarm orchestrator
        logger.debug(f"Message sent: {message.message_type}")

    async def _message_handler(self) -> None:
        """Handle incoming messages."""
        while self._running:
            try:
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._process_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Message handling error: {e}")

    async def _process_message(self, message: AgentMessage) -> None:
        """Process incoming message."""
        logger.debug(f"Processing message: {message.message_type}")

        if message.message_type == "pause":
            self._paused = True
            self.state = AgentState.PAUSED
        elif message.message_type == "resume":
            self._paused = False
            self.state = AgentState.IDLE
        elif message.message_type == "terminate":
            await self.terminate()

    def _update_metrics(self) -> None:
        """Update agent metrics."""
        total = self.completed_tasks + self.failed_tasks
        if total > 0:
            self.metrics["success_rate"] = self.completed_tasks / total
            self.metrics["avg_execution_time_ms"] = self.total_execution_time / total
        self.metrics["tasks_completed"] = self.completed_tasks
        self.metrics["tasks_failed"] = self.failed_tasks

    def get_status(self) -> Dict[str, Any]:
        """Get agent status."""
        return {
            "agent_id": self.agent_id,
            "swarm_id": self.swarm_id,
            "state": self.state.value,
            "capabilities": list(self.capabilities.keys()),
            "current_task": self.current_task,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
        }

    async def pause(self) -> None:
        """Pause agent execution."""
        self._paused = True
        self.state = AgentState.PAUSED
        logger.debug(f"Agent paused: {self.agent_id}")

    async def resume(self) -> None:
        """Resume agent execution."""
        self._paused = False
        self.state = AgentState.IDLE
        logger.debug(f"Agent resumed: {self.agent_id}")

    async def terminate(self) -> None:
        """Terminate the agent."""
        logger.debug(f"Terminating agent: {self.agent_id}")
        self.state = AgentState.TERMINATING
        self._running = False

        # Cancel message handler
        if self._message_handler_task:
            self._message_handler_task.cancel()
            try:
                await self._message_handler_task
            except asyncio.CancelledError:
                pass

        self.state = AgentState.TERMINATED
        logger.debug(f"Agent terminated: {self.agent_id}")


class SpecializedAgent(Agent):
    """Specialized agent with specific capabilities."""

    def __init__(self, agent_id: str, swarm_id: str, specialization: str, **kwargs):
        capabilities = self._get_capabilities_for_specialization(specialization)
        super().__init__(agent_id, swarm_id, capabilities, **kwargs)
        self.specialization = specialization

    def _get_capabilities_for_specialization(
        self, specialization: str
    ) -> List[AgentCapability]:
        """Get default capabilities for specialization."""
        capabilities_map = {
            "monitoring": [
                AgentCapability(name="monitoring", scope=CapabilityScope.REGIONAL),
                AgentCapability(name="metrics_collection", scope=CapabilityScope.LOCAL),
            ],
            "analysis": [
                AgentCapability(name="analysis", scope=CapabilityScope.REGIONAL),
                AgentCapability(
                    name="anomaly_detection", scope=CapabilityScope.NETWORK
                ),
            ],
            "optimization": [
                AgentCapability(name="optimization", scope=CapabilityScope.NETWORK),
                AgentCapability(
                    name="route_optimization", scope=CapabilityScope.NETWORK
                ),
            ],
            "coordination": [
                AgentCapability(
                    name="task_distribution", scope=CapabilityScope.NETWORK
                ),
                AgentCapability(
                    name="result_aggregation", scope=CapabilityScope.NETWORK
                ),
            ],
        }
        return capabilities_map.get(
            specialization, [AgentCapability(name="task_execution")]
        )


# Factory function
def create_agent(
    agent_id: str, swarm_id: str, specialization: Optional[str] = None, **kwargs
) -> Agent:
    """Create an agent with optional specialization."""
    if specialization:
        return SpecializedAgent(agent_id, swarm_id, specialization, **kwargs)
    return Agent(agent_id, swarm_id, [AgentCapability(name="task_execution")], **kwargs)
