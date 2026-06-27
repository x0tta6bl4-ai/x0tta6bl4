"""Shared policy helpers for mesh metric-source evidence."""

from __future__ import annotations

from typing import Any, Dict

from src.coordination.events import EventType

MESH_METRIC_POLICY_KEY = "mesh_metric_evidence_policy"
MESH_METRIC_POLICY_NAME = "dataplane_required_or_explicit_estimate_marker"

DECISION_DATAPLANE_CONFIRMED = "dataplane_confirmed"
DECISION_ESTIMATE_OR_FALLBACK = "estimate_or_fallback_based"
DECISION_SOURCE_PRESENT_WITHOUT_LATENCY_QUALITY = (
    "metric_source_present_without_latency_quality"
)
DECISION_SOURCE_MISSING = "metric_source_missing"
DECISION_POLICY_MISSING = "policy_missing"

HIGH_RISK_ALLOWED_DECISION_BASES = {
    DECISION_DATAPLANE_CONFIRMED,
}


def _nonnegative_float(value: Any) -> float:
    try:
        return max(0.0, float(value or 0.0))
    except (TypeError, ValueError):
        return 0.0


def safe_source_counts(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict):
        return {}
    safe: Dict[str, int] = {}
    for key, count in value.items():
        try:
            safe[str(key)] = int(count)
        except (TypeError, ValueError):
            continue
    return dict(sorted(safe.items()))


def build_mesh_metric_evidence_policy(
    raw_metrics: Dict[str, Any] | None,
) -> Dict[str, Any]:
    raw_metrics = raw_metrics if isinstance(raw_metrics, dict) else {}
    dataplane_samples = _nonnegative_float(
        raw_metrics.get("mesh_metric_dataplane_samples", 0.0)
    )
    estimated_samples = _nonnegative_float(
        raw_metrics.get("mesh_metric_estimated_samples", 0.0)
    )
    fallback_samples = _nonnegative_float(
        raw_metrics.get("mesh_metric_fallback_samples", 0.0)
    )
    source_available = _nonnegative_float(
        raw_metrics.get("mesh_metric_source_available", 0.0)
    ) > 0.0

    if dataplane_samples > 0.0:
        decision_basis = DECISION_DATAPLANE_CONFIRMED
        control_risk = "normal"
        allows_high_risk = True
    elif estimated_samples > 0.0 or fallback_samples > 0.0:
        decision_basis = DECISION_ESTIMATE_OR_FALLBACK
        control_risk = "blocked"
        allows_high_risk = False
    elif source_available:
        decision_basis = DECISION_SOURCE_PRESENT_WITHOUT_LATENCY_QUALITY
        control_risk = "blocked"
        allows_high_risk = False
    else:
        decision_basis = DECISION_SOURCE_MISSING
        control_risk = "blocked"
        allows_high_risk = False

    return {
        "policy": MESH_METRIC_POLICY_NAME,
        "decision_basis": decision_basis,
        "control_risk": control_risk,
        "dataplane_confirmed": dataplane_samples > 0.0,
        "estimate_or_fallback_based": (
            dataplane_samples <= 0.0
            and (estimated_samples > 0.0 or fallback_samples > 0.0)
        ),
        "allows_high_risk_mesh_actions": allows_high_risk,
        "sample_counts": {
            "dataplane_probe": int(dataplane_samples),
            "admin_estimate_or_peer_field": int(estimated_samples),
            "default_baseline": int(fallback_samples),
        },
        "redacted": True,
    }


