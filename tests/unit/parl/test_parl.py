"""
Unit tests for PARL (Parallel-Agent Reinforcement Learning) module.

Tests cover:
- PARLController initialization and task execution
- AgentWorker task processing
- TaskScheduler scheduling and load balancing
"""

import asyncio
import pytest
import time
from typing import List

from src.parl import (
    PARLController, PARLConfig, PARLStats,
    AgentWorker, WorkerState,
    TaskScheduler, QueueStats,
    Task, TaskPriority, TaskStatus,
    Experience, Policy, StepResult, PARLMetrics,
)


# --- Fixtures ---

@pytest.fixture
def parl_config():
    """Create test PARL configuration."""
    return PARLConfig(
        num_workers=10,
        max_parallel_steps=100,
        batch_size=16,
        task_queue_size=1000,
        experience_buffer_size=1000,
        policy_update_interval=10,
        enable_policy_learning=True,
    )


@pytest.fixture
def sample_policy():
    """Create sample policy for testing."""
    return Policy(
        policy_id="test_policy",
        version=1,
        parameters={"test": "value"},
    )


@pytest.fixture
def sample_tasks() -> List[Task]:
    """Create sample tasks for testing."""
    return [
        Task(
            task_type="mesh_analysis",
            payload={"node_count": 10},
            priority=TaskPriority.NORMAL,
        )
        for _ in range(10)
    ]


# --- PARLController Tests ---

class TestPARLController:
    """Tests for PARLController."""
    
    @pytest.mark.asyncio
    async def test_controller_initialization(self, parl_config):
        """Test controller initialization."""
        controller = PARLController(parl_config)
        
        assert controller.config == parl_config
        assert not controller._initialized
        
        await controller.initialize()
        
        assert controller._initialized
        assert len(controller._workers) == parl_config.num_workers
        assert controller._scheduler is not None
        assert controller._global_policy is not None
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_controller_submit_task(self, parl_config):
        """Test single task submission."""
        controller = PARLController(parl_config)
        await controller.initialize()
        
        task = Task(
            task_type="health_check",
            payload={},
            priority=TaskPriority.NORMAL,
        )
        
        task_id = await controller.submit_task(task)
        
        assert task_id is not None
        assert task_id.startswith("task_")
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_controller_submit_batch(self, parl_config, sample_tasks):
        """Test batch task submission."""
        controller = PARLController(parl_config)
        await controller.initialize()
        
        task_ids = await controller.submit_tasks_batch(sample_tasks)
        
        assert len(task_ids) == len(sample_tasks)
        assert all(tid.startswith("task_") for tid in task_ids)
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_controller_execute_parallel(self, parl_config, sample_tasks):
        """Test parallel task execution."""
        controller = PARLController(parl_config)
        await controller.initialize()
        
        results = await controller.execute_parallel(sample_tasks)
        
        assert len(results) == len(sample_tasks)
        assert all(isinstance(r, StepResult) for r in results)
        assert all(r.success for r in results)
        
        # Check statistics
        stats = controller.get_stats()
        assert stats.total_tasks_submitted == len(sample_tasks)
        assert stats.total_tasks_completed == len(sample_tasks)
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_controller_get_metrics(self, parl_config):
        """Test metrics retrieval."""
        controller = PARLController(parl_config)
        await controller.initialize()
        
        metrics = controller.get_metrics()
        
        assert isinstance(metrics, PARLMetrics)
        assert metrics.active_workers >= 0
        assert metrics.idle_workers >= 0
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_controller_policy_update(self, parl_config):
        """Test policy update."""
        controller = PARLController(parl_config)
        await controller.initialize()
        
        # Create experiences
        experiences = [
            Experience(
                state={"test": "state"},
                action={"test": "action"},
                reward=1.0,
                next_state={"test": "next"},
                done=True,
            )
            for _ in range(10)
        ]
        
        await controller.update_policy(experiences)
        
        stats = controller.get_stats()
        assert stats.policy_updates == 1
        
        await controller.shutdown()
    
    @pytest.mark.asyncio
    async def test_controller_context_manager(self, parl_config):
        """Test async context manager usage."""
        async with PARLController(parl_config) as controller:
            assert controller._initialized
            
            task = Task(task_type="health_check", payload={})
            results = await controller.execute_parallel([task])
            
            assert len(results) == 1
            assert results[0].success


# --- AgentWorker Tests ---

