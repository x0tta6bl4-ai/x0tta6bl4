# src/core/mape_k_loop.py
import asyncio
import hashlib
import inspect
import json
import logging
import math
import time
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List

# TD-008: MAPE-K duplication resolution
warnings.warn(
    "src.core.mape_k_loop is deprecated and will be removed. "
    "Please use src.self_healing.mape_k.SelfHealingManager instead.",
    DeprecationWarning,
    stacklevel=2,
)

from ..coordination.events import EventBus, EventType, get_event_bus
from ..dao.ipfs_logger import DAOAuditLogger
from ..integration.spine import (
    AsyncSafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from ..mesh.metric_evidence_policy import (
    MESH_METRIC_POLICY_KEY,
    build_mesh_metric_evidence_policy,
    mesh_metric_policy_allows_high_risk,
    mesh_metric_policy_context,
    safe_mesh_metric_evidence_policy,
)
from ..mesh.network_manager import MeshNetworkManager
from ..mesh.recovery_contracts import build_post_action_dataplane_claim_gate
from ..mesh.recovery_orchestrator import MeshRecoveryOrchestrator
from ..monitoring.prometheus_client import PrometheusExporter
from ..security.zero_trust import ZeroTrustValidator
from ..services.service_event_identity import service_event_identity
from .consciousness import ConsciousnessEngine, ConsciousnessMetrics

# Configure logging
logging.basicConfig(level=logging.INFO)

# Optional imports with graceful fallback
try:
    from src.monitoring.opentelemetry_tracing import get_mapek_spans
except ImportError:
    get_mapek_spans = None

try:
    from src.database import SessionLocal, MeshNode

    DATABASE_AVAILABLE = True
except ImportError:
    SessionLocal = None
    MeshNode = None
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "core-mapek-loop"
_SERVICE_LAYER = "core_mapek_control_spine"
_MAPEK_RESOURCES = {
    "monitor": "core:mapek:monitor",
    "set_route_preference": "core:mapek:execute:set_route_preference",
    "enforce_mesh_optimization": "core:mapek:execute:mesh_optimization",
    "trigger_aggressive_healing": "core:mapek:execute:aggressive_healing",
    "trigger_preemptive_checks": "core:mapek:execute:preemptive_healing",
    "handle_scaling": "core:mapek:execute:scaling",
    "dispatch_dao_action": "core:mapek:execute:dao_action",
    "enter_safe_mode": "core:mapek:safe_mode",
}
_SAFE_ROUTE_PREFERENCES = {"low_latency", "reliability", "balanced"}
_CLAIM_BOUNDARY_LIMIT = 8
_CLAIM_BOUNDARY_TEXT_LIMIT = 400
_MESH_HIGH_RISK_DIRECTIVE_ACTIONS = {
    "enable_aggressive_healing": "aggressive_healing",
    "preemptive_healing": "preemptive_healing",
}
_MESH_HIGH_RISK_ACTION_OPERATIONS = {
    "aggressive_healing": "trigger_aggressive_healing",
    "preemptive_healing": "trigger_preemptive_checks",
    "mesh_optimization": "enforce_mesh_optimization",
}
_DOWNSTREAM_TERMINAL_EVENT_TYPES = (
    EventType.PIPELINE_STAGE_END,
    EventType.TASK_COMPLETED,
    EventType.TASK_FAILED,
    EventType.TASK_BLOCKED,
)
MAPEK_LOOP_CONTROL_CLAIM_BOUNDARY = (
    "MAPE-K control-spine event only. It records local monitor/execute phase "
    "decisions, service identity presence, safe-actuator state, bounded numeric "
    "summaries, downstream evidence event IDs, and mesh metric source provenance "
    "when available. It does not expose raw node IDs, peer addresses, route tables, "
    "DAO action payloads, raw exceptions, or prove that a remote recovery actually "
    "changed live network state."
)
MAPEK_POST_ACTION_DATAPLANE_CLAIM_BOUNDARY = (
    "MAPE-K healing action evidence records local control-action execution and "
    "downstream EventBus references only. A successful local healing call does not "
    "prove restored dataplane behavior, live customer traffic, external reachability, "
    "production SLOs, or production readiness without a bounded post-action "
    "dataplane probe whose nested claim gate allows the restored-dataplane claim."
)
MAPEK_SAFE_MODE_CLAIM_BOUNDARY = (
    "MAPE-K safe-mode evidence records a local fail-closed control decision only. "
    "Safe-mode blocks route, healing, scaling, DAO dispatch, and production-ready "
    "claims until a trusted operator or recovery path clears the underlying "
    "planning, knowledge, or CID-layer fault."
)
MAPEK_RECOVERY_PLAN_CID_CLAIM_BOUNDARY = (
    "Content-addressed MAPE-K recovery plan metadata only. The CID binds the "
    "local redacted directive plan to a deterministic digest; it does not prove "
    "that the plan was executed, restored dataplane behavior, live customer "
    "traffic, external reachability, or production readiness."
)


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_SERVICE_AGENT)
    return {
        "service_name": _SERVICE_AGENT,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _event_bus_or_none(
    event_bus: EventBus | None,
    event_project_root: str,
) -> EventBus | None:
    if event_bus is not None:
        return event_bus
    try:
        return get_event_bus(event_project_root)
    except Exception as exc:
        logger.error("Failed to initialize core MAPE-K EventBus: %s", exc)
        return None


def _sha256_text(value: str) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _json_safe_plan_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return {"truncated": True, "type": type(value).__name__}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_safe_plan_value(nested, depth=depth + 1)
            for key, nested in sorted(value.items(), key=lambda item: str(item[0]))
            if str(key) != "recovery_plan_cid"
        }
    if isinstance(value, (list, tuple, set)):
        return [
            _json_safe_plan_value(item, depth=depth + 1)
            for item in list(value)[:100]
        ]
    redacted = repr(value)
    return {
        "type": type(value).__name__,
        "sha256": _sha256_text(redacted),
        "redacted": True,
    }


def _canonical_recovery_plan_bytes(directives: Dict[str, Any]) -> bytes:
    envelope = {
        "schema": "x0tta6bl4.core_mapek.recovery_plan_canonical.v1",
        "plan": _json_safe_plan_value(directives),
    }
    return json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _content_addressed_recovery_plan_metadata(
    directives: Dict[str, Any],
) -> Dict[str, Any]:
    canonical = _canonical_recovery_plan_bytes(directives)
    plan_sha256 = hashlib.sha256(canonical).hexdigest()
    base: Dict[str, Any] = {
        "schema": "x0tta6bl4.core_mapek.recovery_plan_cid.v1",
        "claim_boundary": MAPEK_RECOVERY_PLAN_CID_CLAIM_BOUNDARY,
        "plan_sha256": plan_sha256,
        "canonical_bytes": len(canonical),
        "cid_version": 1,
        "codec": "raw",
        "multicodec": "raw",
        "multihash": "sha2-256",
        "plan_execution_claim_allowed": False,
        "restored_dataplane_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "redacted": True,
    }
    try:
        import cid
        import multicodec
        import multihash

        if not multicodec.is_codec("raw"):
            raise ValueError("raw_multicodec_unavailable")
        digest = multihash.digest(canonical, "sha2-256").encode()
        plan_cid = str(cid.make_cid(1, "raw", digest))
        if not cid.is_cid(plan_cid):
            raise ValueError("cid_roundtrip_failed")
        return {
            **base,
            "status": "cid_attached",
            "plan_cid": plan_cid,
            "safe_mode_required": False,
            "blockers": [],
        }
    except Exception as exc:
        return {
            **base,
            "status": "cid_generation_failed",
            "plan_cid": None,
            "safe_mode_required": True,
            "failure_reason_id": "recovery_plan_cid_generation_failed",
            "error_type": type(exc).__name__,
            "blockers": ["recovery_plan_cid_generation_failed"],
        }


def _safe_recovery_plan_cid(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "missing", "redacted": True}
    return {
        "schema": str(value.get("schema", "")),
        "status": str(value.get("status", "unknown")),
        "plan_cid": str(value.get("plan_cid") or ""),
        "plan_sha256": str(value.get("plan_sha256") or ""),
        "canonical_bytes": int(value.get("canonical_bytes") or 0),
        "cid_version": int(value.get("cid_version") or 0),
        "codec": str(value.get("codec", "")),
        "multicodec": str(value.get("multicodec", "")),
        "multihash": str(value.get("multihash", "")),
        "safe_mode_required": bool(value.get("safe_mode_required")),
        "claim_boundary": str(value.get("claim_boundary", "")),
        "redacted": True,
    }


