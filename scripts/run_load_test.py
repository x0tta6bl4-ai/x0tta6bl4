#!/usr/bin/env python3
"""
Run Production Load Test in Staging

Runs comprehensive load test against staging environment.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.load.production_load_test import ProductionLoadTester, LoadTestConfig

async def main():
    """Run load test."""
    print("\n" + "="*60)
    print("📊 PRODUCTION LOAD TEST - STAGING")
    print("="*60 + "\n")
    
    # Configure for staging (full production-like load)
    config = LoadTestConfig(
        base_url="http://localhost:8080",
        concurrent_users=1000,  # Production-like
        total_requests=100000,
        ramp_up_seconds=60,
        duration_seconds=300,  # 5 minutes
        target_throughput=6800,
        max_latency_p95=100.0,
        max_memory_mb=2400.0,
        test_pqc_handshake=True,
        test_mesh_routing=True,
        test_health_endpoints=True
    )
    
    print(f"Configuration:")
    print(f"  Base URL: {config.base_url}")
    print(f"  Concurrent Users: {config.concurrent_users}")
    print(f"  Total Requests: {config.total_requests}")
    print(f"  Duration: {config.duration_seconds}s")
    print(f"  Target Throughput: {config.target_throughput} req/sec")
    print(f"  Max Latency P95: {config.max_latency_p95}ms")
    print(f"  Max Memory: {config.max_memory_mb}MB")
    print()
    
    tester = ProductionLoadTester(config)
    metrics = await tester.run_test()
    summary = tester.get_summary()
    
    print("\n" + "="*60)
    print("📊 LOAD TEST RESULTS")
    print("="*60)
    print(f"Duration: {summary['duration_seconds']:.2f}s")
    print(f"Total Requests: {summary['total_requests']:,}")
    print(f"Success Rate: {summary['success_rate_percent']:.2f}%")
    print(f"Latency P50: {summary['latency_p50_ms']:.2f}ms")
    print(f"Latency P95: {summary['latency_p95_ms']:.2f}ms")
    print(f"Latency P99: {summary['latency_p99_ms']:.2f}ms")
    print(f"Throughput: {summary['avg_throughput_per_sec']:.2f} req/sec")
    print(f"Avg Memory: {summary['avg_memory_mb']:.2f}MB")
    print(f"Max Memory: {summary['max_memory_mb']:.2f}MB")
    print(f"Avg CPU: {summary['avg_cpu_percent']:.2f}%")
    print(f"Avg PQC Handshake: {summary['avg_pqc_handshake_ms']:.2f}ms")
    print(f"Errors: {summary['errors_count']}")
    print(f"PASSED: {'✅' if summary['passed'] else '❌'}")
    print("="*60)
    
    # Check criteria
    print("\n🎯 CRITERIA CHECK:")
    print(f"  Success Rate >= 99%: {'✅' if summary['success_rate_percent'] >= 99.0 else '❌'} ({summary['success_rate_percent']:.2f}%)")
    print(f"  Latency P95 <= 100ms: {'✅' if summary['latency_p95_ms'] <= 100.0 else '❌'} ({summary['latency_p95_ms']:.2f}ms)")
    print(f"  Max Memory <= 2.4GB: {'✅' if summary['max_memory_mb'] <= 2400.0 else '❌'} ({summary['max_memory_mb']:.2f}MB)")
    print(f"  Throughput >= 6,800 req/sec: {'✅' if summary['avg_throughput_per_sec'] >= 6800.0 else '❌'} ({summary['avg_throughput_per_sec']:.2f} req/sec)")
    print()
    
    if summary['passed']:
        print("✅ LOAD TEST: PASSED")
        sys.exit(0)
    else:
        print("❌ LOAD TEST: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

