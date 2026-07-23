"""Zero-trust identity gate for first-party VPN sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json

_SHA256_HEX_BYTES = 64


@dataclass(frozen=True)
class IdentityClaims:
    """Identity claims bound into the first-party VPN handshake."""

    spiffe_id: str
    did: str
    workload: str
    tenant: str
    device_id: str
    pqc_kem_algorithm: str
    pqc_signature_algorithm: str
    issued_at: int
    expires_at: int
    policy_epoch: str
    attributes: dict[str, str] = field(default_factory=dict)

    def canonical_json(self) -> bytes:
        return json.dumps(
            {
                "attributes": self.attributes,
                "device_id": self.device_id,
                "did": self.did,
                "expires_at": self.expires_at,
                "issued_at": self.issued_at,
                "policy_epoch": self.policy_epoch,
                "pqc_kem_algorithm": self.pqc_kem_algorithm,
                "pqc_signature_algorithm": self.pqc_signature_algorithm,
                "spiffe_id": self.spiffe_id,
                "tenant": self.tenant,
                "workload": self.workload,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")


@dataclass(frozen=True)
class ZeroTrustDecision:
    allowed: bool
    reasons: tuple[str, ...]
    identity_hash: bytes


@dataclass(frozen=True)
class ZeroTrustPolicy:
    """Fail-closed zero-trust policy for VPN session admission."""

    trust_domain: str = "x0tta6bl4.mesh"
    allowed_workloads: frozenset[str] = frozenset({"vpn-client", "vpn-server"})
    allowed_tenants: frozenset[str] = frozenset()
    did_prefix: str = "did:mesh:pqc:"
    required_kem_algorithms: frozenset[str] = frozenset({"ML-KEM-768", "ML-KEM-1024"})
    required_signature_algorithms: frozenset[str] = frozenset({"ML-DSA-65", "ML-DSA-87"})
    max_token_lifetime_seconds: int = 3600

    def evaluate(self, claims: IdentityClaims, *, now: int | None = None) -> ZeroTrustDecision:
        now = now if now is not None else int(datetime.now(timezone.utc).timestamp())
        reasons: list[str] = []
        expected_prefix = f"spiffe://{self.trust_domain}/"

        if not claims.spiffe_id.startswith(expected_prefix):
            reasons.append("spiffe_trust_domain_mismatch")
        if not claims.did.startswith(self.did_prefix):
            reasons.append("did_prefix_mismatch")
        if claims.workload not in self.allowed_workloads:
            reasons.append("workload_not_allowed")
        if self.allowed_tenants and claims.tenant not in self.allowed_tenants:
            reasons.append("tenant_not_allowed")
        if claims.pqc_kem_algorithm not in self.required_kem_algorithms:
            reasons.append("pqc_kem_not_allowed")
        if claims.pqc_signature_algorithm not in self.required_signature_algorithms:
            reasons.append("pqc_signature_not_allowed")
        if claims.issued_at > now:
            reasons.append("identity_not_yet_valid")
        if claims.expires_at <= now:
            reasons.append("identity_expired")
        if claims.expires_at - claims.issued_at > self.max_token_lifetime_seconds:
            reasons.append("identity_lifetime_too_long")
        if not claims.policy_epoch.strip():
            reasons.append("policy_epoch_missing")

        return ZeroTrustDecision(
            allowed=not reasons,
            reasons=tuple(reasons),
            identity_hash=identity_binding_hash(claims),
        )


@dataclass(frozen=True)
class ZeroTrustPolicyEvidence:
    """Privacy-safe evidence for the session admission policy in use."""

    policy_hash: str
    trust_domain_hash: str
    did_prefix_hash: str
    allowed_workloads: tuple[str, ...]
    allowed_tenant_count: int
    allowed_tenants_hash: str
    required_kem_algorithms: tuple[str, ...]
    required_signature_algorithms: tuple[str, ...]
    max_token_lifetime_seconds: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("policy hash", self.policy_hash),
            ("trust domain hash", self.trust_domain_hash),
            ("DID prefix hash", self.did_prefix_hash),
            ("allowed tenants hash", self.allowed_tenants_hash),
        ):
            if not _is_sha256_hex(value):
                raise ValueError(f"{field_name} must be sha256 hex")
        if self.allowed_tenant_count < 0:
            raise ValueError("allowed tenant count cannot be negative")
        if self.max_token_lifetime_seconds < 1:
            raise ValueError("max token lifetime must be positive")

    @classmethod
    def from_policy(cls, policy: ZeroTrustPolicy) -> "ZeroTrustPolicyEvidence":
        payload = _policy_payload(policy)
        return cls(
            policy_hash=hashlib.sha256(
                b"x0vpn-zero-trust-policy-v1"
                + json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest(),
            trust_domain_hash=_hash_text("trust-domain", policy.trust_domain),
            did_prefix_hash=_hash_text("did-prefix", policy.did_prefix),
            allowed_workloads=tuple(sorted(policy.allowed_workloads)),
            allowed_tenant_count=len(policy.allowed_tenants),
            allowed_tenants_hash=_hash_text(
                "allowed-tenants",
                "\n".join(sorted(policy.allowed_tenants)),
            ),
            required_kem_algorithms=tuple(sorted(policy.required_kem_algorithms)),
            required_signature_algorithms=tuple(
                sorted(policy.required_signature_algorithms)
            ),
            max_token_lifetime_seconds=policy.max_token_lifetime_seconds,
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "allowed_tenant_count": self.allowed_tenant_count,
            "allowed_tenants_hash": self.allowed_tenants_hash,
            "allowed_workloads": list(self.allowed_workloads),
            "did_prefix_hash": self.did_prefix_hash,
            "max_identity_lifetime_seconds": self.max_token_lifetime_seconds,
            "policy_hash": self.policy_hash,
            "required_kem_algorithms": list(self.required_kem_algorithms),
            "required_signature_algorithms": list(
                self.required_signature_algorithms
            ),
            "trust_domain_hash": self.trust_domain_hash,
        }

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-zero-trust-policy-evidence-v1"
            + json.dumps(
                self.to_json_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


def identity_binding_hash(claims: IdentityClaims) -> bytes:
    return hashlib.sha256(b"x0vpn-zt-v1" + claims.canonical_json()).digest()


def _policy_payload(policy: ZeroTrustPolicy) -> dict[str, object]:
    return {
        "allowed_tenants": sorted(policy.allowed_tenants),
        "allowed_workloads": sorted(policy.allowed_workloads),
        "did_prefix": policy.did_prefix,
        "max_token_lifetime_seconds": policy.max_token_lifetime_seconds,
        "required_kem_algorithms": sorted(policy.required_kem_algorithms),
        "required_signature_algorithms": sorted(
            policy.required_signature_algorithms
        ),
        "trust_domain": policy.trust_domain,
    }


def _hash_text(namespace: str, value: str) -> str:
    return hashlib.sha256(f"{namespace}|{value}".encode("utf-8")).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    if len(value) != _SHA256_HEX_BYTES:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True
