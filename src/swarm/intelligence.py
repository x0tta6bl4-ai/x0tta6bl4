"""
Swarm Intelligence Module
=========================

Provides distributed decision-making capabilities for swarm coordination.
Integrates with existing consensus algorithms (Raft, Paxos, PBFT) and
supports optional LLM-based decisions via Kimi K2.5 model.

Features:
- Distributed decision making with < 100ms latency
- Integration with Raft, Paxos, and PBFT consensus
- Optional Kimi K2.5 LLM-based decisions
- MAPE-K integration for autonomous decisions
- Action proposal and consensus tracking

Example:
    >>> from src.swarm.intelligence import SwarmIntelligence, DecisionContext
    >>> swarm = SwarmIntelligence(node_id="agent-1")
    >>> await swarm.initialize()
    >>> 
    >>> context = DecisionContext(topic="routing", data={"path": "A->B"})
    >>> result = await swarm.make_decision(context, timeout_ms=100)
    >>> print(result.approved)
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import AsyncSafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

from .consensus_integration import (
    SwarmConsensusManager,
    ConsensusMode,
    AgentInfo,
)

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "swarm-mapek"

MAPEK_CLAIM_BOUNDARY = (
    "Swarm MAPE-K execution event only. It records local identity, policy, "
    "consensus, and safe actuator state; it is not production rollout or "
    "external settlement evidence."
)


class DecisionPriority(str, Enum):
    """Priority levels for decisions."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DecisionType(str, Enum):
    """Types of decisions the swarm can make."""
    ROUTING = "routing"
    SCALING = "scaling"
    HEALING = "healing"
    CONFIGURATION = "configuration"
    RESOURCE_ALLOCATION = "resource_allocation"
    FAULT_TOLERANCE = "fault_tolerance"
    LOAD_BALANCING = "load_balancing"
    CUSTOM = "custom"


class ConsensusStatus(str, Enum):
    """Status of the consensus system."""
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"


@dataclass
class DecisionContext:
    """Context for a swarm decision."""
    topic: str
    description: str = ""
    decision_type: DecisionType = DecisionType.CUSTOM
    priority: DecisionPriority = DecisionPriority.NORMAL
    data: Dict[str, Any] = field(default_factory=dict)
    options: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "description": self.description,
            "decision_type": self.decision_type.value,
            "priority": self.priority.value,
            "data": self.data,
            "options": self.options,
            "metadata": self.metadata,
        }


@dataclass
class SwarmAction:
    """An action proposed to the swarm."""
    action_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    proposer_id: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    requires_consensus: bool = True
    timeout_ms: int = 100
    priority: DecisionPriority = DecisionPriority.NORMAL
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "description": self.description,
            "parameters": self.parameters,
            "proposer_id": self.proposer_id,
            "created_at": self.created_at.isoformat(),
            "requires_consensus": self.requires_consensus,
            "timeout_ms": self.timeout_ms,
            "priority": self.priority.value,
        }


@dataclass
class DecisionResult:
    """Result of a swarm decision."""
    decision_id: str
    approved: bool
    context: DecisionContext
    consensus_mode: ConsensusMode
    latency_ms: float
    participation_rate: float = 0.0
    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    winner: Optional[Any] = None
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "approved": self.approved,
            "context": self.context.to_dict(),
            "consensus_mode": self.consensus_mode.value,
            "latency_ms": self.latency_ms,
            "participation_rate": self.participation_rate,
            "votes_for": self.votes_for,
            "votes_against": self.votes_against,
            "votes_abstain": self.votes_abstain,
            "winner": self.winner,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class SwarmNodeInfo:
    """Information about a node in the swarm."""
    node_id: str
    name: str = ""
    is_leader: bool = False
    is_active: bool = True
    capabilities: Set[str] = field(default_factory=set)
    weight: float = 1.0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "is_leader": self.is_leader,
            "is_active": self.is_active,
            "capabilities": list(self.capabilities),
            "weight": self.weight,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }


