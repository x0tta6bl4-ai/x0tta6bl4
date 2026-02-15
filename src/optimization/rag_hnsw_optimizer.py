"""
Advanced HNSW Vector Search Optimization for RAG

Provides adaptive parameter tuning, query rewriting, advanced caching,
and performance optimization for HNSW-based similarity search.
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Types of queries for optimization"""

    SEMANTIC = "semantic"
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"


@dataclass
class HNSWParameters:
    """HNSW index parameters"""

    ef_construction: int = 200
    ef_search: int = 50
    max_elements: int = 10000
    m: int = 16
    seed: int = 0


@dataclass
class QueryOptimizationMetrics:
    """Query optimization metrics"""

    total_queries: int = 0
    cache_hits: int = 0
    rewrites_performed: int = 0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    index_updates: int = 0
    batch_operations: int = 0


class QueryRewriter:
    """Rewrite queries for better retrieval"""

    def __init__(self):
        self.synonyms = {
            "error": ["failure", "bug", "fault", "anomaly"],
            "performance": ["throughput", "latency", "speed"],
            "network": ["connectivity", "link", "bandwidth"],
            "memory": ["heap", "cache", "ram"],
        }
        self.expansion_cache: Dict[str, List[str]] = {}

    def expand_query(self, query: str) -> List[str]:
        """Expand query with synonyms for broader search"""
        if query in self.expansion_cache:
            return self.expansion_cache[query]

        variants = [query]
        query_lower = query.lower()

        for term, synonyms in self.synonyms.items():
            if term in query_lower:
                for synonym in synonyms:
                    variant = query_lower.replace(term, synonym)
                    variants.append(variant)

        self.expansion_cache[query] = variants
        return variants

    def rewrite_for_performance(self, query: str, result_quality: float) -> str:
        """Rewrite query based on result quality"""
        if result_quality > 0.8:
            return query

        words = query.split()
        if len(words) > 1:
            return " OR ".join(words[: len(words) // 2])

        return query


class AdaptiveParameterTuner:
    """Adaptively tune HNSW parameters based on workload"""

    def __init__(self):
        self.latency_history = deque(maxlen=100)
        self.query_count = 0
        self.current_params = HNSWParameters()
        self.param_history: List[Dict[str, Any]] = []

    def record_latency(self, latency_ms: float) -> None:
        """Record query latency"""
        self.latency_history.append(latency_ms)
        self.query_count += 1

    def get_p95_latency(self) -> float:
        """Get P95 latency"""
        if not self.latency_history:
            return 0.0
        sorted_latencies = sorted(self.latency_history)
        idx = int(len(sorted_latencies) * 0.95)
        return float(sorted_latencies[idx])

    def get_p99_latency(self) -> float:
        """Get P99 latency"""
        if not self.latency_history:
            return 0.0
        sorted_latencies = sorted(self.latency_history)
        idx = int(len(sorted_latencies) * 0.99)
        return float(sorted_latencies[idx])

    def adapt_parameters(self, target_latency_ms: float = 100) -> HNSWParameters:
        """Adapt HNSW parameters based on latency"""
        if len(self.latency_history) < 10:
            return self.current_params

        p95 = self.get_p95_latency()

        if p95 > target_latency_ms * 1.5:
            self.current_params.ef_search = min(self.current_params.ef_search - 5, 10)
            logger.info(f"Reduced ef_search to {self.current_params.ef_search}")
        elif p95 < target_latency_ms * 0.5:
            self.current_params.ef_search = min(self.current_params.ef_search + 10, 500)
            logger.info(f"Increased ef_search to {self.current_params.ef_search}")

        self.param_history.append(
            {
                "timestamp": time.time(),
                "ef_search": self.current_params.ef_search,
                "p95_latency_ms": p95,
            }
        )

        return self.current_params


class QueryCache:
    """Advanced query caching with TTL and LRU"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.access_times: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def put(self, key: str, value: Any) -> None:
        """Put item in cache"""
        self.cache[key] = (value, time.time())
        self.access_times[key] = time.time()

        if len(self.cache) > self.max_size:
            lru_key = min(self.access_times, key=self.access_times.get)
            del self.cache[lru_key]
            del self.access_times[lru_key]

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        if key not in self.cache:
            self.misses += 1
            return None

        value, timestamp = self.cache[key]

        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            del self.access_times[key]
            self.misses += 1
            return None

        self.access_times[key] = time.time()
        self.hits += 1
        return value

    def hit_rate(self) -> float:
        """Get cache hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class BatchRetrievalManager:
    """Manage batch retrieval operations"""

    def __init__(self, batch_size: int = 32):
        self.batch_size = batch_size
        self.pending_queries: List[Tuple[str, asyncio.Future]] = []
        self.batch_count = 0

    async def add_query(self, query: str) -> Any:
        """Add query to batch"""
        future = asyncio.Future()
        self.pending_queries.append((query, future))

        if len(self.pending_queries) >= self.batch_size:
            await self._process_batch()

        return await future

    async def _process_batch(self) -> None:
        """Process accumulated batch"""
        if not self.pending_queries:
            return

        batch = self.pending_queries[: self.batch_size]
        self.pending_queries = self.pending_queries[self.batch_size :]
        self.batch_count += 1

        queries = [q for q, _ in batch]
        futures = [f for _, f in batch]

        await asyncio.sleep(0.001)

        for i, future in enumerate(futures):
            if not future.done():
                future.set_result(f"result_{i}")

    async def flush(self) -> None:
        """Flush remaining queries"""
        if self.pending_queries:
            await self._process_batch()


class HNSWPerformanceOptimizer:
    """High-performance HNSW search optimizer"""

    def __init__(self, max_cache_size: int = 1000):
        self.query_cache = QueryCache(max_size=max_cache_size)
        self.query_rewriter = QueryRewriter()
        self.param_tuner = AdaptiveParameterTuner()
        self.batch_manager = BatchRetrievalManager()
        self.metrics = QueryOptimizationMetrics()
        self.latency_history: deque = deque(maxlen=1000)

    async def retrieve_with_optimization(
        self,
        query: str,
        retrieval_fn,
        k: int = 5,
        enable_rewrite: bool = True,
        enable_batch: bool = False,
    ) -> Tuple[List[Tuple[str, float]], Dict[str, Any]]:
        """
        Retrieve documents with full optimization

        Args:
            query: Query string
            retrieval_fn: Async retrieval function
            k: Number of results
            enable_rewrite: Enable query rewriting
            enable_batch: Enable batch processing

        Returns:
            Tuple of (results, optimization_stats)
        """
        start_time = time.time()
        optimization_info = {
            "cache_hit": False,
            "rewritten": False,
            "variants_tried": 1,
        }

        cache_key = self._make_cache_key(query, k)

        cached_result = self.query_cache.get(cache_key)
        if cached_result is not None:
            self.metrics.cache_hits += 1
            optimization_info["cache_hit"] = True
            results = cached_result
        else:
            if enable_rewrite:
                variants = self.query_rewriter.expand_query(query)
                optimization_info["variants_tried"] = len(variants)

                all_results = []
                for variant in variants:
                    try:
                        variant_results = await asyncio.wait_for(
                            retrieval_fn(variant, k=k), timeout=5.0
                        )
                        all_results.extend(variant_results)
                        self.metrics.rewrites_performed += 1
                        optimization_info["rewritten"] = True
                    except asyncio.TimeoutError:
                        logger.warning(f"Query variant timed out: {variant}")

                if all_results:
                    results = self._deduplicate_and_rank(all_results)[:k]
                else:
                    results = await retrieval_fn(query, k=k)
            else:
                results = await retrieval_fn(query, k=k)

            self.query_cache.put(cache_key, results)

        elapsed_ms = (time.time() - start_time) * 1000
        self.latency_history.append(elapsed_ms)
        self.param_tuner.record_latency(elapsed_ms)
        self.metrics.total_queries += 1
        self.metrics.avg_latency_ms = sum(self.latency_history) / len(
            self.latency_history
        )
        self.metrics.p95_latency_ms = self.param_tuner.get_p95_latency()
        self.metrics.p99_latency_ms = self.param_tuner.get_p99_latency()

        optimization_info["latency_ms"] = elapsed_ms
        optimization_info["cache_hit_rate"] = self.query_cache.hit_rate()

        return results, optimization_info

    def _make_cache_key(self, query: str, k: int) -> str:
        """Create cache key from query"""
        normalized = query.lower().strip()
        return f"{normalized}:k{k}"

    def _deduplicate_and_rank(
        self, results: List[Tuple[str, float]]
    ) -> List[Tuple[str, float]]:
        """Deduplicate and rank results"""
        seen = {}
        for doc_id, score in results:
            if doc_id not in seen or seen[doc_id] < score:
                seen[doc_id] = score

        sorted_results = sorted(seen.items(), key=lambda x: x[1], reverse=True)
        return sorted_results

    async def batch_retrieve(
        self, queries: List[str], retrieval_fn, k: int = 5
    ) -> Dict[str, List[Tuple[str, float]]]:
        """
        Retrieve multiple queries in batch

        Args:
            queries: List of queries
            retrieval_fn: Async retrieval function
            k: Results per query

        Returns:
            Dict mapping queries to results
        """
        self.metrics.batch_operations += 1

        tasks = [self.retrieve_with_optimization(q, retrieval_fn, k=k) for q in queries]

        results_list = await asyncio.gather(*tasks)

        return {query: results for query, (results, _) in zip(queries, results_list)}

    def get_metrics(self) -> Dict[str, Any]:
        """Get optimization metrics"""
        return {
            "total_queries": self.metrics.total_queries,
            "cache_hits": self.metrics.cache_hits,
            "cache_hit_rate_percent": (
                self.metrics.cache_hits / self.metrics.total_queries * 100
                if self.metrics.total_queries > 0
                else 0
            ),
            "rewrites_performed": self.metrics.rewrites_performed,
            "avg_latency_ms": round(self.metrics.avg_latency_ms, 3),
            "p95_latency_ms": round(self.metrics.p95_latency_ms, 3),
            "p99_latency_ms": round(self.metrics.p99_latency_ms, 3),
            "batch_operations": self.metrics.batch_operations,
            "current_parameters": {
                "ef_search": self.param_tuner.current_params.ef_search,
                "ef_construction": self.param_tuner.current_params.ef_construction,
            },
        }

    def get_adaptive_parameters(self) -> HNSWParameters:
        """Get currently adapted parameters"""
        return self.param_tuner.adapt_parameters()

    def clear_cache(self) -> None:
        """Clear query cache"""
        self.query_cache.cache.clear()
        self.query_cache.access_times.clear()
        logger.info("Cleared HNSW optimization cache")


def create_hnsw_optimizer(max_cache_size: int = 1000) -> HNSWPerformanceOptimizer:
    """Factory function to create HNSW optimizer"""
    return HNSWPerformanceOptimizer(max_cache_size=max_cache_size)
