"""PQC provider boundary for first-party VPN session admission."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
from typing import Literal, Protocol

from .crypto import (
    MIN_SECRET_BYTES,
    SUPPORTED_KEM_ALGORITHMS,
    SUPPORTED_SIGNATURE_ALGORITHMS,
)
from .mlkem import (
    ML_KEM_PARAMETER_SETS,
    ML_KEM_SEED_BYTES,
    MlKemPrimitiveError,
    mlkem_decapsulate,
    mlkem_encapsulate,
    mlkem_encapsulate_from_message,
    mlkem_hash_h,
    mlkem_parameter_set,
)

PqcProviderMode = Literal["test", "production"]


class PqcProviderError(ValueError):
    """Raised when a PQC provider cannot be used for session admission."""


@dataclass(frozen=True)
class PqcKemProfile:
    """FIPS-style output shape for one supported ML-KEM parameter set."""

    kem_algorithm: str
    security_category: int
    encapsulation_key_bytes: int
    decapsulation_key_bytes: int
    ciphertext_bytes: int
    shared_secret_bytes: int = MIN_SECRET_BYTES


ML_KEM_PROFILES: dict[str, PqcKemProfile] = {
    name: PqcKemProfile(
        kem_algorithm=params.name,
        security_category=params.security_category,
        encapsulation_key_bytes=params.encapsulation_key_bytes,
        decapsulation_key_bytes=params.decapsulation_key_bytes,
        ciphertext_bytes=params.ciphertext_bytes,
        shared_secret_bytes=params.shared_secret_bytes,
    )
    for name, params in ML_KEM_PARAMETER_SETS.items()
}


def pqc_kem_profile(kem_algorithm: str) -> PqcKemProfile:
    """Return the strict output profile for a supported ML-KEM algorithm."""
    try:
        return ML_KEM_PROFILES[kem_algorithm]
    except KeyError as exc:
        raise PqcProviderError("unsupported PQC KEM profile") from exc


@dataclass(frozen=True)
class PqcProviderAttestation:
    """Provider metadata used by the production gate."""

    provider_id: str
    kem_algorithm: str
    signature_algorithm: str
    mode: PqcProviderMode
    reviewed: bool
    issued_at: int
    expires_at: int | None = None
    implementation_hash: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("PQC provider id is required")
        if self.kem_algorithm not in SUPPORTED_KEM_ALGORITHMS:
            raise ValueError("unsupported PQC KEM algorithm")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ValueError("unsupported PQC signature algorithm")
        if self.mode not in ("test", "production"):
            raise ValueError("PQC provider mode must be test or production")
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise ValueError("PQC provider attestation validity window is invalid")

    def active_at(self, now: int) -> bool:
        if now < self.issued_at:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def attestation_hash(self) -> str:
        parts = "|".join(
            (
                self.provider_id,
                self.kem_algorithm,
                self.signature_algorithm,
                self.mode,
                "reviewed" if self.reviewed else "unreviewed",
                str(self.issued_at),
                str(self.expires_at or ""),
                self.implementation_hash or "",
            )
        )
        return hashlib.sha256(f"x0vpn-pqc-attestation-v1|{parts}".encode()).hexdigest()


@dataclass(frozen=True)
class PqcSessionSecretMaterial:
    """PQC output consumed by the first-party session key schedule."""

    kem_algorithm: str
    signature_algorithm: str
    shared_secret: bytes
    ciphertext: bytes
    attestation: PqcProviderAttestation
    kat_result: "PqcKatResult | None" = None

    def __post_init__(self) -> None:
        if self.kem_algorithm != self.attestation.kem_algorithm:
            raise ValueError("PQC KEM algorithm does not match provider attestation")
        if self.signature_algorithm != self.attestation.signature_algorithm:
            raise ValueError("PQC signature algorithm does not match provider attestation")
        if len(self.shared_secret) < MIN_SECRET_BYTES:
            raise ValueError("PQC shared secret is too short")
        if not self.ciphertext:
            raise ValueError("PQC ciphertext evidence is required")


class PqcProvider(Protocol):
    attestation: PqcProviderAttestation

    def create_session_material(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcSessionSecretMaterial: ...


@dataclass(frozen=True)
class PqcEncapsulationResult:
    """Output from a first-party PQC algorithm implementation."""

    shared_secret: bytes
    ciphertext: bytes

    def __post_init__(self) -> None:
        if len(self.shared_secret) < MIN_SECRET_BYTES:
            raise PqcProviderError("PQC implementation shared secret is too short")
        if not self.ciphertext:
            raise PqcProviderError("PQC implementation ciphertext is required")


class PqcAlgorithmImplementation(Protocol):
    """Algorithm boundary for first-party ML-KEM/ML-DSA implementations."""

    provider_id: str
    implementation_hash: str
    kem_algorithm: str
    signature_algorithm: str

    def encapsulate(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcEncapsulationResult: ...


@dataclass(frozen=True)
class PqcKnownAnswerVector:
    """Hashed KAT vector for a first-party PQC implementation."""

    vector_id: str
    kem_algorithm: str
    signature_algorithm: str
    transcript: bytes
    client_identity_hash: bytes
    server_identity_hash: bytes
    expected_shared_secret_hash: str
    expected_ciphertext_hash: str

    def __post_init__(self) -> None:
        if not self.vector_id.strip():
            raise PqcProviderError("PQC KAT vector id is required")
        if self.kem_algorithm not in SUPPORTED_KEM_ALGORITHMS:
            raise PqcProviderError("unsupported PQC KAT KEM algorithm")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise PqcProviderError("unsupported PQC KAT signature algorithm")
        if not self.transcript:
            raise PqcProviderError("PQC KAT transcript is required")
        if len(self.client_identity_hash) < MIN_SECRET_BYTES:
            raise PqcProviderError("PQC KAT client identity hash is too short")
        if len(self.server_identity_hash) < MIN_SECRET_BYTES:
            raise PqcProviderError("PQC KAT server identity hash is too short")
        if len(self.expected_shared_secret_hash) != 64:
            raise PqcProviderError("PQC KAT shared secret hash is invalid")
        if len(self.expected_ciphertext_hash) != 64:
            raise PqcProviderError("PQC KAT ciphertext hash is invalid")

    def vector_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "client_identity_hash": self.client_identity_hash.hex(),
            "expected_ciphertext_hash": self.expected_ciphertext_hash,
            "expected_shared_secret_hash": self.expected_shared_secret_hash,
            "kem_algorithm": self.kem_algorithm,
            "server_identity_hash": self.server_identity_hash.hex(),
            "signature_algorithm": self.signature_algorithm,
            "transcript_hash": hashlib.sha256(self.transcript).hexdigest(),
            "vector_id": self.vector_id,
            "version": 1,
        }


@dataclass(frozen=True)
class PqcKatResult:
    """Result of first-party PQC known-answer tests."""

    passed: bool
    reasons: tuple[str, ...]
    suite_hash: str
    vector_count: int
    captured_at: int = 0
    provider_id: str = ""
    kem_algorithm: str = ""
    signature_algorithm: str = ""
    implementation_hash: str = ""

    def __post_init__(self) -> None:
        if self.captured_at < 0:
            raise PqcProviderError("PQC KAT time is invalid")


def run_pqc_known_answer_tests(
    implementation: PqcAlgorithmImplementation,
    vectors: tuple[PqcKnownAnswerVector, ...],
    *,
    captured_at: int | None = None,
) -> PqcKatResult:
    """Run hashed known-answer tests against a first-party PQC implementation."""
    collected_at = _utc_now() if captured_at is None else captured_at
    if collected_at < 0:
        raise PqcProviderError("PQC KAT time is invalid")
    reasons: list[str] = []
    if not vectors:
        reasons.append("pqc_kat_vectors_missing")
    for vector in vectors:
        if vector.kem_algorithm != implementation.kem_algorithm:
            reasons.append(f"{vector.vector_id}:pqc_kat_kem_mismatch")
            continue
        if vector.signature_algorithm != implementation.signature_algorithm:
            reasons.append(f"{vector.vector_id}:pqc_kat_signature_mismatch")
            continue
        try:
            result = implementation.encapsulate(
                transcript=vector.transcript,
                client_identity_hash=vector.client_identity_hash,
                server_identity_hash=vector.server_identity_hash,
            )
        except Exception:
            reasons.append(f"{vector.vector_id}:pqc_kat_execution_failed")
            continue
        reasons.extend(
            f"{vector.vector_id}:{reason}"
            for reason in _mlkem_shape_reasons(
                implementation.kem_algorithm,
                shared_secret=result.shared_secret,
                ciphertext=result.ciphertext,
            )
        )
        if hashlib.sha256(result.shared_secret).hexdigest() != (
            vector.expected_shared_secret_hash
        ):
            reasons.append(f"{vector.vector_id}:pqc_kat_shared_secret_mismatch")
        if hashlib.sha256(result.ciphertext).hexdigest() != (
            vector.expected_ciphertext_hash
        ):
            reasons.append(f"{vector.vector_id}:pqc_kat_ciphertext_mismatch")
    suite_hash = _kat_suite_hash(vectors)
    return PqcKatResult(
        passed=not reasons,
        reasons=tuple(reasons),
        suite_hash=suite_hash,
        vector_count=len(vectors),
        captured_at=collected_at,
        provider_id=implementation.provider_id,
        kem_algorithm=implementation.kem_algorithm,
        signature_algorithm=implementation.signature_algorithm,
        implementation_hash=implementation.implementation_hash,
    )


@dataclass(frozen=True)
class PqcProviderGateDecision:
    allowed: bool
    reasons: tuple[str, ...]
    attestation_hash: str
    provider_id: str = ""
    kem_algorithm: str = ""
    signature_algorithm: str = ""
    implementation_hash: str = ""


@dataclass(frozen=True)
class PqcImplementationManifest:
    """Reviewed implementation artifact metadata for production PQC providers."""

    provider_id: str
    kem_algorithm: str
    signature_algorithm: str
    mode: PqcProviderMode
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
            raise PqcProviderError("unsupported PQC implementation manifest version")
        if not self.provider_id.strip():
            raise PqcProviderError("PQC manifest provider id is required")
        if self.kem_algorithm not in SUPPORTED_KEM_ALGORITHMS:
            raise PqcProviderError("unsupported PQC manifest KEM algorithm")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise PqcProviderError("unsupported PQC manifest signature algorithm")
        if self.mode not in ("test", "production"):
            raise PqcProviderError("PQC manifest mode must be test or production")
        if not self.implementation_hash.strip():
            raise PqcProviderError("PQC manifest implementation hash is required")
        if not self.source_hashes:
            raise PqcProviderError("PQC manifest source hashes are required")
        if not self.kat_hashes:
            raise PqcProviderError("PQC manifest KAT hashes are required")
        if not self.review_evidence_hash.strip():
            raise PqcProviderError("PQC manifest review evidence hash is required")
        if self.expires_at is not None and self.expires_at <= self.issued_at:
            raise PqcProviderError("PQC manifest validity window is invalid")
        for item in (*self.source_hashes, *self.kat_hashes, self.review_evidence_hash):
            if not item.strip():
                raise PqcProviderError("PQC manifest evidence hashes must be non-empty")

    def active_at(self, now: int) -> bool:
        if now < self.issued_at:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return True

    def to_attestation(self) -> PqcProviderAttestation:
        return PqcProviderAttestation(
            provider_id=self.provider_id,
            kem_algorithm=self.kem_algorithm,
            signature_algorithm=self.signature_algorithm,
            mode=self.mode,
            reviewed=self.reviewed,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
            implementation_hash=self.implementation_hash,
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "expires_at": self.expires_at,
            "implementation_hash": self.implementation_hash,
            "issued_at": self.issued_at,
            "kat_hashes": list(self.kat_hashes),
            "kem_algorithm": self.kem_algorithm,
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
    def from_json_dict(cls, value: dict[str, object]) -> "PqcImplementationManifest":
        manifest = cls(
            version=int(value.get("version", 0)),
            provider_id=str(value.get("provider_id", "")),
            kem_algorithm=str(value.get("kem_algorithm", "")),
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
            raise PqcProviderError("PQC implementation manifest hash mismatch")
        return manifest

    def manifest_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self._hash_payload())).hexdigest()

    def _hash_payload(self) -> dict[str, object]:
        return {
            "expires_at": self.expires_at,
            "implementation_hash": self.implementation_hash,
            "issued_at": self.issued_at,
            "kat_hashes": sorted(self.kat_hashes),
            "kem_algorithm": self.kem_algorithm,
            "mode": self.mode,
            "provider_id": self.provider_id,
            "review_evidence_hash": self.review_evidence_hash,
            "reviewed": self.reviewed,
            "signature_algorithm": self.signature_algorithm,
            "source_hashes": sorted(self.source_hashes),
            "version": self.version,
        }


class DurablePqcManifestStore:
    """Atomic JSON store for reviewed PQC implementation manifests."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def save_all(self, manifests: tuple[PqcImplementationManifest, ...]) -> None:
        if not manifests:
            raise PqcProviderError("PQC manifest store cannot be empty")
        payload = {
            "bundle_hash": _manifest_bundle_hash(manifests),
            "manifests": [manifest.to_json_dict() for manifest in manifests],
            "version": 1,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.tmp")
        tmp.write_bytes(_canonical_json(payload) + b"\n")
        tmp.replace(self.path)

    def load_all(self) -> tuple[PqcImplementationManifest, ...]:
        if not self.path.exists():
            raise PqcProviderError("PQC manifest store is missing")
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PqcProviderError("PQC manifest store JSON is invalid") from exc
        if not isinstance(raw, dict):
            raise PqcProviderError("PQC manifest store root must be a map")
        if int(raw.get("version", 0)) != 1:
            raise PqcProviderError("unsupported PQC manifest store version")
        manifests_raw = raw.get("manifests", [])
        if not isinstance(manifests_raw, list):
            raise PqcProviderError("PQC manifest list must be a list")
        manifests = tuple(
            PqcImplementationManifest.from_json_dict(item)
            for item in manifests_raw
            if isinstance(item, dict)
        )
        if len(manifests) != len(manifests_raw):
            raise PqcProviderError("PQC manifest list contains non-map entries")
        if raw.get("bundle_hash") != _manifest_bundle_hash(manifests):
            raise PqcProviderError("PQC manifest bundle hash mismatch")
        return manifests

    def find(
        self,
        *,
        provider_id: str,
        implementation_hash: str,
    ) -> PqcImplementationManifest | None:
        for manifest in self.load_all():
            if (
                manifest.provider_id == provider_id
                and manifest.implementation_hash == implementation_hash
            ):
                return manifest
        return None


@dataclass(frozen=True)
class PqcProductionGate:
    """Fail-closed checks for using a PQC provider in production."""

    require_production: bool = False
    trusted_provider_ids: frozenset[str] = frozenset()
    trusted_implementation_hashes: frozenset[str] = frozenset()

    def evaluate(
        self,
        material: PqcSessionSecretMaterial,
        *,
        now: int | None = None,
    ) -> PqcProviderGateDecision:
        now = now if now is not None else _utc_now()
        reasons: list[str] = []
        attestation = material.attestation
        if material.kem_algorithm not in SUPPORTED_KEM_ALGORITHMS:
            reasons.append("pqc_kem_not_supported")
        if material.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            reasons.append("pqc_signature_not_supported")
        if len(material.shared_secret) < MIN_SECRET_BYTES:
            reasons.append("pqc_shared_secret_too_short")
        if not material.ciphertext:
            reasons.append("pqc_ciphertext_missing")
        if not attestation.active_at(now):
            reasons.append("pqc_provider_attestation_not_active")
        if self.require_production:
            reasons.extend(
                _mlkem_shape_reasons(
                    material.kem_algorithm,
                    shared_secret=material.shared_secret,
                    ciphertext=material.ciphertext,
                )
            )
            if attestation.mode != "production":
                reasons.append("pqc_provider_not_production")
            if not attestation.reviewed:
                reasons.append("pqc_provider_not_reviewed")
            if not attestation.implementation_hash:
                reasons.append("pqc_provider_implementation_hash_missing")
            if (
                self.trusted_provider_ids
                and attestation.provider_id not in self.trusted_provider_ids
            ):
                reasons.append("pqc_provider_not_trusted")
            if (
                self.trusted_implementation_hashes
                and attestation.implementation_hash not in self.trusted_implementation_hashes
            ):
                reasons.append("pqc_provider_implementation_not_trusted")
        return PqcProviderGateDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
            attestation_hash=attestation.attestation_hash(),
            provider_id=attestation.provider_id,
            kem_algorithm=attestation.kem_algorithm,
            signature_algorithm=attestation.signature_algorithm,
            implementation_hash=attestation.implementation_hash or "",
        )


