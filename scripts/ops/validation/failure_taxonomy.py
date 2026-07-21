"""Failure Taxonomy (F1-F10) for x0tta6bl4 Validation Framework.

Each failure type is defined with:
- ID and name
- Description
- How to inject it
- How to detect it
- How to recover from it

Reference: docs/architecture/BENCHMARK_SPEC.md §2
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class FailureCategory(Enum):
    CRASH = "crash"
    NETWORK = "network"
    CRYPTO = "crypto"
    STATE = "state"
    BYZANTINE = "byzantine"


@dataclass(frozen=True)
class FailureType:
    id: str
    name: str
    category: FailureCategory
    description: str
    inject_method: str
    detect_method: str
    recover_method: str
    covers: list[str]  # References to test suites


FAILURE_TAXONOMY: dict[str, FailureType] = {
    "F1": FailureType(
        id="F1",
        name="Node Crash",
        category=FailureCategory.CRASH,
        description="Immediate process termination (SIGKILL) of an active routing/control node.",
        inject_method="kill -9 <pid> or systemctl stop <service>",
        detect_method="Healthcheck failure detection, TCP RST, connection timeout",
        recover_method="systemd Restart=always, MAPE-K self-healing cycle",
        covers=["V1", "V6"],
    ),
    "F2": FailureType(
        id="F2",
        name="Kernel Panic",
        category=FailureCategory.CRASH,
        description="Abrupt termination of eBPF XDP hook execution or driver queue reset.",
        inject_method="echo c > /proc/sysrq-trigger (on test node only)",
        detect_method="Node unreachable, all connections dropped",
        recover_method="Hardware watchdog reboot, node re-registration",
        covers=["V1", "V7"],
    ),
    "F3": FailureType(
        id="F3",
        name="Network Partition",
        category=FailureCategory.NETWORK,
        description="Complete split-brain subnet isolation via iptables/tc.",
        inject_method="iptables -A INPUT -s <node_ip> -j DROP",
        detect_method="Heartbeat timeout, peer registry expiry",
        recover_method="iptables -D, route convergence via mesh",
        covers=["V1", "V4", "V7"],
    ),
    "F4": FailureType(
        id="F4",
        name="Synthetic Packet Loss",
        category=FailureCategory.NETWORK,
        description="Artificial packet drop (10%-30%) via Linux netem.",
        inject_method="tc qdisc add dev eth0 root netem loss 20%",
        detect_method="TTFB degradation, retransmission increase",
        recover_method="tc qdisc del, adaptive retry logic",
        covers=["V2", "V6"],
    ),
    "F5": FailureType(
        id="F5",
        name="High Latency / Jitter",
        category=FailureCategory.NETWORK,
        description="Injection of 100ms-500ms artificial delay.",
        inject_method="tc qdisc add dev eth0 root netem delay 200ms 50ms",
        detect_method="TTFB increase, timeout threshold breach",
        recover_method="tc qdisc del, adaptive timeout adjustment",
        covers=["V2", "V6"],
    ),
    "F6": FailureType(
        id="F6",
        name="DNS Failure",
        category=FailureCategory.NETWORK,
        description="Upstream DNS resolution timeout or NXDOMAIN response injection.",
        inject_method="iptables -A OUTPUT -p udp --dport 53 -j DROP",
        detect_method="DNS timeout, SERVFAIL responses",
        recover_method="DNS failover to backup resolver",
        covers=["V3"],
    ),
    "F7": FailureType(
        id="F7",
        name="Certificate Expiry",
        category=FailureCategory.CRYPTO,
        description="SPIFFE/SPIRE SVID expiration during active mTLS session.",
        inject_method="spire-server entry delete <spiffe_id>",
        detect_method="mTLS handshake failure, x509 validation error",
        recover_method="SVID re-attestation, certificate rotation",
        covers=["V5"],
    ),
    "F8": FailureType(
        id="F8",
        name="PQC Handshake Failure",
        category=FailureCategory.CRYPTO,
        description="Corrupted ML-KEM-768 public key or mismatched signature verification.",
        inject_method="Bit-flip in public_key bytes",
        detect_method="Handshake abort, decapsulation failure",
        recover_method="Key re-exchange, fallback to经典 ECDHE",
        covers=["V5"],
    ),
    "F9": FailureType(
        id="F9",
        name="Registry Loss",
        category=FailureCategory.STATE,
        description="Disconnection from node discovery registry.",
        inject_method="Kill registry process or block registry port",
        detect_method="Peer announcement timeout, stale peer entries",
        recover_method="Registry restart, peer re-announcement",
        covers=["V4", "V7"],
    ),
    "F10": FailureType(
        id="F10",
        name="Byzantine Node",
        category=FailureCategory.BYZANTINE,
        description="Malicious node broadcasting corrupted routing tables.",
        inject_method="Custom script sending invalid PBFT messages",
        detect_method="PBFT quorum failure, signature verification error",
        recover_method="Byzantine fault tolerance, node eviction",
        covers=["V7"],
    ),
}


def get_failure(failure_id: str) -> FailureType:
    """Get failure type by ID (e.g., 'F1')."""
    if failure_id not in FAILURE_TAXONOMY:
        raise ValueError(f"Unknown failure ID: {failure_id}. Valid: {list(FAILURE_TAXONOMY.keys())}")
    return FAILURE_TAXONOMY[failure_id]


def list_failures() -> list[FailureType]:
    """List all failure types."""
    return list(FAILURE_TAXONOMY.values())


def get_failures_by_category(category: FailureCategory) -> list[FailureType]:
    """Get all failure types in a category."""
    return [f for f in FAILURE_TAXONOMY.values() if f.category == category]
