"""
Smart Decision Making Module

Intelligent policy selection and action optimization based on learned patterns.
Integrates with MAPE-K planner and executor.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class PolicyPriority(Enum):
    """Policy priority levels"""

    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Policy:
    """Decision policy"""

    id: str
    name: str
    description: str
    priority: PolicyPriority
    success_rate: float = 0.5
    execution_count: int = 0
    last_used: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass
class PolicyOutcome:
    """Outcome of policy execution"""

    policy_id: str
    timestamp: str
    success: bool
    reward: float
    duration_ms: float
    context: Dict[str, Any] = field(default_factory=dict)


class PolicyRegistry(dict):
    """Dict-like policy store with backward-compatible membership checks."""

    def __contains__(self, item) -> bool:  # type: ignore[override]
        if isinstance(item, Policy):
            return super().__contains__(item.id)
        return super().__contains__(item)


class PolicyRanker:
    """Ranks policies based on historical performance"""

    def __init__(self):
        """Initialize ranker"""
        self.policies: Dict[str, Policy] = PolicyRegistry()
        self.outcomes: List[PolicyOutcome] = []
        self.learning_history: List[Dict[str, Any]] = []

    def register_policy(self, policy: Policy) -> None:
        """Register new policy"""
        self.policies[policy.id] = policy

    def record_outcome(self, outcome: PolicyOutcome) -> None:
        """Record policy execution outcome"""
        self.outcomes.append(outcome)

        if outcome.policy_id in self.policies:
            policy = self.policies[outcome.policy_id]
            policy.execution_count += 1
            policy.last_used = outcome.timestamp

            # Update success rate with exponential moving average
            alpha = 0.1
            new_success_value = 1.0 if outcome.success else 0.0
            policy.success_rate = (
                alpha * new_success_value + (1 - alpha) * policy.success_rate
            )

    def rank_policies(
        self, context: Optional[Dict[str, Any]] = None, top_k: int = 5
    ) -> List[Tuple[Policy, float]]:
        """
        Rank policies by expected value

        Args:
            context: Current context for filtering
            top_k: Number of top policies to return

        Returns:
            List of (policy, score) tuples
        """
        ranked = []

        for policy in self.policies.values():
            # Compute policy score
            score = self._compute_policy_score(policy, context)
            ranked.append((policy, score))

        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)

        return ranked[:top_k]

    def _compute_policy_score(
        self, policy: Policy, context: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Compute composite score for policy

        Factors:
        - Success rate (weight: 0.5)
        - Priority (weight: 0.3)
        - Recency (weight: 0.2)
        """
        # Success component
        success_score = policy.success_rate

        # Priority component (normalized)
        priority_score = 1.0 - (policy.priority.value / 10.0)

        # Recency component
        recency_score = 0.5
        if policy.last_used:
            try:
                last_time = datetime.fromisoformat(policy.last_used)
                age_hours = (datetime.now() - last_time).total_seconds() / 3600
                recency_score = max(0.0, 1.0 - (age_hours / 24.0))  # Decay over 24h
            except:
                pass

        # Composite score
        score = 0.5 * success_score + 0.3 * priority_score + 0.2 * recency_score

        return float(score)

    def get_stats(self) -> Dict[str, Any]:
        """Get ranking statistics"""
        if not self.policies:
            return {"error": "No policies registered"}

        success_rates = [p.success_rate for p in self.policies.values()]
        execution_counts = [p.execution_count for p in self.policies.values()]

        return {
            "total_policies": len(self.policies),
            "total_outcomes": len(self.outcomes),
            "avg_success_rate": float(np.mean(success_rates)) if success_rates else 0.0,
            "total_executions": sum(execution_counts),
            "most_used": (
                max(self.policies.items(), key=lambda x: x[1].execution_count)[0]
                if self.policies
                else None
            ),
        }


