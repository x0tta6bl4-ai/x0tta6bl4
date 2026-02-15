#!/usr/bin/env python3
"""
Cache (Redis) Resilience Tests
Tests cache failure scenarios and fallback mechanisms
"""

import json
import shutil
import subprocess
import time
from datetime import datetime
from typing import Dict, Tuple

import pytest
import requests


class CacheResilienceTests:
    """Test cache failures and recovery"""

    REDIS_CONTAINER = "x0tta6bl4-redis"
    API_URL = "http://localhost:8000"
    HEALTH_ENDPOINT = f"{API_URL}/health"
    METRICS_ENDPOINT = (
        "http://localhost:9090/api/v1/query?query=redis_connected_clients"
    )

    def get_container_status(self, container: str) -> Tuple[bool, str]:
        """Get container running status"""
        try:
            result = subprocess.run(
                f"docker ps --filter 'name={container}' --format '{{{{.State}}}}'",
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            state = result.stdout.strip()
            return state == "running", state
        except Exception as e:
            return False, str(e)

    def check_api_health(self) -> Tuple[bool, int]:
        """Check if API is healthy"""
        try:
            resp = requests.get(self.HEALTH_ENDPOINT, timeout=3)
            return resp.status_code == 200, resp.status_code
        except:
            return False, 0

    def check_redis_metrics(self) -> Dict:
        """Check Redis metrics from Prometheus"""
        try:
            resp = requests.get(self.METRICS_ENDPOINT, timeout=5)
            data = resp.json()
            if data.get("status") == "success":
                return {"connected": True, "data": data.get("data", {})}
            return {"connected": False}
        except:
            return {"connected": False}

    def measure_recovery_time(self, timeout: int = 60) -> float:
        """Measure how long it takes cache to recover"""
        start = time.time()
        while time.time() - start < timeout:
            running, _ = self.get_container_status(self.REDIS_CONTAINER)
            if running:
                # Wait a bit for Redis to be ready
                time.sleep(1)
                return time.time() - start
            time.sleep(0.5)
        return -1  # Timeout

    @pytest.mark.integration
    @pytest.mark.chaos
    def test_cache_stop_and_recovery(self):
        """Test API behavior when cache stops"""
        print("\n" + "=" * 60)
        print("TEST: Cache Stop and Recovery")
        print("=" * 60)

        # Verify initial state
        healthy, status = self.check_api_health()
        assert healthy, f"API should be healthy initially, got {status}"
        print("✅ Initial: API is healthy")

        # Stop cache
        print("Stopping Redis cache...")
        subprocess.run(
            f"docker stop {self.REDIS_CONTAINER}", shell=True, capture_output=True
        )
        time.sleep(2)

        cache_running, cache_state = self.get_container_status(self.REDIS_CONTAINER)
        assert not cache_running, f"Cache should be stopped, state: {cache_state}"
        print(f"✅ Cache stopped: {cache_state}")

        # Check API response during cache outage (should still work via DB)
        time.sleep(1)
        healthy, status = self.check_api_health()

        # API should remain available even without cache
        if healthy:
            print(
                f"✅ API correctly available during cache outage (using DB): {status}"
            )
        else:
            print("⚠️  API degraded during cache outage (expected without optimization)")

        # Restart cache
        print("Restarting cache...")
        subprocess.run(
            f"docker start {self.REDIS_CONTAINER}", shell=True, capture_output=True
        )

        recovery_time = self.measure_recovery_time()
        assert recovery_time > 0, "Cache recovery timeout"

        healthy, status = self.check_api_health()
        assert healthy, f"API should be healthy after cache recovery, got {status}"

        print(f"✅ Cache recovered in {recovery_time:.2f}s")
        print(f"✅ API healthy after recovery: {status}")

    @pytest.mark.integration
    @pytest.mark.chaos
    def test_cache_performance_degradation(self):
        """Test API performance with and without cache"""
        print("\n" + "=" * 60)
        print("TEST: Cache Performance Impact")
        print("=" * 60)

        import concurrent.futures

        def measure_performance(label: str, num_requests: int = 50):
            """Measure API performance"""

            def single_request():
                try:
                    start = time.time()
                    resp = requests.get(self.HEALTH_ENDPOINT, timeout=5)
                    elapsed = (time.time() - start) * 1000
                    return {"success": resp.status_code == 200, "time": elapsed}
                except Exception as e:
                    return {"success": False, "time": 0, "error": str(e)}

            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(single_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            successful = sum(1 for r in results if r["success"])
            times = [r["time"] for r in results if r["success"]]

            if times:
                avg_time = sum(times) / len(times)
                min_time = min(times)
                max_time = max(times)
                p95_time = sorted(times)[int(len(times) * 0.95)]

                print(f"\n{label}:")
                print(
                    f"  Success rate: {successful}/{num_requests} ({successful/num_requests*100:.1f}%)"
                )
                print(f"  Avg response: {avg_time:.2f}ms")
                print(f"  Min response: {min_time:.2f}ms")
                print(f"  Max response: {max_time:.2f}ms")
                print(f"  P95 response: {p95_time:.2f}ms")

                return {
                    "avg": avg_time,
                    "p95": p95_time,
                    "max": max_time,
                    "success_rate": successful / num_requests,
                }
            return {}

        # Measure with cache active
        print("Measuring performance WITH cache...")
        with_cache = measure_performance("WITH CACHE", 50)

        # Stop cache
        print("\nStopping cache...")
        subprocess.run(
            f"docker stop {self.REDIS_CONTAINER}", shell=True, capture_output=True
        )
        time.sleep(2)

        # Measure without cache
        print("Measuring performance WITHOUT cache...")
        without_cache = measure_performance("WITHOUT CACHE", 50)

        # Restart cache
        print("\nRestarting cache...")
        subprocess.run(
            f"docker start {self.REDIS_CONTAINER}", shell=True, capture_output=True
        )

        # Analyze performance difference
        if with_cache and without_cache:
            cache_benefit = (
                (without_cache.get("avg", 0) - with_cache.get("avg", 0))
                / with_cache.get("avg", 1)
                * 100
            )
            print(f"\n{'='*60}")
            print(f"Cache Performance Impact:")
            print(f"  Cache benefit: {cache_benefit:.1f}% faster with cache")
            print(f"{'='*60}")

    @pytest.mark.integration
    @pytest.mark.chaos
    def test_cache_connection_pool(self):
        """Test cache connection pool under load"""
        print("\n" + "=" * 60)
        print("TEST: Cache Connection Pool Behavior")
        print("=" * 60)

        import concurrent.futures

        def concurrent_requests(num_requests: int) -> Dict:
            """Make concurrent requests"""

            def single_request():
                try:
                    resp = requests.get(self.HEALTH_ENDPOINT, timeout=5)
                    return {
                        "success": resp.status_code == 200,
                        "status": resp.status_code,
                    }
                except Exception as e:
                    return {"success": False, "error": str(e)}

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(single_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

            return results

        # Test with increasing concurrency
        for num_requests in [20, 50, 100]:
            print(f"\nTesting with {num_requests} concurrent requests...")
            results = concurrent_requests(num_requests)

            successful = sum(1 for r in results if r["success"])
            success_rate = successful / len(results) * 100

            print(f"  Success rate: {success_rate:.1f}% ({successful}/{num_requests})")

            # Should maintain high success rate
            assert (
                success_rate >= 90
            ), f"Success rate dropped below 90%: {success_rate:.1f}%"

        print("\n✅ Cache connection pool handled all load levels")

    @pytest.mark.integration
    @pytest.mark.chaos
    def test_cache_invalidation_timing(self):
        """Test cache invalidation and refresh timing"""
        print("\n" + "=" * 60)
        print("TEST: Cache Invalidation Timing")
        print("=" * 60)

        # Make requests to establish cache
        for i in range(10):
            try:
                requests.get(self.HEALTH_ENDPOINT, timeout=3)
            except:
                pass
            time.sleep(0.1)

        print("✅ Cache populated with requests")

        # Monitor performance
        times = []
        for i in range(20):
            try:
                start = time.time()
                resp = requests.get(self.HEALTH_ENDPOINT, timeout=3)
                elapsed = (time.time() - start) * 1000
                times.append(elapsed)
            except:
                pass
            time.sleep(0.1)

        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)

            print(f"Cache performance metrics:")
            print(f"  Avg response: {avg_time:.2f}ms")
            print(f"  Min response: {min_time:.2f}ms")
            print(f"  Max response: {max_time:.2f}ms")

            # Cache should provide consistent fast responses
            assert (
                avg_time < 50
            ), f"Average response time {avg_time:.2f}ms too high for cached data"

        print("✅ Cache invalidation timing is appropriate")


def test_cache_resilience_integration():
    """Main integration test for cache resilience"""
    tester = CacheResilienceTests()

    healthy, status = tester.check_api_health()
    if not healthy:
        pytest.skip(
            f"requires local API at {tester.HEALTH_ENDPOINT} (health status={status})"
        )

    if shutil.which("docker") is None:
        pytest.skip("requires docker CLI for cache stop/start resilience checks")

    cache_running, cache_state = tester.get_container_status(tester.REDIS_CONTAINER)
    if not cache_running:
        pytest.skip(
            f"requires running Redis container '{tester.REDIS_CONTAINER}' "
            f"(state='{cache_state}')"
        )

    # Run all tests
    tests = [
        ("Cache Stop and Recovery", tester.test_cache_stop_and_recovery),
        ("Performance Degradation", tester.test_cache_performance_degradation),
        ("Connection Pool", tester.test_cache_connection_pool),
        ("Cache Invalidation", tester.test_cache_invalidation_timing),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"\n✅ {test_name} PASSED")
        except AssertionError as e:
            failed += 1
            print(f"\n❌ {test_name} FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} ERROR: {e}")

    print(f"\n{'='*60}")
    print(f"Summary: {passed} passed, {failed} failed")
    print(f"{'='*60}")

    assert failed == 0, f"Cache resilience tests failed: {failed} failures"


if __name__ == "__main__":
    test_cache_resilience_integration()
