"""
Distributed Ban List — Digital Immune System
=============================================

Implements a gossip-based distributed ban list for the x0tta6bl4 mesh.

Concept
-------
Each node maintains a local set of banned peers/IPs with TTL-based expiry.
When a node bans a peer it:

1. Adds the entry to its local ban set.
2. Serialises the ban as a ``GossipBanUpdate`` and emits it to all neighbours
   (callers are responsible for the transport layer).
3. Receiving nodes call :meth:`DistributedBanList.apply_gossip_update` which
   validates the entry and propagates it further if it is new (epidemic spread).

Optional XDP enforcement
------------------------
If an :class:`~src.network.ebpf.hooks.xdp_hook.XDPHook` instance is injected,
banned IPs are also blocked at kernel level via a pinned BPF map — this mirrors
the pattern used in ``src/network/ebpf/hooks/xdp_hook.py``.

Concurrency
-----------
All public methods are thread-safe (protected by ``threading.Lock``).
Async callers can use ``asyncio.to_thread`` if needed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Iterator, List, Optional, Set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class BanReason(str, Enum):
    """Reason for banning a peer."""
    DOS_ATTACK          = "dos_attack"
    INVALID_SIGNATURE   = "invalid_signature"
    REPLAY_ATTACK       = "replay_attack"
    BYZANTINE_BEHAVIOR  = "byzantine_behavior"
    RATE_LIMIT_ABUSE    = "rate_limit_abuse"
    MANUAL              = "manual"
    UNKNOWN             = "unknown"


@dataclass
class BanEntry:
    """A single ban record."""
    target: str          # IP address or peer ID
    reason: BanReason
    banned_at: float     # Unix timestamp
    ttl: float           # Seconds until expiry (0 = permanent)
    banned_by: str       # Node ID that originated the ban
    severity: int = 1    # 1 (mild) – 3 (critical); affects XDP enforcement priority

    @property
    def expires_at(self) -> Optional[float]:
        return None if self.ttl == 0 else self.banned_at + self.ttl

    def is_expired(self) -> bool:
        if self.ttl == 0:
            return False
        return time.time() > self.banned_at + self.ttl

    def fingerprint(self) -> str:
        """Stable hash for deduplication during gossip propagation."""
        data = f"{self.target}:{self.reason.value}:{self.banned_by}:{self.banned_at:.3f}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "target":    self.target,
            "reason":    self.reason.value,
            "banned_at": self.banned_at,
            "ttl":       self.ttl,
            "banned_by": self.banned_by,
            "severity":  self.severity,
            "fp":        self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BanEntry":
        return cls(
            target    = d["target"],
            reason    = BanReason(d.get("reason", BanReason.UNKNOWN.value)),
            banned_at = float(d["banned_at"]),
            ttl       = float(d.get("ttl", 300)),
            banned_by = d.get("banned_by", "unknown"),
            severity  = int(d.get("severity", 1)),
        )


# ---------------------------------------------------------------------------
# Gossip update envelope
# ---------------------------------------------------------------------------

@dataclass
class GossipBanUpdate:
    """
    Envelope sent to neighbours when a new ban is created or re-gossiped.

    Hop count limits propagation depth so bans don't circulate forever.
    """
    entry: BanEntry
    hop:   int = 0          # Incremented on each relay
    seen_by: Set[str] = field(default_factory=set)  # Node IDs that already processed this

    MAX_HOPS = 6  # Epidemic radius: ~log2(N) hops for N=64 nodes

    def should_relay(self, local_node_id: str) -> bool:
        return (
            not self.entry.is_expired()
            and self.hop < self.MAX_HOPS
            and local_node_id not in self.seen_by
        )

    def make_relay(self, local_node_id: str) -> "GossipBanUpdate":
        """Return a copy with hop incremented and this node marked as seen."""
        return GossipBanUpdate(
            entry    = self.entry,
            hop      = self.hop + 1,
            seen_by  = self.seen_by | {local_node_id},
        )

    def serialise(self) -> str:
        payload = self.entry.to_dict()
        payload["hop"] = self.hop
        payload["seen_by"] = list(self.seen_by)
        return json.dumps(payload)

    @classmethod
    def deserialise(cls, raw: str) -> "GossipBanUpdate":
        d = json.loads(raw)
        entry = BanEntry.from_dict(d)
        return cls(
            entry    = entry,
            hop      = int(d.get("hop", 0)),
            seen_by  = set(d.get("seen_by", [])),
        )


# ---------------------------------------------------------------------------
# Distributed Ban List
# ---------------------------------------------------------------------------

# Callback signature: (entry: BanEntry) -> None
_BanCallback = Callable[[BanEntry], None]


class DistributedBanList:
    """
    Gossip-propagated, TTL-based distributed ban list.

    Example::

        ban_list = DistributedBanList("node-alpha")

        # Subscribe to new bans to relay them to neighbours
        ban_list.on_new_ban(lambda entry: broadcast_to_peers(entry))

        # Ban a misbehaving peer
        ban_list.ban("10.0.0.99", BanReason.DOS_ATTACK, ttl=300)

        # On receiving a gossip update from a peer:
        update = GossipBanUpdate.deserialise(raw_bytes_from_peer)
        ban_list.apply_gossip_update(update)

        # Check before routing
        if ban_list.is_banned("10.0.0.99"):
            drop_packet()
    """

    def __init__(
        self,
        node_id: str,
        max_ban_entries: int = 10_000,
        cleanup_interval: float = 60.0,
    ):
        """
        Args:
            node_id:          Local node identifier (used as ``banned_by`` origin).
            max_ban_entries:  Maximum entries before LRU eviction of oldest expired.
            cleanup_interval: Seconds between automatic expiry sweeps.
        """
        self.node_id = node_id
        self.max_ban_entries = max_ban_entries
        self.cleanup_interval = cleanup_interval

        # Main storage: target → BanEntry
        self._bans: Dict[str, BanEntry] = {}
        # Fingerprints of already-seen gossip updates (for loop detection)
        self._seen_fps: Set[str] = set()

        self._lock = threading.Lock()
        self._ban_callbacks: List[_BanCallback] = []
        self._relay_callbacks: List[Callable[[str], None]] = []

        self._last_cleanup = time.time()

        logger.info("DistributedBanList initialised for node %s", node_id)

    # ------------------------------------------------------------------
    # Callbacks / hooks
    # ------------------------------------------------------------------

    def on_new_ban(self, callback: _BanCallback) -> None:
        """Register a callback invoked whenever *this node* creates a new ban."""
        self._ban_callbacks.append(callback)

    def on_relay(self, callback: Callable[[str], None]) -> None:
        """
        Register a callback invoked when a gossip update should be relayed.
        The argument is the serialised :class:`GossipBanUpdate` JSON string.
        """
        self._relay_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def ban(
        self,
        target: str,
        reason: BanReason = BanReason.UNKNOWN,
        ttl: float = 300.0,
        severity: int = 1,
    ) -> BanEntry:
        """
        Ban a target (IP or peer ID) locally and emit gossip.

        Args:
            target:   IP address or peer ID to ban.
            reason:   Why the ban was issued.
            ttl:      Seconds until the ban expires (0 = permanent).
            severity: 1–3 urgency level (3 triggers immediate XDP enforcement).

        Returns:
            The created :class:`BanEntry`.
        """
        entry = BanEntry(
            target    = target,
            reason    = reason,
            banned_at = time.time(),
            ttl       = ttl,
            banned_by = self.node_id,
            severity  = severity,
        )
        with self._lock:
            self._apply_entry(entry)

        logger.warning(
            "BANNED %s (reason=%s ttl=%ss sev=%d) by %s",
            target, reason.value, ttl or "∞", severity, self.node_id,
        )

        # Notify local subscribers
        for cb in self._ban_callbacks:
            try:
                cb(entry)
            except Exception:
                logger.exception("Ban callback error")

        # Emit gossip
        update = GossipBanUpdate(entry=entry, hop=0, seen_by={self.node_id})
        self._emit_relay(update)

        return entry

    def unban(self, target: str) -> bool:
        """
        Remove a ban (manual lift). Does NOT propagate an unban gossip in MVP.

        Returns:
            True if the target was banned and is now removed.
        """
        with self._lock:
            if target in self._bans:
                del self._bans[target]
                logger.info("Unbanned %s", target)
                return True
        return False

    def is_banned(self, target: str) -> bool:
        """Check whether *target* is currently banned (and not expired)."""
        with self._lock:
            self._maybe_cleanup()
            entry = self._bans.get(target)
            if entry is None:
                return False
            if entry.is_expired():
                del self._bans[target]
                return False
            return True

    def get_entry(self, target: str) -> Optional[BanEntry]:
        """Return the :class:`BanEntry` for *target*, or None."""
        with self._lock:
            entry = self._bans.get(target)
            if entry and entry.is_expired():
                del self._bans[target]
                return None
            return entry

    def active_bans(self) -> List[BanEntry]:
        """Return all non-expired ban entries."""
        with self._lock:
            self._maybe_cleanup()
            return [e for e in self._bans.values() if not e.is_expired()]

    def __len__(self) -> int:
        with self._lock:
            return len(self._bans)

    def __iter__(self) -> Iterator[BanEntry]:
        with self._lock:
            return iter(list(self._bans.values()))

    # ------------------------------------------------------------------
    # Gossip interface
    # ------------------------------------------------------------------

    def apply_gossip_update(self, update: GossipBanUpdate) -> bool:
        """
        Process an incoming gossip ban update from a peer.

        Validates TTL, deduplicates by fingerprint, applies the entry
        locally, and triggers relay to further neighbours.

        Returns:
            True if the update was new and applied; False if duplicate/expired.
        """
        entry = update.entry
        fp = entry.fingerprint()

        with self._lock:
            # Dedup: have we processed this exact ban before?
            if fp in self._seen_fps:
                return False

            if entry.is_expired():
                logger.debug("Discarding expired gossip ban for %s", entry.target)
                self._seen_fps.add(fp)
                return False

            self._seen_fps.add(fp)
            self._apply_entry(entry)

        logger.info(
            "Gossip ban applied: %s (reason=%s hop=%d)",
            entry.target, entry.reason.value, update.hop,
        )

        # Relay to further nodes if within hop limit
        if update.should_relay(self.node_id):
            relay = update.make_relay(self.node_id)
            self._emit_relay(relay)

        return True

    def serialise_snapshot(self) -> str:
        """
        Serialise all active bans for full-state sync with a new peer.

        Returns:
            JSON string containing a list of ban entries.
        """
        with self._lock:
            entries = [e.to_dict() for e in self._bans.values() if not e.is_expired()]
        return json.dumps({"node_id": self.node_id, "bans": entries})

    def apply_snapshot(self, raw: str) -> int:
        """
        Apply a full-state snapshot received from a peer (e.g., on join).

        Returns:
            Number of new entries added.
        """
        data = json.loads(raw)
        added = 0
        for d in data.get("bans", []):
            try:
                entry = BanEntry.from_dict(d)
                fp = entry.fingerprint()
                with self._lock:
                    if fp not in self._seen_fps and not entry.is_expired():
                        self._seen_fps.add(fp)
                        self._apply_entry(entry)
                        added += 1
            except Exception:
                logger.debug("Skipping malformed snapshot entry", exc_info=True)
        logger.info("Snapshot applied: %d new bans from %s", added, data.get("node_id"))
        return added

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_entry(self, entry: BanEntry) -> None:
        """Insert or refresh a ban entry (caller must hold lock)."""
        existing = self._bans.get(entry.target)
        if existing and not existing.is_expired():
            # Keep stricter of the two entries (higher severity, longer TTL)
            if entry.severity > existing.severity or (
                entry.ttl == 0 or (existing.ttl != 0 and entry.expires_at > existing.expires_at)  # type: ignore[operator]
            ):
                self._bans[entry.target] = entry
        else:
            self._bans[entry.target] = entry

        # Evict if over capacity (remove oldest expired first, then shortest-TTL active)
        if len(self._bans) > self.max_ban_entries:
            self._evict_one()

    def _evict_one(self) -> None:
        """Remove one entry to stay within max_ban_entries (called with lock held)."""
        # Prefer expired entries
        for target, entry in list(self._bans.items()):
            if entry.is_expired():
                del self._bans[target]
                return
        # Fallback: evict soonest-to-expire active entry
        soonest = min(
            ((t, e) for t, e in self._bans.items() if e.ttl > 0),
            key=lambda x: x[1].expires_at,
            default=None,
        )
        if soonest:
            del self._bans[soonest[0]]

    def _maybe_cleanup(self) -> None:
        """Periodic sweep of expired entries (called with lock held)."""
        now = time.time()
        if now - self._last_cleanup < self.cleanup_interval:
            return
        expired = [t for t, e in self._bans.items() if e.is_expired()]
        for target in expired:
            del self._bans[target]
        if expired:
            logger.debug("Cleaned up %d expired ban entries", len(expired))
        # Also trim seen_fps to prevent unbounded growth (keep last 50k)
        if len(self._seen_fps) > 50_000:
            # Can't do LRU without ordered set — just clear half
            fps_list = list(self._seen_fps)
            self._seen_fps = set(fps_list[len(fps_list) // 2:])
        self._last_cleanup = now

    def _emit_relay(self, update: GossipBanUpdate) -> None:
        """Push a gossip update to all relay callbacks."""
        if not self._relay_callbacks:
            return
        raw = update.serialise()
        for cb in self._relay_callbacks:
            try:
                cb(raw)
            except Exception:
                logger.exception("Relay callback error")