class DecisionEngine:
    """Intelligent decision engine for autonomous actions"""

    def __init__(self, ranker: Optional[PolicyRanker] = None):
        """
        Initialize decision engine

        Args:
            ranker: Policy ranker (create if None)
        """
        self.ranker = ranker or PolicyRanker()
        self.decision_log: List[Dict[str, Any]] = []
        self.performance_metrics: Dict[str, List[float]] = {}

    async def decide_on_action(
        self,
        available_policies: List[str],
        context: Dict[str, Any],
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Make intelligent decision on action

        Args:
            available_policies: IDs of available policies
            context: Current context (metrics, state, etc.)
            constraints: Execution constraints

        Returns:
            Decision dict with selected policy and reasoning
        """
        constraints = constraints or {}

        # Filter policies
        valid_policies = [
            p for p in self.ranker.policies.values() if p.id in available_policies
        ]

        if not valid_policies:
            return {
                "status": "error",
                "error": "No valid policies available",
                "timestamp": datetime.now().isoformat(),
            }

        # Rank policies
        ranked = self.ranker.rank_policies(context, top_k=3)

        # Select best policy
        if not ranked:
            selected_policy = valid_policies[0]
            score = 0.5
        else:
            selected_policy, score = ranked[0]

        decision = {
            "status": "success",
            "selected_policy": selected_policy.id,
            "policy_name": selected_policy.name,
            "confidence": float(score),
            "ranked_candidates": [
                {"id": p.id, "name": p.name, "score": float(s)} for p, s in ranked[:3]
            ],
            "reasoning": self._generate_reasoning(selected_policy, context),
            "timestamp": datetime.now().isoformat(),
        }

        self.decision_log.append(decision)
        return decision

    def _generate_reasoning(self, policy: Policy, context: Dict[str, Any]) -> str:
        """Generate human-readable reasoning"""
        reasons = []

        if policy.success_rate > 0.8:
            reasons.append(f"high success rate ({policy.success_rate:.1%})")

        if (
            policy.priority == PolicyPriority.HIGH
            or policy.priority == PolicyPriority.CRITICAL
        ):
            reasons.append(f"{policy.priority.name.lower()} priority")

        if context.get("component_type"):
            reasons.append(f"suitable for {context['component_type']}")

        if reasons:
            return f"Selected because: {', '.join(reasons)}"
        return "Selected based on ranking"

    async def evaluate_decision(
        self,
        policy_id: str,
        success: bool,
        reward: float,
        duration_ms: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Evaluate decision outcome and update rankings

        Args:
            policy_id: Policy that was executed
            success: Whether execution succeeded
            reward: Reward value
            duration_ms: Execution duration
            context: Execution context
        """
        outcome = PolicyOutcome(
            policy_id=policy_id,
            timestamp=datetime.now().isoformat(),
            success=success,
            reward=reward,
            duration_ms=duration_ms,
            context=context or {},
        )

        self.ranker.record_outcome(outcome)

        # Track performance
        if policy_id not in self.performance_metrics:
            self.performance_metrics[policy_id] = []
        self.performance_metrics[policy_id].append(reward)

    async def continuous_learning(self, window_size: int = 100) -> Dict[str, Any]:
        """
        Continuous learning from recent outcomes

        Args:
            window_size: Number of recent outcomes to analyze

        Returns:
            Learning summary
        """
        recent_outcomes = self.ranker.outcomes[-window_size:]

        if not recent_outcomes:
            return {"error": "No outcomes to learn from"}

        # Analyze by policy
        policy_performance = {}

        for outcome in recent_outcomes:
            if outcome.policy_id not in policy_performance:
                policy_performance[outcome.policy_id] = {
                    "successes": 0,
                    "failures": 0,
                    "total_reward": 0.0,
                }

            perf = policy_performance[outcome.policy_id]
            if outcome.success:
                perf["successes"] += 1
            else:
                perf["failures"] += 1
            perf["total_reward"] += outcome.reward

        # Identify patterns
        insights = []

        for policy_id, perf in policy_performance.items():
            total = perf["successes"] + perf["failures"]
            success_rate = perf["successes"] / total if total > 0 else 0.0
            avg_reward = perf["total_reward"] / total if total > 0 else 0.0

            if success_rate > 0.8:
                insights.append(
                    f"Policy {policy_id} is highly reliable ({success_rate:.1%})"
                )
            elif success_rate < 0.3:
                insights.append(f"Policy {policy_id} needs review ({success_rate:.1%})")

            if avg_reward > 0.8:
                insights.append(f"Policy {policy_id} provides high value")

        result = {
            "window_size": len(recent_outcomes),
            "policies_analyzed": len(policy_performance),
            "insights": insights,
            "policy_performance": policy_performance,
            "timestamp": datetime.now().isoformat(),
        }

        return result

    def get_decision_stats(self) -> Dict[str, Any]:
        """Get decision statistics"""
        if not self.decision_log:
            return {"decisions": 0}

        confidences = [d["confidence"] for d in self.decision_log]

        return {
            "total_decisions": len(self.decision_log),
            "avg_confidence": float(np.mean(confidences)),
            "min_confidence": float(np.min(confidences)),
            "max_confidence": float(np.max(confidences)),
            "unique_policies": len(
                set(d["selected_policy"] for d in self.decision_log)
            ),
            "timestamp": datetime.now().isoformat(),
        }


# Example usage
async def example_decision_workflow():
    """Example decision making workflow"""
    # Create decision engine
    engine = DecisionEngine()

    # Register policies
    policies = [
        Policy(
            id="scale_up",
            name="Scale Up Replicas",
            description="Increase replicas for load handling",
            priority=PolicyPriority.HIGH,
            tags=["scaling", "reactive"],
        ),
        Policy(
            id="optimize_config",
            name="Optimize Configuration",
            description="Adjust system parameters",
            priority=PolicyPriority.MEDIUM,
            tags=["optimization", "proactive"],
        ),
        Policy(
            id="restart_component",
            name="Restart Component",
            description="Restart misbehaving component",
            priority=PolicyPriority.CRITICAL,
            tags=["recovery", "reactive"],
        ),
    ]

    for policy in policies:
        engine.ranker.register_policy(policy)

    # Make decision
    context = {"component_type": "analyzer", "cpu_usage": 0.85}
    decision = await engine.decide_on_action(
        ["scale_up", "optimize_config", "restart_component"], context
    )
    print(f"Decision: {decision}")

    # Evaluate outcome
    await engine.evaluate_decision(
        policy_id="scale_up",
        success=True,
        reward=0.9,
        duration_ms=45.2,
        context={"cpu_before": 0.85, "cpu_after": 0.65},
    )

    # Learning
    learning = await engine.continuous_learning()
    print(f"Learning insights: {learning}")

    return engine


if __name__ == "__main__":
    engine = DecisionEngine()
    print("Smart Decision Engine initialized")
