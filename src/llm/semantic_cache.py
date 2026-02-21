"""
Semantic Cache for LLM Responses
================================

Intelligent caching system that uses semantic similarity
to return cached responses for semantically similar queries.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry."""
    query: str
    response: str
    embedding: Optional[List[float]] = None
    model: str = ""
    provider: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "response": self.response,
            "embedding": self.embedding,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
            "access_count": self.access_count,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


class SemanticCache:
    """
    Semantic cache for LLM responses.
    
    Features:
    - Exact match caching (fast)
    - Semantic similarity matching (intelligent)
    - LRU eviction policy
    - TTL-based expiration
    - Thread-safe operations
    - Memory-efficient storage
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        similarity_threshold: float = 0.95,
        enable_semantic: bool = True,
    ):
        """
        Initialize semantic cache.
        
        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live for entries in seconds
            similarity_threshold: Minimum similarity for semantic match (0-1)
            enable_semantic: Enable semantic similarity matching
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.enable_semantic = enable_semantic
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._embedder: Optional[Any] = None
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._semantic_hits = 0
        
    def _compute_hash(self, query: str, model: str = "") -> str:
        """Compute hash key for exact matching."""
        content = f"{model}:{query}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _cosine_similarity(
        self,
        vec1: List[float],
        vec2: List[float]
    ) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
            
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        return dot_product / (norm1 * norm2)
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for better matching."""
        # Lowercase, strip whitespace, normalize spaces
        normalized = " ".join(query.lower().strip().split())
        return normalized
    
    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if entry has expired."""
        age = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
        return age > self.ttl_seconds
    
    def _evict_expired(self) -> int:
        """Remove expired entries. Returns count of evicted entries."""
        evicted = 0
        keys_to_remove = []
        
        for key, entry in self._cache.items():
            if self._is_expired(entry):
                keys_to_remove.append(key)
                
        for key in keys_to_remove:
            del self._cache[key]
            evicted += 1
            
        return evicted
    
    def _evict_lru(self) -> None:
        """Evict least recently used entries if over capacity."""
        while len(self._cache) >= self.max_size:
            # Remove oldest entry (first in OrderedDict)
            self._cache.popitem(last=False)
    
    def set_embedder(self, embedder: Any) -> None:
        """
        Set the embedding function for semantic matching.
        
        Args:
            embedder: Object with an `embed(text) -> List[float]` method
        """
        self._embedder = embedder
    
    def get(
        self,
        query: str,
        model: str = "",
        check_semantic: bool = True,
    ) -> Optional[CacheEntry]:
        """
        Get cached response for query.
        
        Args:
            query: Input query
            model: Model identifier
            check_semantic: Whether to check semantic similarity
            
        Returns:
            CacheEntry if found, None otherwise
        """
        with self._lock:
            # Clean expired entries periodically
            if len(self._cache) > self.max_size // 2:
                self._evict_expired()
            
            # Try exact match first
            key = self._compute_hash(query, model)
            if key in self._cache:
                entry = self._cache[key]
                if not self._is_expired(entry):
                    entry.access_count += 1
                    # Move to end (most recently used)
                    self._cache.move_to_end(key)
                    self._hits += 1
                    logger.debug(f"Cache hit (exact): {query[:50]}...")
                    return entry
                else:
                    del self._cache[key]
            
            # Try semantic match if enabled
            if check_semantic and self.enable_semantic and self._embedder:
                query_embedding = self._get_embedding(query)
                if query_embedding:
                    best_match: Optional[Tuple[str, CacheEntry, float]] = None
                    
                    for cache_key, entry in self._cache.items():
                        if entry.embedding and not self._is_expired(entry):
                            similarity = self._cosine_similarity(
                                query_embedding, entry.embedding
                            )
                            if similarity >= self.similarity_threshold:
                                if best_match is None or similarity > best_match[2]:
                                    best_match = (cache_key, entry, similarity)
                    
                    if best_match:
                        _, entry, similarity = best_match
                        entry.access_count += 1
                        self._cache.move_to_end(best_match[0])
                        self._hits += 1
                        self._semantic_hits += 1
                        logger.debug(
                            f"Cache hit (semantic, similarity={similarity:.3f}): "
                            f"{query[:50]}..."
                        )
                        return entry
            
            self._misses += 1
            return None
    
    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding for text using configured embedder."""
        if not self._embedder:
            return None
            
        try:
            if hasattr(self._embedder, "embed"):
                result = self._embedder.embed(text)
                if hasattr(result, "embedding"):
                    return result.embedding
                return result
        except Exception as e:
            logger.warning(f"Failed to get embedding: {e}")
            
        return None
    
    def set(
        self,
        query: str,
        response: str,
        model: str = "",
        provider: str = "",
        tokens_used: int = 0,
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store response in cache.
        
        Args:
            query: Input query
            response: Generated response
            model: Model identifier
            provider: Provider name
            tokens_used: Number of tokens used
            latency_ms: Generation latency in milliseconds
            metadata: Additional metadata
        """
        with self._lock:
            # Evict if at capacity
            self._evict_lru()
            
            key = self._compute_hash(query, model)
            
            # Get embedding for semantic matching
            embedding = None
            if self.enable_semantic and self._embedder:
                embedding = self._get_embedding(query)
            
            entry = CacheEntry(
                query=query,
                response=response,
                embedding=embedding,
                model=model,
                provider=provider,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                metadata=metadata or {},
            )
            
            # Remove old entry if exists
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = entry
            logger.debug(f"Cached response for: {query[:50]}...")
    
    def invalidate(self, query: str, model: str = "") -> bool:
        """
        Invalidate a specific cache entry.
        
        Returns:
            True if entry was found and removed
        """
        with self._lock:
            key = self._compute_hash(query, model)
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
            self._semantic_hits = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            semantic_rate = (
                self._semantic_hits / self._hits if self._hits > 0 else 0.0
            )
            
            # Calculate memory usage estimate
            total_size = sum(
                len(e.query) + len(e.response) + 
                (len(e.embedding) * 8 if e.embedding else 0)
                for e in self._cache.values()
            )
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "semantic_hits": self._semantic_hits,
                "hit_rate": hit_rate,
                "semantic_hit_rate": semantic_rate,
                "ttl_seconds": self.ttl_seconds,
                "similarity_threshold": self.similarity_threshold,
                "estimated_memory_bytes": total_size,
            }
    
    def get_entries(self) -> List[CacheEntry]:
        """Get all cache entries."""
        with self._lock:
            return list(self._cache.values())
    
    def save_to_file(self, filepath: str) -> bool:
        """Save cache to file."""
        try:
            with self._lock:
                data = {
                    "entries": [e.to_dict() for e in self._cache.values()],
                    "stats": self.get_stats(),
                }
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False
    
    def load_from_file(self, filepath: str) -> bool:
        """Load cache from file."""
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            with self._lock:
                self._cache.clear()
                for entry_data in data.get("entries", []):
                    entry = CacheEntry.from_dict(entry_data)
                    key = self._compute_hash(entry.query, entry.model)
                    self._cache[key] = entry
            return True
        except Exception as e:
            logger.error(f"Failed to load cache: {e}")
            return False


__all__ = ["SemanticCache", "CacheEntry"]
