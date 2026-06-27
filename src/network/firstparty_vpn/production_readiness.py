"""Full production readiness gate for first-party VPN rollout."""

from __future__ import annotations

from dataclasses import dataclass
import json

from .crypto import SUPPORTED_KEM_ALGORITHMS, SUPPORTED_SIGNATURE_ALGORITHMS
from .dataplane_validation import (
    DataplaneTransport,
    DataplaneValidationEvidence,
    TunDataplaneValidationEvidence,
)
from .leak_protection import LinuxLeakProtectionEvidence
from .mtu import MtuValidationEvidence
from .ops import RolloutGateDecision, assert_privacy_safe, hash_identifier
from .pqc import PqcImplementationManifest, PqcKatResult, PqcProviderGateDecision
from .preflight import LinuxPreflightEvidence
from .production_control import (
    ExternalPolicySnapshotSourceEvidence,
    FirstPartyIdentitySignerManifest,
    IdentitySignerConformanceEvidence,
    IdentitySignerKatResult,
    ProductionIdentitySignerGateDecision,
)
from .rekey_policy import FirstPartyRekeyPolicyDecision
from .source_audit import FirstPartySourceAuditEvidence
from .zero_trust import ZeroTrustPolicyEvidence


class FullVpnProductionReadinessError(ValueError):
    """Raised when full VPN production readiness evidence is invalid."""


