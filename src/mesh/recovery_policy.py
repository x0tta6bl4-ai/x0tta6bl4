"""Policy guardrails for autonomous mesh recovery actions."""

from __future__ import annotations

import time
import hashlib
from dataclasses import dataclass
from typing import Any, Callable

from src.core.agent_thinking import AgentThinkingCoach
from src.mesh.recovery_contracts import PolicyDecision


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="recovery-policy-manager",
            role="healing",
            capabilities=("ops", "zero-trust"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "recovery_policy_manager_init",
                "goal": "Initialize recovery cooldown policy safely",
                "signals": {
                    "cooldown_seconds": cooldown_seconds,
                    "incident_history_bucket": "0",
                },
                "safety_boundary": (
                    "Keep incident keys and recovery action payloads out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_incident_keys": True,
                    "preserve_policy_decision": True,
                },
                "safety_boundary": "Use hashes, cooldown status, counts, and booleans.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

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
            self._record_thinking(
                "recovery_policy_checked",
                "Deny autonomous recovery while cooldown is active",
                {
                    "incident_hash": _safe_hash(incident_key),
                    "cooldown_active": True,
                    "allowed": False,
                    "history_count_bucket": _safe_count_bucket(
                        len(self.incident_history)
                    ),
                },
            )
            return RecoveryPolicyResult(
                allowed=False,
                safe_mode_required=True,
                cooldown_active=True,
                execution_limit_checked=self.execution_limit_checked,
            )
        result = RecoveryPolicyResult(
            allowed=True,
            safe_mode_required=False,
            cooldown_active=False,
            execution_limit_checked=self.execution_limit_checked,
        )
        self._record_thinking(
            "recovery_policy_checked",
            "Allow autonomous recovery outside cooldown",
            {
                "incident_hash": _safe_hash(incident_key),
                "cooldown_active": False,
                "allowed": True,
                "history_count_bucket": _safe_count_bucket(len(self.incident_history)),
            },
        )
        return result

    def record_action(self, incident_key: str) -> None:
        if not incident_key:
            raise ValueError("incident_key cannot be empty")
        self.incident_history[incident_key] = self._clock()
        self._record_thinking(
            "recovery_policy_action_recorded",
            "Record recovery action timestamp safely",
            {
                "incident_hash": _safe_hash(incident_key),
                "history_count_bucket": _safe_count_bucket(len(self.incident_history)),
            },
        )
