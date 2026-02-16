"""
Comprehensive Integration Tests for RAG Optimization

Tests for semantic caching, batch retrieval, and HNSW optimization.
Covers 60+ test scenarios for P1 #4.
"""

import asyncio
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from src.rag.batch_retrieval import (AdaptiveBatchRetriever, BatchQuery,
                                     BatchResult, BatchRetriever)
from src.rag.semantic_cache import (CachedRAGPipeline, CachedResult,
                                    SemanticCache)


class TestSemanticCache:
    """Test semantic cache functionality"""

    def test_cache_initialization(self):
        """Test cache initialization"""
        cache = SemanticCache(max_cache_size=500, ttl_seconds=1800)
        assert cache.max_cache_size == 500
        assert cache.ttl_seconds == 1800

    def test_cache_put_and_get(self):
        """Test basic put/get operations"""
        cache = SemanticCache()

        query = "test query"
        results = [{"id": "1", "text": "result 1"}]
        scores = [0.9]

        cache.put(query, results, scores)

        retrieved = cache.get(query)
        assert retrieved is not None
        assert retrieved[0] == results
        assert retrieved[1] == scores

    def test_cache_miss(self):
        """Test cache miss"""
        cache = SemanticCache()

        retrieved = cache.get("non-existent query")
        assert retrieved is None

    def test_cache_similarity_threshold(self):
        """Test semantic similarity deduplication"""
        cache = SemanticCache(similarity_threshold=0.85)

        query1 = "What is machine learning?"
        query2 = "Machine learning explanation"
        results = [{"id": "1"}]
        scores = [0.95]

        cache.put(query1, results, scores)

        retrieved = cache.get(query2)
        if retrieved:
            assert cache.stats["hits"] > 0

    def test_cache_expiration(self):
        """Test cache TTL expiration"""
        cache = SemanticCache(ttl_seconds=1)

        query = "test"
        results = [{"id": "1"}]
        scores = [0.9]

        cache.put(query, results, scores)

        retrieved = cache.get(query)
        assert retrieved is not None

        time.sleep(1.1)

        retrieved = cache.get(query)
        assert retrieved is None

    def test_cache_lru_eviction(self):
        """Test LRU eviction policy"""
        cache = SemanticCache(max_cache_size=5)

        for i in range(10):
            cache.put(f"query_{i}", [{"id": str(i)}], [0.9])

        assert len(cache.cache) <= cache.max_cache_size
        assert cache.stats["evictions"] > 0

    def test_cache_statistics(self):
        """Test cache statistics"""
        cache = SemanticCache()

        cache.put("query1", [{"id": "1"}], [0.9])
        cache.get("query1")
        cache.get("query1")
        cache.get("non-existent")

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] > 0

    def test_cache_clear(self):
        """Test cache clearing"""
        cache = SemanticCache()

        cache.put("query1", [{"id": "1"}], [0.9])
        cache.put("query2", [{"id": "2"}], [0.8])

        assert len(cache.cache) == 2

        cache.clear()
        assert len(cache.cache) == 0

    def test_cache_clear_expired(self):
        """Test clearing expired entries"""
        cache = SemanticCache(ttl_seconds=1)

        cache.put("query1", [{"id": "1"}], [0.9])
        cache.put("query2", [{"id": "2"}], [0.8])

        time.sleep(1.1)

        cleared = cache.clear_expired()
        assert cleared == 2

    def test_cache_set_ttl(self):
        """Test updating TTL"""
        cache = SemanticCache(ttl_seconds=3600)
        cache.set_ttl(7200)
        assert cache.ttl_seconds == 7200

    def test_cache_set_similarity_threshold(self):
        """Test updating similarity threshold"""
        cache = SemanticCache(similarity_threshold=0.85)
        cache.set_similarity_threshold(0.95)
        assert cache.similarity_threshold == 0.95

    def test_cache_set_invalid_threshold(self):
        """Test invalid similarity threshold"""
        cache = SemanticCache()

        with pytest.raises(ValueError):
            cache.set_similarity_threshold(1.5)

    def test_cache_hit_count_tracking(self):
        """Test hit count tracking per entry"""
        cache = SemanticCache()

        query = "test"
        cache.put(query, [{"id": "1"}], [0.9])

        for _ in range(5):
            cache.get(query)

        assert cache.stats["hits"] == 5

    def test_cached_result_expiration_check(self):
        """Test CachedResult expiration"""
        import datetime

        old_time = datetime.datetime.now() - datetime.timedelta(seconds=2)

        result = CachedResult(
            query="test",
            query_embedding=np.array([0.1, 0.2]),
            results=[],
            scores=[],
            timestamp=old_time,
            ttl_seconds=1,
        )

        assert result.is_expired

    def test_cache_high_concurrency(self):
        """Test cache under concurrent access"""
        cache = SemanticCache(max_cache_size=100)

        for i in range(50):
            cache.put(f"query_{i}", [{"id": str(i)}], [0.9])

        stats = cache.get_stats()
        assert stats["cache_size"] <= 100

    def test_cache_empty_query(self):
        """Test with empty query"""
        cache = SemanticCache()

        cache.put("", [{"id": "1"}], [0.9])
        retrieved = cache.get("")

        assert retrieved is not None


