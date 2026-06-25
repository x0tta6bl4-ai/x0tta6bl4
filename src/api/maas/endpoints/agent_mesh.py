"""MaaS Agent Mesh endpoints (local-only health bot)."""

from __future__ import annotations

import hmac
import hashlib
import os
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.agents.maas_health_bot import HealthBotConfig, MaasHealthBot
from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth import get_current_user_from_maas
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.resilience.reliability_policy import mark_degraded_dependency

router = APIRouter( tags=["MaaS Agent Mesh"])
_health_bot = MaasHealthBot(HealthBotConfig.from_env())

_HEALTH_STATUS_SOURCE_AGENT = "maas-agent-health-status-read"
_HEALTH_RUN_SOURCE_AGENT = "maas-agent-health-run"
_HEALTH_HISTORY_SOURCE_AGENT = "maas-agent-health-history-read"

_HEALTH_OBSERVED_LAYER = "api_agent_mesh_health_observed_state"
_HEALTH_CONTROL_LAYER = "api_agent_mesh_health_control_action"

AGENT_MESH_HEALTH_CLAIM_BOUNDARY = (
    "MaaS agent health-bot API evidence only. Events record local health-bot "
    "status, guarded run intent, and history metadata with redacted actor and "
    "bounded signal/action counts; they do not prove SOCKS reachability, local "
    "health URL correctness, command execution safety, or self-heal success."
)


class HealthBotRunRequest(BaseModel):
    auto_heal: bool = Field(default=False)
    dry_run: bool = Field(default=True)


def _health_bot_surface_available() -> bool:
    return (
        _health_bot is not None
        and callable(getattr(_health_bot, "run_once", None))
        and callable(getattr(_health_bot, "history", None))
    )


def _health_bot_config_available() -> bool:
    config = getattr(_health_bot, "config", None)
    return all(
        hasattr(config, attr)
        for attr in (
            "socks_host",
            "socks_port",
            "health_urls",
            "allow_external_urls",
            "enable_execute",
        )
    )


def _status_payload_available(payload: Dict[str, Any]) -> bool:
    return isinstance(payload, dict) and isinstance(payload.get("status"), str)


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _value_from_user(user: Any, key: str, default: Any = None) -> Any:
    if isinstance(user, dict):
        return user.get(key, default)
    return getattr(user, key, default)


