"""Lifecycle service for first-party VPN UDP/TCP/camouflage listeners."""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass, field
import hashlib
import json
import threading
from collections.abc import Awaitable, Callable

from .admission import FirstPartySessionAdmissionRegistry
from .camouflage import (
    CamouflagePolicy,
    CamouflageProfile,
    FirstPartyCamouflageAdmissionServer,
    FirstPartyCamouflageMultiSessionServer,
    FirstPartyCamouflageServer,
    open_camouflage_admission_server,
    open_camouflage_multi_session_server,
    open_camouflage_server,
)
from .dataplane_validation import DataplaneTransport
from .linux_policy import LinuxServerNatConfig
from .ops import assert_privacy_safe, hash_identifier
from .runtime import (
    DataplaneResponse,
    DataplaneHandler,
    FirstPartyUdpAdmissionServer,
    FirstPartyUdpMultiSessionServer,
    FirstPartyUdpServer,
    SessionDataplaneHandler,
    open_udp_admission_server,
    open_udp_multi_session_server,
    open_udp_server,
)
from .rekey import FirstPartyRekeyServerProcessor
from .session import SessionContext
from .stream import (
    FirstPartyTcpAdmissionServer,
    FirstPartyTcpMultiSessionServer,
    FirstPartyTcpServer,
    SessionPingHandler,
    open_tcp_admission_server,
    open_tcp_multi_session_server,
    open_tcp_server,
)


class FirstPartyDataplaneServiceError(RuntimeError):
    """Raised when the first-party dataplane service lifecycle is invalid."""


