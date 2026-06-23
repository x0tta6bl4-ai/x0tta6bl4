"""Unified first-party VPN dataplane client with UDP/TCP/camouflage failover."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import time
from typing import Callable, Sequence

from .camouflage import (
    CamouflagePolicy,
    CamouflageProfile,
    FirstPartyCamouflageClient,
    open_camouflage_admission_client,
    open_camouflage_client,
)
from .dataplane_validation import DataplaneProbeResult, FirstPartyRemoteProbeRunner
from .handshake import FirstPartyHandshakeAccept, FirstPartyHandshakeHello, PqcMaterialGate
from .identity import IdentityVerifier, RevocationList
from .ops import assert_privacy_safe
from .pqc import PqcSessionSecretMaterial
from .protocol import Frame
from .runtime import (
    FirstPartyEndpoint,
    FirstPartyUdpAdmissionClient,
    FirstPartyUdpClient,
    RuntimeStats,
    open_udp_admission_client,
    open_udp_client,
)
from .selection import (
    DataplaneEndpointCandidate,
    DataplaneSelectionEvidence,
    FirstPartyDataplaneSelector,
    TunDataplaneSelectionEvidence,
)
from .session import SessionContext
from .stream import FirstPartyTcpClient, open_tcp_admission_client, open_tcp_client
from .zero_trust import ZeroTrustPolicy


class FirstPartyDataplaneClientError(RuntimeError):
    """Raised when a first-party dataplane client cannot be opened or used."""

    def __init__(
        self,
        message: str,
        *,
        selection_evidence: DataplaneSelectionEvidence | None = None,
        tun_selection_evidence: TunDataplaneSelectionEvidence | None = None,
        open_evidence: "DataplaneClientOpenEvidence | None" = None,
    ) -> None:
        super().__init__(message)
        self.selection_evidence = selection_evidence
        self.tun_selection_evidence = tun_selection_evidence
        self.open_evidence = open_evidence


@dataclass(frozen=True)
class DataplaneClientOpenAttempt:
    """Privacy-safe result of opening one already-probed endpoint candidate."""

    candidate_hash: str
    path_label: str
    transport: str
    remote_hash: str
    opened: bool
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.candidate_hash.strip():
            raise FirstPartyDataplaneClientError("dataplane open candidate hash is required")
        if not self.path_label.strip():
            raise FirstPartyDataplaneClientError("dataplane open path label is required")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise FirstPartyDataplaneClientError("dataplane open transport is invalid")
        if not self.remote_hash.strip():
            raise FirstPartyDataplaneClientError("dataplane open remote hash is required")
        if self.opened and self.failure_reason is not None:
            raise FirstPartyDataplaneClientError("opened dataplane attempt has failure reason")
        if not self.opened and not (self.failure_reason or "").strip():
            raise FirstPartyDataplaneClientError("failed dataplane open attempt requires reason")

    @classmethod
    def from_candidate(
        cls,
        candidate: DataplaneEndpointCandidate,
        *,
        opened: bool,
        failure_reason: str | None = None,
    ) -> "DataplaneClientOpenAttempt":
        return cls(
            candidate_hash=candidate.candidate_hash,
            path_label=candidate.path_label,
            transport=candidate.transport,
            remote_hash=candidate.remote_hash,
            opened=opened,
            failure_reason=failure_reason,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "candidate_hash": self.candidate_hash,
            "path_label": self.path_label,
            "transport": self.transport,
            "remote_hash": self.remote_hash,
            "opened": self.opened,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class DataplaneClientOpenEvidence:
    """Payload-free evidence for client transport open failover."""

    selection_evidence: DataplaneSelectionEvidence
    attempts: tuple[DataplaneClientOpenAttempt, ...]
    selected_candidate_hash: str | None
    captured_at: int

    @property
    def passed(self) -> bool:
        return self.selected_candidate_hash is not None

    @property
    def failed_reasons(self) -> tuple[str, ...]:
        if self.passed:
            return ()
        return tuple(
            f"dataplane_open_failed:{attempt.candidate_hash}:{attempt.failure_reason}"
            for attempt in self.attempts
            if not attempt.opened
        ) or tuple(self.selection_evidence.failed_reasons) or ("dataplane_open_missing",)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-dataplane-client-open-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "attempts": [attempt.to_json_dict() for attempt in self.attempts],
            "captured_at": self.captured_at,
            "failed_reasons": list(self.failed_reasons),
            "passed": self.passed,
            "selected_candidate_hash": self.selected_candidate_hash,
            "selection_evidence_hash": self.selection_evidence.evidence_hash(),
        }
        assert_privacy_safe(payload)
        return payload


@dataclass
class FirstPartyDataplaneClient:
    """Client wrapper for the selected first-party dataplane path."""

    session: SessionContext
    selected: DataplaneEndpointCandidate
    selection_evidence: DataplaneSelectionEvidence
    udp_transport: asyncio.DatagramTransport | None = None
    udp_client: FirstPartyUdpClient | FirstPartyUdpAdmissionClient | None = None
    tcp_client: FirstPartyTcpClient | None = None
    camouflage_client: FirstPartyCamouflageClient | None = None
    open_evidence: DataplaneClientOpenEvidence | None = None
    accept: FirstPartyHandshakeAccept | None = None

    @property
    def transport(self) -> str:
        return self.selected.transport

    @property
    def endpoint(self) -> FirstPartyEndpoint:
        if self.udp_client is not None:
            return self.udp_client.endpoint
        if self.tcp_client is not None:
            return self.tcp_client.endpoint
        if self.camouflage_client is not None:
            return self.camouflage_client.endpoint
        raise FirstPartyDataplaneClientError(
            "dataplane client is closed",
            selection_evidence=self.selection_evidence,
        )

    @property
    def stats(self) -> RuntimeStats:
        return self.endpoint.stats

    def send_data(self, payload: bytes) -> None:
        if self.udp_client is not None:
            self.udp_client.send_data(payload)
            return
        if self.tcp_client is not None:
            self.tcp_client.send_data(payload)
            return
        if self.camouflage_client is not None:
            self.camouflage_client.send_data(payload)
            return
        raise FirstPartyDataplaneClientError(
            "dataplane client is closed",
            selection_evidence=self.selection_evidence,
        )

    def send_data_fragments(self, payloads: Sequence[bytes]) -> None:
        if self.udp_client is not None:
            self.udp_client.send_data_fragments(payloads)
            return
        if self.tcp_client is not None:
            self.tcp_client.send_data_fragments(payloads)
            return
        if self.camouflage_client is not None:
            self.camouflage_client.send_data_fragments(payloads)
            return
        raise FirstPartyDataplaneClientError(
            "dataplane client is closed",
            selection_evidence=self.selection_evidence,
        )

    def send_ping(self, payload: bytes = b"") -> None:
        if self.udp_client is not None:
            self.udp_client.send_ping(payload)
            return
        if self.tcp_client is not None:
            self.tcp_client.send_ping(payload)
            return
        if self.camouflage_client is not None:
            self.camouflage_client.send_ping(payload)
            return
        raise FirstPartyDataplaneClientError(
            "dataplane client is closed",
            selection_evidence=self.selection_evidence,
        )

    async def drain(self) -> None:
        if self.tcp_client is not None:
            await self.tcp_client.drain()
        if self.camouflage_client is not None:
            await self.camouflage_client.drain()

    async def recv(self, timeout: float = 1.0) -> Frame:
        if self.udp_client is not None:
            return await self.udp_client.recv(timeout=timeout)
        if self.tcp_client is not None:
            return await self.tcp_client.recv(timeout=timeout)
        if self.camouflage_client is not None:
            return await self.camouflage_client.recv(timeout=timeout)
        raise FirstPartyDataplaneClientError(
            "dataplane client is closed",
            selection_evidence=self.selection_evidence,
        )

    async def close(self) -> None:
        if self.udp_transport is not None:
            self.udp_transport.close()
        self.udp_transport = None
        self.udp_client = None

        if self.tcp_client is not None:
            self.tcp_client.close()
            await self.tcp_client.wait_closed()
        self.tcp_client = None

        if self.camouflage_client is not None:
            self.camouflage_client.close()
            await self.camouflage_client.wait_closed()
        self.camouflage_client = None


async def open_firstparty_dataplane_client(
    *,
    session: SessionContext,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    captured_at: int,
) -> FirstPartyDataplaneClient:
    """Select and open a first-party endpoint, continuing failover on open failure."""
    selector = FirstPartyDataplaneSelector(session=session, candidates=candidates)
    ordered = tuple(
        sorted(
            selector.candidates,
            key=lambda candidate: (candidate.priority, candidate.candidate_hash),
        )
    )
    endpoint_map = {
        candidate.candidate_hash: candidate.remote_addr for candidate in ordered
    }
    runner = FirstPartyRemoteProbeRunner(
        session=session,
        endpoint_resolver=lambda probe: endpoint_map[probe.probe_id],
    )
    results = []
    attempts: list[DataplaneClientOpenAttempt] = []

    for candidate in ordered:
        result = await runner(candidate.to_probe_spec())
        results.append(result)
        if not result.success:
            continue

        selection_evidence = DataplaneSelectionEvidence(
            candidates=ordered,
            results=tuple(results),
            selected_candidate_hash=candidate.candidate_hash,
            captured_at=captured_at,
        )
        try:
            client = await _open_client_for_candidate(
                session=session,
                selected=candidate,
                selection_evidence=selection_evidence,
            )
        except Exception as exc:
            attempts.append(
                DataplaneClientOpenAttempt.from_candidate(
                    candidate,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
            )
            continue

        attempts.append(
            DataplaneClientOpenAttempt.from_candidate(candidate, opened=True)
        )
        open_evidence = DataplaneClientOpenEvidence(
            selection_evidence=selection_evidence,
            attempts=tuple(attempts),
            selected_candidate_hash=candidate.candidate_hash,
            captured_at=captured_at,
        )
        client.open_evidence = open_evidence
        return client

    selection_evidence = DataplaneSelectionEvidence(
        candidates=ordered,
        results=tuple(results),
        selected_candidate_hash=None,
        captured_at=captured_at,
    )
    open_evidence = DataplaneClientOpenEvidence(
        selection_evidence=selection_evidence,
        attempts=tuple(attempts),
        selected_candidate_hash=None,
        captured_at=captured_at,
    )
    raise FirstPartyDataplaneClientError(
        "no working first-party dataplane endpoint",
        selection_evidence=selection_evidence,
        open_evidence=open_evidence,
    )


async def open_firstparty_admission_dataplane_client(
    *,
    hello: FirstPartyHandshakeHello,
    pqc_material: PqcSessionSecretMaterial,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    captured_at: int,
    camouflage_profile: CamouflageProfile | None = None,
    camouflage_policy: CamouflagePolicy | None = None,
    revocations: RevocationList | None = None,
    completed_at_provider: Callable[[FirstPartyHandshakeAccept], int] | None = None,
    production_gate: PqcMaterialGate | None = None,
) -> FirstPartyDataplaneClient:
    """Open the first endpoint that admits HELLO/ACCEPT and return a live client."""
    ordered = _ordered_unique_candidates(candidates)
    attempts: list[DataplaneClientOpenAttempt] = []
    results: list[DataplaneProbeResult] = []

    for candidate in ordered:
        started = time.perf_counter()
        try:
            client = await _open_admission_client_for_candidate(
                hello=hello,
                pqc_material=pqc_material,
                selected=candidate,
                identity_authority=identity_authority,
                policy=policy,
                camouflage_profile=camouflage_profile,
                camouflage_policy=camouflage_policy,
                revocations=revocations,
                completed_at_provider=(
                    completed_at_provider
                    if completed_at_provider is not None
                    else lambda _accept: captured_at
                ),
                production_gate=production_gate,
            )
        except Exception as exc:
            attempts.append(
                DataplaneClientOpenAttempt.from_candidate(
                    candidate,
                    opened=False,
                    failure_reason=type(exc).__name__,
                )
            )
            results.append(
                _admission_probe_result(
                    candidate,
                    started=started,
                    success=False,
                    failure_reason=type(exc).__name__,
                )
            )
            continue

        attempts.append(DataplaneClientOpenAttempt.from_candidate(candidate, opened=True))
        results.append(
            _admission_probe_result(
                candidate,
                started=started,
                success=True,
                rx_frames=client.stats.rx_frames,
                tx_frames=client.stats.tx_frames,
                rx_bytes=client.stats.rx_bytes,
                tx_bytes=client.stats.tx_bytes,
            )
        )
        selection_evidence = DataplaneSelectionEvidence(
            candidates=ordered,
            results=tuple(results),
            selected_candidate_hash=candidate.candidate_hash,
            captured_at=captured_at,
        )
        open_evidence = DataplaneClientOpenEvidence(
            selection_evidence=selection_evidence,
            attempts=tuple(attempts),
            selected_candidate_hash=candidate.candidate_hash,
            captured_at=captured_at,
        )
        client.selection_evidence = selection_evidence
        client.open_evidence = open_evidence
        return client

    selection_evidence = DataplaneSelectionEvidence(
        candidates=ordered,
        results=tuple(results),
        selected_candidate_hash=None,
        captured_at=captured_at,
    )
    open_evidence = DataplaneClientOpenEvidence(
        selection_evidence=selection_evidence,
        attempts=tuple(attempts),
        selected_candidate_hash=None,
        captured_at=captured_at,
    )
    raise FirstPartyDataplaneClientError(
        "no first-party admission dataplane endpoint accepted HELLO",
        selection_evidence=selection_evidence,
        open_evidence=open_evidence,
    )


async def _open_client_for_candidate(
    *,
    session: SessionContext,
    selected: DataplaneEndpointCandidate,
    selection_evidence: DataplaneSelectionEvidence,
) -> FirstPartyDataplaneClient:
    if selected.transport == "udp":
        udp_transport, udp_client = await open_udp_client(
            session=session,
            remote_addr=selected.remote_addr,
        )
        return FirstPartyDataplaneClient(
            session=session,
            selected=selected,
            selection_evidence=selection_evidence,
            udp_transport=udp_transport,
            udp_client=udp_client,
        )
    if selected.transport == "tcp":
        tcp_client = await open_tcp_client(
            session=session,
            remote_addr=selected.remote_addr,
        )
        return FirstPartyDataplaneClient(
            session=session,
            selected=selected,
            selection_evidence=selection_evidence,
            tcp_client=tcp_client,
        )
    if selected.transport == "camouflage":
        camouflage_client = await open_camouflage_client(
            session=session,
            remote_addr=selected.remote_addr,
            timeout=selected.timeout_seconds,
        )
        return FirstPartyDataplaneClient(
            session=session,
            selected=selected,
            selection_evidence=selection_evidence,
            camouflage_client=camouflage_client,
        )
    raise FirstPartyDataplaneClientError(
        "unsupported first-party dataplane transport",
        selection_evidence=selection_evidence,
    )


async def _open_admission_client_for_candidate(
    *,
    hello: FirstPartyHandshakeHello,
    pqc_material: PqcSessionSecretMaterial,
    selected: DataplaneEndpointCandidate,
    identity_authority: IdentityVerifier,
    policy: ZeroTrustPolicy,
    camouflage_profile: CamouflageProfile | None,
    camouflage_policy: CamouflagePolicy | None,
    revocations: RevocationList | None,
    completed_at_provider: Callable[[FirstPartyHandshakeAccept], int],
    production_gate: PqcMaterialGate | None,
) -> FirstPartyDataplaneClient:
    placeholder_evidence = DataplaneSelectionEvidence(
        candidates=(selected,),
        results=(),
        selected_candidate_hash=selected.candidate_hash,
        captured_at=0,
    )
    if selected.transport == "udp":
        udp_transport, udp_client = await open_udp_admission_client(
            hello=hello,
            pqc_material=pqc_material,
            remote_addr=selected.remote_addr,
            identity_authority=identity_authority,
            policy=policy,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
            production_gate=production_gate,
            timeout=selected.timeout_seconds,
        )
        if udp_client.session is None or udp_client.accept is None:
            raise FirstPartyDataplaneClientError(
                "UDP admission did not complete",
                selection_evidence=placeholder_evidence,
            )
        return FirstPartyDataplaneClient(
            session=udp_client.session,
            selected=selected,
            selection_evidence=placeholder_evidence,
            udp_transport=udp_transport,
            udp_client=udp_client,
            accept=udp_client.accept,
        )
    if selected.transport == "tcp":
        result = await open_tcp_admission_client(
            hello=hello,
            pqc_material=pqc_material,
            remote_addr=selected.remote_addr,
            identity_authority=identity_authority,
            policy=policy,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
            production_gate=production_gate,
            timeout=selected.timeout_seconds,
        )
        return FirstPartyDataplaneClient(
            session=result.session,
            selected=selected,
            selection_evidence=placeholder_evidence,
            tcp_client=result.client,
            accept=result.accept,
        )
    if selected.transport == "camouflage":
        result = await open_camouflage_admission_client(
            hello=hello,
            pqc_material=pqc_material,
            remote_addr=selected.remote_addr,
            identity_authority=identity_authority,
            policy=policy,
            profile=camouflage_profile,
            camouflage_policy=camouflage_policy,
            revocations=revocations,
            completed_at_provider=completed_at_provider,
            production_gate=production_gate,
            timeout=selected.timeout_seconds,
        )
        return FirstPartyDataplaneClient(
            session=result.session,
            selected=selected,
            selection_evidence=placeholder_evidence,
            camouflage_client=result.client,
            accept=result.accept,
        )
    raise FirstPartyDataplaneClientError(
        "unsupported first-party admission transport",
        selection_evidence=placeholder_evidence,
    )


def _ordered_unique_candidates(
    candidates: tuple[DataplaneEndpointCandidate, ...],
) -> tuple[DataplaneEndpointCandidate, ...]:
    if not candidates:
        raise FirstPartyDataplaneClientError(
            "admission dataplane endpoint candidates are required"
        )
    candidate_hashes = [candidate.candidate_hash for candidate in candidates]
    if len(set(candidate_hashes)) != len(candidate_hashes):
        raise FirstPartyDataplaneClientError(
            "admission dataplane endpoint candidate ids must be unique"
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (candidate.priority, candidate.candidate_hash),
        )
    )


def _admission_probe_result(
    candidate: DataplaneEndpointCandidate,
    *,
    started: float,
    success: bool,
    rx_frames: int = 0,
    tx_frames: int = 0,
    rx_bytes: int = 0,
    tx_bytes: int = 0,
    failure_reason: str | None = None,
) -> DataplaneProbeResult:
    return DataplaneProbeResult(
        probe_id=candidate.candidate_hash,
        path_label=candidate.path_label,
        transport=candidate.transport,
        remote_hash=candidate.remote_hash,
        success=success,
        latency_millis=max(0, int((time.perf_counter() - started) * 1000)),
        rx_frames=rx_frames,
        tx_frames=tx_frames,
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
        failure_reason=failure_reason,
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
