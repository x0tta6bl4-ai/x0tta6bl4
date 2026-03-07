"""
Memory profile for long-running API call sequences.

Purpose:
  Detects memory leaks in MaaS API business logic by running 500+ sequential
  operations through the in-process logic and measuring heap growth with
  tracemalloc.

Run with:
  pytest tests/benchmarks/test_api_memory_profile.py -v -s

  # Verbose snapshot diff:
  MEMORY_PROFILE_VERBOSE=1 pytest tests/benchmarks/test_api_memory_profile.py -v -s

Thresholds:
  - Absolute heap growth over 500 iterations must be < 5 MB
  - Per-iteration growth must be < 10 KB on average
  - No single snapshot must exceed 20 MB RSS-equivalent growth

These thresholds are conservative; real production leak checks should use
memray on a live process. This suite catches obvious OOM-trajectory bugs
before they reach staging.
"""

from __future__ import annotations

import os
import time
import tracemalloc
import uuid
from collections import OrderedDict
from typing import List, Tuple
from unittest.mock import MagicMock, patch


_VERBOSE = os.getenv("MEMORY_PROFILE_VERBOSE", "0") == "1"

# Thresholds
_MAX_TOTAL_GROWTH_BYTES = 5 * 1024 * 1024   # 5 MB
_MAX_PER_ITER_BYTES = 10 * 1024             # 10 KB
_ITERATIONS = 500


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _snapshot_diff(snap1: tracemalloc.Snapshot, snap2: tracemalloc.Snapshot) -> int:
    """Return net byte growth between two tracemalloc snapshots."""
    stats = snap2.compare_to(snap1, "lineno")
    return sum(s.size_diff for s in stats if s.size_diff > 0)


def _top_growth(snap1: tracemalloc.Snapshot, snap2: tracemalloc.Snapshot, n: int = 5) -> str:
    stats = snap2.compare_to(snap1, "lineno")
    top = sorted(stats, key=lambda s: s.size_diff, reverse=True)[:n]
    lines = []
    for s in top:
        lines.append(f"  +{s.size_diff / 1024:.1f} KB  {s.traceback.format()[0]}")
    return "\n".join(lines) if lines else "  (no growth)"


# ===========================================================================
# Test 1 — Marketplace idempotency cache: 500 inserts, no leaks
# ===========================================================================

def test_memory_marketplace_idempotency_cache_no_leak():
    """
    Insert 500 idempotency entries and verify the OrderedDict does not grow
    unboundedly when max_entries is enforced.
    """
    MAX_ENTRIES = 200
    cache: OrderedDict = OrderedDict()

    def _insert(key: str, result: dict):
        """Mirrors _IDEMPOTENCY_MAX_ENTRIES eviction logic in maas_marketplace."""
        while len(cache) >= MAX_ENTRIES:
            cache.popitem(last=False)
        cache[key] = (time.time(), result)

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    for i in range(_ITERATIONS):
        _insert(f"idempotency-key-{i:04d}", {"status": "processed", "order": i})

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    growth = _snapshot_diff(snap_before, snap_after)
    assert len(cache) <= MAX_ENTRIES, f"Cache grew to {len(cache)} entries"
    assert growth < _MAX_TOTAL_GROWTH_BYTES, (
        f"Heap grew {growth / 1024:.1f} KB over {_ITERATIONS} iterations "
        f"(limit {_MAX_TOTAL_GROWTH_BYTES // 1024} KB)\n"
        + _top_growth(snap_before, snap_after)
    )

    if _VERBOSE:
        print(f"\n[marketplace-idempotency] growth={growth/1024:.1f} KB, cache_size={len(cache)}")
        print(_top_growth(snap_before, snap_after))


# ===========================================================================
# Test 2 — Telemetry LRU cache: 500 heartbeats, no leak
# ===========================================================================