@dataclass(frozen=True)
class FullVpnProductionReadinessRequirements:
    """Non-negotiable evidence required before production VPN rollout."""

    target: str = "nl"
    required_dataplane_paths: frozenset[str] = frozenset(
        {"lan", "vps", "mobile", "restricted-work-wifi"}
    )
    required_dataplane_transports: tuple[tuple[str, DataplaneTransport], ...] = (
        ("restricted-work-wifi", "camouflage"),
    )
    required_dataplane_probe_matrix_hash: str | None = None
    required_zero_trust_workloads: frozenset[str] = frozenset(
        {"vpn-client", "vpn-server"}
    )
    required_zero_trust_policy_hash: str | None = None
    max_identity_token_lifetime_seconds: int = 3600
    max_validation_evidence_age_seconds: int = 3600
    max_policy_snapshot_age_seconds: int = 3600
    max_policy_source_load_age_seconds: int = 3600
    max_source_audit_age_seconds: int = 3600
    max_identity_signer_kat_age_seconds: int = 3600
    max_pqc_kat_age_seconds: int = 3600
    required_linux_host_fingerprint: str | None = None
    required_pqc_manifest_hash: str | None = None
    required_identity_signer_manifest_hash: str | None = None
    required_apply_plan_hash: str | None = None
    required_rollback_plan_hash: str | None = None
    require_leak_protection: bool = True
    required_leak_protection_plan_hash: str | None = None
    required_external_policy_source_hash: str | None = None
    required_policy_snapshot_hash: str | None = None
    required_source_audit_root_hash: str | None = None
    required_source_audit_tree_hash: str | None = None
    required_rekey_rollback_plan_hash: str | None = None
    required_rollout_gate_hash: str | None = None
    evaluated_at: int | None = None

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise FullVpnProductionReadinessError("production readiness target is required")
        if not self.required_dataplane_paths:
            raise FullVpnProductionReadinessError(
                "production readiness dataplane paths are required"
            )
        for path in self.required_dataplane_paths:
            if not path.strip():
                raise FullVpnProductionReadinessError(
                    "production readiness dataplane path cannot be blank"
                )
        for path, transport in self.required_dataplane_transports:
            if not path.strip():
                raise FullVpnProductionReadinessError(
                    "production readiness dataplane transport path cannot be blank"
                )
            if path not in self.required_dataplane_paths:
                raise FullVpnProductionReadinessError(
                    "production readiness transport path must be required"
                )
            if transport not in ("udp", "tcp", "camouflage"):
                raise FullVpnProductionReadinessError(
                    "production readiness transport must be udp, tcp, or camouflage"
                )
        _validate_optional_sha256_hex(
            self.required_dataplane_probe_matrix_hash,
            "required_dataplane_probe_matrix_hash",
        )
        if not self.required_zero_trust_workloads:
            raise FullVpnProductionReadinessError(
                "production readiness zero-trust workloads are required"
            )
        for workload in self.required_zero_trust_workloads:
            if not workload.strip():
                raise FullVpnProductionReadinessError(
                    "production readiness zero-trust workload cannot be blank"
                )
        _validate_optional_sha256_hex(
            self.required_zero_trust_policy_hash,
            "required_zero_trust_policy_hash",
        )
        if self.max_identity_token_lifetime_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness max identity token lifetime must be positive"
            )
        if self.max_validation_evidence_age_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness validation evidence age must be positive"
            )
        if self.max_policy_snapshot_age_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness policy snapshot age must be positive"
            )
        if self.max_policy_source_load_age_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness policy source load age must be positive"
            )
        if self.max_source_audit_age_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness source audit age must be positive"
            )
        if self.max_identity_signer_kat_age_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness identity signer KAT age must be positive"
            )
        if self.max_pqc_kat_age_seconds < 1:
            raise FullVpnProductionReadinessError(
                "production readiness PQC KAT age must be positive"
            )
        _validate_optional_sha256_hex(
            self.required_linux_host_fingerprint,
            "required_linux_host_fingerprint",
        )
        _validate_optional_sha256_hex(
            self.required_pqc_manifest_hash,
            "required_pqc_manifest_hash",
        )
        _validate_optional_sha256_hex(
            self.required_identity_signer_manifest_hash,
            "required_identity_signer_manifest_hash",
        )
        _validate_optional_sha256_hex(
            self.required_apply_plan_hash,
            "required_apply_plan_hash",
        )
        _validate_optional_sha256_hex(
            self.required_rollback_plan_hash,
            "required_rollback_plan_hash",
        )
        _validate_optional_sha256_hex(
            self.required_leak_protection_plan_hash,
            "required_leak_protection_plan_hash",
        )
        _validate_optional_sha256_hex(
            self.required_external_policy_source_hash,
            "required_external_policy_source_hash",
        )
        _validate_optional_sha256_hex(
            self.required_policy_snapshot_hash,
            "required_policy_snapshot_hash",
        )
        _validate_optional_sha256_hex(
            self.required_source_audit_root_hash,
            "required_source_audit_root_hash",
        )
        _validate_optional_sha256_hex(
            self.required_source_audit_tree_hash,
            "required_source_audit_tree_hash",
        )
        _validate_optional_sha256_hex(
            self.required_rekey_rollback_plan_hash,
            "required_rekey_rollback_plan_hash",
        )
        _validate_optional_sha256_hex(
            self.required_rollout_gate_hash,
            "required_rollout_gate_hash",
        )
        if self.evaluated_at is not None and self.evaluated_at < 0:
            raise FullVpnProductionReadinessError(
                "production readiness evaluation time cannot be negative"
            )

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "evaluated_at": self.evaluated_at,
            "max_identity_lifetime_seconds": (
                self.max_identity_token_lifetime_seconds
            ),
            "max_validation_evidence_age_seconds": (
                self.max_validation_evidence_age_seconds
            ),
            "max_policy_snapshot_age_seconds": self.max_policy_snapshot_age_seconds,
            "max_policy_source_load_age_seconds": (
                self.max_policy_source_load_age_seconds
            ),
            "max_identity_signer_kat_age_seconds": (
                self.max_identity_signer_kat_age_seconds
            ),
            "max_pqc_kat_age_seconds": self.max_pqc_kat_age_seconds,
            "max_source_audit_age_seconds": self.max_source_audit_age_seconds,
            "required_dataplane_paths": sorted(self.required_dataplane_paths),
            "required_dataplane_transports": [
                {"path_label": path, "transport": transport}
                for path, transport in sorted(self.required_dataplane_transports)
            ],
            "required_dataplane_probe_matrix_hash": (
                self.required_dataplane_probe_matrix_hash
            ),
            "required_linux_host_fingerprint": self.required_linux_host_fingerprint,
            "required_pqc_manifest_hash": self.required_pqc_manifest_hash,
            "required_identity_signer_manifest_hash": (
                self.required_identity_signer_manifest_hash
            ),
            "required_apply_plan_hash": self.required_apply_plan_hash,
            "required_rollback_plan_hash": self.required_rollback_plan_hash,
            "required_leak_protection_plan_hash": (
                self.required_leak_protection_plan_hash
            ),
            "required_external_policy_source_hash": (
                self.required_external_policy_source_hash
            ),
            "required_policy_snapshot_hash": self.required_policy_snapshot_hash,
            "required_source_audit_root_hash": self.required_source_audit_root_hash,
            "required_source_audit_tree_hash": self.required_source_audit_tree_hash,
            "required_rekey_rollback_plan_hash": (
                self.required_rekey_rollback_plan_hash
            ),
            "required_rollout_gate_hash": self.required_rollout_gate_hash,
            "required_zero_trust_workloads": sorted(
                self.required_zero_trust_workloads
            ),
            "required_zero_trust_policy_hash": self.required_zero_trust_policy_hash,
            "target_hash": hash_identifier(self.target, namespace="readiness-target"),
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class FullVpnProductionReadinessEvidence:
    """Collected evidence for one first-party VPN production rollout candidate."""

    target: str
    linux_preflight: LinuxPreflightEvidence | None = None
    leak_protection: LinuxLeakProtectionEvidence | None = None
    dataplane_validation: DataplaneValidationEvidence | None = None
    tun_dataplane_validation: TunDataplaneValidationEvidence | None = None
    mtu_validation: MtuValidationEvidence | None = None
    pqc_provider_gate: PqcProviderGateDecision | None = None
    pqc_manifest: PqcImplementationManifest | None = None
    pqc_kat: PqcKatResult | None = None
    identity_signer_gate: ProductionIdentitySignerGateDecision | None = None
    identity_signer_manifest: FirstPartyIdentitySignerManifest | None = None
    identity_signer_kat: IdentitySignerKatResult | None = None
    identity_signer_conformance: IdentitySignerConformanceEvidence | None = None
    external_policy_source: ExternalPolicySnapshotSourceEvidence | None = None
    rekey_policy: FirstPartyRekeyPolicyDecision | None = None
    rollout_gate: RolloutGateDecision | None = None
    source_audit: FirstPartySourceAuditEvidence | None = None
    zero_trust_policy: ZeroTrustPolicyEvidence | None = None
    policy_snapshot_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.target.strip():
            raise FullVpnProductionReadinessError("readiness evidence target is required")


@dataclass(frozen=True)
class FullVpnProductionReadinessDecision:
    allowed: bool
    reasons: tuple[str, ...]
    evidence_hash: str

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "allowed": self.allowed,
            "evidence_hash": self.evidence_hash,
            "reasons": list(self.reasons),
        }
        assert_privacy_safe(payload)
        return payload


