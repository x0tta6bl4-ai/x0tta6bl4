from __future__ import annotations

import asyncio

import pytest

import src.optimization.rag_hnsw_optimizer as mod


def test_query_rewriter_and_adaptive_tuner(monkeypatch):
    rewriter = mod.QueryRewriter()

    variants = rewriter.expand_query("Network error in memory")
    assert len(variants) > 1
    assert rewriter.expand_query("Network error in memory") is variants

    assert rewriter.rewrite_for_performance("good query", result_quality=0.9) == "good query"
    assert " OR " in rewriter.rewrite_for_performance(
        "slow network issue now", result_quality=0.1
    )
    assert rewriter.rewrite_for_performance("single", result_quality=0.1) == "single"

    tuner = mod.AdaptiveParameterTuner()
    assert tuner.get_p95_latency() == 0.0
    assert tuner.get_p99_latency() == 0.0

    for value in [10, 20, 30, 40, 50, 60, 70, 80, 90, 200]:
        tuner.record_latency(value)

    assert tuner.get_p95_latency() >= 90
    assert tuner.get_p99_latency() >= 90

    params_before = tuner.current_params.ef_search
    tuned = tuner.adapt_parameters(target_latency_ms=100)
    assert tuned.ef_search <= params_before

    tuner.latency_history.clear()
    for _ in range(12):
        tuner.record_latency(5)
    tuner.current_params.ef_search = 50
    tuned_low = tuner.adapt_parameters(target_latency_ms=100)
    assert tuned_low.ef_search >= 60
    assert len(tuner.param_history) >= 1


def test_query_cache_eviction_ttl_and_hit_rate(monkeypatch):
    now = {"t": 100.0}
    monkeypatch.setattr(mod.time, "time", lambda: now["t"])

    cache = mod.QueryCache(max_size=1, ttl_seconds=10)
    cache.put("a", "A")

    now["t"] = 101.0
    cache.put("b", "B")
    assert "a" not in cache.cache

    assert cache.get("missing") is None
    assert cache.get("b") == "B"

    now["t"] = 120.0
    assert cache.get("b") is None
    assert cache.hit_rate() >= 0.0


@pytest.mark.asyncio
async def test_batch_retrieval_manager_add_process_and_flush():
    manager = mod.BatchRetrievalManager(batch_size=2)

    t1 = asyncio.create_task(manager.add_query("q1"))
    await asyncio.sleep(0)
    t2 = asyncio.create_task(manager.add_query("q2"))
    r1, r2 = await asyncio.gather(t1, t2)

    assert r1.startswith("result_")
    assert r2.startswith("result_")
    assert manager.batch_count == 1

    t3 = asyncio.create_task(manager.add_query("q3"))
    await asyncio.sleep(0)
    await manager.flush()
    r3 = await t3
    assert r3.startswith("result_")


@pytest.mark.asyncio
async def test_optimizer_retrieve_cache_rewrite_timeout_and_fallback(monkeypatch):
    now = {"t": 1000.0}

    def _time():
        now["t"] += 0.01
        return now["t"]

    monkeypatch.setattr(mod.time, "time", _time)

    optimizer = mod.HNSWPerformanceOptimizer(max_cache_size=10)

    calls = []

    async def retrieval(query, k=5):
        calls.append(query)
        return [("doc1", 0.4)]

    res1, info1 = await optimizer.retrieve_with_optimization(
        "Q", retrieval, k=2, enable_rewrite=False
    )
    res2, info2 = await optimizer.retrieve_with_optimization(
        "Q", retrieval, k=2, enable_rewrite=False
    )

    assert res1 == [("doc1", 0.4)]
    assert res2 == [("doc1", 0.4)]
    assert calls == ["Q"]
    assert info2["cache_hit"] is True

    optimizer2 = mod.HNSWPerformanceOptimizer(max_cache_size=10)
    optimizer2.query_rewriter.expand_query = lambda q: ["good", "timeout"]

    async def retrieval2(query, k=5):
        if query == "timeout":
            raise asyncio.TimeoutError()
        if query == "orig":
            return [("orig", 0.1)]
        return [("d1", 0.2), ("d1", 0.5), ("d2", 0.3)]

    rewritten, rewritten_info = await optimizer2.retrieve_with_optimization(
        "orig", retrieval2, k=2, enable_rewrite=True
    )
    assert rewritten[0][0] == "d1"
    assert rewritten_info["rewritten"] is True

    optimizer3 = mod.HNSWPerformanceOptimizer(max_cache_size=10)
    optimizer3.query_rewriter.expand_query = lambda q: ["timeout1", "timeout2"]

    async def retrieval3(query, k=5):
        if query.startswith("timeout"):
            raise asyncio.TimeoutError()
        return [("orig", 0.9)]

    fallback, _ = await optimizer3.retrieve_with_optimization(
        "orig", retrieval3, k=2, enable_rewrite=True
    )
    assert fallback == [("orig", 0.9)]


@pytest.mark.asyncio
async def test_optimizer_batch_metrics_adaptive_clear_and_factory():
    optimizer = mod.HNSWPerformanceOptimizer(max_cache_size=4)

    async def retrieval(query, k=5):
        return [(query, 1.0)]

    batch = await optimizer.batch_retrieve(["a", "b"], retrieval, k=1)
    assert set(batch) == {"a", "b"}
    assert optimizer.metrics.batch_operations == 1

    metrics = optimizer.get_metrics()
    assert "cache_hit_rate_percent" in metrics
    assert "current_parameters" in metrics

    sentinel = mod.HNSWParameters(ef_search=77)
    optimizer.param_tuner.adapt_parameters = lambda target_latency_ms=100: sentinel
    assert optimizer.get_adaptive_parameters() is sentinel

    optimizer.query_cache.put("x", [("x", 1.0)])
    optimizer.clear_cache()
    assert optimizer.query_cache.cache == {}
    assert optimizer.query_cache.access_times == {}

    created = mod.create_hnsw_optimizer(max_cache_size=3)
    assert isinstance(created, mod.HNSWPerformanceOptimizer)


def test_query_type_enum_values():
    assert mod.QueryType.SEMANTIC.value == "semantic"
    assert mod.QueryType.HYBRID.value == "hybrid"
