"""Contracts for bounded autonomous mesh recovery evidence."""

from __future__ import annotations

import hashlib
import hmac
from typing import Literal

from pydantic import BaseModel, Field


ClaimState = Literal["PROVEN", "UNPROVEN", "UNPROVEN_AWAITING_DATAPLANE_PROOF"]


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


class RecoveryEvidenceV1(BaseModel):
    """Machine-readable mesh_node_degradation_recovery.v1 evidence packet."""

    schema: Literal["mesh_node_degradation_recovery.v1"] = (
        "mesh_node_degradation_recovery.v1"
    )
    event_id: str
    incident_id: str
    node_id_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    action: Literal["restart_local_mesh_agent", "block_and_escalate"]
    policy_decision: PolicyDecision
    before: NodeState
    after: NodeState
    claim_gate: BoundedClaims
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
