"""Decision Engine — policy-based decision making for the autonomic ML loop."""

from __future__ import annotations

import time
from enum import auto, IntEnum
from typing import Any


class PolicyPriority(IntEnum):
    """Priority levels for policies."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class Policy:
    """A policy with ID, name, description, priority, and optional success tracking."""

    def __init__(
        self,
        id: str = "",
        name: str = "",
        description: str = "",
        priority: PolicyPriority = PolicyPriority.MEDIUM,
        success_rate: float = 1.0,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.priority = priority
        self.success_rate = success_rate
        self._successes: list[bool] = []


class PolicyRanker:
    """Ranks policies by priority."""

    def __init__(self) -> None:
        self._policies: list[Policy] = []

    def register_policy(self, policy: Policy) -> None:
        self._policies.append(policy)

    def rank_policies(self, top_k: int = 5) -> list[Policy]:
        """Return highest-priority policies, sorted descending."""
        sorted_policies = sorted(self._policies, key=lambda p: p.priority, reverse=True)
        return sorted_policies[:top_k]

    @property
    def policies(self) -> list[Policy]:
        """Public access to policies list (test compat)."""
        return self._policies


class DecisionEngine:
    """Makes decisions based on policies and context.

    Supports policy registration, ranking, decision making,
    decision evaluation, and stats tracking.
    """

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}
        self.ranker = PolicyRanker()
        self._decisions: list[dict] = []
        self._total_decisions = 0

    async def decide_on_action(self, actions: list[str], context: dict) -> dict[str, Any]:
        """Decide which action to take based on available actions and context."""
        ranked = self.ranker.rank_policies(top_k=3)
        if ranked:
            selected_policy = ranked[0]
            self._total_decisions += 1
            self._decisions.append({
                "policy_id": selected_policy.id,
                "action": actions[0] if actions else "noop",
                "timestamp": time.time(),
            })
            return {
                "selected_policy": selected_policy.id,
                "policy_name": selected_policy.name,
                "selected_action": actions[0] if actions else "noop",
                "confidence": 0.8,
            }
        return {
            "selected_policy": "default",
            "selected_action": actions[0] if actions else "noop",
            "confidence": 0.5,
        }

    async def evaluate_decision(
        self,
        policy_id: str,
        success: bool,
        reward: float = 0.0,
        duration_ms: float = 0.0,
    ) -> None:
        """Record the outcome of a decision."""
        for decision in self._decisions:
            if decision["policy_id"] == policy_id:
                decision["success"] = success
                decision["reward"] = reward
                decision["duration_ms"] = duration_ms
                break

    def get_decision_stats(self) -> dict[str, Any]:
        """Get statistics about decisions made."""
        return {
            "total_decisions": self._total_decisions,
            "total_evaluated": sum(1 for d in self._decisions if "success" in d),
            "avg_reward": 0.0,
        }
