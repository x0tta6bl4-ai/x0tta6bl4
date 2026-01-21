#!/usr/bin/env python3
"""
Phase 6: Load Testing Execution Scripts

Run comprehensive load and stress tests on x0tta6bl4 v3.3.0
"""

import asyncio
import sys
import json
import numpy as np
from datetime import datetime

# Add project to path
sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from tests.load.load_testing_framework import (
    LoadTestConfig, LoadTester, StressTestConfig, StressTester
)
from src.ml.integration import MLEnhancedMAPEK


class Phase6LoadTestRunner:
    """Orchestrates Phase 6 load testing"""
    
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()
    
    async def run_baseline_test(self):
        """Test 1: Baseline performance (100 loops)"""
        print("\n" + "="*70)
        print("TEST 1: BASELINE PERFORMANCE (100 autonomic loops)")
        print("="*70)
        
        system = MLEnhancedMAPEK()
        
        async def autonomic_loop():
            await system.autonomic_loop_iteration(
                {
                    "cpu": 0.3 + np.random.random() * 0.3,
                    "memory": 0.4 + np.random.random() * 0.2,
                    "latency_ms": 40 + np.random.random() * 20
                },
                ["scale_up", "optimize", "restart"]
            )
        
        config = LoadTestConfig(
            duration_seconds=30,
            target_throughput=50,
            concurrent_tasks=5
        )
        
        tester = LoadTester(config)
        results = await tester.generate_test_load(autonomic_loop)
        stats = tester.print_results(results)
        
        self.results['baseline'] = stats
        return stats
    
    async def run_throughput_test(self):
        """Test 2: Throughput test (sustained load)"""
        print("\n" + "="*70)
        print("TEST 2: THROUGHPUT TEST (Sustained 100+ ops/sec)")
        print("="*70)
        
        system = MLEnhancedMAPEK()
        
        async def autonomic_loop():
            await system.autonomic_loop_iteration(
                {
                    "cpu": 0.5,
                    "memory": 0.6,
                    "latency_ms": 50
                },
                ["scale_up", "optimize", "restart"]
            )
        
        config = LoadTestConfig(
            duration_seconds=60,
            target_throughput=100,
            concurrent_tasks=10
        )
        
        tester = LoadTester(config)
        results = await tester.generate_test_load(autonomic_loop)
        stats = tester.print_results(results)
        
        self.results['throughput'] = stats
        return stats
    
    async def run_high_concurrency_test(self):
        """Test 3: High concurrency test"""
        print("\n" + "="*70)
        print("TEST 3: HIGH CONCURRENCY TEST (50 concurrent tasks)")
        print("="*70)
        
        system = MLEnhancedMAPEK()
        
        async def autonomic_loop():
            await system.autonomic_loop_iteration(
                {
                    "cpu": 0.2 + np.random.random() * 0.5,
                    "memory": 0.3 + np.random.random() * 0.4,
                },
                ["scale_up", "optimize"]
            )
        
        config = LoadTestConfig(
            duration_seconds=45,
            target_throughput=200,
            concurrent_tasks=50
        )
        
        tester = LoadTester(config)
        results = await tester.generate_test_load(autonomic_loop)
        stats = tester.print_results(results)
        
        self.results['concurrency'] = stats
        return stats
    
    async def run_stress_test(self):
        """Test 4: Stress test (gradually increasing load)"""
        print("\n" + "="*70)
        print("TEST 4: STRESS TEST (Ramping from 50 to 300 ops/sec)")
        print("="*70)
        
        system = MLEnhancedMAPEK()
        
        async def autonomic_loop():
            await system.autonomic_loop_iteration(
                {
                    "cpu": np.random.random(),
                    "memory": np.random.random(),
                },
                ["scale_up", "optimize", "restart"]
            )
        
        config = StressTestConfig(
            start_throughput=50,
            max_throughput=300,
            increment_per_minute=50
        )
        
        tester = StressTester(config)
        summary = await tester.run_stress_test(autonomic_loop)
        
        print(f"\nStress Test Summary:")
        print(f"  Max Throughput Achieved: {summary['max_throughput_achieved']:.1f} ops/sec")
        print(f"  Max Stable Throughput: {summary['max_stable_throughput']:.1f} ops/sec")
        
        self.results['stress'] = summary
        return summary
    
    async def run_latency_consistency_test(self):
        """Test 5: Latency consistency under varying load"""
        print("\n" + "="*70)
        print("TEST 5: LATENCY CONSISTENCY TEST")
        print("="*70)
        
        system = MLEnhancedMAPEK()
        latencies_by_load = {}
        
        for load_level in [50, 100, 150, 200]:
            print(f"\n  Testing at {load_level} ops/sec...")
            
            async def autonomic_loop():
                await system.autonomic_loop_iteration(
                    {"cpu": 0.5, "memory": 0.6},
                    ["scale_up", "optimize"]
                )
            
            config = LoadTestConfig(
                duration_seconds=20,
                target_throughput=load_level,
                concurrent_tasks=max(1, load_level // 50)
            )
            
            tester = LoadTester(config)
            results = await tester.generate_test_load(autonomic_loop)
            stats = results.get_stats()
            
            latencies_by_load[load_level] = {
                "mean": stats['latency_stats']['mean_ms'],
                "p95": stats['latency_stats']['p95_ms'],
                "p99": stats['latency_stats']['p99_ms'],
            }
            
            print(f"    Mean: {stats['latency_stats']['mean_ms']:.2f}ms, "
                  f"P95: {stats['latency_stats']['p95_ms']:.2f}ms, "
                  f"P99: {stats['latency_stats']['p99_ms']:.2f}ms")
        
        self.results['latency_consistency'] = latencies_by_load
        return latencies_by_load
    
    def generate_summary_report(self):
        """Generate comprehensive summary report"""
        print("\n" + "="*70)
        print("PHASE 6 LOAD TEST SUMMARY REPORT")
        print("="*70)
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "duration": str(datetime.now() - self.start_time),
            "tests_completed": len(self.results),
            "results": {}
        }
        
        # Baseline
        if 'baseline' in self.results:
            baseline = self.results['baseline']
            print(f"\n✅ BASELINE TEST:")
            print(f"   Throughput: {baseline.get('actual_throughput_ops_per_sec', 0):.1f} ops/sec")
            print(f"   Mean Latency: {baseline['latency_stats']['mean_ms']:.2f}ms")
            print(f"   P99 Latency: {baseline['latency_stats']['p99_ms']:.2f}ms")
            summary['results']['baseline'] = baseline
        
        # Throughput
        if 'throughput' in self.results:
            throughput = self.results['throughput']
            print(f"\n✅ THROUGHPUT TEST:")
            print(f"   Achieved: {throughput.get('actual_throughput_ops_per_sec', 0):.1f} ops/sec")
            print(f"   Error Rate: {throughput.get('error_rate', 0)*100:.1f}%")
            summary['results']['throughput'] = throughput
        
        # Concurrency
        if 'concurrency' in self.results:
            concurrency = self.results['concurrency']
            print(f"\n✅ CONCURRENCY TEST (50 concurrent):")
            print(f"   Throughput: {concurrency.get('actual_throughput_ops_per_sec', 0):.1f} ops/sec")
            print(f"   Total Iterations: {concurrency['total_iterations']}")
            summary['results']['concurrency'] = concurrency
        
        # Stress
        if 'stress' in self.results:
            stress = self.results['stress']
            print(f"\n✅ STRESS TEST:")
            print(f"   Max Throughput: {stress['max_throughput_achieved']:.1f} ops/sec")
            print(f"   Max Stable: {stress['max_stable_throughput']:.1f} ops/sec")
            print(f"   Phases: {stress['phases_completed']}")
            summary['results']['stress'] = stress
        
        # Latency Consistency
        if 'latency_consistency' in self.results:
            print(f"\n✅ LATENCY CONSISTENCY:")
            for load, latencies in self.results['latency_consistency'].items():
                print(f"   @ {load} ops/sec: Mean={latencies['mean']:.2f}ms, "
                      f"P95={latencies['p95']:.2f}ms")
            summary['results']['latency_consistency'] = self.results['latency_consistency']
        
        print("\n" + "="*70)
        
        return summary
    
    async def run_all_tests(self):
        """Run complete test suite"""
        try:
            await self.run_baseline_test()
            await self.run_throughput_test()
            await self.run_high_concurrency_test()
            await self.run_stress_test()
            await self.run_latency_consistency_test()
            
            summary = self.generate_summary_report()
            return summary
        
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()
            return None


async def main():
    """Main entry point"""
    runner = Phase6LoadTestRunner()
    summary = await runner.run_all_tests()
    
    if summary:
        # Save results to file
        with open('/mnt/AC74CC2974CBF3DC/PHASE_6_LOAD_TEST_RESULTS.json', 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"\n📊 Results saved to PHASE_6_LOAD_TEST_RESULTS.json")
        print(f"✅ All tests completed successfully!")
    else:
        print(f"\n❌ Tests failed")
        sys.exit(1)


if __name__ == "__main__":
    print("Phase 6: Load Testing Suite")
    print("x0tta6bl4 v3.3.0 - Production Readiness Validation")
    print(f"Started: {datetime.now().isoformat()}")
    
    asyncio.run(main())