class TestAgentWorker:
    """Tests for AgentWorker."""
    
    @pytest.mark.asyncio
    async def test_worker_initialization(self, sample_policy):
        """Test worker initialization."""
        worker = AgentWorker(
            worker_id="test_worker_001",
            policy=sample_policy,
        )
        
        assert worker.worker_id == "test_worker_001"
        assert worker.state == WorkerState.IDLE
        assert worker.policy == sample_policy
    
    @pytest.mark.asyncio
    async def test_worker_execute_step(self, sample_policy):
        """Test single step execution."""
        worker = AgentWorker(
            worker_id="test_worker_001",
            policy=sample_policy,
        )
        
        task = Task(
            task_type="health_check",
            payload={},
            priority=TaskPriority.NORMAL,
        )
        
        result = await worker.execute_step(task)
        
        assert isinstance(result, StepResult)
        assert result.task_id == task.task_id
        assert result.success
        assert result.worker_id == worker.worker_id
    
    @pytest.mark.asyncio
    async def test_worker_run_loop(self, sample_policy):
        """Test worker run loop."""
        worker = AgentWorker(
            worker_id="test_worker_001",
            policy=sample_policy,
        )
        
        # Start worker
        task = asyncio.create_task(worker.run())
        
        # Wait for startup
        await asyncio.sleep(0.1)
        
        assert worker._running
        
        # Submit task
        test_task = Task(task_type="health_check", payload={})
        future = asyncio.Future()
        await worker.submit_task(test_task, future)
        
        # Wait for result
        result = await asyncio.wait_for(future, timeout=5.0)
        
        assert result.success
        
        # Terminate
        await worker.terminate()
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_worker_sync_policy(self, sample_policy):
        """Test policy synchronization."""
        worker = AgentWorker(
            worker_id="test_worker_001",
            policy=sample_policy,
        )
        
        new_policy = sample_policy.update_version()
        await worker.sync_policy(new_policy)
        
        assert worker.policy.version == 2
    
    @pytest.mark.asyncio
    async def test_worker_pause_resume(self, sample_policy):
        """Test pause and resume."""
        worker = AgentWorker(
            worker_id="test_worker_001",
            policy=sample_policy,
        )
        
        # Start worker
        task = asyncio.create_task(worker.run())
        await asyncio.sleep(0.1)
        
        # Pause
        await worker.pause()
        assert worker._paused
        
        # Resume
        await worker.resume()
        assert not worker._paused
        
        # Cleanup
        await worker.terminate()
        task.cancel()
    
    @pytest.mark.asyncio
    async def test_worker_get_status(self, sample_policy):
        """Test status retrieval."""
        worker = AgentWorker(
            worker_id="test_worker_001",
            policy=sample_policy,
        )
        
        status = worker.get_status()
        
        assert status["worker_id"] == worker.worker_id
        assert status["state"] == WorkerState.IDLE.value
        assert "tasks_completed" in status


# --- TaskScheduler Tests ---

class TestTaskScheduler:
    """Tests for TaskScheduler."""
    
    @pytest.mark.asyncio
    async def test_scheduler_initialization(self, sample_policy):
        """Test scheduler initialization."""
        workers = [
            AgentWorker(worker_id=f"worker_{i:03d}", policy=sample_policy)
            for i in range(5)
        ]
        
        scheduler = TaskScheduler(workers=workers)
        
        assert len(scheduler._workers) == 5
        assert scheduler._max_queue_size == 10000
    
    @pytest.mark.asyncio
    async def test_scheduler_submit_task(self, sample_policy):
        """Test task submission."""
        workers = [
            AgentWorker(worker_id=f"worker_{i:03d}", policy=sample_policy)
            for i in range(5)
        ]
        
        # Start workers
        worker_tasks = [asyncio.create_task(w.run()) for w in workers]
        
        scheduler = TaskScheduler(workers=workers)
        scheduler_task = asyncio.create_task(scheduler.run())
        
        await asyncio.sleep(0.1)  # Let scheduler start
        
        task = Task(task_type="health_check", payload={})
        future = asyncio.Future()
        
        await scheduler.submit(task, future)
        
        # Wait for result
        result = await asyncio.wait_for(future, timeout=5.0)
        
        assert result.success
        
        # Cleanup
        await scheduler.shutdown()
        for w in workers:
            await w.terminate()
        scheduler_task.cancel()
        for wt in worker_tasks:
            wt.cancel()
    
    @pytest.mark.asyncio
    async def test_scheduler_get_queue_stats(self, sample_policy):
        """Test queue statistics."""
        workers = [
            AgentWorker(worker_id=f"worker_{i:03d}", policy=sample_policy)
            for i in range(5)
        ]
        
        scheduler = TaskScheduler(workers=workers)
        
        stats = scheduler.get_queue_stats()
        
        assert isinstance(stats, QueueStats)
        assert stats.max_queue_depth == 10000
    
    @pytest.mark.asyncio
    async def test_scheduler_priority_ordering(self, sample_policy):
        """Test that tasks are scheduled by priority."""
        workers = [
            AgentWorker(worker_id=f"worker_{i:03d}", policy=sample_policy)
            for i in range(5)
        ]
        
        # Start workers
        worker_tasks = [asyncio.create_task(w.run()) for w in workers]
        
        scheduler = TaskScheduler(workers=workers)
        scheduler_task = asyncio.create_task(scheduler.run())
        
        await asyncio.sleep(0.1)
        
        # Submit tasks with different priorities
        futures = []
        for priority in [TaskPriority.LOW, TaskPriority.HIGH, TaskPriority.NORMAL]:
            task = Task(
                task_type="health_check",
                payload={"priority": priority},
                priority=priority,
            )
            future = asyncio.Future()
            await scheduler.submit(task, future)
            futures.append(future)
        
        # Wait for all results
        results = await asyncio.gather(*futures)
        
        assert all(r.success for r in results)
        
        # Cleanup
        await scheduler.shutdown()
        for w in workers:
            await w.terminate()
        scheduler_task.cancel()
        for wt in worker_tasks:
            wt.cancel()


