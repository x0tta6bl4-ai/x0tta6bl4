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
import hashlib
import json
import logging
import socket
import struct
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.network.routing.stigmergy import StigmergyRouter
from src.services.service_event_identity import service_event_identity
from src.core.security.subprocess_validator import safe_run

logger = logging.getLogger(__name__)

STIGMERGY_BRIDGE_SERVICE_NAME = "ebpf-stigmergy-bridge"
STIGMERGY_BRIDGE_LAYER = "network_ebpf_stigmergy_observed_state"
STIGMERGY_BRIDGE_CLAIM_BOUNDARY = (
    "Local eBPF stigmergy bridge evidence only. Events record bpftool map-read, "
    "XDP attach/detach attempt, and router reinforcement outcomes with duration, "
    "return code, bounded output hashes, and redacted selectors; they do not prove "
    "production traffic, remote peer liveness, route quality, or attached kernel "
    "program correctness."
)

# BPF filesystem pin path — must match LIBBPF_PIN_BY_NAME in the .bpf.c
_BPF_PIN_DIR = Path("/sys/fs/bpf")
_PKT_MAP_NAME = "stigmergy_pkt_count"
_BYTE_MAP_NAME = "stigmergy_byte_count"

# Polling interval: read eBPF map every N seconds
DEFAULT_POLL_INTERVAL = 2.0

# Minimum packet delta to trigger a reinforce (avoids noise from single stray pkts)
MIN_DELTA_TO_REINFORCE = 3

