"""
Unit tests for Swarm Phase 2: Learning and Experience Loop.
Verifies that PARLController collects experience and updates policy.
"""

import asyncio
import unittest
from src.swarm.parl.controller import PARLController, PARLConfig

class TestSwarmLearning(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Use small worker pool for fast tests
        self.controller = PARLController(max_workers=5, max_parallel_steps=10)
        # Set small update interval to trigger policy update quickly
        self.controller.config.update_interval = 3
        await self.controller.initialize()

    async def asyncTearDown(self):
        await self.controller.terminate()

    async def test_experience_collection(self):
        tasks = [
            {"task_id": "t1", "task_type": "analysis", "payload": {}},
            {"task_id": "t2", "task_type": "analysis", "payload": {}},
        ]
        
        # Execute tasks
        results = await self.controller.execute_parallel(tasks)
        
        # Verify buffer has data (might be partially cleared if update triggered)
        # But since interval=3 and we ran 2, they should be in buffer or metrics
        self.assertEqual(len(results), 2)
        total_finished = self.controller.metrics.completed_tasks + self.controller.metrics.failed_tasks
        self.assertGreaterEqual(total_finished, 2)

    async def test_policy_update_trigger(self):
        # Initial updates = 0
        initial_updates = self.controller.metrics.policy_update_count
        
        # Run 4 tasks (interval is 3)
        tasks = [{"task_id": f"task_{i}", "task_type": "bench"} for i in range(4)]
        await self.controller.execute_parallel(tasks)
        
        # Policy should have updated at least once
        self.assertGreater(self.controller.metrics.policy_update_count, initial_updates)

    async def test_worker_specialization(self):
        task_type = "heavy_compute"
        worker_id = "worker_000"
        
        # Simulate success
        self.controller.scheduler.assign_task("temp_id", worker_id)
        self.controller.scheduler.complete_task("temp_id", success=True, task_type=task_type)
        
        score_after_success = self.controller.scheduler.worker_specialization[worker_id][task_type]
        self.assertGreater(score_after_success, 0.5)
        
        # Simulate failure
        self.controller.scheduler.assign_task("temp_id_2", worker_id)
        self.controller.scheduler.complete_task("temp_id_2", success=False, task_type=task_type)
        
        score_after_failure = self.controller.scheduler.worker_specialization[worker_id][task_type]
        self.assertLess(score_after_failure, score_after_success)

if __name__ == "__main__":
    unittest.main()
