"""
Unit tests for src.network.immune.ban_list — DistributedBanList.

All tests are deterministic, zero-external-deps, and run in milliseconds.
No network, no kernel, no oqs required.
"""

import json
import threading
import time
import pytest

from src.network.immune.ban_list import (
    BanEntry,
    BanReason,
    DistributedBanList,
    GossipBanUpdate,
)


# ---------------------------------------------------------------------------
# BanEntry tests
# ---------------------------------------------------------------------------

class TestBanEntry:
    def test_is_not_expired_when_ttl_zero(self):
        """TTL=0 means permanent ban."""
        entry = BanEntry("1.2.3.4", BanReason.MANUAL, time.time(), ttl=0, banned_by="n1")
        assert not entry.is_expired()

    def test_is_expired_after_ttl(self):
        entry = BanEntry(
            "1.2.3.4", BanReason.DOS_ATTACK,
            banned_at=time.time() - 10,  # 10s ago
            ttl=5,                        # expired 5s ago
            banned_by="n1",
        )
        assert entry.is_expired()

    def test_not_expired_before_ttl(self):
        entry = BanEntry("1.2.3.4", BanReason.DOS_ATTACK, time.time(), ttl=300, banned_by="n1")
        assert not entry.is_expired()

    def test_fingerprint_is_stable(self):
        ts = 1_700_000_000.0
        e1 = BanEntry("1.2.3.4", BanReason.DOS_ATTACK, ts, ttl=60, banned_by="n1")
        e2 = BanEntry("1.2.3.4", BanReason.DOS_ATTACK, ts, ttl=60, banned_by="n1")
        assert e1.fingerprint() == e2.fingerprint()

    def test_fingerprint_differs_for_different_target(self):
        ts = 1_700_000_000.0
        e1 = BanEntry("1.2.3.4", BanReason.DOS_ATTACK, ts, ttl=60, banned_by="n1")
        e2 = BanEntry("5.6.7.8", BanReason.DOS_ATTACK, ts, ttl=60, banned_by="n1")
        assert e1.fingerprint() != e2.fingerprint()

    def test_roundtrip_serialisation(self):
        entry = BanEntry("10.0.0.1", BanReason.BYZANTINE_BEHAVIOR, 1_700_000_000.0, ttl=120, banned_by="node-7", severity=2)
        d = entry.to_dict()
        restored = BanEntry.from_dict(d)
        assert restored.target == entry.target
        assert restored.reason == entry.reason
        assert restored.ttl == entry.ttl
        assert restored.banned_by == entry.banned_by
        assert restored.severity == entry.severity


# ---------------------------------------------------------------------------
# GossipBanUpdate tests
# ---------------------------------------------------------------------------

class TestGossipBanUpdate:
    def _make_entry(self, target="10.0.0.1", ttl=300.0) -> BanEntry:
        return BanEntry(target, BanReason.RATE_LIMIT_ABUSE, time.time(), ttl=ttl, banned_by="origin")

    def test_should_relay_initially(self):
        update = GossipBanUpdate(entry=self._make_entry(), hop=0)
        assert update.should_relay("some-other-node")

    def test_should_not_relay_at_max_hops(self):
        update = GossipBanUpdate(entry=self._make_entry(), hop=GossipBanUpdate.MAX_HOPS)
        assert not update.should_relay("any-node")

    def test_should_not_relay_if_already_seen(self):
        update = GossipBanUpdate(entry=self._make_entry(), hop=0, seen_by={"me"})
        assert not update.should_relay("me")

    def test_should_not_relay_expired_entry(self):
        entry = BanEntry("1.2.3.4", BanReason.MANUAL, time.time() - 100, ttl=10, banned_by="n1")
        update = GossipBanUpdate(entry=entry, hop=0)
        assert not update.should_relay("other")

    def test_make_relay_increments_hop(self):
        update = GossipBanUpdate(entry=self._make_entry(), hop=2, seen_by={"a"})
        relay = update.make_relay("b")
        assert relay.hop == 3
        assert "b" in relay.seen_by
        assert "a" in relay.seen_by
        # Original unchanged
        assert update.hop == 2

    def test_serialise_deserialise_roundtrip(self):
        entry = self._make_entry()
        update = GossipBanUpdate(entry=entry, hop=1, seen_by={"n1", "n2"})
        raw = update.serialise()
        restored = GossipBanUpdate.deserialise(raw)
        assert restored.entry.target == entry.target
        assert restored.hop == 1
        assert "n1" in restored.seen_by


