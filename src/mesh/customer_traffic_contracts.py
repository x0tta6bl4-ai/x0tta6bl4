"""Contracts for bounded end-to-end customer traffic EventBus evidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


CUSTOMER_TRAFFIC_INPUT_SCHEMA = "x0tta6bl4.customer_traffic.local_evidence_input.v1"
CUSTOMER_TRAFFIC_EVENTBUS_SCHEMA = "x0tta6bl4.customer_traffic.eventbus_evidence.v1"
CUSTOMER_TRAFFIC_CLAIM_GATE_SCHEMA = "x0tta6bl4.customer_traffic.claim_gate.v1"
CUSTOMER_TRAFFIC_CLAIM_BOUNDARY = (
    "Bounded redacted end-to-end production customer-path evidence only. This "
    "does not prove generic dataplane health, trust finality, settlement "
    "finality, production SLOs, or production readiness."
)
CUSTOMER_TRAFFIC_SOURCE_AGENTS = (
    "customer-traffic-probe",
    "maas-customer-traffic",
    "production-customer-traffic",
)
CUSTOMER_TRAFFIC_REQUIRED_SOURCE_ARTIFACT_ROLES = (
    "redacted_end_to_end_customer_path_probe_report",
)


class CustomerTrafficObservedEvidence(BaseModel):
    """Redacted observed facts for an end-to-end customer-path proof."""

    end_to_end_customer_path_confirmed: bool = False
    customer_request_observed: bool = False
    customer_response_validated: bool = False
    customer_payloads_redacted: bool = True
    environment: Literal["production", "staging", "lab"] = "production"

    @property
    def production_customer_traffic_confirmed(self) -> bool:
        return (
            self.environment == "production"
            and self.end_to_end_customer_path_confirmed
            and self.customer_request_observed
            and self.customer_response_validated
            and self.customer_payloads_redacted
        )


class CustomerTrafficSourceArtifact(BaseModel):
    """A redacted source artifact reference used to justify the traffic claim."""

    role: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    redacted: bool = True


class CustomerTrafficLocalEvidenceInput(BaseModel):
    """Input JSON accepted by the local customer-traffic collector."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(default=CUSTOMER_TRAFFIC_INPUT_SCHEMA, alias="schema")
    status: str
    observed_evidence: CustomerTrafficObservedEvidence
    source_artifacts: list[CustomerTrafficSourceArtifact] = Field(default_factory=list)
    raw_identifiers_redacted: bool = True
    raw_values_redacted: bool = True
    payloads_redacted: bool = True
    authorization_scope_redacted: bool = True
    claim_boundary: str = CUSTOMER_TRAFFIC_CLAIM_BOUNDARY


