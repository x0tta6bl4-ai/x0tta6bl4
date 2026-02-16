"""Unit tests for SemanticCache and CachedResult."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

import numpy as np
import pytest

from src.rag.semantic_cache import CachedResult, SemanticCache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cached_result(
    query="test query",
    embedding=None,
    results=None,
    scores=None,
    timestamp=None,
    hit_count=0,
    ttl_seconds=3600,
):
    """Create a CachedResult with sensible defaults."""
    return CachedResult(
        query=query,
        query_embedding=(
            embedding if embedding is not None else np.zeros(384, dtype=np.float32)
        ),
        results=results if results is not None else [{"id": "1", "text": "hello"}],
        scores=scores if scores is not None else [0.9],
        timestamp=timestamp if timestamp is not None else datetime.now(),
        hit_count=hit_count,
        ttl_seconds=ttl_seconds,
    )


# ---------------------------------------------------------------------------
# CachedResult tests
# ---------------------------------------------------------------------------


class TestCachedResult:
    """Tests for the CachedResult dataclass."""

    def test_is_expired_false_when_fresh(self):
        """A freshly created CachedResult should not be expired."""
        cr = _make_cached_result(ttl_seconds=3600)
        assert cr.is_expired is False

    def test_is_expired_true_after_ttl(self):
        """A CachedResult older than its TTL should be expired."""
        past = datetime.now() - timedelta(seconds=7200)
        cr = _make_cached_result(timestamp=past, ttl_seconds=3600)
        assert cr.is_expired is True

    def test_is_expired_boundary(self):
        """A CachedResult exactly at TTL boundary should not be expired (<=)."""
        # Just under TTL -- still valid
        past = datetime.now() - timedelta(seconds=3599)
        cr = _make_cached_result(timestamp=past, ttl_seconds=3600)
        assert cr.is_expired is False

    def test_to_dict_serializes_correctly(self):
        """to_dict should convert ndarray to list and timestamp to ISO string."""
        embedding = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        ts = datetime(2025, 1, 15, 12, 0, 0)
        results = [{"id": "doc1", "text": "content"}]
        scores = [0.95]

        cr = _make_cached_result(
            query="hello world",
            embedding=embedding,
            results=results,
            scores=scores,
            timestamp=ts,
            hit_count=5,
            ttl_seconds=1800,
        )
        d = cr.to_dict()

        assert d["query"] == "hello world"
        assert d["query_embedding"] == [1.0, 2.0, 3.0]
        assert isinstance(d["query_embedding"], list)
        assert d["results"] == results
        assert d["scores"] == scores
        assert d["timestamp"] == ts.isoformat()
        assert d["hit_count"] == 5
        assert d["ttl_seconds"] == 1800

    def test_to_dict_handles_plain_list_embedding(self):
        """to_dict should handle non-ndarray embedding gracefully."""
        cr = _make_cached_result(embedding=[1.0, 2.0])
        # When embedding is already a list, to_dict should pass it through
        d = cr.to_dict()
        assert d["query_embedding"] == [1.0, 2.0]


# ---------------------------------------------------------------------------
# SemanticCache tests
# ---------------------------------------------------------------------------


class TestSemanticCacheInit:
    """Tests for SemanticCache initialisation."""

    def test_default_parameters(self):
        cache = SemanticCache(enable_embedding_model=False)
        assert cache.max_cache_size == 1000
        assert cache.similarity_threshold == 0.95
        assert cache.ttl_seconds == 3600
        assert cache.embedding_model is None
        assert len(cache.cache) == 0

    def test_custom_parameters(self):
        cache = SemanticCache(
            max_cache_size=50,
            similarity_threshold=0.8,
            ttl_seconds=600,
            enable_embedding_model=False,
        )
        assert cache.max_cache_size == 50
        assert cache.similarity_threshold == 0.8
        assert cache.ttl_seconds == 600

    def test_stats_initialised_to_zero(self):
        cache = SemanticCache(enable_embedding_model=False)
        assert cache.stats == {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
        }


class TestSemanticCachePutGet:
    """Tests for put / get (exact hash match path)."""

    def test_put_then_get_exact_match(self):
        """put followed by get with the same query returns cached results."""
        cache = SemanticCache(enable_embedding_model=False)
        results = [{"id": "1"}]
        scores = [0.99]

        cache.put("my query", results, scores)
        cached = cache.get("my query")

        assert cached is not None
        assert cached[0] == results
        assert cached[1] == scores

    def test_get_miss_returns_none(self):
        """get on a missing query returns None and increments misses."""
        cache = SemanticCache(enable_embedding_model=False)
        assert cache.get("nonexistent") is None
        assert cache.stats["misses"] == 1

    def test_get_increments_hit_count(self):
        """Successive gets increment both stats hits and entry hit_count."""
        cache = SemanticCache(enable_embedding_model=False)
        cache.put("q", [{"id": "1"}], [0.5])

        cache.get("q")
        cache.get("q")

        assert cache.stats["hits"] == 2
        query_hash = cache._compute_query_hash("q")
        assert cache.cache[query_hash].hit_count == 2

    def test_get_expired_returns_none(self):
        """get should return None and track expiration for expired entries."""
        cache = SemanticCache(enable_embedding_model=False, ttl_seconds=3600)
        cache.put("q", [{"id": "1"}], [0.5])

        # Simulate expiration by shifting the timestamp into the past
        query_hash = cache._compute_query_hash("q")
        cache.cache[query_hash].timestamp = datetime.now() - timedelta(seconds=7200)

        result = cache.get("q")
        assert result is None
        assert cache.stats["expirations"] == 1
        assert cache.stats["misses"] == 1
        # Entry should have been removed
        assert query_hash not in cache.cache

    def test_put_overwrites_existing_entry(self):
        """Putting the same query again should overwrite the old entry."""
        cache = SemanticCache(enable_embedding_model=False)
        cache.put("q", [{"id": "old"}], [0.1])
        cache.put("q", [{"id": "new"}], [0.9])

        cached = cache.get("q")
        assert cached is not None
        assert cached[0] == [{"id": "new"}]
        assert cached[1] == [0.9]
        assert len(cache.cache) == 1


class TestSemanticCacheLRUEviction:
    """Tests for LRU eviction when cache exceeds max_cache_size."""

    def test_evicts_oldest_when_over_capacity(self):
        """When cache is full, the oldest (first inserted) entry is evicted."""
        cache = SemanticCache(max_cache_size=3, enable_embedding_model=False)

        cache.put("q1", [{"id": "1"}], [0.1])
        cache.put("q2", [{"id": "2"}], [0.2])
        cache.put("q3", [{"id": "3"}], [0.3])

        # This should evict q1
        cache.put("q4", [{"id": "4"}], [0.4])

        assert cache.get("q1") is None
        assert cache.get("q2") is not None
        assert cache.get("q4") is not None
        assert cache.stats["evictions"] == 1

    def test_multiple_evictions(self):
        """Inserting well beyond capacity evicts multiple oldest entries."""
        cache = SemanticCache(max_cache_size=2, enable_embedding_model=False)

        cache.put("q1", [{"id": "1"}], [0.1])
        cache.put("q2", [{"id": "2"}], [0.2])
        cache.put("q3", [{"id": "3"}], [0.3])
        cache.put("q4", [{"id": "4"}], [0.4])

        assert len(cache.cache) == 2
        assert cache.stats["evictions"] == 2
        # Only q3 and q4 should remain
        assert cache.get("q1") is None
        assert cache.get("q2") is None


class TestSemanticCacheClear:
    """Tests for clear and clear_expired."""

    def test_clear_empties_cache(self):
        """clear() should remove all entries."""
        cache = SemanticCache(enable_embedding_model=False)
        cache.put("q1", [{"id": "1"}], [0.1])
        cache.put("q2", [{"id": "2"}], [0.2])

        cache.clear()

        assert len(cache.cache) == 0

    def test_clear_expired_removes_only_expired(self):
        """clear_expired removes expired entries and returns the count."""
        cache = SemanticCache(enable_embedding_model=False, ttl_seconds=3600)
        cache.put("fresh", [{"id": "1"}], [0.1])
        cache.put("old1", [{"id": "2"}], [0.2])
        cache.put("old2", [{"id": "3"}], [0.3])

        # Age two entries past TTL
        h1 = cache._compute_query_hash("old1")
        h2 = cache._compute_query_hash("old2")
        cache.cache[h1].timestamp = datetime.now() - timedelta(seconds=7200)
        cache.cache[h2].timestamp = datetime.now() - timedelta(seconds=7200)

        removed = cache.clear_expired()

        assert removed == 2
        assert cache.stats["expirations"] == 2
        assert len(cache.cache) == 1
        assert cache.get("fresh") is not None

    def test_clear_expired_returns_zero_when_none_expired(self):
        """clear_expired returns 0 when no entries are expired."""
        cache = SemanticCache(enable_embedding_model=False)
        cache.put("q1", [{"id": "1"}], [0.1])

        removed = cache.clear_expired()
        assert removed == 0


class TestSemanticCacheStats:
    """Tests for get_stats."""

    def test_get_stats_initial(self):
        """Stats should reflect zeroes on a fresh cache."""
        cache = SemanticCache(enable_embedding_model=False)
        stats = cache.get_stats()

        assert stats["cache_size"] == 0
        assert stats["max_cache_size"] == 1000
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0
        assert stats["evictions"] == 0
        assert stats["expirations"] == 0
        assert stats["total_requests"] == 0

    def test_get_stats_after_operations(self):
        """Stats should reflect hits, misses, and evictions correctly."""
        cache = SemanticCache(max_cache_size=2, enable_embedding_model=False)

        cache.put("q1", [{"id": "1"}], [0.1])
        cache.put("q2", [{"id": "2"}], [0.2])

        cache.get("q1")  # hit
        cache.get("q2")  # hit
        cache.get("q_miss")  # miss

        cache.put("q3", [{"id": "3"}], [0.3])  # evicts q1

        stats = cache.get_stats()
        assert stats["cache_size"] == 2
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_requests"] == 3
        assert stats["evictions"] == 1
        # hit_rate = 2/3 * 100 ~ 66.67
        assert abs(stats["hit_rate"] - (2 / 3 * 100)) < 0.01


class TestSemanticCacheSetters:
    """Tests for set_ttl and set_similarity_threshold."""

    def test_set_ttl_updates_value(self):
        cache = SemanticCache(enable_embedding_model=False)
        cache.set_ttl(1800)
        assert cache.ttl_seconds == 1800

    def test_set_similarity_threshold_valid(self):
        cache = SemanticCache(enable_embedding_model=False)
        cache.set_similarity_threshold(0.8)
        assert cache.similarity_threshold == 0.8

    def test_set_similarity_threshold_boundary_zero(self):
        cache = SemanticCache(enable_embedding_model=False)
        cache.set_similarity_threshold(0.0)
        assert cache.similarity_threshold == 0.0

    def test_set_similarity_threshold_boundary_one(self):
        cache = SemanticCache(enable_embedding_model=False)
        cache.set_similarity_threshold(1.0)
        assert cache.similarity_threshold == 1.0

    def test_set_similarity_threshold_too_high_raises(self):
        cache = SemanticCache(enable_embedding_model=False)
        with pytest.raises(ValueError, match="Threshold must be between 0 and 1"):
            cache.set_similarity_threshold(1.5)

    def test_set_similarity_threshold_negative_raises(self):
        cache = SemanticCache(enable_embedding_model=False)
        with pytest.raises(ValueError, match="Threshold must be between 0 and 1"):
            cache.set_similarity_threshold(-0.1)


class TestComputeSimilarity:
    """Tests for _compute_similarity (cosine similarity)."""

    def test_identical_vectors_return_one(self):
        cache = SemanticCache(enable_embedding_model=False)
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        assert cache._compute_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_return_zero(self):
        cache = SemanticCache(enable_embedding_model=False)
        v1 = np.array([1.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0], dtype=np.float32)
        assert cache._compute_similarity(v1, v2) == pytest.approx(0.0)

    def test_opposite_vectors_return_negative_one(self):
        cache = SemanticCache(enable_embedding_model=False)
        v1 = np.array([1.0, 0.0], dtype=np.float32)
        v2 = np.array([-1.0, 0.0], dtype=np.float32)
        assert cache._compute_similarity(v1, v2) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        cache = SemanticCache(enable_embedding_model=False)
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        zero = np.zeros(3, dtype=np.float32)
        assert cache._compute_similarity(v, zero) == 0.0
        assert cache._compute_similarity(zero, v) == 0.0
        assert cache._compute_similarity(zero, zero) == 0.0

    def test_empty_arrays_return_zero(self):
        cache = SemanticCache(enable_embedding_model=False)
        empty = np.array([], dtype=np.float32)
        v = np.array([1.0], dtype=np.float32)
        assert cache._compute_similarity(empty, v) == 0.0
        assert cache._compute_similarity(v, empty) == 0.0


class TestComputeQueryHash:
    """Tests for _compute_query_hash."""

    def test_deterministic(self):
        """Same query always produces the same hash."""
        cache = SemanticCache(enable_embedding_model=False)
        h1 = cache._compute_query_hash("test query")
        h2 = cache._compute_query_hash("test query")
        assert h1 == h2

    def test_matches_sha256(self):
        """Hash matches a direct SHA256 computation."""
        cache = SemanticCache(enable_embedding_model=False)
        query = "hello world"
        expected = hashlib.sha256(query.encode()).hexdigest()
        assert cache._compute_query_hash(query) == expected

    def test_different_queries_different_hashes(self):
        cache = SemanticCache(enable_embedding_model=False)
        h1 = cache._compute_query_hash("query a")
        h2 = cache._compute_query_hash("query b")
        assert h1 != h2


class TestGetQueryEmbedding:
    """Tests for _get_query_embedding without a model."""

    def test_returns_zero_vector_without_model(self):
        """Without an embedding model, returns a zero vector."""
        cache = SemanticCache(enable_embedding_model=False)
        emb = cache._get_query_embedding("anything")
        assert isinstance(emb, np.ndarray)
        assert emb.dtype == np.float32
        assert len(emb) == 384
        assert np.all(emb == 0.0)
