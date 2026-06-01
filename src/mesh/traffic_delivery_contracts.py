"""Contracts for bounded traffic-delivery EventBus evidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TRAFFIC_DELIVERY_INPUT_SCHEMA = "x0tta6bl4.traffic_delivery.local_evidence_input.v1"
TRAFFIC_DELIVERY_EVENTBUS_SCHEMA = "x0tta6bl4.traffic_delivery.eventbus_evidence.v1"
TRAFFIC_DELIVERY_CLAIM_GATE_SCHEMA = "x0tta6bl4.traffic_delivery.claim_gate.v1"
TRAFFIC_DELIVERY_CLAIM_BOUNDARY = (
    "Bounded redacted traffic-delivery evidence for an authorized synthetic or "
    "controlled traffic flow only. This does not prove customer traffic, "
    "external reachability, DPI bypass, trust finality, settlement finality, "
    "production SLOs, or production readiness."
)
TRAFFIC_DELIVERY_SOURCE_AGENTS = (
    "traffic-delivery-probe",
    "mesh-traffic-delivery",
    "synthetic-traffic-probe",
)
TRAFFIC_DELIVERY_REQUIRED_SOURCE_ARTIFACT_ROLES = (
    "redacted_traffic_delivery_scenario_probe_report",
)


class TrafficDeliveryObservedEvidence(BaseModel):
    """Redacted observed facts for a traffic-delivery proof."""

    traffic_flow_confirmed: bool = False
    request_observed: bool = False
    response_validated: bool = False
    traffic_payloads_redacted: bool = True
    environment: Literal["lab", "staging", "production"] = "lab"
    traffic_class: str = Field(default="synthetic_mesh_flow", min_length=1)

    @property
    def traffic_delivery_confirmed(self) -> bool:
        return (
            self.traffic_flow_confirmed
            and self.request_observed
            and self.response_validated
            and self.traffic_payloads_redacted
        )


class TrafficDeliverySourceArtifact(BaseModel):
    """A redacted source artifact reference used to justify the traffic claim."""

    role: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    redacted: bool = True


class TrafficDeliveryLocalEvidenceInput(BaseModel):
    """Input JSON accepted by the local traffic-delivery collector."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(default=TRAFFIC_DELIVERY_INPUT_SCHEMA, alias="schema")
    status: str
    observed_evidence: TrafficDeliveryObservedEvidence
    source_artifacts: list[TrafficDeliverySourceArtifact] = Field(default_factory=list)
    raw_identifiers_redacted: bool = True
    raw_values_redacted: bool = True
    payloads_redacted: bool = True
    authorization_scope_redacted: bool = True
    claim_boundary: str = TRAFFIC_DELIVERY_CLAIM_BOUNDARY


