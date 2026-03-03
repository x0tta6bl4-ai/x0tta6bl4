"""Unit tests for src/edge/edge_cache.py."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from src.edge.edge_cache import (
    AdaptiveStrategy,
    CacheConfig,
    CacheEntry,
    CachePolicy,
    CacheState,
    CacheStatistics,
    DistributedEdgeCache,
    EdgeCache,
    FIFOStrategy,
    LFUStrategy,
    LRUStrategy,
    TTLStrategy,
)


# ── CachePolicy / CacheState Enums ─────────────────────────────────

class TestCacheEnums:
    def test_cache_policy_values(self):
        assert CachePolicy.LRU.value == "lru"
        assert CachePolicy.LFU.value == "lfu"
        assert CachePolicy.FIFO.value == "fifo"
        assert CachePolicy.TTL.value == "ttl"
        assert CachePolicy.ADAPTIVE.value == "adaptive"

    def test_cache_state_values(self):
        assert CacheState.ACTIVE.value == "active"
        assert CacheState.EXPIRED.value == "expired"
        assert CacheState.EVICTING.value == "evicting"
        assert CacheState.PENDING.value == "pending"


# ── CacheEntry ──────────────────────────────────────────────────────

class TestCacheEntry:
    def test_defaults(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.access_count == 0
        assert entry.ttl_seconds is None
        assert entry.size_bytes == 0
        assert entry.tags == set()
        assert entry.metadata == {}

    def test_is_expired_no_ttl(self):
        entry = CacheEntry(key="k", value="v", ttl_seconds=None)
        assert entry.is_expired is False

    def test_is_expired_not_yet(self):
        entry = CacheEntry(key="k", value="v", ttl_seconds=3600)
        assert entry.is_expired is False

    def test_is_expired_past_ttl(self):
        entry = CacheEntry(
            key="k",
            value="v",
            ttl_seconds=1,
            created_at=datetime.utcnow() - timedelta(seconds=10),
        )
        assert entry.is_expired is True

    def test_age_seconds_positive(self):
        entry = CacheEntry(
            key="k",
            value="v",
            created_at=datetime.utcnow() - timedelta(seconds=5),
        )
        assert entry.age_seconds >= 5.0

    def test_idle_seconds_positive(self):
        entry = CacheEntry(
            key="k",
            value="v",
            last_accessed=datetime.utcnow() - timedelta(seconds=3),
        )
        assert entry.idle_seconds >= 3.0

    def test_touch_increments_count(self):
        entry = CacheEntry(key="k", value="v")
        entry.touch()
        assert entry.access_count == 1
        entry.touch()
        assert entry.access_count == 2

    def test_touch_updates_last_accessed(self):
        entry = CacheEntry(
            key="k",
            value="v",
            last_accessed=datetime.utcnow() - timedelta(seconds=60),
        )
        old_time = entry.last_accessed
        entry.touch()
        assert entry.last_accessed > old_time


# ── CacheStatistics ─────────────────────────────────────────────────

class TestCacheStatistics:
    def test_defaults(self):
        s = CacheStatistics()
        assert s.hits == 0
        assert s.misses == 0
        assert s.hit_rate == 0.0

    def test_hit_rate_calculation(self):
        s = CacheStatistics(hits=7, misses=3)
        assert s.hit_rate == pytest.approx(0.7)

    def test_hit_rate_zero_total(self):
        s = CacheStatistics(hits=0, misses=0)
        assert s.hit_rate == 0.0

    def test_avg_get_time_ns_with_hits(self):
        s = CacheStatistics(hits=5, total_get_time_ns=1000)
        assert s.avg_get_time_ns == 200.0

    def test_avg_get_time_ns_no_hits(self):
        s = CacheStatistics(hits=0, total_get_time_ns=0)
        assert s.avg_get_time_ns == 0

    def test_to_dict(self):
        s = CacheStatistics(hits=4, misses=1)
        d = s.to_dict()
        assert d["hits"] == 4
        assert d["misses"] == 1
        assert "hit_rate" in d
        assert "evictions" in d


# ── Eviction Strategies ─────────────────────────────────────────────

def _make_entries(n: int) -> dict:
    """Create n entries with different timestamps and access counts."""
    entries = {}
    base = datetime.utcnow() - timedelta(seconds=n * 10)
    for i in range(n):
        key = f"key{i}"
        entry = CacheEntry(
            key=key,
            value=i,
            created_at=base + timedelta(seconds=i * 10),
            last_accessed=base + timedelta(seconds=i * 5),
            access_count=i,
            ttl_seconds=3600,
        )
        entries[key] = entry
    return entries


class TestLRUStrategy:
    def test_selects_least_recently_used(self):
        entries = _make_entries(5)
        strategy = LRUStrategy()
        evict = strategy.select_for_eviction(entries, 2)
        # key0 has oldest last_accessed
        assert "key0" in evict
        assert len(evict) == 2

    def test_count_capped_at_size(self):
        entries = _make_entries(3)
        strategy = LRUStrategy()
        evict = strategy.select_for_eviction(entries, 10)
        assert len(evict) == 3


class TestLFUStrategy:
    def test_selects_least_frequently_used(self):
        entries = _make_entries(5)
        strategy = LFUStrategy()
        evict = strategy.select_for_eviction(entries, 2)
        # key0 has access_count=0, key1 has access_count=1
        assert "key0" in evict


class TestFIFOStrategy:
    def test_selects_oldest_created(self):
        entries = _make_entries(5)
        strategy = FIFOStrategy()
        evict = strategy.select_for_eviction(entries, 2)
        # key0 is oldest
        assert "key0" in evict


class TestTTLStrategy:
    def test_selects_expired_first(self):
        entries = _make_entries(3)
        # Make key0 expired
        entries["key0"].ttl_seconds = 0.001
        time.sleep(0.01)
        strategy = TTLStrategy()
        evict = strategy.select_for_eviction(entries, 1)
        assert "key0" in evict

    def test_fallback_to_age_when_no_expired(self):
        entries = _make_entries(5)
        strategy = TTLStrategy()
        evict = strategy.select_for_eviction(entries, 2)
        assert len(evict) == 2


class TestAdaptiveStrategy:
    def test_returns_correct_count(self):
        entries = _make_entries(5)
        strategy = AdaptiveStrategy()
        evict = strategy.select_for_eviction(entries, 3)
        assert len(evict) == 3

    def test_evicts_large_idle_entries_first(self):
        entries = {}
        # Large, idle entry
        big_idle = CacheEntry(
            key="big_idle",
            value="x",
            size_bytes=1024 * 1024,
            access_count=0,
            last_accessed=datetime.utcnow() - timedelta(hours=2),
            created_at=datetime.utcnow() - timedelta(hours=5),
            ttl_seconds=7200,
        )
        # Small, recently used entry
        small_fresh = CacheEntry(
            key="small_fresh",
            value="y",
            size_bytes=10,
            access_count=100,
            last_accessed=datetime.utcnow(),
            created_at=datetime.utcnow(),
            ttl_seconds=7200,
        )
        entries["big_idle"] = big_idle
        entries["small_fresh"] = small_fresh

        strategy = AdaptiveStrategy()
        evict = strategy.select_for_eviction(entries, 1)
        assert evict == ["big_idle"]


# ── EdgeCache ───────────────────────────────────────────────────────

class TestEdgeCacheBasic:
    def setup_method(self):
        self.cache = EdgeCache()

    def test_set_and_get(self):
        self.cache.set("k", "value")
        assert self.cache.get("k") == "value"

    def test_get_missing_returns_none(self):
        assert self.cache.get("no_such_key") is None

    def test_delete_existing(self):
        self.cache.set("k", "v")
        assert self.cache.delete("k") is True
        assert self.cache.get("k") is None

    def test_delete_missing_returns_false(self):
        assert self.cache.delete("phantom") is False

    def test_exists_true(self):
        self.cache.set("k", "v")
        assert self.cache.exists("k") is True

    def test_exists_false(self):
        assert self.cache.exists("phantom") is False

    def test_exists_expired_returns_false(self):
        self.cache.set("k", "v", ttl_seconds=0.001)
        time.sleep(0.01)
        assert self.cache.exists("k") is False

    def test_get_expired_returns_none(self):
        self.cache.set("k", "v", ttl_seconds=0.001)
        time.sleep(0.01)
        result = self.cache.get("k")
        assert result is None

    def test_get_increments_hit(self):
        self.cache.set("k", "v")
        self.cache.get("k")
        assert self.cache._stats.hits == 1

    def test_get_miss_increments_miss(self):
        self.cache.get("phantom")
        assert self.cache._stats.misses == 1

    def test_set_updates_entry_count(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        stats = self.cache.get_stats()
        assert stats.entry_count == 2

    def test_set_with_tags(self):
        self.cache.set("k", "v", tags={"user", "profile"})
        assert "user" in self.cache._tag_index
        assert "k" in self.cache._tag_index["user"]

    def test_set_with_metadata(self):
        self.cache.set("k", "v", metadata={"source": "test"})
        info = self.cache.get_entry_info("k")
        assert info is not None

    def test_clear(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        self.cache.clear()
        assert self.cache.get("a") is None
        assert len(self.cache._entries) == 0

    def test_set_overwrites_existing(self):
        self.cache.set("k", "old")
        self.cache.set("k", "new")
        assert self.cache.get("k") == "new"


class TestEdgeCacheInvalidation:
    def setup_method(self):
        self.cache = EdgeCache()

    def test_invalidate_by_tag(self):
        self.cache.set("k1", "v1", tags={"api"})
        self.cache.set("k2", "v2", tags={"api"})
        self.cache.set("k3", "v3", tags={"db"})
        count = self.cache.invalidate_by_tag("api")
        assert count == 2
        assert self.cache.get("k1") is None
        assert self.cache.get("k3") == "v3"

    def test_invalidate_by_tag_missing_tag(self):
        count = self.cache.invalidate_by_tag("nonexistent_tag")
        assert count == 0

    def test_invalidate_by_prefix(self):
        self.cache.set("user:1", "alice")
        self.cache.set("user:2", "bob")
        self.cache.set("post:1", "hello")
        count = self.cache.invalidate_by_prefix("user:")
        assert count == 2
        assert self.cache.get("post:1") == "hello"

    def test_invalidate_wildcard_pattern(self):
        self.cache.set("item:a", 1)
        self.cache.set("item:b", 2)
        self.cache.set("other", 3)
        count = self.cache.invalidate(pattern="item:*")
        assert count == 2
        assert self.cache.get("other") == 3

    def test_invalidate_exact_pattern(self):
        self.cache.set("exact", "v")
        count = self.cache.invalidate(pattern="exact")
        assert count == 1

    def test_invalidate_by_tags_list(self):
        self.cache.set("k", "v", tags={"t1"})
        count = self.cache.invalidate(tags=["t1"])
        assert count == 1

    def test_invalidate_no_args_clears_all(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        count = self.cache.invalidate()
        assert count == 2
        assert len(self.cache._entries) == 0


class TestEdgeCacheGetOrSet:
    def setup_method(self):
        self.cache = EdgeCache()

    def test_get_or_set_missing_key(self):
        result = self.cache.get_or_set("k", lambda: "computed")
        assert result == "computed"
        assert self.cache.get("k") == "computed"

    def test_get_or_set_existing_key(self):
        self.cache.set("k", "cached")
        factory_calls = []

        def factory():
            factory_calls.append(1)
            return "new_value"

        result = self.cache.get_or_set("k", factory)
        assert result == "cached"
        assert not factory_calls

    @pytest.mark.asyncio
    async def test_get_or_set_async_sync_factory(self):
        result = await self.cache.get_or_set_async("k", lambda: "from_factory")
        assert result == "from_factory"

    @pytest.mark.asyncio
    async def test_get_or_set_async_async_factory(self):
        async def async_factory():
            return "async_result"

        result = await self.cache.get_or_set_async("k", async_factory)
        assert result == "async_result"

    @pytest.mark.asyncio
    async def test_get_or_set_async_returns_cached(self):
        self.cache.set("k", "cached")
        result = await self.cache.get_or_set_async("k", lambda: "new")
        assert result == "cached"


class TestEdgeCacheEviction:
    def test_evicts_when_max_entries_reached(self):
        cfg = CacheConfig(max_entries=3, eviction_threshold_percent=100.0)
        cache = EdgeCache(cfg)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # triggers eviction
        assert len(cache._entries) <= 3

    def test_eviction_callbacks_called(self):
        cfg = CacheConfig(max_entries=2, eviction_threshold_percent=100.0)
        cache = EdgeCache(cfg)
        evicted_keys = []
        cache.add_eviction_callback(lambda k, v: evicted_keys.append(k))
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # triggers eviction
        assert len(evicted_keys) > 0

    def test_lru_eviction_policy(self):
        cfg = CacheConfig(
            max_entries=3,
            eviction_threshold_percent=100.0,
            policy=CachePolicy.LRU,
            eviction_batch_size=1,  # evict only 1 per cycle
        )
        cache = EdgeCache(cfg)
        cache.set("a", 1)
        time.sleep(0.01)
        cache.set("b", 2)
        time.sleep(0.01)
        cache.set("c", 3)  # 3 entries, at max
        cache.get("a")     # touch a → now most recently used
        cache.get("b")     # touch b
        # "c" was set last but never touched after; oldest last_accessed is "c"
        # Wait: "c" was set most recently so its created/last_accessed is newest.
        # Actually "a" was set first and then touched, "b" touched after "a".
        # "c" was set last (newest last_accessed from set) but never get()'d.
        # After get("a") and get("b"), last_accessed order: c < a < b (c oldest)
        cache.set("d", 4)  # triggers eviction — should evict c (LRU)
        assert cache.get("a") == 1  # a was recently touched — should survive

    def test_lfu_eviction_policy(self):
        cfg = CacheConfig(
            max_entries=3,
            eviction_threshold_percent=100.0,
            policy=CachePolicy.LFU,
        )
        cache = EdgeCache(cfg)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        # Access b and c multiple times
        for _ in range(5):
            cache.get("b")
            cache.get("c")
        cache.set("d", 4)  # should evict a (access_count=0)
        assert cache.get("a") is None

    def test_fifo_eviction_policy(self):
        cfg = CacheConfig(
            max_entries=3,
            eviction_threshold_percent=100.0,
            policy=CachePolicy.FIFO,
        )
        cache = EdgeCache(cfg)
        cache.set("first", 1)
        cache.set("second", 2)
        cache.set("third", 3)
        cache.set("fourth", 4)  # should evict first
        assert cache.get("first") is None


class TestEdgeCacheStats:
    def test_get_stats_returns_statistics(self):
        cache = EdgeCache()
        cache.set("k", "v")
        stats = cache.get_stats()
        assert isinstance(stats, CacheStatistics)
        assert stats.entry_count == 1

    def test_get_stats_summary_structure(self):
        cache = EdgeCache()
        summary = cache.get_stats_summary()
        assert "hits" in summary
        assert "misses" in summary
        assert "config" in summary
        assert summary["config"]["policy"] == CachePolicy.ADAPTIVE.value

    def test_get_entry_info(self):
        cache = EdgeCache()
        cache.set("k", "v", tags={"t1"}, metadata={"m": 1})
        info = cache.get_entry_info("k")
        assert info is not None
        assert info["key"] == "k"
        assert "created_at" in info
        assert "t1" in info["tags"]

    def test_get_entry_info_missing(self):
        cache = EdgeCache()
        assert cache.get_entry_info("phantom") is None

    def test_get_keys_no_filter(self):
        cache = EdgeCache()
        cache.set("a", 1)
        cache.set("b", 2)
        keys = cache.get_keys()
        assert set(keys) == {"a", "b"}

    def test_get_keys_with_pattern(self):
        cache = EdgeCache()
        cache.set("user:1", "alice")
        cache.set("user:2", "bob")
        cache.set("post:1", "hello")
        keys = cache.get_keys("user:*")
        assert set(keys) == {"user:1", "user:2"}

    def test_get_size_info(self):
        cache = EdgeCache()
        cache.set("k", b"hello world")
        info = cache.get_size_info()
        assert "total_size_bytes" in info
        assert "usage_percent" in info
        assert info["entry_count"] == 1


class TestEdgeCacheCleanup:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        cfg = CacheConfig(enable_background_cleanup=True, cleanup_interval_seconds=0.05)
        cache = EdgeCache(cfg)
        await cache.start()
        assert cache._running is True
        await cache.stop()
        assert cache._running is False

    def test_cleanup_expired_removes_entries(self):
        cache = EdgeCache()
        cache.set("k", "v", ttl_seconds=0.001)
        time.sleep(0.01)
        removed = cache._cleanup_expired()
        assert removed == 1
        assert "k" not in cache._entries

    def test_expiration_callbacks_called(self):
        cache = EdgeCache()
        expired_keys = []
        cache.add_expiration_callback(lambda k, v: expired_keys.append(k))
        cache.set("exp", "value", ttl_seconds=0.001)
        time.sleep(0.01)
        cache._cleanup_expired()
        assert "exp" in expired_keys

    def test_cleanup_skips_non_expired(self):
        cache = EdgeCache()
        cache.set("k", "v", ttl_seconds=3600)
        removed = cache._cleanup_expired()
        assert removed == 0
        assert cache.get("k") == "v"


class TestEdgeCacheCallbacks:
    def test_add_eviction_callback(self):
        cache = EdgeCache()
        cb = MagicMock()
        cache.add_eviction_callback(cb)
        assert cb in cache._eviction_callbacks

    def test_add_expiration_callback(self):
        cache = EdgeCache()
        cb = MagicMock()
        cache.add_expiration_callback(cb)
        assert cb in cache._expiration_callbacks

    def test_eviction_callback_error_does_not_raise(self):
        cfg = CacheConfig(max_entries=1, eviction_threshold_percent=100.0)
        cache = EdgeCache(cfg)

        def bad_cb(k, v):
            raise RuntimeError("callback error")

        cache.add_eviction_callback(bad_cb)
        cache.set("a", 1)
        cache.set("b", 2)  # triggers eviction, callback errors should be swallowed


# ── DistributedEdgeCache ────────────────────────────────────────────

class TestDistributedEdgeCache:
    def test_init(self):
        cache = DistributedEdgeCache(node_id="node1")
        assert cache.node_id == "node1"
        assert cache._peers == {}

    def test_add_remove_peer(self):
        cache = DistributedEdgeCache()
        peer = DistributedEdgeCache(node_id="peer1")
        cache.add_peer("peer1", peer)
        assert "peer1" in cache._peers
        cache.remove_peer("peer1")
        assert "peer1" not in cache._peers

    def test_set_replicates_to_peers(self):
        cfg = CacheConfig(enable_replication=True, replication_factor=2)
        cache = DistributedEdgeCache(config=cfg, node_id="main")
        peer1 = DistributedEdgeCache(config=CacheConfig(enable_replication=False))
        peer2 = DistributedEdgeCache(config=CacheConfig(enable_replication=False))
        cache.add_peer("p1", peer1)
        cache.add_peer("p2", peer2)
        cache.set("k", "v")
        # Peers should have the value
        assert peer1.get("k") == "v" or peer2.get("k") == "v"

    def test_set_no_replication_when_disabled(self):
        cfg = CacheConfig(enable_replication=False)
        cache = DistributedEdgeCache(config=cfg, node_id="main")
        peer = DistributedEdgeCache()
        cache.add_peer("p1", peer)
        cache.set("k", "v")
        # Peer should NOT have the value
        assert peer.get("k") is None

    def test_delete_propagates_to_peers(self):
        cache = DistributedEdgeCache(node_id="main")
        peer = DistributedEdgeCache()
        peer.set("k", "v")  # set directly on peer
        cache.add_peer("p1", peer)
        cache.set("k", "v")
        cache.delete("k")  # should propagate
        assert peer.get("k") is None

    def test_delete_no_propagate(self):
        cache = DistributedEdgeCache()
        peer = DistributedEdgeCache()
        peer.set("k", "v")
        cache.add_peer("p1", peer)
        cache.set("k", "v")
        cache.delete("k", propagate=False)
        # Peer retains its own value
        assert peer.get("k") == "v"

    def test_invalidate_by_tag_propagates(self):
        cache = DistributedEdgeCache()
        peer = DistributedEdgeCache()
        peer.set("k", "v", tags={"mytag"})
        cache.add_peer("p1", peer)
        cache.set("k", "v", tags={"mytag"})
        cache.invalidate_by_tag("mytag")
        assert peer.get("k") is None

    def test_invalidate_by_tag_propagate_false_returns_count(self):
        # propagate=False suppresses _propagate_tag_invalidation, but
        # EdgeCache.invalidate_by_tag calls self.delete() (propagate=True) internally,
        # so individual key deletions still reach peers via _propagate_invalidation.
        cache = DistributedEdgeCache()
        peer = DistributedEdgeCache()
        cache.add_peer("p1", peer)
        cache.set("k", "v", tags={"mytag"})  # only on cache (replication disabled)
        count = cache.invalidate_by_tag("mytag", propagate=False)
        assert count == 1  # 1 entry invalidated on cache itself

    def test_replication_peer_failure_does_not_raise(self):
        cfg = CacheConfig(enable_replication=True)
        cache = DistributedEdgeCache(config=cfg, node_id="main")
        bad_peer = MagicMock()
        bad_peer.set.side_effect = RuntimeError("peer down")
        cache.add_peer("bad", bad_peer)
        # Should not raise
        cache.set("k", "v")

    def test_inherits_edge_cache_functionality(self):
        cache = DistributedEdgeCache()
        cache.set("a", 1)
        assert cache.get("a") == 1
        assert cache.exists("a") is True
        cache.delete("a")
        assert cache.get("a") is None