# ---------------------------------------------------------------------------
# DistributedBanList — core API tests
# ---------------------------------------------------------------------------

class TestDistributedBanList:
    def setup_method(self):
        self.bl = DistributedBanList("node-1")

    def test_ban_makes_target_banned(self):
        self.bl.ban("10.0.0.5", BanReason.DOS_ATTACK)
        assert self.bl.is_banned("10.0.0.5")

    def test_unknown_target_not_banned(self):
        assert not self.bl.is_banned("9.9.9.9")

    def test_unban_removes_entry(self):
        self.bl.ban("10.0.0.5", BanReason.MANUAL)
        assert self.bl.is_banned("10.0.0.5")
        result = self.bl.unban("10.0.0.5")
        assert result is True
        assert not self.bl.is_banned("10.0.0.5")

    def test_unban_nonexistent_returns_false(self):
        assert self.bl.unban("99.99.99.99") is False

    def test_expired_ban_auto_removed_on_is_banned(self):
        entry = BanEntry("1.1.1.1", BanReason.UNKNOWN, time.time() - 100, ttl=10, banned_by="n1")
        with self.bl._lock:
            self.bl._bans["1.1.1.1"] = entry
        assert not self.bl.is_banned("1.1.1.1")
        assert "1.1.1.1" not in self.bl._bans

    def test_permanent_ban_never_expires(self):
        self.bl.ban("2.2.2.2", BanReason.BYZANTINE_BEHAVIOR, ttl=0)
        assert self.bl.is_banned("2.2.2.2")

    def test_active_bans_excludes_expired(self):
        self.bl.ban("3.3.3.3", BanReason.DOS_ATTACK, ttl=300)
        # inject expired entry directly
        expired = BanEntry("4.4.4.4", BanReason.MANUAL, time.time() - 200, ttl=10, banned_by="n1")
        with self.bl._lock:
            self.bl._bans["4.4.4.4"] = expired
        active = self.bl.active_bans()
        targets = {e.target for e in active}
        assert "3.3.3.3" in targets
        assert "4.4.4.4" not in targets

    def test_len_counts_all_stored_entries(self):
        self.bl.ban("a.a.a.a", BanReason.MANUAL)
        self.bl.ban("b.b.b.b", BanReason.MANUAL)
        assert len(self.bl) == 2

    def test_get_entry_returns_none_for_unknown(self):
        assert self.bl.get_entry("0.0.0.0") is None

    def test_get_entry_returns_entry_for_banned(self):
        self.bl.ban("5.5.5.5", BanReason.RATE_LIMIT_ABUSE, ttl=300, severity=2)
        entry = self.bl.get_entry("5.5.5.5")
        assert entry is not None
        assert entry.target == "5.5.5.5"
        assert entry.severity == 2


# ---------------------------------------------------------------------------
# Gossip propagation tests
# ---------------------------------------------------------------------------

