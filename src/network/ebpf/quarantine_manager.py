#!/usr/bin/env python3
"""Zero-Trust quarantine manager for PQC verification failures."""

from __future__ import annotations

import ctypes
import hashlib
import logging
import os
import socket
import struct
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

PQC_QUARANTINE_MANAGER_SERVICE_NAME = "pqc-quarantine-manager"
PQC_QUARANTINE_MANAGER_LAYER = "network_ebpf_pqc_quarantine_observed_state"
PQC_QUARANTINE_MANAGER_CLAIM_BOUNDARY = (
    "Local PQC quarantine manager evidence only. Events record BCC/XDP attach "
    "attempts, software fallback transitions, blocked_ips map mutations, "
    "verification-failure counters, stats reads, and cleanup outcomes with "
    "hashed peer/IP/interface selectors; they do not prove remote peer identity, "
    "production traffic, or kernel datapath enforcement beyond the local "
    "userspace operation result."
)

try:
    from prometheus_client import Counter

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Counter = None  # type: ignore

try:
    from bcc import BPF

    BCC_AVAILABLE = True
except ImportError:
    BCC_AVAILABLE = False
    BPF = None  # type: ignore


class _NoopCounter:
    """Fallback counter when prometheus_client is unavailable."""

    def inc(self, amount: float = 1.0) -> None:
        return


def _build_counter(name: str, description: str):
    if not PROMETHEUS_AVAILABLE or Counter is None:
        return _NoopCounter()
    try:
        return Counter(name, description)
    except Exception as exc:
        logger.debug("Prometheus counter %s unavailable: %s", name, exc)
        return _NoopCounter()


