"""TUN bridge primitives for the first-party VPN runtime.

The in-memory device is for deterministic local tests and development. It
models the packet boundaries expected from a real TUN interface without
creating OS interfaces or mutating routing tables.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import fcntl
import inspect
import ipaddress
import os
import queue
import select
import struct
import subprocess
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable, Literal, Mapping, Protocol, Sequence

from .fragmentation import FragmentError, PacketFragmenter, PacketReassembler
from .mtu import MtuProbeResult
from .protocol import FrameType
from .runtime import FirstPartyUdpClient, SessionRouteDrop
from .session import SessionContext
from src.core.security.subprocess_validator import safe_run

if TYPE_CHECKING:
    from .camouflage import CamouflagePolicy, CamouflageProfile
    from .handshake import FirstPartyHandshakeAccept, FirstPartyHandshakeHello
    from .client import FirstPartyDataplaneClient
    from .admission import FirstPartySessionAdmissionRegistry
    from .service import (
        FirstPartyAdmissionDataplaneService,
        FirstPartyDataplaneBind,
        FirstPartyThreadedDataplaneServiceResource,
    )
    from .identity import IdentityVerifier, RevocationList, SignedIdentityToken
    from .pqc import PqcProvider, PqcSessionSecretMaterial
    from .rekey import (
        FirstPartyRekeyAccept,
        FirstPartyRekeyClientResult,
        FirstPartyRekeyServerProcessor,
    )
    from .selection import (
        DataplaneEndpointCandidate,
        DataplaneSelectionEvidence,
        TunDataplaneSelectionEvidence,
    )
    from .zero_trust import ZeroTrustPolicy

_IFF_TUN = 0x0001
_IFF_NO_PI = 0x1000
_TUNSETIFF = 0x400454CA
_LINUX_IFACE_NAME_MAX = 15

LinuxTunCommand = tuple[str, ...]
CommandRunner = Callable[[LinuxTunCommand], None]
TunReturnTransport = Literal["udp", "tcp", "camouflage"]


class TunPacketError(ValueError):
    """Raised when a TUN packet cannot be accepted by the bridge."""


class LinuxTunError(TunPacketError):
    """Raised when the Linux TUN adapter cannot be used."""


class LinuxTunMutationBlocked(LinuxTunError):
    """Raised when OS mutation is requested without an explicit allow flag."""


class FirstPartyTunPumpError(RuntimeError):
    """Raised when a first-party TUN pump lifecycle is invalid."""


class TunDevice(Protocol):
    mtu: int

    async def read_packet(self, timeout: float | None = None) -> bytes: ...

    async def write_packet(self, packet: bytes) -> None: ...

    def write_packet_nowait(self, packet: bytes) -> None: ...


class FirstPartyClientTransport(Protocol):
    endpoint: object

    def send_data_fragments(self, payloads: Sequence[bytes]) -> None: ...

    async def recv(self, timeout: float = 1.0): ...

    async def drain(self) -> None: ...


class FirstPartyServerTransport(Protocol):
    def send_data_fragments(self, payloads: Sequence[bytes]): ...


class FirstPartyMultiSessionServerTransport(Protocol):
    def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        *,
        session: SessionContext | int,
    ): ...


@dataclass
class TunBridgeStats:
    packets_from_tun: int = 0
    packets_to_tun: int = 0
    bytes_from_tun: int = 0
    bytes_to_tun: int = 0
    mtu_drops: int = 0
    non_data_drops: int = 0
    tx_fragments: int = 0
    rx_fragments: int = 0
    fragment_drops: int = 0
    mtu_probe_updates: int = 0


@dataclass
class TunPumpStats:
    tun_to_transport_cycles: int = 0
    transport_to_tun_cycles: int = 0
    timeouts: int = 0
    errors: int = 0
    cancellations: int = 0
    rekeys: int = 0
    last_error: str | None = None

    def __post_init__(self) -> None:
        for value in (
            self.tun_to_transport_cycles,
            self.transport_to_tun_cycles,
            self.timeouts,
            self.errors,
            self.cancellations,
            self.rekeys,
        ):
            if value < 0:
                raise ValueError("TUN pump counters cannot be negative")


def _validate_packet(packet: bytes, mtu: int) -> None:
    if not packet:
        raise TunPacketError("packet is empty")
    if len(packet) > mtu:
        raise TunPacketError("packet exceeds MTU")
    version = packet[0] >> 4
    if version not in (4, 6):
        raise TunPacketError("packet must be IPv4 or IPv6")
    if version == 4:
        if len(packet) < 20:
            raise TunPacketError("IPv4 packet is too short")
        header_length = (packet[0] & 0x0F) * 4
        total_length = int.from_bytes(packet[2:4], "big")
        if header_length < 20 or header_length > len(packet):
            raise TunPacketError("IPv4 header length is invalid")
        if total_length != len(packet) or total_length < header_length:
            raise TunPacketError("IPv4 total length is invalid")
    else:
        if len(packet) < 40:
            raise TunPacketError("IPv6 packet is too short")
        payload_length = int.from_bytes(packet[4:6], "big")
        if payload_length + 40 != len(packet):
            raise TunPacketError("IPv6 payload length is invalid")


def _packet_destination_ip(packet: bytes) -> str:
    _validate_packet(packet, len(packet))
    version = packet[0] >> 4
    if version == 4:
        return str(ipaddress.IPv4Address(packet[16:20]))
    return str(ipaddress.IPv6Address(packet[24:40]))


class MemoryTunDevice:
    """In-memory packet device with TUN-like read/write semantics."""

    def __init__(self, *, mtu: int = 1400) -> None:
        if mtu < 576:
            raise ValueError("MTU must be at least 576")
        self.mtu = mtu
        self._read_queue: queue.Queue[bytes] = queue.Queue()
        self._write_queue: queue.Queue[bytes] = queue.Queue()

    def inject_packet(self, packet: bytes) -> None:
        self._validate(packet)
        self._read_queue.put_nowait(packet)

    async def read_packet(self, timeout: float | None = None) -> bytes:
        return await _read_memory_tun_queue(self._read_queue, timeout=timeout)

    async def write_packet(self, packet: bytes) -> None:
        self.write_packet_nowait(packet)

    def write_packet_nowait(self, packet: bytes) -> None:
        self._validate(packet)
        self._write_queue.put_nowait(packet)

    async def read_written(self, timeout: float | None = None) -> bytes:
        return await _read_memory_tun_queue(self._write_queue, timeout=timeout)

    def _validate(self, packet: bytes) -> None:
        _validate_packet(packet, self.mtu)


async def _read_memory_tun_queue(
    packets: queue.Queue[bytes],
    *,
    timeout: float | None,
) -> bytes:
    loop = asyncio.get_running_loop()
    deadline = None if timeout is None else loop.time() + timeout
    while True:
        try:
            return packets.get_nowait()
        except queue.Empty:
            if deadline is not None:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise TimeoutError("TUN packet read timed out")
                await asyncio.sleep(min(remaining, 0.01))
                continue
            await asyncio.sleep(0.01)


@dataclass(frozen=True)
class LinuxTunConfig:
    """Configuration for a Linux TUN interface.

    OS mutation is blocked unless allow_os_mutation is set. This lets tests and
    rollout tooling inspect the exact commands before any local route changes.
    """

    name: str = "x0vpn0"
    mtu: int = 1400
    address: str | None = None
    peer: str | None = None
    device_path: str = "/dev/net/tun"
    allow_os_mutation: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("TUN interface name is required")
        if len(self.name.encode("utf-8")) > _LINUX_IFACE_NAME_MAX:
            raise ValueError("TUN interface name must fit Linux IFNAMSIZ")
        if any(ch.isspace() or ch in {"/", "\x00"} for ch in self.name):
            raise ValueError("TUN interface name contains an unsafe character")
        if self.mtu < 576:
            raise ValueError("MTU must be at least 576")
        if self.address is None and self.peer is not None:
            raise ValueError("peer requires address")

    def network_commands(self) -> tuple[LinuxTunCommand, ...]:
        commands: list[LinuxTunCommand] = [
            ("ip", "link", "set", "dev", self.name, "mtu", str(self.mtu)),
        ]
        if self.address is not None:
            if self.peer is None:
                commands.append(("ip", "addr", "add", self.address, "dev", self.name))
            else:
                commands.append(
                    (
                        "ip",
                        "addr",
                        "add",
                        self.address,
                        "peer",
                        self.peer,
                        "dev",
                        self.name,
                    )
                )
        commands.append(("ip", "link", "set", "dev", self.name, "up"))
        return tuple(commands)


class LinuxTunDevice:
    """Linux TUN device adapter with fail-closed OS mutation controls."""

    def __init__(
        self,
        *,
        config: LinuxTunConfig,
        fd: int | None = None,
        owns_fd: bool = False,
        command_runner: CommandRunner | None = None,
    ) -> None:
        self.config = config
        self.mtu = config.mtu
        self._fd = fd
        self._owns_fd = owns_fd
        self._command_runner = command_runner or self._default_command_runner

    @property
    def fd(self) -> int | None:
        return self._fd

    def planned_network_commands(self) -> tuple[LinuxTunCommand, ...]:
        return self.config.network_commands()

    def open_interface(self) -> None:
        self._assert_mutation_allowed()
        if self._fd is not None:
            return
        fd = os.open(self.config.device_path, os.O_RDWR)
        try:
            if_name = self.config.name.encode("utf-8")
            ifr = struct.pack("16sH", if_name, _IFF_TUN | _IFF_NO_PI)
            fcntl.ioctl(fd, _TUNSETIFF, ifr)
        except OSError:
            os.close(fd)
            raise
        self._fd = fd
        self._owns_fd = True

    def apply_network_config(self) -> None:
        self._assert_mutation_allowed()
        for command in self.planned_network_commands():
            self._command_runner(command)

    def activate(self) -> None:
        self.open_interface()
        self.apply_network_config()

    async def read_packet(self, timeout: float | None = None) -> bytes:
        fd = self._require_fd()
        loop = asyncio.get_running_loop()
        packet = await loop.run_in_executor(
            None,
            _read_linux_tun_packet,
            fd,
            self.mtu,
            timeout,
        )
        _validate_packet(packet, self.mtu)
        return packet

    async def write_packet(self, packet: bytes) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.write_packet_nowait, packet)

    def write_packet_nowait(self, packet: bytes) -> None:
        _validate_packet(packet, self.mtu)
        os.write(self._require_fd(), packet)

    def close(self) -> None:
        if self._fd is not None and self._owns_fd:
            os.close(self._fd)
        self._fd = None

    def _require_fd(self) -> int:
        if self._fd is None:
            raise LinuxTunError("Linux TUN interface is not open")
        return self._fd

    def _assert_mutation_allowed(self) -> None:
        if not self.config.allow_os_mutation:
            raise LinuxTunMutationBlocked(
                "Linux TUN OS mutation is blocked; set allow_os_mutation=True"
            )

    @staticmethod
    def _default_command_runner(command: Sequence[str]) -> None:
        safe_run(list(command), check=True)


def _read_linux_tun_packet(fd: int, mtu: int, timeout: float | None) -> bytes:
    if timeout is not None:
        ready, _writable, _errors = select.select((fd,), (), (), timeout)
        if not ready:
            raise TimeoutError
    return os.read(fd, mtu)


@dataclass
class FirstPartyTunClientBridge:
    """Bridge packets between a TUN-like device and first-party UDP client."""

    tun: TunDevice
    client: FirstPartyClientTransport | FirstPartyUdpClient
    fragmenter: PacketFragmenter | None = None
    reassembler: PacketReassembler | None = None
    stats: TunBridgeStats = field(default_factory=TunBridgeStats)

    def apply_mtu_probe_result(self, result: MtuProbeResult) -> None:
        self.fragmenter = result.fragmenter()
        self.stats.mtu_probe_updates += 1

    async def send_one_from_tun(self, timeout: float = 1.0) -> None:
        packet = await self.tun.read_packet(timeout=timeout)
        if len(packet) > self.tun.mtu:
            self.stats.mtu_drops += 1
            raise TunPacketError("packet exceeds MTU")
        payloads = self.fragmenter.split(packet) if self.fragmenter else (packet,)
        self.client.send_data_fragments(payloads)
        drain = getattr(self.client, "drain", None)
        if drain is not None:
            await drain()
        self.stats.packets_from_tun += 1
        self.stats.bytes_from_tun += len(packet)
        self.stats.tx_fragments += len(payloads)

    async def receive_one_to_tun(self, timeout: float = 1.0) -> None:
        packet: bytes | None = None
        while packet is None:
            frame = await self.client.recv(timeout=timeout)
            if frame.frame_type != FrameType.DATA:
                self.stats.non_data_drops += 1
                raise TunPacketError("received non-DATA frame for TUN")
            if self.reassembler is None:
                packet = frame.payload
            else:
                try:
                    packet = self.reassembler.accept(frame.payload)
                except FragmentError as exc:
                    self.stats.fragment_drops += 1
                    raise TunPacketError(str(exc)) from exc
                self.stats.rx_fragments += 1
        await self.tun.write_packet(packet)
        self.stats.packets_to_tun += 1
        self.stats.bytes_to_tun += len(packet)

    async def perform_rekey(
        self,
        *,
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
    ) -> FirstPartyRekeyClientResult:
        """Rotate the selected first-party transport without changing TUN state."""
        from .rekey import perform_firstparty_transport_rekey

        return await perform_firstparty_transport_rekey(
            transport=self.client,
            pqc_provider=pqc_provider,
            client_identity=client_identity,
            server_identity=server_identity,
            identity_authority=identity_authority,
            policy=policy,
            base_deployment_epoch=base_deployment_epoch,
            generation=generation,
            reason=reason,
            client_nonce=client_nonce,
            requested_at=requested_at,
            timeout=timeout,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
        )


@dataclass
class FirstPartyManagedTunClientBridge:
    """Owns a selected first-party dataplane client and its TUN bridge."""

    client: FirstPartyDataplaneClient
    bridge: FirstPartyTunClientBridge
    tun_selection_evidence: TunDataplaneSelectionEvidence | None = None

    @property
    def selection_evidence(self) -> DataplaneSelectionEvidence:
        return self.client.selection_evidence

    @property
    def stats(self) -> TunBridgeStats:
        return self.bridge.stats

    async def send_one_from_tun(self, timeout: float = 1.0) -> None:
        await self.bridge.send_one_from_tun(timeout=timeout)

    async def receive_one_to_tun(self, timeout: float = 1.0) -> None:
        await self.bridge.receive_one_to_tun(timeout=timeout)

    async def perform_rekey(
        self,
        *,
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
    ) -> FirstPartyRekeyClientResult:
        """Rotate the selected transport used by this managed TUN bridge."""
        return await self.bridge.perform_rekey(
            pqc_provider=pqc_provider,
            client_identity=client_identity,
            server_identity=server_identity,
            identity_authority=identity_authority,
            policy=policy,
            base_deployment_epoch=base_deployment_epoch,
            generation=generation,
            reason=reason,
            client_nonce=client_nonce,
            requested_at=requested_at,
            timeout=timeout,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
        )

    async def close(self) -> None:
        await self.client.close()


async def open_firstparty_tun_client_bridge(
    *,
    session: SessionContext,
    tun: TunDevice,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    captured_at: int,
    require_tun_dataplane_probe: bool = False,
    tun_probe_mtu: int | None = None,
    tun_probe_fragment_payload_size: int = 512,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
) -> FirstPartyManagedTunClientBridge:
    """Open a failover-selected first-party client and bridge it to a TUN device."""
    from .client import FirstPartyDataplaneClientError, open_firstparty_dataplane_client
    from .selection import FirstPartyTunDataplaneSelector

    tun_selection_evidence = None
    open_candidates = candidates
    if require_tun_dataplane_probe:
        outcome = await FirstPartyTunDataplaneSelector(
            session=session,
            candidates=candidates,
            tun_mtu=tun_probe_mtu if tun_probe_mtu is not None else tun.mtu,
            fragment_payload_size=tun_probe_fragment_payload_size,
        ).select(captured_at=captured_at)
        tun_selection_evidence = outcome.evidence
        if outcome.selected is None:
            raise FirstPartyDataplaneClientError(
                "no working first-party TUN dataplane endpoint",
                tun_selection_evidence=outcome.evidence,
            )
        open_candidates = (outcome.selected,)

    client = await open_firstparty_dataplane_client(
        session=session,
        candidates=open_candidates,
        captured_at=captured_at,
    )
    bridge = FirstPartyTunClientBridge(
        tun=tun,
        client=client,
        fragmenter=fragmenter,
        reassembler=reassembler,
    )
    return FirstPartyManagedTunClientBridge(
        client=client,
        bridge=bridge,
        tun_selection_evidence=tun_selection_evidence,
    )


async def open_firstparty_admission_tun_client_bridge(
    *,
    hello: FirstPartyHandshakeHello,
    pqc_material: PqcSessionSecretMaterial,
    tun: TunDevice,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    captured_at: int,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    revocations: RevocationList | None = None,
    completed_at_provider: Callable[[FirstPartyHandshakeAccept], int] | None = None,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
) -> FirstPartyManagedTunClientBridge:
    """Open an admitted first-party client and bridge it to a TUN device."""
    from .client import open_firstparty_admission_dataplane_client

    client = await open_firstparty_admission_dataplane_client(
        hello=hello,
        pqc_material=pqc_material,
        candidates=candidates,
        identity_authority=identity_authority,
        policy=policy,
        captured_at=captured_at,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        revocations=revocations,
        completed_at_provider=completed_at_provider,
    )
    bridge = FirstPartyTunClientBridge(
        tun=tun,
        client=client,
        fragmenter=fragmenter,
        reassembler=reassembler,
    )
    return FirstPartyManagedTunClientBridge(client=client, bridge=bridge)


@dataclass
class FirstPartyTunClientPump:
    """Continuously pumps packets between TUN and selected first-party transport."""

    managed: FirstPartyManagedTunClientBridge
    tun_read_timeout: float = 0.1
    transport_read_timeout: float = 0.1
    max_errors: int = 1
    stats: TunPumpStats = field(default_factory=TunPumpStats)
    _tasks: tuple[asyncio.Task[None], ...] = field(default=(), init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.tun_read_timeout <= 0 or self.transport_read_timeout <= 0:
            raise ValueError("TUN pump timeouts must be positive")
        if self.max_errors < 1:
            raise ValueError("TUN pump max_errors must be positive")

    @property
    def running(self) -> bool:
        return any(not task.done() for task in self._tasks)

    def start(self) -> "FirstPartyTunClientPump":
        if self.running:
            raise FirstPartyTunPumpError("TUN pump is already running")
        self._stop_event = asyncio.Event()
        self._tasks = (
            asyncio.create_task(self._pump_tun_to_transport()),
            asyncio.create_task(self._pump_transport_to_tun()),
        )
        return self

    async def stop(self) -> None:
        await self._cancel_tasks()
        await self.managed.close()

    async def _cancel_tasks(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = ()
        self._stop_event = None

    async def perform_rekey(
        self,
        *,
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
    ) -> FirstPartyRekeyClientResult:
        """Pause pumping, rotate transport keys, then resume if the pump was running."""
        was_running = self.running
        if was_running:
            await self._cancel_tasks()
        try:
            result = await self.managed.perform_rekey(
                pqc_provider=pqc_provider,
                client_identity=client_identity,
                server_identity=server_identity,
                identity_authority=identity_authority,
                policy=policy,
                base_deployment_epoch=base_deployment_epoch,
                generation=generation,
                reason=reason,
                client_nonce=client_nonce,
                requested_at=requested_at,
                timeout=timeout,
                revocations=revocations,
                completed_at_provider=completed_at_provider,
            )
            self.stats.rekeys += 1
            return result
        finally:
            if was_running and self._stop_event is None:
                self.start()

    async def _pump_tun_to_transport(self) -> None:
        while not self._stopping:
            try:
                await self.managed.send_one_from_tun(timeout=self.tun_read_timeout)
                self.stats.tun_to_transport_cycles += 1
            except (TimeoutError, asyncio.TimeoutError):
                self.stats.timeouts += 1
            except asyncio.CancelledError:
                self.stats.cancellations += 1
                raise
            except Exception as exc:
                self._record_error(exc)

    async def _pump_transport_to_tun(self) -> None:
        while not self._stopping:
            try:
                await self.managed.receive_one_to_tun(timeout=self.transport_read_timeout)
                self.stats.transport_to_tun_cycles += 1
            except (TimeoutError, asyncio.TimeoutError):
                self.stats.timeouts += 1
            except asyncio.CancelledError:
                self.stats.cancellations += 1
                raise
            except Exception as exc:
                self._record_error(exc)

    @property
    def _stopping(self) -> bool:
        return self._stop_event is None or self._stop_event.is_set()

    def _record_error(self, exc: Exception) -> None:
        self.stats.errors += 1
        self.stats.last_error = type(exc).__name__
        if self.stats.errors >= self.max_errors and self._stop_event is not None:
            self._stop_event.set()


async def open_firstparty_tun_client_pump(
    *,
    session: SessionContext,
    tun: TunDevice,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    captured_at: int,
    require_tun_dataplane_probe: bool = False,
    tun_probe_mtu: int | None = None,
    tun_probe_fragment_payload_size: int = 512,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
    tun_read_timeout: float = 0.1,
    transport_read_timeout: float = 0.1,
    max_errors: int = 1,
    start: bool = True,
) -> FirstPartyTunClientPump:
    """Open a managed TUN bridge and optionally start bidirectional pumping."""
    managed = await open_firstparty_tun_client_bridge(
        session=session,
        tun=tun,
        candidates=candidates,
        captured_at=captured_at,
        require_tun_dataplane_probe=require_tun_dataplane_probe,
        tun_probe_mtu=tun_probe_mtu,
        tun_probe_fragment_payload_size=tun_probe_fragment_payload_size,
        fragmenter=fragmenter,
        reassembler=reassembler,
    )
    pump = FirstPartyTunClientPump(
        managed=managed,
        tun_read_timeout=tun_read_timeout,
        transport_read_timeout=transport_read_timeout,
        max_errors=max_errors,
    )
    if start:
        pump.start()
    return pump


async def open_firstparty_admission_tun_client_pump(
    *,
    hello: FirstPartyHandshakeHello,
    pqc_material: PqcSessionSecretMaterial,
    tun: TunDevice,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    captured_at: int,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    revocations: RevocationList | None = None,
    completed_at_provider: Callable[[FirstPartyHandshakeAccept], int] | None = None,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
    tun_read_timeout: float = 0.1,
    transport_read_timeout: float = 0.1,
    max_errors: int = 1,
    start: bool = True,
) -> FirstPartyTunClientPump:
    """Open an admitted managed TUN bridge and optionally start pumping."""
    managed = await open_firstparty_admission_tun_client_bridge(
        hello=hello,
        pqc_material=pqc_material,
        tun=tun,
        candidates=candidates,
        identity_authority=identity_authority,
        policy=policy,
        captured_at=captured_at,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        revocations=revocations,
        completed_at_provider=completed_at_provider,
        fragmenter=fragmenter,
        reassembler=reassembler,
    )
    pump = FirstPartyTunClientPump(
        managed=managed,
        tun_read_timeout=tun_read_timeout,
        transport_read_timeout=transport_read_timeout,
        max_errors=max_errors,
    )
    if start:
        pump.start()
    return pump


@dataclass
class FirstPartyThreadedTunClientResource:
    """Owns a client-side TUN pump running in a background event loop."""

    pump: FirstPartyTunClientPump
    loop: asyncio.AbstractEventLoop = field(repr=False)
    thread: threading.Thread = field(repr=False)
    close_timeout: float = field(default=5.0, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def running(self) -> bool:
        return not self._closed and self.thread.is_alive() and self.pump.running

    @property
    def managed(self) -> FirstPartyManagedTunClientBridge:
        return self.pump.managed

    @property
    def stats(self) -> TunPumpStats:
        return self.pump.stats

    def close(self) -> None:
        if self._closed:
            return
        close_error: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(self.pump.stop(), self.loop)
            future.result(timeout=self.close_timeout)
        except Exception as exc:
            close_error = exc
        finally:
            self._closed = True
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=self.close_timeout)
        if self.thread.is_alive():
            raise FirstPartyTunPumpError("threaded TUN client loop did not stop") from close_error
        if close_error is not None:
            raise FirstPartyTunPumpError("threaded TUN client close failed") from close_error


def open_threaded_firstparty_tun_client_pump(
    *,
    session: SessionContext,
    tun: TunDevice,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    captured_at: int,
    require_tun_dataplane_probe: bool = False,
    tun_probe_mtu: int | None = None,
    tun_probe_fragment_payload_size: int = 512,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
    tun_read_timeout: float = 0.1,
    transport_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedTunClientResource:
    """Start a client-side TUN pump and return a synchronous close handle."""
    return _start_threaded_tun_client_resource(
        starter=lambda: open_firstparty_tun_client_pump(
            session=session,
            tun=tun,
            candidates=candidates,
            captured_at=captured_at,
            require_tun_dataplane_probe=require_tun_dataplane_probe,
            tun_probe_mtu=tun_probe_mtu,
            tun_probe_fragment_payload_size=tun_probe_fragment_payload_size,
            fragmenter=fragmenter,
            reassembler=reassembler,
            tun_read_timeout=tun_read_timeout,
            transport_read_timeout=transport_read_timeout,
            max_errors=max_errors,
            start=True,
        ),
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )


def open_threaded_firstparty_admission_tun_client_pump(
    *,
    hello: "FirstPartyHandshakeHello",
    pqc_material: "PqcSessionSecretMaterial",
    tun: TunDevice,
    candidates: tuple["DataplaneEndpointCandidate", ...],
    identity_authority: "IdentityVerifier",
    policy: "ZeroTrustPolicy",
    captured_at: int,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    revocations: "RevocationList | None" = None,
    completed_at_provider: "Callable[[FirstPartyHandshakeAccept], int] | None" = None,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
    tun_read_timeout: float = 0.1,
    transport_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedTunClientResource:
    """Start an admitted client-side TUN pump behind a synchronous close handle."""
    return _start_threaded_tun_client_resource(
        starter=lambda: open_firstparty_admission_tun_client_pump(
            hello=hello,
            pqc_material=pqc_material,
            tun=tun,
            candidates=candidates,
            identity_authority=identity_authority,
            policy=policy,
            captured_at=captured_at,
            camouflage_profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
            fragmenter=fragmenter,
            reassembler=reassembler,
            tun_read_timeout=tun_read_timeout,
            transport_read_timeout=transport_read_timeout,
            max_errors=max_errors,
            start=True,
        ),
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )


def _start_threaded_tun_client_resource(
    *,
    starter: Callable[[], Awaitable[FirstPartyTunClientPump]],
    start_timeout: float,
    close_timeout: float,
) -> FirstPartyThreadedTunClientResource:
    if start_timeout <= 0 or close_timeout <= 0:
        raise FirstPartyTunPumpError("threaded TUN client timeouts must be positive")
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    thread = threading.Thread(
        target=_run_threaded_tun_client_loop,
        args=(loop, ready),
        name="x0vpn-tun-client",
        daemon=True,
    )
    thread.start()
    if not ready.wait(timeout=start_timeout):
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=close_timeout)
        raise FirstPartyTunPumpError("threaded TUN client loop did not start")
    future = asyncio.run_coroutine_threadsafe(starter(), loop)
    try:
        pump = future.result(timeout=start_timeout)
    except concurrent.futures.TimeoutError as exc:
        future.cancel()
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=close_timeout)
        raise FirstPartyTunPumpError("threaded TUN client startup timed out") from exc
    except Exception as exc:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=close_timeout)
        raise FirstPartyTunPumpError("threaded TUN client startup failed") from exc
    return FirstPartyThreadedTunClientResource(
        pump=pump,
        loop=loop,
        thread=thread,
        close_timeout=close_timeout,
    )


def _run_threaded_tun_client_loop(
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


@dataclass
class FirstPartyTunServerPump:
    """Continuously pumps packets from server TUN back to active clients."""

    tun: TunDevice
    server: FirstPartyServerTransport
    fragmenter: PacketFragmenter | None = None
    tun_read_timeout: float = 0.1
    max_errors: int = 1
    stats: TunBridgeStats = field(default_factory=TunBridgeStats)
    pump_stats: TunPumpStats = field(default_factory=TunPumpStats)
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.tun_read_timeout <= 0:
            raise ValueError("TUN server pump timeout must be positive")
        if self.max_errors < 1:
            raise ValueError("TUN server pump max_errors must be positive")

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> "FirstPartyTunServerPump":
        if self.running:
            raise FirstPartyTunPumpError("TUN server pump is already running")
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._pump_tun_to_transport())
        return self

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        self._stop_event = None

    async def send_one_from_tun(self, timeout: float = 1.0) -> None:
        packet = await self.tun.read_packet(timeout=timeout)
        if len(packet) > self.tun.mtu:
            self.stats.mtu_drops += 1
            raise TunPacketError("packet exceeds MTU")
        payloads = self.fragmenter.split(packet) if self.fragmenter else (packet,)
        result = self.server.send_data_fragments(payloads)
        if inspect.isawaitable(result):
            await result
        self.stats.packets_from_tun += 1
        self.stats.bytes_from_tun += len(packet)
        self.stats.tx_fragments += len(payloads)

    async def _pump_tun_to_transport(self) -> None:
        while not self._stopping:
            try:
                await self.send_one_from_tun(timeout=self.tun_read_timeout)
                self.pump_stats.tun_to_transport_cycles += 1
            except (TimeoutError, asyncio.TimeoutError):
                self.pump_stats.timeouts += 1
            except asyncio.CancelledError:
                self.pump_stats.cancellations += 1
                raise
            except Exception as exc:
                self._record_error(exc)

    @property
    def _stopping(self) -> bool:
        return self._stop_event is None or self._stop_event.is_set()

    def _record_error(self, exc: Exception) -> None:
        self.pump_stats.errors += 1
        self.pump_stats.last_error = type(exc).__name__
        if self.pump_stats.errors >= self.max_errors and self._stop_event is not None:
            self._stop_event.set()


@dataclass
class FirstPartyThreadedTunServerResource:
    """Owns a threaded dataplane service plus server-side TUN return pump."""

    dataplane: FirstPartyThreadedDataplaneServiceResource
    handler: FirstPartyTunServerHandler
    pump: FirstPartyTunServerPump
    return_transport: TunReturnTransport
    close_timeout: float = 5.0
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def running(self) -> bool:
        return not self._closed and self.dataplane.running and self.pump.running

    @property
    def service(self):
        return self.dataplane.service

    @property
    def bind_evidence(self):
        return self.dataplane.bind_evidence

    def close(self) -> None:
        if self._closed:
            return
        close_error: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.pump.stop(),
                self.dataplane.loop,
            )
            future.result(timeout=self.close_timeout)
        except Exception as exc:
            close_error = exc
        finally:
            self._closed = True
            try:
                self.dataplane.close()
            except Exception as exc:
                if close_error is None:
                    close_error = exc
        if close_error is not None:
            raise FirstPartyTunPumpError("threaded TUN server close failed") from close_error


def open_threaded_firstparty_tun_server(
    *,
    session: SessionContext,
    tun: TunDevice,
    bind: FirstPartyDataplaneBind | None = None,
    return_transport: TunReturnTransport = "tcp",
    response: Callable[[bytes], bytes | None] | None = None,
    fragmenter: PacketFragmenter | None = None,
    reassembler: PacketReassembler | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    rekey_processor: FirstPartyRekeyServerProcessor | None = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedTunServerResource:
    """Start a one-session dataplane listener with a server-side TUN return pump."""
    from .service import open_threaded_firstparty_dataplane_service

    handler = FirstPartyTunServerHandler(
        tun=tun,
        response=response,
        fragmenter=fragmenter,
        reassembler=reassembler,
    )
    dataplane = open_threaded_firstparty_dataplane_service(
        session=session,
        bind=bind,
        on_data=handler,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        rekey_processor=rekey_processor,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )
    try:
        pump = _start_threaded_tun_server_pump(
            dataplane=dataplane,
            tun=tun,
            return_transport=return_transport,
            fragmenter=fragmenter,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
            start_timeout=start_timeout,
        )
    except Exception:
        dataplane.close()
        raise
    return FirstPartyThreadedTunServerResource(
        dataplane=dataplane,
        handler=handler,
        pump=pump,
        return_transport=return_transport,
        close_timeout=close_timeout,
    )


def _start_threaded_tun_server_pump(
    *,
    dataplane: FirstPartyThreadedDataplaneServiceResource,
    tun: TunDevice,
    return_transport: TunReturnTransport,
    fragmenter: PacketFragmenter | None,
    tun_read_timeout: float,
    max_errors: int,
    start_timeout: float,
) -> FirstPartyTunServerPump:
    async def start_pump() -> FirstPartyTunServerPump:
        pump = FirstPartyTunServerPump(
            tun=tun,
            server=_server_transport_for(dataplane.service, return_transport),
            fragmenter=fragmenter,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
        )
        return pump.start()

    future = asyncio.run_coroutine_threadsafe(start_pump(), dataplane.loop)
    return future.result(timeout=start_timeout)


def _server_transport_for(
    service,
    return_transport: TunReturnTransport,
) -> FirstPartyServerTransport:
    if return_transport == "udp":
        server = service.udp_protocol
    elif return_transport == "tcp":
        server = service.tcp_protocol
    elif return_transport == "camouflage":
        server = service.camouflage_protocol
    else:
        raise FirstPartyTunPumpError("TUN server return transport is invalid")
    if server is None:
        raise FirstPartyTunPumpError("TUN server return transport is not running")
    return server


@dataclass
class FirstPartyMultiSessionTunServerPump:
    """Pump server TUN packets back to the active client for one session."""

    session: SessionContext | int
    tun: TunDevice
    server: FirstPartyMultiSessionServerTransport
    fragmenter: PacketFragmenter | None = None
    tun_read_timeout: float = 0.1
    max_errors: int = 1
    stats: TunBridgeStats = field(default_factory=TunBridgeStats)
    pump_stats: TunPumpStats = field(default_factory=TunPumpStats)
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.tun_read_timeout <= 0:
            raise ValueError("TUN server pump timeout must be positive")
        if self.max_errors < 1:
            raise ValueError("TUN server pump max_errors must be positive")
        if isinstance(self.session, int) and self.session < 0:
            raise ValueError("TUN server pump session id is invalid")

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> "FirstPartyMultiSessionTunServerPump":
        if self.running:
            raise FirstPartyTunPumpError("TUN server pump is already running")
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._pump_tun_to_transport())
        return self

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        self._stop_event = None

    async def send_one_from_tun(self, timeout: float = 1.0) -> None:
        packet = await self.tun.read_packet(timeout=timeout)
        if len(packet) > self.tun.mtu:
            self.stats.mtu_drops += 1
            raise TunPacketError("packet exceeds MTU")
        payloads = self.fragmenter.split(packet) if self.fragmenter else (packet,)
        result = self.server.send_data_fragments(payloads, session=self.session)
        if inspect.isawaitable(result):
            await result
        self.stats.packets_from_tun += 1
        self.stats.bytes_from_tun += len(packet)
        self.stats.tx_fragments += len(payloads)

    async def _pump_tun_to_transport(self) -> None:
        while not self._stopping:
            try:
                await self.send_one_from_tun(timeout=self.tun_read_timeout)
                self.pump_stats.tun_to_transport_cycles += 1
            except (TimeoutError, asyncio.TimeoutError):
                self.pump_stats.timeouts += 1
            except asyncio.CancelledError:
                self.pump_stats.cancellations += 1
                raise
            except Exception as exc:
                self._record_error(exc)

    @property
    def _stopping(self) -> bool:
        return self._stop_event is None or self._stop_event.is_set()

    def _record_error(self, exc: Exception) -> None:
        self.pump_stats.errors += 1
        self.pump_stats.last_error = type(exc).__name__
        if self.pump_stats.errors >= self.max_errors and self._stop_event is not None:
            self._stop_event.set()


@dataclass
class FirstPartyAdmissionTunServerReturnPump:
    """Pump server TUN packets back to one admitted on-demand session."""

    session: SessionContext | int
    handler: "FirstPartyAdmissionTunServerHandler"
    server: FirstPartyMultiSessionServerTransport
    fragmenter: PacketFragmenter | None = None
    tun_read_timeout: float = 0.1
    max_errors: int = 1
    stats: TunBridgeStats = field(default_factory=TunBridgeStats)
    pump_stats: TunPumpStats = field(default_factory=TunPumpStats)
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.tun_read_timeout <= 0:
            raise ValueError("TUN server pump timeout must be positive")
        if self.max_errors < 1:
            raise ValueError("TUN server pump max_errors must be positive")
        if isinstance(self.session, int) and self.session < 0:
            raise ValueError("TUN server pump session id is invalid")

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> "FirstPartyAdmissionTunServerReturnPump":
        if self.running:
            raise FirstPartyTunPumpError("TUN server pump is already running")
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._pump_tun_to_transport())
        return self

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        self._stop_event = None

    async def send_one_from_tun(self, timeout: float = 1.0) -> None:
        handler = self.handler.handler_for(self.session)
        packet = await handler.tun.read_packet(timeout=timeout)
        if len(packet) > handler.tun.mtu:
            self.stats.mtu_drops += 1
            raise TunPacketError("packet exceeds MTU")
        payloads = self.fragmenter.split(packet) if self.fragmenter else (packet,)
        result = self.server.send_data_fragments(payloads, session=self.session)
        if inspect.isawaitable(result):
            await result
        self.stats.packets_from_tun += 1
        self.stats.bytes_from_tun += len(packet)
        self.stats.tx_fragments += len(payloads)

    async def _pump_tun_to_transport(self) -> None:
        while not self._stopping:
            try:
                await self.send_one_from_tun(timeout=self.tun_read_timeout)
                self.pump_stats.tun_to_transport_cycles += 1
            except (TimeoutError, asyncio.TimeoutError):
                self.pump_stats.timeouts += 1
            except asyncio.CancelledError:
                self.pump_stats.cancellations += 1
                raise
            except Exception as exc:
                self._record_error(exc)

    @property
    def _stopping(self) -> bool:
        return self._stop_event is None or self._stop_event.is_set()

    def _record_error(self, exc: Exception) -> None:
        self.pump_stats.errors += 1
        self.pump_stats.last_error = type(exc).__name__
        if self.pump_stats.errors >= self.max_errors and self._stop_event is not None:
            self._stop_event.set()


@dataclass
class FirstPartyThreadedMultiSessionTunServerResource:
    """Owns a threaded multi-session dataplane plus per-session TUN return pumps."""

    dataplane: FirstPartyThreadedDataplaneServiceResource
    handler: FirstPartyMultiSessionTunServerHandler
    pumps: tuple[FirstPartyMultiSessionTunServerPump, ...]
    return_transport: TunReturnTransport
    close_timeout: float = 5.0
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def running(self) -> bool:
        return (
            not self._closed
            and self.dataplane.running
            and bool(self.pumps)
            and all(pump.running for pump in self.pumps)
        )

    @property
    def service(self):
        return self.dataplane.service

    @property
    def bind_evidence(self):
        return self.dataplane.bind_evidence

    def pump_for(self, session: SessionContext | int) -> FirstPartyMultiSessionTunServerPump:
        session_id = session if isinstance(session, int) else session.session_id
        for pump in self.pumps:
            pump_session_id = (
                pump.session if isinstance(pump.session, int) else pump.session.session_id
            )
            if pump_session_id == session_id:
                return pump
        raise FirstPartyTunPumpError("session is not admitted on this TUN pump")

    def close(self) -> None:
        if self._closed:
            return
        close_error: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                _stop_multi_session_tun_server_pumps(self.pumps),
                self.dataplane.loop,
            )
            future.result(timeout=self.close_timeout)
        except Exception as exc:
            close_error = exc
        finally:
            self._closed = True
            try:
                self.dataplane.close()
            except Exception as exc:
                if close_error is None:
                    close_error = exc
        if close_error is not None:
            raise FirstPartyTunPumpError(
                "threaded multi-session TUN server close failed"
            ) from close_error


def open_threaded_firstparty_multi_session_tun_server(
    *,
    sessions: tuple[SessionContext, ...],
    tuns: Mapping[int, TunDevice],
    bind: FirstPartyDataplaneBind | None = None,
    return_transport: TunReturnTransport = "tcp",
    responses: Mapping[int, Callable[[bytes], bytes | None]] | None = None,
    fragmenter: PacketFragmenter | None = None,
    reassemblers: Mapping[int, PacketReassembler] | None = None,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedMultiSessionTunServerResource:
    """Start multi-session dataplane listeners with per-session server TUN pumps."""
    from .service import open_threaded_firstparty_multi_session_dataplane_service

    if not sessions:
        raise FirstPartyTunPumpError("multi-session TUN server requires sessions")
    handlers: dict[int, FirstPartyTunServerHandler] = {}
    responses = responses or {}
    reassemblers = reassemblers or {}
    for session in sessions:
        tun = tuns.get(session.session_id)
        if tun is None:
            raise FirstPartyTunPumpError("multi-session TUN server is missing TUN")
        handlers[session.session_id] = FirstPartyTunServerHandler(
            tun=tun,
            response=responses.get(session.session_id),
            fragmenter=fragmenter,
            reassembler=reassemblers.get(session.session_id),
        )
    handler = FirstPartyMultiSessionTunServerHandler(handlers=handlers)
    dataplane = open_threaded_firstparty_multi_session_dataplane_service(
        sessions=sessions,
        bind=bind,
        on_session_data=handler,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )
    try:
        pumps = _start_threaded_multi_session_tun_server_pumps(
            dataplane=dataplane,
            sessions=sessions,
            tuns=tuns,
            return_transport=return_transport,
            fragmenter=fragmenter,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
            start_timeout=start_timeout,
        )
    except Exception:
        dataplane.close()
        raise
    return FirstPartyThreadedMultiSessionTunServerResource(
        dataplane=dataplane,
        handler=handler,
        pumps=pumps,
        return_transport=return_transport,
        close_timeout=close_timeout,
    )


def _start_threaded_multi_session_tun_server_pumps(
    *,
    dataplane: FirstPartyThreadedDataplaneServiceResource,
    sessions: tuple[SessionContext, ...],
    tuns: Mapping[int, TunDevice],
    return_transport: TunReturnTransport,
    fragmenter: PacketFragmenter | None,
    tun_read_timeout: float,
    max_errors: int,
    start_timeout: float,
) -> tuple[FirstPartyMultiSessionTunServerPump, ...]:
    async def start_pumps() -> tuple[FirstPartyMultiSessionTunServerPump, ...]:
        server = _multi_session_server_transport_for(dataplane.service, return_transport)
        pumps = tuple(
            FirstPartyMultiSessionTunServerPump(
                session=session,
                tun=tuns[session.session_id],
                server=server,
                fragmenter=fragmenter,
                tun_read_timeout=tun_read_timeout,
                max_errors=max_errors,
            ).start()
            for session in sessions
        )
        return pumps

    future = asyncio.run_coroutine_threadsafe(start_pumps(), dataplane.loop)
    return future.result(timeout=start_timeout)


async def _stop_multi_session_tun_server_pumps(
    pumps: tuple[FirstPartyMultiSessionTunServerPump, ...],
) -> None:
    await asyncio.gather(*(pump.stop() for pump in pumps), return_exceptions=False)


def _multi_session_server_transport_for(
    service,
    return_transport: TunReturnTransport,
) -> FirstPartyMultiSessionServerTransport:
    if return_transport == "udp":
        server = service.udp_protocol
    elif return_transport == "tcp":
        server = service.tcp_protocol
    elif return_transport == "camouflage":
        server = service.camouflage_protocol
    else:
        raise FirstPartyTunPumpError("multi-session TUN return transport is invalid")
    if server is None:
        raise FirstPartyTunPumpError(
            "multi-session TUN return transport is not running"
        )
    return server


@dataclass
class FirstPartyTunServerHandler:
    """Server-side DATA handler that writes inbound packets to a TUN device."""

    tun: TunDevice
    response: Callable[[bytes], bytes | None] | None = None
    fragmenter: PacketFragmenter | None = None
    reassembler: PacketReassembler | None = None
    stats: TunBridgeStats = field(default_factory=TunBridgeStats)

    def __call__(
        self,
        packet: bytes,
        _addr: tuple[str, int],
    ) -> bytes | tuple[bytes, ...] | None:
        if self.reassembler is not None:
            try:
                self.stats.rx_fragments += 1
                reassembled = self.reassembler.accept(packet)
            except FragmentError as exc:
                self.stats.fragment_drops += 1
                raise TunPacketError(str(exc)) from exc
            if reassembled is None:
                return None
            packet = reassembled
        if len(packet) > self.tun.mtu:
            self.stats.mtu_drops += 1
            raise TunPacketError("packet exceeds MTU")
        self.tun.write_packet_nowait(packet)
        self.stats.packets_to_tun += 1
        self.stats.bytes_to_tun += len(packet)
        if self.response is None:
            return None
        response = self.response(packet)
        if response is not None:
            if len(response) > self.tun.mtu:
                self.stats.mtu_drops += 1
                raise TunPacketError("response exceeds MTU")
            self.stats.packets_from_tun += 1
            self.stats.bytes_from_tun += len(response)
            if self.fragmenter is not None:
                payloads = self.fragmenter.split(response)
                self.stats.tx_fragments += len(payloads)
                return payloads
        return response


AdmissionTunFactory = Callable[[SessionContext], TunDevice]
AdmissionTunResponseFactory = Callable[
    [SessionContext],
    Callable[[bytes], bytes | None] | None,
]
AdmissionTunFragmenterFactory = Callable[[SessionContext], PacketFragmenter | None]
AdmissionTunReassemblerFactory = Callable[[SessionContext], PacketReassembler | None]
AdmissionTunHandlerCreatedCallback = Callable[
    [SessionContext, FirstPartyTunServerHandler],
    None,
]


@dataclass
class FirstPartyAdmissionTunServerHandler:
    """Create server-side TUN handlers lazily for newly admitted sessions."""

    tun_factory: AdmissionTunFactory
    response_factory: AdmissionTunResponseFactory | None = None
    fragmenter_factory: AdmissionTunFragmenterFactory | None = None
    reassembler_factory: AdmissionTunReassemblerFactory | None = None
    on_handler_created: AdmissionTunHandlerCreatedCallback | None = None
    handlers: dict[int, FirstPartyTunServerHandler] = field(
        default_factory=dict,
        init=False,
    )
    route_drops: int = 0

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.handlers))

    def handler_for(self, session: SessionContext | int) -> FirstPartyTunServerHandler:
        session_id = session if isinstance(session, int) else session.session_id
        handler = self.handlers.get(session_id)
        if handler is not None:
            return handler
        if isinstance(session, int):
            self.route_drops += 1
            raise TunPacketError("session is not admitted on this TUN handler")
        handler = self._create_handler(session)
        self.handlers[session_id] = handler
        if self.on_handler_created is not None:
            self.on_handler_created(session, handler)
        return handler

    def __call__(
        self,
        packet: bytes,
        addr: tuple[str, int],
        session: SessionContext,
    ) -> bytes | tuple[bytes, ...] | None:
        return self.handler_for(session)(packet, addr)

    def _create_handler(self, session: SessionContext) -> FirstPartyTunServerHandler:
        tun = self.tun_factory(session)
        response = (
            self.response_factory(session)
            if self.response_factory is not None
            else None
        )
        fragmenter = (
            self.fragmenter_factory(session)
            if self.fragmenter_factory is not None
            else None
        )
        reassembler = (
            self.reassembler_factory(session)
            if self.reassembler_factory is not None
            else None
        )
        return FirstPartyTunServerHandler(
            tun=tun,
            response=response,
            fragmenter=fragmenter,
            reassembler=reassembler,
        )


@dataclass
class FirstPartyAdmissionDataplaneReturnRouter:
    """Send admission TUN return packets over the session's active transport."""

    service: "FirstPartyAdmissionDataplaneService"
    transports: tuple[TunReturnTransport, ...] = ("udp", "tcp", "camouflage")
    route_drops: int = 0
    last_transport_by_session: dict[int, TunReturnTransport] = field(
        default_factory=dict,
        init=False,
    )

    def __post_init__(self) -> None:
        if not self.transports:
            raise FirstPartyTunPumpError("admission TUN return router needs transport")
        valid_transports = {"udp", "tcp", "camouflage"}
        for transport in self.transports:
            if transport not in valid_transports:
                raise FirstPartyTunPumpError(
                    "admission TUN return router transport is invalid"
                )

    async def send_data_fragments(
        self,
        payloads: Sequence[bytes],
        *,
        session: SessionContext | int,
    ) -> None:
        session_id = session if isinstance(session, int) else session.session_id
        for transport in self._ordered_transports(session_id):
            server = self._server_for(transport)
            if server is None:
                continue
            try:
                result = server.send_data_fragments(payloads, session=session)
                if inspect.isawaitable(result):
                    await result
            except (RuntimeError, SessionRouteDrop):
                continue
            self.last_transport_by_session[session_id] = transport
            return
        self.route_drops += 1
        raise FirstPartyTunPumpError(
            "admission TUN return route has no active transport"
        )

    def _ordered_transports(self, session_id: int) -> tuple[TunReturnTransport, ...]:
        ordered: list[TunReturnTransport] = []
        active_transport = self.service.active_transport_by_session.get(session_id)
        last_transport = self.last_transport_by_session.get(session_id)
        for transport in (active_transport, last_transport):
            if transport in self.transports and transport not in ordered:
                ordered.append(transport)
        for transport in self.transports:
            if transport not in ordered:
                ordered.append(transport)
        return tuple(ordered)

    def _server_for(
        self,
        transport: TunReturnTransport,
    ) -> FirstPartyMultiSessionServerTransport | None:
        if transport == "udp":
            return self.service.udp_protocol
        if transport == "tcp":
            return self.service.tcp_protocol
        if transport == "camouflage":
            return self.service.camouflage_protocol
        raise FirstPartyTunPumpError("admission TUN return transport is invalid")


