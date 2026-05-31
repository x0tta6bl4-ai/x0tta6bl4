"""Redacted EventBus evidence for mesh optimization enforcement decisions."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from collections import Counter
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.mesh.metric_evidence_policy import (
    mesh_metric_policy_allows_high_risk,
    safe_mesh_metric_evidence_policy,
)
from src.mesh.yggdrasil_optimizer import get_optimizer
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "mesh-action-enforcer"
_SERVICE_LAYER = "mesh_action_enforcer_control_action"
_RESOURCE = "mesh:action_enforcer:recommendations"
_KNOWN_ACTIONS = {"refresh", "investigate"}
_ROUTE_HASH_LIMIT = 20
_COMMAND_METADATA_LIMIT = 20
_CLAIM_BOUNDARY_LIMIT = 8
_CLAIM_BOUNDARY_TEXT_LIMIT = 400
_APPLY_ENV_VAR = "X0TTA6BL4_MESH_ACTION_ENFORCER_APPLY"
_POST_ACTION_PROBE_ENV_VAR = "X0TTA6BL4_MESH_ACTION_ENFORCER_POST_ACTION_PROBE"
_COMMAND_TIMEOUT_SECONDS = 5

MESH_ACTION_ENFORCER_CLAIM_BOUNDARY = (
    "Local mesh optimization enforcement evidence only. It records the redacted "
    "recommendation summary, service identity presence, duration, fail-closed "
    "restart gates, mesh metric evidence-policy decisions, and bounded yggdrasilctl "
    "command metadata when live apply is explicitly enabled. It also records whether "
    "post-action dataplane revalidation was attempted or explicitly skipped. It does "
    "not expose raw route IDs, peer addresses, route tables, or prove remote peer "
    "quality."
)
POST_ACTION_DATAPLANE_REVALIDATION_CLAIM_BOUNDARY = (
    "Post-action dataplane revalidation metadata only. A local restart/refresh "
    "result is not treated as dataplane proof unless a bounded dataplane probe is "
    "attempted and recorded separately."
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
        return get_event_bus(event_project_root)
    except Exception as exc:
        logger.error("Failed to initialize mesh-action-enforcer EventBus: %s", exc)
        return None


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _find_yggdrasilctl() -> Optional[str]:
    locations = [
        "yggdrasilctl",
        "/usr/local/bin/yggdrasilctl",
        "/usr/bin/yggdrasilctl",
        "/usr/sbin/yggdrasilctl",
        "/sbin/yggdrasilctl",
    ]
    for location in locations:
        if shutil.which(location) or os.path.exists(location):
            return location
    return None


def _bounded_output_metadata(
    stdout: Optional[str],
    stderr: Optional[str],
) -> Dict[str, Any]:
    safe_stdout = str(stdout or "")
    safe_stderr = str(stderr or "")
    return {
        "stdout_chars": len(safe_stdout),
        "stderr_chars": len(safe_stderr),
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "output_redacted": True,
    }


def _safe_action(value: Any) -> str:
    action = str(value or "")
    return action if action in _KNOWN_ACTIONS else "unknown"


def _safe_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_claim_boundary(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return text[:_CLAIM_BOUNDARY_TEXT_LIMIT]


def _claim_boundary_summary(evidence: Any) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        return {
            "claim_boundaries": [],
            "claim_boundaries_total": 0,
            "claim_boundaries_truncated": False,
        }
    boundaries: List[str] = []
    direct_boundary = _safe_claim_boundary(evidence.get("claim_boundary"))
    if direct_boundary:
        boundaries.append(direct_boundary)
    if isinstance(evidence.get("claim_boundaries"), list):
        for item in evidence["claim_boundaries"]:
            boundary = _safe_claim_boundary(item)
            if boundary:
                boundaries.append(boundary)
    distinct = sorted(set(boundaries))
    return {
        "claim_boundaries": distinct[:_CLAIM_BOUNDARY_LIMIT],
        "claim_boundaries_total": len(distinct),
        "claim_boundaries_truncated": len(distinct) > _CLAIM_BOUNDARY_LIMIT,
    }


def _peer_probe_target(*, route_id: str, peer_uri: str) -> Optional[str]:
    for value in (peer_uri, route_id.removeprefix("direct-")):
        text = str(value or "").strip()
        if not text:
            continue
        parsed = urlparse(text)
        target = parsed.hostname or text
        if parsed.hostname is None and target.count(":") == 1:
            target = target.rsplit(":", 1)[0]
        if re.fullmatch(r"[A-Za-z0-9_.:%-]{1,255}", target):
            return target
    return None


def _run_awaitable_sync(awaitable: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    holder: Dict[str, Any] = {}

    def _runner() -> None:
        try:
            holder["value"] = asyncio.run(awaitable)
        except Exception as exc:  # pragma: no cover - exercised through caller path
            holder["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in holder:
        raise holder["error"]
    return holder.get("value")


def _evidence_summary(evidence: Any) -> Dict[str, Any]:
    if not isinstance(evidence, dict):
        return {
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "event_ids_count": 0,
            **_claim_boundary_summary({}),
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
    return {
        "source_agents": source_agents,
        "event_ids": event_ids,
        "events_total": int(evidence.get("events_total", len(event_ids)) or 0),
        "event_ids_count": len(event_ids),
        **_claim_boundary_summary(evidence),
        "redacted": True,
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
    evidence_value = (
        dict(value.get("evidence"))
        if isinstance(value.get("evidence"), dict)
        else {}
    )
    claim_boundary = str(value.get("claim_boundary") or "")
    if claim_boundary and "claim_boundary" not in evidence_value:
        evidence_value["claim_boundary"] = claim_boundary
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
        "evidence": _evidence_summary(evidence_value),
        "claim_boundary": claim_boundary,
        "redacted": True,
    }


def _recommendation_summary(recommendations: List[Any]) -> Dict[str, Any]:
    action_counts = Counter()
    route_id_hashes: List[str] = []
    peer_uri_hashes: List[str] = []
    for recommendation in recommendations:
        if not isinstance(recommendation, dict):
            action_counts["invalid"] += 1
            continue
        action_counts[_safe_action(recommendation.get("action"))] += 1
        route_id_hash = _sha256_text(str(recommendation.get("route_id", "")))
        if route_id_hash:
            route_id_hashes.append(route_id_hash)
        peer_uri_hash = _sha256_text(str(recommendation.get("peer_uri", "")))
        if peer_uri_hash:
            peer_uri_hashes.append(peer_uri_hash)

    return {
        "recommendation_count": len(recommendations),
        "action_counts": dict(sorted(action_counts.items())),
        "route_id_hashes": route_id_hashes[-_ROUTE_HASH_LIMIT:],
        "route_id_hashes_total": len(route_id_hashes),
        "route_id_hashes_limit": _ROUTE_HASH_LIMIT,
        "route_id_hashes_truncated": len(route_id_hashes) > _ROUTE_HASH_LIMIT,
        "peer_uri_hashes": peer_uri_hashes[-_ROUTE_HASH_LIMIT:],
        "peer_uri_hashes_total": len(peer_uri_hashes),
        "peer_uri_hashes_limit": _ROUTE_HASH_LIMIT,
        "peer_uri_hashes_truncated": len(peer_uri_hashes) > _ROUTE_HASH_LIMIT,
        "values_redacted": True,
    }


def _result_summary(
    *,
    refresh_requests: int,
    investigate_requests: int,
    unknown_actions: int,
    invalid_recommendations: int,
    metric_evidence_policy: Optional[Dict[str, Any]] = None,
    blocked_refresh_requests: int = 0,
    blocked_by_metric_evidence_policy: bool = False,
    restart_outcomes: Optional[Counter] = None,
    restart_peer_supported: bool = False,
    yggdrasil_reconfiguration_applied: bool = False,
    command_attempts: int = 0,
    command_successes: int = 0,
    command_metadata: Optional[List[Dict[str, Any]]] = None,
    post_action_probe_enabled: bool = False,
    post_action_probe_target_present: bool = False,
    post_action_probe_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe_command_metadata = list(command_metadata or [])
    post_action_revalidation = _post_action_dataplane_revalidation_summary(
        refresh_requests=refresh_requests,
        blocked_by_metric_evidence_policy=blocked_by_metric_evidence_policy,
        yggdrasil_reconfiguration_applied=yggdrasil_reconfiguration_applied,
        command_attempts=command_attempts,
        post_action_probe_enabled=post_action_probe_enabled,
        post_action_probe_target_present=post_action_probe_target_present,
        post_action_probe_result=post_action_probe_result,
    )
    return {
        "refresh_requests": refresh_requests,
        "investigate_requests": investigate_requests,
        "unknown_actions": unknown_actions,
        "invalid_recommendations": invalid_recommendations,
        "blocked_refresh_requests": blocked_refresh_requests,
        "blocked_by_metric_evidence_policy": blocked_by_metric_evidence_policy,
        "metric_evidence_policy": safe_mesh_metric_evidence_policy(
            metric_evidence_policy
        ),
        "restart_peer_supported": restart_peer_supported,
        "restart_outcomes": dict(sorted((restart_outcomes or Counter()).items())),
        "command_attempts": command_attempts,
        "command_successes": command_successes,
        "command_metadata": safe_command_metadata[-_COMMAND_METADATA_LIMIT:],
        "command_metadata_total": len(safe_command_metadata),
        "command_metadata_limit": _COMMAND_METADATA_LIMIT,
        "command_metadata_truncated": (
            len(safe_command_metadata) > _COMMAND_METADATA_LIMIT
        ),
        "safe_actuator": True,
        "apply_env_var": _APPLY_ENV_VAR,
        "yggdrasil_reconfiguration_applied": yggdrasil_reconfiguration_applied,
        "post_action_dataplane_revalidation": post_action_revalidation,
        "values_redacted": True,
    }


def _post_action_dataplane_revalidation_summary(
    *,
    refresh_requests: int,
    blocked_by_metric_evidence_policy: bool,
    yggdrasil_reconfiguration_applied: bool,
    command_attempts: int,
    post_action_probe_enabled: bool = False,
    post_action_probe_target_present: bool = False,
    post_action_probe_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    probe_result = _probe_result_summary(post_action_probe_result)
    probe_attempted = post_action_probe_result is not None
    dataplane_confirmed = bool(
        probe_attempted and probe_result["dataplane_confirmed"]
    )
    evidence = (
        probe_result["evidence"] if probe_attempted else _evidence_summary({})
    )
    claim_gate = _post_action_dataplane_claim_gate(
        probe_attempted=probe_attempted,
        dataplane_confirmed=dataplane_confirmed,
        evidence=evidence,
    )
    if refresh_requests <= 0:
        status = "not_required"
        reason = "no_refresh_requested"
    elif blocked_by_metric_evidence_policy:
        status = "not_attempted"
        reason = "action_blocked_by_metric_evidence_policy"
    elif not yggdrasil_reconfiguration_applied:
        status = "not_attempted"
        reason = "restart_not_applied"
    elif not post_action_probe_enabled:
        status = "not_attempted"
        reason = "no_post_action_dataplane_probe_configured"
    elif not post_action_probe_target_present:
        status = "not_attempted"
        reason = "no_post_action_dataplane_probe_target"
    elif dataplane_confirmed:
        status = "success"
        reason = "bounded_dataplane_probe_succeeded"
    else:
        status = "failed"
        reason = "bounded_dataplane_probe_failed"

    return {
        "status": status,
        "reason": reason,
        "probe_enabled": post_action_probe_enabled,
        "probe_target_present": post_action_probe_target_present,
        "probe_attempted": probe_attempted,
        "post_action_dataplane_revalidated": dataplane_confirmed,
        "dataplane_confirmed": dataplane_confirmed,
        "required_for_restored_dataplane_claim": True,
        "restored_dataplane_claim_allowed": claim_gate[
            "restored_dataplane_claim_allowed"
        ],
        "claim_gate": claim_gate,
        "probe_result": probe_result if probe_attempted else None,
        "evidence": evidence,
        "refresh_requests": refresh_requests,
        "command_attempts": command_attempts,
        "control_action_applied": bool(yggdrasil_reconfiguration_applied),
        "claim_boundary": POST_ACTION_DATAPLANE_REVALIDATION_CLAIM_BOUNDARY,
        "redacted": True,
    }


def _post_action_dataplane_claim_gate(
    *,
    probe_attempted: bool,
    dataplane_confirmed: bool,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    blockers: List[str] = []
    events_total = int(evidence.get("events_total", 0) or 0)
    event_ids_count = int(evidence.get("event_ids_count", 0) or 0)
    source_agents = evidence.get("source_agents", [])
    if not probe_attempted:
        blockers.append("no_bounded_post_action_dataplane_probe_attached")
    elif not dataplane_confirmed:
        blockers.append("bounded_dataplane_probe_not_confirmed")
    if probe_attempted and (events_total <= 0 or event_ids_count <= 0):
        blockers.append("post_action_probe_evidence_missing")
    if probe_attempted and not source_agents:
        blockers.append("post_action_probe_source_agent_missing")
    if evidence.get("redacted") is not True:
        blockers.append("post_action_probe_evidence_not_redacted")

    return {
        "required_for_restored_dataplane_claim": True,
        "restored_dataplane_claim_allowed": not blockers,
        "blockers": blockers,
        "required_evidence": {
            "probe_attempted": True,
            "dataplane_confirmed": True,
            "redacted_evidence": True,
            "event_ids_count_min": 1,
            "events_total_min": 1,
            "source_agents_min": 1,
        },
        "observed_evidence": {
            "probe_attempted": probe_attempted,
            "dataplane_confirmed": dataplane_confirmed,
            "redacted_evidence": evidence.get("redacted") is True,
            "event_ids_count": event_ids_count,
            "events_total": events_total,
            "source_agents_count": len(source_agents)
            if isinstance(source_agents, list)
            else 0,
        },
        "claim_boundary": POST_ACTION_DATAPLANE_REVALIDATION_CLAIM_BOUNDARY,
        "redacted": True,
    }


class MeshActionEnforcer:
    """Enforces optimizer recommendations against the local mesh data plane."""

    def __init__(
        self,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        enable_post_action_dataplane_probe: Optional[bool] = None,
        post_action_dataplane_probe_provider: Optional[Any] = None,
    ):
        self.optimizer = get_optimizer()
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self._post_action_probe_config_source = (
            "env" if enable_post_action_dataplane_probe is None else "constructor"
        )
        self.enable_post_action_dataplane_probe = (
            _env_bool(_POST_ACTION_PROBE_ENV_VAR, False)
            if enable_post_action_dataplane_probe is None
            else bool(enable_post_action_dataplane_probe)
        )
        self.post_action_dataplane_probe_provider = (
            post_action_dataplane_probe_provider
        )

    def _post_action_probe_enabled(self) -> bool:
        if self._post_action_probe_config_source == "env":
            return _env_bool(_POST_ACTION_PROBE_ENV_VAR, False)
        return bool(self.enable_post_action_dataplane_probe)

    def _publish_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        status: str,
        duration_ms: float,
        recommendations: List[Any],
        result: Dict[str, Any],
        success: bool,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = _event_bus_or_none(self.event_bus, self.event_project_root)
        if bus is None:
            return None
        post_action_revalidation = (
            result.get("post_action_dataplane_revalidation")
            if isinstance(result.get("post_action_dataplane_revalidation"), dict)
            else {}
        )
        downstream_evidence = (
            post_action_revalidation.get("evidence")
            if isinstance(post_action_revalidation.get("evidence"), dict)
            else {}
        )

        payload: Dict[str, Any] = {
            "component": "mesh.action_enforcer",
            "stage": stage,
            "operation": "enforce_recommendations",
            "resource": _RESOURCE,
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "read_only": False,
            "observed_state": False,
            "control_action": True,
            "safe_actuator": bool(result.get("safe_actuator", False)),
            "post_action_dataplane_revalidated": bool(
                post_action_revalidation.get("post_action_dataplane_revalidated")
            ),
            "dataplane_confirmed": bool(
                post_action_revalidation.get("dataplane_confirmed")
            ),
            "restored_dataplane_claim_allowed": bool(
                post_action_revalidation.get("restored_dataplane_claim_allowed")
            ),
            "recommendations": _recommendation_summary(recommendations),
            "result": result,
            "success": success,
            "downstream_evidence": {
                "source_agents": downstream_evidence.get("source_agents", []),
                "event_ids": downstream_evidence.get("event_ids", []),
                "events_total": downstream_evidence.get("events_total", 0),
                "claim_boundaries": downstream_evidence.get("claim_boundaries", []),
                "claim_boundaries_total": downstream_evidence.get(
                    "claim_boundaries_total",
                    0,
                ),
                "claim_boundaries_truncated": downstream_evidence.get(
                    "claim_boundaries_truncated",
                    False,
                ),
                "redacted": True,
            },
            "input_redacted": True,
            "claim_boundary": MESH_ACTION_ENFORCER_CLAIM_BOUNDARY,
        }
        if error_type:
            payload["error"] = {"type": error_type, "message_redacted": True}

        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=6)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish mesh-action-enforcer event: %s", exc)
            return None

    def enforce_recommendations(
        self,
        recommendations: list,
        *,
        metric_evidence_policy: Optional[Dict[str, Any]] = None,
    ):
        """Execute local routing actions based on optimizer recommendations."""
        started = time.monotonic()
        recommendation_list = list(recommendations or [])
        policy_allows_refresh = mesh_metric_policy_allows_high_risk(
            metric_evidence_policy,
            require_present=True,
        )
        self._publish_event(
            EventType.COORDINATION_REQUEST,
            stage="action_requested",
            status="requested",
            duration_ms=0.0,
            recommendations=recommendation_list,
            result=_result_summary(
                refresh_requests=0,
                investigate_requests=0,
                unknown_actions=0,
                invalid_recommendations=0,
                metric_evidence_policy=metric_evidence_policy,
            ),
            success=False,
        )

        refresh_requests = 0
        investigate_requests = 0
        unknown_actions = 0
        invalid_recommendations = 0
        restart_peer_supported = False
        yggdrasil_reconfiguration_applied = False
        command_attempts = 0
        command_successes = 0
        command_metadata: List[Dict[str, Any]] = []
        restart_outcomes: Counter = Counter()
        post_action_probe_target: Optional[str] = None
        post_action_probe_result: Optional[Dict[str, Any]] = None

        try:
            for recommendation in recommendation_list:
                if not isinstance(recommendation, dict):
                    invalid_recommendations += 1
                    continue

                action = recommendation.get("action")
                route_id = str(recommendation.get("route_id", ""))
                peer_uri = str(recommendation.get("peer_uri", ""))

                if action == "refresh":
                    refresh_requests += 1
                    if not policy_allows_refresh:
                        restart_outcomes["blocked_by_metric_evidence_policy"] += 1
                        continue
                    logger.info("Enforcer: Refreshing route; route_id redacted")
                    restart_result = self._restart_peer(route_id, peer_uri=peer_uri)
                    reason_code = str(restart_result.get("reason_code", "unknown"))
                    restart_outcomes[reason_code] += 1
                    restart_peer_supported = (
                        restart_peer_supported
                        or bool(restart_result.get("restart_peer_supported"))
                    )
                    yggdrasil_reconfiguration_applied = (
                        yggdrasil_reconfiguration_applied
                        or bool(restart_result.get("applied"))
                    )
                    if (
                        restart_result.get("applied") is True
                        and post_action_probe_target is None
                    ):
                        post_action_probe_target = _peer_probe_target(
                            route_id=route_id,
                            peer_uri=peer_uri,
                        )
                    command_attempts += int(restart_result.get("command_attempts", 0))
                    command_successes += int(
                        restart_result.get("command_successes", 0)
                    )
                    for output in restart_result.get("output", []):
                        if isinstance(output, dict):
                            command_metadata.append(
                                {
                                    "reason_code": reason_code,
                                    "command": str(output.get("command", "")),
                                    "returncode": output.get("returncode"),
                                    "stdout_chars": int(
                                        output.get("stdout_chars", 0) or 0
                                    ),
                                    "stderr_chars": int(
                                        output.get("stderr_chars", 0) or 0
                                    ),
                                    "stdout_sha256": output.get("stdout_sha256"),
                                    "stderr_sha256": output.get("stderr_sha256"),
                                    "output_redacted": True,
                                }
                            )

                elif action == "investigate":
                    investigate_requests += 1
                    logger.warning(
                        "Enforcer: Route quality low; route_id redacted"
                    )

                else:
                    unknown_actions += 1

            post_action_probe_enabled = self._post_action_probe_enabled()
            if (
                yggdrasil_reconfiguration_applied
                and post_action_probe_enabled
                and post_action_probe_target is not None
            ):
                post_action_probe_result = self._probe_post_action_dataplane(
                    post_action_probe_target,
                )

            result = _result_summary(
                refresh_requests=refresh_requests,
                investigate_requests=investigate_requests,
                unknown_actions=unknown_actions,
                invalid_recommendations=invalid_recommendations,
                metric_evidence_policy=metric_evidence_policy,
                blocked_refresh_requests=restart_outcomes.get(
                    "blocked_by_metric_evidence_policy",
                    0,
                ),
                blocked_by_metric_evidence_policy=bool(
                    restart_outcomes.get("blocked_by_metric_evidence_policy", 0)
                ),
                restart_outcomes=restart_outcomes,
                restart_peer_supported=restart_peer_supported,
                yggdrasil_reconfiguration_applied=yggdrasil_reconfiguration_applied,
                command_attempts=command_attempts,
                command_successes=command_successes,
                command_metadata=command_metadata,
                post_action_probe_enabled=post_action_probe_enabled,
                post_action_probe_target_present=post_action_probe_target is not None,
                post_action_probe_result=post_action_probe_result,
            )
            blocked_by_policy = bool(result["blocked_by_metric_evidence_policy"])
            self._publish_event(
                EventType.TASK_BLOCKED
                if blocked_by_policy
                else EventType.PIPELINE_STAGE_END,
                stage="action_blocked" if blocked_by_policy else "action_completed",
                status="blocked" if blocked_by_policy else "success",
                duration_ms=(time.monotonic() - started) * 1000,
                recommendations=recommendation_list,
                result=result,
                success=not blocked_by_policy,
                error_type=(
                    "MeshMetricEvidencePolicyBlocked" if blocked_by_policy else None
                ),
            )
            return {**result, "success": not blocked_by_policy}
        except Exception as exc:
            result = _result_summary(
                refresh_requests=refresh_requests,
                investigate_requests=investigate_requests,
                unknown_actions=unknown_actions,
                invalid_recommendations=invalid_recommendations,
                metric_evidence_policy=metric_evidence_policy,
                blocked_refresh_requests=restart_outcomes.get(
                    "blocked_by_metric_evidence_policy",
                    0,
                ),
                blocked_by_metric_evidence_policy=bool(
                    restart_outcomes.get("blocked_by_metric_evidence_policy", 0)
                ),
                restart_outcomes=restart_outcomes,
                restart_peer_supported=restart_peer_supported,
                yggdrasil_reconfiguration_applied=yggdrasil_reconfiguration_applied,
                command_attempts=command_attempts,
                command_successes=command_successes,
                command_metadata=command_metadata,
                post_action_probe_enabled=self._post_action_probe_enabled(),
                post_action_probe_target_present=post_action_probe_target is not None,
                post_action_probe_result=post_action_probe_result,
            )
            self._publish_event(
                EventType.TASK_FAILED,
                stage="action_failed",
                status="failed",
                duration_ms=(time.monotonic() - started) * 1000,
                recommendations=recommendation_list,
                result=result,
                success=False,
                error_type=type(exc).__name__,
            )
            raise

    def _probe_post_action_dataplane(
        self,
        target: Optional[str],
    ) -> Dict[str, Any]:
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
            provider = self.post_action_dataplane_probe_provider
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
                raw_result = _run_awaitable_sync(raw_result)
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

    def _restart_peer(
        self,
        route_id: str,
        *,
        peer_uri: str = "",
    ) -> Dict[str, Any]:
        route_id = str(route_id or "")
        peer_uri = str(peer_uri or "")
        base: Dict[str, Any] = {
            "route_id_sha256": _sha256_text(route_id),
            "peer_uri_present": bool(peer_uri),
            "peer_uri_sha256": _sha256_text(peer_uri),
            "peer_uri_redacted": True,
            "apply_enabled": _env_bool(_APPLY_ENV_VAR, False),
            "restart_peer_supported": False,
            "applied": False,
            "command_attempts": 0,
            "command_successes": 0,
            "commands": [],
            "returncodes": [],
            "output": [],
            "safe_actuator": True,
            "values_redacted": True,
        }

        if not route_id.startswith("direct-"):
            return {**base, "reason_code": "unsupported_route_id"}

        if not peer_uri:
            return {**base, "reason_code": "missing_peer_uri"}

        if not base["apply_enabled"]:
            return {
                **base,
                "restart_peer_supported": True,
                "reason_code": "apply_disabled",
            }

        yggdrasilctl = _find_yggdrasilctl()
        if not yggdrasilctl:
            return {
                **base,
                "restart_peer_supported": True,
                "reason_code": "missing_yggdrasilctl",
            }

        def _executor(_action: str, _context: Dict[str, Any]) -> SafeActuatorResult:
            commands = [
                [yggdrasilctl, "removePeer", peer_uri],
                [yggdrasilctl, "addPeer", peer_uri],
            ]
            returncodes: List[Optional[int]] = []
            output: List[Dict[str, Any]] = []
            for command in commands:
                try:
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        timeout=_COMMAND_TIMEOUT_SECONDS,
                        check=False,
                    )
                    returncodes.append(result.returncode)
                    output.append(
                        {
                            "command": command[1],
                            "returncode": result.returncode,
                            **_bounded_output_metadata(
                                result.stdout,
                                result.stderr,
                            ),
                        }
                    )
                except Exception as exc:
                    returncodes.append(getattr(exc, "returncode", None))
                    output.append(
                        {
                            "command": command[1],
                            "returncode": getattr(exc, "returncode", None),
                            "error": {
                                "type": type(exc).__name__,
                                "message_redacted": True,
                            },
                            **_bounded_output_metadata(
                                getattr(exc, "stdout", None),
                                getattr(exc, "stderr", None),
                            ),
                        }
                    )
                    break

            context = _context
            context["commands"] = [command[1] for command in commands]
            context["returncodes"] = returncodes
            context["output"] = output
            success = len(returncodes) == len(commands) and all(
                returncode == 0 for returncode in returncodes
            )
            return SafeActuatorResult(
                success,
                "" if success else "yggdrasilctl peer restart failed",
            )

        actuator_context: Dict[str, Any] = {}
        actuator_result = SafeActuator(_executor).execute(
            "restart_yggdrasil_peer",
            actuator_context,
        )
        returncodes = actuator_context.get("returncodes", [])
        commands = actuator_context.get("commands", [])
        output = actuator_context.get("output", [])
        command_successes = sum(1 for returncode in returncodes if returncode == 0)

        return {
            **base,
            "restart_peer_supported": True,
            "applied": bool(actuator_result.success),
            "reason_code": "applied" if actuator_result.success else "command_failed",
            "command_attempts": len(returncodes),
            "command_successes": command_successes,
            "commands": commands,
            "returncodes": returncodes,
            "output": output,
        }


mesh_action_enforcer = MeshActionEnforcer()
