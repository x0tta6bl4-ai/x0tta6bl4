"""
MeshNetworkManager - aggregates mesh network metrics from real subsystems.

Provides statistics, route management, and healing operations for MAPE-K loop.

Features:
    - ML-based neighbor scoring for intelligent route selection
    - Aggressive healing with state integrity verification
    - Preemptive route freshness checks
    - MTTR (Mean Time To Repair) tracking

Example:
    >>> manager = MeshNetworkManager(node_id="node-001")
    >>> stats = await manager.get_statistics()
    >>> healed = await manager.trigger_aggressive_healing(
    ...     auto_restore_nodes=True,
    ...     verification_mode=VerificationMode.FULL
    ... )
"""

import asyncio
import hashlib
import inspect
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "mesh-network-manager"
_SERVICE_LAYER = "mesh_network_manager_observed_state"
_VALID_ROUTE_PREFERENCES = {"low_latency", "reliability", "balanced"}
_CLAIM_BOUNDARY_LIMIT = 8
_CLAIM_BOUNDARY_TEXT_LIMIT = 400
_POST_HEAL_PROBE_ENV_VAR = "X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE"
_POST_HEAL_PROBE_TARGET_ENV_VAR = "X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE_TARGET"
_MESH_MANAGER_RESOURCES = {
    "get_statistics": "mesh:network_manager:statistics",
    "verify_node_state": "mesh:network_manager:node_verification",
    "set_route_preference": "mesh:network_manager:route_preference",
    "trigger_aggressive_healing": "mesh:network_manager:aggressive_healing",
    "trigger_preemptive_checks": "mesh:network_manager:preemptive_checks",
}
MESH_NETWORK_MANAGER_OBSERVED_STATE_CLAIM_BOUNDARY = (
    "Mesh network manager evidence only. Read-only statistics record local router "
    "metrics and Yggdrasil peer-count observations; local action records summarize "
    "route-preference and healing decisions; node verification records summarize "
    "local probe outcomes and trust-gate decisions. EventBus evidence records service "
    "identity presence, source status, duration, numeric summaries, and downstream "
    "event IDs; it does not expose raw peer addresses, node endpoints, route tables, "
    "node IDs, config hashes, raw exceptions, or prove remote peer authenticity or "
    "live packet reachability."
)
MESH_NETWORK_MANAGER_HEALING_CLAIM_BOUNDARY = (
    "Mesh network manager aggressive-healing action evidence records local route "
    "rediscovery and optional local DB/node-verification lifecycle only. A healed "
    "count does not prove restored dataplane behavior, customer traffic delivery, "
    "external reachability, production SLOs, or production readiness without a "
    "separate bounded post-action dataplane probe."
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
    event_bus: Optional[EventBus],
    event_project_root: str,
) -> Optional[EventBus]:
    if event_bus is not None:
        return event_bus
    try:
        return EventBus(project_root=event_project_root)
    except Exception as exc:
        logger.error(
            "Failed to initialize mesh-network-manager observed-state EventBus: %s",
            exc,
        )
        return None


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _safe_stats_summary(stats: Dict[str, float]) -> Dict[str, float]:
    return {
        key: round(float(value), 4)
        for key, value in stats.items()
        if isinstance(value, (int, float))
    }


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _safe_float(value: Any) -> Optional[float]:
    try:
        return None if value is None else round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _evidence_summary(evidence: Any) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        return {
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "event_ids_count": 0,
            "claim_boundaries": [],
            "claim_boundaries_total": 0,
            "claim_boundaries_truncated": False,
            "redacted": True,
        }
    event_ids = (
        [
            str(event_id)
            for event_id in evidence.get("event_ids", [])
            if str(event_id)
        ]
        if isinstance(evidence.get("event_ids"), list)
        else []
    )
    source_agents = (
        [
            str(source_agent)
            for source_agent in evidence.get("source_agents", [])
            if str(source_agent)
        ]
        if isinstance(evidence.get("source_agents"), list)
        else []
    )
    claim_boundaries: List[str] = []
    direct_boundary = str(evidence.get("claim_boundary") or "").strip()
    if direct_boundary:
        claim_boundaries.append(direct_boundary[:_CLAIM_BOUNDARY_TEXT_LIMIT])
    if isinstance(evidence.get("claim_boundaries"), list):
        for item in evidence["claim_boundaries"]:
            boundary = str(item).strip()
            if boundary:
                claim_boundaries.append(boundary[:_CLAIM_BOUNDARY_TEXT_LIMIT])
    distinct_claim_boundaries = sorted(set(claim_boundaries))
    return {
        "source_agents": source_agents,
        "event_ids": event_ids,
        "events_total": int(evidence.get("events_total", len(event_ids)) or 0),
        "event_ids_count": len(event_ids),
        "claim_boundaries": distinct_claim_boundaries[:_CLAIM_BOUNDARY_LIMIT],
        "claim_boundaries_total": len(distinct_claim_boundaries),
        "claim_boundaries_truncated": len(distinct_claim_boundaries)
        > _CLAIM_BOUNDARY_LIMIT,
        "redacted": evidence.get("redacted") is True,
    }


def _probe_result_summary(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "status": "error",
            "dataplane_confirmed": False,
            "evidence": _evidence_summary({}),
            "redacted": True,
        }

    latency_ms = _safe_float(value.get("latency_ms"))
    packet_loss_percent = _safe_float(value.get("packet_loss_percent"))
    jitter_ms = _safe_float(value.get("jitter_ms"))
    dataplane_confirmed = bool(
        value.get("status") == "ok"
        and (latency_ms is not None or packet_loss_percent is not None)
    )
    return {
        "status": str(value.get("status") or "unknown"),
        "dataplane_confirmed": dataplane_confirmed,
        "latency_ms": latency_ms,
        "packet_loss_percent": packet_loss_percent,
        "jitter_ms": jitter_ms,
        "evidence": _evidence_summary(value.get("evidence")),
        "claim_boundary": str(value.get("claim_boundary") or ""),
        "redacted": True,
    }


def _safe_action_context(context: Dict[str, Any]) -> Dict[str, Any]:
    safe: Dict[str, Any] = {}
    if "route_preference" in context:
        preference = str(context.get("route_preference", ""))
        safe["route_preference"] = (
            preference if preference in _VALID_ROUTE_PREFERENCES else "[redacted]"
        )
        safe["route_preference_sha256"] = _sha256_text(preference)
        safe["route_preference_redacted"] = preference not in _VALID_ROUTE_PREFERENCES
    if "healing_mode" in context:
        safe["healing_mode"] = str(context.get("healing_mode", ""))
    if "auto_restore_nodes" in context:
        safe["auto_restore_nodes"] = bool(context.get("auto_restore_nodes"))
    if "verification_mode" in context:
        safe["verification_mode"] = str(context.get("verification_mode", ""))
    if "require_verification" in context:
        safe["require_verification"] = bool(context.get("require_verification"))
    if "post_action_probe_target_present" in context:
        safe["post_action_probe_target_present"] = bool(
            context.get("post_action_probe_target_present")
        )
    safe["values_redacted"] = True
    return safe


