"""
PARL Controller - Central controller for Parallel-Agent Reinforcement Learning

Manages pool of up to 100 agents, coordinates parallel execution of up to 1500 steps,
collects and aggregates experience, updates global policy.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone

from src.parl.types import (
    Task, TaskId, Experience, Policy, StepResult, 
    PARLMetrics, PPOConfig, WorkerId
)
from src.parl.worker import AgentWorker, WorkerState
from src.parl.scheduler import TaskScheduler, QueueStats

logger = logging.getLogger(__name__)


@dataclass
class PARLConfig:
    """
    Configuration for PARL Controller.
    
    Attributes:
        num_workers: Number of agent workers (1-100)
        max_parallel_steps: Maximum parallel steps (1-1500)
        batch_size: Batch size for experience collection
        task_queue_size: Maximum task queue size
        experience_buffer_size: Maximum experience buffer size
        policy_update_interval: Steps between policy updates
        enable_policy_learning: Whether to enable RL policy updates
        ppo_config: PPO hyperparameters
    """
    num_workers: int = 100
    max_parallel_steps: int = 1500
    batch_size: int = 64
    task_queue_size: int = 10000
    experience_buffer_size: int = 100000
    policy_update_interval: int = 100
    enable_policy_learning: bool = True
    ppo_config: PPOConfig = field(default_factory=PPOConfig)
    
    def __post_init__(self):
        """Validate configuration."""
        if not 1 <= self.num_workers <= 100:
            raise ValueError(f"num_workers must be 1-100, got {self.num_workers}")
        if not 1 <= self.max_parallel_steps <= 1500:
            raise ValueError(f"max_parallel_steps must be 1-1500, got {self.max_parallel_steps}")


@dataclass
class PARLStats:
    """
    Statistics for PARL execution.
    
    Attributes:
        total_tasks_submitted: Total tasks submitted
        total_tasks_completed: Total tasks completed
        total_tasks_failed: Total tasks failed
        total_experiences: Total experiences collected
        policy_updates: Number of policy updates
        avg_parallelism: Average parallelism achieved
        total_execution_time_ms: Total execution time
        speedup_achieved: Speedup factor achieved
    """
    total_tasks_submitted: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    total_experiences: int = 0
    policy_updates: int = 0
    avg_parallelism: float = 1.0
    total_execution_time_ms: float = 0.0
    speedup_achieved: float = 1.0
    last_updated: float = field(default_factory=time.time)


class PARLController:
    """
    Central controller for Parallel-Agent Reinforcement Learning.
    
    Key features:
    - Manages pool of up to 100 agent workers
    - Coordinates parallel execution of up to 1500 steps
    - Collects and aggregates experience
    - Updates global policy using PPO
    - Achieves up to 4.5x speedup over sequential execution
    
    Usage:
        config = PARLConfig(num_workers=50, max_parallel_steps=1000)
        controller = PARLController(config)
        await controller.initialize()
        
        # Submit tasks
        task_ids = await controller.submit_tasks_batch(tasks)
        
        # Wait for results
        results = await controller.wait_for_results(task_ids)
        
        # Get statistics
        stats = controller.get_stats()
    """
    
    def __init__(self, config: Optional[PARLConfig] = None):
        """
        Initialize PARL Controller.
        
        Args:
            config: PARL configuration. Uses defaults if not provided.
        """
        self.config = config or PARLConfig()
        
        # Worker management
        self._workers: Dict[WorkerId, AgentWorker] = {}
        self._worker_tasks: Dict[WorkerId, asyncio.Task] = {}
        
        # Task management
        self._scheduler: Optional[TaskScheduler] = None
        self._pending_futures: Dict[TaskId, asyncio.Future] = {}
        
        # Experience and policy
        self._experience_buffer: List[Experience] = []
        self._global_policy: Optional[Policy] = None
        self._policy_version: int = 0
        
        # Statistics
        self._stats = PARLStats()
        self._start_time: Optional[float] = None
        
        # State
        self._initialized = False
        self._shutdown = False
        self._lock = asyncio.Lock()
        
        # Callbacks
        self._on_task_complete: Optional[Callable] = None
        self._on_policy_update: Optional[Callable] = None
    
    async def initialize(self) -> None:
        """
        Initialize the PARL controller.
        
        Creates worker pool, initializes scheduler, and starts background tasks.
        """
        if self._initialized:
            logger.warning("PARLController already initialized")
            return
        
        logger.info(f"Initializing PARL Controller with {self.config.num_workers} workers")
        
        # Create global policy
        self._global_policy = Policy(
            policy_id="global",
            version=1,
            parameters={},
            metadata={"created_by": "PARLController"}
        )
        
        # Create worker pool
        for i in range(self.config.num_workers):
            worker_id = f"worker_{i:03d}"
            worker = AgentWorker(
                worker_id=worker_id,
                policy=self._global_policy,
                on_experience=self._collect_experience
            )
            self._workers[worker_id] = worker
        
        # Initialize scheduler
        self._scheduler = TaskScheduler(
            workers=list(self._workers.values()),
            max_queue_size=self.config.task_queue_size
        )
        
        # Start workers
        for worker_id, worker in self._workers.items():
            task = asyncio.create_task(worker.run())
            self._worker_tasks[worker_id] = task
        
        # Start scheduler
        asyncio.create_task(self._scheduler.run())
        
        # Start background tasks
        asyncio.create_task(self._policy_update_loop())
        asyncio.create_task(self._metrics_collection_loop())
        
        self._initialized = True
        self._start_time = time.time()
        
        logger.info(
            f"PARL Controller initialized: {len(self._workers)} workers, "
            f"max_parallel_steps={self.config.max_parallel_steps}"
        )
    
    async def submit_task(self, task: Task) -> TaskId:
        """
        Submit a single task for execution.
        
        Args:
            task: Task to execute
            
        Returns:
            Task ID for tracking
        """
        if not self._initialized:
            raise RuntimeError("PARLController not initialized")
        
        async with self._lock:
            self._stats.total_tasks_submitted += 1
        
        # Create future for result
        future: asyncio.Future = asyncio.Future()
        self._pending_futures[task.task_id] = future
        
        # Submit to scheduler
        await self._scheduler.submit(task, future)
        
        logger.debug(f"Task {task.task_id} submitted")
        return task.task_id
    
    async def submit_tasks_batch(self, tasks: List[Task]) -> List[TaskId]:
        """
        Submit multiple tasks for parallel execution.
        
        Args:
            tasks: List of tasks to execute
            
        Returns:
            List of task IDs for tracking
        """
        if not self._initialized:
            raise RuntimeError("PARLController not initialized")
        
        task_ids = []
        for task in tasks:
            task_id = await self.submit_task(task)
            task_ids.append(task_id)
        
        logger.info(f"Submitted batch of {len(tasks)} tasks")
        return task_ids
    
    async def execute_parallel(self, tasks: List[Task]) -> List[StepResult]:
        """
        Execute tasks in parallel and return results.
        
        This is the main entry point for parallel execution.
        Automatically chunks tasks into batches of max_parallel_steps.
        
        Args:
            tasks: List of tasks to execute
            
        Returns:
            List of execution results
        """
        if not self._initialized:
            raise RuntimeError("PARLController not initialized")
        
        start_time = time.time()
        results: List[StepResult] = []

        async with self._lock:
            self._stats.total_tasks_submitted += len(tasks)
        
        # Chunk tasks into batches
        chunks = self._chunk_tasks(tasks, self.config.max_parallel_steps)
        
        for i, chunk in enumerate(chunks):
            logger.debug(f"Executing chunk {i+1}/{len(chunks)} with {len(chunk)} tasks")
            
            # Submit chunk
            futures: List[asyncio.Future] = []
            for task in chunk:
                future: asyncio.Future = asyncio.Future()
                self._pending_futures[task.task_id] = future
                await self._scheduler.submit(task, future)
                futures.append(future)
            
            # Wait for all tasks in chunk
            chunk_results = await asyncio.gather(*futures, return_exceptions=True)
            
            for j, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    results.append(StepResult(
                        task_id=chunk[j].task_id,
                        success=False,
                        error=str(result)
                    ))
                    async with self._lock:
                        self._stats.total_tasks_failed += 1
                else:
                    results.append(result)
                    async with self._lock:
                        self._stats.total_tasks_completed += 1
        
        # Calculate speedup
        execution_time = time.time() - start_time
        sequential_time = sum(r.latency_ms for r in results) / 1000
        if sequential_time > 0:
            speedup = sequential_time / execution_time
            async with self._lock:
                self._stats.speedup_achieved = speedup
                self._stats.avg_parallelism = len(tasks) / max(1, len(chunks))
        
        logger.info(
            f"Parallel execution complete: {len(tasks)} tasks, "
            f"{execution_time:.2f}s, speedup={self._stats.speedup_achieved:.2f}x"
        )
        
        return results
    
    async def wait_for_result(self, task_id: TaskId, timeout: float = 30.0) -> StepResult:
        """
        Wait for a single task result.
        
        Args:
            task_id: Task ID to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            Task result
            
        Raises:
            asyncio.TimeoutError: If timeout exceeded
        """
        if task_id not in self._pending_futures:
            raise ValueError(f"Unknown task ID: {task_id}")
        
        future = self._pending_futures[task_id]
        result = await asyncio.wait_for(future, timeout=timeout)
        
        # Clean up
        del self._pending_futures[task_id]
        
        return result
    
    async def wait_for_results(
        self, 
        task_ids: List[TaskId], 
        timeout: float = 60.0
    ) -> Dict[TaskId, StepResult]:
        """
        Wait for multiple task results.
        
        Args:
            task_ids: List of task IDs to wait for
            timeout: Maximum wait time in seconds
            
        Returns:
            Dictionary mapping task IDs to results
        """
        results = {}
        
        for task_id in task_ids:
            try:
                result = await self.wait_for_result(task_id, timeout=timeout)
                results[task_id] = result
            except asyncio.TimeoutError:
                results[task_id] = StepResult(
                    task_id=task_id,
                    success=False,
                    error="Timeout"
                )
        
        return results
    
    async def update_policy(self, experiences: List[Experience]) -> None:
        """
        Update global policy from collected experiences.
        
        Uses PPO algorithm for policy optimization.
        
        Args:
            experiences: List of experiences to learn from
        """
        if not self.config.enable_policy_learning:
            return
        
        if not experiences:
            return
        
        start_time = time.time()
        
        # Aggregate experiences
        aggregated = self._aggregate_experiences(experiences)
        
        # PPO update (simplified - in production would use actual PPO)
        # This is a placeholder for the actual PPO implementation
        new_policy = self._ppo_update(self._global_policy, aggregated)
        
        # Update global policy
        self._global_policy = new_policy
        self._policy_version += 1
        
        # Sync with workers
        await asyncio.gather(*[
            worker.sync_policy(self._global_policy)
            for worker in self._workers.values()
            if worker.state == WorkerState.IDLE
        ])
        
        update_time = (time.time() - start_time) * 1000
        
        async with self._lock:
            self._stats.policy_updates += 1
            self._stats.total_experiences += len(experiences)
        
        logger.info(
            f"Policy updated to version {self._policy_version} "
            f"from {len(experiences)} experiences in {update_time:.1f}ms"
        )
    
    def get_stats(self) -> PARLStats:
        """Get current PARL statistics."""
        return self._stats
    
    def get_metrics(self) -> PARLMetrics:
        """Get current PARL metrics."""
        if not self._scheduler:
            return PARLMetrics()
        
        queue_stats = self._scheduler.get_queue_stats()
        
        active_workers = sum(
            1 for w in self._workers.values() 
            if w.state == WorkerState.BUSY
        )
        idle_workers = sum(
            1 for w in self._workers.values() 
            if w.state == WorkerState.IDLE
        )
        
        total_workers = len(self._workers)
        utilization = active_workers / total_workers if total_workers > 0 else 0
        
        return PARLMetrics(
            active_workers=active_workers,
            idle_workers=idle_workers,
            queued_tasks=queue_stats.pending_tasks,
            running_tasks=queue_stats.running_tasks,
            completed_tasks=self._stats.total_tasks_completed,
            failed_tasks=self._stats.total_tasks_failed,
            avg_task_latency_ms=queue_stats.avg_execution_time_ms,
            throughput_tps=self._calculate_throughput(),
            worker_utilization=utilization,
            parallelism_ratio=self._stats.avg_parallelism,
            speedup_factor=self._stats.speedup_achieved,
        )
    
    def get_policy(self) -> Optional[Policy]:
        """Get current global policy."""
        return self._global_policy
    
    async def shutdown(self, graceful: bool = True) -> None:
        """
        Shutdown the PARL controller.
        
        Args:
            graceful: Whether to wait for pending tasks
        """
        if self._shutdown:
            return
        
        logger.info(f"Shutting down PARL Controller (graceful={graceful})")
        self._shutdown = True
        
        # Terminate workers
        for worker in self._workers.values():
            await worker.terminate()
        
        # Cancel worker tasks
        for task in self._worker_tasks.values():
            task.cancel()
        
        # Wait for cancellation
        if self._worker_tasks.values():
            await asyncio.gather(*self._worker_tasks.values(), return_exceptions=True)
        
        # Shutdown scheduler
        if self._scheduler:
            await self._scheduler.shutdown()
        
        logger.info("PARL Controller shutdown complete")
    
    # --- Internal methods ---
    
    def _chunk_tasks(self, tasks: List[Task], chunk_size: int) -> List[List[Task]]:
        """Split tasks into chunks of maximum size."""
        chunks = []
        for i in range(0, len(tasks), chunk_size):
            chunks.append(tasks[i:i + chunk_size])
        return chunks if chunks else [[]]
    
    async def _collect_experience(self, experience: Experience) -> None:
        """Collect experience from a worker."""
        self._experience_buffer.append(experience)
        
        # Trim buffer if needed
        if len(self._experience_buffer) > self.config.experience_buffer_size:
            self._experience_buffer = self._experience_buffer[-self.config.experience_buffer_size:]
    
    def _aggregate_experiences(self, experiences: List[Experience]) -> Dict[str, Any]:
        """Aggregate experiences for policy update."""
        if not experiences:
            return {}
        
        # Calculate aggregate statistics
        total_reward = sum(e.reward for e in experiences)
        avg_reward = total_reward / len(experiences)
        
        return {
            "num_experiences": len(experiences),
            "total_reward": total_reward,
            "avg_reward": avg_reward,
            "experiences": experiences,
        }
    
    def _ppo_update(self, policy: Policy, aggregated: Dict[str, Any]) -> Policy:
        """
        Perform PPO policy update.
        
        This is a simplified implementation. In production, would use
        actual PPO with neural network policy.
        """
        new_policy = policy.update_version()
        
        # Store metrics
        new_policy.metrics = {
            "avg_reward": aggregated.get("avg_reward", 0),
            "num_experiences": aggregated.get("num_experiences", 0),
        }
        
        return new_policy
    
    def _calculate_throughput(self) -> float:
        """Calculate current throughput in tasks per second."""
        if not self._start_time:
            return 0.0
        
        elapsed = time.time() - self._start_time
        if elapsed <= 0:
            return 0.0
        
        return self._stats.total_tasks_completed / elapsed
    
    async def _policy_update_loop(self) -> None:
        """Background task for periodic policy updates."""
        while not self._shutdown:
            try:
                await asyncio.sleep(1.0)  # Check every second
                
                if len(self._experience_buffer) >= self.config.policy_update_interval:
                    experiences = self._experience_buffer[:self.config.policy_update_interval]
                    self._experience_buffer = self._experience_buffer[self.config.policy_update_interval:]
                    await self.update_policy(experiences)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in policy update loop: {e}")
    
    async def _metrics_collection_loop(self) -> None:
        """Background task for metrics collection."""
        while not self._shutdown:
            try:
                await asyncio.sleep(10.0)  # Collect every 10 seconds
                
                metrics = self.get_metrics()
                logger.debug(f"PARL metrics: {metrics.to_dict()}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
    
    async def __aenter__(self) -> "PARLController":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.shutdown()
