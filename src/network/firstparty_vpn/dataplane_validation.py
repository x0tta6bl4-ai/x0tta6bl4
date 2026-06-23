"""Privacy-safe external dataplane validation evidence for first-party VPN."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import time
from typing import Awaitable, Callable, Literal

from .camouflage import open_camouflage_client, open_camouflage_server
from .fragmentation import PacketFragmenter, PacketReassembler
from .ops import assert_privacy_safe, hash_identifier
from .protocol import FrameType, MAX_PAYLOAD_BYTES
from .runtime import open_udp_client, open_udp_server
from .session import SessionContext
from .stream import open_tcp_client, open_tcp_server
from .tun import (
    FirstPartyTunClientBridge,
    FirstPartyTunServerHandler,
    MemoryTunDevice,
)

DataplaneTransport = Literal["udp", "tcp", "camouflage"]
DataplaneProbeRunner = Callable[["DataplaneProbeSpec"], Awaitable["DataplaneProbeResult"]]
TunDataplaneProbeRunner = Callable[
    ["DataplaneProbeSpec"],
    Awaitable["TunDataplaneProbeResult"],
]
DataplaneEndpointResolver = Callable[["DataplaneProbeSpec"], tuple[str, int]]


class DataplaneValidationError(ValueError):
    """Raised when dataplane validation evidence is invalid."""


@dataclass(frozen=True)
class DataplaneProbeSpec:
    """One required dataplane probe without storing raw endpoint details."""

    probe_id: str
    path_label: str
    transport: DataplaneTransport
    remote_ref: str
    payload_size: int = 64
    timeout_seconds: float = 1.0
    required: bool = True

    def __post_init__(self) -> None:
        if not self.probe_id.strip():
            raise DataplaneValidationError("dataplane probe id is required")
        if not self.path_label.strip():
            raise DataplaneValidationError("dataplane path label is required")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise DataplaneValidationError(
                "dataplane transport must be udp, tcp, or camouflage"
            )
        if not self.remote_ref.strip():
            raise DataplaneValidationError("dataplane remote reference is required")
        if self.payload_size < 1:
            raise DataplaneValidationError("dataplane payload size must be positive")
        if self.timeout_seconds <= 0:
            raise DataplaneValidationError("dataplane timeout must be positive")

    @property
    def remote_hash(self) -> str:
        return hash_identifier(self.remote_ref, namespace="dataplane-remote")

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "path_label": self.path_label,
            "payload_size": self.payload_size,
            "probe_id": self.probe_id,
            "remote_hash": self.remote_hash,
            "required": self.required,
            "timeout_millis": int(self.timeout_seconds * 1000),
            "transport": self.transport,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class DataplaneProbeResult:
    """Payload-free result for one dataplane probe."""

    probe_id: str
    path_label: str
    transport: DataplaneTransport
    remote_hash: str
    success: bool
    latency_millis: int | None = None
    rx_frames: int = 0
    tx_frames: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.probe_id.strip():
            raise DataplaneValidationError("dataplane result probe id is required")
        if not self.path_label.strip():
            raise DataplaneValidationError("dataplane result path label is required")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise DataplaneValidationError(
                "dataplane result transport must be udp, tcp, or camouflage"
            )
        if not self.remote_hash.strip():
            raise DataplaneValidationError("dataplane result remote hash is required")
        if self.success and self.failure_reason is not None:
            raise DataplaneValidationError("successful dataplane result has failure reason")
        if not self.success and not (self.failure_reason or "").strip():
            raise DataplaneValidationError("failed dataplane result requires reason")
        if self.latency_millis is not None and self.latency_millis < 0:
            raise DataplaneValidationError("dataplane latency cannot be negative")
        for value in (self.rx_frames, self.tx_frames, self.rx_bytes, self.tx_bytes):
            if value < 0:
                raise DataplaneValidationError("dataplane counters cannot be negative")

    @classmethod
    def success_result(
        cls,
        spec: DataplaneProbeSpec,
        *,
        latency_millis: int,
        rx_frames: int = 1,
        tx_frames: int = 1,
        rx_bytes: int = 0,
        tx_bytes: int = 0,
    ) -> "DataplaneProbeResult":
        return cls(
            probe_id=spec.probe_id,
            path_label=spec.path_label,
            transport=spec.transport,
            remote_hash=spec.remote_hash,
            success=True,
            latency_millis=latency_millis,
            rx_frames=rx_frames,
            tx_frames=tx_frames,
            rx_bytes=rx_bytes,
            tx_bytes=tx_bytes,
        )

    @classmethod
    def failure_result(
        cls,
        spec: DataplaneProbeSpec,
        *,
        reason: str,
    ) -> "DataplaneProbeResult":
        return cls(
            probe_id=spec.probe_id,
            path_label=spec.path_label,
            transport=spec.transport,
            remote_hash=spec.remote_hash,
            success=False,
            failure_reason=reason,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "latency_millis": self.latency_millis,
            "path_label": self.path_label,
            "probe_id": self.probe_id,
            "remote_hash": self.remote_hash,
            "rx_bytes": self.rx_bytes,
            "rx_frames": self.rx_frames,
            "success": self.success,
            "transport": self.transport,
            "tx_bytes": self.tx_bytes,
            "tx_frames": self.tx_frames,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class DataplaneValidationPlan:
    """Required external dataplane paths before production rollout."""

    probes: tuple[DataplaneProbeSpec, ...]
    required_path_labels: frozenset[str]
    min_successful_probes: int

    def __post_init__(self) -> None:
        if not self.probes:
            raise DataplaneValidationError("dataplane validation probes are required")
        if not self.required_path_labels:
            raise DataplaneValidationError("dataplane required paths are required")
        if self.min_successful_probes < 1:
            raise DataplaneValidationError("dataplane minimum success count is invalid")
        probe_ids = [probe.probe_id for probe in self.probes]
        if len(set(probe_ids)) != len(probe_ids):
            raise DataplaneValidationError("dataplane probe ids must be unique")


@dataclass(frozen=True)
class DataplaneValidationEvidence:
    """Privacy-safe dataplane validation result for rollout gates."""

    plan_hash: str
    results: tuple[DataplaneProbeResult, ...]
    required_path_labels: frozenset[str]
    min_successful_probes: int
    captured_at: int

    @property
    def covered_path_labels(self) -> tuple[str, ...]:
        return tuple(
            sorted({result.path_label for result in self.results if result.success})
        )

    @property
    def successful_probe_count(self) -> int:
        return sum(1 for result in self.results if result.success)

    @property
    def passed(self) -> bool:
        missing = self.required_path_labels - set(self.covered_path_labels)
        required_failures = any(not result.success for result in self.results)
        return (
            not missing
            and not required_failures
            and self.successful_probe_count >= self.min_successful_probes
        )

    @property
    def failed_reasons(self) -> tuple[str, ...]:
        reasons = [
            f"dataplane_probe_failed:{result.probe_id}:{result.failure_reason}"
            for result in self.results
            if not result.success
        ]
        for path in sorted(self.required_path_labels - set(self.covered_path_labels)):
            reasons.append(f"dataplane_required_path_missing:{path}")
        if self.successful_probe_count < self.min_successful_probes:
            reasons.append("dataplane_success_count_below_required")
        return tuple(reasons)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-dataplane-validation-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def probe_matrix_hash(self) -> str:
        """Hash the validated endpoint matrix without including probe outcomes."""
        return _probe_matrix_hash(
            self.results,
            required_path_labels=self.required_path_labels,
            min_successful=self.min_successful_probes,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "captured_at": self.captured_at,
            "covered_path_labels": list(self.covered_path_labels),
            "failed_reasons": list(self.failed_reasons),
            "min_successful_probes": self.min_successful_probes,
            "passed": self.passed,
            "plan_hash": self.plan_hash,
            "probe_matrix_hash": self.probe_matrix_hash(),
            "required_path_labels": sorted(self.required_path_labels),
            "results": [result.to_json_dict() for result in self.results],
            "successful_probe_count": self.successful_probe_count,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class TunDataplaneProbeResult:
    """Payload-free evidence that one path carried real TUN packets."""

    probe_id: str
    path_label: str
    transport: DataplaneTransport
    remote_hash: str
    success: bool
    packets_from_tun: int = 0
    packets_to_tun: int = 0
    bytes_from_tun: int = 0
    bytes_to_tun: int = 0
    tx_fragments: int = 0
    rx_fragments: int = 0
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.probe_id.strip():
            raise DataplaneValidationError("TUN dataplane result probe id is required")
        if not self.path_label.strip():
            raise DataplaneValidationError("TUN dataplane path label is required")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise DataplaneValidationError(
                "TUN dataplane transport must be udp, tcp, or camouflage"
            )
        if not self.remote_hash.strip():
            raise DataplaneValidationError("TUN dataplane remote hash is required")
        counters = (
            self.packets_from_tun,
            self.packets_to_tun,
            self.bytes_from_tun,
            self.bytes_to_tun,
            self.tx_fragments,
            self.rx_fragments,
        )
        if any(value < 0 for value in counters):
            raise DataplaneValidationError("TUN dataplane counters cannot be negative")
        if self.success and self.failure_reason is not None:
            raise DataplaneValidationError("successful TUN dataplane result has failure reason")
        if not self.success and not (self.failure_reason or "").strip():
            raise DataplaneValidationError("failed TUN dataplane result requires reason")
        if self.success and (
            self.packets_from_tun < 1
            or self.packets_to_tun < 1
            or self.bytes_from_tun < 1
            or self.bytes_to_tun < 1
            or self.tx_fragments < 1
            or self.rx_fragments < 1
        ):
            raise DataplaneValidationError(
                "successful TUN dataplane result requires bidirectional packet evidence"
            )

    @classmethod
    def success_result(
        cls,
        spec: DataplaneProbeSpec,
        *,
        packets_from_tun: int,
        packets_to_tun: int,
        bytes_from_tun: int,
        bytes_to_tun: int,
        tx_fragments: int = 1,
        rx_fragments: int = 1,
    ) -> "TunDataplaneProbeResult":
        return cls(
            probe_id=spec.probe_id,
            path_label=spec.path_label,
            transport=spec.transport,
            remote_hash=spec.remote_hash,
            success=True,
            packets_from_tun=packets_from_tun,
            packets_to_tun=packets_to_tun,
            bytes_from_tun=bytes_from_tun,
            bytes_to_tun=bytes_to_tun,
            tx_fragments=tx_fragments,
            rx_fragments=rx_fragments,
        )

    @classmethod
    def failure_result(
        cls,
        spec: DataplaneProbeSpec,
        *,
        reason: str,
    ) -> "TunDataplaneProbeResult":
        return cls(
            probe_id=spec.probe_id,
            path_label=spec.path_label,
            transport=spec.transport,
            remote_hash=spec.remote_hash,
            success=False,
            failure_reason=reason,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "bytes_from_tun": self.bytes_from_tun,
            "bytes_to_tun": self.bytes_to_tun,
            "path_label": self.path_label,
            "packets_from_tun": self.packets_from_tun,
            "packets_to_tun": self.packets_to_tun,
            "probe_id": self.probe_id,
            "remote_hash": self.remote_hash,
            "rx_fragments": self.rx_fragments,
            "success": self.success,
            "transport": self.transport,
            "tx_fragments": self.tx_fragments,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class TunDataplaneValidationEvidence:
    """Privacy-safe proof that protected DATA carried TUN packets on required paths."""

    plan_hash: str
    results: tuple[TunDataplaneProbeResult, ...]
    required_path_labels: frozenset[str]
    min_successful_paths: int
    captured_at: int

    def __post_init__(self) -> None:
        if not self.results:
            raise DataplaneValidationError("TUN dataplane results are required")
        if not self.required_path_labels:
            raise DataplaneValidationError("TUN dataplane required paths are required")
        if self.min_successful_paths < 1:
            raise DataplaneValidationError("TUN dataplane minimum success count is invalid")
        if self.captured_at < 0:
            raise DataplaneValidationError("TUN dataplane capture time cannot be negative")
        if len(self.plan_hash) != 64:
            raise DataplaneValidationError("TUN dataplane plan hash must be sha256 hex")
        probe_ids = [result.probe_id for result in self.results]
        if len(set(probe_ids)) != len(probe_ids):
            raise DataplaneValidationError("TUN dataplane result probe ids must be unique")

    @classmethod
    def from_results(
        cls,
        *,
        plan: DataplaneValidationPlan,
        results: tuple[TunDataplaneProbeResult, ...],
        captured_at: int,
    ) -> "TunDataplaneValidationEvidence":
        expected = {probe.probe_id: probe for probe in plan.probes}
        for result in results:
            try:
                probe = expected[result.probe_id]
            except KeyError as exc:
                raise DataplaneValidationError(
                    "TUN dataplane result probe id is not in plan"
                ) from exc
            if result.remote_hash != probe.remote_hash:
                raise DataplaneValidationError(
                    "TUN dataplane result remote hash mismatch"
                )
        return cls(
            plan_hash=_tun_plan_hash(plan),
            results=results,
            required_path_labels=plan.required_path_labels,
            min_successful_paths=plan.min_successful_probes,
            captured_at=captured_at,
        )

    @property
    def covered_path_labels(self) -> tuple[str, ...]:
        return tuple(
            sorted({result.path_label for result in self.results if result.success})
        )

    @property
    def successful_path_count(self) -> int:
        return len(self.covered_path_labels)

    @property
    def passed(self) -> bool:
        return not self.failed_reasons

    @property
    def failed_reasons(self) -> tuple[str, ...]:
        reasons = [
            f"tun_dataplane_probe_failed:{result.probe_id}:{result.failure_reason}"
            for result in self.results
            if not result.success
        ]
        for path in sorted(self.required_path_labels - set(self.covered_path_labels)):
            reasons.append(f"tun_dataplane_required_path_missing:{path}")
        if self.successful_path_count < self.min_successful_paths:
            reasons.append("tun_dataplane_success_count_below_required")
        return tuple(reasons)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-tun-dataplane-validation-v1"
            + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def probe_matrix_hash(self) -> str:
        """Hash the validated endpoint matrix without including packet counters."""
        return _probe_matrix_hash(
            self.results,
            required_path_labels=self.required_path_labels,
            min_successful=self.min_successful_paths,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "captured_at": self.captured_at,
            "covered_path_labels": list(self.covered_path_labels),
            "failed_reasons": list(self.failed_reasons),
            "min_successful_paths": self.min_successful_paths,
            "passed": self.passed,
            "plan_hash": self.plan_hash,
            "probe_matrix_hash": self.probe_matrix_hash(),
            "required_path_labels": sorted(self.required_path_labels),
            "results": [result.to_json_dict() for result in self.results],
            "successful_path_count": self.successful_path_count,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class FirstPartyTunLoopbackProbeRunner:
    """Run real TUN packet probes through first-party protected DATA transports."""

    session: SessionContext
    host: str = "127.0.0.1"
    tun_mtu: int = 1400
    fragment_payload_size: int = 512

    async def __call__(self, probe: DataplaneProbeSpec) -> TunDataplaneProbeResult:
        packet_size = 20 + probe.payload_size
        if packet_size > self.tun_mtu:
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason="tun_packet_exceeds_mtu",
            )
        try:
            if probe.transport == "udp":
                return await self._run_udp_tun_probe(probe)
            if probe.transport == "tcp":
                return await self._run_tcp_tun_probe(probe)
            if probe.transport == "camouflage":
                return await self._run_camouflage_tun_probe(probe)
        except Exception as exc:
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason=(
                    "timeout"
                    if isinstance(exc, (TimeoutError, asyncio.TimeoutError))
                    else type(exc).__name__
                ),
            )
        return TunDataplaneProbeResult.failure_result(
            probe,
            reason="unsupported_transport",
        )

    async def _run_udp_tun_probe(
        self,
        probe: DataplaneProbeSpec,
    ) -> TunDataplaneProbeResult:
        server_transport = None
        client_transport = None
        try:
            client_tun, server_tun, server_handler = self._tun_pair()
            server_transport, _server_protocol, server_addr = await open_udp_server(
                session=self.session,
                host=self.host,
                on_data=server_handler,
            )
            client_transport, client = await open_udp_client(
                session=self.session,
                remote_addr=server_addr,
            )
            bridge = self._client_bridge(client_tun, client)
            return await self._run_bridge_probe(
                probe=probe,
                client_tun=client_tun,
                server_tun=server_tun,
                bridge=bridge,
            )
        finally:
            if client_transport is not None:
                client_transport.close()
            if server_transport is not None:
                server_transport.close()

    async def _run_tcp_tun_probe(
        self,
        probe: DataplaneProbeSpec,
    ) -> TunDataplaneProbeResult:
        server = None
        protocol = None
        client = None
        try:
            client_tun, server_tun, server_handler = self._tun_pair()
            server, protocol, server_addr = await open_tcp_server(
                session=self.session,
                host=self.host,
                on_data=server_handler,
            )
            client = await open_tcp_client(
                session=self.session,
                remote_addr=server_addr,
            )
            bridge = self._client_bridge(client_tun, client)
            return await self._run_bridge_probe(
                probe=probe,
                client_tun=client_tun,
                server_tun=server_tun,
                bridge=bridge,
            )
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()
            if server is not None:
                server.close()
                await server.wait_closed()
            if protocol is not None:
                await protocol.wait_client_tasks()

    async def _run_camouflage_tun_probe(
        self,
        probe: DataplaneProbeSpec,
    ) -> TunDataplaneProbeResult:
        server = None
        protocol = None
        client = None
        try:
            client_tun, server_tun, server_handler = self._tun_pair()
            server, protocol, server_addr = await open_camouflage_server(
                session=self.session,
                host=self.host,
                on_data=server_handler,
            )
            client = await open_camouflage_client(
                session=self.session,
                remote_addr=server_addr,
                timeout=probe.timeout_seconds,
            )
            bridge = self._client_bridge(client_tun, client)
            return await self._run_bridge_probe(
                probe=probe,
                client_tun=client_tun,
                server_tun=server_tun,
                bridge=bridge,
            )
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()
            if server is not None:
                server.close()
                await server.wait_closed()
            if protocol is not None:
                await protocol.wait_client_tasks()

    def _tun_pair(
        self,
    ) -> tuple[MemoryTunDevice, MemoryTunDevice, FirstPartyTunServerHandler]:
        client_tun = MemoryTunDevice(mtu=self.tun_mtu)
        server_tun = MemoryTunDevice(mtu=self.tun_mtu)
        server_handler = FirstPartyTunServerHandler(
            tun=server_tun,
            response=_tun_probe_response,
            fragmenter=PacketFragmenter(max_payload_size=self.fragment_payload_size),
            reassembler=PacketReassembler(),
        )
        return client_tun, server_tun, server_handler

    def _client_bridge(
        self,
        client_tun: MemoryTunDevice,
        client: object,
    ) -> FirstPartyTunClientBridge:
        return FirstPartyTunClientBridge(
            tun=client_tun,
            client=client,
            fragmenter=PacketFragmenter(max_payload_size=self.fragment_payload_size),
            reassembler=PacketReassembler(),
        )

    async def _run_bridge_probe(
        self,
        *,
        probe: DataplaneProbeSpec,
        client_tun: MemoryTunDevice,
        server_tun: MemoryTunDevice,
        bridge: FirstPartyTunClientBridge,
    ) -> TunDataplaneProbeResult:
        packet = _tun_probe_packet(probe)
        client_tun.inject_packet(packet)
        await bridge.send_one_from_tun(timeout=probe.timeout_seconds)
        if await server_tun.read_written(timeout=probe.timeout_seconds) != packet:
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason="server_tun_packet_mismatch",
            )
        await bridge.receive_one_to_tun(timeout=probe.timeout_seconds)
        response = await client_tun.read_written(timeout=probe.timeout_seconds)
        if response != _tun_probe_response(packet):
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason="client_tun_response_mismatch",
            )
        return TunDataplaneProbeResult.success_result(
            probe,
            packets_from_tun=bridge.stats.packets_from_tun,
            packets_to_tun=bridge.stats.packets_to_tun,
            bytes_from_tun=bridge.stats.bytes_from_tun,
            bytes_to_tun=bridge.stats.bytes_to_tun,
            tx_fragments=bridge.stats.tx_fragments,
            rx_fragments=bridge.stats.rx_fragments,
        )


@dataclass(frozen=True)
class FirstPartyRemoteTunProbeRunner:
    """Run real TUN packet probes against already-running first-party endpoints."""

    session: SessionContext
    endpoint_resolver: DataplaneEndpointResolver
    tun_mtu: int = 1400
    fragment_payload_size: int = 512

    async def __call__(self, probe: DataplaneProbeSpec) -> TunDataplaneProbeResult:
        packet_size = 20 + probe.payload_size
        if packet_size > self.tun_mtu:
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason="tun_packet_exceeds_mtu",
            )
        try:
            remote_addr = _validate_remote_addr(self.endpoint_resolver(probe))
            if probe.transport == "udp":
                return await self._run_udp_tun_probe(probe, remote_addr)
            if probe.transport == "tcp":
                return await self._run_tcp_tun_probe(probe, remote_addr)
            if probe.transport == "camouflage":
                return await self._run_camouflage_tun_probe(probe, remote_addr)
        except Exception as exc:
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason=(
                    "timeout"
                    if isinstance(exc, (TimeoutError, asyncio.TimeoutError))
                    else type(exc).__name__
                ),
            )
        return TunDataplaneProbeResult.failure_result(
            probe,
            reason="unsupported_transport",
        )

    async def _run_udp_tun_probe(
        self,
        probe: DataplaneProbeSpec,
        remote_addr: tuple[str, int],
    ) -> TunDataplaneProbeResult:
        client_transport = None
        try:
            client_tun = MemoryTunDevice(mtu=self.tun_mtu)
            client_transport, client = await open_udp_client(
                session=self.session,
                remote_addr=remote_addr,
            )
            bridge = self._client_bridge(client_tun, client)
            return await self._run_client_bridge_probe(
                probe=probe,
                client_tun=client_tun,
                bridge=bridge,
            )
        finally:
            if client_transport is not None:
                client_transport.close()

    async def _run_tcp_tun_probe(
        self,
        probe: DataplaneProbeSpec,
        remote_addr: tuple[str, int],
    ) -> TunDataplaneProbeResult:
        client = None
        try:
            client_tun = MemoryTunDevice(mtu=self.tun_mtu)
            client = await open_tcp_client(
                session=self.session,
                remote_addr=remote_addr,
            )
            bridge = self._client_bridge(client_tun, client)
            return await self._run_client_bridge_probe(
                probe=probe,
                client_tun=client_tun,
                bridge=bridge,
            )
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()

    async def _run_camouflage_tun_probe(
        self,
        probe: DataplaneProbeSpec,
        remote_addr: tuple[str, int],
    ) -> TunDataplaneProbeResult:
        client = None
        try:
            client_tun = MemoryTunDevice(mtu=self.tun_mtu)
            client = await open_camouflage_client(
                session=self.session,
                remote_addr=remote_addr,
                timeout=probe.timeout_seconds,
            )
            bridge = self._client_bridge(client_tun, client)
            return await self._run_client_bridge_probe(
                probe=probe,
                client_tun=client_tun,
                bridge=bridge,
            )
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()

    def _client_bridge(
        self,
        client_tun: MemoryTunDevice,
        client: object,
    ) -> FirstPartyTunClientBridge:
        return FirstPartyTunClientBridge(
            tun=client_tun,
            client=client,
            fragmenter=PacketFragmenter(max_payload_size=self.fragment_payload_size),
            reassembler=PacketReassembler(),
        )

    async def _run_client_bridge_probe(
        self,
        *,
        probe: DataplaneProbeSpec,
        client_tun: MemoryTunDevice,
        bridge: FirstPartyTunClientBridge,
    ) -> TunDataplaneProbeResult:
        packet = _tun_probe_packet(probe)
        client_tun.inject_packet(packet)
        await bridge.send_one_from_tun(timeout=probe.timeout_seconds)
        await bridge.receive_one_to_tun(timeout=probe.timeout_seconds)
        response = await client_tun.read_written(timeout=probe.timeout_seconds)
        if response != _tun_probe_response(packet):
            return TunDataplaneProbeResult.failure_result(
                probe,
                reason="client_tun_response_mismatch",
            )
        return TunDataplaneProbeResult.success_result(
            probe,
            packets_from_tun=bridge.stats.packets_from_tun,
            packets_to_tun=bridge.stats.packets_to_tun,
            bytes_from_tun=bridge.stats.bytes_from_tun,
            bytes_to_tun=bridge.stats.bytes_to_tun,
            tx_fragments=bridge.stats.tx_fragments,
            rx_fragments=bridge.stats.rx_fragments,
        )


@dataclass(frozen=True)
class FirstPartyLoopbackProbeRunner:
    """Run probes through first-party UDP/TCP/camouflage runtime on loopback."""

    session: SessionContext
    host: str = "127.0.0.1"

    async def __call__(self, probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        if probe.payload_size > MAX_PAYLOAD_BYTES:
            return DataplaneProbeResult.failure_result(
                probe,
                reason="payload_size_exceeds_frame_limit",
            )
        try:
            if probe.transport == "udp":
                return await self._run_udp_probe(probe)
            if probe.transport == "tcp":
                return await self._run_tcp_probe(probe)
            if probe.transport == "camouflage":
                return await self._run_camouflage_probe(probe)
        except Exception as exc:
            return _failure_result(probe, exc)
        return DataplaneProbeResult.failure_result(probe, reason="unsupported_transport")

    async def _run_udp_probe(self, probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        server_transport = None
        try:
            server_transport, _server, server_addr = await open_udp_server(
                session=self.session,
                host=self.host,
            )
            return await _run_udp_ping_probe(
                session=self.session,
                probe=probe,
                remote_addr=server_addr,
            )
        finally:
            if server_transport is not None:
                server_transport.close()

    async def _run_tcp_probe(self, probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        server = None
        protocol = None
        try:
            server, protocol, server_addr = await open_tcp_server(
                session=self.session,
                host=self.host,
            )
            return await _run_tcp_ping_probe(
                session=self.session,
                probe=probe,
                remote_addr=server_addr,
            )
        finally:
            if server is not None:
                server.close()
                await server.wait_closed()
            if protocol is not None:
                await protocol.wait_client_tasks()

    async def _run_camouflage_probe(self, probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        server = None
        protocol = None
        try:
            server, protocol, server_addr = await open_camouflage_server(
                session=self.session,
                host=self.host,
            )
            return await _run_camouflage_ping_probe(
                session=self.session,
                probe=probe,
                remote_addr=server_addr,
            )
        finally:
            if server is not None:
                server.close()
                await server.wait_closed()
            if protocol is not None:
                await protocol.wait_client_tasks()


@dataclass(frozen=True)
class FirstPartyRemoteProbeRunner:
    """Run probes against already-running first-party UDP/TCP/camouflage servers."""

    session: SessionContext
    endpoint_resolver: DataplaneEndpointResolver

    async def __call__(self, probe: DataplaneProbeSpec) -> DataplaneProbeResult:
        if probe.payload_size > MAX_PAYLOAD_BYTES:
            return DataplaneProbeResult.failure_result(
                probe,
                reason="payload_size_exceeds_frame_limit",
            )
        try:
            remote_addr = _validate_remote_addr(self.endpoint_resolver(probe))
            if probe.transport == "udp":
                return await _run_udp_ping_probe(
                    session=self.session,
                    probe=probe,
                    remote_addr=remote_addr,
                )
            if probe.transport == "tcp":
                return await _run_tcp_ping_probe(
                    session=self.session,
                    probe=probe,
                    remote_addr=remote_addr,
                )
            if probe.transport == "camouflage":
                return await _run_camouflage_ping_probe(
                    session=self.session,
                    probe=probe,
                    remote_addr=remote_addr,
                )
        except Exception as exc:
            return _failure_result(probe, exc)
        return DataplaneProbeResult.failure_result(probe, reason="unsupported_transport")


async def evaluate_dataplane_validation(
    *,
    plan: DataplaneValidationPlan,
    runner: DataplaneProbeRunner,
    captured_at: int,
) -> DataplaneValidationEvidence:
    """Run dataplane probes and return privacy-safe rollout evidence."""
    results: list[DataplaneProbeResult] = []
    for probe in plan.probes:
        try:
            result = await runner(probe)
        except Exception as exc:
            result = DataplaneProbeResult.failure_result(
                probe,
                reason=type(exc).__name__,
            )
        if result.probe_id != probe.probe_id:
            raise DataplaneValidationError("dataplane runner returned wrong probe id")
        if result.remote_hash != probe.remote_hash:
            raise DataplaneValidationError("dataplane runner returned wrong remote hash")
        results.append(result)
    return DataplaneValidationEvidence(
        plan_hash=_plan_hash(plan),
        results=tuple(results),
        required_path_labels=plan.required_path_labels,
        min_successful_probes=plan.min_successful_probes,
        captured_at=captured_at,
    )


async def evaluate_tun_dataplane_validation(
    *,
    plan: DataplaneValidationPlan,
    runner: TunDataplaneProbeRunner,
    captured_at: int,
) -> TunDataplaneValidationEvidence:
    """Run protected TUN packet probes and return privacy-safe rollout evidence."""
    results: list[TunDataplaneProbeResult] = []
    for probe in plan.probes:
        try:
            result = await runner(probe)
        except Exception as exc:
            result = TunDataplaneProbeResult.failure_result(
                probe,
                reason=type(exc).__name__,
            )
        if result.probe_id != probe.probe_id:
            raise DataplaneValidationError("TUN dataplane runner returned wrong probe id")
        if result.remote_hash != probe.remote_hash:
            raise DataplaneValidationError("TUN dataplane runner returned wrong remote hash")
        results.append(result)
    return TunDataplaneValidationEvidence.from_results(
        plan=plan,
        results=tuple(results),
        captured_at=captured_at,
    )


def _plan_hash(plan: DataplaneValidationPlan) -> str:
    payload = {
        "min_successful_probes": plan.min_successful_probes,
        "probes": [probe.to_json_dict() for probe in plan.probes],
        "required_path_labels": sorted(plan.required_path_labels),
        "version": 1,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _tun_plan_hash(plan: DataplaneValidationPlan) -> str:
    payload = {
        "min_successful_paths": plan.min_successful_probes,
        "probes": [probe.to_json_dict() for probe in plan.probes],
        "required_path_labels": sorted(plan.required_path_labels),
        "validation_kind": "tun-dataplane",
        "version": 1,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _probe_matrix_hash(
    results: tuple[object, ...],
    *,
    required_path_labels: frozenset[str],
    min_successful: int,
) -> str:
    payload = {
        "min_successful": min_successful,
        "probes": sorted(
            (
                {
                    "path_label": result.path_label,
                    "probe_id": result.probe_id,
                    "remote_hash": result.remote_hash,
                    "transport": result.transport,
                }
                for result in results
            ),
            key=lambda item: (
                str(item["probe_id"]),
                str(item["path_label"]),
                str(item["transport"]),
                str(item["remote_hash"]),
            ),
        ),
        "required_path_labels": sorted(required_path_labels),
        "version": 1,
    }
    assert_privacy_safe(payload)
    return hashlib.sha256(
        b"x0vpn-dataplane-probe-matrix-v1" + _canonical_json(payload)
    ).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


async def _run_udp_ping_probe(
    *,
    session: SessionContext,
    probe: DataplaneProbeSpec,
    remote_addr: tuple[str, int],
) -> DataplaneProbeResult:
    payload = _probe_payload(probe)
    client_transport = None
    try:
        client_transport, client = await open_udp_client(
            session=session,
            remote_addr=remote_addr,
        )
        started = time.perf_counter()
        client.send_ping(payload)
        frame = await client.recv(timeout=probe.timeout_seconds)
        latency_millis = int((time.perf_counter() - started) * 1000)
        if frame.frame_type != FrameType.PONG:
            return DataplaneProbeResult.failure_result(probe, reason="pong_frame_missing")
        if frame.payload != payload:
            return DataplaneProbeResult.failure_result(probe, reason="pong_payload_mismatch")
        return DataplaneProbeResult.success_result(
            probe,
            latency_millis=max(0, latency_millis),
            rx_frames=client.endpoint.stats.rx_frames,
            tx_frames=client.endpoint.stats.tx_frames,
            rx_bytes=client.endpoint.stats.rx_bytes,
            tx_bytes=client.endpoint.stats.tx_bytes,
        )
    finally:
        if client_transport is not None:
            client_transport.close()


async def _run_tcp_ping_probe(
    *,
    session: SessionContext,
    probe: DataplaneProbeSpec,
    remote_addr: tuple[str, int],
) -> DataplaneProbeResult:
    payload = _probe_payload(probe)
    client = None
    try:
        client = await open_tcp_client(
            session=session,
            remote_addr=remote_addr,
        )
        started = time.perf_counter()
        client.send_ping(payload)
        await client.drain()
        frame = await client.recv(timeout=probe.timeout_seconds)
        latency_millis = int((time.perf_counter() - started) * 1000)
        if frame.frame_type != FrameType.PONG:
            return DataplaneProbeResult.failure_result(probe, reason="pong_frame_missing")
        if frame.payload != payload:
            return DataplaneProbeResult.failure_result(probe, reason="pong_payload_mismatch")
        return DataplaneProbeResult.success_result(
            probe,
            latency_millis=max(0, latency_millis),
            rx_frames=client.endpoint.stats.rx_frames,
            tx_frames=client.endpoint.stats.tx_frames,
            rx_bytes=client.endpoint.stats.rx_bytes,
            tx_bytes=client.endpoint.stats.tx_bytes,
        )
    finally:
        if client is not None:
            client.close()
            await client.wait_closed()


async def _run_camouflage_ping_probe(
    *,
    session: SessionContext,
    probe: DataplaneProbeSpec,
    remote_addr: tuple[str, int],
) -> DataplaneProbeResult:
    payload = _probe_payload(probe)
    client = None
    try:
        client = await open_camouflage_client(
            session=session,
            remote_addr=remote_addr,
            timeout=probe.timeout_seconds,
        )
        started = time.perf_counter()
        client.send_ping(payload)
        await client.drain()
        frame = await client.recv(timeout=probe.timeout_seconds)
        latency_millis = int((time.perf_counter() - started) * 1000)
        if frame.frame_type != FrameType.PONG:
            return DataplaneProbeResult.failure_result(probe, reason="pong_frame_missing")
        if frame.payload != payload:
            return DataplaneProbeResult.failure_result(probe, reason="pong_payload_mismatch")
        return DataplaneProbeResult.success_result(
            probe,
            latency_millis=max(0, latency_millis),
            rx_frames=client.endpoint.stats.rx_frames,
            tx_frames=client.endpoint.stats.tx_frames,
            rx_bytes=client.endpoint.stats.rx_bytes,
            tx_bytes=client.endpoint.stats.tx_bytes,
        )
    finally:
        if client is not None:
            client.close()
            await client.wait_closed()


def _probe_payload(probe: DataplaneProbeSpec) -> bytes:
    seed = f"x0vpn-dataplane-probe-v1:{probe.probe_id}:".encode("utf-8")
    repeats = (probe.payload_size + len(seed) - 1) // len(seed)
    return (seed * repeats)[: probe.payload_size]


def _tun_probe_packet(probe: DataplaneProbeSpec) -> bytes:
    payload = _probe_payload(probe)
    return _ipv4_packet(
        payload,
        source=b"\x0a\x4d\x00\x01",
        destination=b"\x0a\x4d\x00\x02",
    )


def _tun_probe_response(packet: bytes) -> bytes:
    payload = packet[20:]
    response_payload = bytes([payload[0] ^ 0xFF]) + payload[1:]
    return _ipv4_packet(
        response_payload,
        source=b"\x0a\x4d\x00\x02",
        destination=b"\x0a\x4d\x00\x01",
    )


def _ipv4_packet(
    payload: bytes,
    *,
    source: bytes,
    destination: bytes,
) -> bytes:
    total_length = 20 + len(payload)
    if total_length > 0xFFFF:
        raise DataplaneValidationError("TUN probe IPv4 packet exceeds maximum length")
    if len(source) != 4 or len(destination) != 4:
        raise DataplaneValidationError("TUN probe IPv4 address length is invalid")
    return b"".join(
        (
            b"\x45\x00",
            total_length.to_bytes(2, "big"),
            b"\x00\x00",
            b"\x00\x00",
            b"\x40",
            b"\x11",
            b"\x00\x00",
            source,
            destination,
            payload,
        )
    )


def _failure_result(
    probe: DataplaneProbeSpec,
    exc: Exception,
) -> DataplaneProbeResult:
    reason = (
        "timeout"
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError))
        else type(exc).__name__
    )
    return DataplaneProbeResult.failure_result(probe, reason=reason)


def _validate_remote_addr(remote_addr: tuple[str, int]) -> tuple[str, int]:
    host, port = remote_addr
    if not isinstance(host, str) or not host.strip():
        raise DataplaneValidationError("dataplane remote host is invalid")
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise DataplaneValidationError("dataplane remote port is invalid")
    return (host, port)
