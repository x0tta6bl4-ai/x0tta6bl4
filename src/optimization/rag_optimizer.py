"""
RAG Optimization Module

Query caching, semantic indexing, and retrieval acceleration
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class RAGOptimizationMetrics:
    """RAG optimization metrics"""
    cache_hit_rate: float = 0.0
    avg_retrieval_time_ms: float = 0.0
    index_size_mb: float = 0.0
    queries_cached: int = 0
    unique_queries: int = 0
    memory_saved_percent: float = 0.0


class QueryNormalizer:
    """Normalize queries for better caching"""
    
    @staticmethod
    def normalize(query: str) -> str:
        """
        Normalize query for cache key
        
        Args:
            query: Original query
            
        Returns:
            Normalized query
        """
        # Convert to lowercase
        normalized = query.lower()
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        # Remove punctuation variations
        normalized = normalized.replace("?", "").replace("!", "")
        
        return normalized
    
    @staticmethod
    def generate_cache_key(query: str, k: int = 5) -> str:
        """Generate cache key from query"""
        normalized = QueryNormalizer.normalize(query)
        key = f"{normalized}:k{k}"
        return hashlib.md5(key.encode()).hexdigest()


class SemanticIndexer:
    """Semantic indexing for RAG"""
    
    def __init__(self):
        """Initialize semantic indexer"""
        self.query_index: Dict[str, List[str]] = {}  # semantic -> queries
        self.document_cache: Dict[str, Any] = {}  # document_id -> doc
    
    def index_document(self, doc_id: str, content: str, embedding: Optional[List[float]] = None) -> None:
        """
        Index document
        
        Args:
            doc_id: Document ID
            content: Document content
            embedding: Semantic embedding
        """
        self.document_cache[doc_id] = {
            "id": doc_id,
            "content": content,
            "embedding": embedding,
            "indexed_at": datetime.utcnow(),
        }
        
        logger.debug(f"Indexed document: {doc_id}")
    
    def search_similar(self, query: str, k: int = 5) -> List[str]:
        """
        Search for similar documents
        
        Args:
            query: Query string
            k: Number of results
            
        Returns:
            List of document IDs
        """
        # Simple implementation - in production use FAISS, Annoy, etc.
        if not self.document_cache:
            return []
        
        # Return first k documents
        return list(self.document_cache.keys())[:k]
    
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get cached document"""
        return self.document_cache.get(doc_id)


