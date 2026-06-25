"""
eBPF Loader for Stigmergy Routing.
Manages the lifecycle of the BPF program and performs 'pheromone evaporation'.
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.core.thinking.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

try:
    from bcc import BPF

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    BPF = None  # type: ignore

logger = logging.getLogger(__name__)


EBPF_STIGMERGY_LOADER_SERVICE_NAME = "ebpf-stigmergy-loader"
EBPF_STIGMERGY_LOADER_LAYER = "network_ebpf_stigmergy_loader_observed_state"
EBPF_STIGMERGY_LOADER_CLAIM_BOUNDARY = (
    "Local eBPF stigmergy loader evidence only. Events record BCC compile/load/"
    "attach attempts, XDP detach attempts, routing-score map evaporation mutations, "
    "and stats reads with duration, bounded metadata, and hashed selectors; they "
    "do not prove production traffic, route quality, remote peer identity, or "
    "kernel datapath enforcement beyond the local userspace operation result."
)


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
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return _sha256_text(str(value))


def _bounded_output_metadata(
    stdout: Optional[Any] = None,
    stderr: Optional[Any] = None,
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


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_STIGMERGY_LOADER_SERVICE_NAME)
    return {
        "service_name": EBPF_STIGMERGY_LOADER_SERVICE_NAME,
        "layer": EBPF_STIGMERGY_LOADER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _map_key_value(key: Any) -> Any:
    return getattr(key, "value", key)


def _bounded_hashes(values: List[Any], limit: int = 20) -> Dict[str, Any]:
    selected = values[:limit]
    return {
        "hashes": [_hash_value(_map_key_value(value)) for value in selected],
        "count": len(values),
        "limit": limit,
        "truncated": len(values) > limit,
    }


class StigmergyBPF:
    def __init__(
        self,
        interface: str = "eth0",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.interface = interface
        self.bpf = None
        self.running = False
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_STIGMERGY_LOADER_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="monitoring",
            capabilities=("security", "zero-trust", "healing"),
            extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize eBPF stigmergy loader EventBus: %s", exc)
            return None

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                EBPF_STIGMERGY_LOADER_SERVICE_NAME,
            )
            coach = AgentThinkingCoach(
                agent_id=self.source_agent,
                role="monitoring",
                capabilities=("security", "zero-trust", "healing"),
                extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
            )
            self.thinking_coach = coach
        return coach

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_stigmergy_loader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local eBPF stigmergy loader evidence, hashed "
                "interface/program/map selectors, counts, and status; do not "
                "expose raw interface names, program paths, function names, "
                "route IPs, map names, map keys, or map values."
            ),
        }
        self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
            safe_task
        )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose stigmergy-loader thinking state without task secrets."""

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
        read_only: bool = True,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(
            self, "source_agent", EBPF_STIGMERGY_LOADER_SERVICE_NAME
        )
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": read_only,
                "interface_hash": _hash_value(getattr(self, "interface", None)),
                "interface_redacted": True,
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.stigmergy_loader",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:stigmergy_loader:{operation}",
            "service_name": source_agent,
            "layer": EBPF_STIGMERGY_LOADER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "thinking": thinking,
            "output": _bounded_output_metadata(),
            "payloads_redacted": True,
            "claim_boundary": EBPF_STIGMERGY_LOADER_CLAIM_BOUNDARY,
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
                source_agent,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish eBPF stigmergy loader observation")
            return None

    def load(self):
        """Compile and load BPF program."""
        op_start = time.monotonic()
        src_path = os.path.join(os.path.dirname(__file__), "kernel", "stigmergy_kern.c")

        if not BCC_AVAILABLE or BPF is None:
            self._publish_observation(
                stage="stigmergy_bcc_unavailable",
                operation="load",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"bcc_available": False, "loaded": False},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "program_path_hash": _hash_value(src_path),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                },
            )
            raise RuntimeError("BCC required for eBPF stigmergy loader")

        # BCC compiles C code on the fly
        # We need to adapt the C code slightly for BCC syntax if not using libbpf
        # Or we can write inline C for BCC.
        # Let's use BCC's BPF() wrapper which handles most things.
        # Note: raw XDP code often needs slight tweaks for BCC vs libbpf.
        # Here we assume we can load the source file.

        try:
            self.bpf = BPF(src_file=src_path)
            fn = self.bpf.load_func("xdp_prog", BPF.XDP)
            self.bpf.attach_xdp(self.interface, fn, 0)
            logger.info("eBPF stigmergy loader attached to redacted interface")
            self.running = True
            self._publish_observation(
                stage="stigmergy_xdp_attach_succeeded",
                operation="load",
                status="success",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"loaded": True, "attached": True, "xdp_flags": 0},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "program_path_hash": _hash_value(src_path),
                    "function_name_hash": _hash_value("xdp_prog"),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                    "function_name_redacted": True,
                },
            )
        except Exception as e:
            self.running = False
            self._publish_observation(
                stage="stigmergy_xdp_attach_failed",
                operation="load",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"loaded": False, "attached": False},
                error=e,
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "program_path_hash": _hash_value(src_path),
                    "function_name_hash": _hash_value("xdp_prog"),
                    "interface_redacted": True,
                    "program_path_redacted": True,
                    "function_name_redacted": True,
                },
            )
            logger.error("Failed to load eBPF stigmergy program: %s", type(e).__name__)
            raise

    def unload(self):
        op_start = time.monotonic()
        if self.bpf:
            try:
                self.bpf.remove_xdp(self.interface, 0)
                self.running = False
                self._publish_observation(
                    stage="stigmergy_xdp_detach_succeeded",
                    operation="unload",
                    status="success",
                    source_mode="bcc",
                    start=op_start,
                    read_only=False,
                    parsed_summary={"unloaded": True, "xdp_removed": True},
                    extra={
                        "interface_hash": _hash_value(self.interface),
                        "interface_redacted": True,
                    },
                )
                logger.info("eBPF stigmergy loader detached from redacted interface")
            except Exception as exc:
                self._publish_observation(
                    stage="stigmergy_xdp_detach_failed",
                    operation="unload",
                    status="failure",
                    source_mode="bcc",
                    start=op_start,
                    read_only=False,
                    parsed_summary={"unloaded": False, "xdp_removed": False},
                    error=exc,
                    extra={
                        "interface_hash": _hash_value(self.interface),
                        "interface_redacted": True,
                    },
                )
                logger.error("Failed to detach eBPF stigmergy loader")
                raise
            return

        self.running = False
        self._publish_observation(
            stage="stigmergy_unload_skipped_no_bpf",
            operation="unload",
            status="success",
            source_mode="memory",
            start=op_start,
            parsed_summary={"unloaded": False, "reason": "bpf_uninitialized"},
        )

    async def evaporation_loop(self):
        """
        Periodically decay scores in the BPF map.
        Accessing BPF maps from user space is fast.
        """
        if not self.bpf:
            self._publish_observation(
                stage="stigmergy_evaporation_skipped_no_bpf",
                operation="evaporation_loop",
                status="success",
                source_mode="memory",
                start=time.monotonic(),
                parsed_summary={"evaporated": False, "reason": "bpf_uninitialized"},
            )
            return

        map_start = time.monotonic()
        try:
            pheromone_map = self.bpf.get_table("pheromone_map")
            self._publish_observation(
                stage="stigmergy_pheromone_map_opened",
                operation="evaporation_loop",
                status="success",
                source_mode="bcc-map",
                start=map_start,
                parsed_summary={"map_opened": True},
                extra={
                    "map_name_hash": _hash_value("pheromone_map"),
                    "map_name_redacted": True,
                },
            )
        except Exception as exc:
            self._publish_observation(
                stage="stigmergy_pheromone_map_open_failed",
                operation="evaporation_loop",
                status="failure",
                source_mode="bcc-map",
                start=map_start,
                error=exc,
                parsed_summary={"map_opened": False},
                extra={
                    "map_name_hash": _hash_value("pheromone_map"),
                    "map_name_redacted": True,
                },
            )
            raise

        while self.running:
            await asyncio.sleep(1.0) # 1 second tick

            # Iterate and decay
            # Note: Modifying map while iterating can be tricky in BPF,
            # but from userspace it's generally safe-ish for updates.
            # We treat keys as read-only, update values.
            tick_start = time.monotonic()
            scanned_keys: List[Any] = []
            updated_keys: List[Any] = []
            deleted_keys: List[Any] = []
            delete_failed_keys: List[Any] = []
            score_min: Optional[int] = None
            score_max: Optional[int] = None
            try:
                for key, leaf in pheromone_map.items():
                    scanned_keys.append(key)
                    current_score = int(leaf.value)
                    score_min = (
                        current_score
                        if score_min is None
                        else min(score_min, current_score)
                    )
                    score_max = (
                        current_score
                        if score_max is None
                        else max(score_max, current_score)
                    )
                    new_score = int(current_score * 0.9) # 10% decay

                    if new_score < 5:
                        # Prune dead paths to save map space
                        try:
                            del pheromone_map[key]
                            deleted_keys.append(key)
                        except Exception:
                            delete_failed_keys.append(key)
                    else:
                        pheromone_map[key] = new_score
                        updated_keys.append(key)

                self._publish_observation(
                    stage="stigmergy_evaporation_tick_succeeded",
                    operation="evaporation_loop",
                    status="success",
                    source_mode="bcc-map",
                    start=tick_start,
                    read_only=False,
                    parsed_summary={
                        "scanned_count": len(scanned_keys),
                        "updated_count": len(updated_keys),
                        "deleted_count": len(deleted_keys),
                        "delete_failed_count": len(delete_failed_keys),
                        "score_min": score_min,
                        "score_max": score_max,
                    },
                    extra={
                        "map_name_hash": _hash_value("pheromone_map"),
                        "scanned_key_hashes": _bounded_hashes(scanned_keys),
                        "updated_key_hashes": _bounded_hashes(updated_keys),
                        "deleted_key_hashes": _bounded_hashes(deleted_keys),
                        "delete_failed_key_hashes": _bounded_hashes(
                            delete_failed_keys
                        ),
                        "map_name_redacted": True,
                        "map_keys_redacted": True,
                    },
                )
            except Exception as exc:
                self._publish_observation(
                    stage="stigmergy_evaporation_tick_failed",
                    operation="evaporation_loop",
                    status="failure",
                    source_mode="bcc-map",
                    start=tick_start,
                    read_only=False,
                    error=exc,
                    parsed_summary={
                        "scanned_count": len(scanned_keys),
                        "updated_count": len(updated_keys),
                        "deleted_count": len(deleted_keys),
                    },
                    extra={
                        "map_name_hash": _hash_value("pheromone_map"),
                        "scanned_key_hashes": _bounded_hashes(scanned_keys),
                        "map_name_redacted": True,
                        "map_keys_redacted": True,
                    },
                )
                raise

    def get_stats(self):
        """Return current pheromone map for visualization."""
        op_start = time.monotonic()
        if not self.bpf:
            self._publish_observation(
                stage="stigmergy_stats_no_bpf",
                operation="get_stats",
                status="success",
                source_mode="memory",
                start=op_start,
                parsed_summary={"stats_returned": False, "reason": "bpf_uninitialized"},
            )
            return {}

        stats = {}
        keys: List[Any] = []
        scores: List[int] = []
        try:
            pheromone_map = self.bpf.get_table("pheromone_map")
            for k, v in pheromone_map.items():
                keys.append(k)
                score = int(v.value)
                scores.append(score)
                # Convert u32 IP to string
                ip = self._int_to_ip(k.value)
                stats[ip] = score
            self._publish_observation(
                stage="stigmergy_stats_read",
                operation="get_stats",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                parsed_summary={
                    "stats_returned": True,
                    "route_count": len(stats),
                    "score_min": min(scores) if scores else None,
                    "score_max": max(scores) if scores else None,
                },
                extra={
                    "map_name_hash": _hash_value("pheromone_map"),
                    "route_key_hashes": _bounded_hashes(keys),
                    "map_name_redacted": True,
                    "route_ips_redacted": True,
                },
            )
        except Exception as exc:
            self._publish_observation(
                stage="stigmergy_stats_read_failed",
                operation="get_stats",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                error=exc,
                parsed_summary={"stats_returned": False},
                extra={
                    "map_name_hash": _hash_value("pheromone_map"),
                    "route_key_hashes": _bounded_hashes(keys),
                    "map_name_redacted": True,
                    "route_ips_redacted": True,
                },
            )
            raise
        return stats

    def _int_to_ip(self, ip_int):
        import socket
        import struct
        return socket.inet_ntoa(struct.pack("!I", ip_int))
