"""
Edge Computing Performance Benchmarks
=====================================

Comprehensive performance benchmarks for the Edge Computing module.

Run with: python -m benchmarks.edge_computing_benchmark
"""

import asyncio
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

# Benchmark results storage
@dataclass
class BenchmarkResult:
    """Single benchmark result."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    ops_per_second: float
    errors: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time_ms": round(self.total_time_ms, 3),
            "avg_time_ms": round(self.avg_time_ms, 3),
            "min_time_ms": round(self.min_time_ms, 3),
            "max_time_ms": round(self.max_time_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "ops_per_second": round(self.ops_per_second, 2),
            "errors": self.errors,
            "metadata": self.metadata
        }


def calculate_percentile(data: List[float], percentile: float) -> float:
    """Calculate percentile of sorted data."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    index = (len(sorted_data) - 1) * percentile / 100
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_data):
        return sorted_data[-1]
    weight = index - lower
    return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight


class EdgeComputingBenchmark:
    """Edge Computing module benchmarks."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    async def run_all(self) -> Dict[str, Any]:
        """Run all benchmarks."""
        print("=" * 60)
        print("Edge Computing Performance Benchmarks")
        print("=" * 60)
        print(f"Started: {datetime.utcnow().isoformat()}")
        print()

        # Import modules
        try:
            from src.edge.edge_node import EdgeNodeManager, EdgeNodeConfig, EdgeNodeStatus
            from src.edge.task_distributor import TaskDistributor, TaskDistributionStrategy
            from src.edge.edge_cache import EdgeCache, CachePolicy
            from src.resilience import TokenBucket, SemaphoreBulkhead
        except ImportError as e:
            print(f"Import error: {e}")
            return {"error": str(e)}

        # Run benchmarks
        await self._benchmark_node_registration()
        await self._benchmark_node_list()
        await self._benchmark_task_submission()
        await self._benchmark_task_status()
        await self._benchmark_cache_operations()
        await self._benchmark_rate_limiter()
        await self._benchmark_bulkhead()
        await self._benchmark_concurrent_operations()

        # Generate report
        return self._generate_report()

    async def _benchmark_node_registration(self):
        """Benchmark node registration performance."""
        print("Benchmarking node registration...")

        from src.edge.edge_node import EdgeNodeManager

        times = []
        errors = 0
        iterations = 100

        manager = EdgeNodeManager()

        for i in range(iterations):
            start = time.perf_counter()
            try:
                manager.register_node(
                    endpoint=f"https://node{i}.example.com:8443",
                    name=f"benchmark-node-{i}",
                    capabilities=["gpu", "inference"],
                    max_concurrent_tasks=10
                )
            except Exception:
                errors += 1
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="node_registration",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            errors=errors,
            metadata={"nodes_registered": iterations}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_node_list(self):
        """Benchmark node listing performance."""
        print("Benchmarking node listing...")

        from src.edge.edge_node import EdgeNodeManager

        times = []
        iterations = 100

        manager = EdgeNodeManager()
        # Pre-register nodes
        for i in range(50):
            manager.register_node(
                endpoint=f"https://node{i}.example.com:8443",
                name=f"node-{i}",
                capabilities=["gpu"]
            )

        for _ in range(iterations):
            start = time.perf_counter()
            manager.list_nodes()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="node_list",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"total_nodes": 50}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_task_submission(self):
        """Benchmark task submission performance."""
        print("Benchmarking task submission...")

        from src.edge.task_distributor import TaskDistributor, TaskDistributionStrategy

        times = []
        errors = 0
        iterations = 100

        distributor = TaskDistributor(strategy=TaskDistributionStrategy.ADAPTIVE)

        for i in range(iterations):
            start = time.perf_counter()
            try:
                distributor.distribute_task(
                    task_id=str(uuid4()),
                    task_type="inference",
                    payload={"prompt": f"test {i}"},
                    priority="normal"
                )
            except Exception:
                errors += 1
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="task_submission",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            errors=errors,
            metadata={"strategy": "adaptive"}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_task_status(self):
        """Benchmark task status retrieval."""
        print("Benchmarking task status...")

        from src.edge.task_distributor import TaskDistributor, TaskDistributionStrategy

        times = []
        iterations = 100

        distributor = TaskDistributor(strategy=TaskDistributionStrategy.ADAPTIVE)

        # Submit tasks first
        task_ids = []
        for i in range(50):
            result = distributor.distribute_task(
                task_id=str(uuid4()),
                task_type="test",
                payload={"data": i}
            )
            task_ids.append(result.get("task_id"))

        # Benchmark status retrieval
        for task_id in task_ids * 2:  # 100 iterations
            start = time.perf_counter()
            distributor.get_task_status(task_id)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="task_status",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"tasks_tracked": len(task_ids)}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_cache_operations(self):
        """Benchmark edge cache operations."""
        print("Benchmarking cache operations...")

        from src.edge.edge_cache import EdgeCache, CachePolicy

        cache = EdgeCache(max_size=10000, policy=CachePolicy.ADAPTIVE)

        # Benchmark SET
        set_times = []
        for i in range(100):
            start = time.perf_counter()
            cache.set(f"key-{i}", {"data": f"value-{i}"}, ttl_seconds=300)
            end = time.perf_counter()
            set_times.append((end - start) * 1000)

        result_set = BenchmarkResult(
            name="cache_set",
            iterations=100,
            total_time_ms=sum(set_times),
            avg_time_ms=statistics.mean(set_times),
            min_time_ms=min(set_times),
            max_time_ms=max(set_times),
            p50_ms=calculate_percentile(set_times, 50),
            p95_ms=calculate_percentile(set_times, 95),
            p99_ms=calculate_percentile(set_times, 99),
            ops_per_second=1000 / (sum(set_times) / 100)
        )
        self.results.append(result_set)
        print(f"  Cache SET: {result_set.avg_time_ms:.3f}ms, Ops/s: {result_set.ops_per_second:.2f}")

        # Benchmark GET
        get_times = []
        for i in range(100):
            start = time.perf_counter()
            cache.get(f"key-{i}")
            end = time.perf_counter()
            get_times.append((end - start) * 1000)

        result_get = BenchmarkResult(
            name="cache_get",
            iterations=100,
            total_time_ms=sum(get_times),
            avg_time_ms=statistics.mean(get_times),
            min_time_ms=min(get_times),
            max_time_ms=max(get_times),
            p50_ms=calculate_percentile(get_times, 50),
            p95_ms=calculate_percentile(get_times, 95),
            p99_ms=calculate_percentile(get_times, 99),
            ops_per_second=1000 / (sum(get_times) / 100)
        )
        self.results.append(result_get)
        print(f"  Cache GET: {result_get.avg_time_ms:.3f}ms, Ops/s: {result_get.ops_per_second:.2f}")

    async def _benchmark_rate_limiter(self):
        """Benchmark rate limiter performance."""
        print("Benchmarking rate limiter...")

        from src.resilience import TokenBucket

        limiter = TokenBucket(capacity=1000, refill_rate=100.0)

        times = []
        iterations = 10000

        for _ in range(iterations):
            start = time.perf_counter()
            limiter.acquire()
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="rate_limiter_acquire",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"algorithm": "token_bucket", "capacity": 1000}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.6f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_bulkhead(self):
        """Benchmark bulkhead performance."""
        print("Benchmarking bulkhead...")

        from src.resilience import SemaphoreBulkhead

        bulkhead = SemaphoreBulkhead(max_concurrent=100)

        times = []
        iterations = 1000

        def sample_operation():
            return {"result": "ok"}

        for _ in range(iterations):
            start = time.perf_counter()
            bulkhead.execute(sample_operation)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="bulkhead_execute",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"max_concurrent": 100}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_concurrent_operations(self):
        """Benchmark concurrent operations."""
        print("Benchmarking concurrent operations...")

        from src.edge.edge_cache import EdgeCache, CachePolicy

        cache = EdgeCache(max_size=10000, policy=CachePolicy.ADAPTIVE)

        async def cache_operation(i: int):
            start = time.perf_counter()
            cache.set(f"concurrent-key-{i}", {"data": i}, ttl_seconds=60)
            cache.get(f"concurrent-key-{i}")
            end = time.perf_counter()
            return (end - start) * 1000

        # Run 1000 concurrent operations
        iterations = 1000
        start_total = time.perf_counter()
        times = await asyncio.gather(*[cache_operation(i) for i in range(iterations)])
        end_total = time.perf_counter()

        result = BenchmarkResult(
            name="concurrent_cache_ops",
            iterations=iterations,
            total_time_ms=(end_total - start_total) * 1000,
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(list(times), 50),
            p95_ms=calculate_percentile(list(times), 95),
            p99_ms=calculate_percentile(list(times), 99),
            ops_per_second=iterations / ((end_total - start_total)),
            metadata={"concurrency": iterations}
        )
        self.results.append(result)
        print(f"  Total: {result.total_time_ms:.3f}ms for {iterations} ops, Ops/s: {result.ops_per_second:.2f}")

    def _generate_report(self) -> Dict[str, Any]:
        """Generate benchmark report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "module": "edge_computing",
            "version": "3.3.0",
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total_benchmarks": len(self.results),
                "total_errors": sum(r.errors for r in self.results),
                "fastest_op": min(self.results, key=lambda r: r.avg_time_ms).name,
                "slowest_op": max(self.results, key=lambda r: r.avg_time_ms).name
            }
        }

        print()
        print("=" * 60)
        print("Benchmark Summary")
        print("=" * 60)
        print(f"Total benchmarks: {report['summary']['total_benchmarks']}")
        print(f"Total errors: {report['summary']['total_errors']}")
        print(f"Fastest operation: {report['summary']['fastest_op']}")
        print(f"Slowest operation: {report['summary']['slowest_op']}")
        print()

        return report


async def main():
    """Run benchmarks."""
    benchmark = EdgeComputingBenchmark()
    report = await benchmark.run_all()

    # Save report
    import json
    from pathlib import Path

    output_dir = Path("benchmarks/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"edge_computing_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
