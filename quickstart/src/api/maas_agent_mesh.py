"""MaaS Agent Mesh endpoints (local-only health bot)."""

from __future__ import annotations

import hmac
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.agents.maas_health_bot import HealthBotConfig, MaasHealthBot
from src.api.maas_auth import get_current_user_from_maas
from src.core.resilience.reliability_policy import mark_degraded_dependency

router = APIRouter(prefix="/api/v1/maas/agents", tags=["MaaS Agent Mesh"])
_health_bot = MaasHealthBot(HealthBotConfig.from_env())


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
    payload = _health_bot.run_once(auto_heal=False, dry_run=True)
    readiness = _agent_mesh_readiness_status(payload)
    for dependency in readiness["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return {**payload, **readiness}


@router.post("/health/run")
async def run_health_bot(
    req: HealthBotRunRequest,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    _user=Depends(get_current_user_from_maas),
):
    """Run health bot once. Command execution is guarded by X-Agent-Token."""
    _require_exec_token_if_needed(
        auto_heal=req.auto_heal,
        dry_run=req.dry_run,
        token_header=x_agent_token,
    )
    try:
        result = _health_bot.run_once(auto_heal=req.auto_heal, dry_run=req.dry_run)
    except Exception:
        return {"error": "health bot failed", "status": "error"}
    return result


@router.get("/health/history")
async def health_history(
    limit: int = Query(default=20, ge=1, le=200),
    _user=Depends(get_current_user_from_maas),
):
    """Return most recent local health bot reports."""
    return {"items": _health_bot.history(limit)}