def _safe_numeric_summary(values: Dict[str, Any]) -> Dict[str, float]:
    return {
        str(key): round(float(value), 4)
        for key, value in values.items()
        if isinstance(value, (int, float))
    }


def _apply_mesh_metric_evidence_policy(
    directives: Dict[str, Any],
    raw_metrics: Dict[str, Any] | None,
) -> Dict[str, Any]:
    policy = build_mesh_metric_evidence_policy(raw_metrics)
    directives[MESH_METRIC_POLICY_KEY] = policy

    blocked_actions: List[str] = []
    if not policy["allows_high_risk_mesh_actions"]:
        for directive_key, action_name in _MESH_HIGH_RISK_DIRECTIVE_ACTIONS.items():
            if directives.get(directive_key, False):
                directives[directive_key] = False
                blocked_actions.append(action_name)

    directives["blocked_high_risk_mesh_actions"] = blocked_actions
    directives["mesh_high_risk_actions_blocked"] = bool(blocked_actions)
    return directives


def _directive_summary(directives: Dict[str, Any]) -> Dict[str, Any]:
    dao_actions = directives.get("dao_actions", []) or []
    dao_action_types = []
    for action in dao_actions:
        if isinstance(action, dict):
            dao_action_types.append(str(action.get("type", "unknown")))
        else:
            dao_action_types.append(type(action).__name__)
    route_preference = str(directives.get("route_preference", "balanced"))
    mesh_policy = safe_mesh_metric_evidence_policy(
        directives.get(MESH_METRIC_POLICY_KEY)
    )
    summary = {
        "keys": sorted(str(key) for key in directives),
        "safe_mode": bool(directives.get("safe_mode", False)),
        "safe_mode_final_state": str(
            directives.get("safe_mode_final_state", "")
        ),
        "safe_mode_reason_id": str(directives.get("safe_mode_reason_id", "")),
        "route_preference": (
            route_preference
            if route_preference in _SAFE_ROUTE_PREFERENCES
            else "[redacted]"
        ),
        "route_preference_sha256": _sha256_text(route_preference),
        "route_preference_redacted": route_preference not in _SAFE_ROUTE_PREFERENCES,
        "enable_aggressive_healing": bool(
            directives.get("enable_aggressive_healing", False)
        ),
        "preemptive_healing": bool(directives.get("preemptive_healing", False)),
        "scaling_action": str(directives.get("scaling_action", "none")),
        "mesh_metric_evidence_policy": mesh_policy,
        "blocked_high_risk_mesh_actions": _safe_string_list(
            directives.get("blocked_high_risk_mesh_actions", []),
        ),
        "mesh_high_risk_actions_blocked": bool(
            directives.get("mesh_high_risk_actions_blocked", False)
        ),
        "recovery_plan_cid": _safe_recovery_plan_cid(
            directives.get("recovery_plan_cid")
        ),
        "dao_action_count": len(dao_actions),
        "dao_action_types": sorted(dao_action_types),
        "values_redacted": True,
    }
    return summary