@dataclass
class FirstPartySharedTunAdmissionReturnPump:
    """Route one shared server TUN return stream to sessions by destination IP."""

    tun: TunDevice
    server: FirstPartyMultiSessionServerTransport
    session_by_destination: Mapping[str, SessionContext | int]
    fragmenter: PacketFragmenter | None = None
    tun_read_timeout: float = 0.1
    max_errors: int = 1
    stats: TunBridgeStats = field(default_factory=TunBridgeStats)
    pump_stats: TunPumpStats = field(default_factory=TunPumpStats)
    route_drops: int = 0
    last_destination: str | None = None
    _task: asyncio.Task[None] | None = field(default=None, init=False)
    _stop_event: asyncio.Event | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.tun_read_timeout <= 0:
            raise ValueError("shared TUN return pump timeout must be positive")
        if self.max_errors < 1:
            raise ValueError("shared TUN return pump max_errors must be positive")
        for destination, session in self.session_by_destination.items():
            ipaddress.ip_address(destination)
            if isinstance(session, int) and session < 0:
                raise ValueError("shared TUN return pump session id is invalid")

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> "FirstPartySharedTunAdmissionReturnPump":
        if self.running:
            raise FirstPartyTunPumpError("shared TUN return pump is already running")
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._pump_tun_to_transport())
        return self

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
        self._task = None
        self._stop_event = None

    async def send_one_from_tun(self, timeout: float = 1.0) -> None:
        packet = await self.tun.read_packet(timeout=timeout)
        if len(packet) > self.tun.mtu:
            self.stats.mtu_drops += 1
            raise TunPacketError("packet exceeds MTU")
        destination = _packet_destination_ip(packet)
        self.last_destination = destination
        session = self.session_by_destination.get(destination)
        if session is None:
            self.route_drops += 1
            raise FirstPartyTunPumpError(
                "shared TUN return route has no destination session"
            )
        payloads = self.fragmenter.split(packet) if self.fragmenter else (packet,)
        result = self.server.send_data_fragments(payloads, session=session)
        if inspect.isawaitable(result):
            await result
        self.stats.packets_from_tun += 1
        self.stats.bytes_from_tun += len(packet)
        self.stats.tx_fragments += len(payloads)

    async def _pump_tun_to_transport(self) -> None:
        while not self._stopping:
            try:
                await self.send_one_from_tun(timeout=self.tun_read_timeout)
                self.pump_stats.tun_to_transport_cycles += 1
            except (TimeoutError, asyncio.TimeoutError):
                self.pump_stats.timeouts += 1
            except asyncio.CancelledError:
                self.pump_stats.cancellations += 1
                raise
            except FirstPartyTunPumpError as exc:
                if "no destination session" not in str(exc):
                    self._record_error(exc)
            except Exception as exc:
                self._record_error(exc)

    @property
    def _stopping(self) -> bool:
        return self._stop_event is None or self._stop_event.is_set()

    def _record_error(self, exc: Exception) -> None:
        self.pump_stats.errors += 1
        self.pump_stats.last_error = type(exc).__name__
        if self.pump_stats.errors >= self.max_errors and self._stop_event is not None:
            self._stop_event.set()


