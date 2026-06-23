"""Production control-plane gates for first-party VPN identity and policy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable, Literal

from .crypto import SUPPORTED_SIGNATURE_ALGORITHMS
from .identity import (
    IdentityAuthority,
    IdentitySignatureProvider,
    IdentitySigningKey,
    LocalIdentitySignatureProvider,
)
from .mldsa import (
    MlDsaShapeError,
    mldsa_parameter_set,
    mldsa_validate_signature,
    mldsa_validate_signing_key,
)
from .ops import assert_privacy_safe, hash_identifier
from .policy_store import PolicySnapshot, PolicyStoreError

ProductionProviderMode = Literal["test", "production"]
IdentitySignerConformanceProfile = Literal["reference", "fips204-production"]


class ProductionControlPlaneError(ValueError):
    """Raised when the production identity or policy boundary fails closed."""


@dataclass(frozen=True)
class FirstPartyIdentitySignerAttestation:
    """Reviewed signer metadata required before production identity issuance."""

    provider_id: str
    key_id: str
    signature_algorithm: str
    mode: ProductionProviderMode
    reviewed: bool
    implementation_hash: str | None
    issued_at: int
    expires_at: int | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ProductionControlPlaneError("unsupported identity signer attestation version")
        if not self.provider_id.strip():
            raise ProductionControlPlaneError("identity signer provider id is required")
        if not self.key_id.strip():
            raise ProductionControlPlaneError("identity signer key id is required")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ProductionControlPlaneError("unsupported identity signer algorithm")
        if self.mode not in ("test", "production"):
            raise ProductionControlPlaneError("identity signer mode must be test or production")
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise ProductionControlPlaneError("identity signer validity window is invalid")

    def active_at(self, now: int) -> bool:
        if now < self.issued_at:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def attestation_hash(self) -> str:
        return hashlib.sha256(
            _canonical_json(self._hash_payload())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "attestation_hash": self.attestation_hash(),
            "expires_at": self.expires_at,
            "implementation_hash": self.implementation_hash,
            "issued_at": self.issued_at,
            "key_id_hash": hash_identifier(self.key_id, namespace="identity-signer-key"),
            "mode": self.mode,
            "provider_id_hash": hash_identifier(
                self.provider_id,
                namespace="identity-signer-provider",
            ),
            "reviewed": self.reviewed,
            "signature_algorithm": self.signature_algorithm,
            "version": self.version,
        }
        assert_privacy_safe(payload)
        return payload

    def _hash_payload(self) -> dict[str, object]:
        return {
            "expires_at": self.expires_at,
            "implementation_hash": self.implementation_hash,
            "issued_at": self.issued_at,
            "key_id": self.key_id,
            "mode": self.mode,
            "provider_id": self.provider_id,
            "reviewed": self.reviewed,
            "signature_algorithm": self.signature_algorithm,
            "version": self.version,
        }


@dataclass(frozen=True)
class ProductionIdentitySignerGateDecision:
    allowed: bool
    reasons: tuple[str, ...]
    attestation_hash: str
    provider_id: str = ""
    key_id: str = ""
    signature_algorithm: str = ""
    implementation_hash: str = ""

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "allowed": self.allowed,
            "attestation_hash": self.attestation_hash,
            "implementation_hash": self.implementation_hash,
            "key_id_hash": (
                hash_identifier(self.key_id, namespace="identity-signer-key")
                if self.key_id
                else None
            ),
            "provider_id_hash": (
                hash_identifier(
                    self.provider_id,
                    namespace="identity-signer-provider",
                )
                if self.provider_id
                else None
            ),
            "reasons": list(self.reasons),
            "signature_algorithm": self.signature_algorithm,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class ProductionIdentitySignerGate:
    """Fail-closed production gate for reviewed ML-DSA identity signers."""

    require_production: bool = True
    trusted_provider_ids: frozenset[str] = frozenset()
    trusted_implementation_hashes: frozenset[str] = frozenset()

    def evaluate(
        self,
        attestation: FirstPartyIdentitySignerAttestation,
        *,
        signing_key: IdentitySigningKey,
        now: int | None = None,
    ) -> ProductionIdentitySignerGateDecision:
        now = now if now is not None else _utc_now()
        reasons: list[str] = []
        if signing_key.key_id != attestation.key_id:
            reasons.append("identity_signer_key_id_mismatch")
        if signing_key.signature_algorithm != attestation.signature_algorithm:
            reasons.append("identity_signer_algorithm_mismatch")
        if not signing_key.active_at(now):
            reasons.append("identity_signing_key_not_active")
        if not attestation.active_at(now):
            reasons.append("identity_signer_attestation_not_active")
        if self.require_production:
            try:
                mldsa_validate_signing_key(
                    signing_key.signature_algorithm,
                    signing_key.secret,
                )
            except MlDsaShapeError:
                try:
                    expected_length = mldsa_parameter_set(
                        signing_key.signature_algorithm
                    ).signing_key_bytes
                except MlDsaShapeError:
                    expected_length = -1
                if len(signing_key.secret) != expected_length:
                    reasons.append("identity_signing_key_length_invalid")
                else:
                    reasons.append("identity_signing_key_format_invalid")
            if attestation.mode != "production":
                reasons.append("identity_signer_not_production")
            if not attestation.reviewed:
                reasons.append("identity_signer_not_reviewed")
            if not attestation.implementation_hash:
                reasons.append("identity_signer_implementation_hash_missing")
            if (
                self.trusted_provider_ids
                and attestation.provider_id not in self.trusted_provider_ids
            ):
                reasons.append("identity_signer_provider_not_trusted")
            if (
                self.trusted_implementation_hashes
                and attestation.implementation_hash
                not in self.trusted_implementation_hashes
            ):
                reasons.append("identity_signer_implementation_not_trusted")
        return ProductionIdentitySignerGateDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
            attestation_hash=attestation.attestation_hash(),
            provider_id=attestation.provider_id,
            key_id=attestation.key_id,
            signature_algorithm=attestation.signature_algorithm,
            implementation_hash=attestation.implementation_hash or "",
        )


@dataclass(frozen=True)
class IdentitySignerKnownAnswerVector:
    """Hashed KAT vector for a first-party identity signature provider."""

    vector_id: str
    key_id: str
    signature_algorithm: str
    payload: bytes
    expected_signature_hash: str

    def __post_init__(self) -> None:
        if not self.vector_id.strip():
            raise ProductionControlPlaneError("identity signer KAT vector id is required")
        if not self.key_id.strip():
            raise ProductionControlPlaneError("identity signer KAT key id is required")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ProductionControlPlaneError("unsupported identity signer KAT algorithm")
        if not self.payload:
            raise ProductionControlPlaneError("identity signer KAT payload is required")
        _assert_sha256_hex(self.expected_signature_hash, "expected_signature_hash")

    def vector_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "expected_signature_hash": self.expected_signature_hash,
            "key_id": self.key_id,
            "payload_hash": hashlib.sha256(self.payload).hexdigest(),
            "signature_algorithm": self.signature_algorithm,
            "vector_id": self.vector_id,
            "version": 1,
        }


@dataclass(frozen=True)
class IdentitySignerKatResult:
    """Result of first-party identity signer known-answer tests."""

    passed: bool
    reasons: tuple[str, ...]
    suite_hash: str
    vector_count: int
    captured_at: int = 0
    provider_id: str = ""
    key_id: str = ""
    signature_algorithm: str = ""
    implementation_hash: str = ""

    def __post_init__(self) -> None:
        if self.captured_at < 0:
            raise ProductionControlPlaneError("identity signer KAT time is invalid")


@dataclass(frozen=True)
class IdentitySignerConformanceEvidence:
    """Reviewed algorithm-conformance evidence for one identity signer build."""

    provider_id: str
    key_id: str
    signature_algorithm: str
    implementation_hash: str
    manifest_hash: str
    kat_suite_hash: str
    profile: IdentitySignerConformanceProfile
    passed: bool
    vector_count: int
    review_evidence_hash: str
    reasons: tuple[str, ...] = ()
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ProductionControlPlaneError(
                "unsupported identity signer conformance evidence version"
            )
        if not self.provider_id.strip():
            raise ProductionControlPlaneError(
                "identity signer conformance provider id is required"
            )
        if not self.key_id.strip():
            raise ProductionControlPlaneError(
                "identity signer conformance key id is required"
            )
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ProductionControlPlaneError(
                "unsupported identity signer conformance algorithm"
            )
        if self.profile not in ("reference", "fips204-production"):
            raise ProductionControlPlaneError(
                "identity signer conformance profile is invalid"
            )
        if self.vector_count < 0:
            raise ProductionControlPlaneError(
                "identity signer conformance vector count is invalid"
            )
        for value, field_name in (
            (self.implementation_hash, "implementation_hash"),
            (self.manifest_hash, "manifest_hash"),
            (self.kat_suite_hash, "kat_suite_hash"),
            (self.review_evidence_hash, "review_evidence_hash"),
        ):
            _assert_sha256_hex(value, field_name)
        if self.passed and self.reasons:
            raise ProductionControlPlaneError(
                "passed identity signer conformance evidence cannot have reasons"
            )
        if not self.passed and not self.reasons:
            raise ProductionControlPlaneError(
                "failed identity signer conformance evidence requires reasons"
            )

    def evidence_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "evidence_hash": self.evidence_hash(),
            "implementation_hash": self.implementation_hash,
            "kat_suite_hash": self.kat_suite_hash,
            "key_id_hash": hash_identifier(
                self.key_id,
                namespace="identity-signer-conformance-key",
            ),
            "manifest_hash": self.manifest_hash,
            "passed": self.passed,
            "profile": self.profile,
            "provider_id_hash": hash_identifier(
                self.provider_id,
                namespace="identity-signer-conformance-provider",
            ),
            "reasons": list(self.reasons),
            "review_evidence_hash": self.review_evidence_hash,
            "signature_algorithm": self.signature_algorithm,
            "vector_count": self.vector_count,
            "version": self.version,
        }
        assert_privacy_safe(payload)
        return payload

    def _hash_payload(self) -> dict[str, object]:
        return {
            "implementation_hash": self.implementation_hash,
            "kat_suite_hash": self.kat_suite_hash,
            "key_id": self.key_id,
            "manifest_hash": self.manifest_hash,
            "passed": self.passed,
            "profile": self.profile,
            "provider_id": self.provider_id,
            "reasons": list(self.reasons),
            "review_evidence_hash": self.review_evidence_hash,
            "signature_algorithm": self.signature_algorithm,
            "vector_count": self.vector_count,
            "version": self.version,
        }


def run_identity_signer_known_answer_tests(
    signature_provider: IdentitySignatureProvider,
    signing_key: IdentitySigningKey,
    vectors: tuple[IdentitySignerKnownAnswerVector, ...],
    *,
    captured_at: int | None = None,
) -> IdentitySignerKatResult:
    collected_at = _utc_now() if captured_at is None else captured_at
    if collected_at < 0:
        raise ProductionControlPlaneError("identity signer KAT time is invalid")
    reasons: list[str] = []
    if not vectors:
        reasons.append("identity_signer_kat_vectors_missing")
    for vector in vectors:
        if vector.key_id != signing_key.key_id:
            reasons.append(f"{vector.vector_id}:identity_signer_kat_key_mismatch")
            continue
        if vector.signature_algorithm != signing_key.signature_algorithm:
            reasons.append(f"{vector.vector_id}:identity_signer_kat_algorithm_mismatch")
            continue
        try:
            signature = signature_provider.sign(signing_key, vector.payload)
        except Exception:
            reasons.append(f"{vector.vector_id}:identity_signer_kat_sign_failed")
            continue
        reasons.extend(
            f"{vector.vector_id}:{reason}"
            for reason in _identity_signature_shape_reasons(
                signing_key.signature_algorithm,
                signature,
            )
        )
        if hashlib.sha256(signature).hexdigest() != vector.expected_signature_hash:
            reasons.append(f"{vector.vector_id}:identity_signer_kat_signature_mismatch")
        try:
            verified = signature_provider.verify(signing_key, vector.payload, signature)
        except Exception:
            reasons.append(f"{vector.vector_id}:identity_signer_kat_verify_failed")
        else:
            if not verified:
                reasons.append(f"{vector.vector_id}:identity_signer_kat_verify_failed")
    return IdentitySignerKatResult(
        passed=not reasons,
        reasons=tuple(reasons),
        suite_hash=_identity_signer_kat_suite_hash(vectors),
        vector_count=len(vectors),
        captured_at=collected_at,
        provider_id=str(getattr(signature_provider, "provider_id", "")),
        key_id=signing_key.key_id,
        signature_algorithm=signing_key.signature_algorithm,
        implementation_hash=str(getattr(signature_provider, "implementation_hash", "")),
    )


@dataclass(frozen=True)
class FirstPartyIdentitySignerManifest:
    """Reviewed implementation metadata for production identity signers."""

    provider_id: str
    key_id: str
    signature_algorithm: str
    mode: ProductionProviderMode
    reviewed: bool
    implementation_hash: str
    source_hashes: tuple[str, ...]
    kat_hashes: tuple[str, ...]
    review_evidence_hash: str
    issued_at: int
    expires_at: int | None = None
    version: int = 1

    def __post_init__(self) -> None:
        if self.version != 1:
            raise ProductionControlPlaneError("unsupported identity signer manifest version")
        if not self.provider_id.strip():
            raise ProductionControlPlaneError("identity signer manifest provider id is required")
        if not self.key_id.strip():
            raise ProductionControlPlaneError("identity signer manifest key id is required")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ProductionControlPlaneError("unsupported identity signer manifest algorithm")
        if self.mode not in ("test", "production"):
            raise ProductionControlPlaneError("identity signer manifest mode must be test or production")
        _assert_sha256_hex(self.implementation_hash, "implementation_hash")
        if not self.source_hashes:
            raise ProductionControlPlaneError("identity signer manifest source hashes are required")
        if not self.kat_hashes:
            raise ProductionControlPlaneError("identity signer manifest KAT hashes are required")
        _assert_sha256_hex(self.review_evidence_hash, "review_evidence_hash")
        for item in (*self.source_hashes, *self.kat_hashes):
            _assert_sha256_hex(item, "identity signer manifest evidence hash")
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise ProductionControlPlaneError("identity signer manifest validity window is invalid")

    def active_at(self, now: int) -> bool:
        if now < self.issued_at:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def to_attestation(self) -> FirstPartyIdentitySignerAttestation:
        return FirstPartyIdentitySignerAttestation(
            provider_id=self.provider_id,
            key_id=self.key_id,
            signature_algorithm=self.signature_algorithm,
            mode=self.mode,
            reviewed=self.reviewed,
            implementation_hash=self.implementation_hash,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "expires_at": self.expires_at,
            "implementation_hash": self.implementation_hash,
            "issued_at": self.issued_at,
            "kat_hashes": list(self.kat_hashes),
            "key_id": self.key_id,
            "manifest_hash": self.manifest_hash(),
            "mode": self.mode,
            "provider_id": self.provider_id,
            "review_evidence_hash": self.review_evidence_hash,
            "reviewed": self.reviewed,
            "signature_algorithm": self.signature_algorithm,
            "source_hashes": list(self.source_hashes),
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "FirstPartyIdentitySignerManifest":
        manifest = cls(
            version=int(value.get("version", 0)),
            provider_id=str(value.get("provider_id", "")),
            key_id=str(value.get("key_id", "")),
            signature_algorithm=str(value.get("signature_algorithm", "")),
            mode=str(value.get("mode", "")),  # type: ignore[arg-type]
            reviewed=bool(value.get("reviewed", False)),
            implementation_hash=str(value.get("implementation_hash", "")),
            source_hashes=_string_tuple(value, "source_hashes"),
            kat_hashes=_string_tuple(value, "kat_hashes"),
            review_evidence_hash=str(value.get("review_evidence_hash", "")),
            issued_at=int(value.get("issued_at", 0)),
            expires_at=(
                None
                if value.get("expires_at") is None
                else int(value.get("expires_at", 0))
            ),
        )
        if value.get("manifest_hash") != manifest.manifest_hash():
            raise ProductionControlPlaneError("identity signer manifest hash mismatch")
        return manifest

    def manifest_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "expires_at": self.expires_at,
            "implementation_hash": self.implementation_hash,
            "issued_at": self.issued_at,
            "kat_hashes": sorted(self.kat_hashes),
            "key_id": self.key_id,
            "mode": self.mode,
            "provider_id": self.provider_id,
            "review_evidence_hash": self.review_evidence_hash,
            "reviewed": self.reviewed,
            "signature_algorithm": self.signature_algorithm,
            "source_hashes": sorted(self.source_hashes),
            "version": self.version,
        }


class DurableIdentitySignerManifestStore:
    """Atomic JSON store for reviewed identity signer manifests."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def save_all(self, manifests: tuple[FirstPartyIdentitySignerManifest, ...]) -> None:
        if not manifests:
            raise ProductionControlPlaneError("identity signer manifest store cannot be empty")
        payload = {
            "bundle_hash": _identity_signer_manifest_bundle_hash(manifests),
            "manifests": [manifest.to_json_dict() for manifest in manifests],
            "version": 1,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_bytes(_canonical_json(payload) + b"\n")
        tmp.replace(self.path)

    def load_all(self) -> tuple[FirstPartyIdentitySignerManifest, ...]:
        if not self.path.exists():
            raise ProductionControlPlaneError("identity signer manifest store is missing")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProductionControlPlaneError("identity signer manifest store JSON is invalid") from exc
        if not isinstance(raw, dict):
            raise ProductionControlPlaneError("identity signer manifest store root must be a map")
        if int(raw.get("version", 0)) != 1:
            raise ProductionControlPlaneError("unsupported identity signer manifest store version")
        manifests_raw = raw.get("manifests", [])
        if not isinstance(manifests_raw, list):
            raise ProductionControlPlaneError("identity signer manifest list must be a list")
        manifests = tuple(
            FirstPartyIdentitySignerManifest.from_json_dict(item)
            for item in manifests_raw
            if isinstance(item, dict)
        )
        if len(manifests) != len(manifests_raw):
            raise ProductionControlPlaneError("identity signer manifest list contains non-map entries")
        if raw.get("bundle_hash") != _identity_signer_manifest_bundle_hash(manifests):
            raise ProductionControlPlaneError("identity signer manifest bundle hash mismatch")
        return manifests

    def find(
        self,
        *,
        provider_id: str,
        implementation_hash: str,
        key_id: str,
    ) -> FirstPartyIdentitySignerManifest | None:
        for manifest in self.load_all():
            if (
                manifest.provider_id == provider_id
                and manifest.implementation_hash == implementation_hash
                and manifest.key_id == key_id
            ):
                return manifest
        return None


class ManifestBackedIdentitySignatureProvider:
    """Identity signer wrapper that refuses to start without manifest KAT evidence."""

    def __init__(
        self,
        *,
        signature_provider: IdentitySignatureProvider,
        signing_key: IdentitySigningKey,
        manifest: FirstPartyIdentitySignerManifest,
        kat_vectors: tuple[IdentitySignerKnownAnswerVector, ...],
        kat_captured_at: int | None = None,
    ) -> None:
        if isinstance(signature_provider, LocalIdentitySignatureProvider):
            raise ProductionControlPlaneError("identity signer local provider forbidden")
        self.signature_provider = signature_provider
        self.signing_key = signing_key
        self.manifest = manifest
        self._validate_manifest_binding()
        kat_result = run_identity_signer_known_answer_tests(
            signature_provider,
            signing_key,
            kat_vectors,
            captured_at=kat_captured_at,
        )
        if not kat_result.passed:
            raise ProductionControlPlaneError("identity signer KAT failed")
        if kat_result.suite_hash not in manifest.kat_hashes:
            raise ProductionControlPlaneError("identity signer KAT suite is not present in manifest")
        self.kat_result = IdentitySignerKatResult(
            passed=kat_result.passed,
            reasons=kat_result.reasons,
            suite_hash=kat_result.suite_hash,
            vector_count=kat_result.vector_count,
            captured_at=kat_result.captured_at,
            provider_id=manifest.provider_id,
            key_id=manifest.key_id,
            signature_algorithm=manifest.signature_algorithm,
            implementation_hash=manifest.implementation_hash,
        )
        self.attestation = manifest.to_attestation()

    def sign(self, key: IdentitySigningKey, payload: bytes) -> bytes:
        self._validate_key_binding(key)
        return self.signature_provider.sign(key, payload)

    def verify(
        self,
        key: IdentitySigningKey,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        self._validate_key_binding(key)
        return self.signature_provider.verify(key, payload, signature)

    def _validate_manifest_binding(self) -> None:
        if self.manifest.key_id != self.signing_key.key_id:
            raise ProductionControlPlaneError("identity signer manifest key id mismatch")
        if self.manifest.signature_algorithm != self.signing_key.signature_algorithm:
            raise ProductionControlPlaneError("identity signer manifest algorithm mismatch")

    def _validate_key_binding(self, key: IdentitySigningKey) -> None:
        if key.key_id != self.signing_key.key_id:
            raise ProductionControlPlaneError("identity signer key id mismatch")
        if key.signature_algorithm != self.signing_key.signature_algorithm:
            raise ProductionControlPlaneError("identity signer algorithm mismatch")


def create_production_identity_authority(
    *,
    issuer: str,
    policy_epoch: str,
    signing_key: IdentitySigningKey,
    signature_provider: IdentitySignatureProvider,
    signer_attestation: FirstPartyIdentitySignerAttestation,
    gate: ProductionIdentitySignerGate,
    default_lifetime_seconds: int = 600,
    max_lifetime_seconds: int = 3600,
    max_kat_age_seconds: int = 3600,
    now: int | None = None,
) -> IdentityAuthority:
    """Create an identity authority only when production signer evidence passes."""
    if max_kat_age_seconds < 1:
        raise ProductionControlPlaneError("identity signer KAT max age must be positive")
    evaluated_at = now if now is not None else _utc_now()
    decision = gate.evaluate(signer_attestation, signing_key=signing_key, now=evaluated_at)
    reasons = list(decision.reasons)
    if isinstance(signature_provider, LocalIdentitySignatureProvider):
        reasons.append("identity_signer_local_provider_forbidden")
    if gate.require_production and not isinstance(
        signature_provider,
        ManifestBackedIdentitySignatureProvider,
    ):
        reasons.append("identity_signer_manifest_wrapper_required")
    if isinstance(signature_provider, ManifestBackedIdentitySignatureProvider):
        reasons.extend(
            _manifest_backed_identity_signer_kat_reasons(
                signature_provider,
                signer_attestation=signer_attestation,
                gate_decision=decision,
                signing_key=signing_key,
                now=evaluated_at,
                max_kat_age_seconds=max_kat_age_seconds,
            )
        )
    reasons.extend(
        _identity_signature_provider_shape_reasons(
            signature_provider,
            signing_key=signing_key,
        )
    )
    if reasons:
        raise ProductionControlPlaneError(
            "production identity signer gate rejected: " + ",".join(reasons)
        )
    return IdentityAuthority(
        issuer=issuer,
        policy_epoch=policy_epoch,
        signing_keys=(signing_key,),
        active_key_id=signing_key.key_id,
        signature_provider=signature_provider,
        default_lifetime_seconds=default_lifetime_seconds,
        max_lifetime_seconds=max_lifetime_seconds,
    )


def _identity_signature_provider_shape_reasons(
    signature_provider: IdentitySignatureProvider,
    *,
    signing_key: IdentitySigningKey,
) -> tuple[str, ...]:
    probe_payload = _canonical_json(
        {
            "key_id": signing_key.key_id,
            "purpose": "x0vpn-production-identity-signer-shape-probe-v1",
            "signature_algorithm": signing_key.signature_algorithm,
        }
    )
    try:
        signature = signature_provider.sign(signing_key, probe_payload)
    except Exception:
        return ("identity_signer_probe_sign_failed",)
    reasons: list[str] = []
    reasons.extend(
        _identity_signature_shape_reasons(
            signing_key.signature_algorithm,
            signature,
        )
    )
    try:
        verified = signature_provider.verify(signing_key, probe_payload, signature)
    except Exception:
        reasons.append("identity_signer_probe_verify_failed")
    else:
        if not verified:
            reasons.append("identity_signer_probe_verify_failed")
    return tuple(reasons)


def _manifest_backed_identity_signer_kat_reasons(
    signature_provider: ManifestBackedIdentitySignatureProvider,
    *,
    signer_attestation: FirstPartyIdentitySignerAttestation,
    gate_decision: ProductionIdentitySignerGateDecision,
    signing_key: IdentitySigningKey,
    now: int,
    max_kat_age_seconds: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    manifest = signature_provider.manifest
    kat = signature_provider.kat_result
    if signature_provider.attestation.attestation_hash() != signer_attestation.attestation_hash():
        reasons.append("identity_signer_wrapper_attestation_mismatch")
    if not kat.passed:
        reasons.append("identity_signer_kat_failed")
    if kat.vector_count < 1:
        reasons.append("identity_signer_kat_vectors_missing")
    if kat.suite_hash not in manifest.kat_hashes:
        reasons.append("identity_signer_kat_not_in_manifest")
    if kat.provider_id != manifest.provider_id:
        reasons.append("identity_signer_kat_provider_mismatch")
    if kat.key_id != manifest.key_id:
        reasons.append("identity_signer_kat_key_mismatch")
    if kat.signature_algorithm != manifest.signature_algorithm:
        reasons.append("identity_signer_kat_algorithm_mismatch")
    if kat.implementation_hash != manifest.implementation_hash:
        reasons.append("identity_signer_kat_implementation_mismatch")
    if gate_decision.provider_id and kat.provider_id != gate_decision.provider_id:
        reasons.append("identity_signer_gate_kat_provider_mismatch")
    if gate_decision.key_id and kat.key_id != gate_decision.key_id:
        reasons.append("identity_signer_gate_kat_key_mismatch")
    if (
        gate_decision.signature_algorithm
        and kat.signature_algorithm != gate_decision.signature_algorithm
    ):
        reasons.append("identity_signer_gate_kat_algorithm_mismatch")
    if (
        gate_decision.implementation_hash
        and kat.implementation_hash != gate_decision.implementation_hash
    ):
        reasons.append("identity_signer_gate_kat_implementation_mismatch")
    if signing_key.key_id != manifest.key_id:
        reasons.append("identity_signer_wrapper_key_mismatch")
    if signing_key.signature_algorithm != manifest.signature_algorithm:
        reasons.append("identity_signer_wrapper_algorithm_mismatch")
    if kat.captured_at > now:
        reasons.append("identity_signer_kat_from_future")
    elif now - kat.captured_at > max_kat_age_seconds:
        reasons.append("identity_signer_kat_stale")
    return tuple(dict.fromkeys(reasons))


@dataclass(frozen=True)
class ExternalPolicySnapshotSourceEvidence:
    """Privacy-safe evidence for one externally loaded policy snapshot."""

    source_id_hash: str
    source_path_hash: str
    source_document_hash: str
    snapshot_hash: str
    policy_epoch_hash: str
    issued_at: int
    loaded_at: int

    def __post_init__(self) -> None:
        for field_name in (
            "source_id_hash",
            "source_path_hash",
            "source_document_hash",
            "snapshot_hash",
            "policy_epoch_hash",
        ):
            _assert_sha256_hex(getattr(self, field_name), field_name)
        assert_privacy_safe(self.to_json_dict())

    def evidence_hash(self) -> str:
        return hash_identifier(
            json.dumps(self.to_json_dict(), sort_keys=True, separators=(",", ":")),
            namespace="external-policy-source-evidence",
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "issued_at": self.issued_at,
            "loaded_at": self.loaded_at,
            "policy_epoch_hash": self.policy_epoch_hash,
            "snapshot_hash": self.snapshot_hash,
            "source_document_hash": self.source_document_hash,
            "source_id_hash": self.source_id_hash,
            "source_path_hash": self.source_path_hash,
        }


class ExternalPolicySnapshotSource:
    """Validated external source for production policy snapshots."""

    def __init__(
        self,
        *,
        source_id: str,
        path: Path | str,
        expected_snapshot_hash: str | None = None,
        allowed_policy_epochs: frozenset[str] = frozenset(),
        minimum_issued_at: int = 0,
        now_provider: Callable[[], int] | None = None,
    ) -> None:
        if not source_id.strip():
            raise ValueError("external policy source id is required")
        if minimum_issued_at < 0:
            raise ValueError("external policy source minimum_issued_at is invalid")
        self.source_id = source_id
        self.path = Path(path)
        self.expected_snapshot_hash = expected_snapshot_hash
        self.allowed_policy_epochs = frozenset(allowed_policy_epochs)
        self.minimum_issued_at = minimum_issued_at
        self.now_provider = now_provider or _utc_now
        self.last_evidence: ExternalPolicySnapshotSourceEvidence | None = None

    def __call__(self) -> PolicySnapshot:
        return self.load()

    def load(self) -> PolicySnapshot:
        try:
            document = self.path.read_bytes()
        except OSError as exc:
            raise ProductionControlPlaneError("external policy source is unavailable") from exc
        source_document_hash = hashlib.sha256(document).hexdigest()
        try:
            raw = json.loads(document.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProductionControlPlaneError("external policy source JSON is invalid") from exc
        if not isinstance(raw, dict):
            raise ProductionControlPlaneError("external policy source root must be a map")
        expected_hash = raw.get("snapshot_hash")
        try:
            snapshot = PolicySnapshot.from_json_dict(raw)
        except (PolicyStoreError, ValueError) as exc:
            raise ProductionControlPlaneError("external policy snapshot is invalid") from exc
        snapshot_hash = snapshot.snapshot_hash()
        if expected_hash != snapshot_hash:
            raise ProductionControlPlaneError("external policy snapshot hash mismatch")
        if (
            self.expected_snapshot_hash is not None
            and self.expected_snapshot_hash != snapshot_hash
        ):
            raise ProductionControlPlaneError("external policy snapshot unexpected hash")
        if snapshot.issued_at < self.minimum_issued_at:
            raise ProductionControlPlaneError("external policy snapshot is stale")
        if self.allowed_policy_epochs and snapshot.policy_epoch not in self.allowed_policy_epochs:
            raise ProductionControlPlaneError("external policy epoch is not allowed")
        evidence = ExternalPolicySnapshotSourceEvidence(
            source_id_hash=hash_identifier(self.source_id, namespace="policy-source-id"),
            source_path_hash=hash_identifier(str(self.path), namespace="policy-source-path"),
            source_document_hash=source_document_hash,
            snapshot_hash=snapshot_hash,
            policy_epoch_hash=hash_identifier(
                snapshot.policy_epoch,
                namespace="policy-epoch",
            ),
            issued_at=snapshot.issued_at,
            loaded_at=self.now_provider(),
        )
        self.last_evidence = evidence
        return snapshot


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _identity_signature_shape_reasons(
    signature_algorithm: str,
    signature: bytes,
) -> tuple[str, ...]:
    try:
        mldsa_validate_signature(signature_algorithm, signature)
    except MlDsaShapeError:
        try:
            expected_length = mldsa_parameter_set(signature_algorithm).signature_bytes
        except MlDsaShapeError:
            expected_length = -1
        if len(signature) != expected_length:
            return ("identity_signature_length_invalid",)
        return ("identity_signature_format_invalid",)
    return ()


def _identity_signer_kat_suite_hash(
    vectors: tuple[IdentitySignerKnownAnswerVector, ...],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "vector_hashes": [vector.vector_hash() for vector in vectors],
                "version": 1,
            }
        )
    ).hexdigest()


def _identity_signer_manifest_bundle_hash(
    manifests: tuple[FirstPartyIdentitySignerManifest, ...],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "manifest_hashes": sorted(
                    manifest.manifest_hash() for manifest in manifests
                ),
                "version": 1,
            }
        )
    ).hexdigest()


def _string_tuple(value: dict[str, object], key: str) -> tuple[str, ...]:
    items = value.get(key, [])
    if not isinstance(items, list):
        raise ProductionControlPlaneError(f"{key} must be a list")
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            raise ProductionControlPlaneError(f"{key} entries must be strings")
        out.append(item)
    return tuple(out)


def _assert_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64 or not all(character in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a sha256 hex digest")


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
