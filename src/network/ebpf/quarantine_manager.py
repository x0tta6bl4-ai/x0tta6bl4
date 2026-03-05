#!/usr/bin/env python3
"""Zero-Trust quarantine manager for PQC verification failures."""

from __future__ import annotations

import ctypes
import logging
import os
import socket
import struct
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

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
    ):
        self.interface = interface
        self.failure_threshold = max(1, int(failure_threshold))
        self.bpf = None
        self.fn = None
        self._using_software_fallback = False
        self._blocked_ips: Dict[str, int] = {}
        self._verification_failures: Dict[str, int] = {}
        self._bpf_program_path = bpf_program_path

        self._init_ebpf_or_fallback()

    @property
    def is_using_software_fallback(self) -> bool:
        return self._using_software_fallback

    def _init_ebpf_or_fallback(self) -> None:
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, using software quarantine fallback")
            self._enable_software_fallback()
            return

        if os.geteuid() != 0:
            logger.warning("Not running as root, using software quarantine fallback")
            self._enable_software_fallback()
            return

        try:
            program_text = self._load_program_text()
            self.bpf = BPF(text=program_text)
            self.fn = self.bpf.load_func("x0t_quarantine_filter", BPF.XDP)
            self.bpf.attach_xdp(self.interface, self.fn, 0)
            logger.info("Zero-Trust XDP quarantine attached to %s", self.interface)
        except Exception as exc:
            logger.warning(
                "Failed to initialize XDP quarantine, using software fallback: %s", exc
            )
            self._enable_software_fallback()

    def _load_program_text(self) -> str:
        path_candidates = []
        if self._bpf_program_path:
            path_candidates.append(Path(self._bpf_program_path))
        path_candidates.append(Path("src/network/ebpf/programs/node_quarantine.c"))

        for candidate in path_candidates:
            if candidate.exists():
                return candidate.read_text()
        return DEFAULT_QUARANTINE_BPF_PROGRAM

    def _enable_software_fallback(self) -> None:
        self._using_software_fallback = True
        self.bpf = None
        self.fn = None
        logger.info("Software quarantine fallback enabled")

    def _ip_to_u32(self, ip_str: str) -> int:
        """Convert IP string to network byte order u32."""
        return struct.unpack("I", socket.inet_aton(ip_str))[0]

    def block_node(self, ip_address: str, level: int = 2) -> None:
        """
        Add node to quarantine.
        Levels: 2 = quarantine (drop), 3 = hard block.
        """
        try:
            # Validate early for both eBPF and fallback paths.
            ip_u32 = self._ip_to_u32(ip_address)
        except Exception as exc:
            logger.error("Invalid IP %s for quarantine: %s", ip_address, exc)
            return

        if self._using_software_fallback or not self.bpf:
            self._blocked_ips[ip_address] = int(level)
            PQC_EBPF_QUARANTINE_ACTIONS_TOTAL.inc()
            logger.warning(
                "Node %s quarantined in software mode (level=%d)", ip_address, level
            )
            return

        try:
            self.bpf["blocked_ips"][ctypes.c_uint32(ip_u32)] = ctypes.c_uint32(level)
            self._blocked_ips[ip_address] = int(level)
            PQC_EBPF_QUARANTINE_ACTIONS_TOTAL.inc()
            logger.warning("Node %s quarantined via XDP (level=%d)", ip_address, level)
        except Exception as exc:
            logger.error("Failed to block IP %s: %s", ip_address, exc)

    def unblock_node(self, ip_address: str) -> None:
        """Remove node from quarantine."""
        self._blocked_ips.pop(ip_address, None)

        if self._using_software_fallback or not self.bpf:
            logger.info("Node %s released from software quarantine", ip_address)
            return

        try:
            ip_u32 = self._ip_to_u32(ip_address)
            del self.bpf["blocked_ips"][ctypes.c_uint32(ip_u32)]
            logger.info("Node %s released from XDP quarantine", ip_address)
        except KeyError:
            return
        except Exception as exc:
            logger.error("Failed to unblock IP %s: %s", ip_address, exc)

    def is_blocked(self, ip_address: str) -> bool:
        """Check if an IP is currently quarantined."""
        return ip_address in self._blocked_ips

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
        if verified:
            self._verification_failures[peer_id] = 0
            return False

        failures = self._verification_failures.get(peer_id, 0) + 1
        self._verification_failures[peer_id] = failures
        PQC_EBPF_VERIFICATION_FAILURES_TOTAL.inc()

        logger.warning(
            "PQC verification failed for peer=%s reason=%s count=%d threshold=%d",
            peer_id,
            reason,
            failures,
            self.failure_threshold,
        )

        if failures < self.failure_threshold:
            return False

        if not ip_address:
            logger.warning(
                "Quarantine threshold reached for peer=%s but IP is missing", peer_id
            )
            return False

        self.block_node(ip_address, level=quarantine_level)
        return True

    def get_stats(self) -> Dict[str, object]:
        """Return quarantine manager state for diagnostics."""
        return {
            "mode": "software" if self._using_software_fallback else "ebpf",
            "interface": self.interface,
            "failure_threshold": self.failure_threshold,
            "blocked_ips_count": len(self._blocked_ips),
            "blocked_ips": dict(self._blocked_ips),
            "verification_failures": dict(self._verification_failures),
        }

    def cleanup(self) -> None:
        """Detach XDP program and cleanup resources."""
        if self.bpf and not self._using_software_fallback:
            try:
                self.bpf.remove_xdp(self.interface, 0)
                logger.info("XDP quarantine detached from %s", self.interface)
            except Exception as exc:
                logger.error("Failed to detach XDP from %s: %s", self.interface, exc)