class RAGOptimizer:
    """RAG optimization layer"""
    
    def __init__(self, cache_size: int = 5000):
        """
        Initialize RAG optimizer
        
        Args:
            cache_size: Query cache size
        """
        self.query_cache: Dict[str, List[str]] = {}
        self.cache_size = cache_size
        self.indexer = SemanticIndexer()
        self.metrics = RAGOptimizationMetrics()
        self.retrieval_times: List[float] = []
    
    async def retrieve_with_caching(
        self,
        query: str,
        retrieval_fn,
        k: int = 5,
        use_semantic_indexing: bool = True
    ) -> List[str]:
        """
        Retrieve documents with caching
        
        Args:
            query: Query string
            retrieval_fn: Async retrieval function
            k: Number of results
            use_semantic_indexing: Use semantic indexing
            
        Returns:
            Retrieved document IDs
        """
        import time
        start = time.time()
        
        # Generate cache key
        cache_key = QueryNormalizer.generate_cache_key(query, k)
        
        # Check cache
        if cache_key in self.query_cache:
            self.metrics.cache_hit_rate = (
                (self.metrics.cache_hit_rate * self.metrics.queries_cached + 1) /
                (self.metrics.queries_cached + 1)
            )
            self.metrics.queries_cached += 1
            
            elapsed = (time.time() - start) * 1000
            self.retrieval_times.append(elapsed)
            self.metrics.avg_retrieval_time_ms = sum(self.retrieval_times) / len(self.retrieval_times)
            
            return self.query_cache[cache_key]
        
        # Try semantic index first
        if use_semantic_indexing:
            results = self.indexer.search_similar(query, k)
            if results:
                self.query_cache[cache_key] = results
                self.metrics.unique_queries += 1
                
                elapsed = (time.time() - start) * 1000
                self.retrieval_times.append(elapsed)
                self.metrics.avg_retrieval_time_ms = sum(self.retrieval_times) / len(self.retrieval_times)
                
                return results
        
        # Fall back to full retrieval
        results = await retrieval_fn(query, k=k)
        
        # Cache results
        self.query_cache[cache_key] = results
        self.metrics.unique_queries += 1
        
        # Manage cache size
        if len(self.query_cache) > self.cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.query_cache))
            del self.query_cache[oldest_key]
        
        elapsed = (time.time() - start) * 1000
        self.retrieval_times.append(elapsed)
        self.metrics.avg_retrieval_time_ms = sum(self.retrieval_times) / len(self.retrieval_times)
        
        return results
    
    def prefetch_common_queries(
        self,
        common_queries: List[str],
        retrieval_fn
    ) -> None:
        """
        Prefetch common queries
        
        Args:
            common_queries: List of common queries
            retrieval_fn: Retrieval function
        """
        # Run in background
        asyncio.create_task(
            self._prefetch_async(common_queries, retrieval_fn)
        )
    
    async def _prefetch_async(self, queries: List[str], retrieval_fn) -> None:
        """Prefetch queries asynchronously"""
        for query in queries:
            cache_key = QueryNormalizer.generate_cache_key(query)
            if cache_key not in self.query_cache:
                try:
                    results = await retrieval_fn(query, k=5)
                    self.query_cache[cache_key] = results
                except Exception as e:
                    logger.error(f"Prefetch failed for query '{query}': {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get optimization metrics"""
        return {
            "cache_hit_rate_percent": self.metrics.cache_hit_rate * 100,
            "avg_retrieval_time_ms": self.metrics.avg_retrieval_time_ms,
            "cached_queries": self.metrics.queries_cached,
            "unique_queries": self.metrics.unique_queries,
        }
    
    def clear_cache(self) -> None:
        """Clear query cache"""
        self.query_cache.clear()
        logger.info("Cleared RAG query cache")


class BatchRetrievalOptimizer:
    """Batch retrieval optimization"""
    
    def __init__(self, batch_size: int = 10):
        """
        Initialize batch optimizer
        
        Args:
            batch_size: Batch size for retrieval
        """
        self.batch_size = batch_size
    
    async def retrieve_batch(
        self,
        queries: List[str],
        retrieval_fn,
        k: int = 5
    ) -> Dict[str, List[str]]:
        """
        Retrieve multiple queries in batches
        
        Args:
            queries: List of queries
            retrieval_fn: Async retrieval function
            k: Results per query
            
        Returns:
            Dict mapping queries to results
        """
        results = {}
        
        # Process in batches
        for i in range(0, len(queries), self.batch_size):
            batch = queries[i:i + self.batch_size]
            
            # Process batch concurrently
            batch_results = await asyncio.gather(*[
                retrieval_fn(q, k=k) for q in batch
            ])
            
            for query, result in zip(batch, batch_results):
                results[query] = result
        
        return results


# Global instance
_rag_optimizer: Optional[RAGOptimizer] = None


def get_rag_optimizer() -> RAGOptimizer:
    """Get or create RAG optimizer"""
    global _rag_optimizer
    if _rag_optimizer is None:
        _rag_optimizer = RAGOptimizer()
    return _rag_optimizer


async def test_rag_optimization() -> Dict[str, Any]:
    """Test RAG optimization"""
    optimizer = get_rag_optimizer()
    
    # Simulate retrieval function
    async def mock_retrieve(query: str, k: int = 5) -> List[str]:
        await asyncio.sleep(0.01)  # Simulate network latency
        return [f"doc_{i}" for i in range(k)]
    
    # Run retrievals with repetition to test caching
    queries = ["test query", "another query", "test query"]
    
    for query in queries:
        await optimizer.retrieve_with_caching(query, mock_retrieve)
    
    return {
        "status": "success",
        "metrics": optimizer.get_metrics(),
    }
