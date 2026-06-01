"""Contracts for bounded trust-finality EventBus evidence."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TRUST_FINALITY_INPUT_SCHEMA = "x0tta6bl4.trust_finality.local_evidence_input.v1"
TRUST_FINALITY_EVENTBUS_SCHEMA = "x0tta6bl4.trust_finality.eventbus_evidence.v1"
TRUST_FINALITY_CLAIM_GATE_SCHEMA = "x0tta6bl4.trust_finality.claim_gate.v1"
TRUST_FINALITY_CLAIM_BOUNDARY = (
    "Bounded redacted SPIFFE, DID, wallet, or chain-identity evidence only. "
    "This does not prove dataplane delivery, customer traffic, settlement "
    "finality, production SLOs, or production readiness."
)
TRUST_FINALITY_SOURCE_AGENTS = (
    "service-identity-status",
    "spiffe-agent-manager",
    "spiffe-mapek-loop",
    "spiffe-workload-api",
)
TRUST_FINALITY_REQUIRED_SOURCE_ARTIFACT_ROLES = (
    "redacted_local_trust_probe_report",
    "redacted_local_spiffe_svid_probe_report",
    "redacted_did_ownership_probe_report",
    "redacted_wallet_control_probe_report",
    "redacted_chain_identity_finality_probe_report",
)


class TrustFinalityObservedEvidence(BaseModel):
    """Redacted observed trust facts supplied by a local proof input."""

    live_spiffe_svid_confirmed: bool = False
    did_ownership_confirmed: bool = False
    wallet_control_confirmed: bool = False
    chain_identity_finality_confirmed: bool = False

    @property
    def any_confirmed(self) -> bool:
        return any(
            (
                self.live_spiffe_svid_confirmed,
                self.did_ownership_confirmed,
                self.wallet_control_confirmed,
                self.chain_identity_finality_confirmed,
            )
        )


class TrustFinalitySourceArtifact(BaseModel):
    """A redacted source artifact reference used to justify the trust claim."""

    role: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    redacted: bool = True


class TrustFinalityLocalEvidenceInput(BaseModel):
    """Input JSON accepted by the local trust-finality collector."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: str = Field(default=TRUST_FINALITY_INPUT_SCHEMA, alias="schema")
    status: str
    observed_evidence: TrustFinalityObservedEvidence
    source_artifacts: list[TrustFinalitySourceArtifact] = Field(default_factory=list)
    raw_identity_values_redacted: bool = True
    payloads_redacted: bool = True
    claim_boundary: str = TRUST_FINALITY_CLAIM_BOUNDARY


