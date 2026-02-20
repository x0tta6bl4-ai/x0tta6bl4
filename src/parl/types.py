"""
PARL Type Definitions

Core types for Parallel-Agent Reinforcement Learning.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import uuid
import time


# Type aliases
TaskId = str
WorkerId = str


class TaskPriority(int, Enum):
    """Task priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 5
    LOW = 8
    BACKGROUND = 10


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class WorkerState(str, Enum):
    """Worker state."""
    IDLE = "idle"
    BUSY = "busy"
    PAUSED = "paused"
    TERMINATED = "terminated"
    ERROR = "error"


@dataclass
class Task:
    """
    Task for parallel execution.
    
    Attributes:
        task_type: Type of task (e.g., 'mesh_analysis', 'anomaly_detection')
        payload: Task-specific data
        priority: Task priority (1-10, lower is higher priority)
        timeout_seconds: Maximum execution time
        task_id: Unique task identifier
        created_at: Task creation timestamp
        dependencies: List of task IDs that must complete first
        metadata: Additional task metadata
    """
    task_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = TaskPriority.NORMAL
    timeout_seconds: float = 30.0
    task_id: TaskId = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    created_at: float = field(default_factory=time.time)
    dependencies: List[TaskId] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other: "Task") -> bool:
        """Compare tasks by priority for priority queue."""
        return self.priority < other.priority


@dataclass
class StepResult:
    """
    Result of a single execution step.
    
    Attributes:
        task_id: ID of the executed task
        success: Whether the step succeeded
        result: Step result data
        error: Error message if failed
        latency_ms: Execution latency in milliseconds
        worker_id: ID of the worker that executed the step
        timestamp: Execution timestamp
    """
    task_id: TaskId
    success: bool
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: float = 0.0
    worker_id: Optional[WorkerId] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Experience:
    """
    Experience tuple for reinforcement learning.
    
    Represents a single transition: state -> action -> reward -> next_state
    
    Attributes:
        state: Current state observation
        action: Action taken
        reward: Reward received
        next_state: Resulting state
        done: Whether episode is complete
        info: Additional information
        task_id: Associated task ID
        worker_id: Worker that generated this experience
        timestamp: When experience was collected
    """
    state: Dict[str, Any]
    action: Dict[str, Any]
    reward: float
    next_state: Dict[str, Any]
    done: bool = False
    info: Dict[str, Any] = field(default_factory=dict)
    task_id: Optional[TaskId] = None
    worker_id: Optional[WorkerId] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Policy:
    """
    Policy for agent behavior.
    
    Contains the policy network parameters and metadata.
    
    Attributes:
        policy_id: Unique policy identifier
        version: Policy version number
        parameters: Policy parameters (e.g., neural network weights)
        created_at: Policy creation timestamp
        metrics: Performance metrics for this policy
        metadata: Additional metadata
    """
    policy_id: str = field(default_factory=lambda: f"policy_{uuid.uuid4().hex[:8]}")
    version: int = 1
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    metrics: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_version(self) -> "Policy":
        """Create a new version of this policy."""
        return Policy(
            policy_id=self.policy_id,
            version=self.version + 1,
            parameters=self.parameters.copy(),
            created_at=time.time(),
            metrics={},
            metadata=self.metadata.copy(),
        )


@dataclass
class PARLMetrics:
    """
    Performance metrics for PARL system.
    
    Attributes:
        active_workers: Number of currently active workers
        idle_workers: Number of idle workers
        queued_tasks: Number of tasks in queue
        running_tasks: Number of currently running tasks
        completed_tasks: Total completed tasks
        failed_tasks: Total failed tasks
        avg_task_latency_ms: Average task latency
        throughput_tps: Tasks per second throughput
        policy_update_time_ms: Time for last policy update
        worker_utilization: Worker utilization ratio (0-1)
        parallelism_ratio: Actual parallelism achieved
        speedup_factor: Speedup vs sequential execution
    """
    active_workers: int = 0
    idle_workers: int = 0
    queued_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_task_latency_ms: float = 0.0
    throughput_tps: float = 0.0
    policy_update_time_ms: float = 0.0
    worker_utilization: float = 0.0
    parallelism_ratio: float = 1.0
    speedup_factor: float = 1.0
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "active_workers": self.active_workers,
            "idle_workers": self.idle_workers,
            "queued_tasks": self.queued_tasks,
            "running_tasks": self.running_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_task_latency_ms": self.avg_task_latency_ms,
            "throughput_tps": self.throughput_tps,
            "policy_update_time_ms": self.policy_update_time_ms,
            "worker_utilization": self.worker_utilization,
            "parallelism_ratio": self.parallelism_ratio,
            "speedup_factor": self.speedup_factor,
            "timestamp": self.timestamp,
        }


@dataclass
class Schedule:
    """
    Task schedule produced by TaskScheduler.
    
    Attributes:
        assignments: Mapping of worker_id -> list of task_ids
        estimated_completion_time: Estimated time to complete all tasks
        total_tasks: Total number of scheduled tasks
        created_at: Schedule creation timestamp
    """
    assignments: Dict[WorkerId, List[TaskId]] = field(default_factory=dict)
    estimated_completion_time: float = 0.0
    total_tasks: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class QueueStats:
    """
    Statistics for the task queue.
    
    Attributes:
        total_tasks: Total tasks in queue
        pending_tasks: Tasks waiting to be processed
        running_tasks: Currently running tasks
        completed_tasks: Completed tasks (last hour)
        failed_tasks: Failed tasks (last hour)
        avg_wait_time_ms: Average wait time in queue
        avg_execution_time_ms: Average execution time
        queue_depth: Current queue depth
        max_queue_depth: Maximum queue depth
    """
    total_tasks: int = 0
    pending_tasks: int = 0
    running_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_wait_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    queue_depth: int = 0
    max_queue_depth: int = 10000


# PPO Configuration
@dataclass
class PPOConfig:
    """
    Proximal Policy Optimization configuration.
    
    Attributes:
        learning_rate: Learning rate for optimizer
        gamma: Discount factor
        gae_lambda: GAE lambda parameter
        clip_epsilon: PPO clipping parameter
        value_loss_coef: Value loss coefficient
        entropy_coef: Entropy bonus coefficient
        max_grad_norm: Maximum gradient norm
        num_epochs: Number of PPO epochs per update
        minibatch_size: Minibatch size for PPO
    """
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    value_loss_coef: float = 0.5
    entropy_coef: float = 0.01
    max_grad_norm: float = 0.5
    num_epochs: int = 4
    minibatch_size: int = 64