class CustomerTrafficClaimGate(BaseModel):
    """Gate that prevents customer-path evidence from becoming wider claims."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["x0tta6bl4.customer_traffic.claim_gate.v1"] = Field(
        default=CUSTOMER_TRAFFIC_CLAIM_GATE_SCHEMA,
        alias="schema",
    )
    customer_traffic_claim_allowed: bool
    customer_traffic_delivery_claim_allowed: bool
    production_customer_traffic_confirmed: bool
    live_customer_traffic_confirmed: bool
    dataplane_delivery_claim_allowed: bool = False
    trust_finality_claim_allowed: bool = False
    external_settlement_finality_claim_allowed: bool = False
    production_readiness_claim_allowed: bool = False
    raw_identifiers_redacted: bool = True
    raw_values_redacted: bool = True
    payloads_redacted: bool = True
    claim_boundary: str = CUSTOMER_TRAFFIC_CLAIM_BOUNDARY
    blockers: list[str] = Field(default_factory=list)
    redacted: bool = True


def customer_traffic_input_blockers(
    proof: CustomerTrafficLocalEvidenceInput,
) -> list[str]:
    """Return fail-closed blockers for a redacted customer-traffic proof."""

    blockers: list[str] = []
    observed = proof.observed_evidence
    if proof.schema_ != CUSTOMER_TRAFFIC_INPUT_SCHEMA:
        blockers.append("customer_traffic_input_schema_invalid")
    if proof.status != "VERIFIED":
        blockers.append("customer_traffic_input_status_not_verified")
    if observed.environment != "production":
        blockers.append("customer_traffic_input_environment_not_production")
    if observed.end_to_end_customer_path_confirmed is not True:
        blockers.append("customer_traffic_input_end_to_end_path_not_confirmed")
    if observed.customer_request_observed is not True:
        blockers.append("customer_traffic_input_request_not_observed")
    if observed.customer_response_validated is not True:
        blockers.append("customer_traffic_input_response_not_validated")
    if observed.customer_payloads_redacted is not True:
        blockers.append("customer_traffic_input_payloads_not_redacted")
    if proof.raw_identifiers_redacted is not True:
        blockers.append("customer_traffic_input_raw_identifiers_not_redacted")
    if proof.raw_values_redacted is not True:
        blockers.append("customer_traffic_input_raw_values_not_redacted")
    if proof.payloads_redacted is not True:
        blockers.append("customer_traffic_input_payloads_not_redacted")
    if proof.authorization_scope_redacted is not True:
        blockers.append("customer_traffic_input_authorization_scope_not_redacted")
    if not proof.claim_boundary:
        blockers.append("customer_traffic_input_claim_boundary_missing")
    if not proof.source_artifacts:
        blockers.append("customer_traffic_input_source_artifacts_missing")
    elif not any(
        artifact.role in CUSTOMER_TRAFFIC_REQUIRED_SOURCE_ARTIFACT_ROLES
        for artifact in proof.source_artifacts
    ):
        blockers.append("customer_traffic_input_required_source_artifact_missing")
    for artifact in proof.source_artifacts:
        if artifact.redacted is not True:
            blockers.append("customer_traffic_input_source_artifact_not_redacted")
            break
    return blockers


def build_customer_traffic_claim_gate(
    proof: CustomerTrafficLocalEvidenceInput,
    *,
    blockers: list[str] | None = None,
) -> CustomerTrafficClaimGate:
    """Build the redacted customer-traffic claim gate for EventBus evidence."""

    gate_blockers = list(blockers or [])
    confirmed = not gate_blockers and (
        proof.observed_evidence.production_customer_traffic_confirmed
    )
    return CustomerTrafficClaimGate(
        customer_traffic_claim_allowed=confirmed,
        customer_traffic_delivery_claim_allowed=confirmed,
        production_customer_traffic_confirmed=confirmed,
        live_customer_traffic_confirmed=confirmed,
        raw_identifiers_redacted=proof.raw_identifiers_redacted,
        raw_values_redacted=proof.raw_values_redacted,
        payloads_redacted=proof.payloads_redacted,
        claim_boundary=proof.claim_boundary or CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
        blockers=gate_blockers,
    )


def build_customer_traffic_event_data(
    proof: CustomerTrafficLocalEvidenceInput,
    *,
    source_agent: str,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build sanitized EventBus data without copying customer identifiers."""

    gate = build_customer_traffic_claim_gate(proof, blockers=blockers)
    gate_payload = gate.model_dump(mode="json", by_alias=True)
    observed = proof.observed_evidence
    ready = not gate.blockers and observed.production_customer_traffic_confirmed
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
        "schema": CUSTOMER_TRAFFIC_EVENTBUS_SCHEMA,
        "component": "customer_traffic_local_evidence_collector",
        "operation": "end_to_end_customer_path_evidence_intake",
        "source_agent_alias": source_agent,
        "status": "success" if ready else "blocked",
        "production_customer_traffic_confirmed": ready,
        "live_customer_traffic_confirmed": ready,
        "customer_traffic_confirmed": ready,
        "customer_traffic_claim_allowed": ready,
        "customer_traffic_delivery_claim_allowed": ready,
        "dataplane_confirmed": False,
        "dataplane_delivery_claim_allowed": False,
        "trust_finality_claim_allowed": False,
        "settlement_finality_confirmed": False,
        "external_settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "environment": observed.environment,
        "raw_identifiers_redacted": proof.raw_identifiers_redacted,
        "raw_values_redacted": proof.raw_values_redacted,
        "payloads_redacted": proof.payloads_redacted,
        "authorization_scope_redacted": proof.authorization_scope_redacted,
        "source_artifacts": source_artifacts,
        "source_artifacts_count": len(source_artifacts),
        "claim_gate": gate_payload,
        "customer_traffic_claim_gate": gate_payload,
        "evidence": {
            "source_agents": [source_agent],
            "source_agents_count": 1,
            "source_artifacts_count": len(source_artifacts),
            "redacted": True,
        },
        "claim_boundary": proof.claim_boundary or CUSTOMER_TRAFFIC_CLAIM_BOUNDARY,
        "blockers": list(gate.blockers),
        "redacted": True,
    }
