#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


MIN_RESTART_COOLDOWN_SEC = 1800
BLOCKING_PROVIDER_STATUSES = {"provider_outage", "overloaded", "host_degraded"}


@dataclass(frozen=True)
class HealthActionDecision:
    decision: str
    allowed: bool
    reason: str
    cooldown_remaining_sec: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _probes(state: dict[str, Any]) -> dict[str, Any]:
    probes = state.get("probes")
    return probes if isinstance(probes, dict) else {}


def _provider_guard_active(state: dict[str, Any]) -> bool:
    provider_status = str(state.get("provider_status") or "").strip().lower()
    if provider_status in BLOCKING_PROVIDER_STATUSES:
        return True
    probes = _probes(state)
    if bool(probes.get("provider_guard_active")):
        return True
    resource_status = str(probes.get("resource_status") or "").strip().lower()
    return resource_status in BLOCKING_PROVIDER_STATUSES


def _cooldown_remaining(now_epoch: int, last_restart_epoch: int, cooldown_sec: int) -> int:
    elapsed = max(0, now_epoch - max(0, last_restart_epoch))
    return max(0, cooldown_sec - elapsed)


def decide_xui_restart(
    state: dict[str, Any],
    *,
    mutation_allowed: bool,
    now_epoch: int,
    last_restart_epoch: int = 0,
    cooldown_sec: int = MIN_RESTART_COOLDOWN_SEC,
) -> HealthActionDecision:
    """Decide whether a future x-ui restart would be allowed.

    This function is intentionally pure: it does not call systemctl and does not
    write files. Shell wrappers must use it before any mutating action.
    """
    action = str(state.get("recommended_action") or "observe")
    probes = _probes(state)
    listener_ok = bool(probes.get("listener_443_ok"))
    xui_ok = bool(probes.get("xui_service_ok"))

    if action != "restart_primary":
        return HealthActionDecision(
            decision="observe",
            allowed=False,
            reason=f"recommended_action={action}",
        )

    if listener_ok and xui_ok:
        return HealthActionDecision(
            decision="observe",
            allowed=False,
            reason="primary listener and x-ui already healthy",
        )

    if _provider_guard_active(state):
        return HealthActionDecision(
            decision="blocked_provider_guard",
            allowed=False,
            reason="provider or host degradation blocks service restart",
        )

    if not mutation_allowed:
        return HealthActionDecision(
            decision="blocked_mutation_flag",
            allowed=False,
            reason="explicit mutation flag is required",
        )

    remaining = _cooldown_remaining(now_epoch, last_restart_epoch, cooldown_sec)
    if remaining > 0:
        return HealthActionDecision(
            decision="blocked_cooldown",
            allowed=False,
            reason="restart cooldown is still active",
            cooldown_remaining_sec=remaining,
        )

    return HealthActionDecision(
        decision="restart_xui",
        allowed=True,
        reason="primary listener or x-ui is unhealthy and gates passed",
    )