def evaluate_full_vpn_production_readiness(
    requirements: FullVpnProductionReadinessRequirements,
    evidence: FullVpnProductionReadinessEvidence,
) -> FullVpnProductionReadinessDecision:
    """Fail closed unless every production VPN evidence block is present and passing."""
    reasons: list[str] = []

    if evidence.target != requirements.target:
        reasons.append("readiness_target_mismatch")

    if evidence.linux_preflight is None:
        reasons.append("linux_preflight_missing")
    elif not evidence.linux_preflight.passed:
        reasons.append("linux_preflight_failed")
    if evidence.linux_preflight is not None:
        _evaluate_linux_command_plan_binding(requirements, evidence, reasons)

    if evidence.leak_protection is None:
        if requirements.require_leak_protection:
            reasons.append("leak_protection_missing")
    elif not evidence.leak_protection.passed:
        reasons.append("leak_protection_failed")
    if evidence.leak_protection is not None:
        _evaluate_leak_protection_plan_binding(requirements, evidence, reasons)

    if evidence.dataplane_validation is None:
        reasons.append("dataplane_validation_missing")
    else:
        if not evidence.dataplane_validation.passed:
            reasons.append("dataplane_validation_failed")
        for path in sorted(
            requirements.required_dataplane_paths
            - set(evidence.dataplane_validation.covered_path_labels)
        ):
            reasons.append(f"dataplane_required_path_missing:{path}")
        _evaluate_freshness(
            prefix="dataplane",
            captured_at=evidence.dataplane_validation.captured_at,
            requirements=requirements,
            reasons=reasons,
        )
        _evaluate_required_transports(
            prefix="dataplane",
            required_transports=requirements.required_dataplane_transports,
            results=evidence.dataplane_validation.results,
            reasons=reasons,
        )

    if evidence.tun_dataplane_validation is None:
        reasons.append("tun_dataplane_validation_missing")
    else:
        if not evidence.tun_dataplane_validation.passed:
            reasons.append("tun_dataplane_validation_failed")
        for path in sorted(
            requirements.required_dataplane_paths
            - set(evidence.tun_dataplane_validation.covered_path_labels)
        ):
            reasons.append(f"tun_dataplane_required_path_missing:{path}")
        _evaluate_freshness(
            prefix="tun_dataplane",
            captured_at=evidence.tun_dataplane_validation.captured_at,
            requirements=requirements,
            reasons=reasons,
        )
        _evaluate_required_transports(
            prefix="tun_dataplane",
            required_transports=requirements.required_dataplane_transports,
            results=evidence.tun_dataplane_validation.results,
            reasons=reasons,
        )

    if (
        evidence.dataplane_validation is not None
        and evidence.tun_dataplane_validation is not None
        and evidence.dataplane_validation.probe_matrix_hash()
        != evidence.tun_dataplane_validation.probe_matrix_hash()
    ):
        reasons.append("dataplane_tun_probe_matrix_mismatch")

    if evidence.mtu_validation is None:
        reasons.append("mtu_validation_missing")
    else:
        if not evidence.mtu_validation.passed:
            reasons.append("mtu_validation_failed")
        for path in sorted(
            requirements.required_dataplane_paths
            - set(evidence.mtu_validation.covered_path_labels)
        ):
            reasons.append(f"mtu_required_path_missing:{path}")
        _evaluate_freshness(
            prefix="mtu",
            captured_at=evidence.mtu_validation.captured_at,
            requirements=requirements,
            reasons=reasons,
        )
        _evaluate_required_transports(
            prefix="mtu",
            required_transports=requirements.required_dataplane_transports,
            results=evidence.mtu_validation.results,
            reasons=reasons,
        )
        if (
            evidence.dataplane_validation is not None
            and evidence.dataplane_validation.probe_matrix_hash()
            != evidence.mtu_validation.probe_matrix_hash()
        ):
            reasons.append("dataplane_mtu_probe_matrix_mismatch")

    if requirements.required_dataplane_probe_matrix_hash is None:
        reasons.append("dataplane_probe_matrix_requirement_missing")
    else:
        for prefix, validation in (
            ("dataplane", evidence.dataplane_validation),
            ("tun_dataplane", evidence.tun_dataplane_validation),
            ("mtu", evidence.mtu_validation),
        ):
            if (
                validation is not None
                and validation.probe_matrix_hash()
                != requirements.required_dataplane_probe_matrix_hash
            ):
                reasons.append(f"{prefix}_probe_matrix_mismatch")

    if evidence.pqc_provider_gate is None:
        reasons.append("pqc_provider_gate_missing")
    elif not evidence.pqc_provider_gate.allowed:
        reasons.append("pqc_provider_gate_failed")
    if evidence.pqc_manifest is None:
        reasons.append("pqc_manifest_missing")
    else:
        _evaluate_pqc_manifest_evidence(
            requirements=requirements,
            manifest=evidence.pqc_manifest,
            gate=evidence.pqc_provider_gate,
            reasons=reasons,
        )
    if evidence.pqc_kat is None:
        reasons.append("pqc_kat_missing")
    else:
        if not evidence.pqc_kat.passed:
            reasons.append("pqc_kat_failed")
        if evidence.pqc_kat.vector_count < 1:
            reasons.append("pqc_kat_vectors_missing")
        _evaluate_pqc_kat_freshness(
            requirements=requirements,
            kat=evidence.pqc_kat,
            reasons=reasons,
        )
        if evidence.pqc_provider_gate is not None:
            _evaluate_pqc_gate_kat_binding(
                gate=evidence.pqc_provider_gate,
                kat=evidence.pqc_kat,
                reasons=reasons,
            )
        if evidence.pqc_manifest is not None:
            _evaluate_pqc_manifest_kat_binding(
                manifest=evidence.pqc_manifest,
                kat=evidence.pqc_kat,
                reasons=reasons,
            )

    _evaluate_zero_trust_policy_evidence(requirements, evidence, reasons)

    if evidence.identity_signer_gate is None:
        reasons.append("identity_signer_gate_missing")
    elif not evidence.identity_signer_gate.allowed:
        reasons.append("identity_signer_gate_failed")
    if evidence.identity_signer_manifest is None:
        reasons.append("identity_signer_manifest_missing")
    else:
        if requirements.required_identity_signer_manifest_hash is None:
            reasons.append("identity_signer_manifest_hash_requirement_missing")
        elif (
            evidence.identity_signer_manifest.manifest_hash()
            != requirements.required_identity_signer_manifest_hash
        ):
            reasons.append("identity_signer_manifest_hash_mismatch")
        if evidence.identity_signer_manifest.mode != "production":
            reasons.append("identity_signer_manifest_not_production")
        if not evidence.identity_signer_manifest.reviewed:
            reasons.append("identity_signer_manifest_not_reviewed")
        if (
            evidence.identity_signer_gate is not None
            and evidence.identity_signer_gate.attestation_hash
            != evidence.identity_signer_manifest.to_attestation().attestation_hash()
        ):
            reasons.append("identity_signer_manifest_attestation_mismatch")
    if evidence.identity_signer_kat is None:
        reasons.append("identity_signer_kat_missing")
    else:
        if not evidence.identity_signer_kat.passed:
            reasons.append("identity_signer_kat_failed")
        if evidence.identity_signer_kat.vector_count < 1:
            reasons.append("identity_signer_kat_vectors_missing")
        _evaluate_identity_signer_kat_freshness(
            requirements=requirements,
            kat=evidence.identity_signer_kat,
            reasons=reasons,
        )
        if (
            evidence.identity_signer_manifest is not None
            and evidence.identity_signer_kat.suite_hash
            not in evidence.identity_signer_manifest.kat_hashes
        ):
            reasons.append("identity_signer_kat_not_in_manifest")
        _evaluate_identity_signer_kat_binding(
            gate=evidence.identity_signer_gate,
            manifest=evidence.identity_signer_manifest,
            kat=evidence.identity_signer_kat,
            reasons=reasons,
        )
    if evidence.identity_signer_conformance is None:
        reasons.append("identity_signer_conformance_missing")
    else:
        if not evidence.identity_signer_conformance.passed:
            reasons.append("identity_signer_conformance_failed")
        if evidence.identity_signer_conformance.profile != "fips204-production":
            reasons.append("identity_signer_conformance_not_production")
        if evidence.identity_signer_conformance.vector_count < 1:
            reasons.append("identity_signer_conformance_vectors_missing")
        if evidence.identity_signer_manifest is not None:
            if (
                evidence.identity_signer_conformance.manifest_hash
                != evidence.identity_signer_manifest.manifest_hash()
            ):
                reasons.append("identity_signer_conformance_manifest_mismatch")
            if (
                evidence.identity_signer_conformance.provider_id
                != evidence.identity_signer_manifest.provider_id
            ):
                reasons.append("identity_signer_conformance_provider_mismatch")
            if (
                evidence.identity_signer_conformance.key_id
                != evidence.identity_signer_manifest.key_id
            ):
                reasons.append("identity_signer_conformance_key_mismatch")
            if (
                evidence.identity_signer_conformance.signature_algorithm
                != evidence.identity_signer_manifest.signature_algorithm
            ):
                reasons.append("identity_signer_conformance_algorithm_mismatch")
            if (
                evidence.identity_signer_conformance.implementation_hash
                != evidence.identity_signer_manifest.implementation_hash
            ):
                reasons.append("identity_signer_conformance_implementation_mismatch")
            if (
                evidence.identity_signer_conformance.review_evidence_hash
                != evidence.identity_signer_manifest.review_evidence_hash
            ):
                reasons.append("identity_signer_conformance_review_evidence_mismatch")
        if (
            evidence.identity_signer_kat is not None
            and evidence.identity_signer_conformance.kat_suite_hash
            != evidence.identity_signer_kat.suite_hash
        ):
            reasons.append("identity_signer_conformance_kat_mismatch")
        if (
            evidence.identity_signer_kat is not None
            and evidence.identity_signer_conformance.vector_count
            != evidence.identity_signer_kat.vector_count
        ):
            reasons.append("identity_signer_conformance_vector_count_mismatch")

    if evidence.external_policy_source is None:
        reasons.append("external_policy_source_missing")
    else:
        if requirements.required_external_policy_source_hash is None:
            reasons.append("external_policy_source_hash_requirement_missing")
        elif (
            evidence.external_policy_source.evidence_hash()
            != requirements.required_external_policy_source_hash
        ):
            reasons.append("external_policy_source_hash_mismatch")
        if evidence.policy_snapshot_hash is None:
            reasons.append("policy_snapshot_hash_missing")
        elif evidence.policy_snapshot_hash != evidence.external_policy_source.snapshot_hash:
            reasons.append("external_policy_snapshot_hash_mismatch")
        if requirements.required_policy_snapshot_hash is None:
            reasons.append("policy_snapshot_hash_requirement_missing")
        elif (
            evidence.policy_snapshot_hash is not None
            and evidence.policy_snapshot_hash != requirements.required_policy_snapshot_hash
        ):
            reasons.append("policy_snapshot_hash_requirement_mismatch")
        _evaluate_external_policy_freshness(
            requirements=requirements,
            external_policy_source=evidence.external_policy_source,
            reasons=reasons,
        )

    if evidence.rekey_policy is None:
        reasons.append("rekey_policy_missing")
    else:
        if not evidence.rekey_policy.allowed:
            reasons.append("rekey_policy_failed")
        if evidence.rekey_policy.rollback_evidence_hash is None:
            reasons.append("rekey_rollback_evidence_missing")
        if evidence.rekey_policy.allowed:
            if requirements.required_rekey_rollback_plan_hash is None:
                reasons.append("rekey_rollback_plan_requirement_missing")
            elif evidence.rekey_policy.rollback_plan_hash is None:
                reasons.append("rekey_rollback_plan_hash_missing")
            elif (
                evidence.rekey_policy.rollback_plan_hash
                != requirements.required_rekey_rollback_plan_hash
            ):
                reasons.append("rekey_rollback_plan_mismatch")

    if evidence.rollout_gate is None:
        reasons.append("rollout_gate_missing")
    elif not evidence.rollout_gate.allowed:
        reasons.append("rollout_gate_failed")
    else:
        if requirements.required_rollout_gate_hash is None:
            reasons.append("rollout_gate_hash_requirement_missing")
        elif evidence.rollout_gate.decision_hash() != requirements.required_rollout_gate_hash:
            reasons.append("rollout_gate_hash_mismatch")

    if evidence.source_audit is None:
        reasons.append("firstparty_source_audit_missing")
    else:
        if not evidence.source_audit.passed:
            reasons.append("firstparty_source_audit_failed")
        if requirements.required_source_audit_root_hash is None:
            reasons.append("firstparty_source_audit_root_requirement_missing")
        elif evidence.source_audit.root_hash != requirements.required_source_audit_root_hash:
            reasons.append("firstparty_source_audit_root_mismatch")
        if requirements.required_source_audit_tree_hash is None:
            reasons.append("firstparty_source_audit_tree_requirement_missing")
        elif (
            evidence.source_audit.source_tree_hash
            != requirements.required_source_audit_tree_hash
        ):
            reasons.append("firstparty_source_audit_tree_mismatch")
        _evaluate_source_audit_freshness(
            requirements=requirements,
            source_audit=evidence.source_audit,
            reasons=reasons,
        )

    evidence_hash = hash_identifier(
        json.dumps(
            _readiness_evidence_payload(requirements, evidence, reasons),
            sort_keys=True,
            separators=(",", ":"),
        ),
        namespace="full-vpn-production-readiness",
    )
    return FullVpnProductionReadinessDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        evidence_hash=evidence_hash,
    )