class TrafficDeliveryClaimGate(BaseModel):
    """Gate that prevents traffic evidence from becoming wider claims."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["x0tta6bl4.traffic_delivery.claim_gate.v1"] = Field(
        default=TRAFFIC_DELIVERY_CLAIM_GATE_SCHEMA,
        alias="schema",
    )
    traffic_delivery_claim_allowed: bool
    traffic_delivery_confirmed: bool
    dataplane_delivery_claim_allowed: bool
    dataplane_confirmed: bool
    restored_dataplane_claim_allowed: bool
    customer_traffic_claim_allowed: bool = False
    production_customer_traffic_confirmed: bool = False
    external_reachability_claim_allowed: bool = False
    external_dpi_bypass_claim_allowed: bool = False
    trust_finality_claim_allowed: bool = False
    settlement_finality_claim_allowed: bool = False
    production_slo_claim_allowed: bool = False
    production_readiness_claim_allowed: bool = False
    raw_identifiers_redacted: bool = True
    raw_values_redacted: bool = True
    payloads_redacted: bool = True
    observed_evidence: dict[str, Any] = Field(default_factory=dict)
    claim_boundary: str = TRAFFIC_DELIVERY_CLAIM_BOUNDARY
    blockers: list[str] = Field(default_factory=list)
    redacted: bool = True


def traffic_delivery_input_blockers(
    proof: TrafficDeliveryLocalEvidenceInput,
) -> list[str]:
    """Return fail-closed blockers for a redacted traffic-delivery proof."""

    blockers: list[str] = []
    observed = proof.observed_evidence
    if proof.schema_ != TRAFFIC_DELIVERY_INPUT_SCHEMA:
        blockers.append("traffic_delivery_input_schema_invalid")
    if proof.status != "VERIFIED":
        blockers.append("traffic_delivery_input_status_not_verified")
    if observed.traffic_flow_confirmed is not True:
        blockers.append("traffic_delivery_input_flow_not_confirmed")
    if observed.request_observed is not True:
        blockers.append("traffic_delivery_input_request_not_observed")
    if observed.response_validated is not True:
        blockers.append("traffic_delivery_input_response_not_validated")
    if observed.traffic_payloads_redacted is not True:
        blockers.append("traffic_delivery_input_payloads_not_redacted")
    if proof.raw_identifiers_redacted is not True:
        blockers.append("traffic_delivery_input_raw_identifiers_not_redacted")
    if proof.raw_values_redacted is not True:
        blockers.append("traffic_delivery_input_raw_values_not_redacted")
    if proof.payloads_redacted is not True:
        blockers.append("traffic_delivery_input_payloads_not_redacted")
    if proof.authorization_scope_redacted is not True:
        blockers.append("traffic_delivery_input_authorization_scope_not_redacted")
    if not proof.claim_boundary:
        blockers.append("traffic_delivery_input_claim_boundary_missing")
    if not proof.source_artifacts:
        blockers.append("traffic_delivery_input_source_artifacts_missing")
    elif not any(
        artifact.role in TRAFFIC_DELIVERY_REQUIRED_SOURCE_ARTIFACT_ROLES
        for artifact in proof.source_artifacts
    ):
        blockers.append("traffic_delivery_input_required_source_artifact_missing")
    for artifact in proof.source_artifacts:
        if artifact.redacted is not True:
            blockers.append("traffic_delivery_input_source_artifact_not_redacted")
            break
    return blockers


def build_traffic_delivery_claim_gate(
    proof: TrafficDeliveryLocalEvidenceInput,
    *,
    blockers: list[str] | None = None,
) -> TrafficDeliveryClaimGate:
    """Build the redacted traffic-delivery claim gate for EventBus evidence."""

    gate_blockers = list(blockers or [])
    confirmed = not gate_blockers and (
        proof.observed_evidence.traffic_delivery_confirmed
    )
    return TrafficDeliveryClaimGate(
        traffic_delivery_claim_allowed=confirmed,
        traffic_delivery_confirmed=confirmed,
        dataplane_delivery_claim_allowed=confirmed,
        dataplane_confirmed=confirmed,
        restored_dataplane_claim_allowed=confirmed,
        raw_identifiers_redacted=proof.raw_identifiers_redacted,
        raw_values_redacted=proof.raw_values_redacted,
        payloads_redacted=proof.payloads_redacted,
        observed_evidence={
            "probe_attempted": True,
            "dataplane_confirmed": confirmed,
            "traffic_delivery_confirmed": confirmed,
            "traffic_payloads_redacted": proof.observed_evidence.traffic_payloads_redacted,
            "raw_identifiers_redacted": proof.raw_identifiers_redacted,
        },
        claim_boundary=proof.claim_boundary or TRAFFIC_DELIVERY_CLAIM_BOUNDARY,
        blockers=gate_blockers,
    )


def build_traffic_delivery_event_data(
    proof: TrafficDeliveryLocalEvidenceInput,
    *,
    source_agent: str,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build sanitized EventBus data without copying traffic identifiers."""

    gate = build_traffic_delivery_claim_gate(proof, blockers=blockers)
    gate_payload = gate.model_dump(mode="json", by_alias=True)
    observed = proof.observed_evidence
    ready = not gate.blockers and observed.traffic_delivery_confirmed
    source_artifacts = [
        {
            "role": artifact.role,
            "sha256": artifact.sha256,
            "path_redacted": True,
            "redacted": True,
        }
        for artifact in proof.source_artifacts
    ]
    return {
        "schema": TRAFFIC_DELIVERY_EVENTBUS_SCHEMA,
        "component": "traffic_delivery_local_evidence_collector",
        "operation": "traffic_delivery_evidence_intake",
        "source_agent_alias": source_agent,
        "status": "success" if ready else "blocked",
        "probe_attempted": True,
        "dataplane_confirmed": ready,
        "post_action_dataplane_revalidated": ready,
        "restored_dataplane_claim_allowed": ready,
        "dataplane_delivery_claim_allowed": ready,
        "traffic_delivery_confirmed": ready,
        "traffic_delivery_claim_allowed": ready,
        "customer_traffic_claim_allowed": False,
        "production_customer_traffic_confirmed": False,
        "live_customer_traffic_confirmed": False,
        "external_reachability_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "trust_finality_claim_allowed": False,
        "settlement_finality_confirmed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "traffic_class": observed.traffic_class,
        "environment": observed.environment,
        "raw_identifiers_redacted": proof.raw_identifiers_redacted,
        "raw_values_redacted": proof.raw_values_redacted,
        "payloads_redacted": proof.payloads_redacted,
        "authorization_scope_redacted": proof.authorization_scope_redacted,
        "source_artifacts": source_artifacts,
        "source_artifacts_count": len(source_artifacts),
        "claim_gate": gate_payload,
        "traffic_delivery_claim_gate": gate_payload,
        "post_action_dataplane_revalidation": {
            "schema": "x0tta6bl4.traffic_delivery.revalidation.v1",
            "status": "success" if ready else "failed",
            "reason": (
                "bounded_traffic_delivery_succeeded"
                if ready
                else "bounded_traffic_delivery_failed"
            ),
            "probe_attempted": True,
            "dataplane_confirmed": ready,
            "post_action_dataplane_revalidated": ready,
            "restored_dataplane_claim_allowed": ready,
            "traffic_delivery_claim_allowed": ready,
            "traffic_delivery_confirmed": ready,
            "customer_traffic_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "redacted": True,
            "claim_boundary": proof.claim_boundary or TRAFFIC_DELIVERY_CLAIM_BOUNDARY,
            "claim_gate": gate_payload,
            "evidence": {
                "source_agents": [source_agent],
                "source_agents_count": 1,
                "source_artifacts_count": len(source_artifacts),
                "event_ids": [artifact.sha256 for artifact in proof.source_artifacts],
                "event_ids_count": len(source_artifacts),
                "events_total": len(source_artifacts),
                "claim_boundaries": [
                    proof.claim_boundary or TRAFFIC_DELIVERY_CLAIM_BOUNDARY
                ],
                "claim_boundaries_total": 1,
                "redacted": True,
            },
        },
        "evidence": {
            "source_agents": [source_agent],
            "source_agents_count": 1,
            "source_artifacts_count": len(source_artifacts),
            "redacted": True,
        },
        "claim_boundary": proof.claim_boundary or TRAFFIC_DELIVERY_CLAIM_BOUNDARY,
        "blockers": list(gate.blockers),
        "redacted": True,
    }