@dataclass(frozen=True)
class PqcManifestProductionGate:
    """Production gate backed by durable reviewed implementation manifests."""

    manifest_store: DurablePqcManifestStore
    require_production: bool = True
    max_kat_age_seconds: int = 3600

    def __post_init__(self) -> None:
        if self.max_kat_age_seconds < 1:
            raise PqcProviderError("PQC KAT max age must be positive")

    def evaluate(
        self,
        material: PqcSessionSecretMaterial,
        *,
        now: int | None = None,
    ) -> PqcProviderGateDecision:
        now = now if now is not None else _utc_now()
        base = PqcProductionGate(require_production=self.require_production).evaluate(
            material,
            now=now,
        )
        reasons = list(base.reasons)
        attestation = material.attestation
        if not attestation.implementation_hash:
            reasons.append("pqc_manifest_implementation_hash_missing")
            manifest = None
        else:
            try:
                manifest = self.manifest_store.find(
                    provider_id=attestation.provider_id,
                    implementation_hash=attestation.implementation_hash,
                )
            except PqcProviderError:
                reasons.append("pqc_manifest_store_untrusted")
                manifest = None
        if manifest is None:
            reasons.append("pqc_manifest_missing")
        else:
            reasons.extend(_manifest_reasons(manifest, attestation, now=now))
        if self.require_production:
            reasons.extend(
                _kat_result_reasons(
                    material.kat_result,
                    manifest,
                    now=now,
                    max_age_seconds=self.max_kat_age_seconds,
                )
            )
        return PqcProviderGateDecision(
            allowed=not reasons,
            reasons=tuple(dict.fromkeys(reasons)),
            attestation_hash=attestation.attestation_hash(),
            provider_id=attestation.provider_id,
            kem_algorithm=attestation.kem_algorithm,
            signature_algorithm=attestation.signature_algorithm,
            implementation_hash=attestation.implementation_hash or "",
        )