class TestGossipPropagation:
    def test_apply_gossip_update_adds_entry(self):
        bl = DistributedBanList("node-2")
        entry = BanEntry("7.7.7.7", BanReason.DOS_ATTACK, time.time(), ttl=300, banned_by="node-1")
        update = GossipBanUpdate(entry=entry, hop=1, seen_by={"node-1"})
        result = bl.apply_gossip_update(update)
        assert result is True
        assert bl.is_banned("7.7.7.7")

    def test_apply_gossip_update_deduplicates(self):
        bl = DistributedBanList("node-3")
        entry = BanEntry("8.8.8.8", BanReason.MANUAL, time.time(), ttl=300, banned_by="node-1")
        update = GossipBanUpdate(entry=entry, hop=0)
        bl.apply_gossip_update(update)
        # Second application must return False (already seen)
        result2 = bl.apply_gossip_update(update)
        assert result2 is False
        assert len(bl) == 1

    def test_apply_gossip_expired_entry_ignored(self):
        bl = DistributedBanList("node-4")
        entry = BanEntry("9.9.9.9", BanReason.UNKNOWN, time.time() - 200, ttl=10, banned_by="n1")
        update = GossipBanUpdate(entry=entry, hop=0)
        result = bl.apply_gossip_update(update)
        assert result is False
        assert not bl.is_banned("9.9.9.9")

    def test_relay_callback_triggered_on_new_ban(self):
        bl = DistributedBanList("node-5")
        relayed = []
        bl.on_relay(relayed.append)
        bl.ban("6.6.6.6", BanReason.DOS_ATTACK)
        assert len(relayed) == 1
        # Verify the relayed message is valid JSON
        data = json.loads(relayed[0])
        assert data["target"] == "6.6.6.6"

    def test_relay_callback_triggered_on_received_gossip(self):
        bl = DistributedBanList("relay-node")
        relayed = []
        bl.on_relay(relayed.append)

        entry = BanEntry("6.6.6.1", BanReason.DOS_ATTACK, time.time(), ttl=300, banned_by="origin")
        update = GossipBanUpdate(entry=entry, hop=0, seen_by={"origin"})
        bl.apply_gossip_update(update)

        # hop=0 < MAX_HOPS, so relay should fire
        assert len(relayed) == 1

    def test_relay_stops_at_max_hops(self):
        bl = DistributedBanList("end-node")
        relayed = []
        bl.on_relay(relayed.append)

        entry = BanEntry("6.6.6.2", BanReason.DOS_ATTACK, time.time(), ttl=300, banned_by="origin")
        update = GossipBanUpdate(entry=entry, hop=GossipBanUpdate.MAX_HOPS, seen_by={"origin"})
        bl.apply_gossip_update(update)

        # Should be applied locally but NOT relayed
        assert bl.is_banned("6.6.6.2")
        assert len(relayed) == 0

    def test_on_new_ban_callback_invoked(self):
        bl = DistributedBanList("node-cb")
        called_with = []
        bl.on_new_ban(called_with.append)
        bl.ban("3.3.3.3", BanReason.RATE_LIMIT_ABUSE)
        assert len(called_with) == 1
        assert called_with[0].target == "3.3.3.3"


# ---------------------------------------------------------------------------
# Snapshot sync tests
# ---------------------------------------------------------------------------

class TestSnapshotSync:
    def test_serialise_snapshot_and_apply(self):
        bl1 = DistributedBanList("node-A")
        bl1.ban("1.1.1.1", BanReason.DOS_ATTACK, ttl=300)
        bl1.ban("2.2.2.2", BanReason.MANUAL, ttl=0)

        snapshot = bl1.serialise_snapshot()

        bl2 = DistributedBanList("node-B")
        added = bl2.apply_snapshot(snapshot)
        assert added == 2
        assert bl2.is_banned("1.1.1.1")
        assert bl2.is_banned("2.2.2.2")

    def test_apply_snapshot_skips_expired(self):
        bl1 = DistributedBanList("node-C")
        # Inject expired entry directly
        expired = BanEntry("5.5.5.5", BanReason.MANUAL, time.time() - 200, ttl=10, banned_by="n1")
        with bl1._lock:
            bl1._bans["5.5.5.5"] = expired
        # active_bans excludes expired, but serialise_snapshot also filters
        snapshot = bl1.serialise_snapshot()

        bl2 = DistributedBanList("node-D")
        added = bl2.apply_snapshot(snapshot)
        assert added == 0
        assert not bl2.is_banned("5.5.5.5")

    def test_apply_snapshot_idempotent(self):
        bl1 = DistributedBanList("node-E")
        bl1.ban("7.7.7.7", BanReason.DOS_ATTACK, ttl=300)
        snap = bl1.serialise_snapshot()

        bl2 = DistributedBanList("node-F")
        bl2.apply_snapshot(snap)
        added2 = bl2.apply_snapshot(snap)  # second time — dedup
        assert added2 == 0


# ---------------------------------------------------------------------------
# Thread safety smoke test
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_bans_and_reads(self):
        """Banning and querying from multiple threads must not raise."""
        bl = DistributedBanList("node-ts")
        errors = []

        def banner(n):
            try:
                for i in range(10):
                    bl.ban(f"10.{n}.{i}.0", BanReason.MANUAL, ttl=30)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(50):
                    bl.is_banned("10.0.0.0")
                    bl.active_bans()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=banner, args=(i,)) for i in range(4)]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors, f"Thread-safety errors: {errors}"
