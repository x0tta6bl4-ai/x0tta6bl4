"""
Phase 9: Performance Optimization Tests

Tests for caching, quantization, and concurrency improvements.
"""

import pytest
import asyncio
import time
import numpy as np
from datetime import datetime

from src.optimization.performance_core import (
    LRUCache,
    AsyncCache,
    RateLimiter,
    PerformanceOptimizer,
    LoRAQuantizer,
    QuantizationConfig,
    ConcurrencyOptimizer,
    get_performance_optimizer,
    test_performance_optimization,
)
from src.optimization.rag_optimizer import (
    QueryNormalizer,
    SemanticIndexer,
    RAGOptimizer,
    BatchRetrievalOptimizer,
    get_rag_optimizer,
    test_rag_optimization,
)


# ========== CACHE TESTS ==========

class TestLRUCache:
    """LRU cache tests"""
    
    def test_cache_initialization(self):
        """Test cache initialization"""
        cache = LRUCache(max_size=100)
        assert cache.max_size == 100
        assert cache.stats.hits == 0
        assert cache.stats.misses == 0
    
    def test_cache_set_get(self):
        """Test basic cache operations"""
        cache = LRUCache(max_size=10)
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.stats.hits == 1
    
    def test_cache_miss(self):
        """Test cache miss"""
        cache = LRUCache(max_size=10)
        
        result = cache.get("nonexistent")
        assert result is None
        assert cache.stats.misses == 1
    
    def test_cache_eviction(self):
        """Test cache eviction on overflow"""
        cache = LRUCache(max_size=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1
        
        assert cache.get("key1") is None
        assert cache.get("key4") is not None
        assert cache.stats.evictions >= 1
    
    def test_cache_hit_rate(self):
        """Test hit rate calculation"""
        cache = LRUCache(max_size=10)
        
        cache.set("key", "value")
        cache.get("key")  # Hit
        cache.get("key")  # Hit
        cache.get("missing")  # Miss
        
        stats = cache.get_stats()
        assert stats.hit_rate > 0.5


class TestAsyncCache:
    """Async cache tests"""
    
    @pytest.mark.asyncio
    async def test_async_cache_get_set(self):
        """Test async cache get/set"""
        cache = AsyncCache(max_size=100)
        
        await cache.set("key", "value")
        result = await cache.get("key")
        
        assert result == "value"
    
    @pytest.mark.asyncio
    async def test_async_get_or_compute(self):
        """Test async get_or_compute with caching"""
        cache = AsyncCache(max_size=100)
        call_count = 0
        
        async def compute(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call should compute
        result1 = await cache.get_or_compute("key", compute, 5)
        assert result1 == 10
        assert call_count == 1
        
        # Second call should use cache
        result2 = await cache.get_or_compute("key", compute, 5)
        assert result2 == 10
        assert call_count == 1  # Not called again
    
    @pytest.mark.asyncio
    async def test_async_thundering_herd_prevention(self):
        """Test prevention of thundering herd"""
        cache = AsyncCache(max_size=100)
        compute_count = 0
        
        async def slow_compute(x):
            nonlocal compute_count
            compute_count += 1
            await asyncio.sleep(0.1)
            return x
        
        # Multiple concurrent calls for same key
        tasks = [
            cache.get_or_compute("key", slow_compute, 1)
            for _ in range(5)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Should only compute once due to locking
        assert compute_count <= 1
        assert all(r == 1 for r in results)


class TestRateLimiter:
    """Rate limiter tests"""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_tokens(self):
        """Test rate limiter token management"""
        limiter = RateLimiter(rate=10.0, burst=100)
        
        # Should allow burst
        wait1 = await limiter.acquire(50)
        assert wait1 == 0.0
        
        # Should wait for more tokens
        wait2 = await limiter.acquire(100)
        assert wait2 > 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_wait(self):
        """Test rate limiter wait"""
        limiter = RateLimiter(rate=10.0, burst=1)
        
        start = time.time()
        await limiter.wait_if_needed(1)  # Should be instant (within burst)
        elapsed = time.time() - start
        
        assert elapsed < 0.1


# ========== QUANTIZATION TESTS ==========

class TestLoRAQuantizer:
    """LoRA quantization tests"""
    
    def test_quantizer_initialization(self):
        """Test quantizer initialization"""
        config = QuantizationConfig(bit_width=8)
        quantizer = LoRAQuantizer(config)
        
        assert quantizer.config.bit_width == 8
    
    def test_quantization_8bit(self):
        """Test 8-bit quantization"""
        quantizer = LoRAQuantizer(QuantizationConfig(bit_width=8))
        
        weights = np.random.randn(100, 100).astype(np.float32)
        result = quantizer.quantize_weights(weights)
        
        assert result["quantized"] is True
        assert result["bit_width"] == 8
        assert result["compression_ratio"] >= 2.0
        assert result["memory_saved_percent"] > 40
    
    def test_quantization_16bit(self):
        """Test 16-bit quantization"""
        quantizer = LoRAQuantizer(QuantizationConfig(bit_width=16))
        
        weights = np.random.randn(100, 100).astype(np.float32)
        result = quantizer.quantize_weights(weights)
        
        assert result["quantized"] is True
        assert result["compression_ratio"] >= 1.5
    
    def test_speedup_estimation(self):
        """Test speedup estimation"""
        quantizer = LoRAQuantizer(QuantizationConfig(bit_width=8))
        
        speedup_info = quantizer.estimate_speedup()
        assert speedup_info["estimated_speedup"] >= 1.5


# ========== PERFORMANCE OPTIMIZER TESTS ==========

class TestPerformanceOptimizer:
    """Performance optimizer tests"""
    
    def test_optimizer_initialization(self):
        """Test optimizer initialization"""
        optimizer = get_performance_optimizer()
        assert optimizer is not None
    
    @pytest.mark.asyncio
    async def test_cached_ml_operation(self):
        """Test cached ML operation"""
        optimizer = get_performance_optimizer()
        
        call_count = 0
        
        async def ml_op(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # First call
        result1 = await optimizer.cached_ml_operation("test", ml_op, 5)
        assert result1 == 10
        
        # Second call should hit cache
        result2 = await optimizer.cached_ml_operation("test", ml_op, 5)
        assert result2 == 10
    
    @pytest.mark.asyncio
    async def test_performance_report(self):
        """Test performance report"""
        optimizer = get_performance_optimizer()
        
        async def dummy(x):
            return x
        
        await optimizer.cached_ml_operation("test", dummy, 1)
        
        report = optimizer.get_performance_report()
        
        assert "ml_cache" in report
        assert "rag_cache" in report
        assert "pqc_cache" in report


# ========== CONCURRENCY OPTIMIZER TESTS ==========

class TestConcurrencyOptimizer:
    """Concurrency optimizer tests"""
    
    def test_concurrency_initialization(self):
        """Test concurrency optimizer initialization"""
        optimizer = ConcurrencyOptimizer(max_concurrent=5)
        assert optimizer.max_concurrent == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Test concurrent task execution"""
        optimizer = ConcurrencyOptimizer(max_concurrent=3)
        
        async def task(i):
            await asyncio.sleep(0.01)
            return i
        
        tasks = [task(i) for i in range(5)]
        results = await optimizer.run_concurrent(tasks)
        
        assert len(results) == 5


# ========== RAG OPTIMIZER TESTS ==========

class TestQueryNormalizer:
    """Query normalizer tests"""
    
    def test_query_normalization(self):
        """Test query normalization"""
        query1 = "What is MAPE-K?"
        query2 = "what is mape-k"
        
        normalized1 = QueryNormalizer.normalize(query1)
        normalized2 = QueryNormalizer.normalize(query2)
        
        assert normalized1 == normalized2
    
    def test_cache_key_generation(self):
        """Test cache key generation"""
        key1 = QueryNormalizer.generate_cache_key("test query")
        key2 = QueryNormalizer.generate_cache_key("test query")
        
        assert key1 == key2


class TestSemanticIndexer:
    """Semantic indexer tests"""
    
    def test_document_indexing(self):
        """Test document indexing"""
        indexer = SemanticIndexer()
        
        indexer.index_document("doc1", "Content of document 1")
        doc = indexer.get_document("doc1")
        
        assert doc is not None
        assert doc["content"] == "Content of document 1"
    
    def test_similarity_search(self):
        """Test similarity search"""
        indexer = SemanticIndexer()
        
        indexer.index_document("doc1", "Content 1")
        indexer.index_document("doc2", "Content 2")
        
        results = indexer.search_similar("test query", k=2)
        assert len(results) <= 2


class TestRAGOptimizer:
    """RAG optimizer tests"""
    
    def test_optimizer_initialization(self):
        """Test RAG optimizer initialization"""
        optimizer = get_rag_optimizer()
        assert optimizer is not None
    
    @pytest.mark.asyncio
    async def test_retrieval_caching(self):
        """Test retrieval caching"""
        optimizer = RAGOptimizer()
        
        call_count = 0
        
        async def retrieve(query, k=5):
            nonlocal call_count
            call_count += 1
            return [f"doc_{i}" for i in range(k)]
        
        # First call
        result1 = await optimizer.retrieve_with_caching("test query", retrieve)
        
        # Second call should hit cache
        result2 = await optimizer.retrieve_with_caching("test query", retrieve)
        
        assert result1 == result2
        assert call_count == 1  # Only called once
    
    @pytest.mark.asyncio
    async def test_prefetching(self):
        """Test query prefetching"""
        optimizer = RAGOptimizer()
        
        async def retrieve(query, k=5):
            await asyncio.sleep(0.01)
            return [f"doc_{i}" for i in range(k)]
        
        common_queries = ["query 1", "query 2", "query 3"]
        optimizer.prefetch_common_queries(common_queries, retrieve)
        
        # Wait for prefetch to complete
        await asyncio.sleep(0.1)
        
        # Cache should be populated
        assert len(optimizer.query_cache) > 0


class TestBatchRetrieval:
    """Batch retrieval optimizer tests"""
    
    @pytest.mark.asyncio
    async def test_batch_retrieval(self):
        """Test batch retrieval"""
        batch_opt = BatchRetrievalOptimizer(batch_size=5)
        
        async def retrieve(query, k=5):
            await asyncio.sleep(0.01)
            return [f"doc_{i}" for i in range(k)]
        
        queries = [f"query_{i}" for i in range(15)]
        results = await batch_opt.retrieve_batch(queries, retrieve)
        
        assert len(results) == 15


# ========== INTEGRATION TESTS ==========

class TestPhase9Integration:
    """Phase 9 integration tests"""
    
    @pytest.mark.asyncio
    async def test_performance_optimization_integration(self):
        """Test performance optimization integration"""
        result = await test_performance_optimization()
        
        assert result["status"] == "success"
        assert "performance" in result
    
    @pytest.mark.asyncio
    async def test_rag_optimization_integration(self):
        """Test RAG optimization integration"""
        result = await test_rag_optimization()
        
        assert result["status"] == "success"
        assert "metrics" in result


# ========== FIXTURES ==========

@pytest.fixture
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
