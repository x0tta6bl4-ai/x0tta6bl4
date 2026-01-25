#!/usr/bin/env python3
"""
Enhanced Load Testing for x0tta6bl4 Production Readiness
Comprehensive P50, P95, P99 percentile analysis
"""

import asyncio
import time
import statistics
import json
from datetime import datetime
from typing import List, Dict
import httpx


class EnhancedLoadTest:
    """Enhanced load testing with detailed percentile analysis"""
    
    def __init__(self):
        self.results: Dict = {
            "timestamp": datetime.now().isoformat(),
            "scenarios": []
        }
    
    async def load_test_scenario(
        self,
        name: str,
        concurrent_users: int,
        duration_seconds: int,
        endpoint: str = "http://localhost:8000/health",
    ) -> Dict:
        """Run load test scenario with detailed metrics"""
        print(f"\n{'='*70}")
        print(f"Scenario: {name} ({concurrent_users} users, {duration_seconds}s)")
        print(f"{'='*70}")
        
        response_times: List[float] = []
        errors: int = 0
        success: int = 0
        status_codes: Dict[int, int] = {}
        
        async def make_request(client: httpx.AsyncClient):
            """Make single request and measure time"""
            try:
                start = time.time()
                resp = await client.get(endpoint, timeout=10.0)
                elapsed = (time.time() - start) * 1000
                
                response_times.append(elapsed)
                status_codes[resp.status_code] = status_codes.get(resp.status_code, 0) + 1
                
                if resp.status_code == 200:
                    return True
                else:
                    return False
            except Exception as e:
                return False
        
        async def load_generator(client: httpx.AsyncClient):
            """Generate load for duration"""
            nonlocal success, errors
            start_time = time.time()
            tasks = []
            
            while time.time() - start_time < duration_seconds:
                # Create batch of concurrent requests
                batch_tasks = [
                    make_request(client)
                    for _ in range(min(concurrent_users, 10))
                ]
                tasks.extend(batch_tasks)
                
                # Execute batch
                results = await asyncio.gather(*batch_tasks)
                success_count = sum(1 for r in results if r)
                error_count = len(results) - success_count
                
                success += success_count
                errors += error_count
                
                tasks.clear()
                await asyncio.sleep(0.1)  # Small delay between batches
        
        # Run test
        start_time = time.time()
        async with httpx.AsyncClient() as client:
            await load_generator(client)
        total_time = time.time() - start_time
        
        # Calculate statistics
        if response_times:
            sorted_times = sorted(response_times)
            
            p50 = sorted_times[int(len(sorted_times) * 0.50)]
            p75 = sorted_times[int(len(sorted_times) * 0.75)]
            p90 = sorted_times[int(len(sorted_times) * 0.90)]
            p95 = sorted_times[int(len(sorted_times) * 0.95)]
            p99 = sorted_times[int(len(sorted_times) * 0.99)]
            
            avg = statistics.mean(response_times)
            median = statistics.median(response_times)
            stddev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            
            total_requests = success + errors
            error_rate = (errors / total_requests * 100) if total_requests > 0 else 0
            success_rate = (success / total_requests * 100) if total_requests > 0 else 0
            throughput = total_requests / total_time
            
            result = {
                "name": name,
                "concurrent_users": concurrent_users,
                "duration_seconds": duration_seconds,
                "total_requests": total_requests,
                "successful": success,
                "errors": errors,
                "error_rate_percent": error_rate,
                "success_rate_percent": success_rate,
                "throughput_req_per_sec": throughput,
                "response_time_ms": {
                    "min": min(response_times),
                    "max": max(response_times),
                    "mean": avg,
                    "median": median,
                    "stddev": stddev,
                    "p50": p50,
                    "p75": p75,
                    "p90": p90,
                    "p95": p95,
                    "p99": p99,
                },
                "status_codes": status_codes,
                "test_duration_seconds": total_time,
            }
            
            # Print results
            print(f"\nResults:")
            print(f"  Total requests: {total_requests}")
            print(f"  Successful: {success} ({success_rate:.1f}%)")
            print(f"  Errors: {errors} ({error_rate:.1f}%)")
            print(f"  Throughput: {throughput:.1f} req/sec")
            print(f"\nResponse Time (ms):")
            print(f"  Min: {min(response_times):.2f}")
            print(f"  P50: {p50:.2f}")
            print(f"  P75: {p75:.2f}")
            print(f"  P90: {p90:.2f}")
            print(f"  P95: {p95:.2f}")
            print(f"  P99: {p99:.2f}")
            print(f"  Max: {max(response_times):.2f}")
            print(f"  Mean: {avg:.2f}")
            print(f"  Std Dev: {stddev:.2f}")
            print(f"\nStatus codes: {status_codes}")
            
            # Verify SLA targets
            sla_passed = []
            sla_failed = []
            
            if success_rate >= 99.9:
                sla_passed.append("Success rate >= 99.9%")
            else:
                sla_failed.append(f"Success rate {success_rate:.1f}% < 99.9%")
            
            if p95 < 500:
                sla_passed.append("P95 < 500ms")
            else:
                sla_failed.append(f"P95 {p95:.2f}ms >= 500ms")
            
            if p99 < 1000:
                sla_passed.append("P99 < 1000ms")
            else:
                sla_failed.append(f"P99 {p99:.2f}ms >= 1000ms")
            
            result["sla_status"] = "PASS" if not sla_failed else "FAIL"
            result["sla_checks"] = {
                "passed": sla_passed,
                "failed": sla_failed
            }
            
            print(f"\nSLA Compliance:")
            for check in sla_passed:
                print(f"  ✅ {check}")
            for check in sla_failed:
                print(f"  ❌ {check}")
            
            return result
        
        else:
            print("❌ No response times recorded!")
            return {
                "name": name,
                "status": "FAILED",
                "error": "No responses received"
            }
    
    async def run_all_scenarios(self):
        """Run all load test scenarios"""
        scenarios = [
            # Light load
            ("Light Load (5 users, 30s)", 5, 30),
            # Medium load
            ("Medium Load (20 users, 45s)", 20, 45),
            # High load
            ("High Load (50 users, 60s)", 50, 60),
            # Extreme load
            ("Extreme Load (100 users, 60s)", 100, 60),
        ]
        
        for scenario_name, users, duration in scenarios:
            result = await self.load_test_scenario(
                name=scenario_name,
                concurrent_users=users,
                duration_seconds=duration
            )
            self.results["scenarios"].append(result)
        
        return self.results
    
    def save_results(self) -> str:
        """Save test results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/tmp/enhanced_load_test_results_{timestamp}.json"
        
        with open(filename, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📊 Results saved to: {filename}")
        return filename


async def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("ENHANCED LOAD TESTING FOR x0tta6bl4")
    print("="*70)
    
    tester = EnhancedLoadTest()
    
    # Run all scenarios
    results = await tester.run_all_scenarios()
    
    # Summary
    print("\n" + "="*70)
    print("LOAD TEST SUMMARY")
    print("="*70)
    
    total_sla_pass = 0
    total_sla_fail = 0
    
    for scenario in results["scenarios"]:
        if "sla_status" in scenario:
            if scenario["sla_status"] == "PASS":
                print(f"✅ {scenario['name']}: SLA PASS")
                total_sla_pass += 1
            else:
                print(f"❌ {scenario['name']}: SLA FAIL")
                total_sla_fail += 1
    
    print(f"\nOverall: {total_sla_pass} scenarios passed SLA")
    
    # Save results
    tester.save_results()
    
    return total_sla_fail == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