_MODULE_THINKING_COACH: Optional[AgentThinkingCoach] = None
_MODULE_LAST_THINKING_CONTEXT: Optional[Dict[str, Any]] = None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _sha256_text(str(value))


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=STIGMERGY_BRIDGE_SERVICE_NAME)
    return {
        "service_name": STIGMERGY_BRIDGE_SERVICE_NAME,
        "layer": STIGMERGY_BRIDGE_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _bounded_output_metadata(
    stdout: Optional[Any],
    stderr: Optional[Any],
) -> Dict[str, Any]:
    safe_stdout = _normalize_text(stdout)
    safe_stderr = _normalize_text(stderr)
    return {
        "stdout_chars": len(safe_stdout),
        "stderr_chars": len(safe_stderr),
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "output_bounded": True,
        "output_redacted": True,
    }


def _build_thinking_coach(agent_id: str) -> AgentThinkingCoach:
    return AgentThinkingCoach(
        agent_id=agent_id,
        role="coordinator",
        capabilities=("monitoring", "security", "zero-trust"),
        extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
    )


def _module_thinking_coach_or_create() -> AgentThinkingCoach:
    global _MODULE_THINKING_COACH
    if _MODULE_THINKING_COACH is None:
        _MODULE_THINKING_COACH = _build_thinking_coach(STIGMERGY_BRIDGE_SERVICE_NAME)
    return _MODULE_THINKING_COACH


def _record_stigmergy_thinking_context(
    *,
    coach: AgentThinkingCoach,
    operation: str,
    goal: str,
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    safe_task = {
        "task_type": "ebpf_stigmergy_bridge_operation",
        "goal": goal,
        "constraints": {
            "operation": operation,
            "redacted": True,
            **constraints,
        },
        "safety_boundary": (
            "Record only local eBPF stigmergy bridge evidence, redacted command "
            "shapes, hashed map/interface/peer selectors, counts, and status; do "
            "not expose raw map names, IP addresses, peer IDs, route IDs, stdout, "
            "stderr, or eBPF object paths."
        ),
    }
    return coach.prepare_task(safe_task)


def _record_module_thinking_context(
    *,
    operation: str,
    goal: str,
    constraints: Dict[str, Any],
) -> Dict[str, Any]:
    global _MODULE_LAST_THINKING_CONTEXT
    _MODULE_LAST_THINKING_CONTEXT = _record_stigmergy_thinking_context(
        coach=_module_thinking_coach_or_create(),
        operation=operation,
        goal=goal,
        constraints=constraints,
    )
    return _MODULE_LAST_THINKING_CONTEXT


def _event_bus_or_none(
    event_bus: Optional[EventBus],
    event_project_root: str,
) -> Optional[EventBus]:
    if event_bus is not None:
        return event_bus
    try:
        return EventBus(project_root=event_project_root)
    except Exception as exc:
        logger.error("Failed to initialize StigmergyBridge EventBus: %s", exc)
        return None


def _redacted_command(command: List[Any], redacted_indices: Tuple[int, ...]) -> List[str]:
    redacted = set(redacted_indices)
    safe_command: List[str] = []
    for index, item in enumerate(command):
        if index == 0:
            safe_command.append(Path(str(item)).name)
        elif index in redacted:
            safe_command.append("[redacted]")
        else:
            safe_command.append(str(item))
    return safe_command


def _publish_stigmergy_observation(
    *,
    event_bus: Optional[EventBus],
    event_project_root: str,
    stage: str,
    operation: str,
    status: str,
    source_mode: str,
    start: float,
    returncode: Optional[int] = None,
    stdout: Optional[Any] = None,
    stderr: Optional[Any] = None,
    command: Optional[List[str]] = None,
    read_only: bool = True,
    parsed_summary: Optional[Dict[str, Any]] = None,
    error: Optional[BaseException] = None,
    extra: Optional[Dict[str, Any]] = None,
    thinking: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    if thinking is None:
        thinking = _record_module_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "command_present": bool(command),
                "command_length": len(command or []),
                "command_redacted": bool(command),
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
                "output_redacted": True,
            },
        )
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    payload: Dict[str, Any] = {
        "component": "network.ebpf.stigmergy_bridge",
        "stage": stage,
        "operation": operation,
        "operation_resource": f"network:ebpf:stigmergy_bridge:{operation}",
        "service_name": STIGMERGY_BRIDGE_SERVICE_NAME,
        "layer": STIGMERGY_BRIDGE_LAYER,
        "identity": _identity_metadata(),
        "status": status,
        "source_mode": source_mode,
        "returncode": returncode,
        "duration_ms": round((time.monotonic() - start) * 1000, 3),
        "command": command or [],
        "read_only": read_only,
        "observed_state": True,
        "safe_actuator": False,
        "safe_observation": True,
        "parsed_summary": parsed_summary or {},
        "output": _bounded_output_metadata(stdout, stderr),
        "thinking": thinking,
        "payloads_redacted": True,
        "claim_boundary": STIGMERGY_BRIDGE_CLAIM_BOUNDARY,
    }
    if error is not None:
        payload["error"] = {
            "type": type(error).__name__,
            "message_hash": _hash_value(str(error)),
            "message_redacted": True,
        }
    if extra:
        payload.update(extra)

    try:
        event = bus.publish(
            EventType.PIPELINE_STAGE_END,
            STIGMERGY_BRIDGE_SERVICE_NAME,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish StigmergyBridge observation: %s", exc)
        return None


def _ip_u32_to_str(u32_val: int) -> str:
    """Convert a big-endian u32 IP (as read from BPF map) to dotted-quad string."""
    return socket.inet_ntoa(struct.pack(">I", u32_val))


def _bpftool_dump_map(
    map_name: str,
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
) -> Dict[int, int]:
    """
    Read an LRU_HASH BPF map via ``bpftool map dump name <name> --json``.

    Returns:
        Dict mapping src_ip_u32 -> counter_value.
        Empty dict if bpftool not available or map not found.
    """
    command = ["bpftool", "map", "dump", "name", map_name, "--json"]
    safe_command = _redacted_command(command, redacted_indices=(4,))
    start = time.monotonic()
    try:
        result = safe_run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            _publish_stigmergy_observation(
                event_bus=event_bus,
                event_project_root=event_project_root,
                stage="stigmergy_map_dump_failed",
                operation="bpftool_map_dump",
                status="failure",
                source_mode="bpftool",
                start=start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=safe_command,
                parsed_summary={"entries_total": 0, "counter_entries": 0},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                },
            )
            return {}

        entries = json.loads(result.stdout)
        if not isinstance(entries, list):
            _publish_stigmergy_observation(
                event_bus=event_bus,
                event_project_root=event_project_root,
                stage="stigmergy_map_dump_unexpected_shape",
                operation="bpftool_map_dump",
                status="empty",
                source_mode="bpftool",
                start=start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=safe_command,
                parsed_summary={"entries_total": 0, "counter_entries": 0},
                extra={
                    "map_name_hash": _hash_value(map_name),
                    "map_name_redacted": True,
                    "result_shape": type(entries).__name__,
                },
            )
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
        _publish_stigmergy_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            stage="stigmergy_map_dump_succeeded",
            operation="bpftool_map_dump",
            status="success",
            source_mode="bpftool",
            start=start,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=safe_command,
            parsed_summary={
                "entries_total": len(entries),
                "counter_entries": len(counts),
                "ignored_entries": max(0, len(entries) - len(counts)),
            },
            extra={
                "map_name_hash": _hash_value(map_name),
                "map_name_redacted": True,
            },
        )
        return counts

    except json.JSONDecodeError as exc:
        _publish_stigmergy_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            stage="stigmergy_map_dump_parse_failed",
            operation="bpftool_map_dump",
            status="failure",
            source_mode="bpftool",
            start=start,
            returncode=0,
            stdout=getattr(exc, "doc", None),
            stderr=None,
            command=safe_command,
            error=exc,
            parsed_summary={"entries_total": 0, "counter_entries": 0},
            extra={
                "map_name_hash": _hash_value(map_name),
                "map_name_redacted": True,
            },
        )
        return {}
    except FileNotFoundError as exc:
        _publish_stigmergy_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            stage="stigmergy_map_dump_unavailable",
            operation="bpftool_map_dump",
            status="failure",
            source_mode="bpftool",
            start=start,
            command=safe_command,
            error=exc,
            parsed_summary={"entries_total": 0, "counter_entries": 0},
            extra={
                "map_name_hash": _hash_value(map_name),
                "map_name_redacted": True,
            },
        )
        return {}
    except subprocess.TimeoutExpired as exc:
        _publish_stigmergy_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            stage="stigmergy_map_dump_timeout",
            operation="bpftool_map_dump",
            status="failure",
            source_mode="bpftool",
            start=start,
            stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
            stderr=getattr(exc, "stderr", None),
            command=safe_command,
            error=exc,
            parsed_summary={"entries_total": 0, "counter_entries": 0},
            extra={
                "map_name_hash": _hash_value(map_name),
                "map_name_redacted": True,
            },
        )
        return {}
    except Exception as exc:
        logger.debug("bpftool read error: %s", exc)
        _publish_stigmergy_observation(
            event_bus=event_bus,
            event_project_root=event_project_root,
            stage="stigmergy_map_dump_error",
            operation="bpftool_map_dump",
            status="failure",
            source_mode="bpftool",
            start=start,
            command=safe_command,
            error=exc,
            parsed_summary={"entries_total": 0, "counter_entries": 0},
            extra={
                "map_name_hash": _hash_value(map_name),
                "map_name_redacted": True,
            },
        )
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
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """
        Args:
            router:        The StigmergyRouter instance to feed reinforcement signals.
            interface:     Network interface to attach XDP program to (optional).
            poll_interval: Seconds between eBPF map reads.
            ebpf_object:   Path to compiled .bpf.o file (auto-detected if None).
            event_bus:     Optional EventBus for redacted evidence events.
        """
        self.router = router
        self.interface = interface
        self.poll_interval = poll_interval
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = STIGMERGY_BRIDGE_SERVICE_NAME
        self.thinking_coach = _build_thinking_coach(self.source_agent)
        self._last_thinking_context: Optional[Dict[str, Any]] = None

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

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = EventBus(project_root=self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize StigmergyBridge EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                STIGMERGY_BRIDGE_SERVICE_NAME,
            )
            coach = _build_thinking_coach(self.source_agent)
            self.thinking_coach = coach
        return coach

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        self._last_thinking_context = _record_stigmergy_thinking_context(
            coach=self._thinking_coach_or_create(),
            operation=operation,
            goal=goal,
            constraints=constraints,
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose stigmergy-bridge thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        returncode: Optional[int] = None,
        stdout: Optional[Any] = None,
        stderr: Optional[Any] = None,
        command: Optional[List[str]] = None,
        read_only: bool = True,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "returncode_present": returncode is not None,
                "command_present": bool(command),
                "command_length": len(command or []),
                "command_redacted": bool(command),
                "interface_hash": _hash_value(getattr(self, "interface", None)),
                "interface_redacted": getattr(self, "interface", None) is not None,
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
                "output_redacted": True,
            },
        )
        return _publish_stigmergy_observation(
            event_bus=self._event_bus_or_none(),
            event_project_root=self.event_project_root,
            stage=stage,
            operation=operation,
            status=status,
            source_mode=source_mode,
            start=start,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            command=command,
            read_only=read_only,
            parsed_summary=parsed_summary,
            error=error,
            extra=extra,
            thinking=thinking,
        )

    def _publish_reinforcement_observation(
        self,
        *,
        stage: str,
        source_mode: str,
        dest_id: str,
        next_hop: str,
        success: bool,
        delta_packets: Optional[int] = None,
        total_packets: Optional[int] = None,
        ip_address: Optional[str] = None,
        peer_known: Optional[bool] = None,
    ) -> Optional[str]:
        start = time.monotonic()
        return self._publish_observation(
            stage=stage,
            operation="router_reinforce",
            status="success",
            source_mode=source_mode,
            start=start,
            read_only=False,
            parsed_summary={
                "reinforcement_success": success,
                "delta_packets": delta_packets,
                "total_packets": total_packets,
                "peer_known": peer_known,
            },
            extra={
                "dest_id_hash": _hash_value(dest_id),
                "next_hop_hash": _hash_value(next_hop),
                "ip_address_hash": _hash_value(ip_address),
                "dest_id_redacted": True,
                "next_hop_redacted": True,
                "ip_address_redacted": ip_address is not None,
            },
        )

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
        self._publish_reinforcement_observation(
            stage="stigmergy_sim_ack_reinforced",
            source_mode="simulation_ack",
            dest_id=dest_id,
            next_hop=next_hop,
            success=True,
        )
        logger.debug("Stigmergy ACK: %s via %s", dest_id, next_hop)

    def record_timeout(self, dest_id: str, next_hop: str) -> None:
        """
        Record a route timeout (simulation mode).
        Punishes the route in the router.
        """
        self.router.reinforce(dest_id, next_hop, success=False)
        key = (dest_id, next_hop)
        self._sim_timeouts[key] = self._sim_timeouts.get(key, 0) + 1
        self._publish_reinforcement_observation(
            stage="stigmergy_sim_timeout_reinforced",
            source_mode="simulation_timeout",
            dest_id=dest_id,
            next_hop=next_hop,
            success=False,
        )
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
        start = time.monotonic()
        cmd = [
            "ip",
            "link",
            "set",
            "dev",
            self.interface,
            "xdp",
            "obj",
            str(self.ebpf_object),
            "sec",
            "xdp",
        ]
        safe_command = _redacted_command(cmd, redacted_indices=(4, 7))
        try:
            result = safe_run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self._publish_observation(
                    stage="stigmergy_xdp_attach_succeeded",
                    operation="xdp_attach",
                    status="success",
                    source_mode="ip_link",
                    start=start,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=safe_command,
                    read_only=False,
                    parsed_summary={"xdp_attached": True},
                    extra={
                        "interface_hash": _hash_value(self.interface),
                        "ebpf_object_hash": _hash_value(self.ebpf_object),
                        "interface_redacted": self.interface is not None,
                        "ebpf_object_redacted": self.ebpf_object is not None,
                    },
                )
                logger.info("XDP stigmergy counter attached to %s", self.interface)
                return True
            self._publish_observation(
                stage="stigmergy_xdp_attach_failed",
                operation="xdp_attach",
                status="failure",
                source_mode="ip_link",
                start=start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=safe_command,
                read_only=False,
                parsed_summary={"xdp_attached": False},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "ebpf_object_hash": _hash_value(self.ebpf_object),
                    "interface_redacted": self.interface is not None,
                    "ebpf_object_redacted": self.ebpf_object is not None,
                },
            )
            logger.warning(
                "Failed to attach XDP to %s (need root): %s",
                self.interface,
                result.stderr.strip(),
            )
        except Exception as exc:
            self._publish_observation(
                stage="stigmergy_xdp_attach_error",
                operation="xdp_attach",
                status="failure",
                source_mode="ip_link",
                start=start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=safe_command,
                read_only=False,
                parsed_summary={"xdp_attached": False},
                error=exc,
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "ebpf_object_hash": _hash_value(self.ebpf_object),
                    "interface_redacted": self.interface is not None,
                    "ebpf_object_redacted": self.ebpf_object is not None,
                },
            )
            logger.warning("XDP attach error: %s", exc)
        return False

    def _try_detach_xdp(self) -> None:
        start = time.monotonic()
        cmd = ["ip", "link", "set", "dev", self.interface, "xdp", "off"]
        safe_command = _redacted_command(cmd, redacted_indices=(4,))
        try:
            result = safe_run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            status = "success" if result.returncode == 0 else "failure"
            stage = (
                "stigmergy_xdp_detach_succeeded"
                if result.returncode == 0
                else "stigmergy_xdp_detach_failed"
            )
            self._publish_observation(
                stage=stage,
                operation="xdp_detach",
                status=status,
                source_mode="ip_link",
                start=start,
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                command=safe_command,
                read_only=False,
                parsed_summary={"xdp_detached": result.returncode == 0},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "interface_redacted": self.interface is not None,
                },
            )
        except Exception as exc:
            self._publish_observation(
                stage="stigmergy_xdp_detach_error",
                operation="xdp_detach",
                status="failure",
                source_mode="ip_link",
                start=start,
                stdout=getattr(exc, "stdout", None) or getattr(exc, "output", None),
                stderr=getattr(exc, "stderr", None),
                command=safe_command,
                read_only=False,
                parsed_summary={"xdp_detached": False},
                error=exc,
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "interface_redacted": self.interface is not None,
                },
            )

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
        current = _bpftool_dump_map(
            _PKT_MAP_NAME,
            event_bus=self._event_bus_or_none(),
            event_project_root=self.event_project_root,
        )
        if not current:
            return

        for ip_u32, count in current.items():
            prev = self._last_snapshot.get(ip_u32, 0)
            delta = count - prev
            if delta < MIN_DELTA_TO_REINFORCE:
                continue

            ip_str = _ip_u32_to_str(ip_u32)
            peer_id = self._ip_to_peer.get(ip_str)
            peer_known = peer_id is not None
            if peer_id is None:
                # Unknown peer — still record as IP string for visibility
                peer_id = f"ip:{ip_str}"

            # Treat packet activity from this peer as positive reinforcement
            # (they responded → their route is alive).
            # For direct neighbors: dest == next_hop == peer_id
            self.router.reinforce(peer_id, peer_id, success=True)
            self._publish_reinforcement_observation(
                stage="stigmergy_ebpf_delta_reinforced",
                source_mode="ebpf_snapshot",
                dest_id=peer_id,
                next_hop=peer_id,
                success=True,
                delta_packets=delta,
                total_packets=count,
                ip_address=ip_str,
                peer_known=peer_known,
            )
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