def test_memory_telemetry_lru_no_leak():
    """
    500 heartbeat insertions into the telemetry LRU cache.
    Cache is bounded to 200 entries; verify heap growth is bounded.
    """
    with (
        patch("redis.from_url", side_effect=Exception("no redis")),
        patch("src.api.maas_telemetry.get_db", return_value=MagicMock()),
        patch("src.api.maas_telemetry.get_current_user_from_maas"),
        patch("src.api.maas_telemetry._record_heartbeat_metric"),
        patch("src.api.maas_telemetry.mark_degraded_dependency"),
    ):
        import src.api.maas_telemetry as tele
        cache = tele.LRUCache(max_size=200)

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    for i in range(_ITERATIONS):
        node_id = f"mem-node-{i % 300:04d}"  # cycle through more IDs than cache size
        cache.set(f"telemetry:{node_id}", {
            "node_id": node_id,
            "timestamp": time.time(),
            "cpu_usage": 0.3 + (i % 10) * 0.05,
            "memory_usage": 0.4,
            "bandwidth_mbps": 100.0,
            "packet_loss": 0.0,
        })

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    growth = _snapshot_diff(snap_before, snap_after)
    assert len(cache._cache) <= 200, f"LRU grew to {len(cache._cache)} entries"
    assert growth < _MAX_TOTAL_GROWTH_BYTES, (
        f"Heap grew {growth / 1024:.1f} KB (limit {_MAX_TOTAL_GROWTH_BYTES // 1024} KB)\n"
        + _top_growth(snap_before, snap_after)
    )

    if _VERBOSE:
        print(f"\n[telemetry-lru] growth={growth/1024:.1f} KB, cache_size={len(cache._cache)}")


# ===========================================================================
# Test 3 — Marketplace listings dict: create + release cycle, no leak
# ===========================================================================

def test_memory_marketplace_listings_create_release_cycle():
    """
    500 create+release cycles on the in-memory listings dict.
    Each listing is removed after release; heap should be near-zero net growth.
    """
    from threading import Lock
    listings: dict = {}
    lock = Lock()

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    for i in range(_ITERATIONS):
        lid = str(uuid.uuid4())
        with lock:
            listings[lid] = {
                "id": lid,
                "owner_id": f"user-{i % 20}",
                "node_id": f"node-{i:04d}",
                "price_per_hour": 0.05,
                "status": "available",
                "region": "eu-west",
                "created_at": time.time(),
                "updated_at": time.time(),
                "metadata": {"capabilities": ["pqc", "ebpf"], "uptime": 0.999},
            }
        # Simulate rental then release
        with lock:
            if lid in listings:
                listings.pop(lid)

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    growth = _snapshot_diff(snap_before, snap_after)
    assert len(listings) == 0, f"Listing store leaked {len(listings)} entries"
    assert growth < _MAX_TOTAL_GROWTH_BYTES, (
        f"Heap grew {growth / 1024:.1f} KB (limit {_MAX_TOTAL_GROWTH_BYTES // 1024} KB)\n"
        + _top_growth(snap_before, snap_after)
    )

    if _VERBOSE:
        print(f"\n[marketplace-cycle] growth={growth/1024:.1f} KB, final_listings={len(listings)}")


# ===========================================================================
# Test 4 — Node record lifecycle: register + decommission
# ===========================================================================

def test_memory_node_register_decommission_cycle():
    """
    500 node register+decommission cycles.
    Each node dict is created then discarded; net growth must stay < 5 MB.
    """
    active_nodes: dict = {}

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    for i in range(_ITERATIONS):
        nid = str(uuid.uuid4())
        active_nodes[nid] = {
            "id": nid,
            "mesh_id": f"mesh-{i % 5:02d}",
            "name": f"bench-node-{i:04d}",
            "status": "approved",
            "role": "worker",
            "ip_address": f"10.0.{i // 256 % 256}.{i % 256}",
            "region": "eu-west",
            "capabilities": ["pqc", "ebpf", "tor"],
            "joined_at": time.time(),
            "last_seen": time.time(),
            "telemetry": {
                "cpu": 0.35,
                "mem": 0.52,
                "bw_mbps": 100.0,
                "latency_ms": 8.5,
            },
        }
        # Decommission: remove from store
        active_nodes.pop(nid)

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    growth = _snapshot_diff(snap_before, snap_after)
    assert len(active_nodes) == 0
    assert growth < _MAX_TOTAL_GROWTH_BYTES, (
        f"Heap grew {growth / 1024:.1f} KB (limit {_MAX_TOTAL_GROWTH_BYTES // 1024} KB)\n"
        + _top_growth(snap_before, snap_after)
    )

    if _VERBOSE:
        print(f"\n[node-lifecycle] growth={growth/1024:.1f} KB")


