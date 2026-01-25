"""
Test suite for RAG HNSW optimization module.

Tests adaptive parameter tuning, query rewriting, caching, and batch operations.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, Mock
from src.optimization.rag_hnsw_optimizer import (
    HNSWParameters,
    QueryOptimizationMetrics,
    QueryRewriter,
    AdaptiveParameterTuner,
    QueryCache,
    BatchRetrievalManager,
    HNSWPerformanceOptimizer,
    create_hnsw_optimizer
)


class TestHNSWParameters:
    """Test HNSW parameter configuration"""
    
    def test_default_parameters(self):
        params = HNSWParameters()
        assert params.ef_construction == 200
        assert params.ef_search == 50
        assert params.max_elements == 10000
        assert params.m == 16
    
    def test_custom_parameters(self):
        params = HNSWParameters(
            ef_construction=300,
            ef_search=100,
            max_elements=50000
        )
        assert params.ef_construction == 300
        assert params.ef_search == 100
        assert params.max_elements == 50000


class TestQueryOptimizationMetrics:
    """Test optimization metrics dataclass"""
    
    def test_metrics_creation(self):
        metrics = QueryOptimizationMetrics()
        assert metrics.total_queries == 0
        assert metrics.cache_hits == 0
        assert metrics.avg_latency_ms == 0.0
    
    def test_metrics_updates(self):
        metrics = QueryOptimizationMetrics(
            total_queries=100,
            cache_hits=25,
            avg_latency_ms=45.5
        )
        assert metrics.total_queries == 100
        assert metrics.cache_hits == 25
        assert metrics.avg_latency_ms == 45.5


class TestQueryRewriter:
    """Test query rewriting functionality"""
    
    def test_query_expansion(self):
        rewriter = QueryRewriter()
        query = "error in network"
        variants = rewriter.expand_query(query)
        
        assert query.lower() in variants
        assert len(variants) > 1
    
    def test_expansion_caching(self):
        rewriter = QueryRewriter()
        query = "test query"
        
        variants1 = rewriter.expand_query(query)
        variants2 = rewriter.expand_query(query)
        
        assert variants1 == variants2
        assert query in rewriter.expansion_cache
    
    def test_query_rewrite_for_performance(self):
        rewriter = QueryRewriter()
        query = "this is a long query with multiple words"
        
        rewritten = rewriter.rewrite_for_performance(query, result_quality=0.5)
        
        assert rewritten != query or result_quality > 0.8
    
    def test_query_rewrite_high_quality(self):
        rewriter = QueryRewriter()
        query = "test query"
        
        rewritten = rewriter.rewrite_for_performance(query, result_quality=0.9)
        
        assert rewritten == query


class TestAdaptiveParameterTuner:
    """Test adaptive parameter tuning"""
    
    def test_tuner_initialization(self):
        tuner = AdaptiveParameterTuner()
        assert tuner.query_count == 0
        assert len(tuner.latency_history) == 0
    
    def test_latency_recording(self):
        tuner = AdaptiveParameterTuner()
        
        tuner.record_latency(50.0)
        tuner.record_latency(60.0)
        tuner.record_latency(40.0)
        
        assert tuner.query_count == 3
        assert len(tuner.latency_history) == 3
    
    def test_p95_latency_calculation(self):
        tuner = AdaptiveParameterTuner()
        
        for latency in [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]:
            tuner.record_latency(float(latency))
        
        p95 = tuner.get_p95_latency()
        assert p95 > 50
    
    def test_p99_latency_calculation(self):
        tuner = AdaptiveParameterTuner()
        
        for latency in range(1, 101):
            tuner.record_latency(float(latency))
        
        p99 = tuner.get_p99_latency()
        assert p99 > 90
    
    def test_parameter_adaptation_high_latency(self):
        tuner = AdaptiveParameterTuner()
        initial_ef = tuner.current_params.ef_search
        
        for _ in range(20):
            tuner.record_latency(200.0)
        
        adapted = tuner.adapt_parameters(target_latency_ms=100)
        
        assert adapted.ef_search < initial_ef
    
    def test_parameter_adaptation_low_latency(self):
        tuner = AdaptiveParameterTuner()
        initial_ef = tuner.current_params.ef_search
        
        for _ in range(20):
            tuner.record_latency(10.0)
        
        adapted = tuner.adapt_parameters(target_latency_ms=100)
        
        assert adapted.ef_search >= initial_ef
    
    def test_parameter_history(self):
        tuner = AdaptiveParameterTuner()
        
        for _ in range(15):
            tuner.record_latency(150.0)
        
        tuner.adapt_parameters()
        
        assert len(tuner.param_history) > 0


class TestQueryCache:
    """Test query caching with TTL and LRU"""
    
    def test_cache_put_get(self):
        cache = QueryCache()
        
        cache.put("key1", "value1")
        result = cache.get("key1")
        
        assert result == "value1"
    
    def test_cache_miss(self):
        cache = QueryCache()
        
        result = cache.get("nonexistent")
        
        assert result is None
        assert cache.misses == 1
    
    def test_cache_hit_rate(self):
        cache = QueryCache()
        
        cache.put("key1", "value1")
        cache.get("key1")
        cache.get("key1")
        cache.get("nonexistent")
        
        hit_rate = cache.hit_rate()
        assert hit_rate == 2/3
    
    def test_cache_ttl_expiration(self):
        cache = QueryCache(ttl_seconds=1)
        
        cache.put("key1", "value1")
        result1 = cache.get("key1")
        
        time.sleep(1.1)
        result2 = cache.get("key1")
        
        assert result1 == "value1"
        assert result2 is None
    
    def test_cache_lru_eviction(self):
        cache = QueryCache(max_size=3)
        
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")
        cache.put("key4", "value4")
        
        result = cache.get("key1")
        
        assert result is None
        assert len(cache.cache) == 3
    
    def test_cache_access_time_update(self):
        cache = QueryCache(max_size=3)
        
        cache.put("key1", "value1")
        time.sleep(0.01)
        cache.put("key2", "value2")
        time.sleep(0.01)
        cache.put("key3", "value3")
        
        cache.get("key1")
        
        time.sleep(0.01)
        cache.put("key4", "value4")
        
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None


class TestBatchRetrievalManager:
    """Test batch retrieval operations"""
    
    def test_batch_manager_initialization(self):
        manager = BatchRetrievalManager(batch_size=16)
        assert manager.batch_size == 16
        assert manager.batch_count == 0
    
    def test_batch_manager_pending_queries(self):
        manager = BatchRetrievalManager(batch_size=10)
        
        assert manager.batch_count == 0
        assert manager.batch_size == 10
    
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        manager = BatchRetrievalManager(batch_size=2)
        
        future1 = asyncio.create_task(manager.add_query("query1"))
        future2 = asyncio.create_task(manager.add_query("query2"))
        
        await asyncio.sleep(0.1)
        
        assert manager.batch_count == 1
    
    @pytest.mark.asyncio
    async def test_flush_remaining_queries(self):
        manager = BatchRetrievalManager(batch_size=5)
        
        for i in range(3):
            asyncio.create_task(manager.add_query(f"query{i}"))
        
        await asyncio.sleep(0.1)
        await manager.flush()
        
        assert len(manager.pending_queries) == 0


class TestHNSWPerformanceOptimizer:
    """Test HNSW performance optimizer"""
    
    def test_optimizer_initialization(self):
        optimizer = HNSWPerformanceOptimizer()
        
        assert optimizer.metrics.total_queries == 0
        assert optimizer.query_cache is not None
    
    @pytest.mark.asyncio
    async def test_retrieve_with_cache_hit(self):
        optimizer = HNSWPerformanceOptimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.01)
            return [(f"doc_{i}", 0.9 - i*0.1) for i in range(k)]
        
        results1, _ = await optimizer.retrieve_with_optimization(
            "test query",
            mock_retrieval,
            k=3
        )
        
        results2, stats = await optimizer.retrieve_with_optimization(
            "test query",
            mock_retrieval,
            k=3
        )
        
        assert stats["cache_hit"] is True
        assert optimizer.metrics.cache_hits == 1
    
    @pytest.mark.asyncio
    async def test_retrieve_with_rewriting(self):
        optimizer = HNSWPerformanceOptimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.01)
            return [(f"doc_{i}", 0.8) for i in range(k)]
        
        results, stats = await optimizer.retrieve_with_optimization(
            "error in network",
            mock_retrieval,
            k=5,
            enable_rewrite=True
        )
        
        assert len(results) > 0
        assert stats["variants_tried"] >= 1
    
    @pytest.mark.asyncio
    async def test_batch_retrieve(self):
        optimizer = HNSWPerformanceOptimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.01)
            return [(f"doc_{i}", 0.9) for i in range(k)]
        
        queries = ["query1", "query2", "query3"]
        results = await optimizer.batch_retrieve(queries, mock_retrieval, k=5)
        
        assert len(results) == 3
        assert optimizer.metrics.batch_operations == 1
    
    @pytest.mark.asyncio
    async def test_latency_tracking(self):
        optimizer = HNSWPerformanceOptimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.02)
            return [(f"doc_{i}", 0.9) for i in range(k)]
        
        await optimizer.retrieve_with_optimization(
            "test query",
            mock_retrieval,
            k=5
        )
        
        assert optimizer.metrics.avg_latency_ms > 0
    
    def test_cache_key_generation(self):
        optimizer = HNSWPerformanceOptimizer()
        
        key1 = optimizer._make_cache_key("test query", k=5)
        key2 = optimizer._make_cache_key("test query", k=5)
        key3 = optimizer._make_cache_key("test query", k=10)
        
        assert key1 == key2
        assert key1 != key3
    
    def test_deduplication_and_ranking(self):
        optimizer = HNSWPerformanceOptimizer()
        
        results = [
            ("doc1", 0.9),
            ("doc2", 0.8),
            ("doc1", 0.85),
            ("doc3", 0.7)
        ]
        
        deduplicated = optimizer._deduplicate_and_rank(results)
        
        assert len(deduplicated) == 3
        assert deduplicated[0][0] == "doc1"
        assert deduplicated[0][1] == 0.9
    
    def test_metrics_collection(self):
        optimizer = HNSWPerformanceOptimizer()
        optimizer.metrics.total_queries = 100
        optimizer.metrics.cache_hits = 25
        
        metrics = optimizer.get_metrics()
        
        assert metrics["total_queries"] == 100
        assert metrics["cache_hits"] == 25
        assert "cache_hit_rate_percent" in metrics
    
    def test_adaptive_parameters(self):
        optimizer = HNSWPerformanceOptimizer()
        
        for _ in range(20):
            optimizer.param_tuner.record_latency(150.0)
        
        params = optimizer.get_adaptive_parameters()
        
        assert params.ef_search is not None
    
    def test_cache_clearing(self):
        optimizer = HNSWPerformanceOptimizer()
        
        optimizer.query_cache.put("key1", "value1")
        optimizer.query_cache.put("key2", "value2")
        
        optimizer.clear_cache()
        
        assert len(optimizer.query_cache.cache) == 0
        assert len(optimizer.query_cache.access_times) == 0


class TestCreateHNSWOptimizer:
    """Test factory function"""
    
    def test_create_with_default_params(self):
        optimizer = create_hnsw_optimizer()
        
        assert optimizer is not None
        assert isinstance(optimizer, HNSWPerformanceOptimizer)
    
    def test_create_with_custom_params(self):
        optimizer = create_hnsw_optimizer(max_cache_size=5000)
        
        assert optimizer.query_cache.max_size == 5000


class TestHNSWOptimizationIntegration:
    """Integration tests for HNSW optimization"""
    
    @pytest.mark.asyncio
    async def test_full_optimization_workflow(self):
        optimizer = create_hnsw_optimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.01)
            return [(f"doc_{i}", 0.9 - i*0.05) for i in range(k)]
        
        queries = [
            "query1",
            "query2",
            "query1",
            "query3",
            "query1"
        ]
        
        for query in queries:
            await optimizer.retrieve_with_optimization(
                query,
                mock_retrieval,
                k=5,
                enable_rewrite=True
            )
        
        metrics = optimizer.get_metrics()
        
        assert metrics["total_queries"] == 5
        assert metrics["cache_hits"] > 0
        assert metrics["avg_latency_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_batch_vs_individual_queries(self):
        optimizer = create_hnsw_optimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.01)
            return [(f"doc_{i}", 0.9) for i in range(k)]
        
        queries = [f"query{i}" for i in range(5)]
        
        batch_results = await optimizer.batch_retrieve(
            queries,
            mock_retrieval,
            k=5
        )
        
        assert len(batch_results) == 5
        assert optimizer.metrics.batch_operations == 1
    
    @pytest.mark.asyncio
    async def test_parameter_adaptation_during_workload(self):
        optimizer = create_hnsw_optimizer()
        
        async def mock_retrieval(query: str, k: int = 5):
            await asyncio.sleep(0.02)
            return [(f"doc_{i}", 0.9) for i in range(k)]
        
        for i in range(15):
            await optimizer.retrieve_with_optimization(
                f"query{i}",
                mock_retrieval,
                k=5
            )
        
        params = optimizer.get_adaptive_parameters()
        metrics = optimizer.get_metrics()
        
        assert params is not None
        assert metrics["total_queries"] == 15