class FirstPartyPqcProvider:
    """Manifest-backed provider adapter for reviewed first-party PQC code."""

    def __init__(
        self,
        *,
        implementation: PqcAlgorithmImplementation,
        manifest: PqcImplementationManifest,
        kat_vectors: tuple[PqcKnownAnswerVector, ...],
        kat_captured_at: int | None = None,
    ) -> None:
        self.implementation = implementation
        self.manifest = manifest
        self._validate_manifest_binding()
        kat_result = run_pqc_known_answer_tests(
            implementation,
            kat_vectors,
            captured_at=kat_captured_at,
        )
        if not kat_result.passed:
            raise PqcProviderError("PQC implementation KAT failed")
        if kat_result.suite_hash not in manifest.kat_hashes:
            raise PqcProviderError("PQC KAT suite is not present in manifest")
        self.kat_result = kat_result
        self.attestation = manifest.to_attestation()

    def create_session_material(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcSessionSecretMaterial:
        result = self.implementation.encapsulate(
            transcript=transcript,
            client_identity_hash=client_identity_hash,
            server_identity_hash=server_identity_hash,
        )
        return PqcSessionSecretMaterial(
            kem_algorithm=self.attestation.kem_algorithm,
            signature_algorithm=self.attestation.signature_algorithm,
            shared_secret=result.shared_secret,
            ciphertext=result.ciphertext,
            attestation=self.attestation,
            kat_result=self.kat_result,
        )

    def _validate_manifest_binding(self) -> None:
        if self.manifest.provider_id != self.implementation.provider_id:
            raise PqcProviderError("PQC manifest provider id mismatch")
        if self.manifest.implementation_hash != self.implementation.implementation_hash:
            raise PqcProviderError("PQC manifest implementation hash mismatch")
        if self.manifest.kem_algorithm != self.implementation.kem_algorithm:
            raise PqcProviderError("PQC manifest KEM algorithm mismatch")
        if self.manifest.signature_algorithm != self.implementation.signature_algorithm:
            raise PqcProviderError("PQC manifest signature algorithm mismatch")
        if self.manifest.mode != "production":
            raise PqcProviderError("PQC manifest is not production")
        if not self.manifest.reviewed:
            raise PqcProviderError("PQC manifest is not reviewed")


class FirstPartyMlKemImplementation:
    """First-party ML-KEM implementation for the manifest-backed PQC provider."""

    def __init__(
        self,
        *,
        encapsulation_key: bytes,
        provider_id: str = "firstparty-mlkem-provider",
        kem_algorithm: str = "ML-KEM-768",
        signature_algorithm: str = "ML-DSA-65",
        decapsulation_key: bytes | None = None,
        kat_messages: dict[str, bytes] | None = None,
    ) -> None:
        params = mlkem_parameter_set(kem_algorithm)
        if signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise PqcProviderError("unsupported PQC signature algorithm")
        if not provider_id.strip():
            raise PqcProviderError("PQC provider id is required")
        if len(encapsulation_key) != params.encapsulation_key_bytes:
            raise PqcProviderError("ML-KEM encapsulation key length is invalid")
        if decapsulation_key is not None and (
            len(decapsulation_key) != params.decapsulation_key_bytes
        ):
            raise PqcProviderError("ML-KEM decapsulation key length is invalid")
        self.provider_id = provider_id
        self.kem_algorithm = params.name
        self.signature_algorithm = signature_algorithm
        self.encapsulation_key = encapsulation_key
        self.decapsulation_key = decapsulation_key
        self._kat_messages = _validated_kat_messages(kat_messages or {})
        self.implementation_hash = _firstparty_mlkem_implementation_hash(
            provider_id=self.provider_id,
            kem_algorithm=self.kem_algorithm,
            signature_algorithm=self.signature_algorithm,
            encapsulation_key=self.encapsulation_key,
            has_decapsulation_key=self.decapsulation_key is not None,
            kat_context_ids=tuple(self._kat_messages),
        )

    @staticmethod
    def context_id(
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> str:
        return hashlib.sha256(
            b"x0vpn-firstparty-mlkem-context-v1"
            + len(transcript).to_bytes(4, "big")
            + transcript
            + client_identity_hash
            + server_identity_hash
        ).hexdigest()

    def encapsulate(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcEncapsulationResult:
        if not transcript:
            raise PqcProviderError("PQC transcript is required")
        if len(client_identity_hash) < MIN_SECRET_BYTES:
            raise PqcProviderError("PQC client identity hash is too short")
        if len(server_identity_hash) < MIN_SECRET_BYTES:
            raise PqcProviderError("PQC server identity hash is too short")
        context_id = self.context_id(
            transcript=transcript,
            client_identity_hash=client_identity_hash,
            server_identity_hash=server_identity_hash,
        )
        message = self._kat_messages.get(context_id)
        try:
            encapsulated = (
                mlkem_encapsulate_from_message(
                    self.kem_algorithm,
                    self.encapsulation_key,
                    message,
                )
                if message is not None
                else mlkem_encapsulate(self.kem_algorithm, self.encapsulation_key)
            )
        except MlKemPrimitiveError as exc:
            raise PqcProviderError("ML-KEM encapsulation failed") from exc
        if self.decapsulation_key is not None:
            try:
                decapsulated = mlkem_decapsulate(
                    self.kem_algorithm,
                    self.decapsulation_key,
                    encapsulated.ciphertext,
                )
            except MlKemPrimitiveError as exc:
                raise PqcProviderError("ML-KEM decapsulation self-check failed") from exc
            if not hmac.compare_digest(decapsulated, encapsulated.shared_secret):
                raise PqcProviderError("ML-KEM decapsulation self-check failed")
        return PqcEncapsulationResult(
            shared_secret=encapsulated.shared_secret,
            ciphertext=encapsulated.ciphertext,
        )


class LocalTestPqcProvider:
    """Deterministic local provider for tests and development only."""

    def __init__(
        self,
        *,
        provider_id: str = "local-test-pqc-provider",
        kem_algorithm: str = "ML-KEM-768",
        signature_algorithm: str = "ML-DSA-65",
        seed: bytes = b"local-test-pqc-provider-seed".ljust(32, b"-"),
        issued_at: int = 0,
    ) -> None:
        if len(seed) < MIN_SECRET_BYTES:
            raise ValueError("local test PQC seed is too short")
        self.seed = seed
        self.attestation = PqcProviderAttestation(
            provider_id=provider_id,
            kem_algorithm=kem_algorithm,
            signature_algorithm=signature_algorithm,
            mode="test",
            reviewed=False,
            issued_at=issued_at,
            implementation_hash=None,
        )

    def create_session_material(
        self,
        *,
        transcript: bytes,
        client_identity_hash: bytes,
        server_identity_hash: bytes,
    ) -> PqcSessionSecretMaterial:
        secret = hmac.new(
            self.seed,
            b"x0vpn-local-test-pqc-v1"
            + transcript
            + client_identity_hash
            + server_identity_hash,
            hashlib.sha256,
        ).digest()
        ciphertext = hashlib.sha256(
            b"x0vpn-local-test-pqc-ciphertext-v1" + secret + transcript
        ).digest()
        return PqcSessionSecretMaterial(
            kem_algorithm=self.attestation.kem_algorithm,
            signature_algorithm=self.attestation.signature_algorithm,
            shared_secret=secret,
            ciphertext=ciphertext,
            attestation=self.attestation,
        )


def _manifest_reasons(
    manifest: PqcImplementationManifest,
    attestation: PqcProviderAttestation,
    *,
    now: int,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not manifest.active_at(now):
        reasons.append("pqc_manifest_not_active")
    if manifest.provider_id != attestation.provider_id:
        reasons.append("pqc_manifest_provider_mismatch")
    if manifest.kem_algorithm != attestation.kem_algorithm:
        reasons.append("pqc_manifest_kem_mismatch")
    if manifest.signature_algorithm != attestation.signature_algorithm:
        reasons.append("pqc_manifest_signature_mismatch")
    if manifest.mode != attestation.mode:
        reasons.append("pqc_manifest_mode_mismatch")
    if manifest.reviewed != attestation.reviewed:
        reasons.append("pqc_manifest_review_mismatch")
    if manifest.implementation_hash != attestation.implementation_hash:
        reasons.append("pqc_manifest_implementation_mismatch")
    if manifest.mode != "production":
        reasons.append("pqc_manifest_not_production")
    if not manifest.reviewed:
        reasons.append("pqc_manifest_not_reviewed")
    if not manifest.source_hashes:
        reasons.append("pqc_manifest_source_hashes_missing")
    if not manifest.kat_hashes:
        reasons.append("pqc_manifest_kat_hashes_missing")
    if not manifest.review_evidence_hash:
        reasons.append("pqc_manifest_review_evidence_missing")
    return tuple(reasons)


def _kat_result_reasons(
    kat_result: PqcKatResult | None,
    manifest: PqcImplementationManifest | None,
    *,
    now: int | None = None,
    max_age_seconds: int | None = None,
) -> tuple[str, ...]:
    if kat_result is None:
        return ("pqc_kat_missing",)
    reasons: list[str] = []
    if not kat_result.passed:
        reasons.append("pqc_kat_failed")
    if kat_result.vector_count < 1:
        reasons.append("pqc_kat_vectors_missing")
    if manifest is not None and kat_result.suite_hash not in manifest.kat_hashes:
        reasons.append("pqc_kat_not_in_manifest")
    if manifest is not None:
        if not kat_result.provider_id:
            reasons.append("pqc_kat_provider_id_missing")
        elif kat_result.provider_id != manifest.provider_id:
            reasons.append("pqc_kat_provider_mismatch")
        if not kat_result.kem_algorithm:
            reasons.append("pqc_kat_kem_algorithm_missing")
        elif kat_result.kem_algorithm != manifest.kem_algorithm:
            reasons.append("pqc_kat_kem_algorithm_mismatch")
        if not kat_result.signature_algorithm:
            reasons.append("pqc_kat_signature_algorithm_missing")
        elif kat_result.signature_algorithm != manifest.signature_algorithm:
            reasons.append("pqc_kat_signature_algorithm_mismatch")
        if not kat_result.implementation_hash:
            reasons.append("pqc_kat_implementation_hash_missing")
        elif kat_result.implementation_hash != manifest.implementation_hash:
            reasons.append("pqc_kat_implementation_mismatch")
    if now is not None and max_age_seconds is not None:
        if kat_result.captured_at > now:
            reasons.append("pqc_kat_from_future")
        elif now - kat_result.captured_at > max_age_seconds:
            reasons.append("pqc_kat_stale")
    return tuple(reasons)


def _validated_kat_messages(kat_messages: dict[str, bytes]) -> dict[str, bytes]:
    validated: dict[str, bytes] = {}
    for context_id, message in kat_messages.items():
        if len(context_id) != 64:
            raise PqcProviderError("ML-KEM KAT context id is invalid")
        if len(message) != ML_KEM_SEED_BYTES:
            raise PqcProviderError("ML-KEM KAT message must be 32 bytes")
        validated[context_id] = bytes(message)
    return validated


def _firstparty_mlkem_implementation_hash(
    *,
    provider_id: str,
    kem_algorithm: str,
    signature_algorithm: str,
    encapsulation_key: bytes,
    has_decapsulation_key: bool,
    kat_context_ids: tuple[str, ...],
) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "encapsulation_key_hash": mlkem_hash_h(encapsulation_key).hex(),
                "has_decapsulation_key": has_decapsulation_key,
                "kat_context_ids": sorted(kat_context_ids),
                "kem_algorithm": kem_algorithm,
                "profile": "x0vpn-firstparty-mlkem-implementation-v1",
                "provider_id": provider_id,
                "signature_algorithm": signature_algorithm,
                "version": 1,
            }
        )
    ).hexdigest()


def _mlkem_shape_reasons(
    kem_algorithm: str,
    *,
    shared_secret: bytes,
    ciphertext: bytes,
) -> tuple[str, ...]:
    reasons: list[str] = []
    try:
        profile = pqc_kem_profile(kem_algorithm)
    except PqcProviderError:
        return ("pqc_kem_profile_missing",)
    if len(shared_secret) != profile.shared_secret_bytes:
        reasons.append("pqc_shared_secret_length_invalid")
    if len(ciphertext) != profile.ciphertext_bytes:
        reasons.append("pqc_ciphertext_length_invalid")
    return tuple(reasons)


def _manifest_bundle_hash(manifests: tuple[PqcImplementationManifest, ...]) -> str:
    return hashlib.sha256(
        _canonical_json([manifest.manifest_hash() for manifest in manifests])
    ).hexdigest()


def _kat_suite_hash(vectors: tuple[PqcKnownAnswerVector, ...]) -> str:
    return hashlib.sha256(
        _canonical_json([vector.vector_hash() for vector in vectors])
    ).hexdigest()


def _string_tuple(value: dict[str, object], key: str) -> tuple[str, ...]:
    raw = value.get(key, [])
    if not isinstance(raw, list):
        raise PqcProviderError(f"PQC manifest {key} must be a list")
    return tuple(str(item) for item in raw)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