PQC_EBPF_VERIFICATION_FAILURES_TOTAL = _build_counter(
    "pqc_ebpf_verification_failures_total",
    "Total failed PQC verification events observed by quarantine manager",
)
PQC_EBPF_QUARANTINE_ACTIONS_TOTAL = _build_counter(
    "pqc_ebpf_quarantine_actions_total",
    "Total quarantine actions triggered by failed PQC verification",
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
    identity = service_event_identity(service_name=PQC_QUARANTINE_MANAGER_SERVICE_NAME)
    return {
        "service_name": PQC_QUARANTINE_MANAGER_SERVICE_NAME,
        "layer": PQC_QUARANTINE_MANAGER_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _hash_keys(values: List[Any]) -> List[Optional[str]]:
    return [_hash_value(value) for value in values]


DEFAULT_QUARANTINE_BPF_PROGRAM = r"""
#include <uapi/linux/bpf.h>
#include <uapi/linux/if_ether.h>
#include <uapi/linux/ip.h>

BPF_HASH(blocked_ips, u32, u32, 1024);

int x0t_quarantine_filter(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end) return XDP_PASS;
    if (eth->h_proto != __constant_htons(ETH_P_IP)) return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end) return XDP_PASS;

    u32 src = ip->saddr;
    u32 dst = ip->daddr;
    u32 *src_level = blocked_ips.lookup(&src);
    u32 *dst_level = blocked_ips.lookup(&dst);

    if ((src_level && *src_level >= 2) || (dst_level && *dst_level >= 2)) {
        return XDP_DROP;
    }
    return XDP_PASS;
}
"""


class QuarantineManager:
    """
    Manages Zero-Trust quarantine with eBPF XDP and software fallback.

    Key behavior for P1:
    - Tracks failed PQC verification events per peer.
    - Automatically quarantines offending IP after configurable threshold.
    """

    def __init__(
        self,
        interface: str = "eth0",
        failure_threshold: int = 3,
        bpf_program_path: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.interface = interface
        self.failure_threshold = max(1, int(failure_threshold))
        self.bpf = None
        self.fn = None
        self._using_software_fallback = False
        self._blocked_ips: Dict[str, int] = {}
        self._verification_failures: Dict[str, int] = {}
        self._bpf_program_path = bpf_program_path
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = PQC_QUARANTINE_MANAGER_SERVICE_NAME

        self._init_ebpf_or_fallback()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        event_bus = getattr(self, "event_bus", None)
        if event_bus is not None:
            return event_bus
        try:
            event_bus = EventBus(project_root=getattr(self, "event_project_root", "."))
            self.event_bus = event_bus
            return event_bus
        except Exception as exc:
            logger.error("Failed to initialize PQC quarantine EventBus: %s", exc)
            return None

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
            self, "source_agent", PQC_QUARANTINE_MANAGER_SERVICE_NAME
        )
        payload: Dict[str, Any] = {
            "component": "network.ebpf.quarantine_manager",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:pqc_quarantine:{operation}",
            "service_name": source_agent,
            "layer": PQC_QUARANTINE_MANAGER_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": read_only,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "parsed_summary": parsed_summary or {},
            "output": _bounded_output_metadata(),
            "payloads_redacted": True,
            "claim_boundary": PQC_QUARANTINE_MANAGER_CLAIM_BOUNDARY,
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
            logger.exception("Failed to publish PQC quarantine observation")
            return None

    @property
    def is_using_software_fallback(self) -> bool:
        return self._using_software_fallback

    def _init_ebpf_or_fallback(self) -> None:
        op_start = time.monotonic()
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, using software quarantine fallback")
            self._publish_observation(
                stage="quarantine_bcc_unavailable",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="bcc",
                start=op_start,
                parsed_summary={"bcc_available": False, "fallback": True},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="bcc_unavailable")
            return

        if os.geteuid() != 0:
            logger.warning("Not running as root, using software quarantine fallback")
            self._publish_observation(
                stage="quarantine_root_required",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="process",
                start=op_start,
                parsed_summary={"root_required": True, "fallback": True},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="not_root")
            return

        try:
            program_text = self._load_program_text()
            self.bpf = BPF(text=program_text)
            self.fn = self.bpf.load_func("x0t_quarantine_filter", BPF.XDP)
            self.bpf.attach_xdp(self.interface, self.fn, 0)
            logger.info("Zero-Trust XDP quarantine attached to %s", self.interface)
            self._publish_observation(
                stage="quarantine_xdp_attach_succeeded",
                operation="init_ebpf_or_fallback",
                status="success",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                parsed_summary={"attached": True, "fallback": False, "xdp_flags": 0},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "program_text_chars": len(program_text),
                    "program_text_sha256": _hash_value(program_text),
                    "function_name_hash": _hash_value("x0t_quarantine_filter"),
                    "interface_redacted": True,
                    "function_name_redacted": True,
                },
            )
        except Exception as exc:
            logger.warning(
                "Failed to initialize XDP quarantine, using software fallback: %s", exc
            )
            self._publish_observation(
                stage="quarantine_xdp_attach_failed",
                operation="init_ebpf_or_fallback",
                status="failure",
                source_mode="bcc",
                start=op_start,
                read_only=False,
                error=exc,
                parsed_summary={"attached": False, "fallback": True},
                extra={
                    "interface_hash": _hash_value(self.interface),
                    "interface_redacted": True,
                },
            )
            self._enable_software_fallback(reason="xdp_attach_failed")

    def _load_program_text(self) -> str:
        op_start = time.monotonic()
        path_candidates = []
        if self._bpf_program_path:
            path_candidates.append(Path(self._bpf_program_path))
        path_candidates.append(Path("src/network/ebpf/kernel/node_quarantine.c"))

        for candidate in path_candidates:
            if candidate.exists():
                program_text = candidate.read_text()
                self._publish_observation(
                    stage="quarantine_program_text_loaded",
                    operation="load_program_text",
                    status="success",
                    source_mode="filesystem",
                    start=op_start,
                    parsed_summary={"program_source": "file"},
                    extra={
                        "program_path_hash": _hash_value(candidate),
                        "program_text_chars": len(program_text),
                        "program_text_sha256": _hash_value(program_text),
                        "candidate_count": len(path_candidates),
                        "program_path_redacted": True,
                    },
                )
                return program_text
        self._publish_observation(
            stage="quarantine_program_text_defaulted",
            operation="load_program_text",
            status="success",
            source_mode="embedded-default",
            start=op_start,
            parsed_summary={"program_source": "embedded_default"},
            extra={
                "candidate_path_hashes": _hash_keys(path_candidates),
                "candidate_count": len(path_candidates),
                "program_text_chars": len(DEFAULT_QUARANTINE_BPF_PROGRAM),
                "program_text_sha256": _hash_value(DEFAULT_QUARANTINE_BPF_PROGRAM),
                "program_paths_redacted": True,
            },
        )
        return DEFAULT_QUARANTINE_BPF_PROGRAM

    def _enable_software_fallback(self, reason: str = "unspecified") -> None:
        op_start = time.monotonic()
        self._using_software_fallback = True
        self.bpf = None
        self.fn = None
        self._publish_observation(
            stage="quarantine_software_fallback_enabled",
            operation="enable_software_fallback",
            status="success",
            source_mode="software",
            start=op_start,
            read_only=False,
            parsed_summary={"fallback": True, "reason": reason},
            extra={
                "interface_hash": _hash_value(self.interface),
                "interface_redacted": True,
            },
        )
        logger.info("Software quarantine fallback enabled")

    def _ip_to_u32(self, ip_str: str) -> int:
        """Convert IP string to network byte order u32."""
        return struct.unpack("I", socket.inet_aton(ip_str))[0]

    def block_node(self, ip_address: str, level: int = 2) -> None:
        """
        Add node to quarantine.
        Levels: 2 = quarantine (drop), 3 = hard block.
        """
        op_start = time.monotonic()
        metadata = {
            "ip_address_hash": _hash_value(ip_address),
            "ip_address_redacted": True,
            "level": int(level),
            "interface_hash": _hash_value(self.interface),
            "interface_redacted": True,
        }
        try:
            # Validate early for both eBPF and fallback paths.
            ip_u32 = self._ip_to_u32(ip_address)
        except Exception as exc:
            logger.error("Invalid redacted IP for quarantine: %s", type(exc).__name__)
            self._publish_observation(
                stage="quarantine_block_invalid_ip",
                operation="block_node",
                status="failure",
                source_mode="validation",
                start=op_start,
                read_only=False,
                error=exc,
                parsed_summary={"blocked": False, "reason": "invalid_ip"},
                extra=metadata,
            )
            return
        metadata["ip_u32_hash"] = _hash_value(ip_u32)

        if self._using_software_fallback or not self.bpf:
            self._blocked_ips[ip_address] = int(level)
            PQC_EBPF_QUARANTINE_ACTIONS_TOTAL.inc()
            self._publish_observation(
                stage="quarantine_block_software_succeeded",
                operation="block_node",
                status="success",
                source_mode="software",
                start=op_start,
                read_only=False,
                parsed_summary={"blocked": True, "mode": "software"},
                extra={
                    **metadata,
                    "blocked_ips_count": len(self._blocked_ips),
                },
            )
            logger.warning("Redacted node quarantined in software mode (level=%d)", level)
            return

        try:
            self.bpf["blocked_ips"][ctypes.c_uint32(ip_u32)] = ctypes.c_uint32(level)
            self._blocked_ips[ip_address] = int(level)
            PQC_EBPF_QUARANTINE_ACTIONS_TOTAL.inc()
            self._publish_observation(
                stage="quarantine_block_xdp_succeeded",
                operation="block_node",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={"blocked": True, "mode": "ebpf"},
                extra={
                    **metadata,
                    "map_name_hash": _hash_value("blocked_ips"),
                    "map_name_redacted": True,
                    "blocked_ips_count": len(self._blocked_ips),
                },
            )
            logger.warning("Redacted node quarantined via XDP (level=%d)", level)
        except Exception as exc:
            self._publish_observation(
                stage="quarantine_block_xdp_failed",
                operation="block_node",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                error=exc,
                parsed_summary={"blocked": False, "mode": "ebpf"},
                extra={
                    **metadata,
                    "map_name_hash": _hash_value("blocked_ips"),
                    "map_name_redacted": True,
                },
            )
            logger.error("Failed to block redacted IP: %s", type(exc).__name__)

    def unblock_node(self, ip_address: str) -> None:
        """Remove node from quarantine."""
        op_start = time.monotonic()
        metadata = {
            "ip_address_hash": _hash_value(ip_address),
            "ip_address_redacted": True,
            "interface_hash": _hash_value(self.interface),
            "interface_redacted": True,
        }
        was_tracked = ip_address in self._blocked_ips
        self._blocked_ips.pop(ip_address, None)

        if self._using_software_fallback or not self.bpf:
            self._publish_observation(
                stage="quarantine_unblock_software_succeeded",
                operation="unblock_node",
                status="success",
                source_mode="software",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "unblocked": True,
                    "mode": "software",
                    "was_tracked": was_tracked,
                },
                extra={
                    **metadata,
                    "blocked_ips_count": len(self._blocked_ips),
                },
            )
            logger.info("Redacted node released from software quarantine")
            return

        try:
            ip_u32 = self._ip_to_u32(ip_address)
            del self.bpf["blocked_ips"][ctypes.c_uint32(ip_u32)]
            self._publish_observation(
                stage="quarantine_unblock_xdp_succeeded",
                operation="unblock_node",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "unblocked": True,
                    "mode": "ebpf",
                    "was_tracked": was_tracked,
                },
                extra={
                    **metadata,
                    "ip_u32_hash": _hash_value(ip_u32),
                    "map_name_hash": _hash_value("blocked_ips"),
                    "map_name_redacted": True,
                    "blocked_ips_count": len(self._blocked_ips),
                },
            )
            logger.info("Redacted node released from XDP quarantine")
        except KeyError:
            self._publish_observation(
                stage="quarantine_unblock_xdp_key_missing",
                operation="unblock_node",
                status="success",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "unblocked": False,
                    "reason": "key_missing",
                    "was_tracked": was_tracked,
                },
                extra={
                    **metadata,
                    "map_name_hash": _hash_value("blocked_ips"),
                    "map_name_redacted": True,
                    "blocked_ips_count": len(self._blocked_ips),
                },
            )
            return
        except Exception as exc:
            self._publish_observation(
                stage="quarantine_unblock_xdp_failed",
                operation="unblock_node",
                status="failure",
                source_mode="bcc-map",
                start=op_start,
                read_only=False,
                error=exc,
                parsed_summary={"unblocked": False, "was_tracked": was_tracked},
                extra={
                    **metadata,
                    "map_name_hash": _hash_value("blocked_ips"),
                    "map_name_redacted": True,
                    "blocked_ips_count": len(self._blocked_ips),
                },
            )
            logger.error("Failed to unblock redacted IP: %s", type(exc).__name__)

    def is_blocked(self, ip_address: str) -> bool:
        """Check if an IP is currently quarantined."""
        op_start = time.monotonic()
        blocked = ip_address in self._blocked_ips
        self._publish_observation(
            stage="quarantine_is_blocked_checked",
            operation="is_blocked",
            status="success",
            source_mode="memory",
            start=op_start,
            parsed_summary={"blocked": blocked},
            extra={
                "ip_address_hash": _hash_value(ip_address),
                "ip_address_redacted": True,
                "blocked_ips_count": len(self._blocked_ips),
            },
        )
        return blocked

    def record_pqc_verification_result(
        self,
        peer_id: str,
        ip_address: Optional[str],
        verified: bool,
        reason: str = "failed_verification",
        quarantine_level: int = 2,
    ) -> bool:
        """
        Track PQC verification results and auto-quarantine on repeated failures.

        Returns:
            True if quarantine action was triggered, otherwise False.
        """
        op_start = time.monotonic()
        metadata = {
            "peer_id_hash": _hash_value(peer_id),
            "ip_address_hash": _hash_value(ip_address),
            "reason_hash": _hash_value(reason),
            "peer_id_redacted": True,
            "ip_address_redacted": True,
            "reason_redacted": True,
            "threshold": self.failure_threshold,
            "quarantine_level": int(quarantine_level),
        }

        if verified:
            self._verification_failures[peer_id] = 0
            self._publish_observation(
                stage="pqc_verification_success_recorded",
                operation="record_pqc_verification_result",
                status="success",
                source_mode="pqc-verification",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "verified": True,
                    "failure_count": 0,
                    "quarantine_triggered": False,
                },
                extra=metadata,
            )
            return False

        failures = self._verification_failures.get(peer_id, 0) + 1
        self._verification_failures[peer_id] = failures
        PQC_EBPF_VERIFICATION_FAILURES_TOTAL.inc()

        logger.warning(
            "PQC verification failed for redacted peer/reason count=%d threshold=%d",
            failures,
            self.failure_threshold,
        )

        self._publish_observation(
            stage="pqc_verification_failure_recorded",
            operation="record_pqc_verification_result",
            status="failure",
            source_mode="pqc-verification",
            start=op_start,
            read_only=False,
            parsed_summary={
                "verified": False,
                "failure_count": failures,
                "threshold_reached": failures >= self.failure_threshold,
                "quarantine_triggered": False,
            },
            extra=metadata,
        )

        if failures < self.failure_threshold:
            return False

        if not ip_address:
            logger.warning(
                "Quarantine threshold reached for redacted peer but IP is missing"
            )
            self._publish_observation(
                stage="pqc_quarantine_threshold_missing_ip",
                operation="record_pqc_verification_result",
                status="failure",
                source_mode="pqc-verification",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "verified": False,
                    "failure_count": failures,
                    "threshold_reached": True,
                    "quarantine_triggered": False,
                    "reason": "missing_ip",
                },
                extra=metadata,
            )
            return False

        self.block_node(ip_address, level=quarantine_level)
        self._publish_observation(
            stage="pqc_quarantine_threshold_triggered",
            operation="record_pqc_verification_result",
            status="success",
            source_mode="pqc-verification",
            start=op_start,
            read_only=False,
            parsed_summary={
                "verified": False,
                "failure_count": failures,
                "threshold_reached": True,
                "quarantine_triggered": True,
            },
            extra=metadata,
        )
        return True

    def get_stats(self) -> Dict[str, object]:
        """Return quarantine manager state for diagnostics."""
        op_start = time.monotonic()
        stats = {
            "mode": "software" if self._using_software_fallback else "ebpf",
            "interface": self.interface,
            "failure_threshold": self.failure_threshold,
            "blocked_ips_count": len(self._blocked_ips),
            "blocked_ips": dict(self._blocked_ips),
            "verification_failures": dict(self._verification_failures),
        }
        self._publish_observation(
            stage="quarantine_stats_read",
            operation="get_stats",
            status="success",
            source_mode="memory",
            start=op_start,
            parsed_summary={
                "mode": stats["mode"],
                "failure_threshold": self.failure_threshold,
                "blocked_ips_count": len(self._blocked_ips),
                "verification_failures_count": len(self._verification_failures),
            },
            extra={
                "interface_hash": _hash_value(self.interface),
                "blocked_ip_hashes": _hash_keys(list(self._blocked_ips.keys())),
                "peer_id_hashes": _hash_keys(list(self._verification_failures.keys())),
                "interface_redacted": True,
                "blocked_ips_redacted": True,
                "peer_ids_redacted": True,
            },
        )
        return stats

    def cleanup(self) -> None:
        """Detach XDP program and cleanup resources."""
        op_start = time.monotonic()
        if self.bpf and not self._using_software_fallback:
            try:
                self.bpf.remove_xdp(self.interface, 0)
                self._publish_observation(
                    stage="quarantine_cleanup_xdp_succeeded",
                    operation="cleanup",
                    status="success",
                    source_mode="bcc",
                    start=op_start,
                    read_only=False,
                    parsed_summary={"cleanup": True, "xdp_removed": True},
                    extra={
                        "interface_hash": _hash_value(self.interface),
                        "interface_redacted": True,
                    },
                )
                logger.info("XDP quarantine detached from %s", self.interface)
            except Exception as exc:
                self._publish_observation(
                    stage="quarantine_cleanup_xdp_failed",
                    operation="cleanup",
                    status="failure",
                    source_mode="bcc",
                    start=op_start,
                    read_only=False,
                    error=exc,
                    parsed_summary={"cleanup": False, "xdp_removed": False},
                    extra={
                        "interface_hash": _hash_value(self.interface),
                        "interface_redacted": True,
                    },
                )
                logger.error("Failed to detach XDP from redacted interface")
        else:
            self._publish_observation(
                stage="quarantine_cleanup_skipped_no_xdp",
                operation="cleanup",
                status="success",
                source_mode="software",
                start=op_start,
                read_only=False,
                parsed_summary={
                    "cleanup": True,
                    "reason": "software_or_uninitialized",
                },
                extra={
                    "interface_hash": _hash_value(getattr(self, "interface", "")),
                    "interface_redacted": True,
                },
            )
