import asyncio
import time

import pytest

from src.optimization.performance_tuner import (AsyncBottleneckDetector,
                                                ConnectionPoolOptimizer,
                                                EdgeCaseHandler,
                                                LatencyTracker,
                                                MemoryOptimizer,
                                                PerformanceTuner,
                                                get_performance_tuner)


class TestLatencyTracker:
    def test_record_and_get_stats(self):
        tracker = LatencyTracker()
        for i in range(100):
            tracker.record("test_op", float(i))

        stats = tracker.get_stats("test_op")
        assert stats["count"] == 100
        assert stats["min"] == 0
        assert stats["max"] == 99
        assert stats["avg"] > 0

    def test_percentile_calculation(self):
        tracker = LatencyTracker()
        for i in range(100):
            tracker.record("op", float(i))

        stats = tracker.get_stats("op")
        assert 40 <= stats["p50"] <= 60
        assert 90 <= stats["p95"] <= 99
        assert 99 <= stats["p99"] <= 99

    def test_window_size_limit(self):
        tracker = LatencyTracker(window_size=10)
        for i in range(20):
            tracker.record("op", float(i))

        stats = tracker.get_stats("op")
        assert stats["count"] == 10


class TestAsyncBottleneckDetector:
    def test_record_baseline(self):
        detector = AsyncBottleneckDetector()
        detector.record_baseline("db_query", 100.0)
        assert detector.baseline["db_query"] == 100.0

    def test_detect_slowdown(self):
        detector = AsyncBottleneckDetector(slowdown_threshold=1.5)
        detector.record_baseline("db_query", 100.0)
        detector.record_current("db_query", 200.0)

        slowdowns = detector.get_slowdowns()
        assert len(slowdowns) > 0
        assert slowdowns[0]["slowdown_ratio"] == pytest.approx(2.0)

    def test_no_slowdown_alert(self):
        detector = AsyncBottleneckDetector(slowdown_threshold=1.5)
        detector.record_baseline("db_query", 100.0)
        detector.record_current("db_query", 120.0)

        slowdowns = detector.get_slowdowns()
        assert len(slowdowns) == 0

    def test_get_top_slowdowns(self):
        detector = AsyncBottleneckDetector()
        detector.record_baseline("op1", 100.0)
        detector.record_baseline("op2", 100.0)
        detector.record_baseline("op3", 100.0)

        detector.record_current("op1", 300.0)
        detector.record_current("op2", 500.0)
        detector.record_current("op3", 200.0)

        top = detector.get_top_slowdowns(2)
        assert len(top) == 2
        assert top[0]["slowdown_ratio"] > top[1]["slowdown_ratio"]


class TestMemoryOptimizer:
    def test_cache_hit_and_miss(self):
        optimizer = MemoryOptimizer()
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return "result"

        result1 = optimizer.get_cached("key1", compute, ttl_seconds=60)
        result2 = optimizer.get_cached("key1", compute, ttl_seconds=60)

        assert result1 == result2
        assert call_count == 1
        stats = optimizer.get_stats()
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1

    def test_cache_ttl_expiration(self):
        optimizer = MemoryOptimizer()
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return "result"

        optimizer.get_cached("key1", compute, ttl_seconds=1)
        time.sleep(1.1)
        optimizer.get_cached("key1", compute, ttl_seconds=1)

        assert call_count == 2

    def test_cache_size_limit(self):
        optimizer = MemoryOptimizer(max_cache_size_mb=0.001)

        def compute_large():
            return "x" * 10000

        result = optimizer.get_cached("big", compute_large, ttl_seconds=60)
        stats = optimizer.get_stats()
        assert stats["cache_entries"] <= 1

    def test_hit_rate_calculation(self):
        optimizer = MemoryOptimizer()

        def compute():
            return "value"

        for _ in range(10):
            optimizer.get_cached("key", compute, ttl_seconds=60)

        stats = optimizer.get_stats()
        assert stats["hit_rate"] > 0.5


class TestConnectionPoolOptimizer:
    def test_acquire_release_connection(self):
        pool = ConnectionPoolOptimizer(min_connections=2, max_connections=5)

        conn1 = pool.acquire_connection()
        assert conn1["acquired"]
        assert pool.active_connections == 1

        pool.release_connection()
        assert pool.active_connections == 0

    def test_max_connections_limit(self):
        pool = ConnectionPoolOptimizer(max_connections=2)

        conn1 = pool.acquire_connection()
        conn2 = pool.acquire_connection()
        conn3 = pool.acquire_connection()

        assert conn1["acquired"]
        assert conn2["acquired"]
        assert not conn3["acquired"]

    def test_pool_stats(self):
        pool = ConnectionPoolOptimizer(max_connections=10)

        for _ in range(5):
            pool.acquire_connection()

        stats = pool.get_stats()
        assert stats["active"] == 5
        assert stats["available"] == 5
        assert stats["utilization"] == pytest.approx(0.5)


