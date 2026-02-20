"""
eBPF Stigmergy Bridge
======================
Userspace bridge that reads per-peer packet counters from the
``stigmergy_pkt_count`` eBPF map (written by stigmergy_counter.bpf.c)
and converts count deltas into pheromone reinforcement signals for
:class:`~src.network.routing.stigmergy.StigmergyRouter`.

Architecture::

    Kernel XDP program
        ↓ writes per-IP packet counts to BPF LRU_HASH
    StigmergyBridge  (poll every N seconds via asyncio loop)
        ↓ reads map via bpftool / bpffs ctypes
        ↓ computes delta since last poll
    StigmergyRouter.reinforce(dest_id, next_hop, success=True)
        ↓ updates Python-side pheromone scores
    Routing decision uses get_best_route(dest_id)

When the eBPF program is not loaded (development / rootless env),
the bridge operates in *simulation mode*: it listens for explicit
``record_ack()`` / ``record_timeout()`` calls from the application
layer and directly reinforces the router.  No kernel access needed.
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import socket
import struct
import subprocess
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from src.network.routing.stigmergy import StigmergyRouter

logger = logging.getLogger(__name__)

# BPF filesystem pin path — must match LIBBPF_PIN_BY_NAME in the .bpf.c
_BPF_PIN_DIR = Path("/sys/fs/bpf")
_PKT_MAP_NAME = "stigmergy_pkt_count"
_BYTE_MAP_NAME = "stigmergy_byte_count"

# Polling interval: read eBPF map every N seconds
DEFAULT_POLL_INTERVAL = 2.0

# Minimum packet delta to trigger a reinforce (avoids noise from single stray pkts)
MIN_DELTA_TO_REINFORCE = 3


def _ip_u32_to_str(u32_val: int) -> str:
    """Convert a big-endian u32 IP (as read from BPF map) to dotted-quad string."""
    return socket.inet_ntoa(struct.pack(">I", u32_val))


def _bpftool_dump_map(map_name: str) -> Dict[int, int]:
    """
    Read an LRU_HASH BPF map via ``bpftool map dump name <name> --json``.

    Returns:
        Dict mapping src_ip_u32 -> counter_value.
        Empty dict if bpftool not available or map not found.
    """
    try:
        result = subprocess.run(
            ["bpftool", "map", "dump", "name", map_name, "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return {}

        entries = json.loads(result.stdout)
        if not isinstance(entries, list):
            return {}

        counts: Dict[int, int] = {}
        for entry in entries:
            key_bytes = entry.get("key", [])
            val_bytes = entry.get("value", [])
            if len(key_bytes) == 4 and len(val_bytes) == 8:
                # Key is 4-byte array (little-endian u32 as stored by kernel)
                ip_u32 = struct.unpack("<I", bytes(key_bytes))[0]
                count = struct.unpack("<Q", bytes(val_bytes))[0]
                counts[ip_u32] = count
        return counts

    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return {}
    except Exception as exc:
        logger.debug("bpftool read error: %s", exc)
        return {}


class StigmergyBridge:
    """
    Bridges the kernel eBPF packet counter map with the Python StigmergyRouter.

    Usage (with eBPF loaded)::

        router = StigmergyRouter("node-1")
        bridge = StigmergyBridge(router, interface="eth0")
        await bridge.start()          # loads eBPF if compiled .o exists
        # ... runs in background ...
        await bridge.stop()

    Usage (simulation / rootless)::

        bridge = StigmergyBridge(router)
        await bridge.start()
        bridge.record_ack("peer-2", "peer-2")      # emulates ACK from peer
        bridge.record_timeout("peer-3", "peer-3")  # emulates timeout

    The bridge resolves peer IDs via an IP→peer mapping that callers populate::

        bridge.register_peer("peer-2", "10.0.0.2")
    """

    def __init__(
        self,
        router: StigmergyRouter,
        interface: Optional[str] = None,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        ebpf_object: Optional[Path] = None,
    ):
        """
        Args:
            router:        The StigmergyRouter instance to feed reinforcement signals.
            interface:     Network interface to attach XDP program to (optional).
            poll_interval: Seconds between eBPF map reads.
            ebpf_object:   Path to compiled .bpf.o file (auto-detected if None).
        """
        self.router = router
        self.interface = interface
        self.poll_interval = poll_interval

        # Auto-detect compiled object next to this file's bpf_programs subdir
        if ebpf_object is None:
            candidate = Path(__file__).parent / "bpf_programs" / "stigmergy_counter.bpf.o"
            self.ebpf_object: Optional[Path] = candidate if candidate.exists() else None
        else:
            self.ebpf_object = Path(ebpf_object)

        # IP address → peer_id mapping (populated by callers)
        self._ip_to_peer: Dict[str, str] = {}

        # Last snapshot: ip_u32 → pkt_count (for delta computation)
        self._last_snapshot: Dict[int, int] = {}

        self._running = False
        self._poll_task: Optional[asyncio.Task] = None
        self._xdp_attached = False

        # Simulation-mode counters (when eBPF not available)
        self._sim_acks: Dict[Tuple[str, str], int] = {}
        self._sim_timeouts: Dict[Tuple[str, str], int] = {}

    # ------------------------------------------------------------------
    # Peer registry
    # ------------------------------------------------------------------

    def register_peer(self, peer_id: str, ip_address: str) -> None:
        """Associate a peer ID with its IP address for eBPF map lookups."""
        self._ip_to_peer[ip_address] = peer_id
        logger.debug("Registered peer %s → %s", peer_id, ip_address)

    def unregister_peer(self, peer_id: str) -> None:
        """Remove peer from IP mapping."""
        self._ip_to_peer = {ip: p for ip, p in self._ip_to_peer.items() if p != peer_id}

    # ------------------------------------------------------------------
    # Simulation-mode API (no kernel required)
    # ------------------------------------------------------------------

    def record_ack(self, dest_id: str, next_hop: str) -> None:
        """
        Record a successful ACK for a route (simulation mode).
        Directly reinforces the router without going through eBPF.
        """
        self.router.reinforce(dest_id, next_hop, success=True)
        key = (dest_id, next_hop)
        self._sim_acks[key] = self._sim_acks.get(key, 0) + 1
        logger.debug("Stigmergy ACK: %s via %s", dest_id, next_hop)

    def record_timeout(self, dest_id: str, next_hop: str) -> None:
        """
        Record a route timeout (simulation mode).
        Punishes the route in the router.
        """
        self.router.reinforce(dest_id, next_hop, success=False)
        key = (dest_id, next_hop)
        self._sim_timeouts[key] = self._sim_timeouts.get(key, 0) + 1
        logger.debug("Stigmergy timeout: %s via %s", dest_id, next_hop)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the bridge (try to attach XDP, begin polling loop).

        The caller is responsible for starting/stopping the router's own
        evaporation loop independently via ``router.start()`` / ``router.stop()``.
        """
        self._running = True

        if self.interface and self.ebpf_object and self.ebpf_object.exists():
            self._xdp_attached = self._try_attach_xdp()
        else:
            mode = "simulation" if not self.ebpf_object else "no-interface"
            logger.info("StigmergyBridge started in %s mode", mode)

        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(
            "StigmergyBridge started (eBPF=%s, interface=%s)",
            self._xdp_attached,
            self.interface or "none",
        )

    async def stop(self) -> None:
        """Stop polling and detach XDP program."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._xdp_attached and self.interface:
            self._try_detach_xdp()

        logger.info("StigmergyBridge stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _try_attach_xdp(self) -> bool:
        """Attempt to load the eBPF object and attach it to the interface."""
        try:
            cmd = [
                "ip", "link", "set", "dev", self.interface,
                "xdp", "obj", str(self.ebpf_object), "sec", "xdp",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                logger.info("XDP stigmergy counter attached to %s", self.interface)
                return True
            logger.warning(
                "Failed to attach XDP to %s (need root): %s",
                self.interface,
                result.stderr.strip(),
            )
        except Exception as exc:
            logger.warning("XDP attach error: %s", exc)
        return False

    def _try_detach_xdp(self) -> None:
        try:
            subprocess.run(
                ["ip", "link", "set", "dev", self.interface, "xdp", "off"],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            pass

    async def _poll_loop(self) -> None:
        """Periodically read eBPF map and reinforce pheromones."""
        while self._running:
            await asyncio.sleep(self.poll_interval)
            if self._xdp_attached:
                self._process_ebpf_snapshot()

    def _process_ebpf_snapshot(self) -> None:
        """
        Read current eBPF map, compute deltas, and call reinforce() for
        each peer that sent packets since last poll.
        """
        current = _bpftool_dump_map(_PKT_MAP_NAME)
        if not current:
            return

        for ip_u32, count in current.items():
            prev = self._last_snapshot.get(ip_u32, 0)
            delta = count - prev
            if delta < MIN_DELTA_TO_REINFORCE:
                continue

            ip_str = _ip_u32_to_str(ip_u32)
            peer_id = self._ip_to_peer.get(ip_str)
            if peer_id is None:
                # Unknown peer — still record as IP string for visibility
                peer_id = f"ip:{ip_str}"

            # Treat packet activity from this peer as positive reinforcement
            # (they responded → their route is alive).
            # For direct neighbors: dest == next_hop == peer_id
            self.router.reinforce(peer_id, peer_id, success=True)
            logger.debug(
                "eBPF pheromone: peer=%s (+%d pkts, total=%d)",
                peer_id, delta, count,
            )

        self._last_snapshot = dict(current)

    def get_stats(self) -> dict:
        """Return bridge statistics for monitoring."""
        return {
            "ebpf_attached": self._xdp_attached,
            "interface": self.interface,
            "ebpf_peers_tracked": len(self._last_snapshot),
            "sim_acks": sum(self._sim_acks.values()),
            "sim_timeouts": sum(self._sim_timeouts.values()),
            "routing_table": self.router.get_routing_table_snapshot(),
        }
