import asyncio
import logging
import time

from src.agents.gtm_agent import GTMAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LoadTest-GTM")


async def simulate_kpi_request(agent: GTMAgent, request_id: int):
    """Simulate a single KPI request."""
    start_time = time.time()
    try:
        # Use run_in_executor for synchronous DB calls if needed,
        # but here we just call the method to see how it scales.
        stats = agent.get_kpi_stats()
        duration = time.time() - start_time
        if stats:
            return duration
        return None
    except Exception as e:
        logger.error(f"Request {request_id} failed: {e}")
        return None


async def run_load_test(concurrent_requests: int = 100):
    """Run concurrent requests against GTMAgent."""
    agent = GTMAgent()
    logger.info(f"🚀 Starting load test: {concurrent_requests} concurrent requests...")

    start_all = time.time()
    tasks = [simulate_kpi_request(agent, i) for i in range(concurrent_requests)]
    results = await asyncio.gather(*tasks)
    total_duration = time.time() - start_all

    valid_durations = [d for d in results if d is not None]
    success_count = len(valid_durations)

    if valid_durations:
        avg_latency = sum(valid_durations) / success_count
        max_latency = max(valid_durations)
        min_latency = min(valid_durations)
    else:
        avg_latency = max_latency = min_latency = 0

    print("\n" + "=" * 40)
    print(f"📊 LOAD TEST RESULTS ({concurrent_requests} req)")
    print("=" * 40)
    print(
        f"✅ Success Rate: {success_count}/{concurrent_requests} ({success_count/concurrent_requests*100}%)"
    )
    print(f"⏱️ Total Time: {total_duration:.2f}s")
    print(f"⚡ Avg Latency: {avg_latency*1000:.2f}ms")
    print(f"📈 Max Latency: {max_latency*1000:.2f}ms")
    print(f"📉 Min Latency: {min_latency*1000:.2f}ms")
    print(f"🏁 Throughput: {success_count/total_duration:.2f} req/s")
    print("=" * 40)


if __name__ == "__main__":
    asyncio.run(run_load_test(100))
