"""
Unit tests for CRDT implementations
"""
import pytest
import time
from src.data_sync.crdt import (
    GCounter, PNCounter, LWWRegister, GSet, ORSet, LWWMap,
)


# === GCounter ===

class TestGCounter:
    def test_increment(self):
        c = GCounter()
        c.increment("n1")
        assert c.value() == 1
        c.increment("n1", 2)
        assert c.value() == 3

    def test_increment_multiple_nodes(self):
        c = GCounter()
        c.increment("n1", 3)
        c.increment("n2", 5)
        c.increment("n3", 2)
        assert c.value() == 10

    def test_merge(self):
        c1 = GCounter()
        c2 = GCounter()
        c1.increment("n1", 2)
        c2.increment("n1", 1)
        c2.increment("n2", 5)
        c1.merge(c2)
        assert c1.value() == 7

    def test_merge_idempotent(self):
        c1 = GCounter()
        c2 = GCounter()
        c1.increment("n1", 3)
        c2.increment("n2", 5)
        c1.merge(c2)
        c1.merge(c2)
        assert c1.value() == 8

    def test_merge_commutative(self):
        c1 = GCounter()
        c2 = GCounter()
        c1.increment("n1", 3)
        c2.increment("n2", 5)
        a, b = GCounter(), GCounter()
        a.increment("n1", 3)
        b.increment("n2", 5)
        c1.merge(c2)
        b.merge(a)
        assert c1.value() == b.value()

    def test_negative_increment_rejected(self):
        c = GCounter()
        with pytest.raises(ValueError):
            c.increment("n1", -1)

    def test_serialization(self):
        c = GCounter()
        c.increment("n1", 3)
        c.increment("n2", 7)
        data = c.to_dict()
        c2 = GCounter.from_dict(data)
        assert c2.value() == 10


# === PNCounter ===

class TestPNCounter:
    def test_increment_and_decrement(self):
        c = PNCounter()
        c.increment("n1", 10)
        c.decrement("n1", 3)
        assert c.value() == 7

    def test_negative_value(self):
        c = PNCounter()
        c.increment("n1", 2)
        c.decrement("n1", 5)
        assert c.value() == -3

    def test_merge(self):
        c1 = PNCounter()
        c2 = PNCounter()
        c1.increment("n1", 10)
        c1.decrement("n1", 2)
        c2.increment("n2", 5)
        c2.decrement("n2", 1)
        c1.merge(c2)
        assert c1.value() == 12  # (10 + 5) - (2 + 1)

    def test_merge_commutative(self):
        c1 = PNCounter()
        c2 = PNCounter()
        c1.increment("n1", 5)
        c2.decrement("n2", 3)
        a = PNCounter()
        b = PNCounter()
        a.increment("n1", 5)
        b.decrement("n2", 3)
        c1.merge(c2)
        b.merge(a)
        assert c1.value() == b.value()

    def test_invalid_increment(self):
        c = PNCounter()
        with pytest.raises(ValueError):
            c.increment("n1", -1)

    def test_invalid_decrement(self):
        c = PNCounter()
        with pytest.raises(ValueError):
            c.decrement("n1", -1)

    def test_serialization(self):
        c = PNCounter()
        c.increment("n1", 10)
        c.decrement("n2", 3)
        data = c.to_dict()
        c2 = PNCounter.from_dict(data)
        assert c2.value() == 7


# === LWWRegister ===

class TestLWWRegister:
    def test_set_and_get(self):
        r = LWWRegister()
        r.set("hello", timestamp=1.0)
        assert r.value == "hello"

    def test_later_timestamp_wins(self):
        r = LWWRegister()
        r.set("old", timestamp=1.0)
        r.set("new", timestamp=2.0)
        assert r.value == "new"

    def test_earlier_timestamp_ignored(self):
        r = LWWRegister()
        r.set("new", timestamp=2.0)
        r.set("old", timestamp=1.0)
        assert r.value == "new"

    def test_tie_break_deterministic(self):
        r = LWWRegister()
        r.set("aaa", timestamp=1.0)
        r.set("zzz", timestamp=1.0)
        assert r.value == "zzz"

    def test_merge(self):
        r1 = LWWRegister()
        r2 = LWWRegister()
        r1.set("old", timestamp=1.0)
        r2.set("new", timestamp=2.0)
        r1.merge(r2)
        assert r1.value == "new"

    def test_merge_commutative(self):
        r1 = LWWRegister()
        r2 = LWWRegister()
        r1.set("A", timestamp=1.0)
        r2.set("B", timestamp=2.0)
        a = LWWRegister()
        b = LWWRegister()
        a.set("A", timestamp=1.0)
        b.set("B", timestamp=2.0)
        r1.merge(r2)
        b.merge(a)
        assert r1.value == b.value

    def test_serialization(self):
        r = LWWRegister()
        r.set("data", timestamp=42.0)
        data = r.to_dict()
        r2 = LWWRegister.from_dict(data)
        assert r2.value == "data"
        assert r2.timestamp == 42.0