@dataclass
class FirstPartyAdmissionTunServerReturnPumpManager:
    """Starts per-session server TUN return pumps for admitted sessions."""

    handler: FirstPartyAdmissionTunServerHandler
    server: FirstPartyMultiSessionServerTransport
    fragmenter: PacketFragmenter | None = None
    tun_read_timeout: float = 0.1
    max_errors: int = 1
    auto_install: bool = True
    pumps: dict[int, FirstPartyAdmissionTunServerReturnPump] = field(
        default_factory=dict,
        init=False,
    )
    _previous_on_handler_created: AdmissionTunHandlerCreatedCallback | None = field(
        default=None,
        init=False,
        repr=False,
    )
    _installed: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.tun_read_timeout <= 0:
            raise ValueError("TUN server pump manager timeout must be positive")
        if self.max_errors < 1:
            raise ValueError("TUN server pump manager max_errors must be positive")
        if self.auto_install:
            self.install()

    @property
    def running(self) -> bool:
        return bool(self.pumps) and all(pump.running for pump in self.pumps.values())

    def install(self) -> "FirstPartyAdmissionTunServerReturnPumpManager":
        if self._installed:
            return self
        self._previous_on_handler_created = self.handler.on_handler_created
        self.handler.on_handler_created = self.on_handler_created
        self._installed = True
        return self

    def pump_for(
        self,
        session: SessionContext | int,
    ) -> FirstPartyAdmissionTunServerReturnPump:
        session_id = session if isinstance(session, int) else session.session_id
        if session_id < 0:
            raise FirstPartyTunPumpError("admission TUN return pump session is invalid")
        pump = self.pumps.get(session_id)
        if pump is not None:
            return pump
        if isinstance(session, int):
            if session not in self.handler.handlers:
                raise FirstPartyTunPumpError(
                    "session is not admitted on this TUN return pump manager"
                )
        else:
            self.handler.handler_for(session)
        pump = self.pumps.get(session_id)
        if pump is not None:
            return pump
        pump = FirstPartyAdmissionTunServerReturnPump(
            session=session,
            handler=self.handler,
            server=self.server,
            fragmenter=self.fragmenter,
            tun_read_timeout=self.tun_read_timeout,
            max_errors=self.max_errors,
        ).start()
        self.pumps[session_id] = pump
        return pump

    def ensure_for_admitted_sessions(
        self,
    ) -> tuple[FirstPartyAdmissionTunServerReturnPump, ...]:
        return tuple(
            self.pump_for(session_id)
            for session_id in self.handler.admitted_session_ids
        )

    def on_handler_created(
        self,
        session: SessionContext,
        handler: FirstPartyTunServerHandler,
    ) -> None:
        self.pump_for(session)
        if self._previous_on_handler_created is not None:
            self._previous_on_handler_created(session, handler)

    async def stop(self) -> None:
        await asyncio.gather(
            *(pump.stop() for pump in self.pumps.values()),
            return_exceptions=False,
        )