class TestEdgeCaseHandler:
    def test_large_payload_detection(self):
        handler = EdgeCaseHandler()

        result = handler.handle_large_payload(5_000_000, threshold_bytes=10_000_000)
        assert result

        result = handler.handle_large_payload(15_000_000, threshold_bytes=10_000_000)
        assert not result

        cases = handler.get_recent_edge_cases()
        assert len(cases) == 1
        assert cases[0]["type"] == "large_payload"

    def test_high_concurrency_detection(self):
        handler = EdgeCaseHandler()

        result = handler.handle_high_concurrency(500, threshold=1000)
        assert result

        result = handler.handle_high_concurrency(1500, threshold=1000)
        assert not result

        cases = handler.get_recent_edge_cases()
        assert len(cases) == 1
        assert cases[0]["type"] == "high_concurrency"

    def test_slow_query_detection(self):
        handler = EdgeCaseHandler()

        result = handler.handle_slow_query(1000, threshold_ms=5000)
        assert result

        result = handler.handle_slow_query(6000, threshold_ms=5000)
        assert not result

        cases = handler.get_recent_edge_cases()
        assert len(cases) == 1


class TestPerformanceTuner:
    def test_profile_function(self):
        tuner = PerformanceTuner()

        @tuner.profile_function("test_func")
        def slow_function(x):
            time.sleep(0.01)
            return x * 2

        result = slow_function(5)
        assert result == 10

        stats = tuner.latency_tracker.get_stats("test_func")
        assert stats["count"] == 1
        assert stats["avg"] >= 10

    def test_profile_async_function(self):
        tuner = PerformanceTuner()

        @tuner.profile_async_function("async_func")
        async def async_slow_function(x):
            await asyncio.sleep(0.01)
            return x * 3

        result = asyncio.run(async_slow_function(5))
        assert result == 15

        stats = tuner.latency_tracker.get_stats("async_func")
        assert stats["count"] == 1

    def test_analyze_performance(self):
        tuner = PerformanceTuner()

        tuner.latency_tracker.record("op1", 10.0)
        tuner.latency_tracker.record("op2", 20.0)

        analysis = tuner.analyze_performance()
        assert "latency_stats" in analysis
        assert "slowdowns" in analysis
        assert "memory" in analysis
        assert "connections" in analysis
        assert "recommendations" in analysis

    def test_generate_recommendations(self):
        tuner = PerformanceTuner()

        tuner.bottleneck_detector.record_baseline("slow_op", 100)
        tuner.bottleneck_detector.record_current("slow_op", 250)

        recommendations = tuner._generate_recommendations()
        assert len(recommendations) > 0


class TestIntegration:
    def test_complete_performance_analysis_workflow(self):
        tuner = PerformanceTuner()

        @tuner.profile_function("db_query")
        def db_query():
            time.sleep(0.01)
            return {"data": "result"}

        tuner.bottleneck_detector.record_baseline("db_query", 10.0)

        for i in range(10):
            db_query()
            time.sleep(0.001)

        tuner.bottleneck_detector.record_current("db_query", 15.0)

        analysis = tuner.analyze_performance()
        assert analysis["latency_stats"]["db_query"]["count"] == 10
        assert len(analysis["slowdowns"]) == 0

    def test_memory_cache_under_load(self):
        optimizer = MemoryOptimizer(max_cache_size_mb=1)

        def compute_data(key):
            return f"data_{key}" * 100

        for i in range(50):
            optimizer.get_cached(
                f"key_{i}", lambda k=i: compute_data(k), ttl_seconds=60
            )

        stats = optimizer.get_stats()
        assert stats["cache_entries"] <= 100
        assert stats["cache_size_bytes"] <= 1024 * 1024 * 1.5

    def test_edge_case_accumulation(self):
        handler = EdgeCaseHandler()

        for i in range(100):
            if i % 3 == 0:
                handler.handle_large_payload(15_000_000)
            if i % 5 == 0:
                handler.handle_high_concurrency(2000)

        cases = handler.get_recent_edge_cases(50)
        assert len(cases) <= 50
        assert any(c["type"] == "large_payload" for c in cases)
        assert any(c["type"] == "high_concurrency" for c in cases)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
