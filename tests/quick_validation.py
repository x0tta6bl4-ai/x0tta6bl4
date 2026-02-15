#!/usr/bin/env python3
"""Quick validation test suite for x0tta6bl4"""

import json
import time
from datetime import datetime

import requests


def test_health_endpoint():
    """Test health endpoint"""
    try:
        resp = requests.get("http://localhost:8000/health", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("status") == "ok", f"Health status: {data.get('status')}"
        return True, "Health check passed"
    except Exception as e:
        return False, f"Health check failed: {e}"


def test_metrics_endpoint():
    """Test Prometheus metrics endpoint"""
    try:
        resp = requests.get("http://localhost:9090/api/v1/query?query=up", timeout=5)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        assert data.get("status") == "success", f"Query status: {data.get('status')}"
        return True, "Metrics endpoint passed"
    except Exception as e:
        return False, f"Metrics endpoint failed: {e}"


def test_api_info():
    """Test API info endpoint"""
    try:
        resp = requests.get("http://localhost:8000/api/v1/info", timeout=5)
        # May return 404 if endpoint doesn't exist, but should not error
        return True, f"API info returned {resp.status_code}"
    except Exception as e:
        return False, f"API info failed: {e}"


def test_response_time():
    """Test response time performance"""
    try:
        times = []
        for i in range(10):
            start = time.time()
            resp = requests.get("http://localhost:8000/health", timeout=5)
            duration = (time.time() - start) * 1000
            times.append(duration)
            if resp.status_code != 200:
                return False, f"Bad status code: {resp.status_code}"

        avg = sum(times) / len(times)
        max_time = max(times)
        assert avg < 200, f"Average response time {avg:.2f}ms exceeds 200ms"
        assert max_time < 500, f"Max response time {max_time:.2f}ms exceeds 500ms"

        return True, f"Response time OK: avg={avg:.2f}ms, max={max_time:.2f}ms"
    except Exception as e:
        return False, f"Response time test failed: {e}"


def test_concurrent_requests():
    """Test handling concurrent requests"""
    try:
        import concurrent.futures

        def make_request():
            try:
                resp = requests.get("http://localhost:8000/health", timeout=5)
                return resp.status_code == 200
            except:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        success_rate = sum(results) / len(results)
        assert success_rate > 0.9, f"Success rate {success_rate:.1%} below 90%"

        return True, f"Concurrent requests OK: {sum(results)}/{len(results)} passed"
    except Exception as e:
        return False, f"Concurrent test failed: {e}"


def test_error_handling():
    """Test error handling"""
    try:
        # Test non-existent endpoint
        resp = requests.get("http://localhost:8000/nonexistent", timeout=5)
        assert resp.status_code in [
            404,
            405,
        ], f"Expected 404/405, got {resp.status_code}"

        return True, "Error handling OK"
    except Exception as e:
        return False, f"Error handling test failed: {e}"


def run_all_tests():
    """Run all tests and generate report"""
    tests = [
        ("Health Endpoint", test_health_endpoint),
        ("Metrics Endpoint", test_metrics_endpoint),
        ("API Info", test_api_info),
        ("Response Time", test_response_time),
        ("Concurrent Requests", test_concurrent_requests),
        ("Error Handling", test_error_handling),
    ]

    print("=" * 60)
    print("x0tta6bl4 Quick Validation Test Suite")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    print()

    results = []
    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"Running: {test_name}...", end=" ", flush=True)
        try:
            success, message = test_func()
            if success:
                print(f"✅ PASS - {message}")
                results.append((test_name, True, message))
                passed += 1
            else:
                print(f"❌ FAIL - {message}")
                results.append((test_name, False, message))
                failed += 1
        except Exception as e:
            print(f"❌ ERROR - {e}")
            results.append((test_name, False, str(e)))
            failed += 1
        time.sleep(0.5)

    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Total: {len(tests)}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Pass Rate: {(passed/len(tests)*100):.1f}%")
    print()

    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_tests": len(tests),
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / len(tests) * 100),
        "results": [
            {"test": name, "passed": success, "message": message}
            for name, success, message in results
        ],
    }

    with open("/tmp/quick_validation_results.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Results saved to: /tmp/quick_validation_results.json")
    print()
    print("=" * 60)
    print(f"Ended: {datetime.now().isoformat()}")
    print("=" * 60)

    return passed, failed


if __name__ == "__main__":
    passed, failed = run_all_tests()
    exit(0 if failed == 0 else 1)