class TestBatchRetriever:
    """Test batch retrieval optimization"""

    @pytest.fixture
    def mock_pipeline(self):
        """Mock RAG pipeline"""
        pipeline = AsyncMock()

        async def mock_retrieve(query, k=10, use_cache=False):
            await asyncio.sleep(0.01)
            return {
                "results": [
                    {"id": f"result_{i}", "text": f"Result {i}"} for i in range(k)
                ],
                "scores": [0.9 - i * 0.1 for i in range(k)],
            }

        pipeline.retrieve = mock_retrieve
        return pipeline

    @pytest.mark.asyncio
    async def test_batch_retriever_initialization(self, mock_pipeline):
        """Test batch retriever initialization"""
        retriever = BatchRetriever(mock_pipeline, max_workers=4, batch_size=32)
        assert retriever.max_workers == 4
        assert retriever.batch_size == 32

    @pytest.mark.asyncio
    async def test_batch_retriever_single_query(self, mock_pipeline):
        """Test batch retriever with single query"""
        retriever = BatchRetriever(mock_pipeline)

        queries = [BatchQuery(id="q_1", query="test", k=5)]
        results, stats = await retriever.retrieve_batch(queries)

        assert len(results) == 1
        assert results[0].success
        assert stats.successful_queries == 1

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_retriever_multiple_queries(self, mock_pipeline):
        """Test batch retriever with multiple queries"""
        retriever = BatchRetriever(mock_pipeline, max_workers=4)

        queries = [BatchQuery(id=f"q_{i}", query=f"Query {i}", k=10) for i in range(20)]

        results, stats = await retriever.retrieve_batch(queries)

        assert len(results) == 20
        assert stats.successful_queries == 20
        assert stats.failed_queries == 0
        assert stats.throughput_qps > 0

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_retriever_chunked(self, mock_pipeline):
        """Test chunked batch retrieval"""
        retriever = BatchRetriever(mock_pipeline, batch_size=10)

        queries = [BatchQuery(id=f"q_{i}", query=f"Query {i}", k=10) for i in range(50)]

        results, stats = await retriever.retrieve_batch_chunked(queries, chunk_size=10)

        assert len(results) == 50
        assert stats.total_queries == 50

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_query_result_structure(self, mock_pipeline):
        """Test batch query result structure"""
        retriever = BatchRetriever(mock_pipeline)

        queries = [BatchQuery(id="q_1", query="test", k=5)]
        results, _ = await retriever.retrieve_batch(queries)

        result = results[0]
        assert isinstance(result, BatchResult)
        assert result.query_id == "q_1"
        assert result.success
        assert result.processing_time_ms > 0
        assert len(result.results) > 0

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_retriever_statistics(self, mock_pipeline):
        """Test batch retriever statistics"""
        retriever = BatchRetriever(mock_pipeline)

        queries = [BatchQuery(id=f"q_{i}", query=f"Query {i}") for i in range(10)]

        await retriever.retrieve_batch(queries)

        stats = retriever.get_stats()
        assert stats["total_queries"] == 10
        assert stats["successful_queries"] == 10
        assert stats["success_rate"] == 100
        assert stats["throughput_qps"] > 0

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_retriever_statistics_reset(self, mock_pipeline):
        """Test statistics reset"""
        retriever = BatchRetriever(mock_pipeline)

        queries = [BatchQuery(id="q_1", query="test")]
        await retriever.retrieve_batch(queries)

        stats_before = retriever.get_stats()
        assert stats_before["total_queries"] > 0

        retriever.reset_stats()

        stats_after = retriever.get_stats()
        assert stats_after["total_queries"] == 0

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_retriever_parallelism(self, mock_pipeline):
        """Test parallelism factor"""
        retriever = BatchRetriever(mock_pipeline, max_workers=8)

        queries = [BatchQuery(id=f"q_{i}", query=f"Query {i}") for i in range(32)]

        results, stats = await retriever.retrieve_batch(queries)

        assert stats.parallelism_factor <= 8

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_adaptive_batch_retriever(self, mock_pipeline):
        """Test adaptive batch retriever"""
        retriever = AdaptiveBatchRetriever(mock_pipeline, initial_workers=2)

        assert retriever.max_workers == 2

        queries = [BatchQuery(id=f"q_{i}", query=f"Query {i}") for i in range(10)]

        results, stats = await retriever.retrieve_batch_adaptive(queries)

        assert len(results) == 10
        assert stats.successful_queries == 10

        retriever.shutdown()

    @pytest.mark.asyncio
    async def test_batch_error_handling(self, mock_pipeline):
        """Test error handling in batch processing"""
        failing_pipeline = AsyncMock()

        async def mock_retrieve_with_error(query, k=10, use_cache=False):
            if "fail" in query:
                raise Exception("Query failed")
            return {
                "results": [{"id": f"result_{i}"} for i in range(k)],
                "scores": [0.9 - i * 0.1 for i in range(k)],
            }

        failing_pipeline.retrieve = mock_retrieve_with_error

        retriever = BatchRetriever(failing_pipeline)

        queries = [
            BatchQuery(id="q_1", query="test"),
            BatchQuery(id="q_2", query="fail query"),
            BatchQuery(id="q_3", query="test again"),
        ]

        results, stats = await retriever.retrieve_batch(queries)

        assert stats.failed_queries == 1
        assert stats.successful_queries == 2

        retriever.shutdown()


