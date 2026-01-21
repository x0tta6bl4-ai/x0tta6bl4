#!/usr/bin/env python3
"""
Performance Baseline for x0tta6bl4

Establishes performance baseline before production deployment.
"""

import asyncio
import sys
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from tests.load.production_load_test import ProductionLoadTester, LoadTestConfig
except ImportError:
    print("⚠️ Production load test module not found")
    print("   Running simplified baseline check...")
    ProductionLoadTester = None

async def run_baseline_test() -> Dict[str, Any]:
    """Run performance baseline test."""
    print("\n" + "="*60)
    print("📊 PERFORMANCE BASELINE TEST")
    print("="*60 + "\n")
    
    if ProductionLoadTester is None:
        return {
            "status": "skipped",
            "reason": "Load test module not available"
        }
    
    # Configure baseline test (smaller scale for baseline)
    config = LoadTestConfig(
        base_url="http://localhost:8080",
        concurrent_users=100,  # Smaller for baseline
        total_requests=10000,
        ramp_up_seconds=30,
        duration_seconds=60,
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
    
    try:
        tester = ProductionLoadTester(config)
        metrics = await tester.run_test()
        summary = tester.get_summary()
        
        # Save baseline
        baseline_file = project_root / "baseline_metrics.json"
        baseline_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "config": {
                "concurrent_users": config.concurrent_users,
                "total_requests": config.total_requests,
                "duration_seconds": config.duration_seconds
            }
        }
        
        with open(baseline_file, "w") as f:
            json.dump(baseline_data, f, indent=2)
        
        print("\n" + "="*60)
        print("📊 BASELINE RESULTS")
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
        
        print(f"\n✅ Baseline saved to: {baseline_file}")
        
        return {
            "status": "completed",
            "passed": summary['passed'],
            "summary": summary,
            "baseline_file": str(baseline_file)
        }
        
    except Exception as e:
        print(f"\n❌ Baseline test failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }

def check_server_running() -> bool:
    """Check if server is running."""
    import httpx
    
    try:
        response = httpx.get("http://localhost:8080/health", timeout=2)
        return response.status_code == 200
    except:
        return False

async def main():
    """Main function."""
    print("🔍 Checking if server is running...")
    
    if not check_server_running():
        print("❌ Server is not running on http://localhost:8080")
        print("   Please start the server first:")
        print("   cd /mnt/AC74CC2974CBF3DC")
        print("   python -m src.core.app")
        return
    
    print("✅ Server is running\n")
    
    result = await run_baseline_test()
    
    if result.get("status") == "completed":
        if result.get("passed"):
            print("\n✅ PERFORMANCE BASELINE: PASSED")
            sys.exit(0)
        else:
            print("\n❌ PERFORMANCE BASELINE: FAILED")
            sys.exit(1)
    else:
        print(f"\n⚠️ PERFORMANCE BASELINE: {result.get('status', 'unknown')}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

