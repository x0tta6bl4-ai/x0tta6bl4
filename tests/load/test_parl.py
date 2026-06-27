"""
Load Testing for PARL (Parallel Agent Reinforcement Learning) Engine.
Week 13 Deliverable.
"""

import asyncio
import time
import logging
from typing import List, Dict, Any
from src.swarm.parl.controller import PARLController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PARLLoadTest")

async def run_load_test(num_tasks: int = 1500, concurrency: int = 100):
    """
    Simulates high-load parallel execution of agent tasks.
    """
    controller = PARLController()
    controller.config.max_workers = concurrency
    await controller.initialize()
    
    logger.info(f"🚀 Starting PARL Load Test: {num_tasks} tasks, {concurrency} max workers")
    
    tasks: List[Dict[str, Any]] = []
    for i in range(num_tasks):
        tasks.append(
            {
                "task_id": f"load_task_{i}",
                "task_type": "simulation",
                "payload": {"delay_ms": 10}, # Simulate quick CPU/IO work
                "priority": 1
            }
        )
        
    start_time = time.time()
    
    # Execute all tasks
    results = await controller.execute_parallel(tasks)
    
    elapsed = time.time() - start_time
    success_count = sum(1 for r in results if r.get("success") is True)
    
    logger.info("📊 --- Load Test Results ---")
    logger.info(f"Total time: {elapsed:.2f} seconds")
    logger.info(f"Throughput: {num_tasks / elapsed:.2f} tasks/sec")
    logger.info(f"Success rate: {(success_count / num_tasks) * 100:.1f}%")
    logger.info("---------------------------")
    
    assert success_count == num_tasks, f"Not all tasks completed successfully. Success: {success_count}/{num_tasks}"
    # Target: 1500 tasks with 10ms delay on 100 workers
    assert elapsed < 5.0, f"Load test too slow: {elapsed:.2f}s"
    
    # Clean up
    for worker_task in controller._worker_tasks:
        worker_task.cancel()
    if controller._metrics_task:
        controller._metrics_task.cancel()

if __name__ == "__main__":
    asyncio.run(run_load_test())