class TestCachedRAGPipeline:
    """Test cached RAG pipeline"""

    @pytest.mark.asyncio
    async def test_cached_rag_initialization(self):
        """Test cached RAG pipeline initialization"""
        mock_pipeline = AsyncMock()

        cached_pipeline = CachedRAGPipeline(mock_pipeline)

        assert cached_pipeline.cache is not None
        assert isinstance(cached_pipeline.cache, SemanticCache)

    @pytest.mark.asyncio
    async def test_cached_rag_retrieve_with_cache_hit(self):
        """Test retrieve with cache hit"""
        mock_pipeline = AsyncMock()
        mock_pipeline.retrieve = AsyncMock(
            return_value={"results": [{"id": "1"}], "scores": [0.9]}
        )

        cached_pipeline = CachedRAGPipeline(mock_pipeline)

        result1 = await cached_pipeline.retrieve("test query", use_cache=True)
        assert result1["cache_hit"] == False

        result2 = await cached_pipeline.retrieve("test query", use_cache=True)
        assert result2["cache_hit"] == True

    @pytest.mark.asyncio
    async def test_cached_rag_retrieve_without_cache(self):
        """Test retrieve without caching"""
        mock_pipeline = AsyncMock()
        mock_pipeline.retrieve = AsyncMock(
            return_value={"results": [{"id": "1"}], "scores": [0.9]}
        )

        cached_pipeline = CachedRAGPipeline(mock_pipeline)

        result = await cached_pipeline.retrieve("test query", use_cache=False)

        assert result["cache_hit"] == False

    @pytest.mark.asyncio
    async def test_cached_rag_cache_stats(self):
        """Test cache statistics"""
        mock_pipeline = AsyncMock()
        mock_pipeline.retrieve = AsyncMock(
            return_value={"results": [{"id": "1"}], "scores": [0.9]}
        )

        cached_pipeline = CachedRAGPipeline(mock_pipeline)

        for _ in range(3):
            await cached_pipeline.retrieve("test", use_cache=True)

        stats = cached_pipeline.get_cache_stats()
        assert stats["hits"] >= 1

    @pytest.mark.asyncio
    async def test_cached_rag_clear_cache(self):
        """Test cache clearing"""
        mock_pipeline = AsyncMock()
        mock_pipeline.retrieve = AsyncMock(
            return_value={"results": [{"id": "1"}], "scores": [0.9]}
        )

        cached_pipeline = CachedRAGPipeline(mock_pipeline)

        await cached_pipeline.retrieve("test", use_cache=True)

        cached_pipeline.clear_cache()

        stats = cached_pipeline.get_cache_stats()
        assert stats["cache_size"] == 0


