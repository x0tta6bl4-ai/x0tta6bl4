import asyncio
import time
import torch
import numpy as np
from src.parl.scheduler import TaskScheduler
from src.parl.worker import AgentWorker
from src.parl.types import Task, TaskPriority, Policy

async def run_benchmark(num_workers: int, num_tasks: int):
    print(f"\n🚀 Running PARL Benchmark: Workers={num_workers}, Tasks={num_tasks}")
    
    policy = Policy(policy_id="bench", version=1)
    workers = [AgentWorker(worker_id=f"w_{i}", policy=policy) for i in range(num_workers)]
    
    # Start workers
    worker_tasks = [asyncio.create_task(w.run()) for w in workers]
    
    scheduler = TaskScheduler(workers)
    scheduler_task = asyncio.create_task(scheduler.run())
    
    start_time = time.time()
    futures = []
    
    for i in range(num_tasks):
        task = Task(
            task_id=f"task_{i}",
            task_type="mesh_analysis", # Use a real task type from worker.py
            priority=TaskPriority.NORMAL,
            payload={"node_count": 10},
            created_at=time.time()
        )
        fut = asyncio.Future()
        await scheduler.submit(task, fut)
        futures.append(fut)
    
    await asyncio.gather(*futures)
    end_time = time.time()
    
    duration = end_time - start_time
    tps = num_tasks / duration
    
    print(f"✅ Completed {num_tasks} tasks in {duration:.2f}s ({tps:.2f} tasks/sec)")
    
    await scheduler.shutdown()
    for w in workers:
        await w.terminate()
    
    scheduler_task.cancel()
    for wt in worker_tasks:
        wt.cancel()
        
    return duration

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        loop.run_until_complete(run_benchmark(num_workers=1, num_tasks=50))
        loop.run_until_complete(run_benchmark(num_workers=10, num_tasks=50))
        loop.run_until_complete(run_benchmark(num_workers=25, num_tasks=50))
    finally:
        loop.close()
