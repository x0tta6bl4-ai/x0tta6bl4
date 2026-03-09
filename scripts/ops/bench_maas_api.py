#!/usr/bin/env python3
"""
bench_maas_api.py — Performance Benchmark for MaaS API Endpoints
================================================================

Simulates high-frequency heartbeats, telemetry queries, and federation
operations to measure latency and throughput of the Control Plane.

Usage:
    export MAAS_API_URL="http://localhost:8000"
    export MAAS_API_KEY="your_api_key"
    python3 bench_maas_api.py --concurrent 50 --duration 60
"""

import asyncio
import time
import os
import argparse
import random
import statistics
import httpx
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
API_URL = os.getenv("MAAS_API_URL", "http://localhost:8000")
API_KEY = os.getenv("MAAS_API_KEY", "test_key")
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

class BenchmarkResult:
    def __init__(self):
        self.latencies = []
        self.errors = 0
        self.start_time = time.time()
        self.end_time = None

    def record(self, latency):
        self.latencies.append(latency)

    def record_error(self):
        self.errors += 1

    def finish(self):
        self.end_time = time.time()

    def report(self, name):
        total_time = self.end_time - self.start_time
        count = len(self.latencies)
        rps = count / total_time if total_time > 0 else 0
        
        print(f"\n📊 Benchmark Results: {name}")
        print(f"==================================================")
        print(f"Total Requests: {count}")
        print(f"Total Errors:   {self.errors}")
        print(f"Duration:       {total_time:.2f}s")
        print(f"Throughput:     {rps:.2f} req/s")
        
        if count > 0:
            avg = sum(self.latencies) / count
            p95 = statistics.quantiles(self.latencies, n=20)[18] if count >= 20 else avg
            p99 = statistics.quantiles(self.latencies, n=100)[98] if count >= 100 else p95
            print(f"Latency Avg:    {avg*1000:.2f} ms")
            print(f"Latency P95:    {p95*1000:.2f} ms")
            print(f"Latency P99:    {p99*1000:.2f} ms")
        print(f"==================================================\n")

async def bench_heartbeat(client, duration, node_id):
    result = BenchmarkResult()
    deadline = time.time() + duration
    
    while time.time() < deadline:
        payload = {
            "node_id": node_id,
            "mesh_id": "bench-mesh",
            "cpu_usage": random.uniform(10, 80),
            "memory_usage": random.uniform(20, 60),
            "neighbors_count": random.randint(1, 10),
            "routing_table_size": 100,
            "uptime": 3600.0,
            "custom_metrics": {"latency_ms": random.uniform(5, 50)}
        }
        
        start = time.time()
        try:
            resp = await client.post(f"{API_URL}/api/v1/maas/heartbeat", json=payload, headers=HEADERS)
            if resp.status_code == 200:
                result.record(time.time() - start)
            else:
                result.record_error()
        except Exception:
            result.record_error()
            
    result.finish()
    return result

async def bench_topology(client, duration, mesh_id):
    result = BenchmarkResult()
    deadline = time.time() + duration
    
    while time.time() < deadline:
        start = time.time()
        try:
            resp = await client.get(f"{API_URL}/api/v1/maas/{mesh_id}/topology", headers=HEADERS)
            if resp.status_code == 200:
                result.record(time.time() - start)
            else:
                result.record_error()
        except Exception:
            result.record_error()
            
    result.finish()
    return result

async def run_benchmark(args):
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info(f"🚀 Starting benchmark against {API_URL}...")
        logger.info(f"Parameters: concurrency={args.concurrent}, duration={args.duration}s")
        
        # 1. Heartbeat Benchmark
        tasks = []
        for i in range(args.concurrent):
            tasks.append(bench_heartbeat(client, args.duration, f"bench-node-{i}"))
        
        results = await asyncio.gather(*tasks)
        
        # Aggregate results
        final_result = BenchmarkResult()
        for r in results:
            final_result.latencies.extend(r.latencies)
            final_result.errors += r.errors
        final_result.start_time = min(r.start_time for r in results)
        final_result.end_time = max(r.end_time for r in results)
        
        final_result.report("MaaS Node Heartbeat (POST)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MaaS API Benchmark")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent workers")
    parser.add_argument("--duration", type=int, default=10, help="Duration in seconds")
    args = parser.parse_args()
    
    asyncio.run(run_benchmark(args))
