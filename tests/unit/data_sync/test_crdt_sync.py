"""Tests for CRDT Sync module (crdt.py + crdt_sync.py)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.data_sync.crdt import (GCounter, GSet, LWWMap, LWWRegister, ORSet,
                                PNCounter)
from src.data_sync.crdt_sync import CRDTSync


# ---------------------------------------------------------------------------
# GCounter
# ---------------------------------------------------------------------------
class TestGCounter:
    def test_increment_and_value(self):
        c = GCounter()
        c.increment("n1", 5)
        assert c.value() == 5

    def test_increment_multiple_nodes(self):
        c = GCounter()
        c.increment("n1", 3)
        c.increment("n2", 7)
        assert c.value() == 10

    def test_merge(self):
        c1 = GCounter()
        c1.increment("n1", 5)
        c2 = GCounter()
        c2.increment("n2", 7)
        c1.merge(c2)
        assert c1.value() == 12

    def test_merge_takes_max(self):
        c1 = GCounter()
        c1.increment("n1", 5)
        c2 = GCounter()
        c2.increment("n1", 3)  # lower than c1
        c1.merge(c2)
        assert c1.value() == 5  # max wins

    def test_negative_increment_raises(self):
        c = GCounter()
        with pytest.raises(ValueError, match="non-negative"):
            c.increment("n1", -1)

    def test_to_dict_from_dict(self):
        c = GCounter()
        c.increment("n1", 5)
        c.increment("n2", 3)
        data = c.to_dict()
        c2 = GCounter.from_dict(data)
        assert c2.value() == c.value()


# ---------------------------------------------------------------------------
# PNCounter
# ---------------------------------------------------------------------------
class TestPNCounter:
    def test_increment_decrement(self):
        c = PNCounter()
        c.increment("n1", 10)
        c.decrement("n1", 3)
        assert c.value() == 7

    def test_merge(self):
        c1 = PNCounter()
        c1.increment("n1", 10)
        c2 = PNCounter()
        c2.decrement("n2", 4)
        c1.merge(c2)
        assert c1.value() == 6

    def test_negative_increment_raises(self):
        c = PNCounter()
        with pytest.raises(ValueError):
            c.increment("n1", -1)

    def test_negative_decrement_raises(self):
        c = PNCounter()
        with pytest.raises(ValueError):
            c.decrement("n1", -1)

    def test_to_dict_from_dict(self):
        c = PNCounter()
        c.increment("n1", 5)
        c.decrement("n2", 2)
        data = c.to_dict()
        c2 = PNCounter.from_dict(data)
        assert c2.value() == c.value()


# ---------------------------------------------------------------------------
# LWWRegister
# ---------------------------------------------------------------------------
class TestLWWRegister:
    def test_set_and_value(self):
        reg = LWWRegister(node_id="n1", value="v1", timestamp=1.0)
        assert reg.value == "v1"

    def test_set_newer_overwrites(self):
        reg = LWWRegister(node_id="n1", value="v1", timestamp=1.0)
        reg.set("v2", timestamp=2.0)
        assert reg.value == "v2"

    def test_set_older_ignored(self):
        reg = LWWRegister(node_id="n1", value="v1", timestamp=2.0)
        reg.set("v2", timestamp=1.0)
        assert reg.value == "v1"

    def test_merge_newer_wins(self):
        a = LWWRegister(node_id="n1", value="a", timestamp=1.0)
        b = LWWRegister(node_id="n2", value="b", timestamp=2.0)
        a.merge(b)
        assert a.value == "b"

    def test_merge_older_no_change(self):
        a = LWWRegister(node_id="n1", value="a", timestamp=2.0)
        b = LWWRegister(node_id="n2", value="b", timestamp=1.0)
        a.merge(b)
        assert a.value == "a"

    def test_to_dict_from_dict(self):
        reg = LWWRegister(node_id="n1", value="hello", timestamp=42.0)
        data = reg.to_dict()
        reg2 = LWWRegister.from_dict(data)
        assert reg2.value == "hello"
        assert reg2.timestamp == 42.0


# ---------------------------------------------------------------------------
# GSet
# ---------------------------------------------------------------------------
class TestGSet:
    def test_add_and_contains(self):
        s = GSet()
        s.add("apple")
        assert s.contains("apple")
        assert not s.contains("banana")

    def test_merge(self):
        s1 = GSet()
        s1.add("a")
        s2 = GSet()
        s2.add("b")
        s1.merge(s2)
        assert s1.contains("a")
        assert s1.contains("b")

    def test_len(self):
        s = GSet()
        s.add("x")
        s.add("y")
        assert len(s) == 2

    def test_to_dict_from_dict(self):
        s = GSet()
        s.add("a")
        s.add("b")
        data = s.to_dict()
        s2 = GSet.from_dict(data)
        assert s2.contains("a")
        assert s2.contains("b")


# ---------------------------------------------------------------------------
# ORSet
# ---------------------------------------------------------------------------
class TestORSet:
    def test_add_and_contains(self):
        s = ORSet()
        s.add("apple", "n1")
        s.add("banana", "n1")
        assert s.contains("apple")
        assert s.contains("banana")

    def test_remove(self):
        s = ORSet()
        s.add("apple", "n1")
        s.remove("apple")
        assert not s.contains("apple")

    def test_merge(self):
        s1 = ORSet()
        s2 = ORSet()
        s1.add("x", "n1")
        s2.add("x", "n2")
        s1.merge(s2)
        assert s1.contains("x")

    def test_concurrent_add_remove_add_wins(self):
        """Add-wins: concurrent add + remove should preserve the element."""
        s1 = ORSet()
        s2 = ORSet()
        s1.add("x", "n1")
        s2.add("x", "n2")
        s1.remove("x")
        assert not s1.contains("x")
        # merge with s2 — add-wins semantics
        s1.merge(s2)
        assert s1.contains("x")

    def test_len(self):
        s = ORSet()
        s.add("a", "n1")
        s.add("b", "n1")
        assert len(s) == 2

    def test_to_dict_from_dict(self):
        s = ORSet()
        s.add("x", "n1")
        data = s.to_dict()
        s2 = ORSet.from_dict(data)
        assert s2.contains("x")


# ---------------------------------------------------------------------------
# CRDTSync
# ---------------------------------------------------------------------------
class TestCRDTSync:
    def test_register_and_get_state(self):
        sync = CRDTSync("n1")
        counter = GCounter()
        sync.register_crdt("counter", counter)
        counter.increment("n1", 3)
        state = sync.get_crdt_state()
        assert state["counter"] == 3

    def test_merge_from_peer(self):
        sync = CRDTSync("n1")
        local = GCounter()
        local.increment("n1", 5)
        sync.register_crdt("counter", local)

        peer_counter = GCounter()
        peer_counter.increment("n2", 7)
        sync.merge_from_peer("n2", {"counter": peer_counter})

        state = sync.get_crdt_state()
        assert state["counter"] == 12

    def test_broadcast_calls_callbacks(self):
        sync = CRDTSync("n1")
        counter = GCounter()
        counter.increment("n1", 1)
        sync.register_crdt("c", counter)

        received = {}
        sync.register_sync_callback(lambda s: received.update(s))
        sync.broadcast()
        assert received["c"] == 1

    def test_broadcast_handles_callback_error(self):
        sync = CRDTSync("n1")
        counter = GCounter()
        sync.register_crdt("c", counter)

        def bad_callback(state):
            raise RuntimeError("boom")

        sync.register_sync_callback(bad_callback)
        # Should not raise
        sync.broadcast()

    @pytest.mark.asyncio
    async def test_start_stop_sync_no_router(self):
        sync = CRDTSync("n1")
        await sync.start_sync(interval_sec=1)
        await sync.stop_sync()

    @pytest.mark.asyncio
    async def test_receive_updates_from_peer(self):
        sync = CRDTSync("n1")
        counter = GCounter()
        counter.increment("n1", 5)
        sync.register_crdt("counter", counter)

        peer_data = {"n2": 7}
        await sync._receive_updates_from_peer("n2", {"counter": peer_data})
        state = sync.get_crdt_state()
        assert state["counter"] == 12

    @pytest.mark.asyncio
    async def test_receive_updates_unknown_key_ignored(self):
        sync = CRDTSync("n1")
        counter = GCounter()
        sync.register_crdt("counter", counter)

        await sync._receive_updates_from_peer("n2", {"unknown_key": {}})
        assert "unknown_key" not in sync.get_crdt_state()