@dataclass
class FirstPartyThreadedAdmissionTunServerResource:
    """Owns a threaded admission dataplane plus dynamic TUN return pumps."""

    dataplane: "FirstPartyThreadedDataplaneServiceResource"
    handler: FirstPartyAdmissionTunServerHandler
    return_router: FirstPartyAdmissionDataplaneReturnRouter
    pump_manager: FirstPartyAdmissionTunServerReturnPumpManager
    close_timeout: float = 5.0
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def running(self) -> bool:
        return not self._closed and self.dataplane.running

    @property
    def service(self):
        return self.dataplane.service

    @property
    def bind_evidence(self):
        return self.dataplane.bind_evidence

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return self.service.admitted_session_ids

    def pump_for(
        self,
        session: SessionContext | int,
    ) -> FirstPartyAdmissionTunServerReturnPump:
        session_id = session if isinstance(session, int) else session.session_id
        pump = self.pump_manager.pumps.get(session_id)
        if pump is None:
            raise FirstPartyTunPumpError("session has no admission TUN return pump")
        return pump

    def close(self) -> None:
        if self._closed:
            return
        close_error: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.pump_manager.stop(),
                self.dataplane.loop,
            )
            future.result(timeout=self.close_timeout)
        except Exception as exc:
            close_error = exc
        finally:
            self._closed = True
            try:
                self.dataplane.close()
            except Exception as exc:
                if close_error is None:
                    close_error = exc
        if close_error is not None:
            raise FirstPartyTunPumpError(
                "threaded admission TUN server close failed"
            ) from close_error


