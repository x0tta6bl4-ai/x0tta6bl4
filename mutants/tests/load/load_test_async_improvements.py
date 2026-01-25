"""
Load Test для проверки async improvements.

Проверяет:
- Throughput (msg/sec) до и после async fixes
- Latency (p50, p95, p99) до и после
- Event loop blocking detection
"""

import asyncio
import time
import statistics
from typing import List, Dict
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:8080"
CONCURRENT_REQUESTS = 100
REQUESTS_PER_CLIENT = 50
TOTAL_REQUESTS = CONCURRENT_REQUESTS * REQUESTS_PER_CLIENT

# Endpoints to test
ENDPOINTS = [
    "/health",
    "/mesh/peers",
    "/mesh/stats",
]


async def make_request(client: httpx.AsyncClient, endpoint: str) -> Dict[str, float]:
    """Make a single HTTP request and measure latency."""
    start_time = time.time()
    try:
        response = await client.get(f"{BASE_URL}{endpoint}", timeout=5.0)
        latency = (time.time() - start_time) * 1000  # Convert to ms
        
        return {
            "latency": latency,
            "status": response.status_code,
            "success": response.status_code == 200
        }
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        logger.error(f"Request failed: {e}")
        return {
            "latency": latency,
            "status": 0,
            "success": False
        }


async def run_client(client_id: int, endpoint: str) -> List[Dict[str, float]]:
    """Run a client that makes multiple requests."""
    results = []
    async with httpx.AsyncClient() as client:
        for i in range(REQUESTS_PER_CLIENT):
            result = await make_request(client, endpoint)
            results.append(result)
            # Small delay to avoid overwhelming the server
            await asyncio.sleep(0.01)
    
    return results


async def load_test_endpoint(endpoint: str) -> Dict[str, float]:
    """Run load test for a specific endpoint."""
    logger.info(f"🚀 Starting load test for {endpoint}")
    logger.info(f"   Concurrent clients: {CONCURRENT_REQUESTS}")
    logger.info(f"   Requests per client: {REQUESTS_PER_CLIENT}")
    logger.info(f"   Total requests: {TOTAL_REQUESTS}")
    
    start_time = time.time()
    
    # Create tasks for all clients
    tasks = [
        run_client(client_id, endpoint)
        for client_id in range(CONCURRENT_REQUESTS)
    ]
    
    # Run all clients concurrently
    all_results = await asyncio.gather(*tasks)
    
    # Flatten results
    results = []
    for client_results in all_results:
        results.extend(client_results)
    
    total_time = time.time() - start_time
    
    # Calculate metrics
    latencies = [r["latency"] for r in results]
    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful
    
    metrics = {
        "endpoint": endpoint,
        "total_requests": len(results),
        "successful": successful,
        "failed": failed,
        "success_rate": successful / len(results) * 100 if results else 0,
        "total_time": total_time,
        "throughput": len(results) / total_time,  # requests per second
        "latency_p50": statistics.median(latencies) if latencies else 0,
        "latency_p95": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies) if latencies else 0,
        "latency_p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else max(latencies) if latencies else 0,
        "latency_avg": statistics.mean(latencies) if latencies else 0,
        "latency_min": min(latencies) if latencies else 0,
        "latency_max": max(latencies) if latencies else 0,
    }
    
    return metrics


def print_metrics(metrics: Dict[str, float]):
    """Print load test metrics in a readable format."""
    print("\n" + "="*60)
    print(f"📊 LOAD TEST RESULTS: {metrics['endpoint']}")
    print("="*60)
    print(f"Total Requests:     {metrics['total_requests']}")
    print(f"Successful:         {metrics['successful']} ({metrics['success_rate']:.2f}%)")
    print(f"Failed:             {metrics['failed']}")
    print(f"Total Time:          {metrics['total_time']:.2f}s")
    print(f"Throughput:          {metrics['throughput']:.2f} req/sec")
    print(f"\nLatency (ms):")
    print(f"  Average:           {metrics['latency_avg']:.2f}ms")
    print(f"  P50 (median):      {metrics['latency_p50']:.2f}ms")
    print(f"  P95:               {metrics['latency_p95']:.2f}ms")
    print(f"  P99:               {metrics['latency_p99']:.2f}ms")
    print(f"  Min:               {metrics['latency_min']:.2f}ms")
    print(f"  Max:               {metrics['latency_max']:.2f}ms")
    print("="*60 + "\n")