# === GSet ===

class TestGSet:
    def test_add_and_contains(self):
        s = GSet()
        s.add("a")
        assert s.contains("a")
        assert not s.contains("b")

    def test_merge(self):
        s1 = GSet()
        s2 = GSet()
        s1.add("a")
        s1.add("b")
        s2.add("b")
        s2.add("c")
        s1.merge(s2)
        assert s1.value() == frozenset({"a", "b", "c"})

    def test_merge_idempotent(self):
        s1 = GSet()
        s2 = GSet()
        s1.add("x")
        s2.add("y")
        s1.merge(s2)
        s1.merge(s2)
        assert len(s1) == 2

    def test_len(self):
        s = GSet()
        s.add("a")
        s.add("b")
        s.add("a")  # duplicate
        assert len(s) == 2

    def test_serialization(self):
        s = GSet()
        s.add("x")
        s.add("y")
        data = s.to_dict()
        s2 = GSet.from_dict(data)
        assert s2.contains("x")
        assert s2.contains("y")


# === ORSet ===

class TestORSet:
    def test_add_and_contains(self):
        s = ORSet()
        s.add("x", "n1")
        assert s.contains("x")

    def test_remove(self):
        s = ORSet()
        s.add("x", "n1")
        s.remove("x")
        assert not s.contains("x")

    def test_add_after_remove(self):
        s = ORSet()
        s.add("x", "n1")
        s.remove("x")
        s.add("x", "n1")
        assert s.contains("x")

    def test_concurrent_add_remove_add_wins(self):
        """Simulates concurrent add and remove on different replicas."""
        s1 = ORSet()
        s2 = ORSet()
        # Both start with "x"
        s1.add("x", "n1")
        s2.merge(s1)
        # s1 removes "x"
        s1.remove("x")
        # s2 concurrently adds "x" again
        s2.add("x", "n2")
        # Merge: add-wins semantics
        s1.merge(s2)
        assert s1.contains("x")

    def test_merge_commutative(self):
        s1 = ORSet()
        s2 = ORSet()
        s1.add("a", "n1")
        s2.add("b", "n2")
        a = ORSet()
        b = ORSet()
        a.add("a", "n1")
        b.add("b", "n2")
        s1.merge(s2)
        b.merge(a)
        assert s1.value() == b.value()

    def test_len(self):
        s = ORSet()
        s.add("a", "n1")
        s.add("b", "n1")
        s.add("c", "n1")
        s.remove("b")
        assert len(s) == 2

    def test_value(self):
        s = ORSet()
        s.add("x", "n1")
        s.add("y", "n1")
        s.add("z", "n1")
        s.remove("y")
        assert s.value() == frozenset({"x", "z"})

    def test_serialization(self):
        s = ORSet()
        s.add("a", "n1")
        s.add("b", "n2")
        data = s.to_dict()
        s2 = ORSet.from_dict(data)
        assert s2.contains("a")
        assert s2.contains("b")


# === LWWMap ===

class TestLWWMap:
    def test_set_and_get(self):
        m = LWWMap()
        m.set("key1", "value1", timestamp=1.0)
        assert m.get("key1") == "value1"

    def test_delete(self):
        m = LWWMap()
        m.set("key1", "value1", timestamp=1.0)
        m.delete("key1")
        assert m.get("key1") is None

    def test_update_value(self):
        m = LWWMap()
        m.set("key1", "old", timestamp=1.0)
        m.set("key1", "new", timestamp=2.0)
        assert m.get("key1") == "new"

    def test_merge(self):
        m1 = LWWMap()
        m2 = LWWMap()
        m1.set("a", "from_m1", timestamp=1.0)
        m2.set("b", "from_m2", timestamp=2.0)
        m1.merge(m2)
        assert m1.get("a") == "from_m1"
        assert m1.get("b") == "from_m2"

    def test_merge_conflict_resolution(self):
        m1 = LWWMap()
        m2 = LWWMap()
        m1.set("key", "old", timestamp=1.0)
        m2.set("key", "new", timestamp=2.0)
        m1.merge(m2)
        assert m1.get("key") == "new"

    def test_keys(self):
        m = LWWMap()
        m.set("a", 1, timestamp=1.0)
        m.set("b", 2, timestamp=2.0)
        m.set("c", 3, timestamp=3.0)
        m.delete("b")
        assert "a" in m.keys()
        assert "b" not in m.keys()
        assert "c" in m.keys()

    def test_len(self):
        m = LWWMap()
        m.set("a", 1, timestamp=1.0)
        m.set("b", 2, timestamp=2.0)
        assert len(m) == 2
        m.delete("a")
        assert len(m) == 1

    def test_to_dict(self):
        m = LWWMap()
        m.set("x", 10, timestamp=1.0)
        m.set("y", 20, timestamp=2.0)
        d = m.to_dict()
        assert d["x"] == 10
        assert d["y"] == 20
