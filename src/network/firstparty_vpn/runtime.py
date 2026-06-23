"""Async UDP runtime for the first-party VPN dataplane."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
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
from .protocol import (
    Frame,
    FrameAuthError,
    FrameDecodeError,
    FrameType,
    ReplayWindow,
    WireCodec,
    decode_frame_header,
)
from .rekey import FirstPartyRekeyError, FirstPartyRekeyServerProcessor
from .session import SessionContext
from .zero_trust import ZeroTrustPolicy


DataplaneResponse = bytes | Sequence[bytes] | None
DataplaneHandler = Callable[[bytes, tuple[str, int]], DataplaneResponse]
SessionDataplaneHandler = Callable[
    [bytes, tuple[str, int], SessionContext],
    DataplaneResponse,
]


class RuntimeDrop(ValueError):
    """Raised when a received datagram is intentionally dropped."""


class SessionRouteDrop(RuntimeDrop):
    """Raised when a frame cannot be routed to an admitted session."""


def _response_payloads(response: DataplaneResponse) -> tuple[bytes, ...]:
    if response is None:
        return ()
    if isinstance(response, bytes):
        return (response,)
    payloads = tuple(response)
    for payload in payloads:
        if not isinstance(payload, bytes):
            raise TypeError("dataplane response payloads must be bytes")
    return payloads


@dataclass
class RuntimeStats:
    rx_frames: int = 0
    tx_frames: int = 0
    rx_data_frames: int = 0
    tx_data_frames: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    auth_drops: int = 0
    decode_drops: int = 0
    replay_drops: int = 0
    session_drops: int = 0


@dataclass
class FirstPartyEndpoint:
    """Stateful endpoint for one admitted first-party VPN session."""

    session: SessionContext
    role: str
    replay_window: ReplayWindow = field(default_factory=ReplayWindow)
    tx_sequence: int = 1
    stats: RuntimeStats = field(default_factory=RuntimeStats)

    def _codec(self):
        if self.role == "client":
            return self.session.client_codec
        if self.role == "server":
            return self.session.server_codec
        raise ValueError("role must be client or server")

    def next_frame(self, frame_type: FrameType, payload: bytes = b"") -> bytes:
        frame = Frame(
            frame_type=frame_type,
            session_id=self.session.session_id,
            sequence=self.tx_sequence,
            payload=payload,
        )
        self.tx_sequence += 1
        encoded = self._codec().encode(frame)
        self.stats.tx_frames += 1
        self.stats.tx_bytes += len(encoded)
        if frame_type == FrameType.DATA:
            self.stats.tx_data_frames += 1
        return encoded

    def open_frame(self, data: bytes) -> Frame:
        try:
            frame = self._codec().decode(data)
        except FrameAuthError as exc:
            self.stats.auth_drops += 1
            raise RuntimeDrop("frame authentication failed") from exc
        except FrameDecodeError as exc:
            self.stats.decode_drops += 1
            raise RuntimeDrop("frame decode failed") from exc
        if frame.session_id != self.session.session_id:
            self.stats.session_drops += 1
            raise RuntimeDrop("session id mismatch")
        if not self.replay_window.accept(frame.sequence):
            self.stats.replay_drops += 1
            raise RuntimeDrop("replayed frame")
        self.stats.rx_frames += 1
        self.stats.rx_bytes += len(data)
        if frame.frame_type == FrameType.DATA:
            self.stats.rx_data_frames += 1
        return frame

    def rotate_session(self, session: SessionContext) -> None:
        """Switch this endpoint to a newly admitted session and reset replay state."""
        self.session = session
        self.replay_window = ReplayWindow()
        self.tx_sequence = 1


class FirstPartyUdpServer(asyncio.DatagramProtocol):
    """UDP server for one first-party VPN session."""

    def __init__(
        self,
        endpoint: FirstPartyEndpoint,
        on_data: DataplaneHandler | None = None,
        rekey_processor: FirstPartyRekeyServerProcessor | None = None,
    ) -> None:
        if endpoint.role != "server":
            raise ValueError("server requires endpoint role=server")
        self.endpoint = endpoint
        self.on_data = on_data or (lambda payload, _addr: payload)
        self.rekey_processor = rekey_processor
        self.transport: asyncio.DatagramTransport | None = None
        self.last_peer: tuple[str, int] | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self.last_peer = addr
        try:
            frame = self.endpoint.open_frame(data)
        except RuntimeDrop:
            return
        if self.transport is None:
            return
        if frame.frame_type == FrameType.PING:
            self.transport.sendto(self.endpoint.next_frame(FrameType.PONG, frame.payload), addr)
            return
        if frame.frame_type == FrameType.DATA:
            if self.rekey_processor is not None:
                try:
                    rekey_action = self.rekey_processor.try_accept(
                        frame.payload,
                        previous_session=self.endpoint.session,
                    )
                except FirstPartyRekeyError:
                    return
                if rekey_action is not None:
                    self.transport.sendto(
                        self.endpoint.next_frame(
                            FrameType.DATA,
                            rekey_action.response_payload,
                        ),
                        addr,
                    )
                    self.endpoint.rotate_session(rekey_action.next_session)
                    return
            response = self.on_data(frame.payload, addr)
            for payload in _response_payloads(response):
                self.transport.sendto(self.endpoint.next_frame(FrameType.DATA, payload), addr)

    def send_data(self, payload: bytes, addr: tuple[str, int] | None = None) -> None:
        peer = addr or self.last_peer
        if self.transport is None:
            raise RuntimeError("server transport is not connected")
        if peer is None:
            raise RuntimeError("server has no known peer")
        self.transport.sendto(self.endpoint.next_frame(FrameType.DATA, payload), peer)

    def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        addr: tuple[str, int] | None = None,
    ) -> None:
        for payload in payloads:
            self.send_data(payload, addr=addr)


@dataclass
class FirstPartyUdpMultiSessionServer(asyncio.DatagramProtocol):
    """UDP server that routes protected frames across admitted sessions."""

    sessions: tuple[SessionContext, ...]
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    endpoints: dict[int, FirstPartyEndpoint] = field(default_factory=dict, init=False)
    transport: asyncio.DatagramTransport | None = field(default=None, init=False)
    last_peers: dict[int, tuple[str, int]] = field(default_factory=dict, init=False)
    route_stats: RuntimeStats = field(default_factory=RuntimeStats, init=False)

    def __post_init__(self) -> None:
        if not self.sessions:
            raise ValueError("multi-session UDP server requires sessions")
        session_ids = [session.session_id for session in self.sessions]
        if len(set(session_ids)) != len(session_ids):
            raise ValueError("multi-session UDP server session ids must be unique")
        self.endpoints = {
            session.session_id: FirstPartyEndpoint(session=session, role="server")
            for session in self.sessions
        }

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            header = decode_frame_header(data)
        except FrameDecodeError:
            self.route_stats.decode_drops += 1
            return
        endpoint = self.endpoints.get(header.session_id)
        if endpoint is None:
            self.route_stats.session_drops += 1
            return
        self.last_peers[header.session_id] = addr
        try:
            frame = endpoint.open_frame(data)
        except RuntimeDrop:
            return
        if self.transport is None:
            return
        if frame.frame_type == FrameType.PING:
            self.transport.sendto(endpoint.next_frame(FrameType.PONG, frame.payload), addr)
            return
        if frame.frame_type == FrameType.DATA:
            handler = self.on_data or (lambda payload, _addr: payload)
            if self.on_session_data is None:
                response = handler(frame.payload, addr)
            else:
                response = self.on_session_data(frame.payload, addr, endpoint.session)
            for payload in _response_payloads(response):
                self.transport.sendto(endpoint.next_frame(FrameType.DATA, payload), addr)

    def endpoint_for(self, session: SessionContext | int) -> FirstPartyEndpoint:
        session_id = session if isinstance(session, int) else session.session_id
        endpoint = self.endpoints.get(session_id)
        if endpoint is None:
            raise SessionRouteDrop("session is not admitted on this UDP server")
        return endpoint

    def send_data(
        self,
        payload: bytes,
        *,
        session: SessionContext | int,
        addr: tuple[str, int] | None = None,
    ) -> None:
        endpoint = self.endpoint_for(session)
        session_id = session if isinstance(session, int) else session.session_id
        peer = addr or self.last_peers.get(session_id)
        if self.transport is None:
            raise RuntimeError("server transport is not connected")
        if peer is None:
            raise RuntimeError("server has no known peer for session")
        self.transport.sendto(endpoint.next_frame(FrameType.DATA, payload), peer)

    def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        *,
        session: SessionContext | int,
        addr: tuple[str, int] | None = None,
    ) -> None:
        for payload in payloads:
            self.send_data(payload, session=session, addr=addr)

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.endpoints))


@dataclass
class FirstPartyUdpAdmissionServer(asyncio.DatagramProtocol):
    """UDP server that admits new sessions through first-party HELLO/ACCEPT."""

    registry: FirstPartySessionAdmissionRegistry
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    endpoints: dict[int, FirstPartyEndpoint] = field(default_factory=dict, init=False)
    transport: asyncio.DatagramTransport | None = field(default=None, init=False)
    last_peers: dict[int, tuple[str, int]] = field(default_factory=dict, init=False)
    route_stats: RuntimeStats = field(default_factory=RuntimeStats, init=False)

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.endpoints))

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            header = decode_frame_header(data)
        except FrameDecodeError:
            self.route_stats.decode_drops += 1
            return
        if header.frame_type == FrameType.HELLO and header.session_id == 0:
            self._accept_hello(data, addr)
            return
        endpoint = self.endpoints.get(header.session_id)
        if endpoint is None:
            self.route_stats.session_drops += 1
            return
        self.last_peers[header.session_id] = addr
        try:
            frame = endpoint.open_frame(data)
        except RuntimeDrop:
            return
        if self.transport is None:
            return
        if frame.frame_type == FrameType.PING:
            self.transport.sendto(endpoint.next_frame(FrameType.PONG, frame.payload), addr)
            return
        if frame.frame_type == FrameType.DATA:
            handler = self.on_data or (lambda payload, _addr: payload)
            if self.on_session_data is None:
                response = handler(frame.payload, addr)
            else:
                response = self.on_session_data(frame.payload, addr, endpoint.session)
            for payload in _response_payloads(response):
                self.transport.sendto(endpoint.next_frame(FrameType.DATA, payload), addr)

    def endpoint_for(self, session: SessionContext | int) -> FirstPartyEndpoint:
        session_id = session if isinstance(session, int) else session.session_id
        endpoint = self.endpoints.get(session_id)
        if endpoint is None:
            raise SessionRouteDrop("session is not admitted on this UDP server")
        return endpoint

    def send_data(
        self,
        payload: bytes,
        *,
        session: SessionContext | int,
        addr: tuple[str, int] | None = None,
    ) -> None:
        endpoint = self.endpoint_for(session)
        session_id = session if isinstance(session, int) else session.session_id
        peer = addr or self.last_peers.get(session_id)
        if self.transport is None:
            raise RuntimeError("server transport is not connected")
        if peer is None:
            raise RuntimeError("server has no known peer for session")
        self.transport.sendto(endpoint.next_frame(FrameType.DATA, payload), peer)

    def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        *,
        session: SessionContext | int,
        addr: tuple[str, int] | None = None,
    ) -> None:
        for payload in payloads:
            self.send_data(payload, session=session, addr=addr)

    def _accept_hello(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.transport is None:
            return
        try:
            frame = WireCodec().decode(data, protected=False)
            hello = FirstPartyHandshakeHello.from_frame(frame)
            result = self.registry.admit(hello)
        except (
            FrameDecodeError,
            FirstPartyHandshakeError,
            FirstPartySessionAdmissionError,
        ):
            self.route_stats.session_drops += 1
            return
        endpoint = FirstPartyEndpoint(session=result.session, role="server")
        self.endpoints[result.session.session_id] = endpoint
        self.last_peers[result.session.session_id] = addr
        self.transport.sendto(
            WireCodec().encode(result.accept.to_frame(), protect=False),
            addr,
        )


class FirstPartyUdpClient(asyncio.DatagramProtocol):
    """UDP client helper for loopback and future TUN integration."""

    def __init__(self, endpoint: FirstPartyEndpoint) -> None:
        if endpoint.role != "client":
            raise ValueError("client requires endpoint role=client")
        self.endpoint = endpoint
        self.transport: asyncio.DatagramTransport | None = None
        self._queue: asyncio.Queue[Frame] = asyncio.Queue()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            frame = self.endpoint.open_frame(data)
        except RuntimeDrop:
            return
        self._queue.put_nowait(frame)

    def send_data(self, payload: bytes) -> None:
        if self.transport is None:
            raise RuntimeError("client transport is not connected")
        self.transport.sendto(self.endpoint.next_frame(FrameType.DATA, payload))

    def send_data_fragments(self, payloads: Sequence[bytes]) -> None:
        if self.transport is None:
            raise RuntimeError("client transport is not connected")
        for payload in payloads:
            self.transport.sendto(self.endpoint.next_frame(FrameType.DATA, payload))

    def send_ping(self, payload: bytes = b"") -> None:
        if self.transport is None:
            raise RuntimeError("client transport is not connected")
        self.transport.sendto(self.endpoint.next_frame(FrameType.PING, payload))

    async def drain(self) -> None:
        return None

    async def recv(self, timeout: float = 1.0) -> Frame:
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)


class FirstPartyUdpAdmissionClient(asyncio.DatagramProtocol):
    """UDP client that performs first-party HELLO/ACCEPT before protected traffic."""

    def __init__(
        self,
        *,
        hello: FirstPartyHandshakeHello,
        pqc_material: PqcSessionSecretMaterial,
        identity_authority: IdentityVerifier,
        policy: ZeroTrustPolicy,
        admitted: asyncio.Future["FirstPartyUdpAdmissionClient"],
        revocations: RevocationList | None = None,
        completed_at_provider: Callable[[FirstPartyHandshakeAccept], int] | None = None,
        production_gate: PqcMaterialGate | None = None,
    ) -> None:
        self.hello = hello
        self.pqc_material = pqc_material
        self.identity_authority = identity_authority
        self.policy = policy
        self.revocations = revocations
        self.completed_at_provider = completed_at_provider
        self.production_gate = production_gate
        self.admitted = admitted
        self.transport: asyncio.DatagramTransport | None = None
        self.endpoint: FirstPartyEndpoint | None = None
        self.accept: FirstPartyHandshakeAccept | None = None
        self.session: SessionContext | None = None
        self._queue: asyncio.Queue[Frame] = asyncio.Queue()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]
        transport.sendto(WireCodec().encode(self.hello.to_frame(), protect=False))

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if self.endpoint is None:
            self._accept_server_response(data)
            return
        try:
            frame = self.endpoint.open_frame(data)
        except RuntimeDrop:
            return
        self._queue.put_nowait(frame)

    def error_received(self, exc: Exception) -> None:
        if not self.admitted.done():
            self.admitted.set_exception(exc)

    def send_data(self, payload: bytes) -> None:
        endpoint = self._require_endpoint()
        if self.transport is None:
            raise RuntimeError("client transport is not connected")
        self.transport.sendto(endpoint.next_frame(FrameType.DATA, payload))

    def send_data_fragments(self, payloads: Sequence[bytes]) -> None:
        endpoint = self._require_endpoint()
        if self.transport is None:
            raise RuntimeError("client transport is not connected")
        for payload in payloads:
            self.transport.sendto(endpoint.next_frame(FrameType.DATA, payload))

    def send_ping(self, payload: bytes = b"") -> None:
        endpoint = self._require_endpoint()
        if self.transport is None:
            raise RuntimeError("client transport is not connected")
        self.transport.sendto(endpoint.next_frame(FrameType.PING, payload))

    async def drain(self) -> None:
        return None

    async def recv(self, timeout: float = 1.0) -> Frame:
        return await asyncio.wait_for(self._queue.get(), timeout=timeout)

    def _accept_server_response(self, data: bytes) -> None:
        try:
            frame = WireCodec().decode(data, protected=False)
            accept = FirstPartyHandshakeAccept.from_frame(frame)
            session = complete_firstparty_handshake(
                hello=self.hello,
                accept=accept,
                pqc_material=self.pqc_material,
                identity_authority=self.identity_authority,
                policy=self.policy,
                revocations=self.revocations,
                completed_at=(
                    self.completed_at_provider(accept)
                    if self.completed_at_provider is not None
                    else None
                ),
                production_gate=self.production_gate,
            )
        except Exception as exc:
            if not self.admitted.done():
                self.admitted.set_exception(exc)
            return
        self.accept = accept
        self.session = session
        self.endpoint = FirstPartyEndpoint(session=session, role="client")
        if not self.admitted.done():
            self.admitted.set_result(self)

    def _require_endpoint(self) -> FirstPartyEndpoint:
        if self.endpoint is None:
            raise RuntimeError("client admission is not complete")
        return self.endpoint


async def open_udp_server(
    *,
    session: SessionContext,
    host: str = "127.0.0.1",
    port: int = 0,
    on_data: DataplaneHandler | None = None,
    rekey_processor: FirstPartyRekeyServerProcessor | None = None,
) -> tuple[asyncio.DatagramTransport, FirstPartyUdpServer, tuple[str, int]]:
    """Open a first-party UDP server for one admitted session."""
    loop = asyncio.get_running_loop()
    endpoint = FirstPartyEndpoint(session=session, role="server")
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FirstPartyUdpServer(
            endpoint,
            on_data=on_data,
            rekey_processor=rekey_processor,
        ),
        local_addr=(host, port),
    )
    sockname = transport.get_extra_info("sockname")
    return transport, protocol, (str(sockname[0]), int(sockname[1]))


async def open_udp_multi_session_server(
    *,
    sessions: tuple[SessionContext, ...],
    host: str = "127.0.0.1",
    port: int = 0,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
) -> tuple[asyncio.DatagramTransport, FirstPartyUdpMultiSessionServer, tuple[str, int]]:
    """Open a first-party UDP server for multiple admitted sessions."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FirstPartyUdpMultiSessionServer(
            sessions=sessions,
            on_data=on_data,
            on_session_data=on_session_data,
        ),
        local_addr=(host, port),
    )
    sockname = transport.get_extra_info("sockname")
    return transport, protocol, (str(sockname[0]), int(sockname[1]))