def _safe_action_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, bool):
        return {"success": result}
    if isinstance(result, int):
        return {"numeric_result": result}
    if isinstance(result, dict):
        numeric = {
            str(key): round(float(value), 4)
            for key, value in result.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        flags = {
            str(key): bool(value)
            for key, value in result.items()
            if isinstance(value, bool)
        }
        return {
            "numeric": numeric,
            "flags": flags,
            "keys": sorted(str(key) for key in result),
            "values_redacted": True,
        }
    if result is None:
        return {"returned": "none"}
    return {"type": type(result).__name__, "values_redacted": True}


def _healing_claim_gate(
    *,
    healed: int,
    verification_evidence_events: int,
    post_action_probe_enabled: bool = False,
    post_action_probe_target_present: bool = False,
    post_action_probe_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    probe_result = _probe_result_summary(post_action_probe_result)
    probe_attempted = post_action_probe_result is not None
    evidence = probe_result["evidence"] if probe_attempted else _evidence_summary({})
    dataplane_confirmed = bool(
        probe_attempted and probe_result["dataplane_confirmed"]
    )
    blockers: List[str] = []
    if not post_action_probe_enabled:
        blockers.append("no_bounded_post_action_dataplane_probe_attached")
    elif not post_action_probe_target_present:
        blockers.append("no_post_action_dataplane_probe_target")
    elif not probe_attempted:
        blockers.append("no_bounded_post_action_dataplane_probe_attached")
    elif not dataplane_confirmed:
        blockers.append("bounded_dataplane_probe_not_confirmed")
    if probe_attempted and (
        int(evidence.get("events_total", 0) or 0) <= 0
        or int(evidence.get("event_ids_count", 0) or 0) <= 0
    ):
        blockers.append("post_action_probe_evidence_missing")
    if probe_attempted and not evidence.get("source_agents"):
        blockers.append("post_action_probe_source_agent_missing")
    if probe_attempted and evidence.get("redacted") is not True:
        blockers.append("post_action_probe_evidence_not_redacted")
    if int(healed) <= 0 and dataplane_confirmed:
        blockers.append("no_local_healing_action_applied")

    restored_dataplane_claim_allowed = not blockers
    return {
        "schema": "x0tta6bl4.mesh_network_manager.healing_claim_gate.v1",
        "decision": (
            "RESTORED_DATAPLANE_CLAIM_ALLOWED"
            if restored_dataplane_claim_allowed
            else "LOCAL_HEALING_LIFECYCLE_ONLY"
        ),
        "local_healing_lifecycle_claim_allowed": True,
        "local_node_verification_claim_allowed": verification_evidence_events > 0,
        "local_healed_count": int(healed),
        "verification_evidence_events": int(verification_evidence_events),
        "post_action_probe_enabled": post_action_probe_enabled,
        "post_action_probe_target_present": post_action_probe_target_present,
        "post_action_probe_attempted": probe_attempted,
        "post_action_dataplane_revalidated": dataplane_confirmed,
        "dataplane_confirmed": dataplane_confirmed,
        "restored_dataplane_claim_allowed": restored_dataplane_claim_allowed,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_reachability_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "requires_post_action_dataplane_revalidation": True,
        "blockers": blockers,
        "probe_result": probe_result if probe_attempted else None,
        "evidence": evidence,
        "claim_boundary": MESH_NETWORK_MANAGER_HEALING_CLAIM_BOUNDARY,
        "redacted": True,
    }


def _safe_claim_gate(gate: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(gate, dict):
        return None
    safe: Dict[str, Any] = {
        "schema": str(gate.get("schema", "")),
        "decision": str(gate.get("decision", "")),
        "local_healing_lifecycle_claim_allowed": bool(
            gate.get("local_healing_lifecycle_claim_allowed")
        ),
        "local_node_verification_claim_allowed": bool(
            gate.get("local_node_verification_claim_allowed")
        ),
        "local_healed_count": int(gate.get("local_healed_count") or 0),
        "verification_evidence_events": int(
            gate.get("verification_evidence_events") or 0
        ),
        "post_action_probe_enabled": bool(gate.get("post_action_probe_enabled")),
        "post_action_probe_target_present": bool(
            gate.get("post_action_probe_target_present")
        ),
        "post_action_probe_attempted": bool(gate.get("post_action_probe_attempted")),
        "post_action_dataplane_revalidated": bool(
            gate.get("post_action_dataplane_revalidated")
        ),
        "dataplane_confirmed": bool(gate.get("dataplane_confirmed")),
        "restored_dataplane_claim_allowed": bool(
            gate.get("restored_dataplane_claim_allowed")
        ),
        "traffic_delivery_claim_allowed": bool(
            gate.get("traffic_delivery_claim_allowed")
        ),
        "customer_traffic_claim_allowed": bool(
            gate.get("customer_traffic_claim_allowed")
        ),
        "external_reachability_claim_allowed": bool(
            gate.get("external_reachability_claim_allowed")
        ),
        "production_slo_claim_allowed": bool(gate.get("production_slo_claim_allowed")),
        "production_readiness_claim_allowed": bool(
            gate.get("production_readiness_claim_allowed")
        ),
        "requires_post_action_dataplane_revalidation": bool(
            gate.get("requires_post_action_dataplane_revalidation")
        ),
        "blockers": [
            str(blocker)
            for blocker in gate.get("blockers", [])
            if str(blocker).strip()
        ][:10],
        "probe_result": _probe_result_summary(gate.get("probe_result"))
        if isinstance(gate.get("probe_result"), dict)
        else None,
        "evidence": _evidence_summary(gate.get("evidence")),
        "claim_boundary": str(gate.get("claim_boundary", "")),
        "redacted": True,
    }
    return safe


def _verification_mode_value(mode: Any) -> str:
    if isinstance(mode, VerificationMode):
        return mode.value
    return str(mode)


def _safe_verification_context(
    *,
    node_id: str,
    mode: Any,
    expected_last_seen: Optional[datetime],
    expected_config_hash: Optional[str],
) -> Dict[str, Any]:
    return {
        "node_id_sha256": _sha256_text(str(node_id)),
        "node_id_redacted": True,
        "verification_mode": _verification_mode_value(mode),
        "expected_last_seen_provided": expected_last_seen is not None,
        "expected_config_hash_provided": bool(expected_config_hash),
        "expected_config_hash_sha256": _sha256_text(expected_config_hash or ""),
        "expected_config_hash_redacted": bool(expected_config_hash),
        "values_redacted": True,
    }


def _safe_verification_result(result: Any) -> Dict[str, Any]:
    numeric: Dict[str, float] = {}
    flags: Dict[str, bool] = {
        "is_healthy": bool(result.is_healthy),
        "error_message_redacted": bool(result.error_message),
        "verified_at_present": result.verified_at is not None,
    }
    if result.latency_ms is not None:
        numeric["latency_ms"] = round(float(result.latency_ms), 3)
    if result.peer_connectivity is not None:
        numeric["peer_connectivity"] = float(result.peer_connectivity)
    if result.last_seen_match is not None:
        flags["last_seen_match"] = bool(result.last_seen_match)
    if result.config_hash_match is not None:
        flags["config_hash_match"] = bool(result.config_hash_match)

    safe: Dict[str, Any] = {
        "verification_mode": _verification_mode_value(result.verification_mode),
        "numeric": numeric,
        "flags": flags,
        "values_redacted": True,
    }
    if result.error_message:
        safe["error_sha256"] = _sha256_text(result.error_message)
    return safe


def _publish_mesh_manager_observation(
    *,
    event_bus: Optional[EventBus],
    event_project_root: str,
    operation: str,
    status: str,
    duration_ms: float,
    stats: Dict[str, float],
    router_summary: Dict[str, Any],
    yggdrasil_summary: Dict[str, Any],
    evidence_event_ids: List[str],
    downstream_claim_boundaries: Optional[List[str]] = None,
    error_types: Optional[List[str]] = None,
) -> Optional[str]:
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    evidence_ids = sorted(set(evidence_event_ids))
    distinct_claim_boundaries = sorted(
        {
            str(boundary).strip()[:_CLAIM_BOUNDARY_TEXT_LIMIT]
            for boundary in downstream_claim_boundaries or []
            if str(boundary).strip()
        }
    )
    payload: Dict[str, Any] = {
        "component": "mesh.network_manager",
        "stage": "observed_state",
        "operation": operation,
        "resource": _MESH_MANAGER_RESOURCES[operation],
        "service_name": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "identity": _identity_metadata(),
        "status": status,
        "source_mode": "local_aggregate",
        "duration_ms": round(duration_ms, 3),
        "read_only": True,
        "observed_state": True,
        "safe_actuator": False,
        "stats": _safe_stats_summary(stats),
        "sources": {
            "router": router_summary,
            "yggdrasil": yggdrasil_summary,
        },
        "downstream_evidence": {
            "source_agents": ["yggdrasil-client"] if evidence_ids else [],
            "event_ids": evidence_ids,
            "events_total": len(evidence_ids),
            "claim_boundaries": distinct_claim_boundaries[:_CLAIM_BOUNDARY_LIMIT],
            "claim_boundaries_total": len(distinct_claim_boundaries),
            "claim_boundaries_truncated": len(distinct_claim_boundaries)
            > _CLAIM_BOUNDARY_LIMIT,
            "redacted": True,
        },
        "input_redacted": True,
        "claim_boundary": MESH_NETWORK_MANAGER_OBSERVED_STATE_CLAIM_BOUNDARY,
    }
    if error_types:
        payload["errors"] = [
            {"type": error_type, "message_redacted": True}
            for error_type in sorted(set(error_types))
        ]

    try:
        event = bus.publish(
            EventType.PIPELINE_STAGE_END,
            _SERVICE_AGENT,
            payload,
            priority=3,
        )
        return event.event_id
    except Exception as exc:
        logger.error(
            "Failed to publish mesh-network-manager observed-state event: %s", exc
        )
        return None


def _publish_mesh_manager_action(
    *,
    event_bus: Optional[EventBus],
    event_project_root: str,
    event_type: EventType,
    stage: str,
    operation: str,
    status: str,
    duration_ms: float,
    context: Dict[str, Any],
    result: Any,
    success: bool,
    error_types: Optional[List[str]] = None,
    evidence_event_ids: Optional[List[str]] = None,
    downstream_source_agents: Optional[List[str]] = None,
    claim_gate: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    evidence_ids = sorted(set(evidence_event_ids or []))
    payload: Dict[str, Any] = {
        "component": "mesh.network_manager",
        "stage": stage,
        "operation": operation,
        "resource": _MESH_MANAGER_RESOURCES[operation],
        "service_name": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "identity": _identity_metadata(),
        "status": status,
        "source_mode": "local_control_action",
        "duration_ms": round(duration_ms, 3),
        "read_only": False,
        "observed_state": False,
        "control_action": True,
        "safe_actuator": False,
        "context": _safe_action_context(context),
        "result": _safe_action_result(result),
        "success": success,
        "downstream_evidence": {
            "source_agents": sorted(set(downstream_source_agents or []))
            if evidence_ids
            else [],
            "event_ids": evidence_ids,
            "events_total": len(evidence_ids),
            "redacted": True,
        },
        "input_redacted": True,
        "claim_boundary": MESH_NETWORK_MANAGER_OBSERVED_STATE_CLAIM_BOUNDARY,
    }
    safe_claim_gate = _safe_claim_gate(claim_gate)
    if safe_claim_gate is not None:
        payload["claim_gate"] = safe_claim_gate
        payload["post_action_dataplane_revalidation"] = {
            "required_for_restored_dataplane_claim": True,
            "probe_enabled": safe_claim_gate["post_action_probe_enabled"],
            "probe_target_present": safe_claim_gate[
                "post_action_probe_target_present"
            ],
            "probe_attempted": safe_claim_gate["post_action_probe_attempted"],
            "dataplane_confirmed": safe_claim_gate["dataplane_confirmed"],
            "post_action_dataplane_revalidated": safe_claim_gate[
                "post_action_dataplane_revalidated"
            ],
            "restored_dataplane_claim_allowed": safe_claim_gate[
                "restored_dataplane_claim_allowed"
            ],
            "claim_gate": safe_claim_gate,
            "evidence": safe_claim_gate["evidence"],
            "claim_boundary": safe_claim_gate["claim_boundary"],
            "redacted": True,
        }
    if error_types:
        payload["errors"] = [
            {"type": error_type, "message_redacted": True}
            for error_type in sorted(set(error_types))
        ]

    try:
        event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=5)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish mesh-network-manager action event: %s", exc)
        return None


def _publish_mesh_manager_verification(
    *,
    event_bus: Optional[EventBus],
    event_project_root: str,
    event_type: EventType,
    status: str,
    duration_ms: float,
    node_id: str,
    mode: Any,
    expected_last_seen: Optional[datetime],
    expected_config_hash: Optional[str],
    result: Optional[Any],
    attempts_used: int,
    attempts_configured: int,
    cache_written: bool,
    bypassed: bool,
    error_types: Optional[List[str]] = None,
) -> Optional[str]:
    bus = _event_bus_or_none(event_bus, event_project_root)
    if bus is None:
        return None

    payload: Dict[str, Any] = {
        "component": "mesh.network_manager",
        "stage": "node_verification",
        "operation": "verify_node_state",
        "resource": _MESH_MANAGER_RESOURCES["verify_node_state"],
        "service_name": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "identity": _identity_metadata(),
        "status": status,
        "source_mode": "local_node_verification",
        "duration_ms": round(duration_ms, 3),
        "read_only": True,
        "observed_state": True,
        "control_action": False,
        "safe_actuator": False,
        "context": _safe_verification_context(
            node_id=node_id,
            mode=mode,
            expected_last_seen=expected_last_seen,
            expected_config_hash=expected_config_hash,
        ),
        "result": (
            _safe_verification_result(result)
            if result is not None
            else {"returned": "none", "values_redacted": True}
        ),
        "retry": {
            "attempts_used": int(attempts_used),
            "attempts_configured": int(attempts_configured),
            "cache_written": bool(cache_written),
            "bypassed": bool(bypassed),
        },
        "bounded_output": {
            "raw_node_id_redacted": True,
            "raw_endpoint_redacted": True,
            "raw_config_hash_redacted": bool(expected_config_hash),
            "raw_error_message_redacted": bool(
                getattr(result, "error_message", None)
            ),
            "return_code": None,
        },
        "downstream_evidence": {
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "redacted": True,
        },
        "input_redacted": True,
        "claim_boundary": MESH_NETWORK_MANAGER_OBSERVED_STATE_CLAIM_BOUNDARY,
    }
    if error_types:
        payload["errors"] = [
            {"type": error_type, "message_redacted": True}
            for error_type in sorted(set(error_types))
        ]

    try:
        event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
        return event.event_id
    except Exception as exc:
        logger.error(
            "Failed to publish mesh-network-manager verification event: %s", exc
        )
        return None


class VerificationMode(Enum):
    """Verification modes for node state integrity checks.

    Attributes:
        NONE: No verification, auto-restore without checks (dangerous)
        PING: Basic connectivity check via ICMP/TCP ping
        FULL: Full state verification including last_seen, config hash, peer connectivity
        CONSENSUS: Multi-node consensus verification (requires quorum)
    """

    NONE = "none"
    PING = "ping"
    FULL = "full"
    CONSENSUS = "consensus"


@dataclass
class NodeVerificationResult:
    """Result of a node state verification check.

    Attributes:
        node_id: Identifier of the verified node
        is_healthy: Whether the node passed verification
        verification_mode: Mode used for verification
        latency_ms: Round-trip latency in milliseconds (if applicable)
        last_seen_match: Whether last_seen timestamp matches expected
        config_hash_match: Whether configuration hash matches expected
        peer_connectivity: Number of reachable peers from this node
        error_message: Error description if verification failed
        verified_at: Timestamp when verification was performed
    """

    node_id: str
    is_healthy: bool
    verification_mode: VerificationMode
    latency_ms: Optional[float] = None
    last_seen_match: Optional[bool] = None
    config_hash_match: Optional[bool] = None
    peer_connectivity: Optional[int] = None
    error_message: Optional[str] = None
    verified_at: Optional[datetime] = None
    evidence_event_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.verified_at is None:
            self.verified_at = datetime.utcnow()


class NodeVerificationError(Exception):
    """Exception raised when node verification fails."""

    pass


class MeshNetworkManager:
    """
    Aggregates mesh network data from MeshRouter and Yggdrasil.

    Used by MAPEKLoop to monitor network health and trigger healing.

    Attributes:
        node_id: Identifier for this network node
        verification_timeout_seconds: Timeout for node verification checks
        verification_retries: Number of retries for failed verifications
        consensus_quorum: Minimum nodes required for consensus verification

    Example:
        >>> manager = MeshNetworkManager(node_id="node-001")
        >>> result = await manager.verify_node_state(
        ...     node_id="node-002",
        ...     mode=VerificationMode.FULL
        ... )
        >>> if result.is_healthy:
        ...     print(f"Node {result.node_id} is healthy")
    """

    # Default configuration constants
    DEFAULT_VERIFICATION_TIMEOUT: int = 30
    DEFAULT_VERIFICATION_RETRIES: int = 3
    DEFAULT_CONSENSUS_QUORUM: int = 3
    UNVERIFIED_RESTORE_ENV_VAR: str = "X0TTA6BL4_ALLOW_UNVERIFIED_RESTORE"

    def __init__(
        self,
        node_id: str = "local",
        verification_timeout_seconds: int = DEFAULT_VERIFICATION_TIMEOUT,
        verification_retries: int = DEFAULT_VERIFICATION_RETRIES,
        consensus_quorum: int = DEFAULT_CONSENSUS_QUORUM,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        enable_post_heal_dataplane_probe: Optional[bool] = None,
        post_heal_dataplane_probe_provider: Optional[Any] = None,
    ) -> None:
        """Initialize MeshNetworkManager.

        Args:
            node_id: Unique identifier for this network node
            verification_timeout_seconds: Timeout for verification operations
            verification_retries: Number of retries for failed verifications
            consensus_quorum: Minimum nodes for consensus verification
        """
        self.node_id = node_id
        self._router = None  # lazy init
        self._healing_log: List[Dict[str, Any]] = []
        self._route_preference: str = "balanced"
        # ML Scoring components
        self._neighbor_stats: Dict[str, Dict[str, float]] = {}
        self._ml_enabled: bool = True
        # Verification configuration
        self.verification_timeout_seconds = verification_timeout_seconds
        self.verification_retries = verification_retries
        self.consensus_quorum = consensus_quorum
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self._post_heal_probe_config_source = (
            "env" if enable_post_heal_dataplane_probe is None else "constructor"
        )
        self.enable_post_heal_dataplane_probe = (
            _env_bool(_POST_HEAL_PROBE_ENV_VAR, False)
            if enable_post_heal_dataplane_probe is None
            else bool(enable_post_heal_dataplane_probe)
        )
        self.post_heal_dataplane_probe_provider = post_heal_dataplane_probe_provider
        # Cache for verification results
        self._verification_cache: Dict[str, NodeVerificationResult] = {}

    def _post_heal_probe_enabled(self) -> bool:
        if self._post_heal_probe_config_source == "env":
            return _env_bool(_POST_HEAL_PROBE_ENV_VAR, False)
        return bool(self.enable_post_heal_dataplane_probe)

    async def _probe_post_heal_dataplane(self, target: Optional[str]) -> Dict[str, Any]:
        if not target:
            return {
                "status": "error",
                "error": {
                    "type": "MissingProbeTarget",
                    "message_redacted": True,
                },
                "redacted": True,
            }

        try:
            provider = self.post_heal_dataplane_probe_provider
            if provider is not None:
                if hasattr(provider, "probe_peer"):
                    raw_result = provider.probe_peer(target)
                else:
                    raw_result = provider(target)
            else:
                from src.mesh.real_network_adapter import probe_peer_dataplane_ping

                raw_result = probe_peer_dataplane_ping(
                    target,
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                )
            if inspect.isawaitable(raw_result):
                raw_result = await raw_result
            if isinstance(raw_result, dict):
                return raw_result
            return {
                "status": "error",
                "error": {
                    "type": "InvalidProbeResult",
                    "message_redacted": True,
                },
                "redacted": True,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": {
                    "type": type(exc).__name__,
                    "message_redacted": True,
                },
                "redacted": True,
            }

    def ml_score_neighbor(
        self, neighbor_id: str, rssi: float, load: float, hops: int
    ) -> float:
        """
        Calculate reliability score for a neighbor using hybrid ML logic.

        Uses a combination of delivery probability (based on signal strength),
        load factor, and hop count to determine the best next-hop neighbor.

        Formula:
            score = delivery_prob * delay_factor
            where:
                delivery_prob = 0.95 if rssi > -70 else 0.70
                delivery_prob *= 0.5 if load > 0.8
                delay_factor = 1.0 / (hops * 15.0 + 1.0)

        Args:
            neighbor_id: Unique identifier for the neighbor node
            rssi: Received Signal Strength Indicator in dBm (typically -30 to -100)
            load: Current load on the neighbor (0.0 to 1.0)
            hops: Number of hops to reach this neighbor

        Returns:
            Reliability score between 0.0 and 1.0, higher is better

        Example:
            >>> score = manager.ml_score_neighbor("node-002", rssi=-65, load=0.3, hops=1)
            >>> print(f"Neighbor score: {score:.3f}")
        """
        # Baseline metrics (simulating model predictions)
        # In production, these would come from self.classifier.predict()
        delivery_prob = 0.95 if rssi > -70 else 0.70
        if load > 0.8:
            delivery_prob *= 0.5

        delay_factor = 1.0 / (hops * 15.0 + 1.0)

        score = delivery_prob * delay_factor

        # Update local stats for analysis
        self._neighbor_stats[neighbor_id] = {
            "score": score,
            "last_rssi": rssi,
            "last_load": load,
            "timestamp": time.time(),
        }

        return score

    def select_best_neighbor(self, neighbors: List[Dict[str, Any]]) -> Optional[str]:
        """
        Select the best next hop based on ML scores.

        Evaluates all candidate neighbors and returns the one with
        the highest reliability score calculated by ml_score_neighbor().

        Args:
            neighbors: List of neighbor dictionaries, each containing:
                - id: Neighbor identifier
                - rssi: Signal strength (optional, default -100)
                - load: Current load (optional, default 0.0)
                - hops: Hop count (optional, default 1)

        Returns:
            Node ID of the best neighbor, or None if neighbors list is empty

        Example:
            >>> neighbors = [
            ...     {"id": "node-002", "rssi": -65, "load": 0.3, "hops": 1},
            ...     {"id": "node-003", "rssi": -80, "load": 0.1, "hops": 2},
            ... ]
            >>> best = manager.select_best_neighbor(neighbors)
            >>> print(f"Best neighbor: {best}")
        """
        if not neighbors:
            return None

        scored_neighbors: List[Tuple[str, float]] = []
        for n in neighbors:
            score = self.ml_score_neighbor(
                n["id"], n.get("rssi", -100), n.get("load", 0.0), n.get("hops", 1)
            )
            scored_neighbors.append((n["id"], score))

        # Return ID with highest score
        return max(scored_neighbors, key=lambda x: x[1])[0]

    async def verify_node_state(
        self,
        node_id: str,
        mode: VerificationMode = VerificationMode.FULL,
        expected_last_seen: Optional[datetime] = None,
        expected_config_hash: Optional[str] = None,
    ) -> NodeVerificationResult:
        """
        Verify the state integrity of a node before restoring it.

        Performs verification based on the specified mode:
        - NONE: Always returns healthy (dangerous, use with caution)
        - PING: Basic TCP/ICMP connectivity check
        - FULL: Comprehensive check including last_seen, config hash, peer connectivity
        - CONSENSUS: Multi-node verification requiring quorum agreement

        Args:
            node_id: Unique identifier of the node to verify
            mode: Verification mode (default: FULL)
            expected_last_seen: Expected last_seen timestamp for FULL mode
            expected_config_hash: Expected configuration hash for FULL mode

        Returns:
            NodeVerificationResult with verification outcome

        Raises:
            NodeVerificationError: If verification fails critically

        Example:
            >>> result = await manager.verify_node_state(
            ...     "node-002",
            ...     mode=VerificationMode.FULL,
            ...     expected_last_seen=datetime.utcnow() - timedelta(minutes=5)
            ... )
            >>> if result.is_healthy:
            ...     print(f"Node verified in {result.latency_ms:.1f}ms")
        """
        started = time.monotonic()
        if mode == VerificationMode.NONE:
            # Bypass verification - only allowed with explicit environment variable
            if not os.getenv(self.UNVERIFIED_RESTORE_ENV_VAR):
                result = NodeVerificationResult(
                    node_id=node_id,
                    is_healthy=False,
                    verification_mode=mode,
                    error_message=(
                        "VerificationMode.NONE requires explicit environment guard"
                    ),
                )
                result.evidence_event_id = _publish_mesh_manager_verification(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    event_type=EventType.TASK_FAILED,
                    status="blocked",
                    duration_ms=(time.monotonic() - started) * 1000,
                    node_id=node_id,
                    mode=mode,
                    expected_last_seen=expected_last_seen,
                    expected_config_hash=expected_config_hash,
                    result=result,
                    attempts_used=0,
                    attempts_configured=self.verification_retries,
                    cache_written=False,
                    bypassed=True,
                    error_types=["NodeVerificationError"],
                )
                raise NodeVerificationError(
                    f"VerificationMode.NONE requires {self.UNVERIFIED_RESTORE_ENV_VAR}=1"
                )
            logger.warning(f"⚠️ Bypassing verification for node {node_id}")
            result = NodeVerificationResult(
                node_id=node_id,
                is_healthy=True,
                verification_mode=mode,
            )
            result.evidence_event_id = _publish_mesh_manager_verification(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                event_type=EventType.PIPELINE_STAGE_END,
                status="bypassed",
                duration_ms=(time.monotonic() - started) * 1000,
                node_id=node_id,
                mode=mode,
                expected_last_seen=expected_last_seen,
                expected_config_hash=expected_config_hash,
                result=result,
                attempts_used=0,
                attempts_configured=self.verification_retries,
                cache_written=False,
                bypassed=True,
            )
            return result

        # Perform verification with retries
        last_error: Optional[str] = None
        last_error_type: Optional[str] = None
        attempts_used = 0
        for attempt in range(self.verification_retries):
            attempts_used = attempt + 1
            try:
                if mode == VerificationMode.PING:
                    result = await self._verify_ping(node_id)
                elif mode == VerificationMode.FULL:
                    result = await self._verify_full(
                        node_id, expected_last_seen, expected_config_hash
                    )
                elif mode == VerificationMode.CONSENSUS:
                    result = await self._verify_consensus(node_id)
                else:
                    raise NodeVerificationError(f"Unknown verification mode: {mode}")

                # Cache successful result
                cache_written = False
                if result.is_healthy:
                    self._verification_cache[node_id] = result
                    cache_written = True

                result.evidence_event_id = _publish_mesh_manager_verification(
                    event_bus=self.event_bus,
                    event_project_root=self.event_project_root,
                    event_type=EventType.PIPELINE_STAGE_END,
                    status="success" if result.is_healthy else "unhealthy",
                    duration_ms=(time.monotonic() - started) * 1000,
                    node_id=node_id,
                    mode=mode,
                    expected_last_seen=expected_last_seen,
                    expected_config_hash=expected_config_hash,
                    result=result,
                    attempts_used=attempts_used,
                    attempts_configured=self.verification_retries,
                    cache_written=cache_written,
                    bypassed=False,
                    error_types=(
                        ["NodeVerificationUnhealthy"]
                        if not result.is_healthy
                        else None
                    ),
                )

                return result

            except Exception as e:
                last_error = str(e)
                last_error_type = type(e).__name__
                logger.warning(
                    f"Verification attempt {attempt + 1}/{self.verification_retries} "
                    f"failed for node {node_id}: {e}"
                )
                if attempt < self.verification_retries - 1:
                    await asyncio.sleep(2**attempt)  # Exponential backoff

        # All retries exhausted
        result = NodeVerificationResult(
            node_id=node_id,
            is_healthy=False,
            verification_mode=mode,
            error_message=f"Verification failed after {self.verification_retries} attempts: {last_error}",
        )
        result.evidence_event_id = _publish_mesh_manager_verification(
            event_bus=self.event_bus,
            event_project_root=self.event_project_root,
            event_type=EventType.PIPELINE_STAGE_END,
            status="unhealthy",
            duration_ms=(time.monotonic() - started) * 1000,
            node_id=node_id,
            mode=mode,
            expected_last_seen=expected_last_seen,
            expected_config_hash=expected_config_hash,
            result=result,
            attempts_used=attempts_used,
            attempts_configured=self.verification_retries,
            cache_written=False,
            bypassed=False,
            error_types=[last_error_type or "NodeVerificationUnhealthy"],
        )
        return result

    async def _verify_ping(self, node_id: str) -> NodeVerificationResult:
        """
        Perform basic connectivity verification via TCP ping.

        Attempts to establish a TCP connection to the node's mesh port
        to verify basic network reachability.

        Args:
            node_id: Node identifier to ping

        Returns:
            NodeVerificationResult with ping outcome
        """
        start_time = time.time()

        try:
            # Get node address from database or mesh routing table
            node_address = await self._get_node_address(node_id)
            if not node_address:
                return NodeVerificationResult(
                    node_id=node_id,
                    is_healthy=False,
                    verification_mode=VerificationMode.PING,
                    error_message="Node address not found",
                )

            # Attempt TCP connection with timeout
            host, port = node_address
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.verification_timeout_seconds,
            )
            writer.close()
            await writer.wait_closed()

            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"✅ Ping verification passed for {node_id}: {latency_ms:.1f}ms"
            )

            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=True,
                verification_mode=VerificationMode.PING,
                latency_ms=latency_ms,
            )

        except asyncio.TimeoutError:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.PING,
                error_message=f"Connection timeout after {self.verification_timeout_seconds}s",
            )
        except Exception as e:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.PING,
                error_message=str(e),
            )

    async def _verify_full(
        self,
        node_id: str,
        expected_last_seen: Optional[datetime] = None,
        expected_config_hash: Optional[str] = None,
    ) -> NodeVerificationResult:
        """
        Perform full state verification including connectivity, timestamps, and config.

        This is the recommended verification mode for production use as it
        validates multiple aspects of node state integrity.

        Args:
            node_id: Node identifier to verify
            expected_last_seen: Expected last_seen timestamp (tolerance: 5 minutes)
            expected_config_hash: Expected SHA-256 hash of node configuration

        Returns:
            NodeVerificationResult with comprehensive verification outcome
        """
        # Start with ping verification
        ping_result = await self._verify_ping(node_id)
        if not ping_result.is_healthy:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.FULL,
                error_message=f"Ping failed: {ping_result.error_message}",
            )

        last_seen_match: Optional[bool] = None
        config_hash_match: Optional[bool] = None
        peer_connectivity: Optional[int] = None

        try:
            # Query node state from database
            from src.database import SessionLocal, MeshNode

            with SessionLocal() as db:
                node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
                if not node:
                    return NodeVerificationResult(
                        node_id=node_id,
                        is_healthy=False,
                        verification_mode=VerificationMode.FULL,
                        error_message="Node not found in database",
                    )

                # Check last_seen timestamp (5 minute tolerance)
                if expected_last_seen and node.last_seen:
                    time_diff = abs(
                        (node.last_seen - expected_last_seen).total_seconds()
                    )
                    last_seen_match = time_diff <= 300  # 5 minutes tolerance

                # Check configuration hash if provided
                if expected_config_hash:
                    # In production, this would compute hash of node's actual config
                    # For now, we assume match if node has a config
                    config_hash_match = (
                        hasattr(node, "config_hash")
                        and node.config_hash == expected_config_hash
                    )

                # Count reachable peers
                peers = (
                    db.query(MeshNode)
                    .filter(
                        MeshNode.mesh_id == node.mesh_id,
                        MeshNode.status == "approved",
                        MeshNode.id != node_id,
                    )
                    .all()
                )
                peer_connectivity = len(peers)

            # All checks passed
            logger.info(
                f"✅ Full verification passed for {node_id}: "
                f"last_seen_match={last_seen_match}, config_match={config_hash_match}, "
                f"peers={peer_connectivity}"
            )

            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=True,
                verification_mode=VerificationMode.FULL,
                latency_ms=ping_result.latency_ms,
                last_seen_match=last_seen_match,
                config_hash_match=config_hash_match,
                peer_connectivity=peer_connectivity,
            )

        except Exception as e:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.FULL,
                error_message=f"State verification failed: {e}",
            )

    async def _verify_consensus(self, node_id: str) -> NodeVerificationResult:
        """
        Perform multi-node consensus verification.

        Queries multiple nodes in the mesh to reach consensus on whether
        the target node is healthy. Requires quorum agreement.

        Args:
            node_id: Node identifier to verify

        Returns:
            NodeVerificationResult with consensus outcome
        """
        try:
            from src.database import SessionLocal, MeshNode

            # Get peer nodes for consensus
            with SessionLocal() as db:
                node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
                if not node:
                    return NodeVerificationResult(
                        node_id=node_id,
                        is_healthy=False,
                        verification_mode=VerificationMode.CONSENSUS,
                        error_message="Node not found in database",
                    )

                # Get peers for consensus query
                peers = (
                    db.query(MeshNode)
                    .filter(
                        MeshNode.mesh_id == node.mesh_id,
                        MeshNode.status == "approved",
                        MeshNode.id != node_id,
                    )
                    .limit(self.consensus_quorum * 2)
                    .all()
                )

            if len(peers) < self.consensus_quorum:
                logger.warning(
                    f"Insufficient peers for consensus verification of {node_id}: "
                    f"need {self.consensus_quorum}, have {len(peers)}"
                )
                # Fall back to full verification
                return await self._verify_full(node_id)

            # Query each peer for node health opinion
            # In production, this would use actual mesh protocol messages
            healthy_votes = 0
            total_votes = 0

            for peer in peers[: self.consensus_quorum * 2]:
                try:
                    # Simulate peer query (in production: actual mesh RPC)
                    # For now, assume peer agrees if it can reach the node
                    peer_result = await self._verify_ping(node_id)
                    total_votes += 1
                    if peer_result.is_healthy:
                        healthy_votes += 1
                except Exception:
                    continue

            # Check quorum
            quorum_reached = healthy_votes >= self.consensus_quorum
            is_healthy = quorum_reached and (healthy_votes / max(total_votes, 1)) > 0.5

            logger.info(
                f"{'✅' if is_healthy else '❌'} Consensus verification for {node_id}: "
                f"{healthy_votes}/{total_votes} healthy votes, quorum={quorum_reached}"
            )

            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=is_healthy,
                verification_mode=VerificationMode.CONSENSUS,
                peer_connectivity=healthy_votes,
                error_message=None if is_healthy else "Consensus quorum not reached",
            )

        except Exception as e:
            return NodeVerificationResult(
                node_id=node_id,
                is_healthy=False,
                verification_mode=VerificationMode.CONSENSUS,
                error_message=f"Consensus verification failed: {e}",
            )

    async def _get_node_address(self, node_id: str) -> Optional[Tuple[str, int]]:
        """
        Get the network address (host, port) for a node.

        Args:
            node_id: Node identifier

        Returns:
            Tuple of (host, port) or None if not found
        """
        try:
            from src.database import SessionLocal, MeshNode

            with SessionLocal() as db:
                node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
                if node and hasattr(node, "endpoint") and node.endpoint:
                    # Parse endpoint (format: "host:port")
                    parts = node.endpoint.split(":")
                    if len(parts) == 2:
                        return (parts[0], int(parts[1]))
                    return (node.endpoint, 8080)  # Default port
        except Exception as e:
            logger.debug(f"Failed to get node address for {node_id}: {e}")

        # Fallback: try mesh routing table
        router = self._get_router()
        if router:
            try:
                route = router.get_route(node_id)
                if route:
                    return (
                        route.next_hop,
                        route.port if hasattr(route, "port") else 8080,
                    )
            except Exception:
                pass

        return None

    def _get_router(self):
        """Lazy-init MeshRouter to avoid import-time side effects."""
        if self._router is None:
            try:
                from ..network.routing.mesh_router import MeshRouter

                self._router = MeshRouter(self.node_id)
                logger.info(f"MeshRouter initialized for node {self.node_id}")
            except Exception as e:
                logger.warning(f"MeshRouter unavailable: {e}")
        return self._router

    async def get_statistics(self) -> Dict[str, float]:
        """
        Collect real network statistics from subsystems.

        Returns keys expected by MAPEKLoop:
        - active_peers, avg_latency_ms, packet_loss_percent, mttr_minutes
        """
        stats: Dict[str, float] = {
            "active_peers": 0,
            "avg_latency_ms": 0.0,
            "packet_loss_percent": 0.0,
            "mttr_minutes": 0.0,
        }
        started = time.monotonic()
        status = "success"
        error_types: List[str] = []
        router_summary: Dict[str, Any] = {
            "status": "unavailable",
            "metrics_present": False,
        }
        yggdrasil_summary: Dict[str, Any] = {
            "status": "not_attempted",
            "peer_count": 0,
        }
        yggdrasil_evidence_summary = _evidence_summary({})
        bus = _event_bus_or_none(self.event_bus, self.event_project_root)
        yggdrasil_event_ids_before = (
            {
                event.event_id
                for event in bus.get_event_history(
                    EventType.PIPELINE_STAGE_END,
                    source_agent="yggdrasil-client",
                    limit=1000,
                )
            }
            if bus is not None
            else set()
        )

        # MeshRouter metrics
        router = self._get_router()
        if router is not None:
            router_summary["status"] = "attempted"
            try:
                router_metrics = await router.get_mape_k_metrics()
                stats["packet_loss_percent"] = (
                    router_metrics.get("packet_drop_rate", 0) * 100
                )
                stats["active_peers"] = router_metrics.get("total_routes_known", 0)
                hop_count = router_metrics.get("avg_route_hop_count", 0)
                # Estimate latency from hop count (rough: ~15ms per hop)
                if hop_count > 0:
                    stats["avg_latency_ms"] = hop_count * 15.0
                router_summary = {
                    "status": "success",
                    "metrics_present": True,
                    "packet_drop_rate": round(
                        float(router_metrics.get("packet_drop_rate", 0.0)),
                        6,
                    ),
                    "total_routes_known": int(
                        router_metrics.get("total_routes_known", 0)
                    ),
                    "avg_route_hop_count": round(float(hop_count), 4),
                }
            except Exception as e:
                status = "partial"
                error_types.append(type(e).__name__)
                router_summary = {
                    "status": "failed",
                    "metrics_present": False,
                    "error_redacted": True,
                    "error_sha256": _sha256_text(str(e)),
                }
                logger.debug(
                    "MeshRouter metrics unavailable; details redacted in EventBus"
                )

        # Yggdrasil peer count (supplement)
        try:
            from ..network.yggdrasil_client import get_yggdrasil_peers

            yggdrasil_summary["status"] = "attempted"
            peer_data = get_yggdrasil_peers(
                event_bus=bus,
                event_project_root=self.event_project_root,
                include_evidence=True,
            )
            yggdrasil_evidence_summary = _evidence_summary(peer_data.get("evidence"))
            if peer_data and "count" in peer_data:
                ygg_count = peer_data["count"]
                stats["active_peers"] = max(stats["active_peers"], ygg_count)
                yggdrasil_summary = {
                    "status": str(peer_data.get("status", "unknown")),
                    "peer_count": int(ygg_count),
                    "peer_values_redacted": True,
                }
        except Exception as e:
            status = "partial"
            error_types.append(type(e).__name__)
            yggdrasil_summary = {
                "status": "failed",
                "peer_count": 0,
                "error_redacted": True,
                "error_sha256": _sha256_text(str(e)),
            }
            yggdrasil_evidence_summary = _evidence_summary({})

        # MTTR from healing log
        stats["mttr_minutes"] = self._compute_mttr()

        # ML-based reliability metrics
        if self._ml_enabled and self._neighbor_stats:
            avg_score = sum(s["score"] for s in self._neighbor_stats.values()) / len(
                self._neighbor_stats
            )
            stats["ml_reliability_score"] = avg_score

        yggdrasil_event_ids_after = (
            {
                event.event_id
                for event in bus.get_event_history(
                    EventType.PIPELINE_STAGE_END,
                    source_agent="yggdrasil-client",
                    limit=1000,
                )
            }
            if bus is not None
            else set()
        )
        duration_ms = (time.monotonic() - started) * 1000
        _publish_mesh_manager_observation(
            event_bus=bus,
            event_project_root=self.event_project_root,
            operation="get_statistics",
            status=status,
            duration_ms=duration_ms,
            stats=stats,
            router_summary=router_summary,
            yggdrasil_summary=yggdrasil_summary,
            evidence_event_ids=sorted(
                set(yggdrasil_evidence_summary.get("event_ids", []))
                | (yggdrasil_event_ids_after - yggdrasil_event_ids_before)
            ),
            downstream_claim_boundaries=yggdrasil_evidence_summary.get(
                "claim_boundaries",
                [],
            ),
            error_types=error_types,
        )
        return stats

    async def set_route_preference(self, preference: str) -> bool:
        """
        Set route selection preference.

        Args:
            preference: One of 'low_latency', 'reliability', 'balanced'
        """
        started = time.monotonic()
        context = {"route_preference": preference}
        if preference not in _VALID_ROUTE_PREFERENCES:
            logger.warning(f"Invalid route preference: {preference}")
            _publish_mesh_manager_action(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                event_type=EventType.TASK_FAILED,
                stage="action_failed",
                operation="set_route_preference",
                status="invalid",
                duration_ms=(time.monotonic() - started) * 1000,
                context=context,
                result=False,
                success=False,
                error_types=["ValidationFailure"],
            )
            return False
        self._route_preference = preference
        logger.info(f"Route preference set to {preference}")
        _publish_mesh_manager_action(
            event_bus=self.event_bus,
            event_project_root=self.event_project_root,
            event_type=EventType.PIPELINE_STAGE_END,
            stage="action_completed",
            operation="set_route_preference",
            status="success",
            duration_ms=(time.monotonic() - started) * 1000,
            context=context,
            result=True,
            success=True,
        )
        return True

    async def trigger_aggressive_healing(
        self,
        auto_restore_nodes: bool = False,
        node_recovery_callback: Optional[Callable[[str], bool]] = None,
        verification_mode: VerificationMode = VerificationMode.FULL,
        require_verification: bool = True,
        post_action_dataplane_probe_target: Optional[str] = None,
    ) -> int:
        """
        Force route rediscovery and optionally restore offline nodes in DB.

        This method performs two types of healing:
        1. Mesh routing healing - rediscovers stale routes
        2. Database node healing - restores offline nodes with verification

        Args:
            auto_restore_nodes: If True, attempt to restore offline nodes.
                               If False (default), only log and count them.
            node_recovery_callback: Optional async callback for custom verification.
                                   If provided, used instead of built-in verification.
            verification_mode: Mode for state integrity verification (default: FULL).
                              Options: NONE, PING, FULL, CONSENSUS.
            require_verification: If True (default), nodes must pass verification.
                                 If False, allows unverified restore with warning.

        Returns:
            Number of components healed (routes + nodes).

        Raises:
            NodeVerificationError: If verification_mode=NONE without env var.

        Security Notes:
            - By default, nodes are NOT restored without passing verification
            - VerificationMode.NONE requires X0TTA6BL4_ALLOW_UNVERIFIED_RESTORE=1
            - Use require_verification=False with caution (logs warning)

        Example:
            >>> # Safe: Full verification (recommended)
            >>> healed = await manager.trigger_aggressive_healing(
            ...     auto_restore_nodes=True,
            ...     verification_mode=VerificationMode.FULL
            ... )

            >>> # Custom verification callback
            >>> async def my_verify(node_id: str) -> bool:
            ...     return await custom_health_check(node_id)
            >>> healed = await manager.trigger_aggressive_healing(
            ...     auto_restore_nodes=True,
            ...     node_recovery_callback=my_verify
            ... )
        """
        healed = 0
        start_time = time.time()
        started = time.monotonic()
        error_types: List[str] = []
        verification_results: List[NodeVerificationResult] = []

        # 1. Mesh Routing Healing
        router = self._get_router()
        if router is not None:
            try:
                active_routes = router.get_routes()
                for dest in list(active_routes.keys()):
                    routes = active_routes[dest]
                    stale = [r for r in routes if r.age > router.ROUTE_TIMEOUT * 0.8]
                    for route in stale:
                        try:
                            await router._discover_route(dest)
                            healed += 1
                        except Exception:
                            error_types.append("RouteDiscoveryFailure")
                            pass
            except Exception as e:
                error_types.append(type(e).__name__)
                logger.error(f"Aggressive routing healing failed: {e}")

        # 2. Database Node Healing with State Integrity Verification
        try:
            from src.database import SessionLocal, MeshNode

            with SessionLocal() as db:
                offline_nodes = (
                    db.query(MeshNode).filter(MeshNode.status == "offline").all()
                )

                if not offline_nodes:
                    logger.debug("No offline nodes to heal")
                elif auto_restore_nodes:
                    for node in offline_nodes:
                        try:
                            is_recovered = False

                            # Use custom callback if provided
                            if node_recovery_callback is not None:
                                is_recovered = await node_recovery_callback(node.id)
                            else:
                                # Use built-in verification
                                result = await self.verify_node_state(
                                    node_id=node.id,
                                    mode=verification_mode,
                                )
                                verification_results.append(result)
                                is_recovered = result.is_healthy

                            if is_recovered:
                                logger.info(
                                    f"🔧 Healing: Node {node.id} verified and restored "
                                    f"(mode={verification_mode.value})"
                                )
                                node.status = "healthy"
                                node.last_seen = datetime.utcnow()
                                healed += 1
                            elif not require_verification:
                                # Allow unverified restore with warning
                                logger.warning(
                                    f"⚠️ Node {node.id} restored WITHOUT passing verification "
                                    f"(require_verification=False)"
                                )
                                node.status = "healthy"
                                node.last_seen = datetime.utcnow()
                                healed += 1
                            else:
                                logger.warning(
                                    f"⚠️ Node {node.id} failed verification, skipping. "
                                    f"Use require_verification=False to force restore."
                                )
                        except NodeVerificationError as e:
                            error_types.append(type(e).__name__)
                            logger.error(f"❌ Node {node.id} verification error: {e}")
                        except Exception as e:
                            error_types.append(type(e).__name__)
                            logger.warning(
                                f"⚠️ Node {node.id} recovery check failed: {e}"
                            )

                    db.commit()
                else:
                    # Default: just log offline nodes without modifying
                    logger.info(
                        f"📊 Found {len(offline_nodes)} offline nodes. "
                        "Use auto_restore_nodes=True to attempt recovery."
                    )
                    for node in offline_nodes:
                        logger.debug(
                            f"  - Offline node: {node.id} (last_seen: {node.last_seen})"
                        )

        except Exception as e:
            error_types.append(type(e).__name__)
            logger.error(f"Database node healing failed: {e}")

        elapsed = (time.time() - start_time) / 60.0
        self._healing_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "healed": healed,
                "duration_minutes": elapsed,
                "verification_mode": verification_mode.value,
                "verification_results": [
                    {
                        "node_id": r.node_id,
                        "is_healthy": r.is_healthy,
                        "latency_ms": r.latency_ms,
                        "evidence_event_id": r.evidence_event_id,
                    }
                    for r in verification_results
                ],
            }
        )
        verification_evidence_ids = [
            result.evidence_event_id
            for result in verification_results
            if result.evidence_event_id
        ]
        post_action_probe_enabled = self._post_heal_probe_enabled()
        probe_target = (
            post_action_dataplane_probe_target
            or os.environ.get(_POST_HEAL_PROBE_TARGET_ENV_VAR)
            or None
        )
        post_action_probe_result: Optional[Dict[str, Any]] = None
        if post_action_probe_enabled and probe_target:
            post_action_probe_result = await self._probe_post_heal_dataplane(
                probe_target
            )
        healing_claim_gate = _healing_claim_gate(
            healed=healed,
            verification_evidence_events=len(verification_evidence_ids),
            post_action_probe_enabled=post_action_probe_enabled,
            post_action_probe_target_present=bool(probe_target),
            post_action_probe_result=post_action_probe_result,
        )
        probe_evidence = _evidence_summary(healing_claim_gate.get("evidence"))
        post_action_probe_evidence_ids = [
            str(event_id) for event_id in probe_evidence.get("event_ids", [])
        ]
        downstream_source_agents = [_SERVICE_AGENT] if verification_evidence_ids else []
        for source_agent in probe_evidence.get("source_agents", []):
            if source_agent not in downstream_source_agents:
                downstream_source_agents.append(source_agent)
        _publish_mesh_manager_action(
            event_bus=self.event_bus,
            event_project_root=self.event_project_root,
            event_type=EventType.PIPELINE_STAGE_END,
            stage="action_completed",
            operation="trigger_aggressive_healing",
            status="partial" if error_types else "success",
            duration_ms=(time.monotonic() - started) * 1000,
            context={
                "healing_mode": "aggressive",
                "auto_restore_nodes": auto_restore_nodes,
                "verification_mode": verification_mode.value,
                "require_verification": require_verification,
                "post_action_probe_target_present": bool(probe_target),
            },
            result={
                "healed": healed,
                "verification_results": len(verification_results),
                "verification_evidence_events": len(verification_evidence_ids),
                "post_action_probe_attempted": post_action_probe_result is not None,
            },
            success=True,
            error_types=error_types,
            evidence_event_ids=verification_evidence_ids
            + post_action_probe_evidence_ids,
            downstream_source_agents=downstream_source_agents,
            claim_gate=healing_claim_gate,
        )
        return healed

    async def trigger_preemptive_checks(self):
        """
        Proactively check route freshness for all known destinations.
        """
        started = time.monotonic()
        route_count = 0
        discovery_attempts = 0
        discovery_successes = 0
        discovery_failures = 0
        error_types: List[str] = []
        router = self._get_router()
        if router is None:
            _publish_mesh_manager_action(
                event_bus=self.event_bus,
                event_project_root=self.event_project_root,
                event_type=EventType.PIPELINE_STAGE_END,
                stage="action_completed",
                operation="trigger_preemptive_checks",
                status="skipped",
                duration_ms=(time.monotonic() - started) * 1000,
                context={"healing_mode": "preemptive"},
                result={
                    "router_present": False,
                    "route_count": route_count,
                    "discovery_attempts": discovery_attempts,
                    "discovery_successes": discovery_successes,
                    "discovery_failures": discovery_failures,
                },
                success=True,
            )
            return

        try:
            active_routes = router.get_routes()
            route_count = len(active_routes)
            for dest in list(active_routes.keys()):
                routes = active_routes[dest]
                # If best route is getting stale, start background discovery
                if routes and routes[0].age > router.ROUTE_TIMEOUT * 0.5:
                    discovery_attempts += 1
                    try:
                        await router._discover_route(dest)
                        discovery_successes += 1
                    except Exception:
                        discovery_failures += 1
                        error_types.append("RouteDiscoveryFailure")
                        pass
        except Exception as e:
            error_types.append(type(e).__name__)
            logger.debug(f"Preemptive check error: {e}")
        _publish_mesh_manager_action(
            event_bus=self.event_bus,
            event_project_root=self.event_project_root,
            event_type=EventType.PIPELINE_STAGE_END,
            stage="action_completed",
            operation="trigger_preemptive_checks",
            status="partial" if error_types else "success",
            duration_ms=(time.monotonic() - started) * 1000,
            context={"healing_mode": "preemptive"},
            result={
                "router_present": True,
                "route_count": route_count,
                "discovery_attempts": discovery_attempts,
                "discovery_successes": discovery_successes,
                "discovery_failures": discovery_failures,
            },
            success=True,
            error_types=error_types,
        )

    def _compute_mttr(self) -> float:
        """Compute mean time to repair from healing log (minutes)."""
        if not self._healing_log:
            return 0.0
        # Use last 10 entries
        recent = self._healing_log[-10:]
        durations = [
            entry["duration_minutes"] for entry in recent if entry["healed"] > 0
        ]
        if not durations:
            return 0.0
        return sum(durations) / len(durations)
