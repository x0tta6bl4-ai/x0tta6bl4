"""
Semantic Caching for RAG Pipeline

Implements intelligent caching for RAG queries using semantic similarity.
Deduplicates similar queries and caches retrieval results for performance.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import OrderedDict
from datetime import datetime, timedelta
import hashlib
import json
import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("⚠️ sentence-transformers not available for semantic cache")


@dataclass
class CachedResult:
    """Cached RAG retrieval result"""
    query: str
    query_embedding: np.ndarray
    results: List[Dict[str, Any]]
    scores: List[float]
    timestamp: datetime
    hit_count: int = 0
    ttl_seconds: int = 3600
    
    @property
    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        age = datetime.now() - self.timestamp
        return age.total_seconds() > self.ttl_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        return {
            "query": self.query,
            "query_embedding": self.query_embedding.tolist() if isinstance(self.query_embedding, np.ndarray) else self.query_embedding,
            "results": self.results,
            "scores": self.scores,
            "timestamp": self.timestamp.isoformat(),
            "hit_count": self.hit_count,
            "ttl_seconds": self.ttl_seconds
        }


class SemanticCache:
    """
    Semantic cache for RAG pipeline.
    
    Features:
    - Query deduplication based on semantic similarity
    - Automatic cache expiration (TTL)
    - LRU eviction policy
    - Hit/miss tracking
    - Optional persistence
    """
    
    def __init__(
        self,
        max_cache_size: int = 1000,
        similarity_threshold: float = 0.95,
        ttl_seconds: int = 3600,
        enable_embedding_model: bool = True
    ):
        """
        Initialize semantic cache.
        
        Args:
            max_cache_size: Maximum number of cached entries
            similarity_threshold: Threshold for query deduplication (0-1)
            ttl_seconds: Time-to-live for cache entries
            enable_embedding_model: Use embedding model for similarity
        """
        self.max_cache_size = max_cache_size
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        
        self.cache: OrderedDict[str, CachedResult] = OrderedDict()
        self.embedding_model = None
        self.embedding_dim = 384
        
        if enable_embedding_model and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("✅ SemanticCache initialized with embedding model")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load embedding model for cache: {e}")
        
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0
        }
    
    def _get_query_embedding(self, query: str) -> np.ndarray:
        """Generate embedding for query"""
        if self.embedding_model:
            try:
                embedding = self.embedding_model.encode(query, convert_to_numpy=True)
                return embedding.astype(np.float32)
            except Exception as e:
                logger.error(f"Failed to generate query embedding: {e}")
        
        return np.zeros(self.embedding_dim, dtype=np.float32)
    
    def _compute_query_hash(self, query: str) -> str:
        """Compute hash of query for fast lookup"""
        return hashlib.sha256(query.encode()).hexdigest()
    
    def _compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings"""
        if len(emb1) == 0 or len(emb2) == 0:
            return 0.0
        
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(np.dot(emb1, emb2) / (norm1 * norm2))
    
    def _find_similar_cached_query(self, query_embedding: np.ndarray) -> Optional[str]:
        """Find most similar cached query"""
        if not self.embedding_model:
            return None
        
        best_key = None
        best_similarity = self.similarity_threshold
        
        for cache_key, cached_result in self.cache.items():
            if cached_result.is_expired:
                continue
            
            similarity = self._compute_similarity(query_embedding, cached_result.query_embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_key = cache_key
        
        return best_key
    
    def get(self, query: str) -> Optional[Tuple[List[Dict], List[float]]]:
        """
        Retrieve cached result if available.
        
        Args:
            query: Query string
            
        Returns:
            Tuple of (results, scores) or None if not cached
        """
        query_hash = self._compute_query_hash(query)
        
        if query_hash in self.cache:
            cached = self.cache[query_hash]
            
            if cached.is_expired:
                del self.cache[query_hash]
                self.stats['expirations'] += 1
                self.stats['misses'] += 1
                return None
            
            cached.hit_count += 1
            self.cache.move_to_end(query_hash)
            self.stats['hits'] += 1
            
            logger.debug(f"Cache HIT for exact query match")
            return (cached.results, cached.scores)
        
        query_embedding = self._get_query_embedding(query)
        similar_key = self._find_similar_cached_query(query_embedding)
        
        if similar_key:
            cached = self.cache[similar_key]
            
            if cached.is_expired:
                del self.cache[similar_key]
                self.stats['expirations'] += 1
                self.stats['misses'] += 1
                return None
            
            cached.hit_count += 1
            self.cache.move_to_end(similar_key)
            self.stats['hits'] += 1
            
            logger.debug(f"Cache HIT for query (similar to: '{cached.query[:50]}...')")
            return (cached.results, cached.scores)
        
        self.stats['misses'] += 1
        return None
    
    def put(
        self,
        query: str,
        results: List[Dict[str, Any]],
        scores: List[float]
    ) -> None:
        """
        Cache retrieval result.
        
        Args:
            query: Query string
            results: Retrieval results
            scores: Result scores/similarities
        """
        query_embedding = self._get_query_embedding(query)
        query_hash = self._compute_query_hash(query)
        
        cached_result = CachedResult(
            query=query,
            query_embedding=query_embedding,
            results=results,
            scores=scores,
            timestamp=datetime.now(),
            ttl_seconds=self.ttl_seconds
        )
        
        self.cache[query_hash] = cached_result
        self.cache.move_to_end(query_hash)
        
        while len(self.cache) > self.max_cache_size:
            evicted_key = next(iter(self.cache))
            del self.cache[evicted_key]
            self.stats['evictions'] += 1
    
    def clear_expired(self) -> int:
        """Remove expired cache entries"""
        expired_keys = [
            key for key, cached in self.cache.items()
            if cached.is_expired
        ]
        
        for key in expired_keys:
            del self.cache[key]
            self.stats['expirations'] += 1
        
        return len(expired_keys)
    
    def clear(self) -> None:
        """Clear all cache"""
        self.cache.clear()
        logger.info("Semantic cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'cache_size': len(self.cache),
            'max_cache_size': self.max_cache_size,
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': hit_rate,
            'evictions': self.stats['evictions'],
            'expirations': self.stats['expirations'],
            'total_requests': total_requests
        }
    
    def set_ttl(self, ttl_seconds: int) -> None:
        """Update TTL for future cache entries"""
        self.ttl_seconds = ttl_seconds
        logger.info(f"Cache TTL updated to {ttl_seconds}s")
    
    def set_similarity_threshold(self, threshold: float) -> None:
        """Update similarity threshold for query deduplication"""
        if not 0 <= threshold <= 1:
            raise ValueError("Threshold must be between 0 and 1")
        self.similarity_threshold = threshold
        logger.info(f"Cache similarity threshold updated to {threshold}")


class CachedRAGPipeline:
    """
    RAG Pipeline with semantic caching.
    
    Wraps existing RAG pipeline with semantic cache layer.
    """
    
    def __init__(
        self,
        rag_pipeline,
        cache_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize cached RAG pipeline.
        
        Args:
            rag_pipeline: Underlying RAG pipeline
            cache_config: Cache configuration dict
        """
        self.rag_pipeline = rag_pipeline
        
        cache_config = cache_config or {}
        self.cache = SemanticCache(
            max_cache_size=cache_config.get('max_size', 1000),
            similarity_threshold=cache_config.get('similarity_threshold', 0.95),
            ttl_seconds=cache_config.get('ttl_seconds', 3600),
            enable_embedding_model=cache_config.get('enable_embedding', True)
        )
    
    async def retrieve(
        self,
        query: str,
        k: int = 10,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Retrieve with semantic caching.
        
        Args:
            query: Query string
            k: Number of results
            use_cache: Enable caching
            
        Returns:
            Retrieval result with cache info
        """
        start_time = time.time()
        cache_hit = False
        
        if use_cache:
            cached = self.cache.get(query)
            if cached:
                results, scores = cached
                cache_hit = True
                cache_latency_ms = (time.time() - start_time) * 1000
                
                return {
                    'results': results,
                    'scores': scores,
                    'cache_hit': True,
                    'cache_latency_ms': cache_latency_ms
                }
        
        result = await self.rag_pipeline.retrieve(query, k=k)
        
        if use_cache:
            self.cache.put(query, result.get('results', []), result.get('scores', []))
        
        retrieval_latency_ms = (time.time() - start_time) * 1000
        result['cache_hit'] = False
        result['cache_latency_ms'] = retrieval_latency_ms
        
        return result
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()
    
    def clear_cache(self) -> None:
        """Clear cache"""
        self.cache.clear()
    
    def clear_expired_cache(self) -> int:
        """Clear expired cache entries"""
        return self.cache.clear_expired()
