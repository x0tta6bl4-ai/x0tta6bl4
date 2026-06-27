"""HTTP-like camouflage transport for first-party protected frames."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import hashlib
import hmac
import json
from typing import Callable, Sequence

from .admission import (
    FirstPartySessionAdmissionError,
    FirstPartySessionAdmissionRegistry,
)
from .handshake import (
    FirstPartyHandshakeAccept,
    FirstPartyHandshakeError,
    FirstPartyHandshakeHello,
    PqcMaterialGate,
    complete_firstparty_handshake,
)
from .identity import IdentityVerifier, RevocationList
from .pqc import PqcSessionSecretMaterial
from .protocol import Frame, FrameType
from .protocol import FrameDecodeError, WireCodec
from .runtime import (
    DataplaneHandler,
    DataplaneResponse,
    FirstPartyEndpoint,
    RuntimeDrop,
    RuntimeStats,
    SessionDataplaneHandler,
    _response_payloads,
)
from .rekey import FirstPartyRekeyError, FirstPartyRekeyServerProcessor
from .session import SessionContext
from .stream import (
    SessionPingHandler,
    StreamRecordError,
    encode_stream_record,
    read_stream_record,
)
from .zero_trust import ZeroTrustPolicy


MAX_CAMOUFLAGE_PREFACE_BYTES = 4096
CAMOUFLAGE_RESPONSE = b"HTTP/1.1 101 Switching Protocols\r\n"


class CamouflageError(ValueError):
    """Raised when the camouflage preface is invalid or disallowed."""


@dataclass(frozen=True)
class CamouflageProfile:
    """Public-looking HTTP/1.1 preface shape for one first-party transport path."""

    profile_id: str = "default-https-like"
    host: str = "edge.invalid"
    path: str = "/assets/session"
    method: str = "POST"
    user_agent: str = "Mozilla/5.0"

    def __post_init__(self) -> None:
        for name, value in (
            ("profile_id", self.profile_id),
            ("host", self.host),
            ("path", self.path),
            ("method", self.method),
            ("user_agent", self.user_agent),
        ):
            if not value.strip():
                raise CamouflageError(f"camouflage {name} is required")
            if "\r" in value or "\n" in value:
                raise CamouflageError(f"camouflage {name} cannot contain newlines")
        if not self.path.startswith("/"):
            raise CamouflageError("camouflage path must start with /")
        if " " in self.method:
            raise CamouflageError("camouflage method cannot contain spaces")

    def binding_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-camouflage-profile-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        return {
            "host": self.host,
            "method": self.method,
            "path": self.path,
            "profile_id": self.profile_id,
            "user_agent": self.user_agent,
        }


@dataclass(frozen=True)
class CamouflagePolicy:
    """Fail-closed allowlist for camouflage profiles."""

    allowed_profile_ids: frozenset[str] = frozenset({"default-https-like"})
    max_preface_bytes: int = MAX_CAMOUFLAGE_PREFACE_BYTES

    def __post_init__(self) -> None:
        if not self.allowed_profile_ids:
            raise CamouflageError("camouflage policy requires allowed profiles")
        if self.max_preface_bytes < 256:
            raise CamouflageError("camouflage preface limit is too small")

    def assert_allowed(self, profile: CamouflageProfile) -> None:
        if profile.profile_id not in self.allowed_profile_ids:
            raise CamouflageError("camouflage profile is not allowed by policy")


@dataclass(eq=False)
class _CamouflageServerClient:
    endpoint: FirstPartyEndpoint
    writer: asyncio.StreamWriter
    peer: tuple[str, int]


@dataclass
class FirstPartyCamouflageClient:
    """Camouflaged TCP client for one admitted first-party VPN session."""

    endpoint: FirstPartyEndpoint
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    profile: CamouflageProfile

    def send_data(self, payload: bytes) -> None:
        self._write_frame(FrameType.DATA, payload)

    def send_data_fragments(self, payloads: Sequence[bytes]) -> None:
        for payload in payloads:
            self._write_frame(FrameType.DATA, payload)

    def send_ping(self, payload: bytes = b"") -> None:
        self._write_frame(FrameType.PING, payload)

    def send_close(self, payload: bytes = b"") -> None:
        self._write_frame(FrameType.CLOSE, payload)

    async def drain(self) -> None:
        await self.writer.drain()

    async def recv(self, timeout: float = 1.0) -> Frame:
        while True:
            record = await read_stream_record(self.reader, timeout=timeout)
            try:
                return self.endpoint.open_frame(record)
            except RuntimeDrop:
                continue

    def close(self) -> None:
        self.writer.close()

    async def wait_closed(self) -> None:
        await self.writer.wait_closed()

    def _write_frame(self, frame_type: FrameType, payload: bytes) -> None:
        self.writer.write(
            encode_stream_record(self.endpoint.next_frame(frame_type, payload))
        )


@dataclass(frozen=True)
class FirstPartyCamouflageAdmissionClientResult:
    """Client-side result of camouflage HELLO/ACCEPT admission."""

    client: FirstPartyCamouflageClient
    accept: FirstPartyHandshakeAccept
    session: SessionContext


@dataclass
class FirstPartyCamouflageServer:
    """HTTP-like TCP server that carries protected first-party frames after preface."""

    session: SessionContext
    profile: CamouflageProfile = field(default_factory=CamouflageProfile)
    policy: CamouflagePolicy = field(default_factory=CamouflagePolicy)
    on_data: DataplaneHandler | None = None
    rekey_processor: FirstPartyRekeyServerProcessor | None = None
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _clients: set[_CamouflageServerClient] = field(default_factory=set, init=False)
    _last_client: _CamouflageServerClient | None = field(default=None, init=False)

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        endpoint = FirstPartyEndpoint(session=self.session, role="server")
        peer = _peer_addr(writer)
        client = _CamouflageServerClient(endpoint=endpoint, writer=writer, peer=peer)
        handler = self.on_data or (lambda payload, _addr: payload)
        try:
            await accept_camouflage_preface(
                reader=reader,
                writer=writer,
                session=self.session,
                profile=self.profile,
                policy=self.policy,
            )
            self._clients.add(client)
            self._last_client = client
            while True:
                try:
                    record = await read_stream_record(reader)
                    frame = endpoint.open_frame(record)
                except (asyncio.IncompleteReadError, StreamRecordError, RuntimeDrop):
                    break
                if frame.frame_type == FrameType.PING:
                    self._write_frame(writer, endpoint, FrameType.PONG, frame.payload)
                elif frame.frame_type == FrameType.DATA:
                    if self.rekey_processor is not None:
                        try:
                            rekey_action = self.rekey_processor.try_accept(
                                frame.payload,
                                previous_session=endpoint.session,
                            )
                        except FirstPartyRekeyError:
                            break
                        if rekey_action is not None:
                            self._write_frame(
                                writer,
                                endpoint,
                                FrameType.DATA,
                                rekey_action.response_payload,
                            )
                            await writer.drain()
                            endpoint.rotate_session(rekey_action.next_session)
                            self.session = rekey_action.next_session
                            continue
                    response: DataplaneResponse = handler(frame.payload, peer)
                    for payload in _response_payloads(response):
                        self._write_frame(writer, endpoint, FrameType.DATA, payload)
                elif frame.frame_type == FrameType.CLOSE:
                    break
                await writer.drain()
        except CamouflageError:
            pass
        finally:
            self._clients.discard(client)
            if self._last_client is client:
                self._last_client = next(iter(self._clients), None)
            self._merge_stats(endpoint.stats)
            writer.close()
            await writer.wait_closed()

    def client_connected(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.create_task(self.handle_client(reader, writer))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_client_tasks(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def send_data(
        self,
        payload: bytes,
        client: _CamouflageServerClient | None = None,
    ) -> None:
        target = client or self._last_client
        if target is None:
            raise RuntimeError("server has no active camouflage client")
        self._write_frame(target.writer, target.endpoint, FrameType.DATA, payload)
        await target.writer.drain()

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        client: _CamouflageServerClient | None = None,
    ) -> None:
        target = client or self._last_client
        if target is None:
            raise RuntimeError("server has no active camouflage client")
        for payload in payloads:
            self._write_frame(target.writer, target.endpoint, FrameType.DATA, payload)
        await target.writer.drain()

    @staticmethod
    def _write_frame(
        writer: asyncio.StreamWriter,
        endpoint: FirstPartyEndpoint,
        frame_type: FrameType,
        payload: bytes,
    ) -> None:
        writer.write(encode_stream_record(endpoint.next_frame(frame_type, payload)))

    def _merge_stats(self, stats: RuntimeStats) -> None:
        self.stats.rx_frames += stats.rx_frames
        self.stats.tx_frames += stats.tx_frames
        self.stats.rx_data_frames += stats.rx_data_frames
        self.stats.tx_data_frames += stats.tx_data_frames
        self.stats.rx_bytes += stats.rx_bytes
        self.stats.tx_bytes += stats.tx_bytes
        self.stats.auth_drops += stats.auth_drops
        self.stats.decode_drops += stats.decode_drops
        self.stats.replay_drops += stats.replay_drops
        self.stats.session_drops += stats.session_drops


@dataclass
class FirstPartyCamouflageMultiSessionServer:
    """HTTP-like TCP server that routes camouflage clients across sessions."""

    sessions: tuple[SessionContext, ...]
    profile: CamouflageProfile = field(default_factory=CamouflageProfile)
    policy: CamouflagePolicy = field(default_factory=CamouflagePolicy)
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    _session_tokens: dict[str, SessionContext] = field(default_factory=dict, init=False)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _clients: set[_CamouflageServerClient] = field(default_factory=set, init=False)
    _last_client: _CamouflageServerClient | None = field(default=None, init=False)
    _last_clients_by_session: dict[int, _CamouflageServerClient] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self) -> None:
        self.policy.assert_allowed(self.profile)
        if not self.sessions:
            raise CamouflageError("multi-session camouflage server requires sessions")
        session_ids = [session.session_id for session in self.sessions]
        if len(set(session_ids)) != len(session_ids):
            raise CamouflageError(
                "multi-session camouflage server session ids must be unique"
            )
        tokens = {
            camouflage_session_token(session=session, profile=self.profile): session
            for session in self.sessions
        }
        if len(tokens) != len(self.sessions):
            raise CamouflageError(
                "multi-session camouflage tokens must be unique"
            )
        self._session_tokens = tokens

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        endpoint: FirstPartyEndpoint | None = None
        client: _CamouflageServerClient | None = None
        peer = _peer_addr(writer)
        handler = self.on_data or (lambda payload, _addr: payload)
        try:
            session = await self._accept_multi_session_preface(reader, writer)
            endpoint = FirstPartyEndpoint(session=session, role="server")
            client = _CamouflageServerClient(endpoint=endpoint, writer=writer, peer=peer)
            self._clients.add(client)
            self._last_client = client
            self._last_clients_by_session[session.session_id] = client
            while True:
                try:
                    record = await read_stream_record(reader)
                    frame = endpoint.open_frame(record)
                except (asyncio.IncompleteReadError, StreamRecordError, RuntimeDrop):
                    break
                if frame.frame_type == FrameType.PING:
                    FirstPartyCamouflageServer._write_frame(
                        writer,
                        endpoint,
                        FrameType.PONG,
                        frame.payload,
                    )
                elif frame.frame_type == FrameType.DATA:
                    if self.on_session_data is None:
                        response: DataplaneResponse = handler(frame.payload, peer)
                    else:
                        response = self.on_session_data(
                            frame.payload,
                            peer,
                            endpoint.session,
                        )
                    for payload in _response_payloads(response):
                        FirstPartyCamouflageServer._write_frame(
                            writer,
                            endpoint,
                            FrameType.DATA,
                            payload,
                        )
                elif frame.frame_type == FrameType.CLOSE:
                    break
                await writer.drain()
        except CamouflageError:
            pass
        finally:
            if client is not None:
                self._clients.discard(client)
                if self._last_client is client:
                    self._last_client = next(iter(self._clients), None)
                session_id = client.endpoint.session.session_id
                if self._last_clients_by_session.get(session_id) is client:
                    replacement = next(
                        (
                            candidate
                            for candidate in self._clients
                            if candidate.endpoint.session.session_id == session_id
                        ),
                        None,
                    )
                    if replacement is None:
                        self._last_clients_by_session.pop(session_id, None)
                    else:
                        self._last_clients_by_session[session_id] = replacement
            if endpoint is not None:
                self._merge_stats(endpoint.stats)
            writer.close()
            await writer.wait_closed()

    def client_connected(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.create_task(self.handle_client(reader, writer))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_client_tasks(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def send_data(
        self,
        payload: bytes,
        client: _CamouflageServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active camouflage client")
        FirstPartyCamouflageServer._write_frame(
            target.writer,
            target.endpoint,
            FrameType.DATA,
            payload,
        )
        await target.writer.drain()

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        client: _CamouflageServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active camouflage client")
        for payload in payloads:
            FirstPartyCamouflageServer._write_frame(
                target.writer,
                target.endpoint,
                FrameType.DATA,
                payload,
            )
        await target.writer.drain()

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(session.session_id for session in self.sessions))

    def _target_client(
        self,
        *,
        client: _CamouflageServerClient | None,
        session: SessionContext | int | None,
    ) -> _CamouflageServerClient | None:
        if client is not None:
            return client
        if session is None:
            return self._last_client
        session_id = session if isinstance(session, int) else session.session_id
        return self._last_clients_by_session.get(session_id)

    async def _accept_multi_session_preface(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> SessionContext:
        request = await _read_preface(
            reader,
            limit=self.policy.max_preface_bytes,
            timeout=None,
        )
        headers = _validate_request_shape(request, profile=self.profile)
        token = headers.get("x-request-id", "")
        session = self._session_tokens.get(token)
        if session is None:
            raise CamouflageError("camouflage session token mismatch")
        writer.write(_encode_camouflage_response(session=session, profile=self.profile))
        await writer.drain()
        return session

    def _merge_stats(self, stats: RuntimeStats) -> None:
        self.stats.rx_frames += stats.rx_frames
        self.stats.tx_frames += stats.tx_frames
        self.stats.rx_data_frames += stats.rx_data_frames
        self.stats.tx_data_frames += stats.tx_data_frames
        self.stats.rx_bytes += stats.rx_bytes
        self.stats.tx_bytes += stats.tx_bytes
        self.stats.auth_drops += stats.auth_drops
        self.stats.decode_drops += stats.decode_drops
        self.stats.replay_drops += stats.replay_drops
        self.stats.session_drops += stats.session_drops


@dataclass
class FirstPartyCamouflageAdmissionServer:
    """HTTP-like TCP server that admits sessions through first-party HELLO/ACCEPT."""

    registry: FirstPartySessionAdmissionRegistry
    profile: CamouflageProfile = field(default_factory=CamouflageProfile)
    policy: CamouflagePolicy = field(default_factory=CamouflagePolicy)
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    on_session_ping: SessionPingHandler | None = None
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _clients: set[_CamouflageServerClient] = field(default_factory=set, init=False)
    _last_client: _CamouflageServerClient | None = field(default=None, init=False)
    _last_clients_by_session: dict[int, _CamouflageServerClient] = field(
        default_factory=dict,
        init=False,
    )

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return self.registry.admitted_session_ids

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        endpoint: FirstPartyEndpoint | None = None
        client: _CamouflageServerClient | None = None
        peer = _peer_addr(writer)
        handler = self.on_data or (lambda payload, _addr: payload)
        try:
            result = await self._admit_client(reader, writer)
            endpoint = FirstPartyEndpoint(session=result.session, role="server")
            client = _CamouflageServerClient(endpoint=endpoint, writer=writer, peer=peer)
            self._clients.add(client)
            self._last_client = client
            self._last_clients_by_session[endpoint.session.session_id] = client
            while True:
                try:
                    record = await read_stream_record(reader)
                    frame = endpoint.open_frame(record)
                except (asyncio.IncompleteReadError, StreamRecordError, RuntimeDrop):
                    break
                if not await self._handle_frame(writer, endpoint, frame, handler, peer):
                    break
        except (
            asyncio.IncompleteReadError,
            CamouflageError,
            FirstPartyHandshakeError,
            FirstPartySessionAdmissionError,
            FrameDecodeError,
            StreamRecordError,
        ):
            self.stats.session_drops += 1
        finally:
            if client is not None:
                self._clients.discard(client)
                if self._last_client is client:
                    self._last_client = next(iter(self._clients), None)
                session_id = client.endpoint.session.session_id
                if self._last_clients_by_session.get(session_id) is client:
                    replacement = next(
                        (
                            candidate
                            for candidate in self._clients
                            if candidate.endpoint.session.session_id == session_id
                        ),
                        None,
                    )
                    if replacement is None:
                        self._last_clients_by_session.pop(session_id, None)
                    else:
                        self._last_clients_by_session[session_id] = replacement
            if endpoint is not None:
                self._merge_stats(endpoint.stats)
            writer.close()
            await writer.wait_closed()

    def client_connected(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        task = asyncio.create_task(self.handle_client(reader, writer))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_client_tasks(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def send_data(
        self,
        payload: bytes,
        client: _CamouflageServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active admitted camouflage client")
        FirstPartyCamouflageServer._write_frame(
            target.writer,
            target.endpoint,
            FrameType.DATA,
            payload,
        )
        await target.writer.drain()

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        client: _CamouflageServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active admitted camouflage client")
        for payload in payloads:
            FirstPartyCamouflageServer._write_frame(
                target.writer,
                target.endpoint,
                FrameType.DATA,
                payload,
            )
        await target.writer.drain()

    async def _admit_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        self.policy.assert_allowed(self.profile)
        request = await _read_preface(
            reader,
            limit=self.policy.max_preface_bytes,
            timeout=None,
        )
        headers = _validate_request_shape(request, profile=self.profile)
        hello_record = await read_stream_record(reader)
        hello_frame = WireCodec().decode(hello_record, protected=False)
        hello = FirstPartyHandshakeHello.from_frame(hello_frame)
        expected_token = camouflage_admission_token(hello=hello, profile=self.profile)
        if not hmac.compare_digest(headers.get("x-request-id", ""), expected_token):
            raise CamouflageError("camouflage admission token mismatch")
        result = self.registry.admit(hello)
        writer.write(
            _encode_camouflage_response(session=result.session, profile=self.profile)
        )
        writer.write(
            encode_stream_record(
                WireCodec().encode(result.accept.to_frame(), protect=False)
            )
        )
        await writer.drain()
        return result

    async def _handle_frame(
        self,
        writer: asyncio.StreamWriter,
        endpoint: FirstPartyEndpoint,
        frame: Frame,
        handler: DataplaneHandler,
        peer: tuple[str, int],
    ) -> bool:
        if frame.frame_type == FrameType.PING:
            response_payload = frame.payload
            if self.on_session_ping is not None:
                custom_payload = self.on_session_ping(
                    frame.payload,
                    peer,
                    endpoint.session,
                )
                if custom_payload is None:
                    return True
                response_payload = custom_payload
            FirstPartyCamouflageServer._write_frame(
                writer,
                endpoint,
                FrameType.PONG,
                response_payload,
            )
        elif frame.frame_type == FrameType.DATA:
            if self.on_session_data is None:
                response: DataplaneResponse = handler(frame.payload, peer)
            else:
                response = self.on_session_data(
                    frame.payload,
                    peer,
                    endpoint.session,
                )
            for payload in _response_payloads(response):
                FirstPartyCamouflageServer._write_frame(
                    writer,
                    endpoint,
                    FrameType.DATA,
                    payload,
                )
        elif frame.frame_type == FrameType.CLOSE:
            return False
        await writer.drain()
        return True

    def _target_client(
        self,
        *,
        client: _CamouflageServerClient | None,
        session: SessionContext | int | None,
    ) -> _CamouflageServerClient | None:
        if client is not None:
            return client
        if session is None:
            return self._last_client
        session_id = session if isinstance(session, int) else session.session_id
        return self._last_clients_by_session.get(session_id)

    def _merge_stats(self, stats: RuntimeStats) -> None:
        self.stats.rx_frames += stats.rx_frames
        self.stats.tx_frames += stats.tx_frames
        self.stats.rx_data_frames += stats.rx_data_frames
        self.stats.tx_data_frames += stats.tx_data_frames
        self.stats.rx_bytes += stats.rx_bytes
        self.stats.tx_bytes += stats.tx_bytes
        self.stats.auth_drops += stats.auth_drops
        self.stats.decode_drops += stats.decode_drops
        self.stats.replay_drops += stats.replay_drops
        self.stats.session_drops += stats.session_drops


def camouflage_session_token(
    *,
    session: SessionContext,
    profile: CamouflageProfile,
) -> str:
    """Return a per-session cover token for the HTTP-like preface."""
    return hmac.new(
        session.keys.control,
        b"x0vpn-camouflage-session-v1"
        + session.session_id.to_bytes(8, "big")
        + bytes.fromhex(profile.binding_hash()),
        hashlib.sha256,
    ).hexdigest()


def camouflage_admission_token(
    *,
    hello: FirstPartyHandshakeHello,
    profile: CamouflageProfile,
) -> str:
    """Return a profile-bound cover token for a first-party HELLO admission."""
    return hashlib.sha256(
        b"x0vpn-camouflage-admission-v1"
        + bytes.fromhex(hello.hello_hash())
        + bytes.fromhex(profile.binding_hash())
    ).hexdigest()


def encode_camouflage_request(
    *,
    session: SessionContext,
    profile: CamouflageProfile,
    policy: CamouflagePolicy | None = None,
) -> bytes:
    """Encode the client-side HTTP-like preface."""
    active_policy = policy or CamouflagePolicy()
    active_policy.assert_allowed(profile)
    token = camouflage_session_token(session=session, profile=profile)
    request = (
        f"{profile.method} {profile.path} HTTP/1.1\r\n"
        f"Host: {profile.host}\r\n"
        f"User-Agent: {profile.user_agent}\r\n"
        "Accept: application/octet-stream\r\n"
        "Connection: Upgrade\r\n"
        "Upgrade: websocket\r\n"
        f"X-Request-ID: {token}\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    ).encode("ascii")
    if len(request) > active_policy.max_preface_bytes:
        raise CamouflageError("camouflage request exceeds policy preface limit")
    return request


def encode_camouflage_admission_request(
    *,
    hello: FirstPartyHandshakeHello,
    profile: CamouflageProfile,
    policy: CamouflagePolicy | None = None,
) -> bytes:
    """Encode the HTTP-like preface for a HELLO/ACCEPT admission connection."""
    active_policy = policy or CamouflagePolicy()
    active_policy.assert_allowed(profile)
    token = camouflage_admission_token(hello=hello, profile=profile)
    request = (
        f"{profile.method} {profile.path} HTTP/1.1\r\n"
        f"Host: {profile.host}\r\n"
        f"User-Agent: {profile.user_agent}\r\n"
        "Accept: application/octet-stream\r\n"
        "Connection: Upgrade\r\n"
        "Upgrade: websocket\r\n"
        f"X-Request-ID: {token}\r\n"
        "Content-Length: 0\r\n"
        "\r\n"
    ).encode("ascii")
    if len(request) > active_policy.max_preface_bytes:
        raise CamouflageError("camouflage request exceeds policy preface limit")
    return request


async def accept_camouflage_preface(
    *,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    session: SessionContext,
    profile: CamouflageProfile,
    policy: CamouflagePolicy | None = None,
    timeout: float | None = None,
) -> None:
    """Read and validate the client preface, then send the upgrade response."""
    active_policy = policy or CamouflagePolicy()
    active_policy.assert_allowed(profile)
    request = await _read_preface(
        reader,
        limit=active_policy.max_preface_bytes,
        timeout=timeout,
    )
    _validate_request(request, session=session, profile=profile)
    writer.write(_encode_camouflage_response(session=session, profile=profile))
    await writer.drain()


async def open_camouflage_server(
    *,
    session: SessionContext,
    host: str = "127.0.0.1",
    port: int = 0,
    profile: CamouflageProfile | None = None,
    policy: CamouflagePolicy | None = None,
    on_data: DataplaneHandler | None = None,
    rekey_processor: FirstPartyRekeyServerProcessor | None = None,
) -> tuple[asyncio.Server, FirstPartyCamouflageServer, tuple[str, int]]:
    """Open a camouflaged first-party TCP server for one admitted session."""
    protocol = FirstPartyCamouflageServer(
        session=session,
        profile=profile or CamouflageProfile(),
        policy=policy or CamouflagePolicy(),
        on_data=on_data,
        rekey_processor=rekey_processor,
    )
    server = await asyncio.start_server(protocol.client_connected, host, port)
    sock = server.sockets[0]
    sockname = sock.getsockname()
    return server, protocol, (str(sockname[0]), int(sockname[1]))


async def open_camouflage_multi_session_server(
    *,
    sessions: tuple[SessionContext, ...],
    host: str = "127.0.0.1",
    port: int = 0,
    profile: CamouflageProfile | None = None,
    policy: CamouflagePolicy | None = None,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
) -> tuple[asyncio.Server, FirstPartyCamouflageMultiSessionServer, tuple[str, int]]:
    """Open a camouflaged first-party TCP server for multiple admitted sessions."""
    protocol = FirstPartyCamouflageMultiSessionServer(
        sessions=sessions,
        profile=profile or CamouflageProfile(),
        policy=policy or CamouflagePolicy(),
        on_data=on_data,
        on_session_data=on_session_data,
    )
    server = await asyncio.start_server(protocol.client_connected, host, port)
    sock = server.sockets[0]
    sockname = sock.getsockname()
    return server, protocol, (str(sockname[0]), int(sockname[1]))


async def open_camouflage_admission_server(
    *,
    registry: FirstPartySessionAdmissionRegistry,
    host: str = "127.0.0.1",
    port: int = 0,
    profile: CamouflageProfile | None = None,
    policy: CamouflagePolicy | None = None,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
    on_session_ping: SessionPingHandler | None = None,
) -> tuple[asyncio.Server, FirstPartyCamouflageAdmissionServer, tuple[str, int]]:
    """Open a camouflage server that admits sessions through HELLO/ACCEPT."""
    protocol = FirstPartyCamouflageAdmissionServer(
        registry=registry,
        profile=profile or CamouflageProfile(),
        policy=policy or CamouflagePolicy(),
        on_data=on_data,
        on_session_data=on_session_data,
        on_session_ping=on_session_ping,
    )
    server = await asyncio.start_server(protocol.client_connected, host, port)
    sock = server.sockets[0]
    sockname = sock.getsockname()
    return server, protocol, (str(sockname[0]), int(sockname[1]))


async def open_camouflage_client(
    *,
    session: SessionContext,
    remote_addr: tuple[str, int],
    profile: CamouflageProfile | None = None,
    policy: CamouflagePolicy | None = None,
    timeout: float | None = None,
) -> FirstPartyCamouflageClient:
    """Open a camouflaged first-party TCP client for one admitted session."""
    active_profile = profile or CamouflageProfile()
    active_policy = policy or CamouflagePolicy()
    active_policy.assert_allowed(active_profile)
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(*remote_addr),
        timeout=timeout,
    )
    try:
        writer.write(
            encode_camouflage_request(
                session=session,
                profile=active_profile,
                policy=active_policy,
            )
        )
        await writer.drain()
        response = await _read_preface(
            reader,
            limit=active_policy.max_preface_bytes,
            timeout=timeout,
        )
        _validate_response(response, session=session, profile=active_profile)
    except Exception:
        writer.close()
        await writer.wait_closed()
        raise
    endpoint = FirstPartyEndpoint(session=session, role="client")
    return FirstPartyCamouflageClient(
        endpoint=endpoint,
        reader=reader,
        writer=writer,
        profile=active_profile,
    )


async def open_camouflage_admission_client(
    *,
    hello: FirstPartyHandshakeHello,
    pqc_material: PqcSessionSecretMaterial,
    remote_addr: tuple[str, int],
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    revocations: RevocationList | None = None,
    completed_at_provider: Callable[[FirstPartyHandshakeAccept], int] | None = None,
    production_gate: PqcMaterialGate | None = None,
    timeout: float = 1.0,
) -> FirstPartyCamouflageAdmissionClientResult:
    """Open camouflage TCP, perform HELLO/ACCEPT admission, and return a client."""
    active_profile = profile or CamouflageProfile()
    active_policy = camouflage_policy or CamouflagePolicy()
    active_policy.assert_allowed(active_profile)
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(*remote_addr),
        timeout=timeout,
    )
    try:
        writer.write(
            encode_camouflage_admission_request(
                hello=hello,
                profile=active_profile,
                policy=active_policy,
            )
        )
        writer.write(
            encode_stream_record(
                WireCodec().encode(hello.to_frame(), protect=False)
            )
        )
        await writer.drain()
        response = await _read_preface(
            reader,
            limit=active_policy.max_preface_bytes,
            timeout=timeout,
        )
        accept_record = await read_stream_record(reader, timeout=timeout)
        accept_frame = WireCodec().decode(accept_record, protected=False)
        accept = FirstPartyHandshakeAccept.from_frame(accept_frame)
        session = complete_firstparty_handshake(
            hello=hello,
            accept=accept,
            pqc_material=pqc_material,
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
        _validate_response(response, session=session, profile=active_profile)
    except Exception:
        writer.close()
        await writer.wait_closed()
        raise
    client = FirstPartyCamouflageClient(
        endpoint=FirstPartyEndpoint(session=session, role="client"),
        reader=reader,
        writer=writer,
        profile=active_profile,
    )
    return FirstPartyCamouflageAdmissionClientResult(
        client=client,
        accept=accept,
        session=session,
    )


async def _read_preface(
    reader: asyncio.StreamReader,
    *,
    limit: int,
    timeout: float | None,
) -> bytes:
    async def read() -> bytes:
        data = await reader.readuntil(b"\r\n\r\n")
        if len(data) > limit:
            raise CamouflageError("camouflage preface exceeds policy limit")
        return data

    try:
        if timeout is None:
            return await read()
        return await asyncio.wait_for(read(), timeout=timeout)
    except asyncio.LimitOverrunError as exc:
        raise CamouflageError("camouflage preface exceeds stream limit") from exc
    except asyncio.IncompleteReadError as exc:
        raise CamouflageError("camouflage preface was not completed") from exc


def _validate_request(
    request: bytes,
    *,
    session: SessionContext,
    profile: CamouflageProfile,
) -> None:
    headers = _validate_request_shape(request, profile=profile)
    expected_token = camouflage_session_token(session=session, profile=profile)
    if not hmac.compare_digest(headers.get("x-request-id", ""), expected_token):
        raise CamouflageError("camouflage session token mismatch")


def _validate_request_shape(
    request: bytes,
    *,
    profile: CamouflageProfile,
) -> dict[str, str]:
    line, headers = _parse_http_like_preface(request)
    expected_line = f"{profile.method} {profile.path} HTTP/1.1"
    if line != expected_line:
        raise CamouflageError("camouflage request line mismatch")
    if headers.get("host") != profile.host:
        raise CamouflageError("camouflage host mismatch")
    if headers.get("content-length") != "0":
        raise CamouflageError("camouflage content length mismatch")
    if headers.get("connection", "").lower() != "upgrade":
        raise CamouflageError("camouflage connection header mismatch")
    if headers.get("upgrade", "").lower() != "websocket":
        raise CamouflageError("camouflage upgrade header mismatch")
    return headers


def _validate_response(
    response: bytes,
    *,
    session: SessionContext,
    profile: CamouflageProfile,
) -> None:
    line, headers = _parse_http_like_preface(response)
    if line != "HTTP/1.1 101 Switching Protocols":
        raise CamouflageError("camouflage response line mismatch")
    if headers.get("connection", "").lower() != "upgrade":
        raise CamouflageError("camouflage response connection mismatch")
    if headers.get("upgrade", "").lower() != "websocket":
        raise CamouflageError("camouflage response upgrade mismatch")
    expected_token = camouflage_session_token(session=session, profile=profile)
    if not hmac.compare_digest(headers.get("x-request-id", ""), expected_token):
        raise CamouflageError("camouflage response token mismatch")


def _encode_camouflage_response(
    *,
    session: SessionContext,
    profile: CamouflageProfile,
) -> bytes:
    token = camouflage_session_token(session=session, profile=profile)
    return (
        CAMOUFLAGE_RESPONSE
        + b"Connection: Upgrade\r\n"
        + b"Upgrade: websocket\r\n"
        + f"X-Request-ID: {token}\r\n".encode("ascii")
        + b"\r\n"
    )


def _parse_http_like_preface(preface: bytes) -> tuple[str, dict[str, str]]:
    try:
        text = preface.decode("ascii")
    except UnicodeDecodeError as exc:
        raise CamouflageError("camouflage preface must be ascii") from exc
    if not text.endswith("\r\n\r\n"):
        raise CamouflageError("camouflage preface terminator missing")
    lines = text[:-4].split("\r\n")
    if not lines or not lines[0].strip():
        raise CamouflageError("camouflage preface line missing")
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            raise CamouflageError("camouflage header is invalid")
        key, value = line.split(":", 1)
        key = key.strip().lower()
        if not key:
            raise CamouflageError("camouflage header key missing")
        headers[key] = value.strip()
    return lines[0], headers


def _peer_addr(writer: asyncio.StreamWriter) -> tuple[str, int]:
    peer = writer.get_extra_info("peername")
    if isinstance(peer, tuple) and len(peer) >= 2:
        return (str(peer[0]), int(peer[1]))
    return ("0.0.0.0", 0)


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
