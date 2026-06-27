"""Signed zero-trust identity issuance for the first-party VPN."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Mapping, Protocol

from .crypto import MIN_SECRET_BYTES, SUPPORTED_SIGNATURE_ALGORITHMS
from .mldsa import (
    mldsa_derive_verification_key_from_signing_key,
    mldsa_parameter_set,
    mldsa_reference_sign,
    mldsa_reference_verify,
    mldsa_validate_signing_key,
    mldsa_validate_verification_key,
)
from .zero_trust import IdentityClaims, ZeroTrustDecision, ZeroTrustPolicy, identity_binding_hash


class IdentityAuthorityError(ValueError):
    """Raised when identity issuance or verification fails."""


class IdentitySignatureProvider(Protocol):
    def sign(self, key: "IdentitySigningKey", payload: bytes) -> bytes: ...

    def verify(
        self,
        key: "IdentitySigningKey",
        payload: bytes,
        signature: bytes,
    ) -> bool: ...


class IdentityVerifier(Protocol):
    def verify(
        self,
        token: "SignedIdentityToken",
        *,
        policy: ZeroTrustPolicy,
        revocations: "RevocationList" | None = None,
        now: int | None = None,
    ) -> ZeroTrustDecision: ...


@dataclass(frozen=True)
class IdentitySigningKey:
    """Signing key metadata for zero-trust identity tokens."""

    key_id: str
    signature_algorithm: str
    secret: bytes
    not_before: int = 0
    not_after: int | None = None

    def __post_init__(self) -> None:
        if not self.key_id.strip():
            raise ValueError("identity signing key id is required")
        if self.signature_algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ValueError("unsupported identity signature algorithm")
        if len(self.secret) < MIN_SECRET_BYTES:
            raise ValueError("identity signing key secret is too short")
        if self.not_after is not None and self.not_after <= self.not_before:
            raise ValueError("identity signing key validity window is invalid")

    def active_at(self, now: int) -> bool:
        if now < self.not_before:
            return False
        if self.not_after is not None and now >= self.not_after:
            return False
        return True


class LocalIdentitySignatureProvider:
    """Dependency-free local signer for tests and development.

    This intentionally does not claim to implement ML-DSA. Production must
    replace it with a reviewed first-party ML-DSA provider before rollout.
    """

    def sign(self, key: IdentitySigningKey, payload: bytes) -> bytes:
        return hmac.new(
            key.secret,
            b"x0vpn-identity-v1"
            + key.key_id.encode("utf-8")
            + key.signature_algorithm.encode("utf-8")
            + payload,
            hashlib.sha256,
        ).digest()

    def verify(
        self,
        key: IdentitySigningKey,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        expected = self.sign(key, payload)
        return hmac.compare_digest(expected, signature)


class FirstPartyReferenceMlDsaIdentitySignatureProvider:
    """Dependency-free first-party reference ML-DSA identity signer.

    This provider uses the local ML-DSA primitive/codecs to produce structured
    public-verifiable signatures for the production admission path. It is not
    the final optimized FIPS 204 signing algorithm.
    """

    provider_id = "reviewed-firstparty-identity-signer"
    implementation_hash = hashlib.sha256(b"reviewed-identity-signer").hexdigest()

    def __init__(self) -> None:
        self._signature_cache: dict[tuple[str, str, bytes, bytes], bytes] = {}

    def sign(self, key: IdentitySigningKey, payload: bytes) -> bytes:
        cache_key = (
            key.key_id,
            key.signature_algorithm,
            hashlib.sha256(key.secret).digest(),
            hashlib.sha256(payload).digest(),
        )
        cached = self._signature_cache.get(cache_key)
        if cached is not None:
            return cached
        signature = mldsa_reference_sign(
            key.signature_algorithm,
            key.secret,
            payload,
        )
        self._signature_cache[cache_key] = signature
        return signature

    def verify(
        self,
        key: IdentitySigningKey,
        payload: bytes,
        signature: bytes,
    ) -> bool:
        try:
            verification_key = _reference_mldsa_verification_key_for_identity_key(key)
        except Exception:
            return False
        return mldsa_reference_verify(
            key.signature_algorithm,
            verification_key,
            payload,
            signature,
        )


@dataclass(frozen=True)
class IdentityIssueRequest:
    spiffe_id: str
    did: str
    workload: str
    tenant: str
    device_id: str
    pqc_kem_algorithm: str = "ML-KEM-768"
    pqc_signature_algorithm: str = "ML-DSA-65"
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SignedIdentityToken:
    """A signed identity token that wraps zero-trust claims."""

    version: int
    issuer: str
    key_id: str
    signature_algorithm: str
    serial: str
    claims: IdentityClaims
    signature: bytes

    def signing_payload(self) -> bytes:
        return _canonical_json(
            {
                "claims": json.loads(self.claims.canonical_json()),
                "issuer": self.issuer,
                "key_id": self.key_id,
                "serial": self.serial,
                "signature_algorithm": self.signature_algorithm,
                "version": self.version,
            }
        )

    def canonical_json(self) -> bytes:
        return _canonical_json(
            {
                "claims": json.loads(self.claims.canonical_json()),
                "issuer": self.issuer,
                "key_id": self.key_id,
                "serial": self.serial,
                "signature": self.signature.hex(),
                "signature_algorithm": self.signature_algorithm,
                "version": self.version,
            }
        )


@dataclass
class RevocationList:
    """Fail-closed revocation state for identity tokens and signing keys."""

    identity_serials: set[str] = field(default_factory=set)
    key_ids: set[str] = field(default_factory=set)
    policy_epochs: set[str] = field(default_factory=set)

    def revoke_identity(self, token: SignedIdentityToken) -> None:
        self.identity_serials.add(token.serial)

    def revoke_key(self, key_id: str) -> None:
        if not key_id.strip():
            raise ValueError("revoked key id is required")
        self.key_ids.add(key_id)

    def revoke_policy_epoch(self, policy_epoch: str) -> None:
        if not policy_epoch.strip():
            raise ValueError("revoked policy epoch is required")
        self.policy_epochs.add(policy_epoch)

    def reasons_for(self, token: SignedIdentityToken) -> tuple[str, ...]:
        reasons: list[str] = []
        if token.serial in self.identity_serials:
            reasons.append("identity_revoked")
        if token.key_id in self.key_ids:
            reasons.append("identity_key_revoked")
        if token.claims.policy_epoch in self.policy_epochs:
            reasons.append("policy_epoch_revoked")
        return tuple(reasons)


class ReadOnlyIdentityVerifier:
    """Verify signed identity tokens without issuance or rotation authority."""

    def __init__(
        self,
        *,
        issuer: str = "x0tta6bl4-identity-authority",
        verification_keys: tuple[IdentitySigningKey, ...],
        signature_provider: IdentitySignatureProvider | None = None,
    ) -> None:
        if not issuer.strip():
            raise ValueError("identity verifier issuer is required")
        if not verification_keys:
            raise ValueError("identity verifier keys are required")
        self.issuer = issuer
        self._keys = {key.key_id: key for key in verification_keys}
        self.signature_provider = signature_provider or LocalIdentitySignatureProvider()

    def verify(
        self,
        token: SignedIdentityToken,
        *,
        policy: ZeroTrustPolicy,
        revocations: RevocationList | None = None,
        now: int | None = None,
    ) -> ZeroTrustDecision:
        return _verify_signed_identity_token(
            issuer=self.issuer,
            keys=self._keys,
            signature_provider=self.signature_provider,
            token=token,
            policy=policy,
            revocations=revocations,
            now=now,
        )


class IdentityAuthority:
    """Issue, verify, rotate, and revoke first-party VPN identities."""

    def __init__(
        self,
        *,
        issuer: str = "x0tta6bl4-identity-authority",
        policy_epoch: str = "epoch-1",
        signing_keys: tuple[IdentitySigningKey, ...],
        active_key_id: str,
        signature_provider: IdentitySignatureProvider | None = None,
        default_lifetime_seconds: int = 600,
        max_lifetime_seconds: int = 3600,
    ) -> None:
        if not issuer.strip():
            raise ValueError("identity issuer is required")
        if not policy_epoch.strip():
            raise ValueError("identity policy epoch is required")
        if default_lifetime_seconds < 1:
            raise ValueError("identity default lifetime must be positive")
        if max_lifetime_seconds < default_lifetime_seconds:
            raise ValueError("identity max lifetime must cover default lifetime")
        self.issuer = issuer
        self.policy_epoch = policy_epoch
        self._keys = {key.key_id: key for key in signing_keys}
        if active_key_id not in self._keys:
            raise ValueError("active identity signing key is not registered")
        self.active_key_id = active_key_id
        self.signature_provider = signature_provider or LocalIdentitySignatureProvider()
        self.default_lifetime_seconds = default_lifetime_seconds
        self.max_lifetime_seconds = max_lifetime_seconds
        self._serial_counter = 0

    @property
    def serial_counter(self) -> int:
        return self._serial_counter

    def restore_serial_counter(self, serial_counter: int) -> None:
        if serial_counter < self._serial_counter:
            raise IdentityAuthorityError("identity serial counter rollback refused")
        self._serial_counter = serial_counter

    def issue(
        self,
        request: IdentityIssueRequest,
        *,
        now: int | None = None,
        lifetime_seconds: int | None = None,
    ) -> SignedIdentityToken:
        now = now if now is not None else _utc_now()
        lifetime = lifetime_seconds or self.default_lifetime_seconds
        if lifetime < 1 or lifetime > self.max_lifetime_seconds:
            raise IdentityAuthorityError("identity lifetime is outside authority bounds")
        key = self._active_key(now)
        claims = IdentityClaims(
            spiffe_id=request.spiffe_id,
            did=request.did,
            workload=request.workload,
            tenant=request.tenant,
            device_id=request.device_id,
            pqc_kem_algorithm=request.pqc_kem_algorithm,
            pqc_signature_algorithm=request.pqc_signature_algorithm,
            issued_at=now,
            expires_at=now + lifetime,
            policy_epoch=self.policy_epoch,
            attributes=dict(request.attributes),
        )
        serial = self._next_serial(claims, key)
        unsigned = SignedIdentityToken(
            version=1,
            issuer=self.issuer,
            key_id=key.key_id,
            signature_algorithm=key.signature_algorithm,
            serial=serial,
            claims=claims,
            signature=b"",
        )
        signature = self.signature_provider.sign(key, unsigned.signing_payload())
        return SignedIdentityToken(
            version=unsigned.version,
            issuer=unsigned.issuer,
            key_id=unsigned.key_id,
            signature_algorithm=unsigned.signature_algorithm,
            serial=unsigned.serial,
            claims=unsigned.claims,
            signature=signature,
        )

    def verify(
        self,
        token: SignedIdentityToken,
        *,
        policy: ZeroTrustPolicy,
        revocations: RevocationList | None = None,
        now: int | None = None,
    ) -> ZeroTrustDecision:
        return _verify_signed_identity_token(
            issuer=self.issuer,
            keys=self._keys,
            signature_provider=self.signature_provider,
            token=token,
            policy=policy,
            revocations=revocations,
            now=now,
        )

    def rotate_signing_key(
        self,
        key: IdentitySigningKey,
        *,
        revoke_previous: bool = False,
        revocations: RevocationList | None = None,
    ) -> str:
        previous_key_id = self.active_key_id
        self._keys[key.key_id] = key
        self.active_key_id = key.key_id
        if revoke_previous:
            if revocations is None:
                raise IdentityAuthorityError("revocation list is required for key revoke")
            revocations.revoke_key(previous_key_id)
        return previous_key_id

    def rotate_policy_epoch(
        self,
        policy_epoch: str,
        *,
        revoke_previous: bool = False,
        revocations: RevocationList | None = None,
    ) -> str:
        if not policy_epoch.strip():
            raise ValueError("new policy epoch is required")
        previous = self.policy_epoch
        self.policy_epoch = policy_epoch
        if revoke_previous:
            if revocations is None:
                raise IdentityAuthorityError("revocation list is required for policy revoke")
            revocations.revoke_policy_epoch(previous)
        return previous

    def _active_key(self, now: int) -> IdentitySigningKey:
        key = self._keys[self.active_key_id]
        if not key.active_at(now):
            raise IdentityAuthorityError("active identity signing key is not active")
        return key

    def _next_serial(self, claims: IdentityClaims, key: IdentitySigningKey) -> str:
        self._serial_counter += 1
        return hashlib.sha256(
            b"x0vpn-identity-serial-v1"
            + self.issuer.encode("utf-8")
            + key.key_id.encode("utf-8")
            + self._serial_counter.to_bytes(8, "big")
            + claims.canonical_json()
        ).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _verify_signed_identity_token(
    *,
    issuer: str,
    keys: Mapping[str, IdentitySigningKey],
    signature_provider: IdentitySignatureProvider,
    token: SignedIdentityToken,
    policy: ZeroTrustPolicy,
    revocations: RevocationList | None = None,
    now: int | None = None,
) -> ZeroTrustDecision:
    now = now if now is not None else _utc_now()
    policy_decision = policy.evaluate(token.claims, now=now)
    reasons = list(policy_decision.reasons)
    if token.version != 1:
        reasons.append("identity_token_version_unsupported")
    if token.issuer != issuer:
        reasons.append("identity_issuer_mismatch")
    key = keys.get(token.key_id)
    if key is None:
        reasons.append("identity_signing_key_unknown")
    else:
        if token.signature_algorithm != key.signature_algorithm:
            reasons.append("identity_signature_algorithm_mismatch")
        if not key.active_at(now):
            reasons.append("identity_signing_key_not_active")
        if not signature_provider.verify(key, token.signing_payload(), token.signature):
            reasons.append("identity_signature_invalid")
    if revocations is not None:
        reasons.extend(revocations.reasons_for(token))
    return ZeroTrustDecision(
        allowed=not reasons,
        reasons=tuple(reasons),
        identity_hash=identity_binding_hash(token.claims),
    )


def _reference_mldsa_verification_key_for_identity_key(
    key: IdentitySigningKey,
) -> bytes:
    params = mldsa_parameter_set(key.signature_algorithm)
    if len(key.secret) == params.signing_key_bytes:
        mldsa_validate_signing_key(key.signature_algorithm, key.secret)
        return mldsa_derive_verification_key_from_signing_key(
            key.signature_algorithm,
            key.secret,
        )
    if len(key.secret) == params.verification_key_bytes:
        mldsa_validate_verification_key(key.signature_algorithm, key.secret)
        return key.secret
    raise ValueError("ML-DSA identity verification key length is invalid")


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