def _actor_summary(user: Any) -> Dict[str, Any]:
    if user is None:
        return {
            "actor_user_id_hash": None,
            "actor_email_hash": None,
            "actor_email_present": False,
            "actor_role": "",
        }
    email = str(_value_from_user(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(_value_from_user(user, "id")),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(_value_from_user(user, "role", "") or "")[:40],
    }


def _agent_mesh_event_bus_from_request(request: Request | None) -> EventBus | None:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception:
        return None


def _status_counts(items: list[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"ok": 0, "warn": 0, "fail": 0, "skip": 0, "healthy": 0, "degraded": 0, "other": 0}
    for item in items:
        status = str(item.get("status", "") or "").strip().lower()
        if status in counts and status != "other":
            counts[status] += 1
        else:
            counts["other"] += 1
    return counts


def _signal_kind(name: Any) -> str:
    text = str(name or "")
    if text.startswith("health_url:"):
        return "health_url"
    if text in {"socks_port_reachability", "proxy_abort_events", "proxy_delay_ms", "proxy_log_presence"}:
        return text
    return "other"


def _signal_kind_counts(signals: list[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "socks_port_reachability": 0,
        "proxy_abort_events": 0,
        "proxy_delay_ms": 0,
        "proxy_log_presence": 0,
        "health_url": 0,
        "other": 0,
    }
    for signal in signals:
        counts[_signal_kind(signal.get("name"))] += 1
    return counts


def _action_id_counts(actions: list[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "restart_xray": 0,
        "mesh_reroute": 0,
        "restart_control_plane": 0,
        "other": 0,
    }
    for action in actions:
        action_id = str(action.get("id", "") or "")
        if action_id in counts and action_id != "other":
            counts[action_id] += 1
        else:
            counts["other"] += 1
    return counts


def _report_summary(report: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return {
            "report_status": "missing",
            "engine_bucket": "missing",
            "external_ai_providers_used": False,
            "signal_count": 0,
            "signal_status_counts": _status_counts([]),
            "signal_kind_counts": _signal_kind_counts([]),
            "proposed_action_count": 0,
            "proposed_action_counts": _action_id_counts([]),
            "executed_action_count": 0,
            "executed_action_counts": _action_id_counts([]),
            "executed_attempted_count": 0,
            "executed_success_count": 0,
        }
    signals = [item for item in report.get("signals", []) if isinstance(item, dict)]
    proposed = [
        item for item in report.get("proposed_actions", []) if isinstance(item, dict)
    ]
    executed = [
        item for item in report.get("executed_actions", []) if isinstance(item, dict)
    ]
    engine = str(report.get("engine", "") or "")
    return {
        "report_status": str(report.get("status", "") or "")[:40],
        "engine_bucket": engine[:60] if engine else "missing",
        "external_ai_providers_used": bool(report.get("external_ai_providers_used")),
        "signal_count": len(signals),
        "signal_status_counts": _status_counts(signals),
        "signal_kind_counts": _signal_kind_counts(signals),
        "proposed_action_count": len(proposed),
        "proposed_action_counts": _action_id_counts(proposed),
        "executed_action_count": len(executed),
        "executed_action_counts": _action_id_counts(executed),
        "executed_attempted_count": sum(1 for item in executed if item.get("attempted")),
        "executed_success_count": sum(1 for item in executed if item.get("success")),
    }


def _history_summary(items: list[Dict[str, Any]]) -> Dict[str, Any]:
    bounded_items = [item for item in items[:200] if isinstance(item, dict)]
    return {
        "history_item_count": len(bounded_items),
        "history_status_counts": _status_counts(bounded_items),
        "history_truncated": max(0, len(items) - len(bounded_items)),
    }


def _event_type_for_status(http_status_code: int | None) -> EventType:
    if http_status_code is None or http_status_code < 400:
        return EventType.PIPELINE_STAGE_END
    if http_status_code >= 500:
        return EventType.TASK_FAILED
    return EventType.TASK_BLOCKED


def _publish_agent_mesh_health_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    status: str,
    current_user: Any = None,
    report: Dict[str, Any] | None = None,
    readiness: Dict[str, Any] | None = None,
    history_items: list[Dict[str, Any]] | None = None,
    auto_heal: bool | None = None,
    dry_run: bool | None = None,
    token_header_present: bool | None = None,
    exec_token_configured: bool | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _agent_mesh_event_bus_from_request(request)
    if event_bus is None:
        return None

    readiness_payload = readiness if isinstance(readiness, dict) else {}
    payload: Dict[str, Any] = {
        "component": "api.maas_agent_mesh",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_actor_summary(current_user),
        **_report_summary(report),
        **_history_summary(list(history_items or [])),
        "auto_heal": auto_heal,
        "dry_run": dry_run,
        "token_header_present": token_header_present,
        "exec_token_configured": exec_token_configured,
        "agent_mesh_runtime_ready": readiness_payload.get("agent_mesh_runtime_ready"),
        "health_bot_surface_ready": readiness_payload.get("health_bot_surface_ready"),
        "health_bot_config_ready": readiness_payload.get("health_bot_config_ready"),
        "status_payload_ready": readiness_payload.get("status_payload_ready"),
        "non_dry_run_guard_ready": readiness_payload.get("non_dry_run_guard_ready"),
        "local_only_mode": readiness_payload.get("local_only_mode"),
        "degraded_dependency_count": len(readiness_payload.get("degraded_dependencies", []) or []),
        "http_status_code": http_status_code,
        "read_only": source_agent in {
            _HEALTH_STATUS_SOURCE_AGENT,
            _HEALTH_HISTORY_SOURCE_AGENT,
        },
        "observed_state": source_agent in {
            _HEALTH_STATUS_SOURCE_AGENT,
            _HEALTH_HISTORY_SOURCE_AGENT,
        },
        "control_action": source_agent == _HEALTH_RUN_SOURCE_AGENT,
        "raw_health_urls_redacted": True,
        "raw_commands_redacted": True,
        "raw_token_redacted": True,
        "raw_payload_redacted": True,
        "reason": str(reason or "")[:120],
        "claim_boundary": AGENT_MESH_HEALTH_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            _event_type_for_status(http_status_code),
            source_agent,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception:
        return None


def _agent_mesh_readiness_status(
    status_payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    health_bot_surface_ready = _health_bot_surface_available()
    health_bot_config_ready = _health_bot_config_available()
    auth_dependency_ready = callable(get_current_user_from_maas)
    status_payload_ready = (
        _status_payload_available(status_payload)
        if status_payload is not None
        else health_bot_surface_ready
    )

    config = getattr(_health_bot, "config", None)
    non_dry_run_execute_enabled = bool(getattr(config, "enable_execute", False))
    exec_token_configured = bool(os.getenv("MAAS_AGENT_BOT_TOKEN", "").strip())
    non_dry_run_guard_ready = not non_dry_run_execute_enabled or exec_token_configured

    checks = {
        "health_bot_surface": health_bot_surface_ready,
        "health_bot_config": health_bot_config_ready,
        "auth_dependency": auth_dependency_ready,
        "status_payload": status_payload_ready,
        "non_dry_run_guard": non_dry_run_guard_ready,
    }
    degraded_dependencies = [
        dependency for dependency, ready in checks.items() if not ready
    ]
    agent_mesh_runtime_ready = not degraded_dependencies

    return {
        "readiness_status": "ready" if agent_mesh_runtime_ready else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "agent_mesh_runtime_ready": agent_mesh_runtime_ready,
        "health_bot_surface_ready": health_bot_surface_ready,
        "health_bot_config_ready": health_bot_config_ready,
        "auth_dependency_ready": auth_dependency_ready,
        "status_payload_ready": status_payload_ready,
        "non_dry_run_guard_ready": non_dry_run_guard_ready,
        "non_dry_run_execute_enabled": non_dry_run_execute_enabled,
        "exec_token_configured": exec_token_configured,
        "local_only_mode": not bool(getattr(config, "allow_external_urls", False)),
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "engine": (
                status_payload.get("engine")
                if isinstance(status_payload, dict)
                else None
            ),
            "history_size": len(getattr(_health_bot, "_history", []))
            if _health_bot is not None
            else None,
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_agent_mesh_readiness"
        ),
        "claim_boundary": (
            "Readiness verifies the local health bot, auth dependency, status "
            "payload shape, and non-dry-run execution guard. It does not prove "
            "SOCKS, local health URLs, or self-heal commands are healthy."
        ),
    }


def _require_exec_token_if_needed(
    *,
    auto_heal: bool,
    dry_run: bool,
    token_header: str | None,
) -> None:
    if not auto_heal or dry_run:
        return

    expected = os.getenv("MAAS_AGENT_BOT_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="MAAS_AGENT_BOT_TOKEN is required for non-dry-run auto-heal",
        )
    if not token_header or not hmac.compare_digest(token_header, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing X-Agent-Token")


@router.get("/health/status")
async def health_status(
    request: Request,
    _user=Depends(get_current_user_from_maas),
):
    """Collect local health signals without executing heal actions."""
    started = time.monotonic()
    payload = _health_bot.run_once(auto_heal=False, dry_run=True)
    readiness = _agent_mesh_readiness_status(payload)
    for dependency in readiness["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    _publish_agent_mesh_health_event(
        request,
        source_agent=_HEALTH_STATUS_SOURCE_AGENT,
        layer=_HEALTH_OBSERVED_LAYER,
        stage="health_status_observed_state",
        operation="maas_agent_health_status",
        status=payload.get("status", "unknown"),
        current_user=_user,
        report=payload,
        readiness=readiness,
        auto_heal=False,
        dry_run=True,
        exec_token_configured=bool(os.getenv("MAAS_AGENT_BOT_TOKEN", "").strip()),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {**payload, **readiness}


@router.post("/health/run")
async def run_health_bot(
    req: HealthBotRunRequest,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    _user=Depends(get_current_user_from_maas),
    request: Request = None,
):
    """Run health bot once. Command execution is guarded by X-Agent-Token."""
    started = time.monotonic()
    expected_token = os.getenv("MAAS_AGENT_BOT_TOKEN", "").strip()
    if req.auto_heal and not req.dry_run and not expected_token:
        _publish_agent_mesh_health_event(
            request,
            source_agent=_HEALTH_RUN_SOURCE_AGENT,
            layer=_HEALTH_CONTROL_LAYER,
            stage="health_run_control",
            operation="maas_agent_health_run",
            status="blocked",
            current_user=_user,
            auto_heal=req.auto_heal,
            dry_run=req.dry_run,
            token_header_present=bool(x_agent_token),
            exec_token_configured=False,
            http_status_code=503,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="exec_token_missing",
        )
        raise HTTPException(
            status_code=503,
            detail="MAAS_AGENT_BOT_TOKEN is required for non-dry-run auto-heal",
        )
    if req.auto_heal and not req.dry_run and (
        not x_agent_token or not hmac.compare_digest(x_agent_token, expected_token)
    ):
        _publish_agent_mesh_health_event(
            request,
            source_agent=_HEALTH_RUN_SOURCE_AGENT,
            layer=_HEALTH_CONTROL_LAYER,
            stage="health_run_control",
            operation="maas_agent_health_run",
            status="blocked",
            current_user=_user,
            auto_heal=req.auto_heal,
            dry_run=req.dry_run,
            token_header_present=bool(x_agent_token),
            exec_token_configured=True,
            http_status_code=403,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="exec_token_invalid",
        )
        raise HTTPException(status_code=403, detail="Invalid or missing X-Agent-Token")

    payload = _health_bot.run_once(auto_heal=req.auto_heal, dry_run=req.dry_run)
    _publish_agent_mesh_health_event(
        request,
        source_agent=_HEALTH_RUN_SOURCE_AGENT,
        layer=_HEALTH_CONTROL_LAYER,
        stage="health_run_control",
        operation="maas_agent_health_run",
        status=payload.get("status", "unknown"),
        current_user=_user,
        report=payload,
        auto_heal=req.auto_heal,
        dry_run=req.dry_run,
        token_header_present=bool(x_agent_token),
        exec_token_configured=bool(expected_token),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return payload


@router.get("/health/history")
async def health_history(
    limit: int = Query(default=20, ge=1, le=200),
    _user=Depends(get_current_user_from_maas),
    request: Request = None,
):
    """Return most recent local health bot reports."""
    started = time.monotonic()
    items = _health_bot.history(limit)
    _publish_agent_mesh_health_event(
        request,
        source_agent=_HEALTH_HISTORY_SOURCE_AGENT,
        layer=_HEALTH_OBSERVED_LAYER,
        stage="health_history_observed_state",
        operation="maas_agent_health_history",
        status="ok",
        current_user=_user,
        history_items=items,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {"items": items}
