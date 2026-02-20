"""
PARL Agent Worker - Executes tasks in parallel mode

Each worker maintains a local copy of the global policy and executes
tasks asynchronously, collecting experience for policy updates.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from datetime import datetime, timezone

from src.parl.types import (
    Task, TaskId, Experience, Policy, StepResult,
    WorkerId, WorkerState
)

logger = logging.getLogger(__name__)


@dataclass
class WorkerMetrics:
    """Metrics for an individual worker."""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_execution_time_ms: float = 0.0
    avg_latency_ms: float = 0.0
    experiences_collected: int = 0
    last_task_time: float = 0.0
    
    def update_latency(self, latency_ms: float) -> None:
        """Update average latency with new measurement."""
        if self.tasks_completed == 0:
            self.avg_latency_ms = latency_ms
        else:
            # Exponential moving average
            self.avg_latency_ms = 0.9 * self.avg_latency_ms + 0.1 * latency_ms


class AgentWorker:
    """
    Agent Worker for parallel task execution.
    
    Each worker:
    - Maintains a local copy of the global policy
    - Executes tasks asynchronously
    - Collects local experience
    - Communicates with the controller
    
    Usage:
        worker = AgentWorker(
            worker_id="worker_001",
            policy=global_policy,
            on_experience=collect_experience_callback
        )
        asyncio.create_task(worker.run())
        
        # Submit task
        result = await worker.execute_step(task)
        
        # Sync policy
        await worker.sync_policy(new_policy)
        
        # Terminate
        await worker.terminate()
    """
    
    def __init__(
        self,
        worker_id: WorkerId,
        policy: Policy,
        on_experience: Optional[Callable[[Experience], None]] = None,
        capabilities: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize Agent Worker.
        
        Args:
            worker_id: Unique worker identifier
            policy: Initial policy to use
            on_experience: Callback for experience collection
            capabilities: Worker capabilities (e.g., supported task types)
        """
        self.worker_id = worker_id
        self._local_policy = policy
        self._on_experience = on_experience
        self._capabilities = capabilities or {"task_types": ["*"]}
        
        # State
        self._state = WorkerState.IDLE
        self._current_task: Optional[Task] = None
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._result_futures: Dict[TaskId, asyncio.Future] = {}
        
        # Metrics
        self._metrics = WorkerMetrics()
        
        # Control
        self._running = False
        self._paused = False
        self._terminated = False
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> WorkerState:
        """Get current worker state."""
        return self._state
    
    @property
    def policy(self) -> Policy:
        """Get current local policy."""
        return self._local_policy
    
    @property
    def current_task(self) -> Optional[Task]:
        """Get currently executing task."""
        return self._current_task
    
    @property
    def capabilities(self) -> Dict[str, Any]:
        """Get worker capabilities."""
        return self._capabilities
    
    async def run(self) -> None:
        """
        Main worker loop.
        
        Continuously processes tasks from the queue.
        """
        if self._running:
            logger.warning(f"Worker {self.worker_id} already running")
            return
        
        self._running = True
        self._state = WorkerState.IDLE
        logger.info(f"Worker {self.worker_id} started")
        
        while not self._terminated:
            try:
                # Check if paused
                if self._paused:
                    self._state = WorkerState.PAUSED
                    await asyncio.sleep(0.1)
                    continue
                
                # Wait for task with timeout
                try:
                    task, future = await asyncio.wait_for(
                        self._task_queue.get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No task available, continue loop
                    continue
                
                # Execute task
                self._state = WorkerState.BUSY
                self._current_task = task
                
                result = await self._execute_task(task)
                
                # Set result
                if not future.done():
                    future.set_result(result)
                
                # Update metrics
                self._current_task = None
                self._state = WorkerState.IDLE
                
            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                self._state = WorkerState.ERROR
                await asyncio.sleep(1.0)  # Backoff
                self._state = WorkerState.IDLE
        
        self._running = False
        logger.info(f"Worker {self.worker_id} stopped")
    
    async def submit_task(self, task: Task, future: asyncio.Future) -> None:
        """
        Submit a task for execution.
        
        Args:
            task: Task to execute
            future: Future to set result on
        """
        if self._terminated:
            raise RuntimeError(f"Worker {self.worker_id} is terminated")
        
        await self._task_queue.put((task, future))
        logger.debug(f"Task {task.task_id} queued on worker {self.worker_id}")
    
    async def execute_step(self, task: Task) -> StepResult:
        """
        Execute a single task step.
        
        This is a direct execution method without queuing.
        
        Args:
            task: Task to execute
            
        Returns:
            Step result
        """
        async with self._lock:
            self._state = WorkerState.BUSY
            self._current_task = task
            
            result = await self._execute_task(task)
            
            self._current_task = None
            self._state = WorkerState.IDLE
            
            return result
    
    async def sync_policy(self, global_policy: Policy) -> None:
        """
        Synchronize local policy with global policy.
        
        Args:
            global_policy: New global policy to adopt
        """
        async with self._lock:
            self._local_policy = global_policy
            logger.debug(
                f"Worker {self.worker_id} synced policy to version {global_policy.version}"
            )
    
    async def pause(self) -> None:
        """Pause worker execution."""
        self._paused = True
        logger.info(f"Worker {self.worker_id} paused")
    
    async def resume(self) -> None:
        """Resume worker execution."""
        self._paused = False
        self._state = WorkerState.IDLE
        logger.info(f"Worker {self.worker_id} resumed")
    
    async def terminate(self) -> None:
        """Terminate the worker."""
        self._terminated = True
        self._state = WorkerState.TERMINATED
        logger.info(f"Worker {self.worker_id} terminated")
    
    def get_status(self) -> Dict[str, Any]:
        """Get worker status."""
        return {
            "worker_id": self.worker_id,
            "state": self._state.value,
            "current_task": self._current_task.task_id if self._current_task else None,
            "policy_version": self._local_policy.version,
            "tasks_completed": self._metrics.tasks_completed,
            "tasks_failed": self._metrics.tasks_failed,
            "avg_latency_ms": self._metrics.avg_latency_ms,
            "queue_size": self._task_queue.qsize(),
            "capabilities": self._capabilities,
        }
    
    def get_metrics(self) -> WorkerMetrics:
        """Get worker metrics."""
        return self._metrics
    
    # --- Internal methods ---
    
    async def _execute_task(self, task: Task) -> StepResult:
        """
        Execute a task and return result.
        
        Args:
            task: Task to execute
            
        Returns:
            Step result with execution details
        """
        start_time = time.time()
        
        try:
            # Check capabilities
            if not self._can_execute(task):
                return StepResult(
                    task_id=task.task_id,
                    success=False,
                    error=f"Worker cannot execute task type: {task.task_type}",
                    worker_id=self.worker_id,
                )
            
            # Execute based on task type
            result_data = await self._execute_by_type(task)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Create experience
            experience = self._create_experience(task, result_data, latency_ms)
            
            # Collect experience
            if self._on_experience and experience:
                self._on_experience(experience)
                self._metrics.experiences_collected += 1
            
            # Update metrics
            self._metrics.tasks_completed += 1
            self._metrics.total_execution_time_ms += latency_ms
            self._metrics.update_latency(latency_ms)
            self._metrics.last_task_time = time.time()
            
            return StepResult(
                task_id=task.task_id,
                success=True,
                result=result_data,
                latency_ms=latency_ms,
                worker_id=self.worker_id,
            )
            
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.tasks_failed += 1
            
            return StepResult(
                task_id=task.task_id,
                success=False,
                error="Task timeout",
                latency_ms=latency_ms,
                worker_id=self.worker_id,
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._metrics.tasks_failed += 1
            logger.error(f"Worker {self.worker_id} task {task.task_id} failed: {e}")
            
            return StepResult(
                task_id=task.task_id,
                success=False,
                error=str(e),
                latency_ms=latency_ms,
                worker_id=self.worker_id,
            )
    
    def _can_execute(self, task: Task) -> bool:
        """Check if worker can execute the task."""
        allowed_types = self._capabilities.get("task_types", ["*"])
        return "*" in allowed_types or task.task_type in allowed_types
    
    async def _execute_by_type(self, task: Task) -> Dict[str, Any]:
        """
        Execute task based on type.
        
        This is a dispatcher for different task types.
        
        Args:
            task: Task to execute
            
        Returns:
            Task result data
        """
        task_type = task.task_type
        payload = task.payload
        timeout = task.timeout_seconds
        
        # Task type handlers
        handlers = {
            "mesh_analysis": self._handle_mesh_analysis,
            "anomaly_detection": self._handle_anomaly_detection,
            "route_optimization": self._handle_route_optimization,
            "policy_evaluation": self._handle_policy_evaluation,
            "data_processing": self._handle_data_processing,
            "health_check": self._handle_health_check,
        }
        
        handler = handlers.get(task_type, self._handle_generic)
        
        try:
            result = await asyncio.wait_for(
                handler(payload),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            raise
    
    async def _handle_mesh_analysis(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle mesh analysis task."""
        # Simulate mesh analysis
        await asyncio.sleep(0.01)  # Simulated work
        
        return {
            "analysis_type": "mesh",
            "nodes_analyzed": payload.get("node_count", 0),
            "anomalies_found": 0,
            "status": "completed",
        }
    
    async def _handle_anomaly_detection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle anomaly detection task."""
        # Simulate anomaly detection
        await asyncio.sleep(0.02)  # Simulated work
        
        metrics = payload.get("metrics", {})
        
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "metrics_checked": len(metrics),
            "status": "completed",
        }
    
    async def _handle_route_optimization(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle route optimization task."""
        # Simulate route optimization
        await asyncio.sleep(0.05)  # Simulated work
        
        return {
            "routes_optimized": payload.get("route_count", 0),
            "improvement_percent": 0.0,
            "status": "completed",
        }
    
    async def _handle_policy_evaluation(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle policy evaluation task."""
        # Simulate policy evaluation
        await asyncio.sleep(0.01)
        
        return {
            "policy_version": self._local_policy.version,
            "evaluation_score": 0.0,
            "status": "completed",
        }
    
    async def _handle_data_processing(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data processing task."""
        # Simulate data processing
        data_size = payload.get("data_size", 0)
        await asyncio.sleep(0.001 * data_size)  # Simulated work
        
        return {
            "records_processed": data_size,
            "status": "completed",
        }
    
    async def _handle_health_check(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle health check task."""
        return {
            "worker_id": self.worker_id,
            "state": self._state.value,
            "tasks_completed": self._metrics.tasks_completed,
            "avg_latency_ms": self._metrics.avg_latency_ms,
            "status": "healthy",
        }
    
    async def _handle_generic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle generic/unknown task type."""
        # Simulate generic work
        await asyncio.sleep(0.01)
        
        return {
            "task_type": "generic",
            "status": "completed",
        }
    
    def _create_experience(
        self, 
        task: Task, 
        result: Dict[str, Any], 
        latency_ms: float
    ) -> Optional[Experience]:
        """
        Create experience tuple from task execution.
        
        Args:
            task: Executed task
            result: Task result
            latency_ms: Execution latency
            
        Returns:
            Experience tuple or None
        """
        # Create state representation
        state = {
            "task_type": task.task_type,
            "priority": task.priority,
            "payload_size": len(str(task.payload)),
        }
        
        # Action is the task execution
        action = {
            "execute": True,
            "worker_id": self.worker_id,
        }
        
        # Reward based on success and latency
        success = result.get("status") == "completed"
        base_reward = 1.0 if success else -1.0
        
        # Latency penalty (normalized)
        latency_penalty = min(latency_ms / 1000.0, 1.0)  # Max 1 second
        reward = base_reward - latency_penalty * 0.1
        
        # Next state (simplified)
        next_state = {
            "completed": success,
            "result_type": result.get("status", "unknown"),
        }
        
        return Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=True,  # Each task is a complete episode
            task_id=task.task_id,
            worker_id=self.worker_id,
        )
    
    def __repr__(self) -> str:
        return f"AgentWorker(id={self.worker_id}, state={self._state.value})"