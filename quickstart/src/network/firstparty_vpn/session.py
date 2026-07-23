"""Session admission for the first-party VPN core."""

from __future__ import annotations

from dataclasses import dataclass
import json

from .crypto import FrameCrypto, PqcSessionMaterial, SessionKeys, derive_session_keys
from .identity import IdentityVerifier, RevocationList, SignedIdentityToken
from .policy_store import PolicySnapshot
from .pqc import PqcProductionGate, PqcProvider
from .protocol import WireCodec
from .zero_trust import IdentityClaims, ZeroTrustDecision, ZeroTrustPolicy, identity_binding_hash


class ZeroTrustAdmissionError(ValueError):
    """Raised when a first-party VPN session fails zero-trust admission."""


@dataclass(frozen=True)
class SessionContext:
    session_id: int
    keys: SessionKeys
    client_codec: WireCodec
    server_codec: WireCodec
    client_decision: ZeroTrustDecision
    server_decision: ZeroTrustDecision
    transcript: bytes


def establish_firstparty_session(
    *,
    kem_algorithm: str,
    signature_algorithm: str,
    pqc_shared_secret: bytes,
    client_identity: IdentityClaims,
    server_identity: IdentityClaims,
    policy: ZeroTrustPolicy,
    now: int | None = None,
    client_nonce: bytes | None = None,
    server_nonce: bytes | None = None,
    deployment_epoch: str = "local-dev",
) -> SessionContext:
    """Admit and key a first-party VPN session.

    The session is fail-closed: both endpoint identities must pass policy before
    any frame codec is returned.
    """
    client_decision = policy.evaluate(client_identity, now=now)
    server_decision = policy.evaluate(server_identity, now=now)
    client_algorithm_reasons = _identity_algorithm_binding_reasons(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        identity=client_identity,
    )
    server_algorithm_reasons = _identity_algorithm_binding_reasons(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        identity=server_identity,
    )
    if (
        not client_decision.allowed
        or not server_decision.allowed
        or client_algorithm_reasons
        or server_algorithm_reasons
    ):
        reasons = {
            "client": client_decision.reasons + client_algorithm_reasons,
            "server": server_decision.reasons + server_algorithm_reasons,
        }
        raise ZeroTrustAdmissionError(json.dumps(reasons, sort_keys=True))

    transcript = _session_transcript(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        client_identity=client_identity,
        server_identity=server_identity,
        deployment_epoch=deployment_epoch,
    )
    material = PqcSessionMaterial.create(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        pqc_shared_secret=pqc_shared_secret,
        transcript=transcript,
        client_identity_hash=identity_binding_hash(client_identity),
        server_identity_hash=identity_binding_hash(server_identity),
        client_nonce=client_nonce,
        server_nonce=server_nonce,
        deployment_epoch=deployment_epoch,
    )
    keys = derive_session_keys(material)
    client_codec = WireCodec(
        FrameCrypto(encrypt_key=keys.client_tx, decrypt_key=keys.client_rx)
    )
    server_codec = WireCodec(
        FrameCrypto(encrypt_key=keys.server_tx, decrypt_key=keys.server_rx)
    )
    return SessionContext(
        session_id=keys.session_id,
        keys=keys,
        client_codec=client_codec,
        server_codec=server_codec,
        client_decision=client_decision,
        server_decision=server_decision,
        transcript=transcript,
    )


def establish_firstparty_session_from_signed_identities(
    *,
    kem_algorithm: str,
    signature_algorithm: str,
    pqc_shared_secret: bytes,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    revocations: RevocationList | None = None,
    now: int | None = None,
    client_nonce: bytes | None = None,
    server_nonce: bytes | None = None,
    deployment_epoch: str = "local-dev",
) -> SessionContext:
    """Admit a session only after signed identity tokens verify."""
    client_decision = identity_authority.verify(
        client_identity,
        policy=policy,
        revocations=revocations,
        now=now,
    )
    server_decision = identity_authority.verify(
        server_identity,
        policy=policy,
        revocations=revocations,
        now=now,
    )
    if not client_decision.allowed or not server_decision.allowed:
        reasons = {
            "client": client_decision.reasons,
            "server": server_decision.reasons,
        }
        raise ZeroTrustAdmissionError(json.dumps(reasons, sort_keys=True))
    return establish_firstparty_session(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        pqc_shared_secret=pqc_shared_secret,
        client_identity=client_identity.claims,
        server_identity=server_identity.claims,
        policy=policy,
        now=now,
        client_nonce=client_nonce,
        server_nonce=server_nonce,
        deployment_epoch=deployment_epoch,
    )


