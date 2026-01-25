"""
Phase 6: Load Testing Framework

Comprehensive load testing for ML-enhanced autonomic loop.
Tests throughput, latency, resource usage under sustained load.
"""

import asyncio
import time
import numpy as np
from typing import Dict, List, Any
from datetime import datetime
import statistics


class LoadTestConfig:
    """Load test configuration"""
    
    def __init__(
        self,
        duration_seconds: int = 60,
        target_throughput: int = 100,  # loops per second
        concurrent_tasks: int = 10,
        metrics_interval: int = 5  # Report every N seconds
    ):
        self.duration_seconds = duration_seconds
        self.target_throughput = target_throughput
        self.concurrent_tasks = concurrent_tasks
        self.metrics_interval = metrics_interval


class LoadTestResults:
    """Load test results container"""
    
    def __init__(self):
        self.total_iterations = 0
        self.total_time = 0.0
        self.latencies: List[float] = []
        self.errors = 0
        self.start_time = datetime.now()
        self.end_time: Any = None
        self.throughput_samples: List[float] = []
    
    def add_latency(self, latency_ms: float):
        self.latencies.append(latency_ms)
        self.total_iterations += 1
    
    def record_error(self):
        self.errors += 1
    
    def finalize(self):
        self.end_time = datetime.now()
        self.total_time = (self.end_time - self.start_time).total_seconds()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistical summary"""
        if not self.latencies:
            return {"error": "No latencies recorded"}
        
        return {
            "total_iterations": self.total_iterations,
            "total_time_seconds": self.total_time,
            "actual_throughput_ops_per_sec": self.total_iterations / self.total_time if self.total_time > 0 else 0,
            "total_errors": self.errors,
            "error_rate": self.errors / self.total_iterations if self.total_iterations > 0 else 0,
            "latency_stats": {
                "min_ms": float(np.min(self.latencies)),
                "max_ms": float(np.max(self.latencies)),
                "mean_ms": float(np.mean(self.latencies)),
                "median_ms": float(np.median(self.latencies)),
                "p95_ms": float(np.percentile(self.latencies, 95)),
                "p99_ms": float(np.percentile(self.latencies, 99)),
                "stdev_ms": float(np.std(self.latencies)),
            },
            "timestamp": datetime.now().isoformat()
        }


class LoadTester:
    """Load testing orchestrator"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.results = LoadTestResults()
        self.stop_flag = False
    
    async def generate_test_load(
        self,
        async_func,
        *args,
        **kwargs
    ) -> LoadTestResults:
        """
        Generate load by running async_func repeatedly
        
        Args:
            async_func: Async function to load test
            *args, **kwargs: Arguments for async_func
            
        Returns:
            LoadTestResults with statistics
        """
        self.results = LoadTestResults()
        self.stop_flag = False
        
        # Task queue for rate limiting
        async def rate_limited_task(task_id: int):
            while not self.stop_flag:
                try:
                    start = time.time()
                    await async_func(*args, **kwargs)
                    elapsed = (time.time() - start) * 1000  # ms
                    self.results.add_latency(elapsed)
                except Exception as e:
                    self.results.record_error()
        
        # Run concurrent tasks
        start_time = time.time()
        tasks = [
            asyncio.create_task(rate_limited_task(i))
            for i in range(self.config.concurrent_tasks)
        ]
        
        # Monitor for duration
        while time.time() - start_time < self.config.duration_seconds:
            await asyncio.sleep(1)
        
        # Stop all tasks
        self.stop_flag = True
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.results.finalize()
        return self.results
    
    def print_results(self, results: LoadTestResults):
        """Print formatted results"""
        stats = results.get_stats()
        
        print("\n" + "=" * 70)
        print("LOAD TEST RESULTS")
        print("=" * 70)
        print(f"Duration: {stats['total_time_seconds']:.1f}s")
        print(f"Total Iterations: {stats['total_iterations']}")
        print(f"Actual Throughput: {stats['actual_throughput_ops_per_sec']:.1f} ops/sec")
        print(f"Errors: {stats['total_errors']} ({stats['error_rate']*100:.1f}%)")
        print("\nLatency (ms):")
        lat = stats['latency_stats']
        print(f"  Min:    {lat['min_ms']:.2f}")
        print(f"  Max:    {lat['max_ms']:.2f}")
        print(f"  Mean:   {lat['mean_ms']:.2f}")
        print(f"  Median: {lat['median_ms']:.2f}")
        print(f"  P95:    {lat['p95_ms']:.2f}")
        print(f"  P99:    {lat['p99_ms']:.2f}")
        print(f"  StDev:  {lat['stdev_ms']:.2f}")
        print("=" * 70 + "\n")
        
        return stats