def _readiness_evidence_payload(
    requirements: FullVpnProductionReadinessRequirements,
    evidence: FullVpnProductionReadinessEvidence,
    reasons: list[str],
) -> dict[str, object]:
    payload = {
        "dataplane_validation_hash": (
            evidence.dataplane_validation.evidence_hash()
            if evidence.dataplane_validation is not None
            else None
        ),
        "dataplane_probe_matrix_hash": (
            evidence.dataplane_validation.probe_matrix_hash()
            if evidence.dataplane_validation is not None
            else None
        ),
        "external_policy_source_hash": (
            evidence.external_policy_source.evidence_hash()
            if evidence.external_policy_source is not None
            else None
        ),
        "identity_signer_attestation_hash": (
            evidence.identity_signer_gate.attestation_hash
            if evidence.identity_signer_gate is not None
            else None
        ),
        "identity_signer_kat_suite_hash": (
            evidence.identity_signer_kat.suite_hash
            if evidence.identity_signer_kat is not None
            else None
        ),
        "identity_signer_kat_provider_id_hash": (
            hash_identifier(
                evidence.identity_signer_kat.provider_id,
                namespace="identity-signer-provider",
            )
            if (
                evidence.identity_signer_kat is not None
                and evidence.identity_signer_kat.provider_id
            )
            else None
        ),
        "identity_signer_kat_key_id_hash": (
            hash_identifier(
                evidence.identity_signer_kat.key_id,
                namespace="identity-signer-key",
            )
            if evidence.identity_signer_kat is not None and evidence.identity_signer_kat.key_id
            else None
        ),
        "identity_signer_kat_implementation_hash": (
            evidence.identity_signer_kat.implementation_hash
            if evidence.identity_signer_kat is not None
            else None
        ),
        "identity_signer_conformance_hash": (
            evidence.identity_signer_conformance.evidence_hash()
            if evidence.identity_signer_conformance is not None
            else None
        ),
        "identity_signer_conformance_profile": (
            evidence.identity_signer_conformance.profile
            if evidence.identity_signer_conformance is not None
            else None
        ),
        "identity_signer_kat_vector_count": (
            evidence.identity_signer_kat.vector_count
            if evidence.identity_signer_kat is not None
            else None
        ),
        "identity_signer_kat_captured_at": (
            evidence.identity_signer_kat.captured_at
            if evidence.identity_signer_kat is not None
            else None
        ),
        "identity_signer_manifest_hash": (
            evidence.identity_signer_manifest.manifest_hash()
            if evidence.identity_signer_manifest is not None
            else None
        ),
        "linux_preflight_hash": (
            evidence.linux_preflight.evidence_hash()
            if evidence.linux_preflight is not None
            else None
        ),
        "linux_preflight_apply_plan_hash": (
            evidence.linux_preflight.apply_plan.evidence_hash()
            if evidence.linux_preflight is not None
            else None
        ),
        "linux_preflight_rollback_plan_hash": (
            evidence.linux_preflight.rollback_plan.evidence_hash()
            if evidence.linux_preflight is not None
            else None
        ),
        "leak_protection_hash": (
            evidence.leak_protection.evidence_hash()
            if evidence.leak_protection is not None
            else None
        ),
        "leak_protection_plan_hash": (
            evidence.leak_protection.command_plan.evidence_hash()
            if evidence.leak_protection is not None
            else None
        ),
        "policy_snapshot_hash": evidence.policy_snapshot_hash,
        "mtu_validation_hash": (
            evidence.mtu_validation.evidence_hash()
            if evidence.mtu_validation is not None
            else None
        ),
        "mtu_probe_matrix_hash": (
            evidence.mtu_validation.probe_matrix_hash()
            if evidence.mtu_validation is not None
            else None
        ),
        "pqc_provider_attestation_hash": (
            evidence.pqc_provider_gate.attestation_hash
            if evidence.pqc_provider_gate is not None
            else None
        ),
        "pqc_provider_id_hash": (
            hash_identifier(
                evidence.pqc_provider_gate.provider_id,
                namespace="pqc-provider-id",
            )
            if (
                evidence.pqc_provider_gate is not None
                and evidence.pqc_provider_gate.provider_id
            )
            else None
        ),
        "pqc_provider_implementation_hash": (
            evidence.pqc_provider_gate.implementation_hash
            if evidence.pqc_provider_gate is not None
            else None
        ),
        "pqc_manifest_hash": (
            evidence.pqc_manifest.manifest_hash()
            if evidence.pqc_manifest is not None
            else None
        ),
        "pqc_manifest_provider_id_hash": (
            hash_identifier(
                evidence.pqc_manifest.provider_id,
                namespace="pqc-provider-id",
            )
            if evidence.pqc_manifest is not None
            else None
        ),
        "pqc_manifest_implementation_hash": (
            evidence.pqc_manifest.implementation_hash
            if evidence.pqc_manifest is not None
            else None
        ),
        "pqc_manifest_review_evidence_hash": (
            evidence.pqc_manifest.review_evidence_hash
            if evidence.pqc_manifest is not None
            else None
        ),
        "pqc_kat_suite_hash": (
            evidence.pqc_kat.suite_hash
            if evidence.pqc_kat is not None
            else None
        ),
        "pqc_kat_vector_count": (
            evidence.pqc_kat.vector_count
            if evidence.pqc_kat is not None
            else None
        ),
        "pqc_kat_captured_at": (
            evidence.pqc_kat.captured_at
            if evidence.pqc_kat is not None
            else None
        ),
        "pqc_kat_provider_id_hash": (
            hash_identifier(evidence.pqc_kat.provider_id, namespace="pqc-provider-id")
            if evidence.pqc_kat is not None and evidence.pqc_kat.provider_id
            else None
        ),
        "pqc_kat_implementation_hash": (
            evidence.pqc_kat.implementation_hash
            if evidence.pqc_kat is not None
            else None
        ),
        "reasons": sorted(reasons),
        "rekey_policy_hash": (
            evidence.rekey_policy.evidence_hash
            if evidence.rekey_policy is not None
            else None
        ),
        "rekey_rollback_plan_hash": (
            evidence.rekey_policy.rollback_plan_hash
            if evidence.rekey_policy is not None
            else None
        ),
        "requirements": requirements.to_json_dict(),
        "rollout_gate_hash": (
            evidence.rollout_gate.decision_hash()
            if evidence.rollout_gate is not None
            else None
        ),
        "rollout_gate_evidence_hash": (
            evidence.rollout_gate.evidence_hash
            if evidence.rollout_gate is not None
            else None
        ),
        "source_audit_hash": (
            evidence.source_audit.evidence_hash()
            if evidence.source_audit is not None
            else None
        ),
        "source_audit_captured_at": (
            evidence.source_audit.captured_at
            if evidence.source_audit is not None
            else None
        ),
        "target_hash": hash_identifier(evidence.target, namespace="readiness-target"),
        "tun_dataplane_validation_hash": (
            evidence.tun_dataplane_validation.evidence_hash()
            if evidence.tun_dataplane_validation is not None
            else None
        ),
        "tun_dataplane_probe_matrix_hash": (
            evidence.tun_dataplane_validation.probe_matrix_hash()
            if evidence.tun_dataplane_validation is not None
            else None
        ),
        "zero_trust_policy_hash": (
            evidence.zero_trust_policy.policy_hash
            if evidence.zero_trust_policy is not None
            else None
        ),
        "zero_trust_policy_evidence_hash": (
            evidence.zero_trust_policy.evidence_hash()
            if evidence.zero_trust_policy is not None
            else None
        ),
    }
    assert_privacy_safe(payload)
    return payload


