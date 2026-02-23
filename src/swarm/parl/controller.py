"""
PARL (Parallel-Agent Reinforcement Learning) Controller
=========================================================

Implements PARL from Kimi K2.5 for parallel task execution.
- Up to 1500 parallel steps
- 4.5x speedup vs sequential execution
- PPO-based policy optimization

Key Components:
- PARLController: Central coordinator
- AgentWorker: Task executors
- TaskScheduler: Intelligent task distribution
- ExperienceBuffer: PPO training data
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.monitoring.opentelemetry_tracing import get_swarm_spans

logger = logging.getLogger(__name__)


@dataclass
class PARLConfig:
    """Configuration for PARL controller."""

    max_workers: int = 100
    max_parallel_steps: int = 1500
    batch_size: int = 64
    learning_rate: float = 3e-4
    gamma: float = 0.99
    gae_lambda: float = 0.95
    clip_epsilon: float = 0.2
    update_interval: int = 100
    experience_buffer_size: int = 100000
    # Policy update configuration
    # When True, policy updates are skipped (PPO not implemented yet)
    # Experience buffer will naturally evict oldest entries when full
    skip_policy_update: bool = True


@dataclass
class Experience:
    """Single experience for PPO training."""

    state: Dict[str, Any]
    action: int
    reward: float
    next_state: Dict[str, Any]
    done: bool
    log_prob: float
    value: float


@dataclass
class PARLMetrics:
    """PARL performance metrics."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_workers: int = 0
    queued_tasks: int = 0
    avg_task_latency_ms: float = 0.0
    throughput_tps: float = 0.0
    policy_update_count: int = 0
    worker_utilization: float = 0.0


class TaskScheduler:
    """
    Intelligent task scheduler for PARL.

    Features:
    - Priority-based scheduling
    - Load balancing across workers
    - Adaptive scoring based on worker specialization
    """

    def __init__(self, max_workers: int):
        self.max_workers = max_workers
        self.task_queue: asyncio.PriorityQueue[Any] = asyncio.PriorityQueue()
        self.worker_loads: Dict[str, int] = {}
        self.task_assignments: Dict[str, str] = {}
        self.worker_specialization: Dict[str, Dict[str, float]] = {} # type -> success_rate

    async def submit(self, task: Dict[str, Any], priority: int = 5) -> None:
        """Submit task to queue."""
        await self.task_queue.put((priority, time.time(), task))

    def get_best_worker(self, available_workers: List[str], task_type: str = "unknown") -> Optional[str]:
        """Get best worker based on load and specialization score."""
        if not available_workers:
            return None

        # Score = Load + (1 - Specialization)
        # We want lowest score
        best_worker = None
        min_score = float("inf")

        for worker_id in available_workers:
            load = self.worker_loads.get(worker_id, 0)
            spec_bonus = self.worker_specialization.get(worker_id, {}).get(task_type, 0.5)
            
            score = load + (1.0 - spec_bonus)
            
            if score < min_score:
                min_score = score
                best_worker = worker_id

        return best_worker

    def assign_task(self, task_id: str, worker_id: str) -> None:
        """Assign task to worker."""
        self.task_assignments[task_id] = worker_id
        self.worker_loads[worker_id] = self.worker_loads.get(worker_id, 0) + 1

    def complete_task(self, task_id: str, success: bool = True, task_type: str = "unknown") -> None:
        """Mark task as complete and update specialization metrics."""
        worker_id = self.task_assignments.pop(task_id, None)
        if worker_id and worker_id in self.worker_loads:
            self.worker_loads[worker_id] = max(0, self.worker_loads[worker_id] - 1)
            
            # Update specialization (moving average)
            if worker_id not in self.worker_specialization:
                self.worker_specialization[worker_id] = {}
            
            old_score = self.worker_specialization[worker_id].get(task_type, 0.5)
            new_val = 1.0 if success else 0.0
            self.worker_specialization[worker_id][task_type] = old_score * 0.9 + new_val * 0.1