async def check_event_loop_blocking():
    """Check if event loop is being blocked."""
    logger.info("🔍 Checking for event loop blocking...")
    
    blocking_detected = False
    max_blocking_time = 0
    
    async def monitor_loop():
        nonlocal blocking_detected, max_blocking_time
        last_check = time.time()
        while True:
            await asyncio.sleep(0.1)  # Check every 100ms
            current_time = time.time()
            blocking_time = (current_time - last_check) * 1000  # Convert to ms
            
            if blocking_time > 50:  # More than 50ms is suspicious
                blocking_detected = True
                max_blocking_time = max(max_blocking_time, blocking_time)
                logger.warning(f"⚠️ Event loop blocking detected: {blocking_time:.2f}ms")
            
            last_check = current_time
    
    # Run monitoring for 10 seconds
    monitor_task = asyncio.create_task(monitor_loop())
    await asyncio.sleep(10)
    monitor_task.cancel()
    
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    
    if not blocking_detected:
        logger.info("✅ No event loop blocking detected")
    else:
        logger.warning(f"⚠️ Maximum blocking time: {max_blocking_time:.2f}ms")
    
    return {
        "blocking_detected": blocking_detected,
        "max_blocking_time_ms": max_blocking_time
    }


async def main():
    """Run all load tests."""
    print("\n" + "="*60)
    print("🚀 x0tta6bl4 Load Test - Async Improvements Verification")
    print("="*60)
    print(f"Target: {BASE_URL}")
    print(f"Endpoints: {', '.join(ENDPOINTS)}")
    print("="*60 + "\n")
    
    # Check if server is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            if response.status_code != 200:
                logger.error(f"❌ Server health check failed: {response.status_code}")
                return
    except Exception as e:
        logger.error(f"❌ Cannot connect to server: {e}")
        logger.error("   Make sure x0tta6bl4 is running on http://localhost:8080")
        return
    
    logger.info("✅ Server is running\n")
    
    # Check for event loop blocking
    blocking_results = await check_event_loop_blocking()
    
    # Run load tests for each endpoint
    all_metrics = []
    for endpoint in ENDPOINTS:
        metrics = await load_test_endpoint(endpoint)
        all_metrics.append(metrics)
        print_metrics(metrics)
        
        # Small delay between endpoints
        await asyncio.sleep(2)
    
    # Summary
    print("\n" + "="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    avg_throughput = statistics.mean([m["throughput"] for m in all_metrics])
    avg_latency_p95 = statistics.mean([m["latency_p95"] for m in all_metrics])
    
    print(f"Average Throughput:  {avg_throughput:.2f} req/sec")
    print(f"Average Latency P95: {avg_latency_p95:.2f}ms")
    
    # Check if improvements are met
    print("\n🎯 TARGETS:")
    print(f"  Throughput:  >6,800 req/sec (current: {avg_throughput:.2f})")
    print(f"  Latency P95: <100ms (current: {avg_latency_p95:.2f}ms)")
    
    if avg_throughput >= 6800:
        print("  ✅ Throughput target MET")
    else:
        print("  ⚠️ Throughput target NOT MET")
    
    if avg_latency_p95 < 100:
        print("  ✅ Latency target MET")
    else:
        print("  ⚠️ Latency target NOT MET")
    
    if blocking_results["blocking_detected"]:
        print(f"  ⚠️ Event loop blocking detected: {blocking_results['max_blocking_time_ms']:.2f}ms")
    else:
        print("  ✅ No event loop blocking detected")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

