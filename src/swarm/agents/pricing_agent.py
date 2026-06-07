"""
Dynamic Pricing Agent for MaaS Marketplace.
Evolution of Swarm Intelligence (Q2 P4).
"""

import logging
import inspect
import time
from typing import Any, Callable, Dict, Optional

from src.swarm.agent import Agent, AgentCapabilities

logger = logging.getLogger(__name__)


class MarketSignalPricingPolicy:
    """Deterministic pricing policy based on explicit marketplace signals."""

    def __init__(
        self,
        base_price: float,
        min_multiplier: float = 0.5,
        max_multiplier: float = 4.0,
        min_price: float = 0.001,
        max_price: float = 1.0,
    ):
        if base_price <= 0:
            raise ValueError("base_price must be greater than zero")
        self.base_price = float(base_price)
        self.min_multiplier = float(min_multiplier)
        self.max_multiplier = float(max_multiplier)
        self.min_price = float(min_price)
        self.max_price = float(max_price)

    @staticmethod
    def _metric(
        payload: Dict[str, Any],
        name: str,
        default: float,
        minimum: float,
        maximum: float,
        defaulted: list[str],
    ) -> float:
        if name in payload:
            raw = payload[name]
        else:
            raw = default
            defaulted.append(name)

        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"{name} must be numeric")

        value = float(raw)
        if value < minimum or value > maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
        return value

    def recommend(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Return a price recommendation from bounded market inputs."""
        node_id = payload.get("node_id")
        if not node_id:
            raise ValueError("node_id is required")

        defaulted: list[str] = []
        demand_score = self._metric(payload, "demand_score", 0.5, 0.0, 1.0, defaulted)
        scarcity = self._metric(payload, "scarcity", 0.1, 0.0, 1.0, defaulted)
        utilization = self._metric(
            payload, "utilization", demand_score, 0.0, 1.0, defaulted
        )
        reliability_score = self._metric(
            payload, "reliability_score", 0.95, 0.0, 1.0, defaulted
        )
        region_cost_multiplier = self._metric(
            payload, "region_cost_multiplier", 1.0, 0.25, 5.0, defaulted
        )

        raw_multiplier = (
            1.0
            + demand_score * 0.55
            + scarcity * 1.15
            + utilization * 0.35
            + (reliability_score - 0.5) * 0.25
        ) * region_cost_multiplier
        multiplier = min(max(raw_multiplier, self.min_multiplier), self.max_multiplier)
        suggested_price = min(
            max(self.base_price * multiplier, self.min_price),
            self.max_price,
        )
        confidence = max(0.5, min(0.99, 0.95 - len(defaulted) * 0.06))

        return {
            "suggested_price": round(suggested_price, 4),
            "multiplier": round(suggested_price / self.base_price, 4),
            "confidence": round(confidence, 2),
            "pricing_model": "market_signal_policy",
            "signals": {
                "demand_score": demand_score,
                "scarcity": scarcity,
                "utilization": utilization,
                "reliability_score": reliability_score,
                "region_cost_multiplier": region_cost_multiplier,
                "defaulted": defaulted,
            },
        }


class DynamicPricingAgent(Agent):
    """
    Agent responsible for analyzing marketplace demand and suggesting optimal prices.
    Uses Reinforcement Learning (PPO) via PARL Engine.
    """

    def __init__(
        self,
        agent_id: str,
        *,
        base_price: float = 0.01,
        pricing_policy: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ):
        capabilities = AgentCapabilities(
            can_read_metrics=True,
            can_suggest_prices=True,
            max_parallel_tasks=5
        )
        super().__init__(agent_id, "pricing_optimizer", capabilities)
        self.base_price = float(base_price)  # $ per node-hour
        self.pricing_policy = pricing_policy or MarketSignalPricingPolicy(
            base_price=self.base_price
        )
        logger.info(f"DynamicPricingAgent {agent_id} initialized")

    async def execute_task(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes demand and calculates price multipliers.
        """
        start_time = time.time()
        try:
            node_id = payload.get("node_id")
            self.last_thinking_context = self.thinking_coach.prepare_task(
                {
                    "task_id": task_id,
                    "task_type": "pricing",
                    "goal": "produce a bounded marketplace price recommendation",
                    "payload": payload,
                }
            )
            recommendation = await self._recommend(payload)
            recommendation["node_id"] = node_id
            recommendation["task_id"] = task_id
            recommendation["thinking_techniques"] = list(
                (self.last_thinking_context or {}).get("techniques", [])
            )

            logger.info(
                "💰 Node %s: Suggested price $%.4f (Multiplier: %.2fx)",
                node_id,
                recommendation["suggested_price"],
                recommendation["multiplier"],
            )

            self.completed_tasks += 1
            return recommendation
        except Exception:
            self.failed_tasks += 1
            raise
        finally:
            self.total_execution_time += (time.time() - start_time) * 1000
            self._update_metrics()

    async def _recommend(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Run the configured pricing policy and validate the result shape."""
        if hasattr(self.pricing_policy, "recommend"):
            recommendation = self.pricing_policy.recommend(payload)  # type: ignore[attr-defined]
        else:
            recommendation = self.pricing_policy(payload)

        if inspect.isawaitable(recommendation):
            recommendation = await recommendation

        if not isinstance(recommendation, dict):
            raise ValueError("pricing policy must return a dictionary")

        for field in ("suggested_price", "multiplier", "confidence"):
            value = recommendation.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"pricing policy field {field!r} must be numeric")

        return dict(recommendation)

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status["optimized_count"] = self.completed_tasks
        return status