async def open_udp_admission_server(
    *,
    registry: FirstPartySessionAdmissionRegistry,
    host: str = "127.0.0.1",
    port: int = 0,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
) -> tuple[asyncio.DatagramTransport, FirstPartyUdpAdmissionServer, tuple[str, int]]:
    """Open a UDP server that admits sessions through first-party HELLO/ACCEPT."""
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FirstPartyUdpAdmissionServer(
            registry=registry,
            on_data=on_data,
            on_session_data=on_session_data,
        ),
        local_addr=(host, port),
    )
    sockname = transport.get_extra_info("sockname")
    return transport, protocol, (str(sockname[0]), int(sockname[1]))


async def open_udp_client(
    *,
    session: SessionContext,
    remote_addr: tuple[str, int],
) -> tuple[asyncio.DatagramTransport, FirstPartyUdpClient]:
    """Open a first-party UDP client for one admitted session."""
    loop = asyncio.get_running_loop()
    endpoint = FirstPartyEndpoint(session=session, role="client")
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: FirstPartyUdpClient(endpoint),
        remote_addr=remote_addr,
    )
    return transport, protocol


async def open_udp_admission_client(
    *,
    hello: FirstPartyHandshakeHello,
    pqc_material: PqcSessionSecretMaterial,
    remote_addr: tuple[str, int],
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    revocations: RevocationList | None = None,
    completed_at_provider: Callable[[FirstPartyHandshakeAccept], int] | None = None,
    production_gate: PqcMaterialGate | None = None,
    timeout: float = 1.0,
) -> tuple[asyncio.DatagramTransport, FirstPartyUdpAdmissionClient]:
    """Open UDP, perform HELLO/ACCEPT admission, and return an admitted client."""
    loop = asyncio.get_running_loop()
    admitted: asyncio.Future[FirstPartyUdpAdmissionClient] = loop.create_future()
    transport, _protocol = await loop.create_datagram_endpoint(
        lambda: FirstPartyUdpAdmissionClient(
            hello=hello,
            pqc_material=pqc_material,
            identity_authority=identity_authority,
            policy=policy,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
            production_gate=production_gate,
            admitted=admitted,
        ),
        remote_addr=remote_addr,
    )
    try:
        client = await asyncio.wait_for(admitted, timeout=timeout)
    except Exception:
        transport.close()
        raise
    return transport, client
