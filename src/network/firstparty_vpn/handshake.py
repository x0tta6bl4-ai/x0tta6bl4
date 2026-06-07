"""First-party HELLO/ACCEPT session handshake for X0VPN001."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Protocol

from .identity import IdentityVerifier, RevocationList, SignedIdentityToken
from .pqc import PqcProvider, PqcProviderGateDecision, PqcSessionSecretMaterial
from .protocol import Frame, FrameDecodeError, FrameType
from .session import (
    SessionContext,
    establish_firstparty_session_from_signed_identities,
    _session_transcript,
)
from .zero_trust import IdentityClaims, ZeroTrustPolicy, identity_binding_hash


HANDSHAKE_VERSION = 1
HANDSHAKE_SESSION_ID = 0
DEFAULT_MAX_HANDSHAKE_AGE_SECONDS = 300
HandshakeSecretResolver = Callable[["FirstPartyHandshakeHello"], PqcSessionSecretMaterial]


class FirstPartyHandshakeError(ValueError):
    """Raised when a first-party handshake is invalid."""


class PqcMaterialGate(Protocol):
    """Fail-closed gate for PQC material before session key creation."""

    def evaluate(
        self,
        material: PqcSessionSecretMaterial,
        *,
        now: int | None = None,
    ) -> PqcProviderGateDecision: ...


@dataclass(frozen=True)
class FirstPartyHandshakeHello:
    """Client HELLO payload for first-party session admission."""

    version: int
    deployment_epoch: str
    client_identity: SignedIdentityToken
    server_identity_hash: str
    kem_algorithm: str
    signature_algorithm: str
    pqc_ciphertext: bytes
    pqc_attestation_hash: str
    client_nonce: bytes
    issued_at: int

    def __post_init__(self) -> None:
        if self.version != HANDSHAKE_VERSION:
            raise FirstPartyHandshakeError("unsupported handshake hello version")
        if not self.deployment_epoch.strip():
            raise FirstPartyHandshakeError("handshake deployment epoch is required")
        if len(self.server_identity_hash) != 64:
            raise FirstPartyHandshakeError("handshake server identity hash is invalid")
        if not self.kem_algorithm.strip() or not self.signature_algorithm.strip():
            raise FirstPartyHandshakeError("handshake algorithms are required")
        if not self.pqc_ciphertext:
            raise FirstPartyHandshakeError("handshake PQC ciphertext is required")
        if not self.pqc_attestation_hash.strip():
            raise FirstPartyHandshakeError("handshake PQC attestation hash is required")
        if not self.client_nonce:
            raise FirstPartyHandshakeError("handshake client nonce is required")
        if self.issued_at < 0:
            raise FirstPartyHandshakeError("handshake issued_at is invalid")

    @property
    def pqc_ciphertext_hash(self) -> str:
        return hashlib.sha256(self.pqc_ciphertext).hexdigest()

    def hello_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-handshake-hello-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_frame(self, *, sequence: int = 1) -> Frame:
        return Frame(
            frame_type=FrameType.HELLO,
            session_id=HANDSHAKE_SESSION_ID,
            sequence=sequence,
            payload=_canonical_json(self.to_json_dict()),
        )

    @classmethod
    def from_frame(cls, frame: Frame) -> "FirstPartyHandshakeHello":
        if frame.frame_type != FrameType.HELLO:
            raise FirstPartyHandshakeError("expected HELLO frame")
        if frame.session_id != HANDSHAKE_SESSION_ID:
            raise FirstPartyHandshakeError("HELLO frame session id must be zero")
        return cls.from_payload(frame.payload)

    @classmethod
    def from_payload(cls, payload: bytes) -> "FirstPartyHandshakeHello":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FrameDecodeError("invalid HELLO payload") from exc
        if not isinstance(value, dict):
            raise FirstPartyHandshakeError("HELLO payload must be an object")
        return cls.from_json_dict(value)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "client_identity": _token_to_json_dict(self.client_identity),
            "client_nonce": self.client_nonce.hex(),
            "deployment_epoch": self.deployment_epoch,
            "issued_at": self.issued_at,
            "kem_algorithm": self.kem_algorithm,
            "pqc_attestation_hash": self.pqc_attestation_hash,
            "pqc_ciphertext": self.pqc_ciphertext.hex(),
            "pqc_ciphertext_hash": self.pqc_ciphertext_hash,
            "server_identity_hash": self.server_identity_hash,
            "signature_algorithm": self.signature_algorithm,
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "FirstPartyHandshakeHello":
        ciphertext = bytes.fromhex(str(value.get("pqc_ciphertext", "")))
        expected_hash = str(value.get("pqc_ciphertext_hash", ""))
        if hashlib.sha256(ciphertext).hexdigest() != expected_hash:
            raise FirstPartyHandshakeError("HELLO PQC ciphertext hash mismatch")
        return cls(
            version=int(value.get("version", 0)),
            deployment_epoch=str(value.get("deployment_epoch", "")),
            client_identity=_token_from_json_dict(_object(value, "client_identity")),
            server_identity_hash=str(value.get("server_identity_hash", "")),
            kem_algorithm=str(value.get("kem_algorithm", "")),
            signature_algorithm=str(value.get("signature_algorithm", "")),
            pqc_ciphertext=ciphertext,
            pqc_attestation_hash=str(value.get("pqc_attestation_hash", "")),
            client_nonce=bytes.fromhex(str(value.get("client_nonce", ""))),
            issued_at=int(value.get("issued_at", 0)),
        )


@dataclass(frozen=True)
class FirstPartyHandshakeAccept:
    """Server ACCEPT payload for first-party session admission."""

    version: int
    hello_hash: str
    server_identity: SignedIdentityToken
    server_nonce: bytes
    session_id: int
    accepted_at: int

    def __post_init__(self) -> None:
        if self.version != HANDSHAKE_VERSION:
            raise FirstPartyHandshakeError("unsupported handshake accept version")
        if len(self.hello_hash) != 64:
            raise FirstPartyHandshakeError("ACCEPT hello hash is invalid")
        if not self.server_nonce:
            raise FirstPartyHandshakeError("handshake server nonce is required")
        if self.session_id < 0:
            raise FirstPartyHandshakeError("handshake session id is invalid")
        if self.accepted_at < 0:
            raise FirstPartyHandshakeError("handshake accepted_at is invalid")

    def accept_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-handshake-accept-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_frame(self, *, sequence: int = 1) -> Frame:
        return Frame(
            frame_type=FrameType.ACCEPT,
            session_id=self.session_id,
            sequence=sequence,
            payload=_canonical_json(self.to_json_dict()),
        )

    @classmethod
    def from_frame(cls, frame: Frame) -> "FirstPartyHandshakeAccept":
        if frame.frame_type != FrameType.ACCEPT:
            raise FirstPartyHandshakeError("expected ACCEPT frame")
        accept = cls.from_payload(frame.payload)
        if frame.session_id != accept.session_id:
            raise FirstPartyHandshakeError("ACCEPT frame session id mismatch")
        return accept

    @classmethod
    def from_payload(cls, payload: bytes) -> "FirstPartyHandshakeAccept":
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise FrameDecodeError("invalid ACCEPT payload") from exc
        if not isinstance(value, dict):
            raise FirstPartyHandshakeError("ACCEPT payload must be an object")
        return cls.from_json_dict(value)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "accepted_at": self.accepted_at,
            "hello_hash": self.hello_hash,
            "server_identity": _token_to_json_dict(self.server_identity),
            "server_nonce": self.server_nonce.hex(),
            "session_id": self.session_id,
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "FirstPartyHandshakeAccept":
        return cls(
            version=int(value.get("version", 0)),
            hello_hash=str(value.get("hello_hash", "")),
            server_identity=_token_from_json_dict(_object(value, "server_identity")),
            server_nonce=bytes.fromhex(str(value.get("server_nonce", ""))),
            session_id=int(value.get("session_id", -1)),
            accepted_at=int(value.get("accepted_at", 0)),
        )


@dataclass(frozen=True)
class FirstPartyHandshakeResult:
    session: SessionContext
    hello: FirstPartyHandshakeHello
    accept: FirstPartyHandshakeAccept


class FirstPartyHandshakeSecretStore:
    """In-memory resolver for local tests and decapsulation adapters."""

    def __init__(self) -> None:
        self._materials: dict[str, PqcSessionSecretMaterial] = {}

    def add(self, material: PqcSessionSecretMaterial) -> None:
        self._materials[hashlib.sha256(material.ciphertext).hexdigest()] = material

    def resolve(self, hello: FirstPartyHandshakeHello) -> PqcSessionSecretMaterial:
        try:
            return self._materials[hello.pqc_ciphertext_hash]
        except KeyError as exc:
            raise FirstPartyHandshakeError("PQC ciphertext is unknown") from exc


def create_firstparty_handshake_hello(
    *,
    pqc_provider: PqcProvider,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    deployment_epoch: str,
    client_nonce: bytes,
    issued_at: int,
) -> tuple[FirstPartyHandshakeHello, PqcSessionSecretMaterial]:
    """Create a first-party HELLO and local PQC material."""
    transcript = _handshake_session_transcript(
        kem_algorithm=pqc_provider.attestation.kem_algorithm,
        signature_algorithm=pqc_provider.attestation.signature_algorithm,
        client_identity=client_identity,
        server_identity=server_identity,
        deployment_epoch=deployment_epoch,
    )
    material = pqc_provider.create_session_material(
        transcript=transcript,
        client_identity_hash=identity_binding_hash(client_identity.claims),
        server_identity_hash=identity_binding_hash(server_identity.claims),
    )
    hello = FirstPartyHandshakeHello(
        version=HANDSHAKE_VERSION,
        deployment_epoch=deployment_epoch,
        client_identity=client_identity,
        server_identity_hash=identity_binding_hash(server_identity.claims).hex(),
        kem_algorithm=material.kem_algorithm,
        signature_algorithm=material.signature_algorithm,
        pqc_ciphertext=material.ciphertext,
        pqc_attestation_hash=material.attestation.attestation_hash(),
        client_nonce=client_nonce,
        issued_at=issued_at,
    )
    return hello, material


def accept_firstparty_handshake(
    *,
    hello: FirstPartyHandshakeHello,
    server_identity: SignedIdentityToken,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    shared_secret_resolver: HandshakeSecretResolver,
    server_nonce: bytes,
    accepted_at: int,
    revocations: RevocationList | None = None,
    max_hello_age_seconds: int = DEFAULT_MAX_HANDSHAKE_AGE_SECONDS,
    production_gate: PqcMaterialGate | None = None,
) -> FirstPartyHandshakeResult:
    """Verify HELLO and build ACCEPT plus server session context."""
    _assert_hello_fresh(
        hello,
        accepted_at=accepted_at,
        max_hello_age_seconds=max_hello_age_seconds,
    )
    _assert_server_matches_hello(hello, server_identity)
    material = shared_secret_resolver(hello)
    _assert_material_matches_hello(hello, material)
    _assert_pqc_gate_allows(
        material,
        production_gate=production_gate,
        now=accepted_at,
    )
    session = establish_firstparty_session_from_signed_identities(
        kem_algorithm=hello.kem_algorithm,
        signature_algorithm=hello.signature_algorithm,
        pqc_shared_secret=material.shared_secret,
        client_identity=hello.client_identity,
        server_identity=server_identity,
        identity_authority=identity_authority,
        policy=policy,
        revocations=revocations,
        now=accepted_at,
        client_nonce=hello.client_nonce,
        server_nonce=server_nonce,
        deployment_epoch=hello.deployment_epoch,
    )
    accept = FirstPartyHandshakeAccept(
        version=HANDSHAKE_VERSION,
        hello_hash=hello.hello_hash(),
        server_identity=server_identity,
        server_nonce=server_nonce,
        session_id=session.session_id,
        accepted_at=accepted_at,
    )
    return FirstPartyHandshakeResult(session=session, hello=hello, accept=accept)


def complete_firstparty_handshake(
    *,
    hello: FirstPartyHandshakeHello,
    accept: FirstPartyHandshakeAccept,
    pqc_material: PqcSessionSecretMaterial,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    revocations: RevocationList | None = None,
    completed_at: int | None = None,
    max_accept_age_seconds: int = DEFAULT_MAX_HANDSHAKE_AGE_SECONDS,
    production_gate: PqcMaterialGate | None = None,
) -> SessionContext:
    """Verify ACCEPT and return the client-side session context."""
    if accept.hello_hash != hello.hello_hash():
        raise FirstPartyHandshakeError("ACCEPT does not match HELLO")
    _assert_accept_fresh(
        hello,
        accept,
        completed_at=completed_at,
        max_accept_age_seconds=max_accept_age_seconds,
    )
    _assert_server_matches_hello(hello, accept.server_identity)
    _assert_material_matches_hello(hello, pqc_material)
    _assert_pqc_gate_allows(
        pqc_material,
        production_gate=production_gate,
        now=completed_at if completed_at is not None else accept.accepted_at,
    )
    session = establish_firstparty_session_from_signed_identities(
        kem_algorithm=hello.kem_algorithm,
        signature_algorithm=hello.signature_algorithm,
        pqc_shared_secret=pqc_material.shared_secret,
        client_identity=hello.client_identity,
        server_identity=accept.server_identity,
        identity_authority=identity_authority,
        policy=policy,
        revocations=revocations,
        now=accept.accepted_at,
        client_nonce=hello.client_nonce,
        server_nonce=accept.server_nonce,
        deployment_epoch=hello.deployment_epoch,
    )
    if session.session_id != accept.session_id:
        raise FirstPartyHandshakeError("ACCEPT session id mismatch")
    return session


def _handshake_session_transcript(
    *,
    kem_algorithm: str,
    signature_algorithm: str,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    deployment_epoch: str,
) -> bytes:
    return _session_transcript(
        kem_algorithm=kem_algorithm,
        signature_algorithm=signature_algorithm,
        client_identity=client_identity.claims,
        server_identity=server_identity.claims,
        deployment_epoch=deployment_epoch,
    )


def _assert_server_matches_hello(
    hello: FirstPartyHandshakeHello,
    server_identity: SignedIdentityToken,
) -> None:
    if identity_binding_hash(server_identity.claims).hex() != hello.server_identity_hash:
        raise FirstPartyHandshakeError("server identity does not match HELLO")


def _assert_hello_fresh(
    hello: FirstPartyHandshakeHello,
    *,
    accepted_at: int,
    max_hello_age_seconds: int,
) -> None:
    if accepted_at < 0:
        raise FirstPartyHandshakeError("handshake accepted_at is invalid")
    if max_hello_age_seconds < 1:
        raise FirstPartyHandshakeError("handshake max age must be positive")
    if hello.issued_at > accepted_at:
        raise FirstPartyHandshakeError("handshake HELLO issued in the future")
    if accepted_at - hello.issued_at > max_hello_age_seconds:
        raise FirstPartyHandshakeError("handshake HELLO is stale")


def _assert_accept_fresh(
    hello: FirstPartyHandshakeHello,
    accept: FirstPartyHandshakeAccept,
    *,
    completed_at: int | None,
    max_accept_age_seconds: int,
) -> None:
    if max_accept_age_seconds < 1:
        raise FirstPartyHandshakeError("handshake accept max age must be positive")
    if accept.accepted_at < hello.issued_at:
        raise FirstPartyHandshakeError("handshake ACCEPT predates HELLO")
    if accept.accepted_at - hello.issued_at > max_accept_age_seconds:
        raise FirstPartyHandshakeError("handshake ACCEPT is stale for HELLO")
    if completed_at is None:
        return
    if completed_at < 0:
        raise FirstPartyHandshakeError("handshake completed_at is invalid")
    if accept.accepted_at > completed_at:
        raise FirstPartyHandshakeError("handshake ACCEPT accepted in the future")
    if completed_at - accept.accepted_at > max_accept_age_seconds:
        raise FirstPartyHandshakeError("handshake ACCEPT is stale")


def _assert_material_matches_hello(
    hello: FirstPartyHandshakeHello,
    material: PqcSessionSecretMaterial,
) -> None:
    if hashlib.sha256(material.ciphertext).hexdigest() != hello.pqc_ciphertext_hash:
        raise FirstPartyHandshakeError("PQC material does not match HELLO")
    if material.attestation.attestation_hash() != hello.pqc_attestation_hash:
        raise FirstPartyHandshakeError("PQC attestation does not match HELLO")
    if material.kem_algorithm != hello.kem_algorithm:
        raise FirstPartyHandshakeError("PQC KEM does not match HELLO")
    if material.signature_algorithm != hello.signature_algorithm:
        raise FirstPartyHandshakeError("PQC signature does not match HELLO")


def _assert_pqc_gate_allows(
    material: PqcSessionSecretMaterial,
    *,
    production_gate: PqcMaterialGate | None,
    now: int | None,
) -> None:
    if production_gate is None:
        return
    decision = production_gate.evaluate(material, now=now)
    if not decision.allowed:
        raise FirstPartyHandshakeError(
            "PQC production gate failed: " + ",".join(decision.reasons)
        )


def _token_to_json_dict(token: SignedIdentityToken) -> dict[str, object]:
    return {
        "claims": json.loads(token.claims.canonical_json()),
        "issuer": token.issuer,
        "key_id": token.key_id,
        "serial": token.serial,
        "signature": token.signature.hex(),
        "signature_algorithm": token.signature_algorithm,
        "version": token.version,
    }


def _token_from_json_dict(value: dict[str, object]) -> SignedIdentityToken:
    return SignedIdentityToken(
        version=int(value.get("version", 0)),
        issuer=str(value.get("issuer", "")),
        key_id=str(value.get("key_id", "")),
        signature_algorithm=str(value.get("signature_algorithm", "")),
        serial=str(value.get("serial", "")),
        claims=_claims_from_json_dict(_object(value, "claims")),
        signature=bytes.fromhex(str(value.get("signature", ""))),
    )


def _claims_from_json_dict(value: dict[str, object]) -> IdentityClaims:
    attributes_raw = value.get("attributes", {})
    if not isinstance(attributes_raw, dict):
        raise FirstPartyHandshakeError("identity attributes must be an object")
    return IdentityClaims(
        spiffe_id=str(value.get("spiffe_id", "")),
        did=str(value.get("did", "")),
        workload=str(value.get("workload", "")),
        tenant=str(value.get("tenant", "")),
        device_id=str(value.get("device_id", "")),
        pqc_kem_algorithm=str(value.get("pqc_kem_algorithm", "")),
        pqc_signature_algorithm=str(value.get("pqc_signature_algorithm", "")),
        issued_at=int(value.get("issued_at", 0)),
        expires_at=int(value.get("expires_at", 0)),
        policy_epoch=str(value.get("policy_epoch", "")),
        attributes={str(key): str(item) for key, item in attributes_raw.items()},
    )


def _object(value: dict[str, object], key: str) -> dict[str, object]:
    item = value.get(key)
    if not isinstance(item, dict):
        raise FirstPartyHandshakeError(f"{key} must be an object")
    return item


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