# --- Task Tests ---

class TestTask:
    """Tests for Task type."""
    
    def test_task_creation(self):
        """Test task creation."""
        task = Task(
            task_type="test_task",
            payload={"key": "value"},
            priority=TaskPriority.HIGH,
        )
        
        assert task.task_type == "test_task"
        assert task.payload == {"key": "value"}
        assert task.priority == TaskPriority.HIGH
        assert task.task_id.startswith("task_")
    
    def test_task_comparison(self):
        """Test task priority comparison."""
        high_task = Task(task_type="test", priority=TaskPriority.HIGH)
        low_task = Task(task_type="test", priority=TaskPriority.LOW)
        
        assert high_task < low_task  # Lower value = higher priority
    
    def test_task_dependencies(self):
        """Test task dependencies."""
        task1 = Task(task_type="test", task_id="task_1")
        task2 = Task(
            task_type="test",
            task_id="task_2",
            dependencies=["task_1"],
        )
        
        assert "task_1" in task2.dependencies


# --- Experience Tests ---

class TestExperience:
    """Tests for Experience type."""
    
    def test_experience_creation(self):
        """Test experience creation."""
        exp = Experience(
            state={"x": 1},
            action={"a": 0},
            reward=1.0,
            next_state={"x": 2},
            done=True,
        )
        
        assert exp.state == {"x": 1}
        assert exp.action == {"a": 0}
        assert exp.reward == 1.0
        assert exp.done is True


# --- Policy Tests ---

class TestPolicy:
    """Tests for Policy type."""
    
    def test_policy_creation(self):
        """Test policy creation."""
        policy = Policy(
            policy_id="test",
            version=1,
            parameters={"weights": [1, 2, 3]},
        )
        
        assert policy.policy_id == "test"
        assert policy.version == 1
    
    def test_policy_update_version(self):
        """Test policy version update."""
        policy = Policy(policy_id="test", version=1)
        new_policy = policy.update_version()
        
        assert new_policy.version == 2
        assert new_policy.policy_id == policy.policy_id


# --- Integration Tests ---

class TestPARLIntegration:
    """Integration tests for PARL system."""
    
    @pytest.mark.asyncio
    async def test_full_parl_workflow(self, parl_config):
        """Test complete PARL workflow."""
        async with PARLController(parl_config) as controller:
            # Create tasks
            tasks = [
                Task(
                    task_type="mesh_analysis",
                    payload={"node_id": f"node_{i}"},
                    priority=TaskPriority.NORMAL,
                )
                for i in range(50)
            ]
            
            # Execute in parallel
            results = await controller.execute_parallel(tasks)
            
            # Verify results
            assert len(results) == 50
            assert all(r.success for r in results)
            
            # Check metrics
            metrics = controller.get_metrics()
            assert metrics.completed_tasks == 50
            assert metrics.speedup_factor > 1.0  # Should have speedup
    
    @pytest.mark.asyncio
    async def test_parl_with_dependencies(self, parl_config):
        """Test PARL with task dependencies."""
        async with PARLController(parl_config) as controller:
            # Create tasks with dependencies
            task1 = Task(
                task_type="health_check",
                payload={},
                task_id="dep_task_1",
            )
            
            task2 = Task(
                task_type="health_check",
                payload={},
                task_id="dep_task_2",
                dependencies=["dep_task_1"],
            )
            
            results = await controller.execute_parallel([task1, task2])
            
            assert len(results) == 2
            assert all(r.success for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])