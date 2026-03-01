"""MaaS Agent Mesh endpoints (local-only health bot)."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from src.agents.maas_health_bot import HealthBotConfig, MaasHealthBot
from src.api.maas_auth import get_current_user_from_maas

router = APIRouter(prefix="/api/v1/maas/agents", tags=["MaaS Agent Mesh"])
_health_bot = MaasHealthBot(HealthBotConfig.from_env())


class HealthBotRunRequest(BaseModel):
    auto_heal: bool = Field(default=False)
    dry_run: bool = Field(default=True)


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
    _user=Depends(get_current_user_from_maas),
):
    """Collect local health signals without executing heal actions."""
    return _health_bot.run_once(auto_heal=False, dry_run=True)


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
    return _health_bot.run_once(auto_heal=req.auto_heal, dry_run=req.dry_run)


@router.get("/health/history")
async def health_history(
    limit: int = Query(default=20, ge=1, le=200),
    _user=Depends(get_current_user_from_maas),
):
    """Return most recent local health bot reports."""
    return {"items": _health_bot.history(limit)}