def _evaluate_zero_trust_policy_evidence(
    requirements: FullVpnProductionReadinessRequirements,
    evidence: FullVpnProductionReadinessEvidence,
    reasons: list[str],
) -> None:
    policy = evidence.zero_trust_policy
    if policy is None:
        reasons.append("zero_trust_policy_missing")
        return
    if requirements.required_zero_trust_policy_hash is None:
        reasons.append("zero_trust_policy_hash_requirement_missing")
    elif policy.policy_hash != requirements.required_zero_trust_policy_hash:
        reasons.append("zero_trust_policy_hash_mismatch")
    if policy.allowed_tenant_count < 1:
        reasons.append("zero_trust_tenant_allowlist_missing")
    for workload in sorted(
        requirements.required_zero_trust_workloads - set(policy.allowed_workloads)
    ):
        reasons.append(f"zero_trust_required_workload_missing:{workload}")
    if not policy.required_kem_algorithms:
        reasons.append("zero_trust_pqc_kem_allowlist_missing")
    if not policy.required_signature_algorithms:
        reasons.append("zero_trust_pqc_signature_allowlist_missing")
    for algorithm in policy.required_kem_algorithms:
        if algorithm not in SUPPORTED_KEM_ALGORITHMS:
            reasons.append(f"zero_trust_pqc_kem_not_supported:{algorithm}")
    for algorithm in policy.required_signature_algorithms:
        if algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            reasons.append(f"zero_trust_pqc_signature_not_supported:{algorithm}")
    if (
        policy.max_token_lifetime_seconds
        > requirements.max_identity_token_lifetime_seconds
    ):
        reasons.append("zero_trust_identity_lifetime_too_long")