class MAPEKIntegration:
    """
    Integration with MAPE-K autonomic loop for autonomous decisions.
    
    Provides:
    - Monitor: Collect swarm state and metrics
    - Analyze: Detect anomalies and opportunities
    - Plan: Generate action proposals
    - Execute: Apply approved actions
    - Knowledge: Learn from outcomes
    """
    
    def __init__(
        self,
        swarm_intelligence: "SwarmIntelligence",
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[Any] = None,
    ):
        self.swarm = swarm_intelligence
        self._metrics_history: List[Dict[str, Any]] = []
        self._action_history: List[Dict[str, Any]] = []
        self._learning_data: Dict[str, Any] = {}
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_SWARM_MAPEK_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_SWARM_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="swarm-mapek")
        self.identity = {
            "node_id": getattr(swarm_intelligence, "node_id", ""),
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }
        self._last_decision_result: Optional[DecisionResult] = None
        self.safe_actuator = safe_actuator or AsyncSafeActuator(self._propose_action_internal)

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except Exception as exc:
            logger.error("Failed to initialize swarm MAPE-K EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize swarm MAPE-K policy engine: %s", exc)
            return None

    @staticmethod
    def _policy_allowed(decision: Any) -> bool:
        return normalize_policy_allowed(decision)

    @staticmethod
    def _policy_reason(decision: Any) -> str:
        return normalize_policy_reason(decision)

    @staticmethod
    def _policy_rules(decision: Any) -> list[str]:
        return normalize_policy_rules(decision)

    @classmethod
    def _safe_value(cls, key: str, value: Any, depth: int = 0) -> Any:
        blocked_fragments = ("secret", "password", "token", "key", "private")
        if any(fragment in str(key).lower() for fragment in blocked_fragments):
            return "<redacted>"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict) and depth < 3:
            return {
                str(child_key): cls._safe_value(str(child_key), child_value, depth + 1)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list) and depth < 3:
            return [cls._safe_value(key, item, depth + 1) for item in value]
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    @staticmethod
    def _action_resource_name(action_type: str) -> str:
        action_lower = str(action_type or "unknown_action").lower().strip()
        slug = "".join(
            char if char.isalnum() else "_"
            for char in action_lower
        ).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug or "unknown_action"

    def _action_context(self, action: SwarmAction) -> Dict[str, Any]:
        return {
            "node_id": self.identity["node_id"],
            "action_id": action.action_id,
            "action_type": action.action_type,
            "description": action.description,
            "parameters": dict(action.parameters),
            "proposer_id": action.proposer_id,
            "requires_consensus": action.requires_consensus,
            "timeout_ms": action.timeout_ms,
            "priority": action.priority.value,
        }

    def _publish_execution_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        action: SwarmAction,
        context: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action_resource = self._action_resource_name(action.action_type)
        payload = {
            "component": "swarm.intelligence.mapek",
            "stage": stage,
            "action_id": action.action_id,
            "action_type": action.action_type,
            "action_resource": action_resource,
            "resource": f"swarm:mapek:{action_resource}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "result": self._safe_context(result or {}) if result is not None else None,
            "success": result.get("success") if result is not None else None,
            "reason": reason,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": self._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "safe_actuator": True,
            "claim_boundary": MAPEK_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish swarm MAPE-K event: %s", exc)
            return None

    def _evaluate_action_policy(self, action: SwarmAction) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "swarm MAPE-K policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "swarm MAPE-K SPIFFE identity is required for policy evaluation"
        action_resource = self._action_resource_name(action.action_type)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"swarm:mapek:{action_resource}",
                workload_type="swarm-mapek",
            )
        except Exception as exc:
            return False, None, f"swarm MAPE-K policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "swarm MAPE-K policy denied action"
        return True, decision, self._policy_reason(decision)

    async def _execute_safe_actuator(
        self,
        action_type: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        raw = self.safe_actuator.execute(action_type, context)
        if asyncio.iscoroutine(raw):
            return await raw
        if isinstance(raw, SafeActuatorResult):
            return raw
        if isinstance(raw, dict):
            return SafeActuatorResult(
                success=bool(raw.get("success", raw.get("ok", False))),
                reason=str(raw.get("reason", raw.get("error", "")) or ""),
                simulated=bool(raw.get("simulated", False)),
            )
        return SafeActuatorResult(bool(raw))

    async def _propose_action_internal(
        self,
        _action_type: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        action = context.get("_action")
        if not isinstance(action, SwarmAction):
            return SafeActuatorResult(False, "swarm MAPE-K action is missing")
        decision_result = await self.swarm.propose_action(action)
        self._last_decision_result = decision_result
        if decision_result.approved:
            return SafeActuatorResult(True, decision_result.reason)
        return SafeActuatorResult(
            False,
            decision_result.reason or "swarm consensus rejected MAPE-K action",
        )
    
    async def monitor(self) -> Dict[str, Any]:
        """Collect swarm state and metrics."""
        status = await self.swarm.get_consensus_status()
        nodes = self.swarm.get_nodes()
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "consensus_status": status.value,
            "active_nodes": sum(1 for n in nodes if n.is_active),
            "total_nodes": len(nodes),
            "pending_decisions": len(self.swarm._pending_decisions),
        }
        
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > 100:
            self._metrics_history = self._metrics_history[-100:]
        
        return metrics
    
    def analyze(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Analyze metrics for anomalies and opportunities."""
        anomalies = []
        
        # Check node availability
        active_ratio = metrics.get("active_nodes", 0) / max(metrics.get("total_nodes", 1), 1)
        if active_ratio < 0.5:
            anomalies.append({
                "type": "low_availability",
                "severity": "high",
                "value": active_ratio,
            })
        
        # Check pending decisions backlog
        pending = metrics.get("pending_decisions", 0)
        if pending > 10:
            anomalies.append({
                "type": "decision_backlog",
                "severity": "medium",
                "value": pending,
            })
        
        return anomalies
    
    def plan(self, anomalies: List[Dict[str, Any]]) -> List[SwarmAction]:
        """Generate action proposals based on anomalies."""
        actions = []
        
        for anomaly in anomalies:
            if anomaly["type"] == "low_availability":
                actions.append(SwarmAction(
                    action_type="healing",
                    description="Initiate node recovery procedure",
                    parameters={"anomaly": anomaly},
                    priority=DecisionPriority.HIGH,
                ))
            elif anomaly["type"] == "decision_backlog":
                actions.append(SwarmAction(
                    action_type="scaling",
                    description="Request additional decision capacity",
                    parameters={"anomaly": anomaly},
                    priority=DecisionPriority.NORMAL,
                ))
        
        return actions
    
    async def execute(self, action: SwarmAction) -> Dict[str, Any]:
        """Execute an approved action."""
        result = {
            "action_id": action.action_id,
            "action_type": action.action_type,
            "executed_at": datetime.utcnow().isoformat(),
            "success": False,
            "safe_actuator": True,
        }
        context = self._action_context(action)
        
        try:
            self._last_decision_result = None
            self._publish_execution_event(
                EventType.COORDINATION_REQUEST,
                stage="received",
                action=action,
                context=context,
            )

            policy_allowed, policy_decision, policy_reason = (
                self._evaluate_action_policy(action)
            )
            if not policy_allowed:
                result.update({
                    "error": policy_reason,
                    "policy_required": True,
                    "matched_rules": self._policy_rules(policy_decision),
                })
                self._publish_execution_event(
                    EventType.TASK_BLOCKED,
                    stage="policy_denied",
                    action=action,
                    context=context,
                    result=result,
                    reason=policy_reason,
                    policy_decision=policy_decision,
                )
                return result

            self._publish_execution_event(
                EventType.PIPELINE_STAGE_START,
                stage="actuator_start",
                action=action,
                context=context,
                reason=policy_reason,
                policy_decision=policy_decision,
            )

            actuator_context = dict(context)
            actuator_context["_action"] = action
            actuator_result = await self._execute_safe_actuator(
                action.action_type,
                actuator_context,
            )
            if self._last_decision_result is not None:
                result["decision"] = self._last_decision_result.to_dict()

            if actuator_result.simulated:
                reason = actuator_result.reason or "safe actuator returned simulated result"
                result.update({"error": reason, "simulated": True})
                self._publish_execution_event(
                    EventType.TASK_FAILED,
                    stage="actuator_simulated",
                    action=action,
                    context=context,
                    result=result,
                    reason=reason,
                    policy_decision=policy_decision,
                )
            elif actuator_result.success:
                result.update({
                    "success": True,
                    "reason": actuator_result.reason or policy_reason,
                    "simulated": actuator_result.simulated,
                })
                self._publish_execution_event(
                    EventType.PIPELINE_STAGE_END,
                    stage="actuator_completed",
                    action=action,
                    context=context,
                    result=result,
                    reason=actuator_result.reason or policy_reason,
                    policy_decision=policy_decision,
                )
            else:
                reason = actuator_result.reason or "swarm MAPE-K safe actuator failed"
                result.update({"error": reason, "simulated": actuator_result.simulated})
                self._publish_execution_event(
                    EventType.TASK_FAILED,
                    stage="actuator_failed",
                    action=action,
                    context=context,
                    result=result,
                    reason=reason,
                    policy_decision=policy_decision,
                )
        except Exception as e:
            result["error"] = str(e)
            self._publish_execution_event(
                EventType.TASK_FAILED,
                stage="actuator_error",
                action=action,
                context=context,
                result=result,
                reason=str(e),
            )
        finally:
            self._action_history.append(result)
            if len(self._action_history) > 50:
                self._action_history = self._action_history[-50:]
        
        return result
    
    def learn(self, action: SwarmAction, result: Dict[str, Any]) -> None:
        """Learn from action outcomes."""
        action_type = action.action_type
        if action_type not in self._learning_data:
            self._learning_data[action_type] = {
                "total": 0,
                "successful": 0,
            }
        
        self._learning_data[action_type]["total"] += 1
        if result.get("success"):
            self._learning_data[action_type]["successful"] += 1
    
    def get_success_rate(self, action_type: str) -> float:
        """Get success rate for an action type."""
        data = self._learning_data.get(action_type, {})
        total = data.get("total", 0)
        if total == 0:
            return 0.5  # Unknown
        return data.get("successful", 0) / total


class KimiK25Integration:
    """
    Integration with Kimi K2.5 (or any OpenAI-compatible) LLM for swarm decisions.

    Calls the chat-completions endpoint to get a recommendation from ``options``
    given a ``DecisionContext``.  Falls back to a score-based heuristic when the
    endpoint is unreachable, returns an unparseable response, or times out.

    Configuration
    -------------
    - ``api_endpoint``: full URL, e.g. ``https://api.moonshot.cn/v1`` or a
      local proxy.  The path ``/chat/completions`` is appended automatically.
    - ``api_key``: Bearer token; can also be supplied via ``KIMI_API_KEY`` env
      var.
    - ``model``: model tag; defaults to ``moonshot-v1-8k``.
    - ``timeout_s``: HTTP timeout in seconds (default 30).
    - ``max_retries``: number of retry attempts on transient errors (default 2).
    """

    _DEFAULT_ENDPOINT = "https://api.moonshot.cn/v1"
    _MODEL = "moonshot-v1-8k"
    _SYSTEM_PROMPT = (
        "You are a distributed-systems decision-making assistant for an autonomous "
        "mesh node. Given a decision context and a numbered list of options, reply "
        "with ONLY a JSON object: {\"index\": <0-based int>, \"reasoning\": <string>}. "
        "Choose the option that best balances safety, performance, and fault tolerance."
    )

    def __init__(
        self,
        enabled: bool = False,
        api_endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_s: float = 30.0,
        max_retries: int = 2,
    ):
        self.enabled = enabled
        self.api_endpoint = (api_endpoint or self._DEFAULT_ENDPOINT).rstrip("/")
        self._api_key = api_key or ""
        self._model = model or self._MODEL
        self._timeout_s = timeout_s
        self._max_retries = max_retries

        self._request_count = 0
        self._error_count = 0
        self._total_latency_ms = 0.0

        # Lazy-imported to avoid hard dep at module level
        self._httpx: Optional[Any] = None

    def _get_api_key(self) -> str:
        import os
        return self._api_key or os.environ.get("KIMI_API_KEY", "")

    def _load_httpx(self) -> Any:
        if self._httpx is None:
            import httpx  # already in requirements.txt
            self._httpx = httpx
        return self._httpx

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_user_message(self, context: DecisionContext, options: List[Any]) -> str:
        import json as _json
        lines = [
            f"Decision topic: {context.topic}",
            f"Type: {context.decision_type.value}",
            f"Priority: {context.priority.value}",
        ]
        if context.description:
            lines.append(f"Description: {context.description}")
        if context.data:
            lines.append(f"Context data: {_json.dumps(context.data, default=str)}")
        lines.append(f"\nOptions ({len(options)} total):")
        for i, opt in enumerate(options):
            lines.append(f"  [{i}] {opt}")
        lines.append("\nRespond with JSON only: {\"index\": <int>, \"reasoning\": <str>}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(text: str, n_options: int) -> Tuple[int, str]:
        """Extract index+reasoning from LLM JSON reply; raise ValueError on failure."""
        import json as _json
        import re

        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
        # Find first {...} block
        match = re.search(r"\{[^{}]+\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in: {text!r}")
        obj = _json.loads(match.group())
        idx = int(obj["index"])
        if not (0 <= idx < n_options):
            raise ValueError(f"index {idx} out of range [0, {n_options})")
        reasoning = str(obj.get("reasoning", ""))
        return idx, reasoning

    # ------------------------------------------------------------------
    # Score-based fallback (no LLM call)
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_fallback(context: DecisionContext, options: List[Any]) -> Tuple[int, str]:
        """
        Simple local heuristic used when LLM is unavailable.

        Scoring rules (higher = better):
        - HEALING / FAULT_TOLERANCE options score +2
        - Options whose string repr contains "safe", "stable", "primary" score +1
        - First option gets +0.5 tie-breaker
        Returns the highest-scoring option index.
        """
        priority_keywords = {"safe", "stable", "primary", "main", "default"}
        high_priority_types = {DecisionType.HEALING, DecisionType.FAULT_TOLERANCE}
        scores = []
        for i, opt in enumerate(options):
            score = 0.0
            opt_str = str(opt).lower()
            if context.decision_type in high_priority_types:
                score += 2.0
            if any(kw in opt_str for kw in priority_keywords):
                score += 1.0
            if i == 0:
                score += 0.5  # tie-breaker
            scores.append(score)
        best = max(range(len(scores)), key=lambda i: scores[i])
        return best, f"heuristic fallback (LLM unavailable): selected option {best}"

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def enhance_decision(
        self,
        context: DecisionContext,
        options: List[Any],
    ) -> Tuple[int, str]:
        """
        Use Kimi K2.5 LLM to recommend the best option.

        Returns ``(recommended_option_index, reasoning_string)``.
        Falls back to a local heuristic on any error or timeout.
        """
        if not self.enabled or not options:
            return (0, "LLM not enabled")

        start_time = time.time()

        # Resolve key; if missing, skip the real call entirely
        api_key = self._get_api_key()
        if not api_key:
            logger.debug("KimiK25Integration: no API key — using heuristic fallback")
            return self._heuristic_fallback(context, options)

        httpx = self._load_httpx()
        url = f"{self.api_endpoint}/chat/completions"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": self._SYSTEM_PROMPT},
                {"role": "user", "content": self._build_user_message(context, options)},
            ],
            "temperature": 0.2,
            "max_tokens": 256,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        last_exc: Optional[Exception] = None
        for attempt in range(self._max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout_s) as client:
                    resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                idx, reasoning = self._parse_response(content, len(options))

                elapsed_ms = (time.time() - start_time) * 1000
                self._request_count += 1
                self._total_latency_ms += elapsed_ms
                logger.debug(
                    "KimiK25Integration: option=%d latency=%.0fms attempt=%d",
                    idx, elapsed_ms, attempt,
                )
                return idx, reasoning

            except Exception as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # back-off

        self._error_count += 1
        logger.warning("KimiK25Integration: all attempts failed (%s) — heuristic fallback", last_exc)
        return self._heuristic_fallback(context, options)

    def get_stats(self) -> Dict[str, Any]:
        """Return runtime statistics for monitoring."""
        return {
            "enabled": self.enabled,
            "model": self._model,
            "endpoint": self.api_endpoint,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "avg_latency_ms": (
                self._total_latency_ms / self._request_count
                if self._request_count > 0 else 0.0
            ),
        }


class SwarmIntelligence:
    """
    Main class for distributed decision-making across mesh nodes.
    
    Provides:
    - Distributed decision making with configurable consensus
    - Integration with Raft, Paxos, and PBFT algorithms
    - Optional Kimi K2.5 LLM-based decisions
    - MAPE-K integration for autonomous decisions
    - Sub-100ms latency for most decisions
    
    Example:
        >>> config = SwarmIntelligenceConfig(
        ...     node_id="agent-1",
        ...     consensus_mode=ConsensusMode.RAFT,
        ... )
        >>> swarm = SwarmIntelligence(config)
        >>> await swarm.initialize()
        >>> 
        >>> context = DecisionContext(topic="routing", data={"path": "A->B"})
        >>> result = await swarm.make_decision(context, timeout_ms=100)
    """
    
    def __init__(
        self,
        node_id: str,
        peers: Optional[Set[str]] = None,
        consensus_mode: ConsensusMode = ConsensusMode.SIMPLE,
        default_timeout_ms: int = 100,
        enable_llm: bool = False,
        llm_endpoint: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[Any] = None,
    ):
        """
        Initialize SwarmIntelligence.
        
        Args:
            node_id: Unique identifier for this node
            peers: Set of peer node IDs
            consensus_mode: Default consensus algorithm to use
            default_timeout_ms: Default timeout for decisions
            enable_llm: Enable Kimi K2.5 LLM integration
            llm_endpoint: API endpoint for LLM
        """
        self.node_id = node_id
        self.peers = peers or set()
        self.consensus_mode = consensus_mode
        self.default_timeout_ms = default_timeout_ms
        
        # Initialize consensus manager
        self._consensus_manager = SwarmConsensusManager(
            node_id=node_id,
            default_mode=consensus_mode,
        )
        
        # Optional transport layer for real distributed communication
        self._transport: Optional["ConsensusTransport"] = None
        
        # Node tracking
        self._nodes: Dict[str, SwarmNodeInfo] = {}
        self._nodes[node_id] = SwarmNodeInfo(
            node_id=node_id,
            name=f"node-{node_id}",
            is_leader=False,
        )
        
        # Decision tracking
        self._pending_decisions: Dict[str, asyncio.Future] = {}
        self._decision_history: List[DecisionResult] = []
        
        # Consensus state
        self._status = ConsensusStatus.INITIALIZING
        self._leader_id: Optional[str] = None
        self._term = 0
        
        # Integrations
        self._mapek = MAPEKIntegration(
            self,
            event_bus=event_bus,
            event_project_root=event_project_root,
            policy_engine=policy_engine,
            require_policy=require_policy,
            source_agent=source_agent,
            spiffe_id=spiffe_id,
            did=did,
            wallet_address=wallet_address,
            safe_actuator=safe_actuator,
        )
        self._llm = KimiK25Integration(enabled=enable_llm, api_endpoint=llm_endpoint)
        
        # Callbacks
        self._on_decision: Optional[Callable[[DecisionResult], None]] = None
        self._on_leader_change: Optional[Callable[[str], None]] = None
        
        # Metrics
        self._total_decisions = 0
        self._successful_decisions = 0
        self._total_latency_ms = 0.0
        
        logger.info(f"SwarmIntelligence initialized for node {node_id}")
    
    async def initialize(self) -> None:
        """Initialize the swarm intelligence system."""
        # Add peers as nodes
        for peer_id in self.peers:
            self._nodes[peer_id] = SwarmNodeInfo(
                node_id=peer_id,
                name=f"node-{peer_id}",
            )
        
        # Initialize consensus manager agents
        for node_id, node_info in self._nodes.items():
            self._consensus_manager.add_agent(AgentInfo(
                agent_id=node_id,
                name=node_info.name,
                capabilities=node_info.capabilities,
                weight=node_info.weight,
            ))
        
        # Start consensus manager (initializes all consensus nodes)
        await self._consensus_manager.start()
        
        self._status = ConsensusStatus.READY
        logger.info(f"SwarmIntelligence initialized with {len(self._nodes)} nodes")
    
    async def shutdown(self) -> None:
        """Shutdown the swarm intelligence system."""
        await self._consensus_manager.stop()
        self._status = ConsensusStatus.OFFLINE
        logger.info(f"SwarmIntelligence shutdown for node {self.node_id}")
    
    def set_callbacks(
        self,
        on_decision: Optional[Callable[[DecisionResult], None]] = None,
        on_leader_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Set callbacks for events."""
        self._on_decision = on_decision
        self._on_leader_change = on_leader_change
    
    def add_node(self, node: SwarmNodeInfo) -> None:
        """Add a node to the swarm."""
        self._nodes[node.node_id] = node
        self._consensus_manager.add_agent(AgentInfo(
            agent_id=node.node_id,
            name=node.name,
            capabilities=node.capabilities,
            weight=node.weight,
        ))
        logger.info(f"Added node {node.node_id} to swarm")
    
    def remove_node(self, node_id: str) -> None:
        """Remove a node from the swarm."""
        if node_id in self._nodes:
            del self._nodes[node_id]
            self._consensus_manager.remove_agent(node_id)
            logger.info(f"Removed node {node_id} from swarm")
    
    def get_nodes(self) -> List[SwarmNodeInfo]:
        """Get all nodes in the swarm."""
        return list(self._nodes.values())
    
    def get_active_nodes(self) -> List[SwarmNodeInfo]:
        """Get active nodes in the swarm."""
        return [n for n in self._nodes.values() if n.is_active]
    
    async def make_decision(
        self,
        context: DecisionContext,
        timeout_ms: Optional[int] = None,
        consensus_mode: Optional[ConsensusMode] = None,
    ) -> DecisionResult:
        """
        Make a distributed decision.
        
        Args:
            context: Decision context with topic and data
            timeout_ms: Timeout in milliseconds (default: self.default_timeout_ms)
            consensus_mode: Consensus mode to use (default: self.consensus_mode)
        
        Returns:
            DecisionResult with the outcome
        
        Raises:
            asyncio.TimeoutError: If decision times out
        """
        start_time = time.time()
        timeout_ms = timeout_ms or self.default_timeout_ms
        consensus_mode = consensus_mode or self.consensus_mode
        
        decision_id = str(uuid.uuid4())[:8]
        
        # Prepare options
        options = context.options or [context.data]
        
        # Optional LLM enhancement
        llm_recommendation = None
        if self._llm.enabled and len(options) > 1:
            llm_recommendation = await self._llm.enhance_decision(context, options)
        
        try:
            # Use consensus manager to decide
            swarm_decision = await asyncio.wait_for(
                self._consensus_manager.decide(
                    topic=context.topic,
                    proposals=options,
                    mode=consensus_mode,
                ),
                timeout=timeout_ms / 1000.0,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            result = DecisionResult(
                decision_id=decision_id,
                approved=swarm_decision.success,
                context=context,
                consensus_mode=consensus_mode,
                latency_ms=latency_ms,
                participation_rate=1.0,  # Simplified
                winner=swarm_decision.winner,
                reason=f"Consensus reached via {consensus_mode.value}",
                metadata={
                    "swarm_decision": swarm_decision.to_dict(),
                    "llm_recommendation": llm_recommendation,
                },
            )
            
            self._total_decisions += 1
            if result.approved:
                self._successful_decisions += 1
            self._total_latency_ms += latency_ms
            
            self._decision_history.append(result)
            if len(self._decision_history) > 100:
                self._decision_history = self._decision_history[-100:]
            
            if self._on_decision:
                self._on_decision(result)
            
            logger.info(
                f"Decision {decision_id}: {'approved' if result.approved else 'rejected'} "
                f"in {latency_ms:.2f}ms"
            )
            
            return result
            
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            logger.warning(f"Decision {decision_id} timed out after {latency_ms:.2f}ms")
            
            result = DecisionResult(
                decision_id=decision_id,
                approved=False,
                context=context,
                consensus_mode=consensus_mode,
                latency_ms=latency_ms,
                reason="Decision timed out",
            )
            
            self._total_decisions += 1
            self._decision_history.append(result)
            
            return result
    
    async def propose_action(self, action: SwarmAction) -> DecisionResult:
        """
        Propose an action to the swarm.
        
        Args:
            action: The action to propose
        
        Returns:
            DecisionResult with the outcome
        """
        context = DecisionContext(
            topic=action.action_type,
            description=action.description,
            data=action.parameters,
            priority=action.priority,
        )
        
        return await self.make_decision(
            context=context,
            timeout_ms=action.timeout_ms,
        )
    
    async def get_consensus_status(self) -> ConsensusStatus:
        """
        Get the current consensus status.
        
        Returns:
            ConsensusStatus indicating system state
        """
        # Check node health
        active_nodes = len(self.get_active_nodes())
        total_nodes = len(self._nodes)
        
        if total_nodes == 0:
            return ConsensusStatus.OFFLINE
        
        if active_nodes < total_nodes // 2 + 1:
            return ConsensusStatus.DEGRADED
        
        if self._status == ConsensusStatus.READY:
            return ConsensusStatus.ACTIVE
        
        return self._status
    
    def get_leader_id(self) -> Optional[str]:
        """Get the current leader node ID."""
        return self._leader_id
    
    def is_leader(self) -> bool:
        """Check if this node is the leader."""
        return self._leader_id == self.node_id
    
    def get_decision_history(self, limit: int = 10) -> List[DecisionResult]:
        """Get recent decision history."""
        return self._decision_history[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get swarm intelligence statistics."""
        success_rate = (
            self._successful_decisions / self._total_decisions
            if self._total_decisions > 0 else 0
        )
        
        avg_latency = (
            self._total_latency_ms / self._total_decisions
            if self._total_decisions > 0 else 0
        )
        
        return {
            "node_id": self.node_id,
            "status": self._status.value,
            "consensus_mode": self.consensus_mode.value,
            "total_nodes": len(self._nodes),
            "active_nodes": len(self.get_active_nodes()),
            "total_decisions": self._total_decisions,
            "successful_decisions": self._successful_decisions,
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency,
            "llm_stats": self._llm.get_stats(),
            "mapek_stats": {
                "metrics_history": len(self._mapek._metrics_history),
                "action_history": len(self._mapek._action_history),
                "learning_data": self._mapek._learning_data,
            },
        }
    
    # ==================== MAPE-K Integration ====================
    
    async def run_mapek_cycle(self) -> Dict[str, Any]:
        """
        Run one MAPE-K cycle for autonomous decision-making.
        
        Returns:
            Dict with cycle results
        """
        cycle_start = time.time()
        
        # Monitor
        metrics = await self._mapek.monitor()
        
        # Analyze
        anomalies = self._mapek.analyze(metrics)
        
        # Plan
        actions = self._mapek.plan(anomalies)
        
        # Execute
        results = []
        for action in actions:
            result = await self._mapek.execute(action)
            self._mapek.learn(action, result)
            results.append(result)
        
        return {
            "duration_ms": (time.time() - cycle_start) * 1000,
            "metrics": metrics,
            "anomalies": anomalies,
            "actions_planned": len(actions),
            "actions_executed": len([r for r in results if r.get("success")]),
        }
    
    def get_mapek_integration(self) -> MAPEKIntegration:
        """Get the MAPE-K integration instance."""
        return self._mapek
    
    def get_llm_integration(self) -> KimiK25Integration:
        """Get the LLM integration instance."""
        return self._llm
    
    # ==================== Transport Integration ====================
    
    def set_transport(self, transport: "ConsensusTransport") -> None:
        """
        Set the transport layer for real distributed communication.
        
        This enables actual inter-process communication instead of
        simulated message passing.
        
        Args:
            transport: ConsensusTransport instance
        """
        self._transport = transport
        
        # Register message handlers
        self._transport.register_handler("consensus", self._handle_consensus_message)
        
        logger.info(f"Transport layer set for node {self.node_id}")
    
    def _handle_consensus_message(self, message: "ConsensusMessage") -> None:
        """Handle incoming consensus message from transport."""
        # Forward to consensus manager
        self._consensus_manager.receive_message(message.payload)
    
    def get_transport(self) -> Optional["ConsensusTransport"]:
        """Get the transport layer instance."""
        return self._transport
    
    # ==================== Consensus Protocol Methods ====================
    
    async def start_election(self) -> None:
        """Start a leader election (Raft-style)."""
        self._term += 1
        logger.info(f"Node {self.node_id} starting election for term {self._term}")
        
        # Simplified election - in production, use RaftNode
        # For now, just become leader if we have quorum
        active_nodes = len(self.get_active_nodes())
        quorum = len(self._nodes) // 2 + 1
        
        if active_nodes >= quorum:
            self._leader_id = self.node_id
            self._nodes[self.node_id].is_leader = True
            
            if self._on_leader_change:
                self._on_leader_change(self.node_id)
            
            logger.info(f"Node {self.node_id} became leader for term {self._term}")
    
    async def heartbeat(self) -> None:
        """Send heartbeat to maintain leadership."""
        if self.is_leader():
            # Update heartbeat timestamp
            self._nodes[self.node_id].last_heartbeat = datetime.utcnow()
    
    def receive_message(self, message: Dict[str, Any]) -> None:
        """Receive a consensus message from another node."""
        msg_type = message.get("type")
        
        if msg_type == "heartbeat":
            leader_id = message.get("leader_id")
            if leader_id:
                self._leader_id = leader_id
                if leader_id in self._nodes:
                    self._nodes[leader_id].is_leader = True
                    self._nodes[leader_id].last_heartbeat = datetime.utcnow()
        
        # Forward to consensus manager
        self._consensus_manager.receive_message(message)


async def create_swarm_intelligence(
    node_id: str,
    peers: Optional[Set[str]] = None,
    consensus_mode: ConsensusMode = ConsensusMode.SIMPLE,
    enable_llm: bool = False,
) -> SwarmIntelligence:
    """
    Create and initialize a SwarmIntelligence instance.
    
    Args:
        node_id: Unique identifier for this node
        peers: Set of peer node IDs
        consensus_mode: Consensus algorithm to use
        enable_llm: Enable LLM integration
    
    Returns:
        Initialized SwarmIntelligence instance
    """
    swarm = SwarmIntelligence(
        node_id=node_id,
        peers=peers,
        consensus_mode=consensus_mode,
        enable_llm=enable_llm,
    )
    await swarm.initialize()
    return swarm


# Export
__all__ = [
    "DecisionPriority",
    "DecisionType",
    "ConsensusStatus",
    "DecisionContext",
    "SwarmAction",
    "DecisionResult",
    "SwarmNodeInfo",
    "MAPEKIntegration",
    "KimiK25Integration",
    "SwarmIntelligence",
    "create_swarm_intelligence",
]