@dataclass
class FirstPartyThreadedSharedTunAdmissionServerResource:
    """Owns admission dataplane plus one shared server TUN return demux pump."""

    dataplane: "FirstPartyThreadedDataplaneServiceResource"
    handler: FirstPartyAdmissionTunServerHandler
    return_router: FirstPartyAdmissionDataplaneReturnRouter
    return_pump: FirstPartySharedTunAdmissionReturnPump
    session_by_destination: dict[str, SessionContext | int]
    destination_by_identity_hash: Mapping[str, str]
    close_timeout: float = 5.0
    _lease_drop_counter: dict[str, int] = field(default_factory=dict, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def running(self) -> bool:
        return (
            not self._closed
            and self.dataplane.running
            and self.return_pump.running
        )

    @property
    def service(self):
        return self.dataplane.service

    @property
    def bind_evidence(self):
        return self.dataplane.bind_evidence

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return self.service.admitted_session_ids

    @property
    def lease_drops(self) -> int:
        return int(self._lease_drop_counter.get("count", 0))

    def close(self) -> None:
        if self._closed:
            return
        close_error: Exception | None = None
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.return_pump.stop(),
                self.dataplane.loop,
            )
            future.result(timeout=self.close_timeout)
        except Exception as exc:
            close_error = exc
        finally:
            self._closed = True
            try:
                self.dataplane.close()
            except Exception as exc:
                if close_error is None:
                    close_error = exc
        if close_error is not None:
            raise FirstPartyTunPumpError(
                "threaded shared TUN admission server close failed"
            ) from close_error


