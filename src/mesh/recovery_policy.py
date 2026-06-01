"""Policy guardrails for autonomous mesh recovery actions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from src.mesh.recovery_contracts import PolicyDecision


@dataclass(frozen=True)
class RecoveryPolicyResult:
    """Internal policy result with a serializable decision payload."""

    allowed: bool
    safe_mode_required: bool
    cooldown_active: bool
    execution_limit_checked: str

    def to_decision(self) -> PolicyDecision:
        return PolicyDecision(
            allowed=self.allowed,
            cooldown_active=self.cooldown_active,
            execution_limit_checked=self.execution_limit_checked,
            safe_mode_required=self.safe_mode_required,
        )


class RecoveryPolicyManager:
    """Enforce one autonomous action per incident key per cooldown window."""

    def __init__(
        self,
        cooldown_seconds: int = 600,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be positive")
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock or time.monotonic
        self.incident_history: dict[str, float] = {}

    @property
    def execution_limit_checked(self) -> str:
        if self.cooldown_seconds % 60 == 0:
            minutes = self.cooldown_seconds // 60
            unit = "minute" if minutes == 1 else "minutes"
            return f"1_attempt_per_{minutes}_{unit}"
        unit = "second" if self.cooldown_seconds == 1 else "seconds"
        return f"1_attempt_per_{self.cooldown_seconds}_{unit}"

    def check_policy(self, incident_key: str) -> RecoveryPolicyResult:
        if not incident_key:
            raise ValueError("incident_key cannot be empty")

        now = self._clock()
        last_action_time = self.incident_history.get(incident_key)
        cooldown_active = (
            last_action_time is not None
            and now - last_action_time < self.cooldown_seconds
        )
        if cooldown_active:
            return RecoveryPolicyResult(
                allowed=False,
                safe_mode_required=True,
                cooldown_active=True,
                execution_limit_checked=self.execution_limit_checked,
            )
        return RecoveryPolicyResult(
            allowed=True,
            safe_mode_required=False,
            cooldown_active=False,
            execution_limit_checked=self.execution_limit_checked,
        )

    def record_action(self, incident_key: str) -> None:
        if not incident_key:
            raise ValueError("incident_key cannot be empty")
        self.incident_history[incident_key] = self._clock()