def _safe_action_context(context: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    if "route_preference" in context:
        route_preference = str(context["route_preference"])
        safe["route_preference"] = (
            route_preference
            if route_preference in _SAFE_ROUTE_PREFERENCES
            else "[redacted]"
        )
        if route_preference not in _SAFE_ROUTE_PREFERENCES:
            safe["route_preference_sha256"] = _sha256_text(route_preference)
            safe["route_preference_redacted"] = True
    if "recommendation_count" in context:
        safe["recommendation_count"] = int(context.get("recommendation_count") or 0)
    if "optimizer_evidence_events_total" in context:
        safe["optimizer_evidence_events_total"] = int(
            context.get("optimizer_evidence_events_total") or 0
        )
    if "optimizer_evidence_source_agents" in context:
        safe["optimizer_evidence_source_agents"] = sorted(
            str(agent) for agent in context.get("optimizer_evidence_source_agents", [])
        )
    if "scaling_action" in context:
        safe["scaling_action"] = str(context["scaling_action"])
    if "dao_action_type" in context:
        safe["dao_action_type"] = str(context["dao_action_type"])
    if "healing_mode" in context:
        safe["healing_mode"] = str(context["healing_mode"])
    if "mesh_high_risk_action" in context:
        safe["mesh_high_risk_action"] = str(context["mesh_high_risk_action"])
    if "mesh_metric_decision_basis" in context:
        safe["mesh_metric_decision_basis"] = str(
            context["mesh_metric_decision_basis"]
        )
    if "mesh_metric_control_risk" in context:
        safe["mesh_metric_control_risk"] = str(context["mesh_metric_control_risk"])
    if "mesh_estimate_or_fallback_based" in context:
        safe["mesh_estimate_or_fallback_based"] = bool(
            context["mesh_estimate_or_fallback_based"]
        )
    if "mesh_dataplane_confirmed" in context:
        safe["mesh_dataplane_confirmed"] = bool(context["mesh_dataplane_confirmed"])
    if "safe_mode_reason_id" in context:
        safe["safe_mode_reason_id"] = str(context["safe_mode_reason_id"])
    if "safe_mode_final_state" in context:
        safe["safe_mode_final_state"] = str(context["safe_mode_final_state"])
    if "dependency" in context:
        safe["dependency"] = str(context["dependency"])
    safe["values_redacted"] = True
    return safe


def _optimizer_evidence_context(report: Dict[str, Any]) -> Dict[str, Any]:
    evidence = report.get("evidence") if isinstance(report, dict) else None
    if not isinstance(evidence, dict):
        return {
            "optimizer_evidence_events_total": 0,
            "optimizer_evidence_source_agents": [],
        }
    return {
        "optimizer_evidence_events_total": int(evidence.get("events_total") or 0),
        "optimizer_evidence_source_agents": [
            str(agent) for agent in evidence.get("source_agents", []) if str(agent)
        ],
    }


def _safe_result_summary(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, SafeActuatorResult):
        return {
            "success": bool(raw.success),
            "simulated": bool(raw.simulated),
            "reason_redacted": bool(raw.reason),
            "evidence_metadata": raw.evidence_metadata.to_dict(),
        }
    if hasattr(raw, "success"):
        return {
            "success": bool(getattr(raw, "success")),
            "action_type": str(getattr(raw, "action_type", "unknown")),
            "detail_redacted": bool(getattr(raw, "detail", "")),
        }
    if isinstance(raw, dict):
        return {
            "success": bool(raw.get("success", raw.get("ok", False))),
            "keys": sorted(str(key) for key in raw),
            "values_redacted": True,
        }
    if isinstance(raw, bool):
        return {"success": raw}
    if isinstance(raw, int):
        return {"numeric_result": raw}
    if raw is None:
        return {"returned": "none"}
    return {"type": type(raw).__name__, "values_redacted": True}


def _safe_actuator_evidence_metadata_payload(
    metadata: SafeActuatorEvidenceMetadata | None,
) -> Dict[str, Any] | None:
    if metadata is None:
        return None
    if not (
        metadata.claim_gate
        or metadata.cross_plane_claim_gate
        or metadata.evidence
        or metadata.source_agents
        or metadata.event_ids
        or metadata.claim_boundary
    ):
        return None
    return metadata.to_dict()


def _local_healing_post_action_claim_gate(operation: str) -> Dict[str, Any]:
    gate = build_post_action_dataplane_claim_gate(
        probe_required=True,
        probe_enabled=False,
        probe_target_present=False,
        probe_attempted=False,
        dataplane_confirmed=False,
        evidence={},
        claim_boundary=MAPEK_POST_ACTION_DATAPLANE_CLAIM_BOUNDARY,
        local_action_applied=True,
    ).model_dump(mode="json")
    gate["schema"] = "x0tta6bl4.core_mapek.post_action_dataplane_claim_gate.v1"
    gate["operation"] = operation
    gate["local_control_action_claim_allowed"] = True
    gate["safe_actuator_result_recorded"] = True
    return gate


def _safe_post_action_claim_gate(gate: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not isinstance(gate, dict):
        return None
    required = bool(
        gate.get(
            "requires_post_action_dataplane_revalidation",
            gate.get("required_for_restored_dataplane_claim", True),
        )
    )
    normalized = build_post_action_dataplane_claim_gate(
        probe_required=required,
        probe_enabled=bool(gate.get("post_action_probe_enabled")),
        probe_target_present=bool(gate.get("post_action_probe_target_present")),
        probe_attempted=bool(gate.get("post_action_probe_attempted")),
        dataplane_confirmed=bool(gate.get("dataplane_confirmed")),
        evidence=gate.get("evidence", {}),
        claim_boundary=str(
            gate.get("claim_boundary") or MAPEK_POST_ACTION_DATAPLANE_CLAIM_BOUNDARY
        ),
        local_action_applied=bool(gate.get("local_action_applied", True)),
    ).model_dump(mode="json")
    normalized["schema"] = str(
        gate.get("schema") or "x0tta6bl4.core_mapek.post_action_dataplane_claim_gate.v1"
    )
    normalized["operation"] = str(gate.get("operation", ""))
    normalized["local_control_action_claim_allowed"] = bool(
        gate.get("local_control_action_claim_allowed", normalized["local_action_applied"])
    )
    normalized["redacted"] = True
    return normalized


def _safe_actuator_claim_gate(
    actuator_result: SafeActuatorResult,
    fallback_claim_gate: Dict[str, Any] | None,
) -> Dict[str, Any] | None:
    if actuator_result.evidence_metadata.claim_gate:
        return actuator_result.evidence_metadata.claim_gate
    return fallback_claim_gate


def _raw_success(raw: Any) -> bool:
    if isinstance(raw, SafeActuatorResult):
        return bool(raw.success)
    if hasattr(raw, "success"):
        return bool(getattr(raw, "success"))
    if isinstance(raw, dict) and ("success" in raw or "ok" in raw):
        return bool(raw.get("success", raw.get("ok")))
    if raw is False:
        return False
    return True


def _reason_metadata(reason: str) -> Dict[str, Any]:
    return {
        "present": bool(reason),
        "sha256": _sha256_text(reason),
        "redacted": True,
    }


def _event_ids(
    bus: EventBus | None,
    *,
    source_agent: str,
) -> set[str]:
    if bus is None:
        return set()
    event_ids: set[str] = set()
    for event_type in _DOWNSTREAM_TERMINAL_EVENT_TYPES:
        event_ids.update(
            event.event_id
            for event in bus.get_event_history(
                event_type,
                source_agent=source_agent,
                limit=1000,
            )
        )
    return event_ids


def _event_ids_by_source(
    bus: EventBus | None,
    source_agents: tuple[str, ...],
) -> Dict[str, set[str]]:
    return {
        source_agent: _event_ids(bus, source_agent=source_agent)
        for source_agent in source_agents
    }


def _terminal_event_payloads_by_source(
    bus: EventBus | None,
    source_agents: tuple[str, ...],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    if bus is None:
        return {}
    by_source: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for source_agent in source_agents:
        payloads: Dict[str, Dict[str, Any]] = {}
        for event_type in _DOWNSTREAM_TERMINAL_EVENT_TYPES:
            for event in bus.get_event_history(
                event_type,
                source_agent=source_agent,
                limit=1000,
            ):
                payloads[event.event_id] = (
                    event.data if isinstance(event.data, dict) else {}
                )
        by_source[source_agent] = payloads
    return by_source


def _pipeline_stage_end_events(
    bus: EventBus | None,
    *,
    source_agent: str,
) -> Dict[str, Dict[str, Any]]:
    if bus is None:
        return {}
    return {
        event.event_id: event.data
        for event in bus.get_event_history(
            EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=1000,
        )
    }


def _latest_pipeline_stage_end_event(
    bus: EventBus | None,
    *,
    source_agent: str,
) -> tuple[str, Dict[str, Any]] | None:
    if bus is None:
        return None
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent=source_agent,
        limit=1,
    )
    if not events:
        return None
    event = events[-1]
    return event.event_id, event.data


def _safe_source_counts(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    safe: Dict[str, int] = {}
    for key, count in value.items():
        try:
            safe[str(key)] = int(count)
        except (TypeError, ValueError):
            continue
    return dict(sorted(safe.items()))


def _safe_string_list(value: Any, *, limit: int = 10) -> List[str]:
    return sorted(str(item) for item in _string_values(value))[:limit]


def _safe_metric_source_summary(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: Dict[str, Any] = {}
    for metric_name in (
        "latency_ms",
        "packet_loss_percent",
        "jitter_ms",
        "bandwidth_mbps",
        "hop_count",
    ):
        metric = value.get(metric_name)
        if not isinstance(metric, dict):
            continue
        safe[metric_name] = {
            "source_counts": _safe_source_counts(metric.get("source_counts")),
            "observed": int(metric.get("observed", 0) or 0),
            "probed": int(metric.get("probed", 0) or 0),
            "estimated": int(metric.get("estimated", 0) or 0),
            "fallback_default": int(metric.get("fallback_default", 0) or 0),
            "fields": _safe_string_list(metric.get("fields")),
        }
    return safe


def _safe_probe_section(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {"status": "missing", "values_redacted": True}
    safe: Dict[str, Any] = {
        "status": str(value.get("status", "unknown")),
        "source": str(value.get("source", "unknown")),
        "values_redacted": True,
    }
    for key in (
        "attempts",
        "successes",
        "matched_peer_count",
        "max_probe_peers",
        "admin_peer_count",
        "estimated_peer_count",
        "events_total",
    ):
        if key in value:
            try:
                safe[key] = int(value.get(key) or 0)
            except (TypeError, ValueError):
                continue
    return safe


def _monitor_metric_source_evidence(bus: EventBus | None) -> Dict[str, Any]:
    latest = _latest_pipeline_stage_end_event(
        bus,
        source_agent="mesh-telemetry-collector",
    )
    if latest is None:
        return {
            "status": "missing",
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "redacted": True,
        }

    event_id, payload = latest
    optimizer = payload.get("optimizer") if isinstance(payload, dict) else None
    optimizer = optimizer if isinstance(optimizer, dict) else {}
    return {
        "status": "available",
        "source_agents": ["mesh-telemetry-collector"],
        "event_ids": [event_id],
        "events_total": 1,
        "metric_sources": _safe_metric_source_summary(
            optimizer.get("metric_sources")
        ),
        "dataplane_probe": _safe_probe_section(optimizer.get("dataplane_probe")),
        "metric_enrichment": _safe_probe_section(optimizer.get("metric_enrichment")),
        "redacted": True,
    }


def _string_values(values: Any) -> List[str]:
    if values is None:
        return []
    if isinstance(values, (str, bytes)):
        return [str(values)] if str(values) else []
    if isinstance(values, (list, tuple, set)):
        return [str(value) for value in values if str(value)]
    return [str(values)] if str(values) else []


def _safe_claim_boundary(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:_CLAIM_BOUNDARY_TEXT_LIMIT]


def _claim_boundary_set(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    boundaries: set[str] = set()
    direct_boundary = _safe_claim_boundary(value.get("claim_boundary"))
    if direct_boundary:
        boundaries.add(direct_boundary)
    if isinstance(value.get("claim_boundaries"), list):
        for item in value["claim_boundaries"]:
            boundary = _safe_claim_boundary(item)
            if boundary:
                boundaries.add(boundary)
    return boundaries


def _claim_boundary_summary(boundaries: set[str]) -> Dict[str, Any]:
    distinct = sorted(boundaries)
    return {
        "claim_boundaries": distinct[:_CLAIM_BOUNDARY_LIMIT],
        "claim_boundaries_total": len(distinct),
        "claim_boundaries_truncated": len(distinct) > _CLAIM_BOUNDARY_LIMIT,
    }


def _payload_claim_boundaries(payloads: List[Dict[str, Any]]) -> set[str]:
    boundaries: set[str] = set()
    for payload in payloads:
        boundaries.update(_claim_boundary_set(payload))
        downstream = payload.get("downstream_evidence")
        if isinstance(downstream, dict):
            boundaries.update(_claim_boundary_set(downstream))
        revalidation = payload.get("post_action_dataplane_revalidation")
        if isinstance(revalidation, dict):
            boundaries.update(_claim_boundary_set(revalidation))
            evidence = revalidation.get("evidence")
            if isinstance(evidence, dict):
                boundaries.update(_claim_boundary_set(evidence))
            claim_gate = revalidation.get("claim_gate")
            if isinstance(claim_gate, dict):
                boundaries.update(_claim_boundary_set(claim_gate))
    return boundaries


def _transitive_downstream_evidence(mesh_event_payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_agent: Dict[str, set[str]] = {}
    claim_boundaries_by_agent: Dict[str, set[str]] = {}
    for payload in mesh_event_payloads:
        downstream = payload.get("downstream_evidence")
        if not isinstance(downstream, dict):
            continue
        source_agents = _string_values(downstream.get("source_agents"))
        event_ids = _string_values(downstream.get("event_ids"))
        claim_boundaries = _claim_boundary_set(downstream)
        if not source_agents or not event_ids:
            continue
        for source_agent in source_agents:
            by_agent.setdefault(source_agent, set()).update(event_ids)
            claim_boundaries_by_agent.setdefault(source_agent, set()).update(
                claim_boundaries
            )

    return {
        source_agent: {
            "event_ids": sorted(event_ids),
            "events_total": len(event_ids),
            **_claim_boundary_summary(
                claim_boundaries_by_agent.get(source_agent, set())
            ),
            "redacted": True,
        }
        for source_agent, event_ids in sorted(by_agent.items())
    }


def _downstream_evidence_delta(
    before: Dict[str, set[str]],
    after: Dict[str, set[str]],
    *,
    event_payloads_by_source: Dict[str, Dict[str, Dict[str, Any]]] | None = None,
    limit: int = 20,
) -> Dict[str, Any]:
    by_source_agent: Dict[str, Dict[str, Any]] = {}
    all_event_ids: List[str] = []
    all_claim_boundaries: set[str] = set()
    for source_agent in sorted(set(before) | set(after)):
        event_ids = sorted(after.get(source_agent, set()) - before.get(source_agent, set()))
        if not event_ids:
            continue
        all_event_ids.extend(event_ids)
        payloads = [
            payload
            for event_id in event_ids
            for payload in [
                (event_payloads_by_source or {}).get(source_agent, {}).get(event_id)
            ]
            if isinstance(payload, dict)
        ]
        claim_boundaries = _payload_claim_boundaries(payloads)
        all_claim_boundaries.update(claim_boundaries)
        by_source_agent[source_agent] = {
            "event_ids": event_ids[-limit:],
            "events_total": len(event_ids),
            "event_ids_limit": limit,
            "event_ids_truncated": len(event_ids) > limit,
            **_claim_boundary_summary(claim_boundaries),
            "redacted": True,
        }

    return {
        "source_agents": sorted(by_source_agent),
        "event_ids": all_event_ids[-limit:],
        "events_total": len(all_event_ids),
        "event_ids_limit": limit,
        "event_ids_truncated": len(all_event_ids) > limit,
        "by_source_agent": by_source_agent,
        **_claim_boundary_summary(all_claim_boundaries),
        "redacted": True,
    }


@dataclass
class MAPEKState:
    """State container for MAPE-K loop"""

    metrics: ConsciousnessMetrics
    directives: Dict[str, Any]
    actions_taken: List[str]
    timestamp: float


class MAPEKLoop:
    """
    Implements the Monitor-Analyze-Plan-Execute-Knowledge loop
    integrated with Consciousness Engine.

    Philosophy: The system continuously observes itself (Monitor),
    evaluates its harmony state (Analyze), decides on actions (Plan),
    executes self-healing (Execute), and learns from experience (Knowledge).
    """

    def __init__(
        self,
        consciousness_engine: ConsciousnessEngine,
        mesh_manager: MeshNetworkManager,
        prometheus: PrometheusExporter,
        zero_trust: ZeroTrustValidator,
        dao_logger: DAOAuditLogger = None,
        action_dispatcher=None,
        parl_controller=None,
        fl_integration=None,
        event_bus: EventBus | None = None,
        event_project_root: str = ".",
        self_healing_manager=None,
    ):
        self.consciousness = consciousness_engine
        self.mesh = mesh_manager
        self.prometheus = prometheus
        self.zero_trust = zero_trust
        self.dao_logger = dao_logger
        self.action_dispatcher = action_dispatcher
        self.parl_controller = parl_controller  # Swarm Integration
        self.fl_integration = fl_integration  # FL integration compatibility
        self.event_project_root = event_project_root
        self.event_bus = _event_bus_or_none(event_bus, event_project_root)
        self.self_healing = self_healing_manager

        # TD-008: Auto-initialize modular self-healing if not provided
        if self.self_healing is None:
            try:
                from src.self_healing.mape_k.manager import SelfHealingManager
                self.self_healing = SelfHealingManager(
                    node_id=service_event_identity(service_name=_SERVICE_AGENT).get("node_id", "core-mapek"),
                    event_bus=self.event_bus,
                    event_project_root=event_project_root,
                )
            except Exception as exc:
                logger.debug("Modular SelfHealingManager unavailable: %s", exc)

        if self.event_bus is not None:
            try:
                self.mesh.event_bus = self.event_bus
                self.mesh.event_project_root = event_project_root
            except Exception:
                logger.debug("Unable to attach core MAPE-K EventBus to mesh manager")

        self.running = False
        self.loop_interval = 60  # Dynamic, adjusted by consciousness state
        self.state_history: List[MAPEKState] = []

        # Thought Generation Control
        self.cycle_count = 0
        self.thought_frequency = 10  # Generate thought every 10 cycles (~10 mins)
        self.safe_mode_active = False
        self.safe_mode_reason_id = ""

    def _safe_mode_directives(
        self,
        *,
        reason_id: str,
        dependency: str,
        error_type: str = "",
        base_directives: Dict[str, Any] | None = None,
        raw_metrics: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        directives = dict(base_directives or {})
        directives = _apply_mesh_metric_evidence_policy(directives, raw_metrics or {})
        directives.update(
            {
                "safe_mode": True,
                "safe_mode_reason_id": reason_id,
                "safe_mode_dependency": dependency,
                "safe_mode_error_type": error_type,
                "safe_mode_final_state": "control_actions_blocked",
                "monitoring_interval_sec": max(
                    int(directives.get("monitoring_interval_sec", 60) or 60),
                    60,
                ),
                "route_preference": "balanced",
                "enable_aggressive_healing": False,
                "preemptive_healing": False,
                "scaling_action": "none",
                "dao_actions": [],
                "blocked_high_risk_mesh_actions": [
                    "aggressive_healing",
                    "mesh_optimization",
                    "preemptive_healing",
                    "scaling",
                    "dao_action",
                ],
                "mesh_high_risk_actions_blocked": True,
                "production_readiness_claim_allowed": False,
                "claim_boundary": MAPEK_SAFE_MODE_CLAIM_BOUNDARY,
            }
        )
        self.safe_mode_active = True
        self.safe_mode_reason_id = reason_id
        return directives

    def _attach_recovery_plan_cid(self, directives: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(directives)
        enriched["recovery_plan_cid"] = _content_addressed_recovery_plan_metadata(
            enriched
        )
        return enriched

    def _publish_safe_mode_event(
        self,
        *,
        directives: Dict[str, Any],
        metrics: Dict[str, Any] | None = None,
        reason: str,
        error_type: str,
    ) -> None:
        self._publish_control_event(
            EventType.TASK_BLOCKED,
            stage="safe_mode_entered",
            operation="enter_safe_mode",
            status="safe_mode",
            directives=directives,
            metrics=metrics,
            context={
                "safe_mode_reason_id": directives.get("safe_mode_reason_id", ""),
                "safe_mode_final_state": directives.get(
                    "safe_mode_final_state", "control_actions_blocked"
                ),
                "dependency": directives.get("safe_mode_dependency", ""),
            },
            success=False,
            simulated=False,
            raw_result={
                "success": False,
                "safe_mode_active": True,
                "control_actions_blocked": True,
                "production_readiness_claim_allowed": False,
            },
            reason=reason,
            error_type=error_type or None,
        )

    def _publish_control_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        operation: str,
        status: str,
        duration_ms: float = 0.0,
        directives: Dict[str, Any] | None = None,
        metrics: Dict[str, Any] | None = None,
        context: Dict[str, Any] | None = None,
        success: bool | None = None,
        simulated: bool | None = None,
        raw_result: Any = None,
        downstream_evidence: Dict[str, Any] | None = None,
        reason: str = "",
        error_type: str | None = None,
        claim_gate: Dict[str, Any] | None = None,
        safe_actuator_evidence_metadata: SafeActuatorEvidenceMetadata | None = None,
    ) -> str | None:
        if self.event_bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "core.mape_k_loop",
            "stage": stage,
            "operation": operation,
            "resource": _MAPEK_RESOURCES[operation],
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "safe_actuator": stage.startswith("action_"),
            "read_only": operation == "monitor",
            "observed_state": operation == "monitor",
            "control_action": operation != "monitor",
            "success": success,
            "simulated": simulated,
            "directives": _directive_summary(directives or {}),
            "metrics": _safe_numeric_summary(metrics or {}),
            "context": _safe_action_context(context or {}),
            "result": _safe_result_summary(raw_result),
            "reason": _reason_metadata(reason),
            "downstream_evidence": downstream_evidence
            or {"event_ids": [], "events_total": 0, "redacted": True},
            "claim_boundary": MAPEK_LOOP_CONTROL_CLAIM_BOUNDARY,
        }
        safe_claim_gate = _safe_post_action_claim_gate(claim_gate)
        if safe_claim_gate is not None:
            payload["post_action_dataplane_revalidation"] = {
                "required_for_restored_dataplane_claim": True,
                "dataplane_confirmed": safe_claim_gate["dataplane_confirmed"],
                "post_action_dataplane_revalidated": safe_claim_gate[
                    "post_action_dataplane_revalidated"
                ],
                "restored_dataplane_claim_allowed": safe_claim_gate[
                    "restored_dataplane_claim_allowed"
                ],
                "claim_gate": safe_claim_gate,
                "claim_boundary": safe_claim_gate["claim_boundary"],
                "redacted": True,
            }
        safe_actuator_metadata = _safe_actuator_evidence_metadata_payload(
            safe_actuator_evidence_metadata
        )
        if safe_actuator_metadata is not None:
            payload["safe_actuator_evidence_metadata"] = safe_actuator_metadata
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        try:
            event = self.event_bus.publish(
                event_type,
                _SERVICE_AGENT,
                payload,
                priority=7,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish core MAPE-K control event: %s", exc)
            return None

    async def _run_control_action(
        self,
        operation: str,
        context: Dict[str, Any],
        executor,
        *,
        directives: Dict[str, Any],
        downstream_source_agents: tuple[str, ...] = (),
        claim_gate: Dict[str, Any] | None = None,
    ) -> tuple[Any, SafeActuatorResult]:
        self._publish_control_event(
            EventType.COORDINATION_REQUEST,
            stage="action_requested",
            operation=operation,
            status="requested",
            directives=directives,
            context=context,
            claim_gate=claim_gate,
        )
        started = time.monotonic()
        raw_holder: Dict[str, Any] = {}
        downstream_before = _event_ids_by_source(
            self.event_bus,
            downstream_source_agents,
        )

        async def _executor(
            _action: str, _context: Dict[str, Any]
        ) -> SafeActuatorResult:
            raw = executor()
            if inspect.isawaitable(raw):
                raw = await raw
            raw_holder["raw"] = raw
            if isinstance(raw, SafeActuatorResult):
                return raw
            evidence_metadata = SafeActuatorEvidenceMetadata.from_value(raw)
            if not evidence_metadata.claim_gate and claim_gate:
                evidence_metadata = SafeActuatorEvidenceMetadata.from_value(
                    {
                        "claim_gate": claim_gate,
                        "evidence": {
                            "component": "core.mape_k_loop",
                            "operation": operation,
                            "resource": _MAPEK_RESOURCES[operation],
                            "raw_context_values_redacted": True,
                            "raw_result_values_redacted": True,
                            "redacted": True,
                        },
                        "source_agents": [_SERVICE_AGENT],
                        "claim_boundary": (
                            str(claim_gate.get("claim_boundary", ""))
                            if isinstance(claim_gate, dict)
                            else ""
                        ),
                        "redacted": True,
                    }
                )
            return SafeActuatorResult(
                success=_raw_success(raw),
                evidence_metadata=evidence_metadata,
            )

        actuator_result = await AsyncSafeActuator(_executor).execute(operation, context)
        duration_ms = (time.monotonic() - started) * 1000
        raw_result = raw_holder.get("raw")
        success = bool(actuator_result.success)
        simulated = bool(actuator_result.simulated)
        downstream_after = _event_ids_by_source(
            self.event_bus,
            downstream_source_agents,
        )
        downstream_payloads = _terminal_event_payloads_by_source(
            self.event_bus,
            downstream_source_agents,
        )
        self._publish_control_event(
            (
                EventType.PIPELINE_STAGE_END
                if success and not simulated
                else EventType.TASK_FAILED
            ),
            stage=(
                "action_completed"
                if success and not simulated
                else "action_simulated" if simulated else "action_failed"
            ),
            operation=operation,
            status="success" if success and not simulated else "failed",
            duration_ms=duration_ms,
            directives=directives,
            context=context,
            success=success and not simulated,
            simulated=simulated,
            raw_result=raw_result if raw_result is not None else actuator_result,
            downstream_evidence=_downstream_evidence_delta(
                downstream_before,
                downstream_after,
                event_payloads_by_source=downstream_payloads,
            ),
            reason=actuator_result.reason,
            error_type=None if success else "SafeActuatorFailure",
            claim_gate=_safe_actuator_claim_gate(actuator_result, claim_gate),
            safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
        )
        return raw_result, actuator_result

    def _publish_blocked_control_action(
        self,
        operation: str,
        context: Dict[str, Any],
        *,
        directives: Dict[str, Any],
        reason: str,
    ) -> None:
        self._publish_control_event(
            EventType.TASK_BLOCKED,
            stage="action_blocked",
            operation=operation,
            status="blocked",
            directives=directives,
            context=context,
            success=False,
            simulated=False,
            raw_result={"success": False, "blocked": True},
            reason=reason,
            error_type="MeshMetricEvidencePolicyBlocked",
        )

    async def start(self, fl_integration: bool = False):
        """Start the autonomic loop."""
        self.running = True
        logger.info("🌀 MAPEKLoop started")

        if fl_integration and self.fl_integration:
            logger.info("🧠 Federated Learning integration active in MAPE-K")

        while self.running:
            try:
                await self._execute_cycle()
                await asyncio.sleep(self.loop_interval)
            except Exception as e:
                logger.error(f"MAPE-K cycle error: {e}", exc_info=True)
                await asyncio.sleep(10)  # Brief pause before retry

    async def stop(self):
        """Stop the MAPE-K loop"""
        self.running = False
        logger.info("MAPE-K loop stopped")

    async def _execute_cycle(self):
        """Execute one complete MAPE-K cycle with tracing."""
        cycle_start = time.time()
        mapek_spans = get_mapek_spans() if get_mapek_spans is not None else None
        node_id = "local-node"  # Fallback if mesh manager not ready

        # ===== MONITOR =====
        if mapek_spans:
            with mapek_spans.monitor_phase(node_id):
                raw_metrics = await self._monitor()
        else:
            raw_metrics = await self._monitor()

        # ===== ANALYZE =====
        if mapek_spans:
            with mapek_spans.analyze_phase(node_id):
                consciousness_metrics = await self._analyze(raw_metrics)
        else:
            consciousness_metrics = await self._analyze(raw_metrics)

        # ===== PLAN =====
        if self.safe_mode_active:
            directives = self._safe_mode_directives(
                reason_id=self.safe_mode_reason_id or "safe_mode_active",
                dependency="previous_cycle",
                raw_metrics=raw_metrics,
            )
        else:
            try:
                if mapek_spans:
                    with mapek_spans.plan_phase(node_id):
                        directives = self._plan(consciousness_metrics)
                else:
                    directives = self._plan(consciousness_metrics)
            except Exception as exc:
                logger.error("MAPE-K planning failed; entering safe mode: %s", exc)
                directives = self._safe_mode_directives(
                    reason_id="planning_failed",
                    dependency="planner",
                    error_type=type(exc).__name__,
                    raw_metrics=raw_metrics,
                )

        # ===== EXECUTE =====
        if mapek_spans:
            with mapek_spans.execute_phase(node_id):
                actions_taken = await self._execute(directives)
        else:
            actions_taken = await self._execute(directives)

        # ===== KNOWLEDGE =====
        if mapek_spans:
            with mapek_spans.knowledge_phase(node_id):
                try:
                    await self._knowledge(
                        consciousness_metrics, directives, actions_taken, raw_metrics
                    )
                except Exception as exc:
                    logger.error(
                        "MAPE-K knowledge phase failed; entering safe mode: %s",
                        exc,
                    )
                    safe_directives = self._safe_mode_directives(
                        reason_id="knowledge_phase_failed",
                        dependency="knowledge",
                        error_type=type(exc).__name__,
                        base_directives=directives,
                        raw_metrics=raw_metrics,
                    )
                    self._publish_safe_mode_event(
                        directives=safe_directives,
                        metrics=raw_metrics,
                        reason="knowledge_phase_failed",
                        error_type=type(exc).__name__,
                    )
                    directives = safe_directives
        else:
            try:
                await self._knowledge(
                    consciousness_metrics, directives, actions_taken, raw_metrics
                )
            except Exception as exc:
                logger.error(
                    "MAPE-K knowledge phase failed; entering safe mode: %s",
                    exc,
                )
                safe_directives = self._safe_mode_directives(
                    reason_id="knowledge_phase_failed",
                    dependency="knowledge",
                    error_type=type(exc).__name__,
                    base_directives=directives,
                    raw_metrics=raw_metrics,
                )
                self._publish_safe_mode_event(
                    directives=safe_directives,
                    metrics=raw_metrics,
                    reason="knowledge_phase_failed",
                    error_type=type(exc).__name__,
                )
                directives = safe_directives

        cycle_duration = time.time() - cycle_start
        self.cycle_count += 1

        log_msg = (
            f"φ-cycle {self.cycle_count} complete: {consciousness_metrics.state.value} "
            f"(φ={consciousness_metrics.phi_ratio:.3f}, "
            f"duration={cycle_duration:.2f}s)"
        )
        logger.info(log_msg)

        # Automated Thought Generation (Optimization: Run infrequently)
        if self.cycle_count % self.thought_frequency == 0:
            try:
                # Use a specific logger for thoughts to separate them
                thought = self.consciousness.get_system_thought(consciousness_metrics)
                logger.info(f"🧠 SYSTEM THOUGHT: {thought}")
            except Exception as e:
                logger.warning(f"Failed to generate system thought: {e}")

        # Adjust loop interval based on consciousness state
        self.loop_interval = directives.get("monitoring_interval_sec", 60)

    async def _monitor(self) -> Dict[str, float]:
        """
        MONITOR phase: Collect system metrics and sync with DAO
        """
        metrics = {}

        # 0. Sync with DAO Governance
        if DATABASE_AVAILABLE and SessionLocal is not None:
            try:
                from src.services.dao_enforcement import dao_enforcer

                with SessionLocal() as db:
                    dao_enforcer.sync_config_with_dao(db)
            except Exception as e:
                logger.debug(f"DAO sync failed: {e}")

        # System resources
        try:
            import psutil

            metrics["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            metrics["memory_percent"] = psutil.virtual_memory().percent
        except ImportError:
            metrics["cpu_percent"] = 50.0
            metrics["memory_percent"] = 50.0

        # Mesh network metrics
        mesh_events_before = _pipeline_stage_end_events(
            self.event_bus,
            source_agent="mesh-network-manager",
        )
        mesh_stats = await self.mesh.get_statistics()
        mesh_events_after = _pipeline_stage_end_events(
            self.event_bus,
            source_agent="mesh-network-manager",
        )
        metrics["mesh_connectivity"] = mesh_stats.get("active_peers", 0)
        metrics["latency_ms"] = mesh_stats.get("avg_latency_ms", 100)
        metrics["packet_loss"] = mesh_stats.get("packet_loss_percent", 0)
        metrics["mttr_minutes"] = mesh_stats.get("mttr_minutes", 5.0)

        # Security metrics
        zt_stats = self.zero_trust.get_validation_stats()
        metrics["zero_trust_success_rate"] = zt_stats.get("success_rate", 0.95)

        # DB Metrics: Offline nodes & Premium (rented) nodes
        if DATABASE_AVAILABLE and SessionLocal is not None:
            try:
                with SessionLocal() as db:
                    metrics["offline_nodes"] = (
                        db.query(MeshNode).filter(MeshNode.status == "offline").count()
                    )

                    # Trust Engine Integration
                    from src.security.trust_engine import TrustEvaluator

                    trust_eval = TrustEvaluator(db)

                    # Check all online nodes for trust issues
                    online_nodes = (
                        db.query(MeshNode).filter(MeshNode.status != "offline").all()
                    )
                    low_trust_count = 0
                    for node in online_nodes:
                        score = trust_eval.calculate_node_trust(node.id)
                        if score < 0.6:
                            low_trust_count += 1
                            logger.warning(
                                f"🛡️ Node {node.id} has LOW TRUST ({score:.2f}). Planning re-attestation."
                            )

                    metrics["low_trust_nodes"] = float(low_trust_count)

                    # Premium nodes count (rented in Marketplace)
                    from src.database import MarketplaceListing

                    premium_nodes = (
                        db.query(MarketplaceListing)
                        .filter(MarketplaceListing.status == "rented")
                        .all()
                    )
                    metrics["premium_nodes_online"] = sum(
                        1 for n in premium_nodes if n.status == "rented"
                    )

                    # If any premium node is offline, set high priority alert
                    for p_node in premium_nodes:
                        node_record = (
                            db.query(MeshNode)
                            .filter(MeshNode.id == p_node.node_id)
                            .first()
                        )
                        if node_record and node_record.status == "offline":
                            metrics["premium_node_failure"] = 1.0
                            logger.critical(
                                f"🚨 Premium node {p_node.node_id} is OFFLINE! SLA breach imminent."
                            )
            except Exception as e:
                logger.warning(f"Failed to query premium nodes: {e}")
                metrics["offline_nodes"] = 0
        else:
            metrics["offline_nodes"] = 0

        mesh_evidence_ids = sorted(set(mesh_events_after) - set(mesh_events_before))
        mesh_event_payloads = [
            mesh_events_after[event_id]
            for event_id in mesh_evidence_ids
            if event_id in mesh_events_after
        ]
        transitive_evidence = _transitive_downstream_evidence(mesh_event_payloads)
        downstream_claim_boundaries = _payload_claim_boundaries(mesh_event_payloads)
        for evidence in transitive_evidence.values():
            downstream_claim_boundaries.update(
                _claim_boundary_set(evidence)
            )
        downstream_claim_boundary_summary = _claim_boundary_summary(
            downstream_claim_boundaries
        )
        downstream_source_agents = ["mesh-network-manager"] if mesh_evidence_ids else []
        downstream_source_agents.extend(
            source_agent
            for source_agent in sorted(transitive_evidence)
            if source_agent not in downstream_source_agents
        )
        metric_source_evidence = _monitor_metric_source_evidence(self.event_bus)
        metrics["mesh_metric_source_available"] = (
            1.0 if metric_source_evidence["status"] == "available" else 0.0
        )
        metrics["mesh_metric_dataplane_samples"] = 0.0
        metrics["mesh_metric_estimated_samples"] = 0.0
        metrics["mesh_metric_fallback_samples"] = 0.0
        if metric_source_evidence["status"] == "available":
            for source_agent in metric_source_evidence["source_agents"]:
                if source_agent not in downstream_source_agents:
                    downstream_source_agents.append(source_agent)
            latency_sources = metric_source_evidence.get("metric_sources", {}).get(
                "latency_ms",
                {},
            )
            metrics["mesh_metric_dataplane_samples"] = float(
                latency_sources.get("probed", 0) or 0
            )
            metrics["mesh_metric_estimated_samples"] = float(
                latency_sources.get("estimated", 0) or 0
            )
            metrics["mesh_metric_fallback_samples"] = float(
                latency_sources.get("fallback_default", 0) or 0
            )
        self._publish_control_event(
            EventType.PIPELINE_STAGE_END,
            stage="monitor_completed",
            operation="monitor",
            status="success",
            metrics=metrics,
            downstream_evidence={
                "source_agents": downstream_source_agents,
                "event_ids": mesh_evidence_ids,
                "events_total": len(mesh_evidence_ids),
                "transitive": transitive_evidence,
                "metric_source_evidence": metric_source_evidence,
                **downstream_claim_boundary_summary,
                "redacted": True,
            },
        )
        return metrics

    async def _analyze(self, raw_metrics: Dict[str, float]) -> ConsciousnessMetrics:
        """
        ANALYZE phase: Evaluate consciousness state using Swarm Intelligence & ML
        """
        swarm_risk_penalty = 0.0

        # 1. Neural Anomaly Detection
        try:
            from src.ml.anomaly import AnomalyDetectionSystem
            import numpy as np

            detector_system = AnomalyDetectionSystem()
            # Vectorize metrics
            metric_vector = np.array(
                [v for v in raw_metrics.values() if isinstance(v, (int, float))]
            )
            anomaly, confidence = await detector_system.check_component(
                "mesh_core", metric_vector
            )
            if anomaly:
                logger.warning(
                    f"🧠 ML: Anomaly detected with confidence {confidence:.2f}"
                )
        except Exception as e:
            logger.debug(f"ML analysis failed: {e}")

        # 2. Swarm Intelligence Analysis
        if self.parl_controller:
            try:
                # Define analysis tasks
                tasks = [
                    {
                        "task_id": "analyze_security_logs",
                        "task_type": "security_analysis",
                        "priority": 10,
                        "payload": {"metrics": raw_metrics},
                    },
                    {
                        "task_id": "analyze_performance_trends",
                        "task_type": "performance_analysis",
                        "priority": 5,
                        "payload": {"metrics": raw_metrics},
                    },
                    {
                        "task_id": "predict_resource_usage",
                        "task_type": "oracle_prediction",
                        "priority": 5,
                        "payload": {"metrics": raw_metrics},
                    },
                ]

                # Execute in parallel
                results = await self.parl_controller.execute_parallel(tasks)

                # Aggregate risks
                for res in results:
                    if not res.get("success"):
                        continue

                    inner = res.get("result", {})
                    risk = inner.get("risk_score", 0.0)
                    if risk > 0:
                        swarm_risk_penalty = max(swarm_risk_penalty, risk)

                if swarm_risk_penalty > 0:
                    logger.info(
                        f"🐝 Swarm detection: Risk penalty {swarm_risk_penalty:.2f} applied"
                    )
            except Exception as e:
                logger.debug(f"Swarm analysis failed: {e}")

        # TD-008: Modular MAPE-K Shadow Check
        if self.self_healing:
            try:
                # Map raw_metrics to format expected by modular check
                modular_metrics = {
                    "node_id": self.mesh.node_id if hasattr(self.mesh, "node_id") else "core-mapek",
                    **raw_metrics
                }
                modular_result = self.self_healing.monitor.check(modular_metrics)

                # Check for discrepancies
                legacy_has_issue = swarm_risk_penalty > 0.5
                modular_has_issue = modular_result.get("anomaly_detected", False)

                if legacy_has_issue != modular_has_issue:
                    logger.info(
                        f"⚖️ TD-008 Discrepancy: legacy={legacy_has_issue}, modular={modular_has_issue}. "
                        f"Modular Issue: {modular_result.get('issue')}"
                    )

                # Record modular evidence
                self._publish_control_event(
                    EventType.MONITOR_PHASE_END,
                    stage="analyze",
                    operation="shadow_check",
                    status="success" if modular_has_issue else "stable",
                    metrics=raw_metrics,
                    check_result=modular_result,
                )
            except Exception as exc:
                logger.debug("Modular shadow check failed: %s", exc)

        metrics = self.consciousness.get_consciousness_metrics(
            raw_metrics, swarm_risk_penalty=swarm_risk_penalty
        )
        try:
            setattr(metrics, "raw_metrics", raw_metrics)
        except Exception:
            logger.debug("Unable to attach raw MAPE-K metrics to analysis result")
        return metrics

    def _plan(self, metrics: ConsciousnessMetrics) -> Dict[str, Any]:
        """
        PLAN phase: Generate operational directives
        """
        directives = self.consciousness.get_operational_directive(metrics)

        raw = getattr(metrics, "raw_metrics", {}) or {}

        # SLA Policy: If premium nodes are failing, override to AGGRESSIVE HEALING
        if raw.get("premium_node_failure", 0.0) > 0:
            directives["enable_aggressive_healing"] = True
            directives["message"] = (
                "🚨 Emergency: Premium node failure detected. Overriding to AGGRESSIVE HEALING."
            )
            logger.info(
                "⚖️ Plan: SLA Policy override triggered (Aggressive Healing enabled)"
            )

        # Trust Policy: If low trust nodes detected, trigger re-attestation
        if raw.get("low_trust_nodes", 0.0) > 0:
            directives["audit_required"] = True
            logger.info(
                "🛡️ Plan: Low trust nodes detected. Scheduling mandatory re-attestation."
            )

        # Add trend analysis for proactive planning
        trend = self.consciousness.get_trend_analysis()
        directives["trend"] = trend

        # If degrading trend in CONTEMPLATIVE state, prepare for MYSTICAL
        if metrics.state.value == "CONTEMPLATIVE" and trend.get("trend") == "degrading":
            directives["preemptive_healing"] = True
            logger.warning("⚠️  Degrading trend detected, preparing preemptive healing")

        directives = _apply_mesh_metric_evidence_policy(directives, raw)
        directives = self._attach_recovery_plan_cid(directives)
        plan_cid = directives.get("recovery_plan_cid")
        if isinstance(plan_cid, dict) and plan_cid.get("safe_mode_required"):
            return self._safe_mode_directives(
                reason_id="recovery_plan_cid_failed",
                dependency="recovery_plan_cid",
                error_type=str(plan_cid.get("error_type", "")),
                base_directives=directives,
                raw_metrics=raw,
            )

        return directives

    async def _execute(self, directives: Dict[str, Any]) -> List[str]:
        """
        EXECUTE phase: Take action based on directives
        """
        actions = []
        if directives.get("safe_mode"):
            reason_id = str(directives.get("safe_mode_reason_id", "safe_mode"))
            self._publish_safe_mode_event(
                directives=directives,
                reason=reason_id,
                error_type=str(directives.get("safe_mode_error_type", "")),
            )
            return [f"safe_mode={reason_id}"]

        for blocked_action in _safe_string_list(
            directives.get("blocked_high_risk_mesh_actions", []),
        ):
            blocked_operation = _MESH_HIGH_RISK_ACTION_OPERATIONS.get(blocked_action)
            if not blocked_operation:
                continue
            self._publish_blocked_control_action(
                blocked_operation,
                mesh_metric_policy_context(
                    directives.get(MESH_METRIC_POLICY_KEY),
                    high_risk_action=blocked_action,
                ),
                directives=directives,
                reason="mesh_metric_source_evidence_missing",
            )

        # Route preference adjustment
        route_pref = directives.get("route_preference", "balanced")
        route_raw, route_result = await self._run_control_action(
            "set_route_preference",
            {"route_preference": route_pref},
            lambda: self.mesh.set_route_preference(route_pref),
            directives=directives,
            downstream_source_agents=("mesh-network-manager",),
        )
        if route_result.success and route_raw is not False:
            actions.append(f"route_preference={route_pref}")

        # Mesh Optimization Enforcement
        try:
            from src.mesh.yggdrasil_optimizer import get_optimizer
            from src.mesh.action_enforcer import mesh_action_enforcer

            try:
                report = get_optimizer().optimize_routes(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    include_evidence=True,
                )
            except TypeError as exc:
                if "unexpected keyword" not in str(exc):
                    raise
                report = get_optimizer().optimize_routes()
            if report.get("recommendations"):
                recommendations = report["recommendations"]
                if not mesh_metric_policy_allows_high_risk(
                    directives.get(MESH_METRIC_POLICY_KEY),
                    require_present=False,
                ):
                    self._publish_blocked_control_action(
                        "enforce_mesh_optimization",
                        mesh_metric_policy_context(
                            directives.get(MESH_METRIC_POLICY_KEY),
                            high_risk_action="mesh_optimization",
                        ),
                        directives=directives,
                        reason="mesh_metric_source_evidence_missing",
                    )
                else:
                    if self.event_bus is not None:
                        try:
                            mesh_action_enforcer.event_bus = self.event_bus
                            mesh_action_enforcer.event_project_root = (
                                self.event_project_root
                            )
                        except Exception:
                            logger.debug(
                                "Unable to attach core MAPE-K EventBus to mesh enforcer"
                            )
                    _raw, optimization_result = await self._run_control_action(
                        "enforce_mesh_optimization",
                        {
                            "recommendation_count": len(recommendations),
                            **_optimizer_evidence_context(report),
                            **mesh_metric_policy_context(
                                directives.get(MESH_METRIC_POLICY_KEY),
                                high_risk_action="mesh_optimization",
                            ),
                        },
                        lambda: mesh_action_enforcer.enforce_recommendations(
                            recommendations,
                            metric_evidence_policy=directives.get(
                                MESH_METRIC_POLICY_KEY
                            ),
                        ),
                        directives=directives,
                        downstream_source_agents=(
                            "mesh-yggdrasil-optimizer",
                            "mesh-action-enforcer",
                        ),
                    )
                    if optimization_result.success:
                        actions.append(
                            f"mesh_optimization={len(recommendations)}_actions"
                        )
        except Exception as e:
            logger.debug(f"Mesh optimization enforcement failed: {e}")

        # Aggressive healing if needed
        if directives.get("enable_aggressive_healing", False):
            if not mesh_metric_policy_allows_high_risk(
                directives.get(MESH_METRIC_POLICY_KEY),
                require_present=False,
            ):
                self._publish_blocked_control_action(
                    "trigger_aggressive_healing",
                    mesh_metric_policy_context(
                        directives.get(MESH_METRIC_POLICY_KEY),
                        high_risk_action="aggressive_healing",
                    ),
                    directives=directives,
                    reason="mesh_metric_source_evidence_missing",
                )
            else:
                healed, _healing_result = await self._run_control_action(
                    "trigger_aggressive_healing",
                    {
                        "healing_mode": "aggressive",
                        **mesh_metric_policy_context(
                            directives.get(MESH_METRIC_POLICY_KEY),
                            high_risk_action="aggressive_healing",
                        ),
                    },
                    lambda: self.mesh.trigger_aggressive_healing(),
                    directives=directives,
                    downstream_source_agents=("mesh-network-manager",),
                    claim_gate=_local_healing_post_action_claim_gate(
                        "trigger_aggressive_healing"
                    ),
                )
                if _healing_result.success:
                    healed = int(healed or 0)
                    actions.append(f"aggressive_healing={healed}_nodes")

        # Preemptive healing
        if directives.get("preemptive_healing", False):
            if not mesh_metric_policy_allows_high_risk(
                directives.get(MESH_METRIC_POLICY_KEY),
                require_present=False,
            ):
                self._publish_blocked_control_action(
                    "trigger_preemptive_checks",
                    mesh_metric_policy_context(
                        directives.get(MESH_METRIC_POLICY_KEY),
                        high_risk_action="preemptive_healing",
                    ),
                    directives=directives,
                    reason="mesh_metric_source_evidence_missing",
                )
            else:
                _raw, preemptive_result = await self._run_control_action(
                    "trigger_preemptive_checks",
                    {
                        "healing_mode": "preemptive",
                        **mesh_metric_policy_context(
                            directives.get(MESH_METRIC_POLICY_KEY),
                            high_risk_action="preemptive_healing",
                        ),
                    },
                    lambda: self.mesh.trigger_preemptive_checks(),
                    directives=directives,
                    downstream_source_agents=("mesh-network-manager",),
                )
                if preemptive_result.success:
                    actions.append("preemptive_healing_initiated")

        # Scaling actions
        scaling = directives.get("scaling_action", "none")
        if scaling != "none":
            _raw, scaling_result = await self._run_control_action(
                "handle_scaling",
                {"scaling_action": scaling},
                lambda: self._handle_scaling(scaling),
                directives=directives,
            )
            if scaling_result.success:
                actions.append(f"scaling={scaling}")

        # DAO governance actions (dispatched via ActionDispatcher)
        dao_actions = directives.get("dao_actions", [])
        if dao_actions and self.action_dispatcher is not None:
            if self.event_bus is not None:
                try:
                    self.action_dispatcher.event_bus = self.event_bus
                    self.action_dispatcher.event_project_root = self.event_project_root
                except Exception:
                    logger.debug("Unable to attach core MAPE-K EventBus to DAO dispatcher")
            for dao_action in dao_actions:
                dao_action_type = (
                    str(dao_action.get("type", "unknown"))
                    if isinstance(dao_action, dict)
                    else type(dao_action).__name__
                )
                result, _dao_actuator_result = await self._run_control_action(
                    "dispatch_dao_action",
                    {"dao_action_type": dao_action_type},
                    lambda dao_action=dao_action: self.action_dispatcher.dispatch(
                        dao_action
                    ),
                    directives=directives,
                    downstream_source_agents=("dao-governance",),
                )
                result_success = bool(getattr(result, "success", False))
                result_action_type = str(
                    getattr(result, "action_type", dao_action_type)
                )
                status = "OK" if result_success else "FAIL"
                actions.append(f"dao:{result_action_type}={status}")
                if not result_success:
                    logger.warning(
                        "DAO action failed: %s — detail redacted",
                        result_action_type,
                    )

        return actions

    async def _knowledge(
        self,
        metrics: ConsciousnessMetrics,
        directives: Dict[str, Any],
        actions: List[str],
        raw_metrics: Dict[str, float] = None,
    ):  # Added raw_metrics
        """
        KNOWLEDGE phase: Store learnings and update models
        """
        # Export Consciousness metrics to Prometheus
        prom_metrics = metrics.to_prometheus_format()
        for metric_name, value in prom_metrics.items():
            self.prometheus.set_gauge(metric_name, value)

        # Export Raw metrics to Prometheus for observability
        if raw_metrics:
            for metric_name, value in raw_metrics.items():
                # Prefix to avoid collision if needed, or just mapped directly
                # Using mapped names for clarity
                # mapped_name = f"mesh_{metric_name}" if metric_name not in ['mesh_connectivity', 'mesh_latency_ms'] else metric_name

                # Custom mapping for specific keys if needed
                if metric_name == "latency_ms":
                    self.prometheus.set_gauge("mesh_latency_ms", value)
                elif metric_name == "cpu_percent":
                    self.prometheus.set_gauge("system_cpu_percent", value)
                elif metric_name == "memory_percent":
                    self.prometheus.set_gauge("system_memory_percent", value)
                elif metric_name == "packet_loss":
                    self.prometheus.set_gauge("mesh_packet_loss_percent", value)
                else:
                    self.prometheus.set_gauge(metric_name, value)

        # Store state for historical analysis
        state = MAPEKState(
            metrics=metrics,
            directives=directives,
            actions_taken=actions,
            timestamp=time.time(),
        )
        self.state_history.append(state)

        # Trim history to prevent memory bloat (keep last 10,000 states)
        if len(self.state_history) > 10000:
            self.state_history = self.state_history[-10000:]

        # Log message from consciousness
        message = directives.get("message", "")
        if message:
            logger.info(f"💭 Consciousness: {message}")

        # Trigger DAO logging for critical events
        if metrics.state.value in ["EUPHORIC", "MYSTICAL"]:
            await self._log_to_dao(state)

    async def _handle_scaling(self, action: str):
        """Handle scaling actions"""
        if action == "optimize":
            # Scale down idle resources
            logger.info("🔧 Optimizing resource allocation")
        elif action == "emergency_scale":
            # Emergency scale-up
            logger.critical("🚨 Emergency scaling initiated")

    async def _log_to_dao(self, state: MAPEKState):
        """Log significant events to DAO audit trail"""
        if self.dao_logger:
            event_data = {
                "state": state.metrics.state.value,
                "phi_ratio": state.metrics.phi_ratio,
                "directives": state.directives,
                "actions_taken": state.actions_taken,
                "timestamp": state.timestamp,
            }
            try:
                cid = await self.dao_logger.log_consciousness_event(event_data)
                logger.info(f"📜 DAO audit logged: {cid}")
            except Exception as e:
                logger.error(f"Failed to log to DAO: {e}")
                safe_directives = self._safe_mode_directives(
                    reason_id="cid_log_failed",
                    dependency="cid_audit_log",
                    error_type=type(e).__name__,
                    base_directives=state.directives,
                    raw_metrics=getattr(state.metrics, "raw_metrics", None),
                )
                self._publish_safe_mode_event(
                    directives=safe_directives,
                    metrics=getattr(state.metrics, "raw_metrics", None),
                    reason="cid_log_failed",
                    error_type=type(e).__name__,
                )
        else:
            logger.info(
                f"📜 DAO audit (simulation): {state.metrics.state.value} state recorded"
            )