def establish_firstparty_session_from_policy_snapshot(
    *,
    kem_algorithm: str,
    signature_algorithm: str,
    pqc_shared_secret: bytes,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    identity_authority: IdentityVerifier,
    policy_snapshot: PolicySnapshot,
    policy: ZeroTrustPolicy,
    now: int | None = None,
    client_nonce: bytes | None = None,
    server_nonce: bytes | None = None,
    deployment_epoch: str = "local-dev",
) -> SessionContext:
    """Admit a session through the durable policy snapshot gate."""
    client_decision = policy_snapshot.evaluate_signed_identity(
        identity_authority,
        client_identity,
        policy=policy,
        now=now,
    )
    server_decision = policy_snapshot.evaluate_signed_identity(
        identity_authority,
        server_identity,
        policy=policy,
        now=now,
    )
    if not client_decision.allowed or not server_decision.allowed:
        reasons = {
            "client": client_decision.reasons,
            "server": server_decision.reasons,
        }
        raise ZeroTrustAdmissionError(json.dumps(reasons, sort_keys=True))
    return establish_firstparty_session(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        pqc_shared_secret=pqc_shared_secret,
        client_identity=client_identity.claims,
        server_identity=server_identity.claims,
        policy=policy,
        now=now,
        client_nonce=client_nonce,
        server_nonce=server_nonce,
        deployment_epoch=deployment_epoch,
    )


def establish_firstparty_session_from_pqc_provider(
    *,
    pqc_provider: PqcProvider,
    client_identity: IdentityClaims,
    server_identity: IdentityClaims,
    policy: ZeroTrustPolicy,
    production_gate: PqcProductionGate | None = None,
    require_production_provider: bool = False,
    now: int | None = None,
    client_nonce: bytes | None = None,
    server_nonce: bytes | None = None,
    deployment_epoch: str = "local-dev",
) -> SessionContext:
    """Admit a session using a gated PQC provider output."""
    transcript = _session_transcript(
        kem_algorithm=pqc_provider.attestation.kem_algorithm,
        signature_algorithm=pqc_provider.attestation.signature_algorithm,
        client_identity=client_identity,
        server_identity=server_identity,
        deployment_epoch=deployment_epoch,
    )
    material = pqc_provider.create_session_material(
        transcript=transcript,
        client_identity_hash=identity_binding_hash(client_identity),
        server_identity_hash=identity_binding_hash(server_identity),
    )
    gate = production_gate or PqcProductionGate(
        require_production=require_production_provider
    )
    gate_decision = gate.evaluate(material, now=now)
    if not gate_decision.allowed:
        raise ZeroTrustAdmissionError(
            json.dumps({"pqc_provider": gate_decision.reasons}, sort_keys=True)
        )
    return establish_firstparty_session(
        kem_algorithm=material.kem_algorithm,
        signature_algorithm=material.signature_algorithm,
        pqc_shared_secret=material.shared_secret,
        client_identity=client_identity,
        server_identity=server_identity,
        policy=policy,
        now=now,
        client_nonce=client_nonce,
        server_nonce=server_nonce,
        deployment_epoch=deployment_epoch,
    )


def establish_firstparty_session_from_pqc_provider_and_signed_identities(
    *,
    pqc_provider: PqcProvider,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    production_gate: PqcProductionGate | None = None,
    require_production_provider: bool = False,
    revocations: RevocationList | None = None,
    now: int | None = None,
    client_nonce: bytes | None = None,
    server_nonce: bytes | None = None,
    deployment_epoch: str = "local-dev",
) -> SessionContext:
    """Admit a provider-backed session only after signed identity verification."""
    client_decision = identity_authority.verify(
        client_identity,
        policy=policy,
        revocations=revocations,
        now=now,
    )
    server_decision = identity_authority.verify(
        server_identity,
        policy=policy,
        revocations=revocations,
        now=now,
    )
    if not client_decision.allowed or not server_decision.allowed:
        reasons = {
            "client": client_decision.reasons,
            "server": server_decision.reasons,
        }
        raise ZeroTrustAdmissionError(json.dumps(reasons, sort_keys=True))
    return establish_firstparty_session_from_pqc_provider(
        pqc_provider=pqc_provider,
        client_identity=client_identity.claims,
        server_identity=server_identity.claims,
        policy=policy,
        production_gate=production_gate,
        require_production_provider=require_production_provider,
        now=now,
        client_nonce=client_nonce,
        server_nonce=server_nonce,
        deployment_epoch=deployment_epoch,
    )


def _session_transcript(
    *,
    kem_algorithm: str,
    signature_algorithm: str,
    client_identity: IdentityClaims,
    server_identity: IdentityClaims,
    deployment_epoch: str,
) -> bytes:
    return json.dumps(
        {
            "deployment_epoch": deployment_epoch,
            "kem_algorithm": kem_algorithm,
            "protocol": "x0tta6bl4-firstparty-vpn-v1",
            "signature_algorithm": signature_algorithm,
            "client_identity_hash": identity_binding_hash(client_identity).hex(),
            "server_identity_hash": identity_binding_hash(server_identity).hex(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _identity_algorithm_binding_reasons(
    *,
    kem_algorithm: str,
    signature_algorithm: str,
    identity: IdentityClaims,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if identity.pqc_kem_algorithm != kem_algorithm:
        reasons.append("pqc_kem_algorithm_mismatch")
    if identity.pqc_signature_algorithm != signature_algorithm:
        reasons.append("pqc_signature_algorithm_mismatch")
    return tuple(reasons)
