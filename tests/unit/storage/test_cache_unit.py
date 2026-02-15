from datetime import datetime, timedelta

import pytest

from src.storage.cache import DistributedCache, LRUCache, cache_key, cached


def test_lru_cache_eviction_by_max_size():
    c = LRUCache(max_size=2)
    c.set("a", 1)
    c.set("b", 2)
    assert c.get("a") == 1

    c.set("c", 3)

    # LRU should evict "b" ("a" was recently used)
    assert c.get("b") is None
    assert c.get("a") == 1
    assert c.get("c") == 3


def test_lru_cache_ttl_expiration(monkeypatch):
    class _FakeDT(datetime):
        now_value = datetime(2026, 1, 1, 0, 0, 0)

        @classmethod
        def utcnow(cls):
            return cls.now_value

    monkeypatch.setattr("src.storage.cache.datetime", _FakeDT)

    c = LRUCache(max_size=10)
    c.set("k", "v", ttl=10)
    assert c.get("k") == "v"

    _FakeDT.now_value = _FakeDT.now_value + timedelta(seconds=11)
    assert c.get("k") is None


def test_lru_cache_invalidate_by_tag():
    c = LRUCache(max_size=10)
    c.set("a", 1, tags=["t1"])
    c.set("b", 2, tags=["t1", "t2"])
    c.set("c", 3, tags=["t2"])

    assert c.invalidate_by_tag("t1") == 2
    assert c.get("a") is None
    assert c.get("b") is None
    assert c.get("c") == 3


def test_distributed_cache_backend_get_set_delete_metrics():
    backend = type("B", (), {})()
    backend.get = lambda key: "remote" if key == "rk" else None
    backend.set = lambda *args, **kwargs: None
    backend.delete = lambda *args, **kwargs: None

    dc = DistributedCache(enable_distributed=True)
    dc.distributed_backend = backend

    # miss -> default
    assert dc.get("missing", default="d") == "d"

    # remote hit populates local
    assert dc.get("rk") == "remote"
    assert dc.get("rk") == "remote"  # local hit

    dc.set("x", 1, ttl=1, tags=["t"])
    assert dc.delete("x") is True

    m = dc.get_metrics()
    assert m["hits"] >= 1
    assert m["misses"] >= 1
    assert m["sets"] >= 1
    assert m["deletes"] >= 1


def test_cache_key_is_deterministic_for_same_inputs():
    k1 = cache_key(1, "a", x=2, y=3)
    k2 = cache_key(1, "a", y=3, x=2)
    assert k1 == k2


def test_cached_decorator_uses_cache():
    dc = DistributedCache(enable_distributed=False)

    calls = {"n": 0}

    @cached(dc, ttl=10, tags=["t"])
    def f(x):
        calls["n"] += 1
        return x + 1

    assert f(1) == 2
    assert f(1) == 2
    assert calls["n"] == 1