def safe_mesh_metric_evidence_policy(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "policy_present": False,
            "policy": MESH_METRIC_POLICY_NAME,
            "decision_basis": DECISION_POLICY_MISSING,
            "control_risk": "blocked",
            "dataplane_confirmed": False,
            "estimate_or_fallback_based": False,
            "allows_high_risk_mesh_actions": False,
            "sample_counts": {},
            "redacted": True,
        }

    sample_counts = value.get("sample_counts")
    if not isinstance(sample_counts, dict):
        sample_counts = {}

    return {
        "policy_present": True,
        "policy": str(value.get("policy", "unknown")),
        "decision_basis": str(value.get("decision_basis", "unknown")),
        "control_risk": str(value.get("control_risk", "unknown")),
        "dataplane_confirmed": bool(value.get("dataplane_confirmed", False)),
        "estimate_or_fallback_based": bool(
            value.get("estimate_or_fallback_based", False)
        ),
        "allows_high_risk_mesh_actions": bool(
            value.get("allows_high_risk_mesh_actions", False)
        ),
        "sample_counts": safe_source_counts(sample_counts),
        "redacted": True,
    }


def mesh_metric_policy_allows_high_risk(
    value: Any,
    *,
    require_present: bool = True,
) -> bool:
    policy = safe_mesh_metric_evidence_policy(value)
    if not policy["policy_present"]:
        return not require_present
    return bool(
        policy["allows_high_risk_mesh_actions"]
        and policy["decision_basis"] in HIGH_RISK_ALLOWED_DECISION_BASES
    )


def mesh_metric_policy_context(
    value: Any,
    *,
    high_risk_action: str,
) -> Dict[str, Any]:
    policy = safe_mesh_metric_evidence_policy(value)
    return {
        "mesh_high_risk_action": high_risk_action,
        "mesh_metric_decision_basis": policy["decision_basis"],
        "mesh_metric_control_risk": policy["control_risk"],
        "mesh_estimate_or_fallback_based": policy["estimate_or_fallback_based"],
        "mesh_dataplane_confirmed": policy["dataplane_confirmed"],
    }


def _policy_from_event_payload(payload: Any) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None

    directives = payload.get("directives")
    if isinstance(directives, dict):
        policy = directives.get(MESH_METRIC_POLICY_KEY)
        if isinstance(policy, dict):
            return policy

    result = payload.get("result")
    if isinstance(result, dict):
        policy = result.get("metric_evidence_policy")
        if isinstance(policy, dict):
            return policy

    policy = payload.get(MESH_METRIC_POLICY_KEY)
    if isinstance(policy, dict):
        return policy

    return None


def latest_mesh_metric_policy_evidence(
    bus: Any,
    *,
    source_agents: tuple[str, ...] = ("core-mapek-loop", "mesh-action-enforcer"),
    limit: int = 100,
) -> Dict[str, Any]:
    if bus is None:
        return {
            "status": "missing",
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            MESH_METRIC_POLICY_KEY: safe_mesh_metric_evidence_policy(None),
            "redacted": True,
        }

    terminal_event_types = {
        EventType.PIPELINE_STAGE_END,
        EventType.TASK_BLOCKED,
        EventType.TASK_FAILED,
        EventType.COORDINATION_REQUEST,
    }
    try:
        events = bus.get_event_history(
            source_agents=set(source_agents),
            limit=limit,
        )
    except Exception:
        return {
            "status": "unavailable",
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            MESH_METRIC_POLICY_KEY: safe_mesh_metric_evidence_policy(None),
            "redacted": True,
        }

    for event in reversed(events):
        if event.event_type not in terminal_event_types:
            continue
        policy = _policy_from_event_payload(getattr(event, "data", None))
        if policy is None:
            continue
        event_type = getattr(event, "event_type", "")
        event_type_value = getattr(event_type, "value", str(event_type))
        return {
            "status": "available",
            "source_agents": [str(getattr(event, "source_agent", "unknown"))],
            "event_ids": [str(getattr(event, "event_id", ""))],
            "events_total": 1,
            "event_type": event_type_value,
            MESH_METRIC_POLICY_KEY: safe_mesh_metric_evidence_policy(policy),
            "redacted": True,
        }

    return {
        "status": "missing",
        "source_agents": [],
        "event_ids": [],
        "events_total": 0,
        MESH_METRIC_POLICY_KEY: safe_mesh_metric_evidence_policy(None),
        "redacted": True,
    }
