#!/usr/bin/env python3
"""
Advanced Chaos Engineering Scenarios
Tests complex failure scenarios and cascading failures
"""

import subprocess
import time
import requests
import json
from datetime import datetime
from typing import Dict, List, Tuple
import concurrent.futures


class AdvancedChaosTests:
    """Advanced chaos engineering tests"""
    
    CONTAINERS = {
        "api": "x0tta6bl4-api",
        "db": "x0tta6bl4-db",
        "redis": "x0tta6bl4-redis",
        "prometheus": "x0tta6bl4-prometheus",
        "grafana": "x0tta6bl4-grafana",
    }
    
    API_URL = "http://localhost:8000"
    HEALTH_ENDPOINT = f"{API_URL}/health"
    
    def __init__(self):
        self.results: List[Dict] = []
        self.start_time = datetime.now()
    
    def execute_cmd(self, cmd: str) -> Tuple[int, str, str]:
        """Execute command and return code, stdout, stderr"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return -1, "", str(e)
    
    def get_container_status(self, container: str) -> str:
        """Get container status"""
        code, stdout, _ = self.execute_cmd(
            f"docker ps --filter 'name={container}' --format '{{{{.State}}}}'"
        )
        return stdout.strip() if code == 0 else "unknown"
    
    def stop_container(self, container: str, delay: int = 0) -> bool:
        """Stop a container"""
        if delay > 0:
            time.sleep(delay)
        code, _, _ = self.execute_cmd(f"docker stop {container}")
        return code == 0
    
    def start_container(self, container: str) -> bool:
        """Start a container"""
        code, _, _ = self.execute_cmd(f"docker start {container}")
        return code == 0
    
    def check_health(self) -> Tuple[bool, int]:
        """Check API health"""
        try:
            resp = requests.get(self.HEALTH_ENDPOINT, timeout=3)
            return resp.status_code == 200, resp.status_code
        except:
            return False, 0
    
    def measure_recovery_time(self, timeout: int = 120) -> float:
        """Measure recovery time"""
        start = time.time()
        while time.time() - start < timeout:
            healthy, _ = self.check_health()
            if healthy:
                return time.time() - start
            time.sleep(1)
        return -1
    
    def test_cascading_failure_scenario(self):
        """Test cascading failure: DB -> Cache -> API"""
        print("\n" + "="*70)
        print("TEST: Cascading Failure Scenario (DB → Cache → API)")
        print("="*70)
        
        test_result = {
            "name": "Cascading Failure",
            "timestamp": datetime.now().isoformat(),
            "stages": []
        }
        
        try:
            # Stage 1: Stop DB
            print("\nStage 1: Stopping Database...")
            self.stop_container(self.CONTAINERS["db"])
            time.sleep(2)
            
            db_state = self.get_container_status(self.CONTAINERS["db"])
            print(f"  Database state: {db_state}")
            test_result["stages"].append({"stage": "DB stopped", "state": db_state})
            
            # Stage 2: Stop Cache
            print("\nStage 2: Stopping Cache...")
            self.stop_container(self.CONTAINERS["redis"])
            time.sleep(2)
            
            redis_state = self.get_container_status(self.CONTAINERS["redis"])
            print(f"  Cache state: {redis_state}")
            test_result["stages"].append({"stage": "Cache stopped", "state": redis_state})
            
            # Check API status
            healthy, status = self.check_health()
            print(f"  API status during cascade: {status} ({'healthy' if healthy else 'unhealthy'})")
            test_result["stages"].append({
                "stage": "API check",
                "status": status,
                "healthy": healthy
            })
            
            # Stage 3: Recover Cache first
            print("\nStage 3: Recovering Cache...")
            self.start_container(self.CONTAINERS["redis"])
            time.sleep(2)
            
            redis_state = self.get_container_status(self.CONTAINERS["redis"])
            print(f"  Cache state: {redis_state}")
            test_result["stages"].append({"stage": "Cache recovered", "state": redis_state})
            
            # Stage 4: Recover DB
            print("\nStage 4: Recovering Database...")
            self.start_container(self.CONTAINERS["db"])
            recovery_time = self.measure_recovery_time(timeout=120)
            
            if recovery_time > 0:
                print(f"  Database recovery time: {recovery_time:.2f}s")
                healthy, status = self.check_health()
                print(f"  API status after full recovery: {status}")
                test_result["stages"].append({
                    "stage": "DB recovered",
                    "recovery_time": recovery_time,
                    "api_status": status,
                    "healthy": healthy
                })
                
                assert healthy, "API should be healthy after full recovery"
                print("\n✅ Cascading failure recovery SUCCESSFUL")
            else:
                print("  Recovery timeout!")
                test_result["stages"].append({
                    "stage": "Recovery timeout",
                    "error": "Recovery exceeded timeout"
                })
                raise AssertionError("Recovery timeout exceeded")
            
            self.results.append(test_result)
            return True
            
        except Exception as e:
            print(f"❌ Cascading failure test FAILED: {e}")
            test_result["error"] = str(e)
            self.results.append(test_result)
            raise
    
    def test_sequential_pod_failures(self):
        """Test system behavior with sequential pod failures"""
        print("\n" + "="*70)
        print("TEST: Sequential Pod Failures")
        print("="*70)
        
        test_result = {
            "name": "Sequential Pod Failures",
            "timestamp": datetime.now().isoformat(),
            "failures": []
        }
        
        try:
            containers_to_test = [
                self.CONTAINERS["redis"],
                self.CONTAINERS["db"],
            ]
            
            for container in containers_to_test:
                print(f"\nFailing: {container}...")
                
                # Verify health before failure
                healthy_before, _ = self.check_health()
                print(f"  Health before: {'✅' if healthy_before else '❌'}")
                
                # Cause failure
                self.stop_container(container)
                time.sleep(2)
                
                # Check impact
                healthy_during, status = self.check_health()
                print(f"  Health during: {status} ({'✅' if healthy_during else '❌'})")
                
                # Recover
                self.start_container(container)
                recovery_time = self.measure_recovery_time(timeout=60)
                
                if recovery_time > 0:
                    print(f"  Recovery time: {recovery_time:.2f}s")
                    healthy_after, _ = self.check_health()
                    print(f"  Health after: {'✅' if healthy_after else '❌'}")
                    
                    test_result["failures"].append({
                        "container": container,
                        "recovery_time": recovery_time,
                        "recovered": healthy_after
                    })
                    
                    assert healthy_after, f"API should recover after {container} restart"
                else:
                    raise AssertionError(f"Recovery timeout for {container}")
            
            self.results.append(test_result)
            print("\n✅ Sequential pod failures handled correctly")
            return True
            
        except Exception as e:
            print(f"❌ Sequential pod test FAILED: {e}")
            test_result["error"] = str(e)
            self.results.append(test_result)
            raise
    
    def test_high_load_during_recovery(self):
        """Test system under load during failure recovery"""
        print("\n" + "="*70)
        print("TEST: High Load During Recovery")
        print("="*70)
        
        test_result = {
            "name": "High Load During Recovery",
            "timestamp": datetime.now().isoformat(),
        }
        
        try:
            # Function to make requests under load
            def make_requests(num_requests: int = 100) -> Dict:
                def single_request():
                    try:
                        resp = requests.get(self.HEALTH_ENDPOINT, timeout=5)
                        return {
                            "success": resp.status_code == 200,
                            "status": resp.status_code,
                            "time": resp.elapsed.total_seconds() * 1000
                        }
                    except:
                        return {"success": False}
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                    futures = [executor.submit(single_request) for _ in range(num_requests)]
                    results = [f.result() for f in concurrent.futures.as_completed(futures)]
                
                successful = sum(1 for r in results if r["success"])
                return {
                    "total": len(results),
                    "successful": successful,
                    "success_rate": successful / len(results) * 100
                }
            
            # Normal load baseline
            print("\nPhase 1: Baseline load (50 requests)...")
            baseline = make_requests(50)
            print(f"  Success rate: {baseline['success_rate']:.1f}%")
            test_result["baseline"] = baseline
            
            # Induce failure
            print("\nPhase 2: Stopping database while handling load...")
            self.stop_container(self.CONTAINERS["db"])
            
            # Maintain load during failure
            time.sleep(1)
            failed_load = make_requests(50)
            print(f"  Success rate during failure: {failed_load['success_rate']:.1f}%")
            test_result["during_failure"] = failed_load
            
            # Start recovery with load
            print("\nPhase 3: Recovering database while handling load...")
            self.start_container(self.CONTAINERS["db"])
            
            recovering_load = make_requests(100)
            print(f"  Success rate during recovery: {recovering_load['success_rate']:.1f}%")
            test_result["during_recovery"] = recovering_load
            
            # Verify full recovery
            time.sleep(5)
            recovered = make_requests(50)
            print(f"  Success rate after recovery: {recovered['success_rate']:.1f}%")
            test_result["after_recovery"] = recovered
            
            # Assertions
            assert baseline["success_rate"] >= 90, "Baseline success rate too low"
            assert recovered["success_rate"] >= 90, "Recovery success rate too low"
            
            self.results.append(test_result)
            print("\n✅ High load during recovery handled successfully")
            return True
            
        except Exception as e:
            print(f"❌ High load test FAILED: {e}")
            test_result["error"] = str(e)
            self.results.append(test_result)
            raise
    
    def test_rapid_restart_cycles(self):
        """Test system resilience with rapid restart cycles"""
        print("\n" + "="*70)
        print("TEST: Rapid Restart Cycles (Redis)")
        print("="*70)
        
        test_result = {
            "name": "Rapid Restart Cycles",
            "timestamp": datetime.now().isoformat(),
            "cycles": []
        }
        
        try:
            num_cycles = 5
            
            for cycle in range(num_cycles):
                print(f"\nCycle {cycle + 1}/{num_cycles}:")
                
                # Stop
                print(f"  Stopping Redis...")
                self.stop_container(self.CONTAINERS["redis"])
                time.sleep(1)
                
                # Start
                print(f"  Starting Redis...")
                self.start_container(self.CONTAINERS["redis"])
                
                # Verify
                recovery_time = self.measure_recovery_time(timeout=30)
                healthy, _ = self.check_health()
                
                print(f"  Recovery time: {recovery_time:.2f}s if successful, healthy: {healthy}")
                
                test_result["cycles"].append({
                    "cycle": cycle + 1,
                    "recovery_time": recovery_time if recovery_time > 0 else None,
                    "recovered": healthy
                })
                
                if recovery_time < 0:
                    raise AssertionError(f"Cycle {cycle + 1} recovery timeout")
                
                time.sleep(2)  # Wait before next cycle
            
            self.results.append(test_result)
            print(f"\n✅ All {num_cycles} rapid restart cycles SUCCESSFUL")
            return True
            
        except Exception as e:
            print(f"❌ Rapid restart test FAILED: {e}")
            test_result["error"] = str(e)
            self.results.append(test_result)
            raise
    
    def generate_report(self) -> str:
        """Generate test report"""
        report = {
            "test_suite": "Advanced Chaos Engineering",
            "started": self.start_time.isoformat(),
            "completed": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_tests": len(self.results),
            "results": self.results
        }
        
        # Save to file
        filename = f"/tmp/advanced_chaos_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
        
        return filename


def run_advanced_chaos_tests():
    """Execute all advanced chaos tests"""
    tester = AdvancedChaosTests()
    
    tests = [
        ("Cascading Failure Scenario", tester.test_cascading_failure_scenario),
        ("Sequential Pod Failures", tester.test_sequential_pod_failures),
        ("High Load During Recovery", tester.test_high_load_during_recovery),
        ("Rapid Restart Cycles", tester.test_rapid_restart_cycles),
    ]
    
    print("\n" + "="*70)
    print("ADVANCED CHAOS ENGINEERING TEST SUITE")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"Test failed: {e}")
    
    # Generate report
    report_file = tester.generate_report()
    
    print("\n" + "="*70)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print(f"Report saved to: {report_file}")
    print("="*70)
    
    return failed == 0


if __name__ == "__main__":
    success = run_advanced_chaos_tests()
    exit(0 if success else 1)