def _evaluate_linux_command_plan_binding(
    requirements: FullVpnProductionReadinessRequirements,
    evidence: FullVpnProductionReadinessEvidence,
    reasons: list[str],
) -> None:
    if evidence.linux_preflight is None:
        return
    if requirements.required_linux_host_fingerprint is None:
        reasons.append("linux_host_fingerprint_requirement_missing")
    elif (
        evidence.linux_preflight.host_fingerprint
        != requirements.required_linux_host_fingerprint
    ):
        reasons.append("linux_host_fingerprint_mismatch")
    if requirements.required_apply_plan_hash is None:
        reasons.append("apply_plan_hash_requirement_missing")
    elif (
        evidence.linux_preflight.apply_plan.evidence_hash()
        != requirements.required_apply_plan_hash
    ):
        reasons.append("apply_plan_hash_mismatch")
    if requirements.required_rollback_plan_hash is None:
        reasons.append("rollback_plan_hash_requirement_missing")
    elif (
        evidence.linux_preflight.rollback_plan.evidence_hash()
        != requirements.required_rollback_plan_hash
    ):
        reasons.append("rollback_plan_hash_mismatch")


def _evaluate_leak_protection_plan_binding(
    requirements: FullVpnProductionReadinessRequirements,
    evidence: FullVpnProductionReadinessEvidence,
    reasons: list[str],
) -> None:
    if evidence.leak_protection is None:
        return
    if requirements.required_leak_protection_plan_hash is None:
        reasons.append("leak_protection_plan_hash_requirement_missing")
    elif (
        evidence.leak_protection.command_plan.evidence_hash()
        != requirements.required_leak_protection_plan_hash
    ):
        reasons.append("leak_protection_plan_hash_mismatch")


