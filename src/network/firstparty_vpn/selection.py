"""Privacy-safe first-party dataplane endpoint selection and failover."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from .dataplane_validation import (
    DataplaneProbeResult,
    DataplaneProbeSpec,
    DataplaneTransport,
    FirstPartyRemoteProbeRunner,
    FirstPartyRemoteTunProbeRunner,
    TunDataplaneProbeResult,
)
from .ops import assert_privacy_safe, hash_identifier
from .session import SessionContext


class DataplaneSelectionError(ValueError):
    """Raised when dataplane endpoint selection input is invalid."""


@dataclass(frozen=True)
class DataplaneEndpointCandidate:
    """One in-memory endpoint candidate; raw host/port are never serialized."""

    candidate_id: str
    path_label: str
    transport: DataplaneTransport
    remote_ref: str
    remote_addr: tuple[str, int]
    priority: int = 100
    payload_size: int = 64
    timeout_seconds: float = 1.0

    def __post_init__(self) -> None:
        if not self.candidate_id.strip():
            raise DataplaneSelectionError("dataplane candidate id is required")
        if not self.path_label.strip():
            raise DataplaneSelectionError("dataplane candidate path label is required")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise DataplaneSelectionError(
                "dataplane candidate transport must be udp, tcp, or camouflage"
            )
        if not self.remote_ref.strip():
            raise DataplaneSelectionError("dataplane candidate remote reference is required")
        if self.priority < 0:
            raise DataplaneSelectionError("dataplane candidate priority cannot be negative")
        if self.payload_size < 1:
            raise DataplaneSelectionError("dataplane candidate payload size must be positive")
        if self.timeout_seconds <= 0:
            raise DataplaneSelectionError("dataplane candidate timeout must be positive")
        host, port = self.remote_addr
        if not isinstance(host, str) or not host.strip():
            raise DataplaneSelectionError("dataplane candidate remote host is invalid")
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise DataplaneSelectionError("dataplane candidate remote port is invalid")

    @property
    def candidate_hash(self) -> str:
        return hash_identifier(self.candidate_id, namespace="dataplane-candidate")

    @property
    def remote_hash(self) -> str:
        return hash_identifier(self.remote_ref, namespace="dataplane-remote")

    def to_probe_spec(self) -> DataplaneProbeSpec:
        return DataplaneProbeSpec(
            probe_id=self.candidate_hash,
            path_label=self.path_label,
            transport=self.transport,
            remote_ref=self.remote_ref,
            payload_size=self.payload_size,
            timeout_seconds=self.timeout_seconds,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "candidate_hash": self.candidate_hash,
            "path_label": self.path_label,
            "priority": self.priority,
            "remote_hash": self.remote_hash,
            "timeout_millis": int(self.timeout_seconds * 1000),
            "transport": self.transport,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class DataplaneSelectionEvidence:
    """Payload-free evidence for automatic endpoint selection."""

    candidates: tuple[DataplaneEndpointCandidate, ...]
    results: tuple[DataplaneProbeResult, ...]
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
            f"dataplane_candidate_failed:{result.probe_id}:{result.failure_reason}"
            for result in self.results
            if not result.success
        ) or ("dataplane_candidate_missing",)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-dataplane-selection-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "candidates": [candidate.to_json_dict() for candidate in self.candidates],
            "captured_at": self.captured_at,
            "failed_reasons": list(self.failed_reasons),
            "passed": self.passed,
            "results": [result.to_json_dict() for result in self.results],
            "selected_candidate_hash": self.selected_candidate_hash,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class DataplaneSelectionOutcome:
    """Selection result; selected raw endpoint stays in memory only."""

    selected: DataplaneEndpointCandidate | None
    evidence: DataplaneSelectionEvidence

    @property
    def passed(self) -> bool:
        return self.selected is not None and self.evidence.passed


@dataclass(frozen=True)
class TunDataplaneSelectionEvidence:
    """Payload-free evidence for TUN-packet based endpoint selection."""

    candidates: tuple[DataplaneEndpointCandidate, ...]
    results: tuple[TunDataplaneProbeResult, ...]
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
            f"tun_dataplane_candidate_failed:{result.probe_id}:{result.failure_reason}"
            for result in self.results
            if not result.success
        ) or ("tun_dataplane_candidate_missing",)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-tun-dataplane-selection-v1"
            + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "candidates": [candidate.to_json_dict() for candidate in self.candidates],
            "captured_at": self.captured_at,
            "failed_reasons": list(self.failed_reasons),
            "passed": self.passed,
            "results": [result.to_json_dict() for result in self.results],
            "selected_candidate_hash": self.selected_candidate_hash,
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class TunDataplaneSelectionOutcome:
    """TUN packet selection result; raw endpoint stays in memory only."""

    selected: DataplaneEndpointCandidate | None
    evidence: TunDataplaneSelectionEvidence

    @property
    def passed(self) -> bool:
        return self.selected is not None and self.evidence.passed


@dataclass(frozen=True)
class FirstPartyDataplaneSelector:
    """Try first-party endpoint candidates by priority and select the first success."""

    session: SessionContext
    candidates: tuple[DataplaneEndpointCandidate, ...]

    def __post_init__(self) -> None:
        if not self.candidates:
            raise DataplaneSelectionError("dataplane endpoint candidates are required")
        candidate_hashes = [candidate.candidate_hash for candidate in self.candidates]
        if len(set(candidate_hashes)) != len(candidate_hashes):
            raise DataplaneSelectionError("dataplane endpoint candidate ids must be unique")

    async def select(self, *, captured_at: int) -> DataplaneSelectionOutcome:
        ordered = tuple(
            sorted(
                self.candidates,
                key=lambda candidate: (candidate.priority, candidate.candidate_hash),
            )
        )
        endpoint_map = {
            candidate.candidate_hash: candidate.remote_addr for candidate in ordered
        }
        runner = FirstPartyRemoteProbeRunner(
            session=self.session,
            endpoint_resolver=lambda probe: endpoint_map[probe.probe_id],
        )
        results: list[DataplaneProbeResult] = []
        selected: DataplaneEndpointCandidate | None = None

        for candidate in ordered:
            result = await runner(candidate.to_probe_spec())
            results.append(result)
            if result.success:
                selected = candidate
                break

        selected_hash = selected.candidate_hash if selected is not None else None
        evidence = DataplaneSelectionEvidence(
            candidates=ordered,
            results=tuple(results),
            selected_candidate_hash=selected_hash,
            captured_at=captured_at,
        )
        return DataplaneSelectionOutcome(selected=selected, evidence=evidence)


@dataclass(frozen=True)
class FirstPartyTunDataplaneSelector:
    """Try candidates by priority and select the first real protected TUN round trip."""

    session: SessionContext
    candidates: tuple[DataplaneEndpointCandidate, ...]
    tun_mtu: int = 1400
    fragment_payload_size: int = 512

    def __post_init__(self) -> None:
        if not self.candidates:
            raise DataplaneSelectionError("TUN dataplane endpoint candidates are required")
        candidate_hashes = [candidate.candidate_hash for candidate in self.candidates]
        if len(set(candidate_hashes)) != len(candidate_hashes):
            raise DataplaneSelectionError(
                "TUN dataplane endpoint candidate ids must be unique"
            )
        if self.tun_mtu < 576:
            raise DataplaneSelectionError("TUN dataplane MTU must be at least 576")
        if self.fragment_payload_size < 1:
            raise DataplaneSelectionError(
                "TUN dataplane fragment payload size must be positive"
            )

    async def select(self, *, captured_at: int) -> TunDataplaneSelectionOutcome:
        ordered = _ordered_candidates(self.candidates)
        endpoint_map = {
            candidate.candidate_hash: candidate.remote_addr for candidate in ordered
        }
        runner = FirstPartyRemoteTunProbeRunner(
            session=self.session,
            endpoint_resolver=lambda probe: endpoint_map[probe.probe_id],
            tun_mtu=self.tun_mtu,
            fragment_payload_size=self.fragment_payload_size,
        )
        results: list[TunDataplaneProbeResult] = []
        selected: DataplaneEndpointCandidate | None = None

        for candidate in ordered:
            result = await runner(candidate.to_probe_spec())
            results.append(result)
            if result.success:
                selected = candidate
                break

        selected_hash = selected.candidate_hash if selected is not None else None
        evidence = TunDataplaneSelectionEvidence(
            candidates=ordered,
            results=tuple(results),
            selected_candidate_hash=selected_hash,
            captured_at=captured_at,
        )
        return TunDataplaneSelectionOutcome(selected=selected, evidence=evidence)


async def select_firstparty_dataplane_endpoint(
    *,
    session: SessionContext,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    captured_at: int,
) -> DataplaneSelectionOutcome:
    """Select the first working first-party dataplane endpoint by priority."""
    return await FirstPartyDataplaneSelector(
        session=session,
        candidates=candidates,
    ).select(captured_at=captured_at)


async def select_firstparty_tun_dataplane_endpoint(
    *,
    session: SessionContext,
    candidates: tuple[DataplaneEndpointCandidate, ...],
    captured_at: int,
    tun_mtu: int = 1400,
    fragment_payload_size: int = 512,
) -> TunDataplaneSelectionOutcome:
    """Select the first endpoint that carries real protected TUN packets."""
    return await FirstPartyTunDataplaneSelector(
        session=session,
        candidates=candidates,
        tun_mtu=tun_mtu,
        fragment_payload_size=fragment_payload_size,
    ).select(captured_at=captured_at)


def _ordered_candidates(
    candidates: tuple[DataplaneEndpointCandidate, ...],
) -> tuple[DataplaneEndpointCandidate, ...]:
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (candidate.priority, candidate.candidate_hash),
        )
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
