import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.swarm.parl.controller import PARLController


@pytest.fixture
def controller():
    # Patch AgentWorker where it is imported/used in controller module
    with patch("src.swarm.parl.controller.AgentWorker") as mock_worker_cls:
        # Create a mock worker instance
        mock_worker_instance = MagicMock()
        mock_worker_instance.run = AsyncMock()  # run is async
        mock_worker_instance.stop = MagicMock()
        mock_worker_cls.return_value = mock_worker_instance

        ctrl = PARLController(max_workers=2)
        yield ctrl
        # Cleanup tasks if any
        if ctrl._metrics_task and not ctrl._metrics_task.done():
            ctrl._metrics_task.cancel()


@pytest.mark.asyncio
class TestPARLController:
    async def test_initialization(self, controller):
        """Test initialization creates workers"""
        await controller.initialize()
        assert len(controller.workers) == 2
        assert controller._running is True
        # Clean up
        await controller.terminate()

    async def test_execute_parallel_success(self, controller):
        """Test parallel execution of tasks"""
        await controller.initialize()

        # We need to simulate the worker's _execute_task behavior or mock _execute_batch
        # But for unit testing execute_parallel, mocking _execute_batch is easier
        # HOWEVER, to test the actual logic, we should probably mock the Scheduler interactions or Worker.run loop
        # Given complexity, let's mock _execute_batch to test execute_parallel's batching

        with patch.object(
            controller, "_execute_batch", new_callable=AsyncMock
        ) as mock_batch:
            mock_batch.return_value = [{"result": "ok"}, {"result": "ok"}]

            tasks = [{"id": 1}, {"id": 2}]
            results = await controller.execute_parallel(tasks)

            assert len(results) == 2
            assert results[0] == {"result": "ok"}
            mock_batch.assert_called()

        await controller.terminate()

    async def test_execute_batch_logic(self, controller):
        """Test the _execute_batch logic specifically"""
        # This requires the scheduler and workers to actually "run" or be mocked effectively
        # Since we patched AgentWorker, the actual worker loop won't pick up tasks unless we start it
        # But AgentWorker.run is mocked (AsyncMock).

        # So we can't test full integration here easily without a real AgentWorker.
        # But we can verify _execute_batch submits to scheduler.

        await controller.initialize()

        # Mock scheduler.submit
        controller.scheduler.submit = AsyncMock()

        # Mock waiting for results - this is tricky because _execute_batch waits on futures
        # We can fire a background task to resolve futures?

        async def resolve_futures():
            await asyncio.sleep(0.1)
            for tid, fut in controller.task_futures.items():
                if not fut.done():
                    fut.set_result({"task_id": tid, "status": "completed"})

        asyncio.create_task(resolve_futures())

        tasks = [{"task_id": "1", "type": "test"}]
        results = await controller._execute_batch(tasks)

        assert len(results) == 1
        assert results[0]["status"] == "completed"

        await controller.terminate()

    async def test_terminate_graceful(self, controller):
        """Test graceful termination"""
        await controller.initialize()
        await controller.terminate()

        assert not controller._running
        # Check workers stopped
        for w in controller.workers.values():
            w.stop.assert_called()