class TrustFinalityClaimGate(BaseModel):
    """Gate that prevents identity evidence from becoming wider platform claims."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["x0tta6bl4.trust_finality.claim_gate.v1"] = Field(
        default=TRUST_FINALITY_CLAIM_GATE_SCHEMA,
        alias="schema",
    )
    live_spiffe_svid_claim_allowed: bool
    did_ownership_claim_allowed: bool
    wallet_control_claim_allowed: bool
    chain_identity_finality_claim_allowed: bool
    dataplane_delivery_claim_allowed: bool = False
    customer_traffic_claim_allowed: bool = False
    settlement_finality_claim_allowed: bool = False
    production_readiness_claim_allowed: bool = False
    raw_identity_values_redacted: bool = True
    payloads_redacted: bool = True
    claim_boundary: str = TRUST_FINALITY_CLAIM_BOUNDARY
    blockers: list[str] = Field(default_factory=list)
    redacted: bool = True


def trust_finality_input_blockers(proof: TrustFinalityLocalEvidenceInput) -> list[str]:
    """Return fail-closed blockers for a local redacted trust-finality proof."""

    blockers: list[str] = []
    if proof.schema_ != TRUST_FINALITY_INPUT_SCHEMA:
        blockers.append("trust_finality_input_schema_invalid")
    if proof.status != "VERIFIED":
        blockers.append("trust_finality_input_status_not_verified")
    if not proof.observed_evidence.any_confirmed:
        blockers.append("trust_finality_input_has_no_confirmed_identity_fact")
    if proof.raw_identity_values_redacted is not True:
        blockers.append("trust_finality_input_raw_identity_values_not_redacted")
    if proof.payloads_redacted is not True:
        blockers.append("trust_finality_input_payloads_not_redacted")
    if not proof.claim_boundary:
        blockers.append("trust_finality_input_claim_boundary_missing")
    if not proof.source_artifacts:
        blockers.append("trust_finality_input_source_artifacts_missing")
    elif not any(
        artifact.role in TRUST_FINALITY_REQUIRED_SOURCE_ARTIFACT_ROLES
        for artifact in proof.source_artifacts
    ):
        blockers.append("trust_finality_input_required_source_artifact_missing")
    for artifact in proof.source_artifacts:
        if artifact.redacted is not True:
            blockers.append("trust_finality_input_source_artifact_not_redacted")
            break
    return blockers


def build_trust_finality_claim_gate(
    proof: TrustFinalityLocalEvidenceInput,
    *,
    blockers: list[str] | None = None,
) -> TrustFinalityClaimGate:
    """Build the redacted trust-finality claim gate for EventBus evidence."""

    gate_blockers = list(blockers or [])
    verified = not gate_blockers
    observed = proof.observed_evidence
    return TrustFinalityClaimGate(
        live_spiffe_svid_claim_allowed=(
            verified and observed.live_spiffe_svid_confirmed
        ),
        did_ownership_claim_allowed=verified and observed.did_ownership_confirmed,
        wallet_control_claim_allowed=verified and observed.wallet_control_confirmed,
        chain_identity_finality_claim_allowed=(
            verified and observed.chain_identity_finality_confirmed
        ),
        raw_identity_values_redacted=proof.raw_identity_values_redacted,
        payloads_redacted=proof.payloads_redacted,
        claim_boundary=proof.claim_boundary or TRUST_FINALITY_CLAIM_BOUNDARY,
        blockers=gate_blockers,
    )


def build_trust_finality_event_data(
    proof: TrustFinalityLocalEvidenceInput,
    *,
    source_agent: str,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    """Build sanitized EventBus data without copying raw identity values."""

    gate = build_trust_finality_claim_gate(proof, blockers=blockers)
    gate_payload = gate.model_dump(mode="json", by_alias=True)
    observed = proof.observed_evidence
    ready = not gate.blockers
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
        "schema": TRUST_FINALITY_EVENTBUS_SCHEMA,
        "component": "trust_finality_local_evidence_collector",
        "operation": "trust_finality_evidence_intake",
        "source_agent_alias": source_agent,
        "status": "success" if ready else "blocked",
        "live_spiffe_svid_confirmed": (
            ready and observed.live_spiffe_svid_confirmed
        ),
        "live_spire_svid_confirmed": ready and observed.live_spiffe_svid_confirmed,
        "did_ownership_confirmed": ready and observed.did_ownership_confirmed,
        "wallet_control_confirmed": ready and observed.wallet_control_confirmed,
        "chain_identity_finality_confirmed": (
            ready and observed.chain_identity_finality_confirmed
        ),
        "dataplane_confirmed": False,
        "dataplane_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "settlement_finality_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "raw_identity_values_redacted": proof.raw_identity_values_redacted,
        "raw_identifiers_redacted": proof.raw_identity_values_redacted,
        "payloads_redacted": proof.payloads_redacted,
        "source_artifacts": source_artifacts,
        "source_artifacts_count": len(source_artifacts),
        "claim_gate": gate_payload,
        "service_identity_claim_gate": gate_payload,
        "claim_boundary": proof.claim_boundary or TRUST_FINALITY_CLAIM_BOUNDARY,
        "blockers": list(gate.blockers),
        "redacted": True,
    }