class AgentWorker:
    """
    Worker agent for PARL parallel execution.

    Each worker:
    - Executes tasks independently
    - Collects experience for PPO
    - Reports metrics to controller
    """

    def __init__(self, worker_id: str, parl_controller: "PARLController"):
        self.worker_id = worker_id
        self.parl_controller = parl_controller
        self.active = False
        self.current_task: Optional[str] = None
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_execution_time = 0.0

    async def run(self) -> None:
        """Main worker loop."""
        self.active = True
        logger.debug(f"Worker {self.worker_id} started")

        while self.active:
            try:
                # Get task from controller
                task = await self.parl_controller.get_task_for_worker(self.worker_id)
                if task is None:
                    await asyncio.sleep(0.1)
                    continue

                # Execute task
                await self._execute_task(task)

            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
                await asyncio.sleep(1)

        logger.debug(f"Worker {self.worker_id} stopped")

    async def _execute_task(self, task: Dict[str, Any]) -> None:
        """Execute a single task with tracing."""
        start_time = time.time()
        task_id = task.get("task_id", "unknown")
        task_type = task.get("task_type", "unknown")
        self.current_task = task_id
        
        swarm_spans = get_swarm_spans()

        try:
            # Execute based on task type with tracing
            if swarm_spans:
                with swarm_spans.task_execution(task_id, task_type, self.worker_id):
                    result = await self._process_task(task_type, task.get("payload", {}))
            else:
                result = await self._process_task(task_type, task.get("payload", {}))

            # Report success
            execution_time = time.time() - start_time
            self.completed_tasks += 1
            self.total_execution_time += execution_time

            await self.parl_controller.report_task_complete(
                task_id, result, execution_time
            )

        except Exception as e:
            # Report failure
            await self.parl_controller.report_task_failed(task_id, str(e))
            self.failed_tasks += 1

        finally:
            self.current_task = None

    async def _process_task(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """Process specific task type."""
        # Simulate different task types
        task_delays = {
            "monitoring": 0.05,
            "analysis": 0.15,
            "optimization": 0.2,
            "route_optimization": 0.1,
        }

        delay = task_delays.get(task_type, 0.1)
        await asyncio.sleep(delay)

        return {
            "task_type": task_type,
            "status": "completed",
            "worker_id": self.worker_id,
        }

    def stop(self) -> None:
        """Stop the worker."""
        self.active = False


class PARLController:
    """
    PARL Controller for parallel task execution.

    Manages:
    - Worker pool (up to 100 workers)
    - Parallel task execution (up to 1500 steps)
    - PPO policy optimization
    - Experience collection

    Example:
        >>> parl = PARLController(max_workers=50, max_parallel_steps=1500)
        >>> await parl.initialize()
        >>> tasks = [{"task_id": "1", "task_type": "analyze"}, ...]
        >>> results = await parl.execute_parallel(tasks)
    """

    def __init__(self, max_workers: int = 100, max_parallel_steps: int = 1500):
        self.config = PARLConfig(
            max_workers=max_workers, max_parallel_steps=max_parallel_steps
        )

        self.workers: Dict[str, AgentWorker] = {}
        self.scheduler = TaskScheduler(max_workers)
        self.metrics = PARLMetrics()

        # Task tracking
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}
        self.completed_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_futures: Dict[str, asyncio.Future[Dict[str, Any]]] = {}

        # Experience buffer for PPO
        self.experience_buffer: deque[Experience] = deque(
            maxlen=self.config.experience_buffer_size
        )

        # Control
        self._running = False
        self._worker_tasks: List[asyncio.Task[Any]] = []
        self._metrics_task: Optional[asyncio.Task[Any]] = None

        # Locks
        self._task_lock = asyncio.Lock()

        logger.info(
            f"PARLController created: {max_workers} workers, {max_parallel_steps} max steps"
        )

    async def initialize(self) -> None:
        """Initialize PARL controller and worker pool."""
        logger.info("Initializing PARL controller...")

        self._running = True

        # Create workers
        for i in range(self.config.max_workers):
            worker_id = f"worker_{i:03d}"
            worker = AgentWorker(worker_id, self)
            self.workers[worker_id] = worker

            # Start worker
            task = asyncio.create_task(worker.run())
            self._worker_tasks.append(task)

        # Start metrics collector
        self._metrics_task = asyncio.create_task(self._collect_metrics())

        self.metrics.active_workers = len(self.workers)
        logger.info(f"PARL controller initialized with {len(self.workers)} workers")

    async def execute_parallel(
        self, tasks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute tasks in parallel using PARL with tracing.
        """
        if not tasks:
            return []

        results: List[Dict[str, Any]] = []
        batch_size = self.config.max_parallel_steps
        
        swarm_spans = get_swarm_spans()

        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            
            if swarm_spans:
                with swarm_spans.parallel_batch(len(batch)):
                    batch_results = await self._execute_batch(batch)
            else:
                batch_results = await self._execute_batch(batch)
                
            results.extend(batch_results)

        return results

    async def _execute_batch(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute a batch of tasks in parallel."""
        # Create futures for all tasks
        futures: List[asyncio.Future[Dict[str, Any]]] = []

        async with self._task_lock:
            for task in tasks:
                task_id = task.get("task_id", str(time.time()))
                task["task_id"] = task_id

                future: asyncio.Future[Dict[str, Any]] = asyncio.Future()
                self.task_futures[task_id] = future
                self.pending_tasks[task_id] = task

                # Submit to scheduler
                priority = task.get("priority", 5)
                await self.scheduler.submit(task, priority)

                futures.append(future)

        # Wait for all tasks to complete
        results = await asyncio.gather(*futures, return_exceptions=True)

        # Process results
        processed_results: List[Dict[str, Any]] = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({"success": False, "error": str(result)})
            else:
                processed_results.append(result)

        return processed_results

    async def get_task_for_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get next task for worker from scheduler."""
        try:
            # Try to get task from queue
            priority, timestamp, task = await asyncio.wait_for(
                self.scheduler.task_queue.get(), timeout=0.1
            )

            task_id = task.get("task_id")
            if task_id:
                self.scheduler.assign_task(task_id, worker_id)

            return task

        except asyncio.TimeoutError:
            return None

    async def report_task_complete(
        self, task_id: str, result: Any, execution_time: float
    ) -> None:
        """Report task completion and record experience."""
        async with self._task_lock:
            task = self.pending_tasks.get(task_id, {})
            task_type = task.get("task_type", "unknown")
            self.scheduler.complete_task(task_id, success=True, task_type=task_type)

            # 1. Record experience for learning
            # State is current worker loads and task metadata
            state = {
                "worker_loads": list(self.scheduler.worker_loads.values()),
                "task_type": task.get("task_type"),
                "priority": task.get("priority")
            }
            
            # Reward: inverse of execution time + success bonus
            # Cap reward to prevent extreme values when execution_time is near zero
            reward = min(100.0, 1.0 / max(execution_time, 0.001) + 5.0) 
            
            exp = Experience(
                state=state,
                action=0, # Simplified action index for now
                reward=reward,
                next_state={}, # Will be populated if needed for sequential tasks
                done=True,
                log_prob=0.0,
                value=0.0
            )
            self.experience_buffer.append(exp)

            # 2. Update internal state
            self.completed_tasks[task_id] = {
                "task_id": task_id,
                "success": True,
                "result": result,
                "execution_time": execution_time,
            }

            # Resolve future
            future = self.task_futures.pop(task_id, None)
            if future and not future.done():
                future.set_result(self.completed_tasks[task_id])

            # Clean up pending
            self.pending_tasks.pop(task_id, None)

            # Update metrics
            self.metrics.completed_tasks += 1
            
            # 3. Check for policy update
            if len(self.experience_buffer) >= self.config.update_interval:
                await self._update_policy()

    async def report_task_failed(self, task_id: str, error: str) -> None:
        """Report task failure and record negative experience."""
        async with self._task_lock:
            task = self.pending_tasks.get(task_id, {})
            task_type = task.get("task_type", "unknown")
            self.scheduler.complete_task(task_id, success=False, task_type=task_type)

            # Record negative experience
            state = {
                "worker_loads": list(self.scheduler.worker_loads.values()),
                "task_type": task.get("task_type")
            }
            exp = Experience(
                state=state,
                action=0,
                reward=-10.0, # Strong penalty for failure
                next_state={},
                done=True,
                log_prob=0.0,
                value=0.0
            )
            self.experience_buffer.append(exp)

            # Store failure
            self.completed_tasks[task_id] = {
                "task_id": task_id,
                "success": False,
                "error": error,
            }

            # Resolve future
            future = self.task_futures.pop(task_id, None)
            if future and not future.done():
                future.set_result(self.completed_tasks[task_id])

            # Clean up pending
            self.pending_tasks.pop(task_id, None)

            # Update metrics
            self.metrics.failed_tasks += 1

    async def _update_policy(self) -> None:
        """
        PPO policy update placeholder.
        
        When skip_policy_update=True (default), this method logs a warning
        and returns without clearing the buffer. The experience buffer will
        naturally evict oldest entries when it reaches max size (FIFO).
        
        When skip_policy_update=False, this method should be implemented with:
        1. Sample mini-batches from the experience buffer
        2. Compute advantages using GAE (Generalized Advantage Estimation)
        3. Update policy network using PPO clipped objective
        4. Update value function to estimate expected returns
        """
        self.metrics.policy_update_count += 1
        buffer_size = len(self.experience_buffer)
        
        if self.config.skip_policy_update:
            # Skip update - buffer will naturally evict old entries when full
            logger.debug(
                f"Policy update skipped (skip_policy_update=True). "
                f"Buffer size: {buffer_size}/{self.config.experience_buffer_size}"
            )
            return
        
        # When skip_policy_update=False, implement actual PPO update
        # TODO: Implement actual PPO update for production use
        swarm_spans = get_swarm_spans()
        
        logger.info(
            f"Policy update triggered with {buffer_size} experiences "
            f"(PPO not yet implemented - buffer preserved)"
        )
        
        if swarm_spans:
            with swarm_spans.policy_update(buffer_size):
                pass  # Placeholder for actual PPO implementation

    async def _collect_metrics(self) -> None:
        """Background metrics collection."""
        while self._running:
            try:
                # Calculate throughput
                completed = self.metrics.completed_tasks
                await asyncio.sleep(5)
                new_completed = self.metrics.completed_tasks

                self.metrics.throughput_tps = (new_completed - completed) / 5.0

                # Calculate worker utilization
                active_workers = sum(
                    1 for w in self.workers.values() if w.current_task is not None
                )
                self.metrics.worker_utilization = (
                    active_workers / len(self.workers) if self.workers else 0
                )

                # Update queued tasks
                self.metrics.queued_tasks = len(self.pending_tasks)

            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(5)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current PARL metrics."""
        return {
            "tasks": {
                "total": self.metrics.total_tasks,
                "completed": self.metrics.completed_tasks,
                "failed": self.metrics.failed_tasks,
                "queued": self.metrics.queued_tasks,
            },
            "workers": {
                "total": len(self.workers),
                "active": self.metrics.active_workers,
                "utilization": round(self.metrics.worker_utilization * 100, 2),
            },
            "performance": {
                "throughput_tps": round(self.metrics.throughput_tps, 2),
                "avg_latency_ms": round(self.metrics.avg_task_latency_ms, 2),
                "policy_updates": self.metrics.policy_update_count,
            },
        }

    async def terminate(self) -> None:
        """Terminate PARL controller and all workers."""
        logger.info("Terminating PARL controller...")
        self._running = False

        # Stop all workers
        for worker in self.workers.values():
            worker.stop()

        # Cancel worker tasks
        for task in self._worker_tasks:
            task.cancel()

        # Wait for workers to stop
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)

        # Cancel metrics task
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass

        logger.info("PARL controller terminated")


# Convenience function
async def execute_with_parl(
    tasks: List[Dict[str, Any]], max_workers: int = 100, max_parallel_steps: int = 1500
) -> List[Dict[str, Any]]:
    """Execute tasks with PARL optimization."""
    controller = PARLController(max_workers, max_parallel_steps)
    await controller.initialize()

    try:
        results = await controller.execute_parallel(tasks)
        return results
    finally:
        await controller.terminate()