def _evaluate_required_transports(
    *,
    prefix: str,
    required_transports: tuple[tuple[str, DataplaneTransport], ...],
    results: tuple[object, ...],
    reasons: list[str],
) -> None:
    for path_label, transport in required_transports:
        if not any(
            result.success
            and result.path_label == path_label
            and result.transport == transport
            for result in results
        ):
            reasons.append(
                f"{prefix}_required_transport_missing:{path_label}:{transport}"
            )


def _evaluate_freshness(
    *,
    prefix: str,
    captured_at: int,
    requirements: FullVpnProductionReadinessRequirements,
    reasons: list[str],
) -> None:
    if requirements.evaluated_at is None:
        return
    if captured_at > requirements.evaluated_at:
        reasons.append(f"{prefix}_validation_from_future")
        return
    age = requirements.evaluated_at - captured_at
    if age > requirements.max_validation_evidence_age_seconds:
        reasons.append(f"{prefix}_validation_stale")


def _evaluate_external_policy_freshness(
    *,
    requirements: FullVpnProductionReadinessRequirements,
    external_policy_source: ExternalPolicySnapshotSourceEvidence,
    reasons: list[str],
) -> None:
    if external_policy_source.issued_at < 0:
        reasons.append("external_policy_snapshot_time_invalid")
    if external_policy_source.loaded_at < 0:
        reasons.append("external_policy_source_load_time_invalid")
    if external_policy_source.loaded_at < external_policy_source.issued_at:
        reasons.append("external_policy_source_loaded_before_snapshot_issue")
    if requirements.evaluated_at is None:
        return
    if external_policy_source.issued_at > requirements.evaluated_at:
        reasons.append("external_policy_snapshot_from_future")
    if external_policy_source.loaded_at > requirements.evaluated_at:
        reasons.append("external_policy_source_loaded_from_future")
    else:
        source_load_age = requirements.evaluated_at - external_policy_source.loaded_at
        if source_load_age > requirements.max_policy_source_load_age_seconds:
            reasons.append("external_policy_source_load_stale")
    snapshot_age = requirements.evaluated_at - external_policy_source.issued_at
    if snapshot_age > requirements.max_policy_snapshot_age_seconds:
        reasons.append("external_policy_snapshot_stale")


def _evaluate_source_audit_freshness(
    *,
    requirements: FullVpnProductionReadinessRequirements,
    source_audit: FirstPartySourceAuditEvidence,
    reasons: list[str],
) -> None:
    if requirements.evaluated_at is None:
        return
    if source_audit.captured_at > requirements.evaluated_at:
        reasons.append("firstparty_source_audit_from_future")
        return
    age = requirements.evaluated_at - source_audit.captured_at
    if age > requirements.max_source_audit_age_seconds:
        reasons.append("firstparty_source_audit_stale")


def _evaluate_identity_signer_kat_freshness(
    *,
    requirements: FullVpnProductionReadinessRequirements,
    kat: IdentitySignerKatResult,
    reasons: list[str],
) -> None:
    if requirements.evaluated_at is None:
        return
    if kat.captured_at > requirements.evaluated_at:
        reasons.append("identity_signer_kat_from_future")
        return
    age = requirements.evaluated_at - kat.captured_at
    if age > requirements.max_identity_signer_kat_age_seconds:
        reasons.append("identity_signer_kat_stale")


def _evaluate_pqc_kat_freshness(
    *,
    requirements: FullVpnProductionReadinessRequirements,
    kat: PqcKatResult,
    reasons: list[str],
) -> None:
    if requirements.evaluated_at is None:
        return
    if kat.captured_at > requirements.evaluated_at:
        reasons.append("pqc_kat_from_future")
        return
    age = requirements.evaluated_at - kat.captured_at
    if age > requirements.max_pqc_kat_age_seconds:
        reasons.append("pqc_kat_stale")