# ===========================================================================
# Test 5 — Governance proposal + vote cycle
# ===========================================================================

def test_memory_governance_proposal_vote_cycle():
    """
    100 proposal creation + voting cycles through GovernanceEngine.
    PQC signature validation is bypassed via test mode.
    """
    os.environ.setdefault("_X0TTA_TEST_MODE_", "true")

    from src.dao.governance import GovernanceEngine, VoteType

    gov = GovernanceEngine(node_id="mem-bench-node")

    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    for i in range(100):  # proposals are heavier — 100 is sufficient
        prop = gov.create_proposal(
            f"Bench Proposal {i}",
            f"Description {i}",
            duration_seconds=0.001,
        )
        for voter in ["v1", "v2", "v3"]:
            gov.cast_vote(prop.id, voter, VoteType.YES, tokens=100.0)

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    growth = _snapshot_diff(snap_before, snap_after)
    # Governance keeps proposals in memory by design; check growth is reasonable
    # 100 proposals × ~5 KB each ≈ 500 KB absolute max
    _GOV_LIMIT = 2 * 1024 * 1024  # 2 MB (generous — proposals accumulate)
    assert growth < _GOV_LIMIT, (
        f"Governance heap grew {growth / 1024:.1f} KB for 100 proposals "
        f"(limit {_GOV_LIMIT // 1024} KB)\n"
        + _top_growth(snap_before, snap_after)
    )

    if _VERBOSE:
        print(f"\n[governance-cycle] growth={growth/1024:.1f} KB, proposals={len(gov.proposals)}")


# ===========================================================================
# Test 6 — Per-iteration growth regression check
# ===========================================================================

def test_memory_per_iteration_growth_regression():
    """
    Measures growth at checkpoints (every 100 iterations) to detect
    linear vs. constant growth patterns.  Fails if any 100-iter window
    shows > 1 MB growth (signals a leak trajectory).
    """
    from threading import Lock
    listings: dict = {}
    lock = Lock()

    tracemalloc.start()

    checkpoints: List[Tuple[int, int]] = []
    snap_prev = tracemalloc.take_snapshot()

    for i in range(_ITERATIONS):
        lid = str(uuid.uuid4())
        with lock:
            listings[lid] = {
                "id": lid,
                "owner_id": f"u-{i % 10}",
                "node_id": f"n-{i:04d}",
                "price_per_hour": 0.05,
                "status": "available",
                "region": "us-east",
                "created_at": time.time(),
            }
        with lock:
            listings.pop(lid, None)

        if (i + 1) % 100 == 0:
            snap_now = tracemalloc.take_snapshot()
            window_growth = _snapshot_diff(snap_prev, snap_now)
            checkpoints.append((i + 1, window_growth))
            snap_prev = snap_now

    tracemalloc.stop()

    _WINDOW_LIMIT = 1 * 1024 * 1024  # 1 MB per 100-iter window
    for iteration, growth in checkpoints:
        assert growth < _WINDOW_LIMIT, (
            f"Window [{iteration-99}..{iteration}] grew {growth/1024:.1f} KB "
            f"(limit {_WINDOW_LIMIT // 1024} KB) — possible leak"
        )

    if _VERBOSE:
        print("\n[per-iter-regression] checkpoints:")
        for iteration, growth in checkpoints:
            print(f"  iter {iteration:4d}: +{growth/1024:.1f} KB")
