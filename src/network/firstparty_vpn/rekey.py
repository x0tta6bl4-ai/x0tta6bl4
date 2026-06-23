"""First-party in-session PQC rekey handshake."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Callable, Protocol

from .handshake import (
    DEFAULT_MAX_HANDSHAKE_AGE_SECONDS,
    FirstPartyHandshakeAccept,
    FirstPartyHandshakeHello,
    PqcMaterialGate,
    accept_firstparty_handshake,
    complete_firstparty_handshake,
    create_firstparty_handshake_hello,
)
from .identity import IdentityVerifier, RevocationList, SignedIdentityToken
from .pqc import PqcProvider, PqcSessionSecretMaterial
from .protocol import Frame, FrameDecodeError, FrameType
from .session import SessionContext
from .zero_trust import ZeroTrustPolicy


REKEY_VERSION = 1
REKEY_REQUEST_MAGIC = b"X0REKEYR"
REKEY_ACCEPT_MAGIC = b"X0REKEYA"
RekeySecretResolver = Callable[["FirstPartyRekeyRequest"], PqcSessionSecretMaterial]
RekeyNonceProvider = Callable[["FirstPartyRekeyRequest"], bytes]
RekeyNowProvider = Callable[["FirstPartyRekeyRequest"], int]


class FirstPartyRekeyError(ValueError):
    """Raised when a first-party in-session rekey is invalid."""


@dataclass(frozen=True)
class FirstPartyRekeyRequest:
    """Client rekey request carried inside the currently protected session."""

    version: int
    previous_session_id: int
    previous_transcript_hash: str
    base_deployment_epoch: str
    generation: int
    reason: str
    hello: FirstPartyHandshakeHello

    def __post_init__(self) -> None:
        if self.version != REKEY_VERSION:
            raise FirstPartyRekeyError("unsupported rekey request version")
        if self.previous_session_id < 0:
            raise FirstPartyRekeyError("rekey previous session id is invalid")
        if len(self.previous_transcript_hash) != 64:
            raise FirstPartyRekeyError("rekey previous transcript hash is invalid")
        if self.generation < 1:
            raise FirstPartyRekeyError("rekey generation must be positive")
        if not self.reason.strip():
            raise FirstPartyRekeyError("rekey reason is required")
        if not self.base_deployment_epoch.strip():
            raise FirstPartyRekeyError("rekey base deployment epoch is required")
        if self.hello.deployment_epoch != _rekey_deployment_epoch(
            base_epoch=self.base_deployment_epoch,
            previous_session_id=self.previous_session_id,
            previous_transcript_hash=self.previous_transcript_hash,
            generation=self.generation,
            reason=self.reason,
        ):
            raise FirstPartyRekeyError("rekey deployment epoch binding mismatch")

    def request_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-rekey-request-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_payload(self) -> bytes:
        return REKEY_REQUEST_MAGIC + _canonical_json(self.to_json_dict())

    def to_frame(self, *, sequence: int) -> Frame:
        return Frame(
            frame_type=FrameType.DATA,
            session_id=self.previous_session_id,
            sequence=sequence,
            payload=self.to_payload(),
        )

    @classmethod
    def from_frame(cls, frame: Frame) -> "FirstPartyRekeyRequest":
        if frame.frame_type != FrameType.DATA:
            raise FirstPartyRekeyError("rekey request must be carried in DATA frame")
        request = cls.from_payload(frame.payload)
        if frame.session_id != request.previous_session_id:
            raise FirstPartyRekeyError("rekey request frame session id mismatch")
        return request

    @classmethod
    def from_payload(cls, payload: bytes) -> "FirstPartyRekeyRequest":
        if not payload.startswith(REKEY_REQUEST_MAGIC):
            raise FirstPartyRekeyError("rekey request magic mismatch")
        try:
            value = json.loads(payload[len(REKEY_REQUEST_MAGIC) :])
        except json.JSONDecodeError as exc:
            raise FrameDecodeError("invalid rekey request payload") from exc
        if not isinstance(value, dict):
            raise FirstPartyRekeyError("rekey request payload must be an object")
        return cls.from_json_dict(value)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "base_deployment_epoch": self.base_deployment_epoch,
            "generation": self.generation,
            "hello": self.hello.to_json_dict(),
            "previous_session_id": self.previous_session_id,
            "previous_transcript_hash": self.previous_transcript_hash,
            "reason": self.reason,
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "FirstPartyRekeyRequest":
        hello_raw = value.get("hello")
        if not isinstance(hello_raw, dict):
            raise FirstPartyRekeyError("rekey request hello must be an object")
        return cls(
            version=int(value.get("version", 0)),
            previous_session_id=int(value.get("previous_session_id", -1)),
            previous_transcript_hash=str(value.get("previous_transcript_hash", "")),
            base_deployment_epoch=str(value.get("base_deployment_epoch", "")),
            generation=int(value.get("generation", 0)),
            reason=str(value.get("reason", "")),
            hello=FirstPartyHandshakeHello.from_json_dict(hello_raw),
        )


@dataclass(frozen=True)
class FirstPartyRekeyAccept:
    """Server rekey accept carried inside the currently protected session."""

    version: int
    previous_session_id: int
    previous_transcript_hash: str
    generation: int
    request_hash: str
    accept: FirstPartyHandshakeAccept

    def __post_init__(self) -> None:
        if self.version != REKEY_VERSION:
            raise FirstPartyRekeyError("unsupported rekey accept version")
        if self.previous_session_id < 0:
            raise FirstPartyRekeyError("rekey accept previous session id is invalid")
        if len(self.previous_transcript_hash) != 64:
            raise FirstPartyRekeyError("rekey accept previous transcript hash is invalid")
        if self.generation < 1:
            raise FirstPartyRekeyError("rekey accept generation must be positive")
        if len(self.request_hash) != 64:
            raise FirstPartyRekeyError("rekey accept request hash is invalid")

    def to_payload(self) -> bytes:
        return REKEY_ACCEPT_MAGIC + _canonical_json(self.to_json_dict())

    def to_frame(self, *, sequence: int) -> Frame:
        return Frame(
            frame_type=FrameType.DATA,
            session_id=self.previous_session_id,
            sequence=sequence,
            payload=self.to_payload(),
        )

    @classmethod
    def from_frame(cls, frame: Frame) -> "FirstPartyRekeyAccept":
        if frame.frame_type != FrameType.DATA:
            raise FirstPartyRekeyError("rekey accept must be carried in DATA frame")
        accept = cls.from_payload(frame.payload)
        if frame.session_id != accept.previous_session_id:
            raise FirstPartyRekeyError("rekey accept frame session id mismatch")
        return accept

    @classmethod
    def from_payload(cls, payload: bytes) -> "FirstPartyRekeyAccept":
        if not payload.startswith(REKEY_ACCEPT_MAGIC):
            raise FirstPartyRekeyError("rekey accept magic mismatch")
        try:
            value = json.loads(payload[len(REKEY_ACCEPT_MAGIC) :])
        except json.JSONDecodeError as exc:
            raise FrameDecodeError("invalid rekey accept payload") from exc
        if not isinstance(value, dict):
            raise FirstPartyRekeyError("rekey accept payload must be an object")
        return cls.from_json_dict(value)

    def to_json_dict(self) -> dict[str, object]:
        return {
            "accept": self.accept.to_json_dict(),
            "generation": self.generation,
            "previous_session_id": self.previous_session_id,
            "previous_transcript_hash": self.previous_transcript_hash,
            "request_hash": self.request_hash,
            "version": self.version,
        }

    @classmethod
    def from_json_dict(cls, value: dict[str, object]) -> "FirstPartyRekeyAccept":
        accept_raw = value.get("accept")
        if not isinstance(accept_raw, dict):
            raise FirstPartyRekeyError("rekey accept handshake accept must be an object")
        return cls(
            version=int(value.get("version", 0)),
            previous_session_id=int(value.get("previous_session_id", -1)),
            previous_transcript_hash=str(value.get("previous_transcript_hash", "")),
            generation=int(value.get("generation", 0)),
            request_hash=str(value.get("request_hash", "")),
            accept=FirstPartyHandshakeAccept.from_json_dict(accept_raw),
        )


@dataclass(frozen=True)
class FirstPartyRekeyResult:
    session: SessionContext
    request: FirstPartyRekeyRequest
    accept: FirstPartyRekeyAccept


class FirstPartyRekeySecretStore:
    """In-memory resolver for local tests and rekey decapsulation adapters."""

    def __init__(self) -> None:
        self._materials: dict[str, PqcSessionSecretMaterial] = {}

    def add(self, material: PqcSessionSecretMaterial) -> None:
        self._materials[hashlib.sha256(material.ciphertext).hexdigest()] = material

    def resolve(self, request: FirstPartyRekeyRequest) -> PqcSessionSecretMaterial:
        try:
            return self._materials[request.hello.pqc_ciphertext_hash]
        except KeyError as exc:
            raise FirstPartyRekeyError("rekey PQC ciphertext is unknown") from exc


@dataclass(frozen=True)
class FirstPartyRekeyServerAction:
    """Server action that must be sent under old keys before endpoint rotation."""

    request: FirstPartyRekeyRequest
    accept: FirstPartyRekeyAccept
    next_session: SessionContext

    @property
    def response_payload(self) -> bytes:
        return self.accept.to_payload()


@dataclass(frozen=True)
class FirstPartyRekeyServerProcessor:
    """Accepts protected rekey DATA payloads for one live server endpoint."""

    server_identity: SignedIdentityToken
    identity_authority: IdentityVerifier
    policy: ZeroTrustPolicy
    shared_secret_resolver: RekeySecretResolver
    server_nonce_provider: RekeyNonceProvider
    accepted_at_provider: RekeyNowProvider
    revocations: RevocationList | None = None
    production_gate: PqcMaterialGate | None = None

    def try_accept(
        self,
        payload: bytes,
        *,
        previous_session: SessionContext,
    ) -> FirstPartyRekeyServerAction | None:
        if not payload.startswith(REKEY_REQUEST_MAGIC):
            return None
        request = FirstPartyRekeyRequest.from_payload(payload)
        result = accept_firstparty_rekey(
            request=request,
            previous_session=previous_session,
            server_identity=self.server_identity,
            identity_authority=self.identity_authority,
            policy=self.policy,
            shared_secret_resolver=self.shared_secret_resolver,
            server_nonce=self.server_nonce_provider(request),
            accepted_at=self.accepted_at_provider(request),
            revocations=self.revocations,
            production_gate=self.production_gate,
        )
        return FirstPartyRekeyServerAction(
            request=request,
            accept=result.accept,
            next_session=result.session,
        )


class FirstPartyRekeyTransportClient(Protocol):
    @property
    def endpoint(self): ...

    def send_data(self, payload: bytes) -> None: ...

    async def drain(self) -> None: ...

    async def recv(self, timeout: float = 1.0) -> Frame: ...


@dataclass(frozen=True)
class FirstPartyRekeyClientResult:
    request: FirstPartyRekeyRequest
    accept: FirstPartyRekeyAccept
    material: PqcSessionSecretMaterial
    next_session: SessionContext


def create_firstparty_rekey_request(
    *,
    pqc_provider: PqcProvider,
    previous_session: SessionContext,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    base_deployment_epoch: str,
    generation: int,
    reason: str,
    client_nonce: bytes,
    requested_at: int,
) -> tuple[FirstPartyRekeyRequest, PqcSessionSecretMaterial]:
    """Create a rekey request and local PQC material for the next session."""
    previous_hash = _previous_transcript_hash(previous_session)
    hello, material = create_firstparty_handshake_hello(
        pqc_provider=pqc_provider,
        client_identity=client_identity,
        server_identity=server_identity,
        deployment_epoch=_rekey_deployment_epoch(
            base_epoch=base_deployment_epoch,
            previous_session_id=previous_session.session_id,
            previous_transcript_hash=previous_hash,
            generation=generation,
            reason=reason,
        ),
        client_nonce=client_nonce,
        issued_at=requested_at,
    )
    request = FirstPartyRekeyRequest(
        version=REKEY_VERSION,
        previous_session_id=previous_session.session_id,
        previous_transcript_hash=previous_hash,
        base_deployment_epoch=base_deployment_epoch,
        generation=generation,
        reason=reason,
        hello=hello,
    )
    return request, material


async def perform_firstparty_transport_rekey(
    *,
    transport: FirstPartyRekeyTransportClient,
    pqc_provider: PqcProvider,
    client_identity: SignedIdentityToken,
    server_identity: SignedIdentityToken,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    base_deployment_epoch: str,
    generation: int,
    reason: str,
    client_nonce: bytes,
    requested_at: int,
    timeout: float = 1.0,
    revocations: RevocationList | None = None,
    completed_at_provider: Callable[[FirstPartyRekeyAccept], int] | None = None,
    production_gate: PqcMaterialGate | None = None,
) -> FirstPartyRekeyClientResult:
    """Perform a live rekey over an already protected client transport."""
    previous_session = transport.endpoint.session
    request, material = create_firstparty_rekey_request(
        pqc_provider=pqc_provider,
        previous_session=previous_session,
        client_identity=client_identity,
        server_identity=server_identity,
        base_deployment_epoch=base_deployment_epoch,
        generation=generation,
        reason=reason,
        client_nonce=client_nonce,
        requested_at=requested_at,
    )
    transport.send_data(request.to_payload())
    await transport.drain()
    accept_frame = await transport.recv(timeout=timeout)
    accept = FirstPartyRekeyAccept.from_frame(accept_frame)
    next_session = complete_firstparty_rekey(
        request=request,
        accept=accept,
        previous_session=previous_session,
        pqc_material=material,
        identity_authority=identity_authority,
        policy=policy,
        revocations=revocations,
        completed_at=(
            completed_at_provider(accept)
            if completed_at_provider is not None
            else None
        ),
        production_gate=production_gate,
    )
    transport.endpoint.rotate_session(next_session)
    return FirstPartyRekeyClientResult(
        request=request,
        accept=accept,
        material=material,
        next_session=next_session,
    )


def accept_firstparty_rekey(
    *,
    request: FirstPartyRekeyRequest,
    previous_session: SessionContext,
    server_identity: SignedIdentityToken,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    shared_secret_resolver: RekeySecretResolver,
    server_nonce: bytes,
    accepted_at: int,
    revocations: RevocationList | None = None,
    production_gate: PqcMaterialGate | None = None,
) -> FirstPartyRekeyResult:
    """Verify a protected rekey request and return the server next-session context."""
    _assert_request_matches_previous_session(request, previous_session)
    material = shared_secret_resolver(request)
    server_result = accept_firstparty_handshake(
        hello=request.hello,
        server_identity=server_identity,
        identity_authority=identity_authority,
        policy=policy,
        shared_secret_resolver=lambda _hello: material,
        server_nonce=server_nonce,
        accepted_at=accepted_at,
        revocations=revocations,
        production_gate=production_gate,
    )
    accept = FirstPartyRekeyAccept(
        version=REKEY_VERSION,
        previous_session_id=request.previous_session_id,
        previous_transcript_hash=request.previous_transcript_hash,
        generation=request.generation,
        request_hash=request.request_hash(),
        accept=server_result.accept,
    )
    return FirstPartyRekeyResult(
        session=server_result.session,
        request=request,
        accept=accept,
    )


def complete_firstparty_rekey(
    *,
    request: FirstPartyRekeyRequest,
    accept: FirstPartyRekeyAccept,
    previous_session: SessionContext,
    pqc_material: PqcSessionSecretMaterial,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    revocations: RevocationList | None = None,
    completed_at: int | None = None,
    max_accept_age_seconds: int = DEFAULT_MAX_HANDSHAKE_AGE_SECONDS,
    production_gate: PqcMaterialGate | None = None,
) -> SessionContext:
    """Verify a server rekey accept and return the client next-session context."""
    _assert_request_matches_previous_session(request, previous_session)
    if accept.previous_session_id != request.previous_session_id:
        raise FirstPartyRekeyError("rekey accept previous session id mismatch")
    if accept.previous_transcript_hash != request.previous_transcript_hash:
        raise FirstPartyRekeyError("rekey accept previous transcript hash mismatch")
    if accept.generation != request.generation:
        raise FirstPartyRekeyError("rekey accept generation mismatch")
    if accept.request_hash != request.request_hash():
        raise FirstPartyRekeyError("rekey accept request hash mismatch")
    return complete_firstparty_handshake(
        hello=request.hello,
        accept=accept.accept,
        pqc_material=pqc_material,
        identity_authority=identity_authority,
        policy=policy,
        revocations=revocations,
        completed_at=completed_at,
        max_accept_age_seconds=max_accept_age_seconds,
        production_gate=production_gate,
    )


def _assert_request_matches_previous_session(
    request: FirstPartyRekeyRequest,
    previous_session: SessionContext,
) -> None:
    if request.previous_session_id != previous_session.session_id:
        raise FirstPartyRekeyError("rekey previous session id mismatch")
    if request.previous_transcript_hash != _previous_transcript_hash(previous_session):
        raise FirstPartyRekeyError("rekey previous transcript hash mismatch")


def _previous_transcript_hash(session: SessionContext) -> str:
    return hashlib.sha256(session.transcript).hexdigest()


def _rekey_deployment_epoch(
    *,
    base_epoch: str,
    previous_session_id: int,
    previous_transcript_hash: str,
    generation: int,
    reason: str,
) -> str:
    payload = {
        "base_epoch": base_epoch,
        "generation": generation,
        "previous_session_id": previous_session_id,
        "previous_transcript_hash": previous_transcript_hash,
        "reason": reason,
        "version": REKEY_VERSION,
    }
    return "rekey:" + hashlib.sha256(
        b"x0vpn-rekey-epoch-v1" + _canonical_json(payload)
    ).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