def open_threaded_firstparty_admission_tun_server(
    *,
    registry: "FirstPartySessionAdmissionRegistry",
    tun_factory: AdmissionTunFactory,
    bind: "FirstPartyDataplaneBind | None" = None,
    return_transports: tuple[TunReturnTransport, ...] = (
        "udp",
        "tcp",
        "camouflage",
    ),
    response_factory: AdmissionTunResponseFactory | None = None,
    on_session_ping: "SessionPingHandler | None" = None,
    fragmenter_factory: AdmissionTunFragmenterFactory | None = None,
    reassembler_factory: AdmissionTunReassemblerFactory | None = None,
    fragmenter: PacketFragmenter | None = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedAdmissionTunServerResource:
    """Start admission listeners with dynamic per-session server TUN pumps."""
    from .service import open_threaded_firstparty_admission_dataplane_service

    handler = FirstPartyAdmissionTunServerHandler(
        tun_factory=tun_factory,
        response_factory=response_factory,
        fragmenter_factory=fragmenter_factory,
        reassembler_factory=reassembler_factory,
    )
    dataplane = open_threaded_firstparty_admission_dataplane_service(
        registry=registry,
        bind=bind,
        on_session_data=handler,
        on_session_ping=on_session_ping,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )
    try:
        return_router = FirstPartyAdmissionDataplaneReturnRouter(
            service=dataplane.service,
            transports=return_transports,
        )
        pump_manager = FirstPartyAdmissionTunServerReturnPumpManager(
            handler=handler,
            server=return_router,
            fragmenter=fragmenter,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
        )
    except Exception:
        dataplane.close()
        raise
    return FirstPartyThreadedAdmissionTunServerResource(
        dataplane=dataplane,
        handler=handler,
        return_router=return_router,
        pump_manager=pump_manager,
        close_timeout=close_timeout,
    )


def open_threaded_firstparty_shared_tun_admission_server(
    *,
    registry: "FirstPartySessionAdmissionRegistry",
    tun: TunDevice,
    destination_by_identity_hash: Mapping[str, str],
    bind: "FirstPartyDataplaneBind | None" = None,
    return_transports: tuple[TunReturnTransport, ...] = (
        "udp",
        "tcp",
        "camouflage",
    ),
    response_factory: AdmissionTunResponseFactory | None = None,
    on_session_ping: "SessionPingHandler | None" = None,
    fragmenter_factory: AdmissionTunFragmenterFactory | None = None,
    reassembler_factory: AdmissionTunReassemblerFactory | None = None,
    fragmenter: PacketFragmenter | None = None,
    camouflage_profile: "CamouflageProfile | None" = None,
    camouflage_policy: "CamouflagePolicy | None" = None,
    tun_read_timeout: float = 0.1,
    max_errors: int = 1,
    start_timeout: float = 5.0,
    close_timeout: float = 5.0,
) -> FirstPartyThreadedSharedTunAdmissionServerResource:
    """Start admission listeners with one shared TUN return demux pump."""
    from .service import open_threaded_firstparty_admission_dataplane_service

    for identity_hash, destination in destination_by_identity_hash.items():
        if not identity_hash.strip():
            raise FirstPartyTunPumpError("shared TUN lease identity hash is required")
        ipaddress.ip_address(destination)

    session_by_destination: dict[str, SessionContext | int] = {}
    lease_drop_counter = {"count": 0}

    def on_handler_created(
        session: SessionContext,
        _handler: FirstPartyTunServerHandler,
    ) -> None:
        identity_hash = session.client_decision.identity_hash.hex()
        destination = destination_by_identity_hash.get(identity_hash)
        if destination is None:
            lease_drop_counter["count"] += 1
            return
        session_by_destination[str(ipaddress.ip_address(destination))] = session

    handler = FirstPartyAdmissionTunServerHandler(
        tun_factory=lambda _session: tun,
        response_factory=response_factory,
        fragmenter_factory=fragmenter_factory,
        reassembler_factory=reassembler_factory,
        on_handler_created=on_handler_created,
    )
    dataplane = open_threaded_firstparty_admission_dataplane_service(
        registry=registry,
        bind=bind,
        on_session_data=handler,
        on_session_ping=on_session_ping,
        camouflage_profile=camouflage_profile,
        camouflage_policy=camouflage_policy,
        start_timeout=start_timeout,
        close_timeout=close_timeout,
    )
    try:
        return_router = FirstPartyAdmissionDataplaneReturnRouter(
            service=dataplane.service,
            transports=return_transports,
        )
        return_pump = FirstPartySharedTunAdmissionReturnPump(
            tun=tun,
            server=return_router,
            session_by_destination=session_by_destination,
            fragmenter=fragmenter,
            tun_read_timeout=tun_read_timeout,
            max_errors=max_errors,
        )
        future = asyncio.run_coroutine_threadsafe(
            _start_shared_tun_return_pump(return_pump),
            dataplane.loop,
        )
        future.result(timeout=start_timeout)
    except Exception:
        dataplane.close()
        raise
    resource = FirstPartyThreadedSharedTunAdmissionServerResource(
        dataplane=dataplane,
        handler=handler,
        return_router=return_router,
        return_pump=return_pump,
        session_by_destination=session_by_destination,
        destination_by_identity_hash=destination_by_identity_hash,
        close_timeout=close_timeout,
        _lease_drop_counter=lease_drop_counter,
    )
    return resource


async def _start_shared_tun_return_pump(
    pump: FirstPartySharedTunAdmissionReturnPump,
) -> FirstPartySharedTunAdmissionReturnPump:
    pump.start()
    return pump


@dataclass
class FirstPartyMultiSessionTunServerHandler:
    """Route server-side DATA packets to the TUN handler for the selected session."""

    handlers: Mapping[int, FirstPartyTunServerHandler]
    route_drops: int = 0

    def __post_init__(self) -> None:
        if not self.handlers:
            raise ValueError("multi-session TUN server handler requires handlers")
        for session_id, handler in self.handlers.items():
            if session_id < 0:
                raise ValueError("multi-session TUN handler session id is invalid")
            if not callable(handler):
                raise ValueError("multi-session TUN handler route is not callable")

    @property
    def admitted_session_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.handlers))

    def handler_for(self, session: SessionContext | int) -> FirstPartyTunServerHandler:
        session_id = session if isinstance(session, int) else session.session_id
        handler = self.handlers.get(session_id)
        if handler is None:
            self.route_drops += 1
            raise TunPacketError("session is not admitted on this TUN handler")
        return handler

    def __call__(
        self,
        packet: bytes,
        addr: tuple[str, int],
        session: SessionContext,
    ) -> bytes | tuple[bytes, ...] | None:
        return self.handler_for(session)(packet, addr)
