"""Adapters that feed bounded dataplane proof into mesh recovery."""

from __future__ import annotations

import asyncio
import inspect
import threading
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from src.coordination.events import EventBus


RECOVERY_DATAPLANE_PROBE_CLAIM_BOUNDARY = (
    "Recovery dataplane probe adapter metadata only. It normalizes an existing "
    "bounded dataplane probe result into redacted EventBus evidence references "
    "for recovery claim gates; it does not expose raw targets or prove customer "
    "traffic."
)
RECOVERY_DATAPLANE_PROBE_CLAIM_GATE_SCHEMA = (
    "x0tta6bl4.recovery_dataplane_probe.claim_gate.v1"
)

ProbeCallable = Callable[..., Mapping[str, Any] | Awaitable[Mapping[str, Any]]]


def _run_awaitable_sync(awaitable: Awaitable[Any]) -> Any:
    """Run an awaitable from sync recovery code without assuming loop ownership."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    holder: dict[str, Any] = {}

    def _runner() -> None:
        try:
            holder["value"] = asyncio.run(awaitable)
        except Exception as exc:  # pragma: no cover - exercised by caller path
            holder["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in holder:
        raise holder["error"]
    return holder.get("value")


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _safe_nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _normalize_evidence(value: Any, *, fallback_boundary: str) -> dict[str, Any]:
    evidence = dict(value) if isinstance(value, Mapping) else {}
    event_ids = _safe_text_list(evidence.get("event_ids"))
    source_agents = _safe_text_list(evidence.get("source_agents"))
    claim_boundaries = _safe_text_list(evidence.get("claim_boundaries"))
    if not claim_boundaries and evidence.get("claim_boundary"):
        claim_boundaries = [str(evidence["claim_boundary"])]
    if not claim_boundaries:
        claim_boundaries = [fallback_boundary]
    return {
        "source_agents": source_agents,
        "event_ids": event_ids,
        "events_total": _safe_nonnegative_int(
            evidence.get("events_total"),
            default=len(event_ids),
        ),
        "event_ids_count": len(event_ids),
        "claim_boundaries": claim_boundaries,
        "claim_boundaries_total": _safe_nonnegative_int(
            evidence.get("claim_boundaries_total"),
            default=len(claim_boundaries),
        ),
        "redacted": evidence.get("redacted") is True,
    }


def _probe_claim_gate(
    *,
    dataplane_confirmed: bool,
    evidence: Mapping[str, Any],
    claim_boundary: str,
) -> dict[str, Any]:
    blockers: list[str] = []
    if not dataplane_confirmed:
        blockers.append("bounded_dataplane_probe_not_confirmed")
    if int(evidence.get("event_ids_count") or 0) <= 0 or int(
        evidence.get("events_total") or 0
    ) <= 0:
        blockers.append("dataplane_probe_event_evidence_missing")
    if not evidence.get("source_agents"):
        blockers.append("dataplane_probe_source_agent_missing")
    if evidence.get("redacted") is not True:
        blockers.append("dataplane_probe_evidence_not_redacted")

    bounded_probe_allowed = not blockers
    return {
        "schema": RECOVERY_DATAPLANE_PROBE_CLAIM_GATE_SCHEMA,
        "decision": (
            "BOUNDED_DATAPLANE_PROBE_CLAIM_ALLOWED"
            if bounded_probe_allowed
            else "DATAPLANE_PROBE_LIFECYCLE_ONLY"
        ),
        "bounded_dataplane_probe_claim_allowed": bounded_probe_allowed,
        "dataplane_confirmed": dataplane_confirmed,
        "eventbus_evidence_present": bool(evidence.get("event_ids")),
        "source_agent_present": bool(evidence.get("source_agents")),
        "evidence_redacted": evidence.get("redacted") is True,
        "restored_dataplane_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": blockers,
        "claim_boundary": claim_boundary,
        "redacted": True,
    }


def normalize_recovery_dataplane_probe_result(
    value: Any,
    *,
    claim_boundary: str = RECOVERY_DATAPLANE_PROBE_CLAIM_BOUNDARY,
) -> dict[str, Any]:
    """Return the strict recovery dataplane probe shape without raw targets."""

    raw = dict(value) if isinstance(value, Mapping) else {}
    evidence = _normalize_evidence(
        raw.get("evidence"),
        fallback_boundary=str(raw.get("claim_boundary") or claim_boundary),
    )
    dataplane_confirmed = bool(
        raw.get("dataplane_confirmed") is True
        or (
            raw.get("status") == "ok"
            and (
                raw.get("latency_ms") is not None
                or raw.get("packet_loss_percent") is not None
            )
        )
    )
    effective_claim_boundary = str(raw.get("claim_boundary") or claim_boundary)
    return {
        "status": "ok" if dataplane_confirmed else "error",
        "dataplane_confirmed": dataplane_confirmed,
        "latency_ms": raw.get("latency_ms"),
        "packet_loss_percent": raw.get("packet_loss_percent"),
        "jitter_ms": raw.get("jitter_ms"),
        "evidence": evidence,
        "claim_gate": _probe_claim_gate(
            dataplane_confirmed=dataplane_confirmed,
            evidence=evidence,
            claim_boundary=effective_claim_boundary,
        ),
        "claim_boundary": effective_claim_boundary,
        "raw_target_redacted": True,
        "payloads_redacted": True,
        "redacted": True,
    }


class RecoveryDataplanePingProbe:
    """Sync callable adapter around real_network_adapter.probe_peer_dataplane_ping."""

    def __init__(
        self,
        target: str,
        *,
        event_bus: EventBus | None = None,
        event_project_root: str = ".",
        count: int = 2,
        timeout_seconds: int = 1,
        output_preview_limit: int = 0,
        probe_func: ProbeCallable | None = None,
    ) -> None:
        self.target = target
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.count = count
        self.timeout_seconds = timeout_seconds
        self.output_preview_limit = output_preview_limit
        self.probe_func = probe_func

    def __call__(self) -> dict[str, Any]:
        probe_func = self.probe_func
        if probe_func is None:
            from src.mesh.real_network_adapter import probe_peer_dataplane_ping

            probe_func = probe_peer_dataplane_ping

        raw_result = probe_func(
            self.target,
            event_bus=self.event_bus,
            event_project_root=self.event_project_root,
            count=self.count,
            timeout_seconds=self.timeout_seconds,
            output_preview_limit=self.output_preview_limit,
        )
        if inspect.isawaitable(raw_result):
            raw_result = _run_awaitable_sync(raw_result)
        return normalize_recovery_dataplane_probe_result(raw_result)


def build_recovery_dataplane_ping_probe(
    target: str,
    *,
    event_bus: EventBus | None = None,
    event_project_root: str = ".",
    count: int = 2,
    timeout_seconds: int = 1,
    output_preview_limit: int = 0,
    probe_func: ProbeCallable | None = None,
) -> RecoveryDataplanePingProbe:
    """Build a recovery-compatible dataplane probe from the shared ping probe."""

    return RecoveryDataplanePingProbe(
        target,
        event_bus=event_bus,
        event_project_root=event_project_root,
        count=count,
        timeout_seconds=timeout_seconds,
        output_preview_limit=output_preview_limit,
        probe_func=probe_func,
    )