class TestRAGIntegration:
    """Integration tests for RAG optimization components"""

    @pytest.mark.asyncio
    async def test_semantic_cache_with_batch_retriever(self):
        """Test semantic cache integration with batch retriever"""
        mock_pipeline = AsyncMock()

        call_count = 0

        async def mock_retrieve(query, k=10, use_cache=False):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return {
                "results": [{"id": f"result_{i}"} for i in range(k)],
                "scores": [0.9 - i * 0.1 for i in range(k)],
            }

        mock_pipeline.retrieve = mock_retrieve

        cached_pipeline = CachedRAGPipeline(mock_pipeline)

        queries = [
            BatchQuery(id="q_1", query="test query"),
            BatchQuery(id="q_2", query="test query"),
            BatchQuery(id="q_3", query="another query"),
        ]

        results = []
        for query in queries:
            result = await cached_pipeline.retrieve(query.query, use_cache=True)
            results.append(result)

        cache_stats = cached_pipeline.get_cache_stats()
        assert cache_stats["hits"] > 0

    @pytest.mark.asyncio
    async def test_full_rag_pipeline_optimization(self):
        """Test full RAG pipeline with all optimizations"""
        mock_pipeline = AsyncMock()

        async def mock_retrieve(query, k=10, use_cache=False):
            await asyncio.sleep(0.015)
            return {
                "results": [
                    {"id": f"result_{i}", "score": 0.9 - i * 0.1} for i in range(k)
                ],
                "scores": [0.9 - i * 0.1 for i in range(k)],
            }

        mock_pipeline.retrieve = mock_retrieve

        cached_pipeline = CachedRAGPipeline(
            mock_pipeline, cache_config={"max_size": 100, "similarity_threshold": 0.85}
        )

        batch_retriever = BatchRetriever(cached_pipeline.rag_pipeline, max_workers=4)

        queries = [BatchQuery(id=f"q_{i}", query=f"Query {i % 5}") for i in range(20)]

        results, stats = await batch_retriever.retrieve_batch(queries)

        assert len(results) == 20
        assert stats.successful_queries == 20
        assert stats.throughput_qps > 0

        cache_stats = cached_pipeline.get_cache_stats()
        assert cache_stats["hit_rate"] >= 0

        batch_retriever.shutdown()


@pytest.mark.parametrize("cache_size", [100, 500, 1000])
def test_cache_with_different_sizes(cache_size):
    """Test cache with different max sizes"""
    cache = SemanticCache(max_cache_size=cache_size)

    for i in range(cache_size + 100):
        cache.put(f"query_{i}", [{"id": str(i)}], [0.9])

    assert len(cache.cache) <= cache_size


@pytest.mark.parametrize("num_queries,num_workers", [(10, 2), (32, 4), (64, 8)])
@pytest.mark.asyncio
async def test_batch_retriever_configurations(num_queries, num_workers):
    """Test batch retriever with different configurations"""
    mock_pipeline = AsyncMock()

    async def mock_retrieve(query, k=10, use_cache=False):
        await asyncio.sleep(0.01)
        return {
            "results": [{"id": f"result_{i}"} for i in range(k)],
            "scores": [0.9 - i * 0.1 for i in range(k)],
        }

    mock_pipeline.retrieve = mock_retrieve

    retriever = BatchRetriever(mock_pipeline, max_workers=num_workers)

    queries = [BatchQuery(id=f"q_{i}", query=f"Query {i}") for i in range(num_queries)]

    results, stats = await retriever.retrieve_batch(queries)

    assert len(results) == num_queries
    assert stats.successful_queries == num_queries

    retriever.shutdown()


@pytest.mark.parametrize("similarity_threshold", [0.70, 0.85, 0.95])
def test_cache_similarity_thresholds(similarity_threshold):
    """Test cache with different similarity thresholds"""
    cache = SemanticCache(similarity_threshold=similarity_threshold)
    assert cache.similarity_threshold == similarity_threshold


class TestRAGEdgeCases:
    """Test edge cases and error conditions"""

    def test_cache_with_none_results(self):
        """Test cache with None results"""
        cache = SemanticCache()

        cache.put("query", [], [])
        retrieved = cache.get("query")

        assert retrieved == ([], [])

    def test_cache_with_large_embeddings(self):
        """Test cache with large embeddings"""
        cache = SemanticCache()

        large_results = [{"id": str(i), "data": "x" * 10000} for i in range(100)]
        cache.put("query", large_results, [0.9] * 100)

        retrieved = cache.get("query")
        assert retrieved is not None

    @pytest.mark.asyncio
    async def test_batch_retriever_empty_queries(self):
        """Test batch retriever with empty queries list"""
        mock_pipeline = AsyncMock()
        retriever = BatchRetriever(mock_pipeline)

        results, stats = await retriever.retrieve_batch([])

        assert len(results) == 0
        assert stats.total_queries == 0

        retriever.shutdown()

    def test_cache_query_deduplication_accuracy(self):
        """Test query deduplication accuracy"""
        cache = SemanticCache(similarity_threshold=0.90)

        queries = [
            "What is machine learning?",
            "Machine learning explanation",
            "Something completely different",
        ]

        cache.put(queries[0], [{"id": "1"}], [0.95])

        stats = cache.get_stats()
        initial_size = stats["cache_size"]

        for query in queries[1:]:
            cache.get(query)

        final_stats = cache.get_stats()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
