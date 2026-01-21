#!/usr/bin/env python3
"""
Python-based load testing for x0tta6bl4 production readiness validation.
Tests API endpoints under various load levels.
"""

import asyncio
import time
from datetime import datetime
import statistics
import json
from typing import List, Dict
import httpx


class LoadTestResult:
    def __init__(self):
        self.response_times: List[float] = []
        self.status_codes: Dict[int, int] = {}
        self.errors: int = 0
        self.start_time = None
        self.end_time = None
        
    def add_response(self, duration: float, status_code: int):
        self.response_times.append(duration)
        self.status_codes[status_code] = self.status_codes.get(status_code, 0) + 1
        
    def add_error(self):
        self.errors += 1
        
    def get_stats(self) -> Dict:
        if not self.response_times:
            return {}
            
        return {
            "total_requests": len(self.response_times) + self.errors,
            "successful": len(self.response_times),
            "errors": self.errors,
            "error_rate": self.errors / (len(self.response_times) + self.errors),
            "status_codes": self.status_codes,
            "avg_response_time_ms": statistics.mean(self.response_times),
            "min_response_time_ms": min(self.response_times),
            "max_response_time_ms": max(self.response_times),
            "p50_response_time_ms": statistics.median(self.response_times),
            "p95_response_time_ms": statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) > 20 else max(self.response_times),
            "p99_response_time_ms": statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) > 100 else max(self.response_times),
            "duration_seconds": (self.end_time - self.start_time) if self.end_time and self.start_time else 0,
        }


async def load_test_endpoint(
    client: httpx.AsyncClient,
    url: str,
    concurrent_users: int,
    duration_seconds: int,
    request_per_user: int = 10
) -> LoadTestResult:
    """Load test a single endpoint"""
    result = LoadTestResult()
    result.start_time = time.time()
    
    async def single_user():
        for _ in range(request_per_user):
            try:
                start = time.time()
                response = await client.get(url, timeout=10.0)
                duration = (time.time() - start) * 1000  # Convert to ms
                result.add_response(duration, response.status_code)
            except Exception as e:
                print(f"Error: {e}")
                result.add_error()
            await asyncio.sleep(0.1)
    
    # Run concurrent users
    tasks = [single_user() for _ in range(concurrent_users)]
    await asyncio.gather(*tasks)
    
    result.end_time = time.time()
    return result


async def run_load_test_scenario(scenario_name: str, endpoints: List[Dict]):
    """Run a complete load test scenario"""
    print(f"\n{'='*60}")
    print(f"Load Test Scenario: {scenario_name}")
    print(f"{'='*60}")
    
    async with httpx.AsyncClient() as client:
        for endpoint in endpoints:
            url = endpoint["url"]
            concurrent = endpoint.get("concurrent_users", 5)
            duration = endpoint.get("duration_seconds", 30)
            
            print(f"\nTesting: {url}")
            print(f"  Concurrent users: {concurrent}")
            print(f"  Duration: {duration}s")
            
            try:
                result = await load_test_endpoint(client, url, concurrent, duration)
                stats = result.get_stats()
                
                print(f"\n  Results:")
                print(f"    ✅ Successful: {stats.get('successful', 0)}")
                print(f"    ❌ Errors: {stats.get('errors', 0)}")
                print(f"    📊 Error Rate: {stats.get('error_rate', 0):.2%}")
                print(f"    ⏱️  Avg Response: {stats.get('avg_response_time_ms', 0):.2f}ms")
                print(f"    📈 P95 Response: {stats.get('p95_response_time_ms', 0):.2f}ms")
                print(f"    📊 P99 Response: {stats.get('p99_response_time_ms', 0):.2f}ms")
                print(f"    📍 Status Codes: {stats.get('status_codes', {})}")
                
                # Check thresholds
                p95 = stats.get('p95_response_time_ms', float('inf'))
                p99 = stats.get('p99_response_time_ms', float('inf'))
                error_rate = stats.get('error_rate', 1.0)
                
                p95_ok = p95 < 500
                p99_ok = p99 < 1000
                error_ok = error_rate < 0.01
                
                print(f"\n  Thresholds:")
                print(f"    {'✅' if p95_ok else '❌'} P95 < 500ms: {p95:.2f}ms")
                print(f"    {'✅' if p99_ok else '❌'} P99 < 1000ms: {p99:.2f}ms")
                print(f"    {'✅' if error_ok else '❌'} Error Rate < 1%: {error_rate:.2%}")
                
                # Save results
                with open(f"/tmp/{endpoint['name']}_results.json", "w") as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "endpoint": url,
                        "concurrent_users": concurrent,
                        "stats": stats,
                        "thresholds_passed": p95_ok and p99_ok and error_ok
                    }, f, indent=2)
                    
            except Exception as e:
                print(f"  ❌ Test failed: {e}")


async def main():
    """Main load test execution"""
    print(f"x0tta6bl4 Production Readiness Load Test")
    print(f"Started: {datetime.now().isoformat()}")
    
    # Scenario 1: Light load baseline (5 concurrent users)
    scenario1 = [
        {"name": "health_light", "url": "http://localhost:8000/health", "concurrent_users": 5, "duration_seconds": 30},
        {"name": "metrics_light", "url": "http://localhost:9090/api/v1/query?query=up", "concurrent_users": 5, "duration_seconds": 30},
    ]
    
    # Scenario 2: Medium load (20 concurrent users)
    scenario2 = [
        {"name": "health_medium", "url": "http://localhost:8000/health", "concurrent_users": 20, "duration_seconds": 30},
        {"name": "metrics_medium", "url": "http://localhost:9090/api/v1/query?query=up", "concurrent_users": 20, "duration_seconds": 30},
    ]
    
    # Scenario 3: High load (100 concurrent users)
    scenario3 = [
        {"name": "health_high", "url": "http://localhost:8000/health", "concurrent_users": 100, "duration_seconds": 30},
    ]
    
    await run_load_test_scenario("Light Load (5 users)", scenario1)
    await run_load_test_scenario("Medium Load (20 users)", scenario2)
    await run_load_test_scenario("High Load (100 users)", scenario3)
    
    print(f"\n{'='*60}")
    print(f"Load Test Complete")
    print(f"Ended: {datetime.now().isoformat()}")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
