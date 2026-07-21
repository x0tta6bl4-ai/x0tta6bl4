"""Architecture Invariants for x0tta6bl4.

Invariants are properties that MUST always hold true.
Validation doesn't just measure speed — it verifies that
the system's fundamental guarantees are preserved.

Reference: docs/architecture/BENCHMARK_SPEC.md
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class InvariantStatus(Enum):
    VERIFIED = "VERIFIED"
    VIOLATED = "VIOLATED"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


@dataclass
class InvariantCheck:
    """Result of a single invariant check."""
    invariant_id: str
    name: str
    status: InvariantStatus
    details: str
    evidence: str  # Path to log/test that proves this
    timestamp: float


@dataclass
class Invariant:
    """Architectural invariant that must always hold."""
    id: str
    name: str
    description: str
    how_to_verify: str
    what_violation_means: str


INVARIANTS: dict[str, Invariant] = {
    "I1": Invariant(
        id="I1",
        name="No Routing Loops",
        description="A packet must never visit the same node twice in its path from source to destination.",
        how_to_verify="Capture packets at each hop. Verify TTL decrements. Check for cycles in routing tables.",
        what_violation_means="Packet loop causes bandwidth exhaustion, CPU spin, and eventual network partition.",
    ),
    "I2": Invariant(
        id="I2",
        name="No Packet Duplication",
        description="Each packet must be delivered exactly once. No duplication at any layer.",
        how_to_verify="Count packets at ingress and egress. Verify sequence numbers. Check for retransmission storms.",
        what_violation_means="Duplication wastes bandwidth and can cause application-level errors.",
    ),
    "I3": Invariant(
        id="I3",
        name="Session Continuity",
        description="An active TCP/UDP session must survive node failure and route reconvergence without application-level reset.",
        how_to_verify="Establish session, inject F1/F3 failure, Check that session continues after recovery (no RST, no reconnection).",
        what_violation_means="Session loss forces application restart, data loss, poor user experience.",
    ),
    "I4": Invariant(
        id="I4",
        name="Zero Trust Policy Preserved",
        description="Every inter-node communication must be authenticated and encrypted. No plaintext trust.",
        how_to_verify="Capture traffic at each hop. Verify TLS/PQC handshake. Check for unauthenticated paths.",
        what_violation_means="Breaks security model. Untrusted nodes can inject/modify traffic.",
    ),
    "I5": Invariant(
        id="I5",
        name="Eventually Consistent Topology",
        description="After all failures are resolved, all nodes must converge to the same routing table within bounded time.",
        how_to_verify="Inject partition, resolve, wait T, Check that all routing tables are identical across all nodes.",
        what_violation_means="Split-brain: different nodes route to different destinations, causing blackholes or loops.",
    ),
    "I6": Invariant(
        id="I6",
        name="Bounded Recovery Time",
        description="System must recover from any single failure within the declared SLA (currently 2s for F1/F3).",
        how_to_verify="Inject failure, measure time to full recovery across N=30+ runs, Check that p95 < SLA.",
        what_violation_means="Unbounded recovery means system is not self-healing in practice.",
    ),
    "I7": Invariant(
        id="I7",
        name="Monotonic Packet Delivery",
        description="Packets must be delivered in order within a single session. No reordering at the mesh layer.",
        how_to_verify="Send numbered packets, verify order at receiver. Check for gaps/duplicates.",
        what_violation_means="Reordering causes application-level corruption for ordered protocols.",
    ),
}


def get_invariant(invariant_id: str) -> Invariant:
    """Get invariant by ID."""
    if invariant_id not in INVARIANTS:
        raise ValueError(f"Unknown invariant: {invariant_id}")
    return INVARIANTS[invariant_id]


def list_invariants() -> list[Invariant]:
    """List all invariants."""
    return list(INVARIANTS.values())


def check_invariant(
    invariant_id: str,
    check_fn: Callable[[], tuple[InvariantStatus, str, str]],
) -> InvariantCheck:
    """Run an invariant check.

    Args:
        invariant_id: Invariant to check (I1-I7)
        check_fn: Function that returns (status, details, evidence_path)

    Returns:
        InvariantCheck with result
    """
    import time

    invariant = get_invariant(invariant_id)
    status, details, evidence = check_fn()

    return InvariantCheck(
        invariant_id=invariant_id,
        name=invariant.name,
        status=status,
        details=details,
        evidence=evidence,
        timestamp=time.time(),
    )
