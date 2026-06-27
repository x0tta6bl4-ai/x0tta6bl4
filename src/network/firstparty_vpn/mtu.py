"""Live MTU probing policy for first-party VPN transports."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Awaitable, Callable, Literal, Protocol, Sequence

from .camouflage import open_camouflage_client
from .fragmentation import PacketFragmenter
from .protocol import FrameType, MAX_PAYLOAD_BYTES
from .runtime import open_udp_client
from .session import SessionContext
from .stream import open_tcp_client

if TYPE_CHECKING:
    from .dataplane_validation import DataplaneProbeSpec, DataplaneValidationPlan

MTU_PROBE_MAGIC = b"X0MTU1|"
MIN_PROBE_PAYLOAD_BYTES = 64
DataplaneTransport = Literal["udp", "tcp", "camouflage"]


class MtuProbeError(ValueError):
    """Raised when MTU probing cannot produce a safe result."""


class MtuProbeClient(Protocol):
    def send_ping(self, payload: bytes = b"") -> None: ...

    async def recv(self, timeout: float = 1.0): ...


MtuValidationRunner = Callable[
    [object],
    Awaitable["MtuPathProbeResult"],
]


@dataclass(frozen=True)
class MtuProbePolicy:
    """Candidate payload sizes for live path probing."""

    candidates: tuple[int, ...] = (1400, 1280, 1200, 1024, 768, 576)
    timeout: float = 1.0
    attempts_per_size: int = 1
    safety_margin: int = 64
    minimum_payload_size: int = 576

    def __post_init__(self) -> None:
        if not self.candidates:
            raise ValueError("MTU probe candidates are required")
        if self.timeout <= 0:
            raise ValueError("MTU probe timeout must be positive")
        if self.attempts_per_size < 1:
            raise ValueError("MTU probe attempts must be at least 1")
        if self.safety_margin < 0:
            raise ValueError("MTU probe safety margin cannot be negative")
        if self.minimum_payload_size < MIN_PROBE_PAYLOAD_BYTES:
            raise ValueError("MTU probe minimum payload is too small")
        for candidate in self.candidates:
            if candidate < MIN_PROBE_PAYLOAD_BYTES:
                raise ValueError("MTU probe candidate is too small")
            if candidate > MAX_PAYLOAD_BYTES:
                raise ValueError("MTU probe candidate exceeds frame payload limit")

    @property
    def ordered_candidates(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.candidates), reverse=True))


@dataclass(frozen=True)
class MtuProbeAttempt:
    payload_size: int
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class MtuProbeResult:
    selected_payload_size: int
    selected_fragment_payload_size: int
    attempts: tuple[MtuProbeAttempt, ...]

    def __post_init__(self) -> None:
        if self.selected_payload_size < MIN_PROBE_PAYLOAD_BYTES:
            raise MtuProbeError("selected MTU payload is too small")
        if self.selected_fragment_payload_size < MIN_PROBE_PAYLOAD_BYTES:
            raise MtuProbeError("selected MTU fragment payload is too small")
        if self.selected_fragment_payload_size > self.selected_payload_size:
            raise MtuProbeError("selected MTU fragment exceeds selected payload")
        if not self.attempts:
            raise MtuProbeError("MTU result attempts are required")
        if all(not attempt.success for attempt in self.attempts):
            raise MtuProbeError("MTU result requires one successful attempt")

    def fragmenter(self) -> PacketFragmenter:
        return PacketFragmenter(max_payload_size=self.selected_fragment_payload_size)


@dataclass(frozen=True)
class MtuPathProbeResult:
    """Payload-free evidence for one path-specific MTU probe."""

    probe_id: str
    path_label: str
    transport: DataplaneTransport
    remote_hash: str
    success: bool
    attempted_payload_sizes: tuple[int, ...] = ()
    failed_attempt_count: int = 0
    selected_payload_size: int | None = None
    selected_fragment_payload_size: int | None = None
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.probe_id.strip():
            raise MtuProbeError("MTU path probe id is required")
        if not self.path_label.strip():
            raise MtuProbeError("MTU path label is required")
        if self.transport not in ("udp", "tcp", "camouflage"):
            raise MtuProbeError("MTU path transport must be udp, tcp, or camouflage")
        if not self.remote_hash.strip():
            raise MtuProbeError("MTU path remote hash is required")
        if any(size < MIN_PROBE_PAYLOAD_BYTES for size in self.attempted_payload_sizes):
            raise MtuProbeError("MTU attempted payload is too small")
        if self.failed_attempt_count < 0:
            raise MtuProbeError("MTU failed attempt count cannot be negative")
        if self.failed_attempt_count > len(self.attempted_payload_sizes):
            raise MtuProbeError("MTU failed attempts exceed attempts")
        if self.success:
            if self.failure_reason is not None:
                raise MtuProbeError("successful MTU path result has failure reason")
            if self.selected_payload_size is None:
                raise MtuProbeError("successful MTU path result requires payload size")
            if self.selected_fragment_payload_size is None:
                raise MtuProbeError("successful MTU path result requires fragment size")
            if self.selected_payload_size < MIN_PROBE_PAYLOAD_BYTES:
                raise MtuProbeError("successful MTU payload is too small")
            if self.selected_fragment_payload_size < MIN_PROBE_PAYLOAD_BYTES:
                raise MtuProbeError("successful MTU fragment payload is too small")
            if self.selected_fragment_payload_size > self.selected_payload_size:
                raise MtuProbeError("successful MTU fragment exceeds payload")
            if self.selected_payload_size not in self.attempted_payload_sizes:
                raise MtuProbeError("successful MTU payload was not attempted")
        else:
            if not (self.failure_reason or "").strip():
                raise MtuProbeError("failed MTU path result requires reason")
            if (
                self.selected_payload_size is not None
                or self.selected_fragment_payload_size is not None
            ):
                raise MtuProbeError("failed MTU path result cannot select sizes")

    @classmethod
    def success_result(
        cls,
        spec: DataplaneProbeSpec,
        result: MtuProbeResult,
    ) -> "MtuPathProbeResult":
        return cls(
            probe_id=spec.probe_id,
            path_label=spec.path_label,
            transport=spec.transport,
            remote_hash=spec.remote_hash,
            success=True,
            attempted_payload_sizes=tuple(
                attempt.payload_size for attempt in result.attempts
            ),
            failed_attempt_count=sum(1 for attempt in result.attempts if not attempt.success),
            selected_payload_size=result.selected_payload_size,
            selected_fragment_payload_size=result.selected_fragment_payload_size,
        )

    @classmethod
    def failure_result(
        cls,
        spec: DataplaneProbeSpec,
        *,
        reason: str,
        attempted_payload_sizes: tuple[int, ...] = (),
        failed_attempt_count: int | None = None,
    ) -> "MtuPathProbeResult":
        return cls(
            probe_id=spec.probe_id,
            path_label=spec.path_label,
            transport=spec.transport,
            remote_hash=spec.remote_hash,
            success=False,
            attempted_payload_sizes=attempted_payload_sizes,
            failed_attempt_count=(
                len(attempted_payload_sizes)
                if failed_attempt_count is None
                else failed_attempt_count
            ),
            failure_reason=reason,
        )

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "attempted_payload_sizes": list(self.attempted_payload_sizes),
            "failed_attempt_count": self.failed_attempt_count,
            "path_label": self.path_label,
            "probe_id": self.probe_id,
            "remote_hash": self.remote_hash,
            "selected_fragment_payload_size": self.selected_fragment_payload_size,
            "selected_payload_size": self.selected_payload_size,
            "success": self.success,
            "transport": self.transport,
        }
        if self.failure_reason is not None:
            payload["failure_reason"] = self.failure_reason
        _assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class MtuValidationEvidence:
    """Privacy-safe evidence that required paths have probed MTU policy."""

    plan_hash: str
    results: tuple[MtuPathProbeResult, ...]
    required_path_labels: frozenset[str]
    min_successful_paths: int
    captured_at: int

    def __post_init__(self) -> None:
        if not self.results:
            raise MtuProbeError("MTU validation results are required")
        if not self.required_path_labels:
            raise MtuProbeError("MTU validation required paths are required")
        if self.min_successful_paths < 1:
            raise MtuProbeError("MTU validation minimum success count is invalid")
        if self.captured_at < 0:
            raise MtuProbeError("MTU validation capture time cannot be negative")
        if len(self.plan_hash) != 64:
            raise MtuProbeError("MTU validation plan hash must be sha256 hex")
        probe_ids = [result.probe_id for result in self.results]
        if len(set(probe_ids)) != len(probe_ids):
            raise MtuProbeError("MTU validation result probe ids must be unique")

    @classmethod
    def from_results(
        cls,
        *,
        plan: DataplaneValidationPlan,
        results: tuple[MtuPathProbeResult, ...],
        captured_at: int,
    ) -> "MtuValidationEvidence":
        expected = {probe.probe_id: probe for probe in plan.probes}
        for result in results:
            try:
                probe = expected[result.probe_id]
            except KeyError as exc:
                raise MtuProbeError("MTU validation result probe id is not in plan") from exc
            if result.path_label != probe.path_label:
                raise MtuProbeError("MTU validation result path mismatch")
            if result.transport != probe.transport:
                raise MtuProbeError("MTU validation result transport mismatch")
            if result.remote_hash != probe.remote_hash:
                raise MtuProbeError("MTU validation result remote hash mismatch")
        return cls(
            plan_hash=_mtu_plan_hash(plan),
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
            f"mtu_probe_failed:{result.probe_id}:{result.failure_reason}"
            for result in self.results
            if not result.success
        ]
        for path in sorted(self.required_path_labels - set(self.covered_path_labels)):
            reasons.append(f"mtu_required_path_missing:{path}")
        if self.successful_path_count < self.min_successful_paths:
            reasons.append("mtu_success_count_below_required")
        return tuple(reasons)

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-mtu-validation-v1" + _canonical_json(self.to_json_dict())
        ).hexdigest()

    def probe_matrix_hash(self) -> str:
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
        _assert_privacy_safe(payload)
        return payload


@dataclass
class PathMtuCache:
    """Small in-memory cache for path-specific MTU probe results."""

    results: dict[str, MtuProbeResult] = field(default_factory=dict)

    def remember(self, path_id: str, result: MtuProbeResult) -> None:
        if not path_id:
            raise ValueError("MTU path id is required")
        self.results[path_id] = result

    def get(self, path_id: str) -> MtuProbeResult | None:
        return self.results.get(path_id)

    def fragmenter_for(self, path_id: str) -> PacketFragmenter | None:
        result = self.get(path_id)
        if result is None:
            return None
        return result.fragmenter()


def mtu_path_id(*, transport: str, host: str, port: int) -> str:
    if not transport:
        raise ValueError("MTU transport name is required")
    if not host:
        raise ValueError("MTU host is required")
    if not 1 <= port <= 65535:
        raise ValueError("MTU port must be between 1 and 65535")
    digest = hashlib.sha256(f"{transport}|{host}|{port}".encode("utf-8")).hexdigest()
    return f"{transport}:{digest[:16]}"


@dataclass(frozen=True)
class FirstPartyRemoteMtuProbeRunner:
    """Probe MTU against already-running first-party endpoints."""

    session: SessionContext
    endpoint_resolver: Callable[["DataplaneProbeSpec"], tuple[str, int]]
    policy: MtuProbePolicy = field(default_factory=MtuProbePolicy)

    async def __call__(self, probe: DataplaneProbeSpec) -> MtuPathProbeResult:
        try:
            remote_addr = _validate_remote_addr(self.endpoint_resolver(probe))
            if probe.transport == "udp":
                result = await self._probe_udp(remote_addr)
            elif probe.transport == "tcp":
                result = await self._probe_tcp(remote_addr)
            elif probe.transport == "camouflage":
                result = await self._probe_camouflage(remote_addr)
            else:
                return MtuPathProbeResult.failure_result(
                    probe,
                    reason="unsupported_transport",
                )
            return MtuPathProbeResult.success_result(probe, result)
        except Exception as exc:
            return MtuPathProbeResult.failure_result(
                probe,
                reason=(
                    "timeout"
                    if isinstance(exc, (TimeoutError, asyncio.TimeoutError))
                    else type(exc).__name__
                ),
            )

    async def _probe_udp(self, remote_addr: tuple[str, int]) -> MtuProbeResult:
        client_transport = None
        try:
            client_transport, client = await open_udp_client(
                session=self.session,
                remote_addr=remote_addr,
            )
            return await probe_firstparty_mtu(client, policy=self.policy)
        finally:
            if client_transport is not None:
                client_transport.close()

    async def _probe_tcp(self, remote_addr: tuple[str, int]) -> MtuProbeResult:
        client = None
        try:
            client = await open_tcp_client(
                session=self.session,
                remote_addr=remote_addr,
            )
            return await probe_firstparty_mtu(client, policy=self.policy)
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()

    async def _probe_camouflage(self, remote_addr: tuple[str, int]) -> MtuProbeResult:
        client = None
        try:
            client = await open_camouflage_client(
                session=self.session,
                remote_addr=remote_addr,
                timeout=self.policy.timeout,
            )
            return await probe_firstparty_mtu(client, policy=self.policy)
        finally:
            if client is not None:
                client.close()
                await client.wait_closed()


async def evaluate_mtu_validation(
    *,
    plan: DataplaneValidationPlan,
    runner: MtuValidationRunner,
    captured_at: int,
) -> MtuValidationEvidence:
    """Run path-specific MTU probes and return privacy-safe rollout evidence."""
    results: list[MtuPathProbeResult] = []
    for probe in plan.probes:
        try:
            result = await runner(probe)
        except Exception as exc:
            result = MtuPathProbeResult.failure_result(
                probe,
                reason=type(exc).__name__,
            )
        if result.probe_id != probe.probe_id:
            raise MtuProbeError("MTU runner returned wrong probe id")
        if result.remote_hash != probe.remote_hash:
            raise MtuProbeError("MTU runner returned wrong remote hash")
        results.append(result)
    return MtuValidationEvidence.from_results(
        plan=plan,
        results=tuple(results),
        captured_at=captured_at,
    )


async def probe_firstparty_mtu(
    client: MtuProbeClient,
    *,
    policy: MtuProbePolicy | None = None,
) -> MtuProbeResult:
    active_policy = policy or MtuProbePolicy()
    attempts: list[MtuProbeAttempt] = []
    for candidate in active_policy.ordered_candidates:
        ok = True
        error: str | None = None
        for attempt_index in range(active_policy.attempts_per_size):
            payload = _probe_payload(candidate, attempt_index)
            try:
                client.send_ping(payload)
                drain = getattr(client, "drain", None)
                if drain is not None:
                    await drain()
                frame = await client.recv(timeout=active_policy.timeout)
                if frame.frame_type != FrameType.PONG or frame.payload != payload:
                    ok = False
                    error = "unexpected probe response"
                    break
            except Exception as exc:  # pragma: no cover - exact transport errors vary
                ok = False
                error = exc.__class__.__name__
                break
        attempts.append(MtuProbeAttempt(candidate, ok, error))
        if ok:
            fragment_payload = max(
                active_policy.minimum_payload_size,
                candidate - active_policy.safety_margin,
            )
            return MtuProbeResult(
                selected_payload_size=candidate,
                selected_fragment_payload_size=fragment_payload,
                attempts=tuple(attempts),
            )
    raise MtuProbeError("MTU probing failed for every candidate")


def _probe_payload(size: int, attempt_index: int) -> bytes:
    if size < MIN_PROBE_PAYLOAD_BYTES:
        raise ValueError("MTU probe payload is too small")
    prefix = MTU_PROBE_MAGIC + attempt_index.to_bytes(2, "big") + b"|"
    return prefix + (b"x" * (size - len(prefix)))


def _mtu_plan_hash(plan: DataplaneValidationPlan) -> str:
    payload = {
        "min_successful_paths": plan.min_successful_probes,
        "probes": [probe.to_json_dict() for probe in plan.probes],
        "required_path_labels": sorted(plan.required_path_labels),
        "validation_kind": "mtu",
        "version": 1,
    }
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _probe_matrix_hash(
    results: tuple[MtuPathProbeResult, ...],
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
    _assert_privacy_safe(payload)
    return hashlib.sha256(
        b"x0vpn-dataplane-probe-matrix-v1" + _canonical_json(payload)
    ).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _assert_privacy_safe(value: object) -> None:
    from .ops import assert_privacy_safe

    assert_privacy_safe(value)


def _validate_remote_addr(remote_addr: tuple[str, int]) -> tuple[str, int]:
    host, port = remote_addr
    if not isinstance(host, str) or not host.strip():
        raise MtuProbeError("MTU remote host is invalid")
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise MtuProbeError("MTU remote port is invalid")
    return host, port
