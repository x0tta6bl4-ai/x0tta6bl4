"""
PARL Task Scheduler - Intelligent task scheduling for parallel execution

Implements priority-based scheduling, load balancing, dependency resolution,
and dynamic worker allocation.
"""

import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone

from src.parl.types import Task, TaskId, TaskStatus, TaskPriority
from src.parl.worker import AgentWorker, WorkerState
from src.parl.types import WorkerId, Schedule, QueueStats

logger = logging.getLogger(__name__)


@dataclass(order=True)
class PrioritizedTask:
    """Task wrapper for priority queue (lower priority value = higher priority)."""
    priority: int
    task: Task = field(compare=False)
    future: asyncio.Future = field(compare=False, default=None)
    
    def __post_init__(self):
        if self.future is None:
            self.future = asyncio.Future()


class TaskScheduler:
    """
    Intelligent task scheduler for PARL.
    
    Features:
    - Priority-based scheduling
    - Load balancing across workers
    - Dependency resolution
    - Dynamic worker allocation
    - Task timeout handling
    
    Usage:
        scheduler = TaskScheduler(workers, max_queue_size=10000)
        asyncio.create_task(scheduler.run())
        
        # Submit task
        future = asyncio.Future()
        await scheduler.submit(task, future)
        result = await future
        
        # Get stats
        stats = scheduler.get_queue_stats()
        
        # Shutdown
        await scheduler.shutdown()
    """
    
    def __init__(
        self,
        workers: List[AgentWorker],
        max_queue_size: int = 10000,
        rebalance_interval: float = 5.0,
    ):
        """
        Initialize Task Scheduler.
        
        Args:
            workers: List of agent workers
            max_queue_size: Maximum task queue size
            rebalance_interval: Interval for load rebalancing (seconds)
        """
        self._workers: Dict[WorkerId, AgentWorker] = {w.worker_id: w for w in workers}
        self._max_queue_size = max_queue_size
        self._rebalance_interval = rebalance_interval
        
        # Priority queue for tasks
        self._task_queue: List[PrioritizedTask] = []
        self._queue_lock = asyncio.Lock()
        
        # Task tracking
        self._pending_tasks: Dict[TaskId, PrioritizedTask] = {}
        self._running_tasks: Dict[TaskId, Tuple[WorkerId, float]] = {}  # task_id -> (worker_id, start_time)
        self._completed_tasks: Dict[TaskId, TaskStatus] = {}
        self._task_dependencies: Dict[TaskId, Set[TaskId]] = {}  # task_id -> set of dependency task_ids
        self._dependency_waiters: Dict[TaskId, Set[TaskId]] = {}  # task_id -> set of tasks waiting for it
        
        # Statistics
        self._stats = QueueStats()
        self._task_latencies: List[float] = []  # Recent task latencies
        self._task_wait_times: List[float] = []  # Recent wait times
        
        # State
        self._running = False
        self._shutdown = False
        
        # Worker load tracking
        self._worker_load: Dict[WorkerId, int] = {w: 0 for w in self._workers}
    
    async def run(self) -> None:
        """
        Main scheduler loop.
        
        Continuously schedules tasks to available workers.
        """
        if self._running:
            logger.warning("TaskScheduler already running")
            return
        
        self._running = True
        logger.info(f"TaskScheduler started with {len(self._workers)} workers")
        
        # Start background tasks
        rebalance_task = asyncio.create_task(self._rebalance_loop())
        timeout_task = asyncio.create_task(self._timeout_check_loop())
        
        try:
            while not self._shutdown:
                try:
                    # Process completed tasks
                    await self._process_completed()
                    
                    # Schedule pending tasks
                    await self._schedule_tasks()
                    
                    # Small sleep to prevent busy loop
                    await asyncio.sleep(0.01)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Scheduler error: {e}")
                    await asyncio.sleep(0.1)
        
        finally:
            rebalance_task.cancel()
            timeout_task.cancel()
            self._running = False
            logger.info("TaskScheduler stopped")
    
    async def submit(self, task: Task, future: asyncio.Future) -> None:
        """
        Submit a task for scheduling.
        
        Args:
            task: Task to schedule
            future: Future to set result on
            
        Raises:
            RuntimeError: If queue is full
        """
        async with self._queue_lock:
            if len(self._task_queue) >= self._max_queue_size:
                raise RuntimeError(f"Task queue full (max: {self._max_queue_size})")
            
            # Create prioritized task
            prioritized = PrioritizedTask(
                priority=task.priority,
                task=task,
                future=future
            )
            
            # Check dependencies
            if task.dependencies:
                unresolved = self._check_dependencies(task)
                if unresolved:
                    # Store for later scheduling
                    self._task_dependencies[task.task_id] = unresolved
                    for dep_id in unresolved:
                        if dep_id not in self._dependency_waiters:
                            self._dependency_waiters[dep_id] = set()
                        self._dependency_waiters[dep_id].add(task.task_id)
                    
                    # Still add to pending
                    self._pending_tasks[task.task_id] = prioritized
                    logger.debug(f"Task {task.task_id} waiting for dependencies: {unresolved}")
                    return
            
            # Add to priority queue
            heapq.heappush(self._task_queue, prioritized)
            self._pending_tasks[task.task_id] = prioritized
            self._stats.total_tasks += 1
            self._stats.pending_tasks += 1
            
            logger.debug(f"Task {task.task_id} queued (priority={task.priority})")
    
    def get_queue_stats(self) -> QueueStats:
        """Get current queue statistics."""
        self._stats.queue_depth = len(self._task_queue)
        self._stats.running_tasks = len(self._running_tasks)
        
        # Calculate averages
        if self._task_latencies:
            self._stats.avg_execution_time_ms = sum(self._task_latencies[-100:]) / min(100, len(self._task_latencies))
        if self._task_wait_times:
            self._stats.avg_wait_time_ms = sum(self._task_wait_times[-100:]) / min(100, len(self._task_wait_times))
        
        return self._stats
    
    def get_schedule(self) -> Schedule:
        """Get current schedule snapshot."""
        assignments = {}
        
        for worker_id, worker in self._workers.items():
            if worker.current_task:
                assignments[worker_id] = [worker.current_task.task_id]
            else:
                assignments[worker_id] = []
        
        return Schedule(
            assignments=assignments,
            estimated_completion_time=self._estimate_completion_time(),
            total_tasks=self._stats.total_tasks,
        )
    
    async def rebalance_load(self) -> None:
        """Manually trigger load rebalancing."""
        await self._rebalance_workers()
    
    async def shutdown(self) -> None:
        """Shutdown the scheduler."""
        logger.info("TaskScheduler shutting down")
        self._shutdown = True
        
        # Cancel pending tasks
        async with self._queue_lock:
            for prioritized in self._task_queue:
                if not prioritized.future.done():
                    prioritized.future.set_exception(RuntimeError("Scheduler shutdown"))
            
            self._task_queue.clear()
            self._pending_tasks.clear()
    
    # --- Internal methods ---
    
    def _check_dependencies(self, task: Task) -> Set[TaskId]:
        """Check for unresolved dependencies."""
        unresolved = set()
        
        for dep_id in task.dependencies:
            if dep_id not in self._completed_tasks:
                unresolved.add(dep_id)
        
        return unresolved
    
    async def _process_completed(self) -> None:
        """Process completed tasks and update tracking."""
        completed = []
        
        for task_id, (worker_id, start_time) in list(self._running_tasks.items()):
            # Check if task is complete (future is done)
            if task_id in self._pending_tasks:
                prioritized = self._pending_tasks[task_id]
                if prioritized.future.done():
                    completed.append(task_id)
                    
                    # Record latency
                    latency = (time.time() - start_time) * 1000
                    self._task_latencies.append(latency)
                    self._worker_load[worker_id] = max(0, self._worker_load.get(worker_id, 0) - 1)
        
        for task_id in completed:
            del self._running_tasks[task_id]
            self._stats.running_tasks -= 1
            
            # Update dependency waiters
            if task_id in self._dependency_waiters:
                waiters = self._dependency_waiters.pop(task_id)
                for waiter_id in waiters:
                    if waiter_id in self._task_dependencies:
                        self._task_dependencies[waiter_id].discard(task_id)
                        if not self._task_dependencies[waiter_id]:
                            # All dependencies resolved, schedule task
                            del self._task_dependencies[waiter_id]
                            prioritized = self._pending_tasks.get(waiter_id)
                            if prioritized:
                                heapq.heappush(self._task_queue, prioritized)
                                self._stats.pending_tasks += 1
    
    async def _schedule_tasks(self) -> None:
        """Schedule pending tasks to available workers."""
        async with self._queue_lock:
            while self._task_queue:
                # Get highest priority task
                prioritized = heapq.heappop(self._task_queue)
                task = prioritized.task
                
                # Find available worker
                worker = self._find_available_worker(task)
                if not worker:
                    # No worker available, put back in queue
                    heapq.heappush(self._task_queue, prioritized)
                    break
                
                # Record wait time
                wait_time = (time.time() - task.created_at) * 1000
                self._task_wait_times.append(wait_time)
                
                # Submit to worker
                await worker.submit_task(task, prioritized.future)
                
                # Update tracking
                self._running_tasks[task.task_id] = (worker.worker_id, time.time())
                self._stats.pending_tasks -= 1
                self._stats.running_tasks += 1
                self._worker_load[worker.worker_id] = self._worker_load.get(worker.worker_id, 0) + 1
                
                logger.debug(f"Task {task.task_id} assigned to worker {worker.worker_id}")
    
    def _find_available_worker(self, task: Task) -> Optional[AgentWorker]:
        """Find the best available worker for a task."""
        best_worker = None
        best_load = float('inf')
        
        for worker_id, worker in self._workers.items():
            if worker.state == WorkerState.IDLE:
                load = self._worker_load.get(worker_id, 0)
                
                # Check capabilities
                if self._worker_can_execute(worker, task):
                    if load < best_load:
                        best_worker = worker
                        best_load = load
        
        return best_worker
    
    def _worker_can_execute(self, worker: AgentWorker, task: Task) -> bool:
        """Check if worker can execute the task."""
        capabilities = worker.capabilities
        allowed_types = capabilities.get("task_types", ["*"])
        return "*" in allowed_types or task.task_type in allowed_types
    
    def _estimate_completion_time(self) -> float:
        """Estimate time to complete all pending tasks."""
        pending = len(self._task_queue)
        running = len(self._running_tasks)
        
        if pending == 0 and running == 0:
            return 0.0
        
        # Use average latency for estimation
        avg_latency = (
            sum(self._task_latencies[-100:]) / min(100, len(self._task_latencies))
            if self._task_latencies else 100.0
        )
        
        # Estimate based on parallelism
        active_workers = sum(
            1 for w in self._workers.values() 
            if w.state in (WorkerState.IDLE, WorkerState.BUSY)
        )
        
        if active_workers == 0:
            return pending * avg_latency / 1000
        
        # Time for running tasks + time for pending tasks
        running_time = avg_latency / 1000  # Assume running tasks finish soon
        pending_time = (pending * avg_latency / 1000) / active_workers
        
        return running_time + pending_time
    
    async def _rebalance_loop(self) -> None:
        """Background task for load rebalancing."""
        while not self._shutdown:
            try:
                await asyncio.sleep(self._rebalance_interval)
                await self._rebalance_workers()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rebalance error: {e}")
    
    async def _rebalance_workers(self) -> None:
        """Rebalance load across workers."""
        if not self._workers:
            return
        
        loads = list(self._worker_load.values())
        if not loads:
            return
        
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)
        min_load = min(loads)
        
        # Log imbalance if significant
        if max_load - min_load > 2:
            logger.debug(
                f"Load imbalance detected: avg={avg_load:.1f}, "
                f"min={min_load}, max={max_load}"
            )
        
        # Future: Implement task stealing between workers
    
    async def _timeout_check_loop(self) -> None:
        """Background task for timeout checking."""
        while not self._shutdown:
            try:
                await asyncio.sleep(1.0)
                await self._check_timeouts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Timeout check error: {e}")
    
    async def _check_timeouts(self) -> None:
        """Check for timed out tasks."""
        current_time = time.time()
        timed_out = []
        
        for task_id, (worker_id, start_time) in list(self._running_tasks.items()):
            prioritized = self._pending_tasks.get(task_id)
            if prioritized:
                task = prioritized.task
                elapsed = current_time - start_time
                
                if elapsed > task.timeout_seconds:
                    logger.warning(
                        f"Task {task_id} timed out after {elapsed:.1f}s "
                        f"(timeout={task.timeout_seconds}s)"
                    )
                    timed_out.append(task_id)
                    
                    # Set timeout result
                    if not prioritized.future.done():
                        from src.parl.types import StepResult
                        prioritized.future.set_result(StepResult(
                            task_id=task_id,
                            success=False,
                            error="Task timeout",
                            worker_id=worker_id,
                        ))
        
        for task_id in timed_out:
            del self._running_tasks[task_id]
            self._stats.running_tasks -= 1
            self._stats.failed_tasks += 1
            if task_id in self._pending_tasks:
                del self._pending_tasks[task_id]
    
    def get_worker_stats(self) -> Dict[WorkerId, Dict[str, Any]]:
        """Get statistics for all workers."""
        stats = {}
        
        for worker_id, worker in self._workers.items():
            stats[worker_id] = {
                "state": worker.state.value,
                "load": self._worker_load.get(worker_id, 0),
                "tasks_completed": worker.get_metrics().tasks_completed,
                "avg_latency_ms": worker.get_metrics().avg_latency_ms,
            }
        
        return stats


# Convenience function
def create_scheduler(
    num_workers: int = 100,
    **kwargs
) -> Tuple[TaskScheduler, List[AgentWorker]]:
    """
    Create a scheduler with workers.
    
    Args:
        num_workers: Number of workers to create
        **kwargs: Additional scheduler arguments
        
    Returns:
        Tuple of (scheduler, workers list)
    """
    from src.parl.types import Policy
    
    # Create initial policy
    policy = Policy(policy_id="initial", version=1)
    
    # Create workers
    workers = [
        AgentWorker(
            worker_id=f"worker_{i:03d}",
            policy=policy,
        )
        for i in range(num_workers)
    ]
    
    # Create scheduler
    scheduler = TaskScheduler(workers=workers, **kwargs)
    
    return scheduler, workers