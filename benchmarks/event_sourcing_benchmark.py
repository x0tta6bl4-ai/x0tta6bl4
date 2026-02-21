"""
Event Sourcing Performance Benchmarks
======================================

Comprehensive performance benchmarks for the Event Sourcing module.

Run with: python -m benchmarks.event_sourcing_benchmark
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


class EventSourcingBenchmark:
    """Event Sourcing module benchmarks."""

    def __init__(self):
        self.results: List[BenchmarkResult] = []

    async def run_all(self) -> Dict[str, Any]:
        """Run all benchmarks."""
        print("=" * 60)
        print("Event Sourcing Performance Benchmarks")
        print("=" * 60)
        print(f"Started: {datetime.utcnow().isoformat()}")
        print()

        # Import modules
        try:
            from src.event_sourcing.event_store import EventStore, Event
            from src.event_sourcing.command_bus import CommandBus, Command
            from src.event_sourcing.query_bus import QueryBus, Query
            from src.event_sourcing.projection import ProjectionManager
            from src.event_sourcing.aggregate import AggregateRoot, Repository
            from src.resilience import TokenBucket, SemaphoreBulkhead
        except ImportError as e:
            print(f"Import error: {e}")
            return {"error": str(e)}

        # Run benchmarks
        await self._benchmark_event_append()
        await self._benchmark_event_read()
        await self._benchmark_stream_read()
        await self._benchmark_command_execution()
        await self._benchmark_query_execution()
        await self._benchmark_projection_processing()
        await self._benchmark_aggregate_rebuild()
        await self._benchmark_concurrent_appends()
        await self._benchmark_resilience_overhead()

        # Generate report
        return self._generate_report()

    async def _benchmark_event_append(self):
        """Benchmark event append performance."""
        print("Benchmarking event append...")

        from src.event_sourcing.event_store import EventStore, Event

        store = EventStore()
        times = []
        errors = 0
        iterations = 100

        for i in range(iterations):
            stream_id = f"stream-{i % 10}"  # 10 streams
            event = Event(
                event_id=uuid4(),
                event_type="TestEvent",
                stream_id=stream_id,
                version=0,
                timestamp=datetime.utcnow(),
                payload={"index": i, "data": f"test data {i}"},
                metadata={"benchmark": True}
            )

            start = time.perf_counter()
            try:
                store.append(stream_id, [event])
            except Exception:
                errors += 1
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="event_append",
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
            metadata={"streams": 10, "events_per_append": 1}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_event_read(self):
        """Benchmark event read performance."""
        print("Benchmarking event read...")

        from src.event_sourcing.event_store import EventStore, Event

        store = EventStore()

        # Pre-populate events
        stream_id = "benchmark-stream"
        for i in range(100):
            event = Event(
                event_id=uuid4(),
                event_type="TestEvent",
                stream_id=stream_id,
                version=i + 1,
                timestamp=datetime.utcnow(),
                payload={"index": i}
            )
            store.append(stream_id, [event])

        times = []
        iterations = 100

        for _ in range(iterations):
            start = time.perf_counter()
            store.read_stream(stream_id, limit=50)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="event_read",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"events_in_stream": 100, "read_limit": 50}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_stream_read(self):
        """Benchmark reading from multiple streams."""
        print("Benchmarking multi-stream read...")

        from src.event_sourcing.event_store import EventStore, Event

        store = EventStore()

        # Pre-populate multiple streams
        stream_ids = [f"multi-stream-{i}" for i in range(20)]
        for stream_id in stream_ids:
            for j in range(10):
                event = Event(
                    event_id=uuid4(),
                    event_type="TestEvent",
                    stream_id=stream_id,
                    version=j + 1,
                    timestamp=datetime.utcnow(),
                    payload={"data": j}
                )
                store.append(stream_id, [event])

        times = []
        iterations = 50

        for _ in range(iterations):
            start = time.perf_counter()
            for stream_id in stream_ids:
                store.read_stream(stream_id)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="multi_stream_read",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"streams": 20, "events_per_stream": 10}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms for 20 streams, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_command_execution(self):
        """Benchmark command execution."""
        print("Benchmarking command execution...")

        from src.event_sourcing.command_bus import CommandBus, Command

        bus = CommandBus()

        # Register a simple handler
        def test_handler(command: Command):
            return {"processed": True, "command_id": str(command.command_id)}

        bus.register_handler("TestCommand", test_handler)

        times = []
        errors = 0
        iterations = 100

        for _ in range(iterations):
            command = Command(
                command_id=uuid4(),
                command_type="TestCommand",
                payload={"test": "data"},
                metadata={"benchmark": True}
            )

            start = time.perf_counter()
            try:
                bus.execute(command)
            except Exception:
                errors += 1
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="command_execution",
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
            metadata={"handler_type": "sync"}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_query_execution(self):
        """Benchmark query execution."""
        print("Benchmarking query execution...")

        from src.event_sourcing.query_bus import QueryBus, Query

        bus = QueryBus()

        # Register a simple handler
        def test_query_handler(query: Query):
            return {"result": [1, 2, 3, 4, 5], "count": 5}

        bus.register_handler("TestQuery", test_query_handler)

        times = []
        iterations = 100

        # First pass - no cache
        for _ in range(iterations):
            query = Query(
                query_id=uuid4(),
                query_type="TestQuery",
                parameters={"filter": "all"},
                options={"use_cache": False}
            )

            start = time.perf_counter()
            bus.execute(query)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result_no_cache = BenchmarkResult(
            name="query_execution_no_cache",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"cached": False}
        )
        self.results.append(result_no_cache)
        print(f"  No cache: {result_no_cache.avg_time_ms:.3f}ms, Ops/s: {result_no_cache.ops_per_second:.2f}")

        # Second pass - with cache
        times_cached = []
        cached_query = Query(
            query_id=uuid4(),
            query_type="TestQuery",
            parameters={"filter": "cached"},
            options={"use_cache": True, "cache_key": "cached-query"}
        )

        # Prime cache
        bus.execute(cached_query)

        for _ in range(iterations):
            start = time.perf_counter()
            bus.execute(cached_query)
            end = time.perf_counter()
            times_cached.append((end - start) * 1000)

        result_cached = BenchmarkResult(
            name="query_execution_cached",
            iterations=iterations,
            total_time_ms=sum(times_cached),
            avg_time_ms=statistics.mean(times_cached),
            min_time_ms=min(times_cached),
            max_time_ms=max(times_cached),
            p50_ms=calculate_percentile(times_cached, 50),
            p95_ms=calculate_percentile(times_cached, 95),
            p99_ms=calculate_percentile(times_cached, 99),
            ops_per_second=1000 / (sum(times_cached) / iterations),
            metadata={"cached": True}
        )
        self.results.append(result_cached)
        print(f"  Cached: {result_cached.avg_time_ms:.3f}ms, Ops/s: {result_cached.ops_per_second:.2f}")

    async def _benchmark_projection_processing(self):
        """Benchmark projection event processing."""
        print("Benchmarking projection processing...")

        from src.event_sourcing.projection import ProjectionManager, Projection
        from src.event_sourcing.event_store import EventStore, Event

        store = EventStore()

        # Create a simple projection
        class BenchmarkProjection(Projection):
            def __init__(self):
                super().__init__("BenchmarkProjection")
                self.processed_count = 0

            def process_event(self, event):
                self.processed_count += 1
                self.position = event.version

        manager = ProjectionManager()
        projection = BenchmarkProjection()
        manager.register_projection(projection)

        # Pre-populate events
        stream_id = "projection-test-stream"
        events = []
        for i in range(100):
            event = Event(
                event_id=uuid4(),
                event_type="TestEvent",
                stream_id=stream_id,
                version=i + 1,
                timestamp=datetime.utcnow(),
                payload={"index": i}
            )
            events.append(event)
        store.append(stream_id, events)

        times = []
        iterations = 50

        for _ in range(iterations):
            projection.processed_count = 0
            projection.position = 0

            start = time.perf_counter()
            for event in events:
                projection.process_event(event)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="projection_processing",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"events_processed": 100}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms for 100 events, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_aggregate_rebuild(self):
        """Benchmark aggregate state rebuild from events."""
        print("Benchmarking aggregate rebuild...")

        from src.event_sourcing.event_store import EventStore, Event
        from src.event_sourcing.aggregate import AggregateRoot

        store = EventStore()

        # Create test aggregate
        class TestAggregate(AggregateRoot):
            def __init__(self, aggregate_id: str):
                super().__init__(aggregate_id)
                self.state = {"count": 0, "items": []}

            def apply_event(self, event):
                if event.event_type == "ItemAdded":
                    self.state["count"] += 1
                    self.state["items"].append(event.payload.get("item"))
                elif event.event_type == "ItemRemoved":
                    self.state["count"] -= 1
                    self.state["items"].remove(event.payload.get("item"))

        # Pre-populate events
        aggregate_id = "test-aggregate-1"
        stream_id = f"TestAggregate-{aggregate_id}"
        events = []
        for i in range(50):
            event = Event(
                event_id=uuid4(),
                event_type="ItemAdded",
                stream_id=stream_id,
                version=i + 1,
                timestamp=datetime.utcnow(),
                payload={"item": f"item-{i}"}
            )
            events.append(event)
        store.append(stream_id, events)

        times = []
        iterations = 50

        for _ in range(iterations):
            aggregate = TestAggregate(aggregate_id)

            start = time.perf_counter()
            # Rebuild from events
            stored_events = store.read_stream(stream_id)
            for event in stored_events:
                aggregate.apply_event(event)
            end = time.perf_counter()
            times.append((end - start) * 1000)

        result = BenchmarkResult(
            name="aggregate_rebuild",
            iterations=iterations,
            total_time_ms=sum(times),
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(times, 50),
            p95_ms=calculate_percentile(times, 95),
            p99_ms=calculate_percentile(times, 99),
            ops_per_second=1000 / (sum(times) / iterations),
            metadata={"events_replayed": 50}
        )
        self.results.append(result)
        print(f"  Avg: {result.avg_time_ms:.3f}ms for 50 events, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_concurrent_appends(self):
        """Benchmark concurrent event appends."""
        print("Benchmarking concurrent appends...")

        from src.event_sourcing.event_store import EventStore, Event

        store = EventStore()

        async def append_events(stream_index: int):
            stream_id = f"concurrent-stream-{stream_index}"
            events = []
            for i in range(10):
                event = Event(
                    event_id=uuid4(),
                    event_type="ConcurrentEvent",
                    stream_id=stream_id,
                    version=i + 1,
                    timestamp=datetime.utcnow(),
                    payload={"batch": stream_index, "index": i}
                )
                events.append(event)

            start = time.perf_counter()
            store.append(stream_id, events)
            end = time.perf_counter()
            return (end - start) * 1000

        iterations = 100  # 100 concurrent streams

        start_total = time.perf_counter()
        times = await asyncio.gather(*[append_events(i) for i in range(iterations)])
        end_total = time.perf_counter()

        result = BenchmarkResult(
            name="concurrent_appends",
            iterations=iterations,
            total_time_ms=(end_total - start_total) * 1000,
            avg_time_ms=statistics.mean(times),
            min_time_ms=min(times),
            max_time_ms=max(times),
            p50_ms=calculate_percentile(list(times), 50),
            p95_ms=calculate_percentile(list(times), 95),
            p99_ms=calculate_percentile(list(times), 99),
            ops_per_second=iterations / ((end_total - start_total)),
            metadata={"concurrent_streams": iterations, "events_per_stream": 10}
        )
        self.results.append(result)
        print(f"  Total: {result.total_time_ms:.3f}ms for {iterations} streams, Ops/s: {result.ops_per_second:.2f}")

    async def _benchmark_resilience_overhead(self):
        """Benchmark resilience patterns overhead."""
        print("Benchmarking resilience overhead...")

        from src.resilience import TokenBucket, SemaphoreBulkhead

        # Rate limiter overhead
        limiter = TokenBucket(capacity=10000, refill_rate=1000.0)

        times_limiter = []
        for _ in range(10000):
            start = time.perf_counter()
            limiter.acquire()
            end = time.perf_counter()
            times_limiter.append((end - start) * 1000)

        result_limiter = BenchmarkResult(
            name="rate_limiter_overhead",
            iterations=10000,
            total_time_ms=sum(times_limiter),
            avg_time_ms=statistics.mean(times_limiter),
            min_time_ms=min(times_limiter),
            max_time_ms=max(times_limiter),
            p50_ms=calculate_percentile(times_limiter, 50),
            p95_ms=calculate_percentile(times_limiter, 95),
            p99_ms=calculate_percentile(times_limiter, 99),
            ops_per_second=1000 / (sum(times_limiter) / 10000),
            metadata={"algorithm": "token_bucket"}
        )
        self.results.append(result_limiter)
        print(f"  Rate limiter: {result_limiter.avg_time_ms:.6f}ms overhead")

        # Bulkhead overhead
        bulkhead = SemaphoreBulkhead(max_concurrent=100)

        def simple_op():
            return 42

        times_bulkhead = []
        for _ in range(1000):
            start = time.perf_counter()
            bulkhead.execute(simple_op)
            end = time.perf_counter()
            times_bulkhead.append((end - start) * 1000)

        result_bulkhead = BenchmarkResult(
            name="bulkhead_overhead",
            iterations=1000,
            total_time_ms=sum(times_bulkhead),
            avg_time_ms=statistics.mean(times_bulkhead),
            min_time_ms=min(times_bulkhead),
            max_time_ms=max(times_bulkhead),
            p50_ms=calculate_percentile(times_bulkhead, 50),
            p95_ms=calculate_percentile(times_bulkhead, 95),
            p99_ms=calculate_percentile(times_bulkhead, 99),
            ops_per_second=1000 / (sum(times_bulkhead) / 1000),
            metadata={"max_concurrent": 100}
        )
        self.results.append(result_bulkhead)
        print(f"  Bulkhead: {result_bulkhead.avg_time_ms:.3f}ms overhead")

    def _generate_report(self) -> Dict[str, Any]:
        """Generate benchmark report."""
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "module": "event_sourcing",
            "version": "3.3.0",
            "results": [r.to_dict() for r in self.results],
            "summary": {
                "total_benchmarks": len(self.results),
                "total_errors": sum(r.errors for r in self.results),
                "fastest_op": min(self.results, key=lambda r: r.avg_time_ms).name,
                "slowest_op": max(self.results, key=lambda r: r.avg_time_ms).name,
                "highest_throughput": max(self.results, key=lambda r: r.ops_per_second).name
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
        print(f"Highest throughput: {report['summary']['highest_throughput']}")
        print()

        return report


async def main():
    """Run benchmarks."""
    benchmark = EventSourcingBenchmark()
    report = await benchmark.run_all()

    # Save report
    import json
    from pathlib import Path

    output_dir = Path("benchmarks/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"event_sourcing_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report saved to: {output_file}")


if __name__ == "__main__":
    asyncio.run(main())
