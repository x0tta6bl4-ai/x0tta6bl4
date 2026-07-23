"""Fail-closed session admission registry for first-party VPN runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .handshake import (
    DEFAULT_MAX_HANDSHAKE_AGE_SECONDS,
    FirstPartyHandshakeHello,
    FirstPartyHandshakeResult,
    HandshakeSecretResolver,
    PqcMaterialGate,
    accept_firstparty_handshake,
)
from .identity import IdentityVerifier, RevocationList, SignedIdentityToken
from .session import SessionContext
from .zero_trust import ZeroTrustPolicy, identity_binding_hash


class FirstPartySessionAdmissionError(ValueError):
    """Raised when a session cannot be admitted into the runtime registry."""


ServerNonceProvider = Callable[[FirstPartyHandshakeHello], bytes]
AcceptedAtProvider = Callable[[FirstPartyHandshakeHello], int]


@dataclass
class FirstPartySessionAdmissionRegistry:
    """Owns fail-closed HELLO/ACCEPT admission state for runtime listeners."""

    server_identity: SignedIdentityToken
    identity_authority: IdentityVerifier
    policy: ZeroTrustPolicy
    shared_secret_resolver: HandshakeSecretResolver
    server_nonce_provider: ServerNonceProvider
    accepted_at_provider: AcceptedAtProvider
    revocations: RevocationList | None = None
    alternate_server_identities: tuple[SignedIdentityToken, ...] = ()
    client_identity_hash_allowlist: frozenset[str] = frozenset()
    enforce_client_identity_allowlist: bool = False
    max_hello_age_seconds: int = DEFAULT_MAX_HANDSHAKE_AGE_SECONDS
    production_gate: PqcMaterialGate | None = None
    _sessions_by_id: dict[int, SessionContext] = field(default_factory=dict, init=False)
    _accepted_hello_hashes: set[str] = field(default_factory=set, init=False)

    def __post_init__(self) -> None:
        if self.max_hello_age_seconds < 1:
            raise FirstPartySessionAdmissionError(
                "handshake max age must be positive"
            )
        server_identity_hashes: set[str] = set()
        for identity in (self.server_identity, *self.alternate_server_identities):
            identity_hash = identity_binding_hash(identity.claims).hex()
            if identity_hash in server_identity_hashes:
                raise FirstPartySessionAdmissionError(
                    "server identity candidates contain duplicate hash"
                )
            server_identity_hashes.add(identity_hash)
        for identity_hash in self.client_identity_hash_allowlist:
            if len(identity_hash) != 64:
                raise FirstPartySessionAdmissionError(
                    "client identity allowlist contains invalid hash"
                )

    @property
    def sessions(self) -> tuple[SessionContext, ...]:
        return tuple(
            self._sessions_by_id[session_id]
            for session_id in sorted(self._sessions_by_id)
        )

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._sessions_by_id))

    def session_for(self, session_id: int) -> SessionContext:
        try:
            return self._sessions_by_id[session_id]
        except KeyError as exc:
            raise FirstPartySessionAdmissionError(
                "session is not admitted"
            ) from exc

    def admit(self, hello: FirstPartyHandshakeHello) -> FirstPartyHandshakeResult:
        hello_hash = hello.hello_hash()
        if hello_hash in self._accepted_hello_hashes:
            raise FirstPartySessionAdmissionError("handshake HELLO replay refused")
        server_identity = self._server_identity_for_hello(hello)
        result = accept_firstparty_handshake(
            hello=hello,
            server_identity=server_identity,
            identity_authority=self.identity_authority,
            policy=self.policy,
            shared_secret_resolver=self.shared_secret_resolver,
            server_nonce=self.server_nonce_provider(hello),
            accepted_at=self.accepted_at_provider(hello),
            revocations=self.revocations,
            max_hello_age_seconds=self.max_hello_age_seconds,
            production_gate=self.production_gate,
        )
        client_identity_hash = result.session.client_decision.identity_hash.hex()
        if (
            self.enforce_client_identity_allowlist
            and client_identity_hash not in self.client_identity_hash_allowlist
        ):
            raise FirstPartySessionAdmissionError(
                "client identity is not in server allowlist"
            )
        if result.session.session_id in self._sessions_by_id:
            raise FirstPartySessionAdmissionError("session id collision refused")
        self._sessions_by_id[result.session.session_id] = result.session
        self._accepted_hello_hashes.add(hello_hash)
        return result

    def _server_identity_for_hello(
        self,
        hello: FirstPartyHandshakeHello,
    ) -> SignedIdentityToken:
        for identity in (self.server_identity, *self.alternate_server_identities):
            if identity_binding_hash(identity.claims).hex() == hello.server_identity_hash:
                return identity
        return self.server_identity

    def forget(self, session: SessionContext | int) -> None:
        session_id = session if isinstance(session, int) else session.session_id
        if session_id not in self._sessions_by_id:
            raise FirstPartySessionAdmissionError("session is not admitted")
        del self._sessions_by_id[session_id]
