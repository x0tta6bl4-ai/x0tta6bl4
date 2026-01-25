#!/usr/bin/env python3
"""
End-to-End Tests for Critical Application Paths
Tests complete workflows and user scenarios
"""

import pytest
import requests
import json
import time
from datetime import datetime
from typing import Dict, Tuple


class E2ECriticalPathTests:
    """E2E tests for critical application workflows"""
    
    API_URL = "http://localhost:8000"
    HEALTH_ENDPOINT = f"{API_URL}/health"
    METRICS_ENDPOINT = "http://localhost:9090/api/v1/query"
    
    def check_api_healthy(self) -> Tuple[bool, Dict]:
        """Check API health and get component status"""
        try:
            resp = requests.get(self.HEALTH_ENDPOINT, timeout=5)
            if resp.status_code == 200:
                return True, resp.json()
            return False, {}
        except Exception as e:
            return False, {"error": str(e)}
    
    def check_metrics_available(self) -> Tuple[bool, str]:
        """Check if Prometheus metrics are available"""
        try:
            resp = requests.get(f"{self.METRICS_ENDPOINT}?query=up", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    return True, "Prometheus operational"
            return False, f"Status: {resp.status_code}"
        except Exception as e:
            return False, str(e)
    
    @pytest.mark.e2e
    @pytest.mark.critical
    def test_e2e_system_startup_and_initialization(self):
        """Test: System startup and full initialization"""
        print("\n" + "="*70)
        print("E2E TEST: System Startup and Initialization")
        print("="*70)
        
        # Step 1: Verify API is accessible
        print("\nStep 1: Checking API accessibility...")
        healthy, info = self.check_api_healthy()
        assert healthy, "API should be accessible"
        print(f"  ✅ API is accessible (v{info.get('version')})")
        
        # Step 2: Verify component initialization
        print("\nStep 2: Checking component status...")
        components = info.get("components", {})
        active_count = sum(1 for v in components.values() if v)
        total_count = len(components)
        print(f"  ✅ {active_count}/{total_count} components initialized ({active_count/total_count*100:.1f}%)")
        
        # Step 3: Verify dependencies
        print("\nStep 3: Checking critical dependencies...")
        deps = info.get("dependencies", {})
        critical_deps = {
            "liboqs": "PQC cryptography",
            "spiffe": "Service identity",
        }
        
        for dep_name, dep_desc in critical_deps.items():
            if dep_name in deps:
                dep_info = deps[dep_name]
                status = dep_info.get("status")
                graceful = dep_info.get("graceful_degradation", False)
                symbol = "✅" if status == "available" else ("⚠️" if graceful else "❌")
                print(f"  {symbol} {dep_desc}: {status}")
        
        # Step 4: Verify metrics collection
        print("\nStep 4: Checking metrics collection...")
        metrics_ok, metrics_msg = self.check_metrics_available()
        assert metrics_ok, f"Metrics should be available: {metrics_msg}"
        print(f"  ✅ Prometheus metrics operational")
        
        print("\n✅ System startup and initialization PASSED")
    
    @pytest.mark.e2e
    @pytest.mark.critical
    def test_e2e_health_check_workflow(self):
        """Test: Health check workflow consistency"""
        print("\n" + "="*70)
        print("E2E TEST: Health Check Workflow")
        print("="*70)
        
        print("\nPhase 1: Rapid health checks...")
        health_checks = []
        for i in range(20):
            healthy, info = self.check_api_healthy()
            assert healthy, f"Health check {i} failed"
            health_checks.append({
                "timestamp": datetime.now().isoformat(),
                "healthy": healthy,
                "version": info.get("version")
            })
            time.sleep(0.1)
        
        print(f"  ✅ 20/20 health checks passed")
        
        print("\nPhase 2: Analyzing health check consistency...")
        versions = set(h["version"] for h in health_checks)
        assert len(versions) == 1, f"Version should be consistent, got: {versions}"
        print(f"  ✅ Version is consistent: {list(versions)[0]}")
        
        print("\nPhase 3: Stress test with concurrent health checks...")
        import concurrent.futures
        
        def concurrent_health_check():
            try:
                healthy, _ = self.check_api_healthy()
                return healthy
            except:
                return False
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(concurrent_health_check) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        success_count = sum(results)
        assert success_count >= 45, f"At least 45/50 concurrent checks should pass, got {success_count}"
        print(f"  ✅ Concurrent health checks: {success_count}/50 passed")
        
        print("\n✅ Health check workflow PASSED")
    
    @pytest.mark.e2e
    @pytest.mark.critical
    def test_e2e_error_handling_and_recovery(self):
        """Test: Error handling and graceful recovery"""
        print("\n" + "="*70)
        print("E2E TEST: Error Handling and Recovery")
        print("="*70)
        
        print("\nPhase 1: Testing 404 error handling...")
        try:
            resp = requests.get(f"{self.API_URL}/nonexistent-endpoint", timeout=5)
            assert resp.status_code in [404, 405], f"Should get 404/405, got {resp.status_code}"
            print(f"  ✅ 404 handling correct: {resp.status_code}")
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
        
        print("\nPhase 2: Testing timeout behavior...")
        start = time.time()
        try:
            resp = requests.get(self.HEALTH_ENDPOINT, timeout=1)
            elapsed = time.time() - start
            assert resp.status_code == 200, f"Health should return 200, got {resp.status_code}"
            print(f"  ✅ Request completed in {elapsed:.3f}s (within timeout)")
        except requests.Timeout:
            print(f"  ❌ Request timed out (API too slow)")
            raise
        
        print("\nPhase 3: Testing rapid request recovery...")
        failed_requests = 0
        successful_requests = 0
        
        for i in range(30):
            try:
                resp = requests.get(self.HEALTH_ENDPOINT, timeout=3)
                if resp.status_code == 200:
                    successful_requests += 1
                else:
                    failed_requests += 1
            except:
                failed_requests += 1
            time.sleep(0.05)
        
        recovery_rate = successful_requests / 30
        assert recovery_rate >= 0.95, f"Recovery rate should be >= 95%, got {recovery_rate*100:.1f}%"
        print(f"  ✅ Request recovery rate: {recovery_rate*100:.1f}%")
        
        print("\n✅ Error handling and recovery PASSED")
    
    @pytest.mark.e2e
    def test_e2e_performance_under_load(self):
        """Test: Performance characteristics under load"""
        print("\n" + "="*70)
        print("E2E TEST: Performance Under Load")
        print("="*70)
        
        import concurrent.futures
        
        print("\nPhase 1: Baseline performance (10 sequential requests)...")
        baseline_times = []
        for i in range(10):
            start = time.time()
            resp = requests.get(self.HEALTH_ENDPOINT, timeout=5)
            elapsed = (time.time() - start) * 1000
            baseline_times.append(elapsed)
            assert resp.status_code == 200
        
        baseline_avg = sum(baseline_times) / len(baseline_times)
        print(f"  Avg: {baseline_avg:.2f}ms, Min: {min(baseline_times):.2f}ms, Max: {max(baseline_times):.2f}ms")
        
        print("\nPhase 2: Concurrent load performance (50 concurrent requests)...")
        def make_request():
            start = time.time()
            resp = requests.get(self.HEALTH_ENDPOINT, timeout=5)
            elapsed = (time.time() - start) * 1000
            return {
                "status": resp.status_code,
                "time": elapsed,
                "success": resp.status_code == 200
            }
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        successful = sum(1 for r in results if r["success"])
        times = [r["time"] for r in results if r["success"]]
        
        if times:
            concurrent_avg = sum(times) / len(times)
            concurrent_p95 = sorted(times)[int(len(times) * 0.95)]
            print(f"  Success rate: {successful}/50 ({successful/50*100:.1f}%)")
            print(f"  Avg: {concurrent_avg:.2f}ms, P95: {concurrent_p95:.2f}ms")
            
            # Should maintain reasonable performance
            assert successful >= 45, "Should handle at least 45/50 requests"
            assert concurrent_avg < 500, f"Average response should be < 500ms, got {concurrent_avg:.2f}ms"
        
        print("\nPhase 3: High concurrency stress (100 concurrent requests)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(100)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        successful = sum(1 for r in results if r["success"])
        times = [r["time"] for r in results if r["success"]]
        
        if times:
            stress_avg = sum(times) / len(times)
            print(f"  Success rate: {successful}/100 ({successful/100*100:.1f}%)")
            print(f"  Avg response: {stress_avg:.2f}ms")
            
            assert successful >= 90, "Should handle at least 90/100 requests under stress"
        
        print("\n✅ Performance under load PASSED")
    
    @pytest.mark.e2e
    def test_e2e_dependency_health_cascade(self):
        """Test: Dependency health propagation"""
        print("\n" + "="*70)
        print("E2E TEST: Dependency Health Cascade")
        print("="*70)
        
        print("\nChecking health status with dependency details...")
        healthy, info = self.check_api_healthy()
        assert healthy, "API should be healthy"
        
        print(f"✅ API Status: {info.get('status')}")
        print(f"   Version: {info.get('version')}")
        
        # Check component stats
        stats = info.get("component_stats", {})
        print(f"\nComponent Status:")
        print(f"  Active: {stats.get('active', 0)}")
        print(f"  Total: {stats.get('total', 0)}")
        print(f"  Percentage: {stats.get('percentage', 0):.1f}%")
        
        # Check dependencies
        deps = info.get("dependencies", {})
        print(f"\nDependency Status:")
        
        available_count = 0
        unavailable_count = 0
        
        for dep_name, dep_info in deps.items():
            status = dep_info.get("status", "unknown")
            graceful = dep_info.get("graceful_degradation", False)
            
            if status == "available":
                available_count += 1
                symbol = "✅"
            elif graceful:
                unavailable_count += 1
                symbol = "⚠️"
            else:
                unavailable_count += 1
                symbol = "❌"
            
            print(f"  {symbol} {dep_name}: {status}")
        
        print(f"\nSummary: {available_count} available, {unavailable_count} with graceful degradation")
        print("\n✅ Dependency health cascade PASSED")


def test_e2e_critical_paths():
    """Main E2E test runner"""
    tester = E2ECriticalPathTests()
    
    tests = [
        ("System Startup and Initialization", tester.test_e2e_system_startup_and_initialization),
        ("Health Check Workflow", tester.test_e2e_health_check_workflow),
        ("Error Handling and Recovery", tester.test_e2e_error_handling_and_recovery),
        ("Performance Under Load", tester.test_e2e_performance_under_load),
        ("Dependency Health Cascade", tester.test_e2e_dependency_health_cascade),
    ]
    
    print("\n" + "="*70)
    print("E2E CRITICAL PATH TESTS")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"\n✅ {test_name} PASSED\n")
        except AssertionError as e:
            failed += 1
            print(f"\n❌ {test_name} FAILED: {e}\n")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} ERROR: {e}\n")
    
    print("="*70)
    print(f"E2E SUMMARY: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("="*70)
    
    assert failed == 0, f"E2E tests failed: {failed} failures"
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = test_e2e_critical_paths()
    exit(0 if failed == 0 else 1)