def _evaluate_identity_signer_kat_binding(
    *,
    gate: ProductionIdentitySignerGateDecision | None,
    manifest: FirstPartyIdentitySignerManifest | None,
    kat: IdentitySignerKatResult,
    reasons: list[str],
) -> None:
    if manifest is not None:
        if not kat.provider_id:
            reasons.append("identity_signer_kat_provider_id_missing")
        elif kat.provider_id != manifest.provider_id:
            reasons.append("identity_signer_kat_provider_mismatch")
        if not kat.key_id:
            reasons.append("identity_signer_kat_key_id_missing")
        elif kat.key_id != manifest.key_id:
            reasons.append("identity_signer_kat_key_mismatch")
        if not kat.signature_algorithm:
            reasons.append("identity_signer_kat_algorithm_missing")
        elif kat.signature_algorithm != manifest.signature_algorithm:
            reasons.append("identity_signer_kat_algorithm_mismatch")
        if not kat.implementation_hash:
            reasons.append("identity_signer_kat_implementation_hash_missing")
        elif kat.implementation_hash != manifest.implementation_hash:
            reasons.append("identity_signer_kat_implementation_mismatch")

    if gate is not None:
        if not gate.provider_id:
            reasons.append("identity_signer_gate_provider_id_missing")
        elif kat.provider_id and gate.provider_id != kat.provider_id:
            reasons.append("identity_signer_gate_kat_provider_mismatch")
        if not gate.key_id:
            reasons.append("identity_signer_gate_key_id_missing")
        elif kat.key_id and gate.key_id != kat.key_id:
            reasons.append("identity_signer_gate_kat_key_mismatch")
        if not gate.signature_algorithm:
            reasons.append("identity_signer_gate_algorithm_missing")
        elif kat.signature_algorithm and gate.signature_algorithm != kat.signature_algorithm:
            reasons.append("identity_signer_gate_kat_algorithm_mismatch")
        if not gate.implementation_hash:
            reasons.append("identity_signer_gate_implementation_hash_missing")
        elif kat.implementation_hash and gate.implementation_hash != kat.implementation_hash:
            reasons.append("identity_signer_gate_kat_implementation_mismatch")


def _evaluate_pqc_manifest_evidence(
    *,
    requirements: FullVpnProductionReadinessRequirements,
    manifest: PqcImplementationManifest,
    gate: PqcProviderGateDecision | None,
    reasons: list[str],
) -> None:
    if requirements.required_pqc_manifest_hash is None:
        reasons.append("pqc_manifest_hash_requirement_missing")
    elif manifest.manifest_hash() != requirements.required_pqc_manifest_hash:
        reasons.append("pqc_manifest_hash_mismatch")
    if manifest.mode != "production":
        reasons.append("pqc_manifest_not_production")
    if not manifest.reviewed:
        reasons.append("pqc_manifest_not_reviewed")
    if gate is not None:
        if gate.attestation_hash != manifest.to_attestation().attestation_hash():
            reasons.append("pqc_manifest_attestation_mismatch")
        if gate.provider_id and gate.provider_id != manifest.provider_id:
            reasons.append("pqc_manifest_provider_mismatch")
        if gate.kem_algorithm and gate.kem_algorithm != manifest.kem_algorithm:
            reasons.append("pqc_manifest_kem_algorithm_mismatch")
        if (
            gate.signature_algorithm
            and gate.signature_algorithm != manifest.signature_algorithm
        ):
            reasons.append("pqc_manifest_signature_algorithm_mismatch")
        if (
            gate.implementation_hash
            and gate.implementation_hash != manifest.implementation_hash
        ):
            reasons.append("pqc_manifest_implementation_mismatch")


def _evaluate_pqc_manifest_kat_binding(
    *,
    manifest: PqcImplementationManifest,
    kat: PqcKatResult,
    reasons: list[str],
) -> None:
    if kat.suite_hash not in manifest.kat_hashes:
        reasons.append("pqc_kat_not_in_manifest")
    if not kat.provider_id:
        reasons.append("pqc_kat_provider_id_missing")
    elif kat.provider_id != manifest.provider_id:
        reasons.append("pqc_kat_provider_mismatch")
    if not kat.kem_algorithm:
        reasons.append("pqc_kat_kem_algorithm_missing")
    elif kat.kem_algorithm != manifest.kem_algorithm:
        reasons.append("pqc_kat_kem_algorithm_mismatch")
    if not kat.signature_algorithm:
        reasons.append("pqc_kat_signature_algorithm_missing")
    elif kat.signature_algorithm != manifest.signature_algorithm:
        reasons.append("pqc_kat_signature_algorithm_mismatch")
    if not kat.implementation_hash:
        reasons.append("pqc_kat_implementation_hash_missing")
    elif kat.implementation_hash != manifest.implementation_hash:
        reasons.append("pqc_kat_implementation_mismatch")


def _evaluate_pqc_gate_kat_binding(
    *,
    gate: PqcProviderGateDecision,
    kat: PqcKatResult,
    reasons: list[str],
) -> None:
    if not gate.provider_id:
        reasons.append("pqc_provider_gate_provider_id_missing")
    elif not kat.provider_id:
        reasons.append("pqc_kat_provider_id_missing")
    elif gate.provider_id != kat.provider_id:
        reasons.append("pqc_provider_gate_kat_provider_mismatch")

    if not gate.kem_algorithm:
        reasons.append("pqc_provider_gate_kem_algorithm_missing")
    elif not kat.kem_algorithm:
        reasons.append("pqc_kat_kem_algorithm_missing")
    elif gate.kem_algorithm != kat.kem_algorithm:
        reasons.append("pqc_provider_gate_kat_kem_algorithm_mismatch")

    if not gate.signature_algorithm:
        reasons.append("pqc_provider_gate_signature_algorithm_missing")
    elif not kat.signature_algorithm:
        reasons.append("pqc_kat_signature_algorithm_missing")
    elif gate.signature_algorithm != kat.signature_algorithm:
        reasons.append("pqc_provider_gate_kat_signature_algorithm_mismatch")

    if not gate.implementation_hash:
        reasons.append("pqc_provider_gate_implementation_hash_missing")
    elif not kat.implementation_hash:
        reasons.append("pqc_kat_implementation_hash_missing")
    elif gate.implementation_hash != kat.implementation_hash:
        reasons.append("pqc_provider_gate_kat_implementation_mismatch")


def _validate_optional_sha256_hex(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if len(value) != 64:
        raise FullVpnProductionReadinessError(f"{field_name} must be sha256 hex")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise FullVpnProductionReadinessError(
            f"{field_name} must be sha256 hex"
        ) from exc