@dataclass(frozen=True)
class DataplaneServiceBindAttempt:
    """Privacy-safe result of one listener bind attempt."""

    transport: DataplaneTransport
    bind_hash: str
    port_index: int
    requested_ephemeral_port: bool
    opened: bool
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise FirstPartyDataplaneServiceError("dataplane bind transport is invalid")
        if not self.bind_hash.strip():
            raise FirstPartyDataplaneServiceError("dataplane bind hash is required")
        if self.port_index < 0:
            raise FirstPartyDataplaneServiceError("dataplane bind port index is invalid")
        if self.opened and self.failure_reason is not None:
            raise FirstPartyDataplaneServiceError("opened dataplane bind has failure reason")
        if not self.opened and not (self.failure_reason or "").strip():
            raise FirstPartyDataplaneServiceError("failed dataplane bind requires reason")

    @classmethod
    def from_port(
        cls,
        *,
        transport: DataplaneTransport,
        host: str,
        port: int,
        port_index: int,
        opened: bool,
        failure_reason: str | None = None,
    ) -> "DataplaneServiceBindAttempt":
        return cls(
            transport=transport,
            bind_hash=hash_identifier(
                f"{transport}|{host}|{port}|{port_index}",
                namespace="dataplane-bind",
            ),
            port_index=port_index,
            requested_ephemeral_port=port == 0,
            opened=opened,
            failure_reason=failure_reason,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "bind_hash": self.bind_hash,
            "opened": self.opened,
            "port_index": self.port_index,
            "requested_ephemeral_port": self.requested_ephemeral_port,
            "transport": self.transport,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class DataplaneServiceBindEvidence:
    """Payload-free bind evidence for first-party listener startup."""

    attempts: tuple[DataplaneServiceBindAttempt, ...]

    @property
    def passed(self) -> bool:
        opened_transports = {attempt.transport for attempt in self.attempts if attempt.opened}
        attempted_transports = {attempt.transport for attempt in self.attempts}
        return bool(attempted_transports) and opened_transports == attempted_transports

    @property
    def failed_reasons(self) -> tuple[str, ...]:
        if self.passed:
            return ()
        return tuple(
            f"dataplane_bind_failed:{attempt.transport}:{attempt.bind_hash}:{attempt.failure_reason}"
            for attempt in self.attempts
            if not attempt.opened
        )

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-dataplane-service-bind-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "attempts": [attempt.to_json_dict() for attempt in self.attempts],
            "failed_reasons": list(self.failed_reasons),
            "passed": self.passed,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class FirstPartyDataplaneBind:
    """Bind settings for first-party UDP/TCP/camouflage dataplane listeners."""

    host: str = "0.0.0.0"
    udp_port: int = 443
    tcp_port: int = 443
    camouflage_port: int = 443
    udp_port_candidates: tuple[int, ...] = ()
    tcp_port_candidates: tuple[int, ...] = ()
    camouflage_port_candidates: tuple[int, ...] = ()
    enable_udp: bool = True
    enable_tcp: bool = True
    enable_camouflage: bool = False

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise ValueError("dataplane bind host is required")
        if not self.enable_udp and not self.enable_tcp and not self.enable_camouflage:
            raise ValueError("at least one dataplane transport must be enabled")
        ports = (
            self.udp_port,
            self.tcp_port,
            self.camouflage_port,
            *self.udp_port_candidates,
            *self.tcp_port_candidates,
            *self.camouflage_port_candidates,
        )
        for port in ports:
            if port < 0 or port > 65535:
                raise ValueError("dataplane bind port is invalid")

    @classmethod
    def from_server_nat(
        cls,
        server_nat: LinuxServerNatConfig,
        *,
        host: str = "0.0.0.0",
    ) -> "FirstPartyDataplaneBind":
        """Build runtime listener ports from reviewed Linux server NAT config."""
        if not server_nat.allow_vpn_listener:
            raise FirstPartyDataplaneServiceError(
                "server NAT does not expose VPN listeners"
            )
        ports: dict[DataplaneTransport, list[int]] = {
            "udp": [],
            "tcp": [],
            "camouflage": [],
        }
        for listener in server_nat.listeners:
            ports[listener.transport].append(listener.port)
        return cls(
            host=host,
            udp_port=_primary_port(ports["udp"]),
            tcp_port=_primary_port(ports["tcp"]),
            camouflage_port=_primary_port(ports["camouflage"]),
            udp_port_candidates=_candidate_ports(ports["udp"]),
            tcp_port_candidates=_candidate_ports(ports["tcp"]),
            camouflage_port_candidates=_candidate_ports(ports["camouflage"]),
            enable_udp=bool(ports["udp"]),
            enable_tcp=bool(ports["tcp"]),
            enable_camouflage=bool(ports["camouflage"]),
        )

    def ports_for(self, transport: DataplaneTransport) -> tuple[int, ...]:
        if transport == "udp":
            return _dedupe_ports((self.udp_port, *self.udp_port_candidates))
        if transport == "tcp":
            return _dedupe_ports((self.tcp_port, *self.tcp_port_candidates))
        if transport == "camouflage":
            return _dedupe_ports((self.camouflage_port, *self.camouflage_port_candidates))
        raise FirstPartyDataplaneServiceError("dataplane bind transport is invalid")


@dataclass
class FirstPartyDataplaneService:
    """Owns first-party UDP/TCP/camouflage listeners for one admitted session."""

    session: SessionContext
    bind: FirstPartyDataplaneBind = field(default_factory=FirstPartyDataplaneBind)
    on_data: DataplaneHandler | None = None
    camouflage_profile: CamouflageProfile = field(default_factory=CamouflageProfile)
    camouflage_policy: CamouflagePolicy = field(default_factory=CamouflagePolicy)
    rekey_processor: FirstPartyRekeyServerProcessor | None = None
    udp_transport: asyncio.DatagramTransport | None = field(default=None, init=False)
    udp_protocol: FirstPartyUdpServer | None = field(default=None, init=False)
    udp_addr: tuple[str, int] | None = field(default=None, init=False)
    tcp_server: asyncio.Server | None = field(default=None, init=False)
    tcp_protocol: FirstPartyTcpServer | None = field(default=None, init=False)
    tcp_addr: tuple[str, int] | None = field(default=None, init=False)
    camouflage_server: asyncio.Server | None = field(default=None, init=False)
    camouflage_protocol: FirstPartyCamouflageServer | None = field(default=None, init=False)
    camouflage_addr: tuple[str, int] | None = field(default=None, init=False)
    bind_attempts: tuple[DataplaneServiceBindAttempt, ...] = field(
        default=(),
        init=False,
    )

    @property
    def running(self) -> bool:
        return (
            self.udp_transport is not None
            or self.tcp_server is not None
            or self.camouflage_server is not None
        )

    @property
    def bind_evidence(self) -> DataplaneServiceBindEvidence:
        return DataplaneServiceBindEvidence(attempts=self.bind_attempts)

    async def start(self) -> "FirstPartyDataplaneService":
        if self.running:
            raise FirstPartyDataplaneServiceError("dataplane service is already running")
        self.bind_attempts = ()
        try:
            if self.bind.enable_udp:
                self.udp_transport, self.udp_protocol, self.udp_addr = (
                    await self._open_udp_with_port_fallback()
                )
            if self.bind.enable_tcp:
                self.tcp_server, self.tcp_protocol, self.tcp_addr = (
                    await self._open_tcp_with_port_fallback()
                )
            if self.bind.enable_camouflage:
                (
                    self.camouflage_server,
                    self.camouflage_protocol,
                    self.camouflage_addr,
                ) = await self._open_camouflage_with_port_fallback()
        except Exception:
            await self.close()
            raise
        return self

    async def _open_udp_with_port_fallback(
        self,
    ) -> tuple[asyncio.DatagramTransport, FirstPartyUdpServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("udp")):
            try:
                result = await open_udp_server(
                    session=self.session,
                    host=self.bind.host,
                    port=port,
                    on_data=self.on_data,
                    rekey_processor=self.rekey_processor,
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "udp",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt("udp", port=port, port_index=port_index, opened=True)
            return result
        raise FirstPartyDataplaneServiceError(
            "dataplane UDP listener could not bind"
        ) from last_error

    async def _open_tcp_with_port_fallback(
        self,
    ) -> tuple[asyncio.Server, FirstPartyTcpServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("tcp")):
            try:
                result = await open_tcp_server(
                    session=self.session,
                    host=self.bind.host,
                    port=port,
                    on_data=self.on_data,
                    rekey_processor=self.rekey_processor,
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "tcp",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt("tcp", port=port, port_index=port_index, opened=True)
            return result
        raise FirstPartyDataplaneServiceError(
            "dataplane TCP listener could not bind"
        ) from last_error

    async def _open_camouflage_with_port_fallback(
        self,
    ) -> tuple[asyncio.Server, FirstPartyCamouflageServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("camouflage")):
            try:
                result = await open_camouflage_server(
                    session=self.session,
                    host=self.bind.host,
                    port=port,
                    profile=self.camouflage_profile,
                    policy=self.camouflage_policy,
                    on_data=self.on_data,
                    rekey_processor=self.rekey_processor,
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "camouflage",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt(
                "camouflage",
                port=port,
                port_index=port_index,
                opened=True,
            )
            return result
        raise FirstPartyDataplaneServiceError(
            "dataplane camouflage listener could not bind"
        ) from last_error

    def _record_bind_attempt(
        self,
        transport: DataplaneTransport,
        *,
        port: int,
        port_index: int,
        opened: bool,
        failure_reason: str | None = None,
    ) -> None:
        self.bind_attempts = (
            *self.bind_attempts,
            DataplaneServiceBindAttempt.from_port(
                transport=transport,
                host=self.bind.host,
                port=port,
                port_index=port_index,
                opened=opened,
                failure_reason=failure_reason,
            ),
        )

    async def close(self) -> None:
        if self.udp_transport is not None:
            self.udp_transport.close()
        self.udp_transport = None
        self.udp_protocol = None
        self.udp_addr = None

        if self.tcp_server is not None:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
        self.tcp_server = None
        if self.tcp_protocol is not None:
            await self.tcp_protocol.wait_client_tasks()
        self.tcp_protocol = None
        self.tcp_addr = None

        if self.camouflage_server is not None:
            self.camouflage_server.close()
            await self.camouflage_server.wait_closed()
        self.camouflage_server = None
        if self.camouflage_protocol is not None:
            await self.camouflage_protocol.wait_client_tasks()
        self.camouflage_protocol = None
        self.camouflage_addr = None


@dataclass
class FirstPartyMultiSessionDataplaneService:
    """Owns UDP/TCP/camouflage listeners for multiple admitted sessions."""

    sessions: tuple[SessionContext, ...]
    bind: FirstPartyDataplaneBind = field(default_factory=FirstPartyDataplaneBind)
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    camouflage_profile: CamouflageProfile = field(default_factory=CamouflageProfile)
    camouflage_policy: CamouflagePolicy = field(default_factory=CamouflagePolicy)
    udp_transport: asyncio.DatagramTransport | None = field(default=None, init=False)
    udp_protocol: FirstPartyUdpMultiSessionServer | None = field(default=None, init=False)
    udp_addr: tuple[str, int] | None = field(default=None, init=False)
    tcp_server: asyncio.Server | None = field(default=None, init=False)
    tcp_protocol: FirstPartyTcpMultiSessionServer | None = field(default=None, init=False)
    tcp_addr: tuple[str, int] | None = field(default=None, init=False)
    camouflage_server: asyncio.Server | None = field(default=None, init=False)
    camouflage_protocol: FirstPartyCamouflageMultiSessionServer | None = field(
        default=None,
        init=False,
    )
    camouflage_addr: tuple[str, int] | None = field(default=None, init=False)
    bind_attempts: tuple[DataplaneServiceBindAttempt, ...] = field(
        default=(),
        init=False,
    )

    def __post_init__(self) -> None:
        if not self.sessions:
            raise FirstPartyDataplaneServiceError(
                "multi-session dataplane service requires sessions"
            )
        session_ids = [session.session_id for session in self.sessions]
        if len(set(session_ids)) != len(session_ids):
            raise FirstPartyDataplaneServiceError(
                "multi-session dataplane service session ids must be unique"
            )

    @property
    def running(self) -> bool:
        return (
            self.udp_transport is not None
            or self.tcp_server is not None
            or self.camouflage_server is not None
        )

    @property
    def bind_evidence(self) -> DataplaneServiceBindEvidence:
        return DataplaneServiceBindEvidence(attempts=self.bind_attempts)

    async def start(self) -> "FirstPartyMultiSessionDataplaneService":
        if self.running:
            raise FirstPartyDataplaneServiceError(
                "multi-session dataplane service is already running"
            )
        self.bind_attempts = ()
        try:
            if self.bind.enable_udp:
                self.udp_transport, self.udp_protocol, self.udp_addr = (
                    await self._open_udp_with_port_fallback()
                )
            if self.bind.enable_tcp:
                self.tcp_server, self.tcp_protocol, self.tcp_addr = (
                    await self._open_tcp_with_port_fallback()
                )
            if self.bind.enable_camouflage:
                (
                    self.camouflage_server,
                    self.camouflage_protocol,
                    self.camouflage_addr,
                ) = await self._open_camouflage_with_port_fallback()
        except Exception:
            await self.close()
            raise
        return self

    async def _open_udp_with_port_fallback(
        self,
    ) -> tuple[asyncio.DatagramTransport, FirstPartyUdpMultiSessionServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("udp")):
            try:
                result = await open_udp_multi_session_server(
                    sessions=self.sessions,
                    host=self.bind.host,
                    port=port,
                    on_data=self.on_data,
                    on_session_data=self.on_session_data,
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "udp",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt("udp", port=port, port_index=port_index, opened=True)
            return result
        raise FirstPartyDataplaneServiceError(
            "multi-session UDP listener could not bind"
        ) from last_error

    async def _open_tcp_with_port_fallback(
        self,
    ) -> tuple[asyncio.Server, FirstPartyTcpMultiSessionServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("tcp")):
            try:
                result = await open_tcp_multi_session_server(
                    sessions=self.sessions,
                    host=self.bind.host,
                    port=port,
                    on_data=self.on_data,
                    on_session_data=self.on_session_data,
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "tcp",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt("tcp", port=port, port_index=port_index, opened=True)
            return result
        raise FirstPartyDataplaneServiceError(
            "multi-session TCP listener could not bind"
        ) from last_error

    async def _open_camouflage_with_port_fallback(
        self,
    ) -> tuple[
        asyncio.Server,
        FirstPartyCamouflageMultiSessionServer,
        tuple[str, int],
    ]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("camouflage")):
            try:
                result = await open_camouflage_multi_session_server(
                    sessions=self.sessions,
                    host=self.bind.host,
                    port=port,
                    profile=self.camouflage_profile,
                    policy=self.camouflage_policy,
                    on_data=self.on_data,
                    on_session_data=self.on_session_data,
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "camouflage",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt(
                "camouflage",
                port=port,
                port_index=port_index,
                opened=True,
            )
            return result
        raise FirstPartyDataplaneServiceError(
            "multi-session camouflage listener could not bind"
        ) from last_error

    def _record_bind_attempt(
        self,
        transport: DataplaneTransport,
        *,
        port: int,
        port_index: int,
        opened: bool,
        failure_reason: str | None = None,
    ) -> None:
        self.bind_attempts = (
            *self.bind_attempts,
            DataplaneServiceBindAttempt.from_port(
                transport=transport,
                host=self.bind.host,
                port=port,
                port_index=port_index,
                opened=opened,
                failure_reason=failure_reason,
            ),
        )

    async def close(self) -> None:
        if self.udp_transport is not None:
            self.udp_transport.close()
        self.udp_transport = None
        self.udp_protocol = None
        self.udp_addr = None

        if self.tcp_server is not None:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
        self.tcp_server = None
        if self.tcp_protocol is not None:
            await self.tcp_protocol.wait_client_tasks()
        self.tcp_protocol = None
        self.tcp_addr = None

        if self.camouflage_server is not None:
            self.camouflage_server.close()
            await self.camouflage_server.wait_closed()
        self.camouflage_server = None
        if self.camouflage_protocol is not None:
            await self.camouflage_protocol.wait_client_tasks()
        self.camouflage_protocol = None
        self.camouflage_addr = None


@dataclass
class FirstPartyAdmissionDataplaneService:
    """Owns UDP/TCP/camouflage listeners that admit sessions through HELLO/ACCEPT."""

    registry: FirstPartySessionAdmissionRegistry
    bind: FirstPartyDataplaneBind = field(default_factory=FirstPartyDataplaneBind)
    on_data: DataplaneHandler | None = None
    on_session_data: SessionDataplaneHandler | None = None
    on_session_ping: SessionPingHandler | None = None
    camouflage_profile: CamouflageProfile = field(default_factory=CamouflageProfile)
    camouflage_policy: CamouflagePolicy = field(default_factory=CamouflagePolicy)
    udp_transport: asyncio.DatagramTransport | None = field(default=None, init=False)
    udp_protocol: FirstPartyUdpAdmissionServer | None = field(default=None, init=False)
    udp_addr: tuple[str, int] | None = field(default=None, init=False)
    tcp_server: asyncio.Server | None = field(default=None, init=False)
    tcp_protocol: FirstPartyTcpAdmissionServer | None = field(default=None, init=False)
    tcp_addr: tuple[str, int] | None = field(default=None, init=False)
    camouflage_server: asyncio.Server | None = field(default=None, init=False)
    camouflage_protocol: FirstPartyCamouflageAdmissionServer | None = field(
        default=None,
        init=False,
    )
    camouflage_addr: tuple[str, int] | None = field(default=None, init=False)
    active_transport_by_session: dict[int, DataplaneTransport] = field(
        default_factory=dict,
        init=False,
    )
    bind_attempts: tuple[DataplaneServiceBindAttempt, ...] = field(
        default=(),
        init=False,
    )

    @property
    def running(self) -> bool:
        return (
            self.udp_transport is not None
            or self.tcp_server is not None
            or self.camouflage_server is not None
        )

    @property
    def bind_evidence(self) -> DataplaneServiceBindEvidence:
        return DataplaneServiceBindEvidence(attempts=self.bind_attempts)

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return self.registry.admitted_session_ids

    async def start(self) -> "FirstPartyAdmissionDataplaneService":
        if self.running:
            raise FirstPartyDataplaneServiceError(
                "admission dataplane service is already running"
            )
        self.bind_attempts = ()
        try:
            if self.bind.enable_udp:
                self.udp_transport, self.udp_protocol, self.udp_addr = (
                    await self._open_udp_with_port_fallback()
                )
            if self.bind.enable_tcp:
                self.tcp_server, self.tcp_protocol, self.tcp_addr = (
                    await self._open_tcp_with_port_fallback()
                )
            if self.bind.enable_camouflage:
                (
                    self.camouflage_server,
                    self.camouflage_protocol,
                    self.camouflage_addr,
                ) = await self._open_camouflage_with_port_fallback()
        except Exception:
            await self.close()
            raise
        return self

    async def _open_udp_with_port_fallback(
        self,
    ) -> tuple[asyncio.DatagramTransport, FirstPartyUdpAdmissionServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("udp")):
            try:
                result = await open_udp_admission_server(
                    registry=self.registry,
                    host=self.bind.host,
                    port=port,
                    on_data=self.on_data,
                    on_session_data=self._session_data_handler_for("udp"),
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "udp",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt("udp", port=port, port_index=port_index, opened=True)
            return result
        raise FirstPartyDataplaneServiceError(
            "admission UDP listener could not bind"
        ) from last_error

    async def _open_tcp_with_port_fallback(
        self,
    ) -> tuple[asyncio.Server, FirstPartyTcpAdmissionServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("tcp")):
            try:
                result = await open_tcp_admission_server(
                    registry=self.registry,
                    host=self.bind.host,
                    port=port,
                    on_data=self.on_data,
                    on_session_data=self._session_data_handler_for("tcp"),
                    on_session_ping=self._session_ping_handler_for("tcp"),
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "tcp",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt("tcp", port=port, port_index=port_index, opened=True)
            return result
        raise FirstPartyDataplaneServiceError(
            "admission TCP listener could not bind"
        ) from last_error

    async def _open_camouflage_with_port_fallback(
        self,
    ) -> tuple[asyncio.Server, FirstPartyCamouflageAdmissionServer, tuple[str, int]]:
        last_error: Exception | None = None
        for port_index, port in enumerate(self.bind.ports_for("camouflage")):
            try:
                result = await open_camouflage_admission_server(
                    registry=self.registry,
                    host=self.bind.host,
                    port=port,
                    profile=self.camouflage_profile,
                    policy=self.camouflage_policy,
                    on_data=self.on_data,
                    on_session_data=self._session_data_handler_for("camouflage"),
                    on_session_ping=self._session_ping_handler_for("camouflage"),
                )
            except Exception as exc:
                self._record_bind_attempt(
                    "camouflage",
                    port=port,
                    port_index=port_index,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
                last_error = exc
                continue
            self._record_bind_attempt(
                "camouflage",
                port=port,
                port_index=port_index,
                opened=True,
            )
            return result
        raise FirstPartyDataplaneServiceError(
            "admission camouflage listener could not bind"
        ) from last_error

    def _record_bind_attempt(
        self,
        transport: DataplaneTransport,
        *,
        port: int,
        port_index: int,
        opened: bool,
        failure_reason: str | None = None,
    ) -> None:
        self.bind_attempts = (
            *self.bind_attempts,
            DataplaneServiceBindAttempt.from_port(
                transport=transport,
                host=self.bind.host,
                port=port,
                port_index=port_index,
                opened=opened,
                failure_reason=failure_reason,
            ),
        )

    def _session_data_handler_for(
        self,
        transport: DataplaneTransport,
    ) -> SessionDataplaneHandler | None:
        if self.on_session_data is None:
            return None

        def handler(
            packet: bytes,
            addr: tuple[str, int],
            session: SessionContext,
        ) -> DataplaneResponse:
            self.active_transport_by_session[session.session_id] = transport
            return self.on_session_data(packet, addr, session)

        return handler

    def _session_ping_handler_for(
        self,
        transport: DataplaneTransport,
    ) -> SessionPingHandler | None:
        if self.on_session_ping is None:
            return None

        def handler(
            payload: bytes,
            addr: tuple[str, int],
            session: SessionContext,
        ) -> bytes | None:
            self.active_transport_by_session[session.session_id] = transport
            return self.on_session_ping(payload, addr, session)

        return handler

    async def close(self) -> None:
        if self.udp_transport is not None:
            self.udp_transport.close()
        self.udp_transport = None
        self.udp_protocol = None
        self.udp_addr = None

        if self.tcp_server is not None:
            self.tcp_server.close()
            await self.tcp_server.wait_closed()
        self.tcp_server = None
        if self.tcp_protocol is not None:
            await self.tcp_protocol.wait_client_tasks()
        self.tcp_protocol = None
        self.tcp_addr = None

        if self.camouflage_server is not None:
            self.camouflage_server.close()
            await self.camouflage_server.wait_closed()
        self.camouflage_server = None
        if self.camouflage_protocol is not None:
            await self.camouflage_protocol.wait_client_tasks()
        self.camouflage_protocol = None
        self.camouflage_addr = None
        self.active_transport_by_session.clear()


@dataclass
class FirstPartyThreadedDataplaneServiceResource:
    """Closeable sync handle for a first-party async dataplane service."""

    service: (
        FirstPartyDataplaneService
        | FirstPartyMultiSessionDataplaneService
        | FirstPartyAdmissionDataplaneService
    )
    loop: asyncio.AbstractEventLoop = field(repr=False)
    thread: threading.Thread = field(repr=False)
    close_timeout: float = field(default=5.0, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def running(self) -> bool:
        return not self._closed and self.thread.is_alive() and self.service.running

    @property
    def bind_evidence(self) -> DataplaneServiceBindEvidence:
        return self.service.bind_evidence

    def close(self) -> None:
        if self._closed:
            return
        close_error: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(self.service.close(), self.loop)
            future.result(timeout=self.close_timeout)
        except Exception as exc:
            close_error = exc
        finally:
            self._closed = True
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=self.close_timeout)
        if self.thread.is_alive():
            raise FirstPartyDataplaneServiceError(
                "threaded dataplane service loop did not stop"
            ) from close_error
        if close_error is not None:
            raise FirstPartyDataplaneServiceError(
                "threaded dataplane service close failed"
            ) from close_error


async def open_firstparty_dataplane_service(
    *,
    session: SessionContext,
    bind: FirstPartyDataplaneBind | None = None,
    on_data: DataplaneHandler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    rekey_processor: FirstPartyRekeyServerProcessor | None = None,
) -> FirstPartyDataplaneService:
    """Open a first-party dataplane service and return the running lifecycle owner."""
    service = FirstPartyDataplaneService(
        session=session,
        bind=bind or FirstPartyDataplaneBind(),
        on_data=on_data,
        camouflage_profile=camouflage_profile or CamouflageProfile(),
        camouflage_policy=camouflage_policy or CamouflagePolicy(),
        rekey_processor=rekey_processor,
    )
    return await service.start()


def open_threaded_firstparty_dataplane_service(
    *,
    session: SessionContext,
    bind: FirstPartyDataplaneBind | None = None,
    on_data: DataplaneHandler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    rekey_processor: FirstPartyRekeyServerProcessor | None = None,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedDataplaneServiceResource:
    """Start the one-session dataplane service and return a sync closeable handle."""
    return _start_threaded_dataplane_service(
        lambda: open_firstparty_dataplane_service(
            session=session,
            bind=bind,
            on_data=on_data,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
            rekey_processor=rekey_processor,
        ),
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )


async def open_firstparty_multi_session_dataplane_service(
    *,
    sessions: tuple[SessionContext, ...],
    bind: FirstPartyDataplaneBind | None = None,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
) -> FirstPartyMultiSessionDataplaneService:
    """Open a first-party dataplane service for multiple admitted sessions."""
    service = FirstPartyMultiSessionDataplaneService(
        sessions=sessions,
        bind=bind or FirstPartyDataplaneBind(),
        on_data=on_data,
        on_session_data=on_session_data,
        camouflage_profile=camouflage_profile or CamouflageProfile(),
        camouflage_policy=camouflage_policy or CamouflagePolicy(),
    )
    return await service.start()


def open_threaded_firstparty_multi_session_dataplane_service(
    *,
    sessions: tuple[SessionContext, ...],
    bind: FirstPartyDataplaneBind | None = None,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedDataplaneServiceResource:
    """Start the multi-session dataplane service and return a sync closeable handle."""
    return _start_threaded_dataplane_service(
        lambda: open_firstparty_multi_session_dataplane_service(
            sessions=sessions,
            bind=bind,
            on_data=on_data,
            on_session_data=on_session_data,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
        ),
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )


async def open_firstparty_admission_dataplane_service(
    *,
    registry: FirstPartySessionAdmissionRegistry,
    bind: FirstPartyDataplaneBind | None = None,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
    on_session_ping: SessionPingHandler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
) -> FirstPartyAdmissionDataplaneService:
    """Open a first-party dataplane service that admits sessions on demand."""
    service = FirstPartyAdmissionDataplaneService(
        registry=registry,
        bind=bind or FirstPartyDataplaneBind(),
        on_data=on_data,
        on_session_data=on_session_data,
        on_session_ping=on_session_ping,
        camouflage_profile=camouflage_profile or CamouflageProfile(),
        camouflage_policy=camouflage_policy or CamouflagePolicy(),
    )
    return await service.start()


def open_threaded_firstparty_admission_dataplane_service(
    *,
    registry: FirstPartySessionAdmissionRegistry,
    bind: FirstPartyDataplaneBind | None = None,
    on_data: DataplaneHandler | None = None,
    on_session_data: SessionDataplaneHandler | None = None,
    on_session_ping: SessionPingHandler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedDataplaneServiceResource:
    """Start the admission dataplane service and return a sync closeable handle."""
    return _start_threaded_dataplane_service(
        lambda: open_firstparty_admission_dataplane_service(
            registry=registry,
            bind=bind,
            on_data=on_data,
            on_session_data=on_session_data,
            on_session_ping=on_session_ping,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
        ),
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )


def _start_threaded_dataplane_service(
    starter: Callable[
        [],
        Awaitable[
            FirstPartyDataplaneService
            | FirstPartyMultiSessionDataplaneService
            | FirstPartyAdmissionDataplaneService
        ],
    ],
    *,
    start_timeout: float,
    close_timeout: float,
) -> FirstPartyThreadedDataplaneServiceResource:
    if start_timeout <= 0 or close_timeout <= 0:
        raise FirstPartyDataplaneServiceError(
            "threaded dataplane timeouts must be positive"
        )
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    thread = threading.Thread(
        target=_run_threaded_dataplane_loop,
        args=(loop, ready),
        name="x0vpn-dataplane-service",
        daemon=True,
    )
    thread.start()
    if not ready.wait(timeout=start_timeout):
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=close_timeout)
        raise FirstPartyDataplaneServiceError(
            "threaded dataplane service loop did not start"
        )
    future = asyncio.run_coroutine_threadsafe(starter(), loop)
    try:
        service = future.result(timeout=start_timeout)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=close_timeout)
        raise FirstPartyDataplaneServiceError(
            "threaded dataplane service startup timed out"
        ) from exc
    except Exception as exc:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=close_timeout)
        raise FirstPartyDataplaneServiceError(
            "threaded dataplane service startup failed"
        ) from exc
    return FirstPartyThreadedDataplaneServiceResource(
        service=service,
        loop=loop,
        thread=thread,
        close_timeout=close_timeout,
    )


def _run_threaded_dataplane_loop(
    loop: asyncio.AbstractEventLoop,
    ready: threading.Event,
) -> None:
    asyncio.set_event_loop(loop)
    ready.set()
    try:
        loop.run_forever()
    finally:
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
        loop.close()
        asyncio.set_event_loop(None)


def _dedupe_ports(ports: tuple[int, ...]) -> tuple[int, ...]:
    deduped: list[int] = []
    for port in ports:
        if port not in deduped:
            deduped.append(port)
    return tuple(deduped)


def _primary_port(ports: list[int]) -> int:
    if ports:
        return ports[0]
    return 443


def _candidate_ports(ports: list[int]) -> tuple[int, ...]:
    if len(ports) <= 1:
        return ()
    return tuple(ports[1:])


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
