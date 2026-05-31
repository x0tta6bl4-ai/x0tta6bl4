"""Contracts for bounded autonomous mesh recovery evidence."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Literal

from pydantic import BaseModel, Field


ClaimState = Literal["PROVEN", "UNPROVEN", "UNPROVEN_AWAITING_DATAPLANE_PROOF"]
PostActionDataplaneDecision = Literal[
    "RESTORED_DATAPLANE_CLAIM_ALLOWED",
    "LOCAL_RECOVERY_LIFECYCLE_ONLY",
]

POST_ACTION_DATAPLANE_CLAIM_GATE_SCHEMA = (
    "x0tta6bl4.post_action_dataplane_claim_gate.v1"
)
CUSTOMER_TRAFFIC_PROOF_BLOCKER = (
    "customer_traffic_requires_separate_end_to_end_proof"
)
POST_ACTION_DATAPLANE_REQUIRED_EVIDENCE = {
    "probe_attempted": True,
    "dataplane_confirmed": True,
    "redacted_evidence": True,
    "event_ids_count_min": 1,
    "events_total_min": 1,
    "source_agents_min": 1,
}


class BoundedClaims(BaseModel):
    """Bounded claims produced by a local recovery revalidation pass."""

    local_peer_visible: ClaimState
    yggdrasil_status_improved: ClaimState
    packet_loss_metric_decreased: ClaimState
    customer_traffic_restored: ClaimState = "UNPROVEN_AWAITING_DATAPLANE_PROOF"


class PolicyDecision(BaseModel):
    """Policy decision that allows or blocks an autonomous action."""

    allowed: bool
    cooldown_active: bool
    execution_limit_checked: str
    safe_mode_required: bool


class NodeState(BaseModel):
    """Redacted local node health snapshot."""

    local_health: str
    packet_loss_pct: float = Field(ge=0.0, le=100.0)
    yggdrasil_status: str


class ServiceIdentityEvidence(BaseModel):
    """Redacted workload identity presence attached to recovery evidence."""

    schema: Literal["x0tta6bl4.service_identity_evidence.v1"] = (
        "x0tta6bl4.service_identity_evidence.v1"
    )
    service_name: str
    spiffe_id_configured: bool = False
    did_configured: bool = False
    wallet_address_configured: bool = False
    raw_identity_values_redacted: bool = True
    redacted: bool = True


class DataplaneEvidenceRef(BaseModel):
    """Redacted EventBus evidence reference for a dataplane proof."""

    source_agents: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)
    events_total: int = Field(default=0, ge=0)
    event_ids_count: int = Field(default=0, ge=0)
    claim_boundaries: list[str] = Field(default_factory=list)
    claim_boundaries_total: int = Field(default=0, ge=0)
    redacted: bool = True


class PostActionDataplaneClaimGate(BaseModel):
    """Gate that prevents local recovery from becoming a dataplane claim."""

    schema: Literal["x0tta6bl4.post_action_dataplane_claim_gate.v1"] = (
        POST_ACTION_DATAPLANE_CLAIM_GATE_SCHEMA
    )
    decision: PostActionDataplaneDecision
    required_for_restored_dataplane_claim: bool = True
    requires_post_action_dataplane_revalidation: bool = True
    local_action_applied: bool = True
    post_action_probe_enabled: bool = True
    post_action_probe_target_present: bool = True
    post_action_probe_attempted: bool
    post_action_dataplane_revalidated: bool
    dataplane_confirmed: bool
    restored_dataplane_claim_allowed: bool
    traffic_delivery_claim_allowed: bool = False
    customer_traffic_claim_allowed: bool = False
    customer_traffic_claim_blockers: list[str] = Field(default_factory=list)
    external_reachability_claim_allowed: bool = False
    production_slo_claim_allowed: bool = False
    production_readiness_claim_allowed: bool = False
    blockers: list[str] = Field(default_factory=list)
    required_evidence: dict[str, Any] = Field(default_factory=dict)
    observed_evidence: dict[str, Any] = Field(default_factory=dict)
    evidence: DataplaneEvidenceRef = Field(default_factory=DataplaneEvidenceRef)
    claim_boundary: str
    redacted: bool = True


class PostActionDataplaneRevalidation(BaseModel):
    """Optional dataplane proof attached after local recovery revalidation."""

    schema: Literal[
        "mesh_node_degradation_recovery.post_action_dataplane_revalidation.v1"
    ] = "mesh_node_degradation_recovery.post_action_dataplane_revalidation.v1"
    status: Literal["not_attempted", "success", "failed"]
    reason: str
    probe_attempted: bool
    post_action_dataplane_revalidated: bool
    dataplane_confirmed: bool
    required_for_restored_dataplane_claim: bool = True
    restored_dataplane_claim_allowed: bool
    customer_traffic_claim_allowed: bool = False
    claim_gate: PostActionDataplaneClaimGate
    evidence: DataplaneEvidenceRef
    claim_boundary: str
    redacted: bool = True


class RecoveryEvidenceV1(BaseModel):
    """Machine-readable mesh_node_degradation_recovery.v1 evidence packet."""

    schema: Literal["mesh_node_degradation_recovery.v1"] = (
        "mesh_node_degradation_recovery.v1"
    )
    event_id: str
    incident_id: str
    node_id_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    service_identity: ServiceIdentityEvidence
    action: Literal["restart_local_mesh_agent", "block_and_escalate"]
    policy_decision: PolicyDecision
    before: NodeState
    after: NodeState
    claim_gate: BoundedClaims
    post_action_dataplane_revalidation: PostActionDataplaneRevalidation | None = None
    raw_values_redacted: bool = True
    duration_ms: int = Field(ge=0)
    return_code: int
    escalation_required: bool = False


def generate_node_id_hash(node_id: str, local_audit_secret: str) -> str:
    """Return an HMAC-SHA256 node identifier hash for audit evidence."""

    if not node_id:
        raise ValueError("node_id cannot be empty")
    if not local_audit_secret:
        raise ValueError("local_audit_secret cannot be empty")

    return hmac.new(
        local_audit_secret.encode("utf-8"),
        node_id.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _safe_nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def build_dataplane_evidence_ref(value: Any) -> DataplaneEvidenceRef:
    """Normalize arbitrary probe evidence into the shared redacted reference."""

    if isinstance(value, DataplaneEvidenceRef):
        return value

    evidence = value if isinstance(value, dict) else {}
    event_ids = _safe_text_list(evidence.get("event_ids"))
    source_agents = _safe_text_list(evidence.get("source_agents"))
    claim_boundaries = _safe_text_list(evidence.get("claim_boundaries"))
    if not claim_boundaries and evidence.get("claim_boundary"):
        claim_boundaries = [str(evidence["claim_boundary"])]

    return DataplaneEvidenceRef(
        source_agents=source_agents,
        event_ids=event_ids,
        events_total=_safe_nonnegative_int(
            evidence.get("events_total"),
            default=len(event_ids),
        ),
        event_ids_count=len(event_ids),
        claim_boundaries=claim_boundaries,
        claim_boundaries_total=_safe_nonnegative_int(
            evidence.get("claim_boundaries_total"),
            default=len(claim_boundaries),
        ),
        redacted=evidence.get("redacted") is True,
    )


def build_post_action_dataplane_claim_gate(
    *,
    probe_required: bool = True,
    probe_enabled: bool = True,
    probe_target_present: bool = True,
    probe_attempted: bool,
    dataplane_confirmed: bool,
    evidence: Any,
    claim_boundary: str,
    local_action_applied: bool = True,
) -> PostActionDataplaneClaimGate:
    """Build one shared gate for post-action restored-dataplane claims.

    This helper intentionally keeps customer traffic, external reachability,
    production SLO, and production readiness claims false. A local dataplane
    probe can only prove a bounded restored-dataplane claim for the local
    recovery action.
    """

    evidence_ref = build_dataplane_evidence_ref(evidence)
    blockers: list[str] = []

    if not probe_required:
        blockers.append("action_type_does_not_require_dataplane_restoration_claim")
    else:
        if not probe_enabled:
            blockers.append("no_bounded_post_action_dataplane_probe_attached")
        elif not probe_target_present:
            blockers.append("no_post_action_dataplane_probe_target")
        elif not probe_attempted:
            blockers.append("no_bounded_post_action_dataplane_probe_attached")
        elif not dataplane_confirmed:
            blockers.append("bounded_dataplane_probe_not_confirmed")

        if probe_attempted and (
            evidence_ref.events_total <= 0 or evidence_ref.event_ids_count <= 0
        ):
            blockers.append("post_action_probe_evidence_missing")
        if probe_attempted and not evidence_ref.source_agents:
            blockers.append("post_action_probe_source_agent_missing")
        if probe_attempted and evidence_ref.redacted is not True:
            blockers.append("post_action_probe_evidence_not_redacted")
        if dataplane_confirmed and not local_action_applied:
            blockers.append("no_local_healing_action_applied")

    restored_dataplane_claim_allowed = bool(probe_required and not blockers)
    decision: PostActionDataplaneDecision = (
        "RESTORED_DATAPLANE_CLAIM_ALLOWED"
        if restored_dataplane_claim_allowed
        else "LOCAL_RECOVERY_LIFECYCLE_ONLY"
    )

    return PostActionDataplaneClaimGate(
        decision=decision,
        required_for_restored_dataplane_claim=probe_required,
        requires_post_action_dataplane_revalidation=probe_required,
        local_action_applied=local_action_applied,
        post_action_probe_enabled=probe_enabled,
        post_action_probe_target_present=probe_target_present,
        post_action_probe_attempted=probe_attempted,
        post_action_dataplane_revalidated=restored_dataplane_claim_allowed,
        dataplane_confirmed=dataplane_confirmed,
        restored_dataplane_claim_allowed=restored_dataplane_claim_allowed,
        traffic_delivery_claim_allowed=False,
        customer_traffic_claim_allowed=False,
        customer_traffic_claim_blockers=[CUSTOMER_TRAFFIC_PROOF_BLOCKER],
        external_reachability_claim_allowed=False,
        production_slo_claim_allowed=False,
        production_readiness_claim_allowed=False,
        blockers=blockers,
        required_evidence=dict(POST_ACTION_DATAPLANE_REQUIRED_EVIDENCE),
        observed_evidence={
            "probe_attempted": probe_attempted,
            "dataplane_confirmed": dataplane_confirmed,
            "redacted_evidence": evidence_ref.redacted is True,
            "event_ids_count": evidence_ref.event_ids_count,
            "events_total": evidence_ref.events_total,
            "source_agents_count": len(evidence_ref.source_agents),
            "local_action_applied": local_action_applied,
        },
        evidence=evidence_ref,
        claim_boundary=claim_boundary,
        redacted=True,
    )