class StressTestConfig:
    """Stress test configuration"""
    
    def __init__(
        self,
        start_throughput: int = 50,
        max_throughput: int = 500,
        increment_per_minute: int = 50,
        error_threshold: float = 0.1  # 10% error rate
    ):
        self.start_throughput = start_throughput
        self.max_throughput = max_throughput
        self.increment_per_minute = increment_per_minute
        self.error_threshold = error_threshold


class StressTester:
    """Stress testing orchestrator (gradually increase load)"""
    
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.results: List[LoadTestResults] = []
    
    async def run_stress_test(
        self,
        async_func,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run stress test with gradually increasing load
        
        Args:
            async_func: Async function to stress test
            *args, **kwargs: Arguments for async_func
            
        Returns:
            Summary of stress test
        """
        current_throughput = self.config.start_throughput
        phase = 0
        
        while current_throughput <= self.config.max_throughput:
            print(f"\nStress Test Phase {phase}: {current_throughput} ops/sec")
            
            config = LoadTestConfig(
                duration_seconds=30,
                target_throughput=current_throughput,
                concurrent_tasks=max(1, current_throughput // 50)
            )
            
            tester = LoadTester(config)
            results = await tester.generate_test_load(async_func, *args, **kwargs)
            self.results.append(results)
            
            stats = results.get_stats()
            error_rate = stats.get('error_rate', 0)
            
            if error_rate > self.config.error_threshold:
                print(f"ERROR THRESHOLD EXCEEDED: {error_rate*100:.1f}%")
                break
            
            current_throughput += self.config.increment_per_minute
            phase += 1
        
        return self._summarize_stress_test()
    
    def _summarize_stress_test(self) -> Dict[str, Any]:
        """Summarize stress test results"""
        max_throughput = 0
        max_stable_throughput = 0
        
        for results in self.results:
            stats = results.get_stats()
            throughput = stats['actual_throughput_ops_per_sec']
            error_rate = stats.get('error_rate', 0)
            
            max_throughput = max(max_throughput, throughput)
            
            if error_rate <= self.config.error_threshold:
                max_stable_throughput = max(max_stable_throughput, throughput)
        
        return {
            "phases_completed": len(self.results),
            "max_throughput_achieved": max_throughput,
            "max_stable_throughput": max_stable_throughput,
            "timestamp": datetime.now().isoformat()
        }


# Example usage functions

async def example_load_test():
    """Example load test"""
    from src.ml.integration import MLEnhancedMAPEK
    
    system = MLEnhancedMAPEK()
    
    async def autonomic_loop():
        metrics = {
            "cpu": 0.3 + np.random.random() * 0.3,
            "memory": 0.4 + np.random.random() * 0.2,
        }
        await system.autonomic_loop_iteration(
            metrics,
            ["scale_up", "optimize", "restart"]
        )
    
    config = LoadTestConfig(
        duration_seconds=60,
        target_throughput=100,
        concurrent_tasks=10
    )
    
    tester = LoadTester(config)
    results = await tester.generate_test_load(autonomic_loop)
    tester.print_results(results)
    
    return results


async def example_stress_test():
    """Example stress test"""
    from src.ml.integration import MLEnhancedMAPEK
    
    system = MLEnhancedMAPEK()
    
    async def autonomic_loop():
        metrics = {
            "cpu": 0.3 + np.random.random() * 0.3,
            "memory": 0.4 + np.random.random() * 0.2,
        }
        await system.autonomic_loop_iteration(
            metrics,
            ["scale_up", "optimize", "restart"]
        )
    
    config = StressTestConfig(
        start_throughput=50,
        max_throughput=300,
        increment_per_minute=50
    )
    
    tester = StressTester(config)
    summary = await tester.run_stress_test(autonomic_loop)
    
    print("\nStress Test Summary:")
    print(f"Max Throughput: {summary['max_throughput_achieved']:.1f} ops/sec")
    print(f"Max Stable: {summary['max_stable_throughput']:.1f} ops/sec")
    
    return summary


if __name__ == "__main__":
    print("Load Testing Framework for x0tta6bl4 v3.3.0")
