"""Async TCP stream transport for the first-party VPN dataplane."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field
from typing import Callable, Sequence

from .admission import (
    FirstPartySessionAdmissionError,
    FirstPartySessionAdmissionRegistry,
)
from .crypto import TAG_BYTES
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
    FrameDecodeError,
    FrameType,
    HEADER_BYTES,
    MAX_PAYLOAD_BYTES,
    WireCodec,
    decode_frame_header,
)
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
from .session import SessionContext, ZeroTrustAdmissionError
from .zero_trust import ZeroTrustPolicy

STREAM_MAGIC = b"X0STRM1!"
STREAM_RECORD = struct.Struct("!8sI")
STREAM_RECORD_HEADER_BYTES = STREAM_RECORD.size
MAX_STREAM_RECORD_BYTES = HEADER_BYTES + MAX_PAYLOAD_BYTES + TAG_BYTES


class StreamRecordError(ValueError):
    """Raised when a TCP stream record cannot be decoded safely."""


class StreamSessionRouteError(StreamRecordError):
    """Raised when a stream record cannot be routed to an admitted session."""


SessionPingHandler = Callable[
    [bytes, tuple[str, int], SessionContext],
    bytes | None,
]


def encode_stream_record(frame_bytes: bytes) -> bytes:
    if not frame_bytes:
        raise StreamRecordError("stream record is empty")
    if len(frame_bytes) > MAX_STREAM_RECORD_BYTES:
        raise StreamRecordError("stream record exceeds maximum frame size")
    return STREAM_RECORD.pack(STREAM_MAGIC, len(frame_bytes)) + frame_bytes


async def read_stream_record(
    reader: asyncio.StreamReader,
    *,
    timeout: float | None = None,
) -> bytes:
    async def read_exact_record() -> bytes:
        header = await reader.readexactly(STREAM_RECORD_HEADER_BYTES)
        magic, record_len = STREAM_RECORD.unpack(header)
        if magic != STREAM_MAGIC:
            raise StreamRecordError("bad stream record magic")
        if record_len == 0 or record_len > MAX_STREAM_RECORD_BYTES:
            raise StreamRecordError("invalid stream record length")
        return await reader.readexactly(record_len)

    if timeout is None:
        return await read_exact_record()
    return await asyncio.wait_for(read_exact_record(), timeout=timeout)


def _peer_addr(writer: asyncio.StreamWriter) -> tuple[str, int]:
    peer = writer.get_extra_info("peername")
    if isinstance(peer, tuple) and len(peer) >= 2:
        return (str(peer[0]), int(peer[1]))
    return ("0.0.0.0", 0)


def _run_dataplane_handler(
    endpoint: FirstPartyEndpoint,
    handler: DataplaneHandler,
    on_session_data: SessionDataplaneHandler | None,
    payload: bytes,
    peer: tuple[str, int],
) -> DataplaneResponse:
    try:
        if on_session_data is None:
            return handler(payload, peer)
        return on_session_data(payload, peer, endpoint.session)
    except Exception as exc:
        endpoint.stats.session_drops += 1
        raise RuntimeDrop("dataplane handler rejected payload") from exc


@dataclass(eq=False)
class _TcpServerClient:
    endpoint: FirstPartyEndpoint
    writer: asyncio.StreamWriter
    peer: tuple[str, int]


@dataclass
class FirstPartyTcpClient:
    """TCP client helper for one admitted first-party VPN session."""

    endpoint: FirstPartyEndpoint
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

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
        frame = self.endpoint.next_frame(frame_type, payload)
        self.writer.write(encode_stream_record(frame))


@dataclass
class FirstPartyTcpServer:
    """TCP server for one first-party VPN session."""

    session: SessionContext
    on_data: DataplaneHandler | None = None
    rekey_processor: FirstPartyRekeyServerProcessor | None = None
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _clients: set[_TcpServerClient] = field(default_factory=set, init=False)
    _last_client: _TcpServerClient | None = field(default=None, init=False)

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        endpoint = FirstPartyEndpoint(session=self.session, role="server")
        peer = _peer_addr(writer)
        client = _TcpServerClient(endpoint=endpoint, writer=writer, peer=peer)
        self._clients.add(client)
        self._last_client = client
        handler = self.on_data or (lambda payload, _addr: payload)
        try:
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
                    response = _run_dataplane_handler(
                        endpoint,
                        handler,
                        None,
                        frame.payload,
                        peer,
                    )
                    for payload in _response_payloads(response):
                        self._write_frame(writer, endpoint, FrameType.DATA, payload)
                elif frame.frame_type == FrameType.CLOSE:
                    break
                await writer.drain()
        except RuntimeDrop:
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
        client: _TcpServerClient | None = None,
    ) -> None:
        target = client or self._last_client
        if target is None:
            raise RuntimeError("server has no active TCP client")
        self._write_frame(target.writer, target.endpoint, FrameType.DATA, payload)
        await target.writer.drain()

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        client: _TcpServerClient | None = None,
    ) -> None:
        target = client or self._last_client
        if target is None:
            raise RuntimeError("server has no active TCP client")
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
class FirstPartyTcpMultiSessionServer:
    """TCP server that routes connections across admitted first-party sessions."""

    sessions: tuple[SessionContext, ...]
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    _session_map: dict[int, SessionContext] = field(default_factory=dict, init=False)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _clients: set[_TcpServerClient] = field(default_factory=set, init=False)
    _last_client: _TcpServerClient | None = field(default=None, init=False)
    _last_clients_by_session: dict[int, _TcpServerClient] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self) -> None:
        if not self.sessions:
            raise ValueError("multi-session TCP server requires sessions")
        session_ids = [session.session_id for session in self.sessions]
        if len(set(session_ids)) != len(session_ids):
            raise ValueError("multi-session TCP server session ids must be unique")
        self._session_map = {session.session_id: session for session in self.sessions}

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        endpoint: FirstPartyEndpoint | None = None
        client: _TcpServerClient | None = None
        peer = _peer_addr(writer)
        handler = self.on_data or (lambda payload, _addr: payload)
        try:
            first_record = await read_stream_record(reader)
            endpoint = self._endpoint_for_record(first_record)
            client = _TcpServerClient(endpoint=endpoint, writer=writer, peer=peer)
            self._clients.add(client)
            self._last_client = client
            self._last_clients_by_session[endpoint.session.session_id] = client
            frame = endpoint.open_frame(first_record)
            if not await self._handle_frame(writer, endpoint, frame, handler, peer):
                return
            while True:
                try:
                    record = await read_stream_record(reader)
                    frame = endpoint.open_frame(record)
                except (asyncio.IncompleteReadError, StreamRecordError, RuntimeDrop):
                    break
                if not await self._handle_frame(writer, endpoint, frame, handler, peer):
                    break
        except (asyncio.IncompleteReadError, StreamRecordError, RuntimeDrop):
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
        client: _TcpServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active TCP client")
        FirstPartyTcpServer._write_frame(
            target.writer,
            target.endpoint,
            FrameType.DATA,
            payload,
        )
        await target.writer.drain()

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self._session_map))

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        client: _TcpServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active TCP client")
        for payload in payloads:
            FirstPartyTcpServer._write_frame(
                target.writer,
                target.endpoint,
                FrameType.DATA,
                payload,
            )
        await target.writer.drain()

    def _target_client(
        self,
        *,
        client: _TcpServerClient | None,
        session: SessionContext | int | None,
    ) -> _TcpServerClient | None:
        if client is not None:
            return client
        if session is None:
            return self._last_client
        session_id = session if isinstance(session, int) else session.session_id
        return self._last_clients_by_session.get(session_id)

    def _endpoint_for_record(self, record: bytes) -> FirstPartyEndpoint:
        try:
            header = decode_frame_header(record)
        except FrameDecodeError as exc:
            self.stats.decode_drops += 1
            raise StreamSessionRouteError("stream frame header is invalid") from exc
        session = self._session_map.get(header.session_id)
        if session is None:
            self.stats.session_drops += 1
            raise StreamSessionRouteError("stream frame session is not admitted")
        return FirstPartyEndpoint(session=session, role="server")

    async def _handle_frame(
        self,
        writer: asyncio.StreamWriter,
        endpoint: FirstPartyEndpoint,
        frame: Frame,
        handler: DataplaneHandler,
        peer: tuple[str, int],
    ) -> bool:
        if frame.frame_type == FrameType.PING:
            FirstPartyTcpServer._write_frame(
                writer,
                endpoint,
                FrameType.PONG,
                frame.payload,
            )
        elif frame.frame_type == FrameType.DATA:
            response = _run_dataplane_handler(
                endpoint,
                handler,
                self.on_session_data,
                frame.payload,
                peer,
            )
            for payload in _response_payloads(response):
                FirstPartyTcpServer._write_frame(writer, endpoint, FrameType.DATA, payload)
        elif frame.frame_type == FrameType.CLOSE:
            return False
        await writer.drain()
        return True

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


@dataclass(frozen=True)
class FirstPartyTcpAdmissionClientResult:
    """Client-side result of TCP HELLO/ACCEPT admission."""

    client: FirstPartyTcpClient
    accept: FirstPartyHandshakeAccept
    session: SessionContext


@dataclass
class FirstPartyTcpAdmissionServer:
    """TCP server that admits new sessions through first-party HELLO/ACCEPT."""

    registry: FirstPartySessionAdmissionRegistry
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    on_session_ping: SessionPingHandler | None = None
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False)
    _clients: set[_TcpServerClient] = field(default_factory=set, init=False)
    _last_client: _TcpServerClient | None = field(default=None, init=False)
    _last_clients_by_session: dict[int, _TcpServerClient] = field(
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
        client: _TcpServerClient | None = None
        peer = _peer_addr(writer)
        handler = self.on_data or (lambda payload, _addr: payload)
        try:
            result = await self._admit_client(reader, writer)
            endpoint = FirstPartyEndpoint(session=result.session, role="server")
            client = _TcpServerClient(endpoint=endpoint, writer=writer, peer=peer)
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
        except RuntimeDrop:
            pass
        except (
            asyncio.IncompleteReadError,
            FrameDecodeError,
            FirstPartyHandshakeError,
            FirstPartySessionAdmissionError,
            StreamRecordError,
            ZeroTrustAdmissionError,
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
        client: _TcpServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active admitted TCP client")
        FirstPartyTcpServer._write_frame(
            target.writer,
            target.endpoint,
            FrameType.DATA,
            payload,
        )
        await target.writer.drain()

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        client: _TcpServerClient | None = None,
        *,
        session: SessionContext | int | None = None,
    ) -> None:
        target = self._target_client(client=client, session=session)
        if target is None:
            raise RuntimeError("server has no active admitted TCP client")
        for payload in payloads:
            FirstPartyTcpServer._write_frame(
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
        hello_record = await read_stream_record(reader)
        hello_frame = WireCodec().decode(hello_record, protected=False)
        hello = FirstPartyHandshakeHello.from_frame(hello_frame)
        result = self.registry.admit(hello)
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
            FirstPartyTcpServer._write_frame(
                writer,
                endpoint,
                FrameType.PONG,
                response_payload,
            )
        elif frame.frame_type == FrameType.DATA:
            response = _run_dataplane_handler(
                endpoint,
                handler,
                self.on_session_data,
                frame.payload,
                peer,
            )
            for payload in _response_payloads(response):
                FirstPartyTcpServer._write_frame(writer, endpoint, FrameType.DATA, payload)
        elif frame.frame_type == FrameType.CLOSE:
            return False
        await writer.drain()
        return True

    def _target_client(
        self,
        *,
        client: _TcpServerClient | None,
        session: SessionContext | int | None,
    ) -> _TcpServerClient | None:
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


async def open_tcp_server(
    *,
    session: SessionContext,
    host: str = "127.0.0.1",
    port: int = 0,
    on_data: DataplaneHandler | None = None,
    rekey_processor: FirstPartyRekeyServerProcessor | None = None,
) -> tuple[asyncio.Server, FirstPartyTcpServer, tuple[str, int]]:
    """Open a first-party TCP server for one admitted session."""
    protocol = FirstPartyTcpServer(
        session=session,
        on_data=on_data,
        rekey_processor=rekey_processor,
    )
    server = await asyncio.start_server(protocol.client_connected, host, port)
    sock = server.sockets[0]
    sockname = sock.getsockname()
    return server, protocol, (str(sockname[0]), int(sockname[1]))


async def open_tcp_multi_session_server(
    *,
    sessions: tuple[SessionContext, ...],
    host: str = "127.0.0.1",
    port: int = 0,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
) -> tuple[asyncio.Server, FirstPartyTcpMultiSessionServer, tuple[str, int]]:
    """Open a first-party TCP server for multiple admitted sessions."""
    protocol = FirstPartyTcpMultiSessionServer(
        sessions=sessions,
        on_data=on_data,
        on_session_data=on_session_data,
    )
    server = await asyncio.start_server(protocol.client_connected, host, port)
    sock = server.sockets[0]
    sockname = sock.getsockname()
    return server, protocol, (str(sockname[0]), int(sockname[1]))


async def open_tcp_admission_server(
    *,
    registry: FirstPartySessionAdmissionRegistry,
    host: str = "127.0.0.1",
    port: int = 0,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
    on_session_ping: SessionPingHandler | None = None,
) -> tuple[asyncio.Server, FirstPartyTcpAdmissionServer, tuple[str, int]]:
    """Open a TCP server that admits sessions through first-party HELLO/ACCEPT."""
    protocol = FirstPartyTcpAdmissionServer(
        registry=registry,
        on_data=on_data,
        on_session_data=on_session_data,
        on_session_ping=on_session_ping,
    )
    server = await asyncio.start_server(protocol.client_connected, host, port)
    sock = server.sockets[0]
    sockname = sock.getsockname()
    return server, protocol, (str(sockname[0]), int(sockname[1]))


async def open_tcp_admission_client(
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
) -> FirstPartyTcpAdmissionClientResult:
    """Open a TCP connection, perform HELLO/ACCEPT admission, and return a client."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(*remote_addr),
        timeout=timeout,
    )
    try:
        writer.write(
            encode_stream_record(
                WireCodec().encode(hello.to_frame(), protect=False)
            )
        )
        await writer.drain()
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
    except Exception:
        writer.close()
        await writer.wait_closed()
        raise
    client = FirstPartyTcpClient(
        endpoint=FirstPartyEndpoint(session=session, role="client"),
        reader=reader,
        writer=writer,
    )
    return FirstPartyTcpAdmissionClientResult(
        client=client,
        accept=accept,
        session=session,
    )


async def open_tcp_client(
    *,
    session: SessionContext,
    remote_addr: tuple[str, int],
) -> FirstPartyTcpClient:
    """Open a first-party TCP client for one admitted session."""
    reader, writer = await asyncio.open_connection(*remote_addr)
    endpoint = FirstPartyEndpoint(session=session, role="client")
    return FirstPartyTcpClient(endpoint=endpoint, reader=reader, writer=writer)
