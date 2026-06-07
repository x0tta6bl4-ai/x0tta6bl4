"""Fail-closed integration spine for x0tta6bl4 control actions.

This module wires the local building blocks into one auditable path:
identity -> event bus -> policy engine -> safe actuator -> settlement/reward.
It does not submit transactions or mutate production by itself.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from src.core.agent_thinking import AgentThinkingCoach
from src.coordination.events import EventBus, EventType


CLAIM_BOUNDARY = (
    "Local integration spine contract only. It proves fail-closed wiring "
    "between identity, event bus, policy engine, safe actuator, and "
    "settlement/reward adapters; it does not prove production rollout, "
    "customer traffic, or live on-chain settlement."
)
SPINE_STRONG_CLAIM_IDS = (
    "production_readiness",
    "dataplane_delivery",
    "traffic_delivery",
    "customer_traffic",
    "dpi_bypass",
    "settlement_finality",
)
SAFE_ACTUATOR_EVIDENCE_METADATA_SCHEMA = (
    "x0tta6bl4.safe_actuator.evidence_metadata.v1"
)
SAFE_ACTUATOR_ADAPTER_CLAIM_BOUNDARY = (
    "SafeActuator adapter metadata proves only local adapter normalization for "
    "one guarded action result. It does not prove runtime execution beyond the "
    "local executor result, dataplane delivery, customer traffic, DPI bypass, "
    "external settlement finality, production SLOs, or production readiness."
)


def _safe_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


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


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


def _safe_context_summary(context: Any) -> Dict[str, Any]:
    if not isinstance(context, dict):
        return {"context_type": type(context).__name__, "context_key_count_bucket": "0"}
    return {
        "context_key_count_bucket": _safe_count_bucket(len(context)),
        "context_key_hashes": [_safe_hash(key) for key in sorted(context.keys())[:20]],
        "has_claim_gate": bool(context.get("claim_gate")),
        "has_cross_plane_claim_gate": bool(context.get("cross_plane_claim_gate")),
        "upstream_event_count_bucket": _safe_count_bucket(
            len(_safe_string_list(context.get("upstream_event_ids")))
        ),
    }


def _safe_identity_summary(identity: "SpineIdentity") -> Dict[str, Any]:
    return {
        "node_hash": _safe_hash(identity.node_id),
        "spiffe_hash": _safe_hash(identity.spiffe_id),
        "did_hash": _safe_hash(identity.did),
        "wallet_hash": _safe_hash(identity.wallet_address),
        "has_wallet": bool(identity.wallet_address),
    }


def _safe_request_summary(request: "SpineRequest") -> Dict[str, Any]:
    return {
        "request_hash": _safe_hash(request.request_id),
        "identity": _safe_identity_summary(request.identity),
        "action_hash": _safe_hash(request.action),
        "resource_hash": _safe_hash(request.resource),
        "workload_hash": _safe_hash(request.workload_type),
        "reward_packets_band": _safe_number_band(request.reward_packets),
        "reward_address_hash": _safe_hash(request.reward_address),
        "metadata_key_count_bucket": _safe_count_bucket(len(request.metadata)),
        "metadata_key_hashes": [
            _safe_hash(key) for key in sorted(request.metadata.keys())[:20]
        ],
    }


def _spine_claim_gate(
    *,
    status: str,
    policy_allowed: bool,
    action_executed: bool,
    settlement_recorded: bool,
    surface: str,
) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.integration_spine.claim_gate.v1",
        "surface": surface,
        "status": status,
        "local_spine_lifecycle_claim_allowed": True,
        "policy_decision_claim_allowed": policy_allowed,
        "local_actuator_execution_claim_allowed": action_executed,
        "local_reward_adapter_record_claim_allowed": settlement_recorded,
        "production_readiness_claim_allowed": False,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "blocked_claim_ids": list(SPINE_STRONG_CLAIM_IDS),
        "claim_boundary": (
            "IntegrationSpine evidence is local control-spine lifecycle evidence only. "
            "policy_allowed, action_executed, and settlement_recorded do not prove "
            "production readiness, customer/dataplane traffic delivery, DPI bypass, "
            "or external settlement finality."
        ),
    }


def _spine_cross_plane_claim_gate(*, surface: str) -> Dict[str, Any]:
    return {
        "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
        "surface": surface,
        "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
        "allowed": False,
        "requested_claim_ids": list(SPINE_STRONG_CLAIM_IDS),
        "blockers": ["integration_spine_local_contract_only"],
        "claim_boundary": (
            "The integration spine records local wiring and adapter outcomes. "
            "Any production, dataplane, traffic, DPI-bypass, or settlement-finality "
            "claim still needs the dedicated cross-plane proof gate and external evidence."
        ),
    }


class PolicyEngineLike(Protocol):
    def evaluate(
        self,
        peer_spiffe_id: str,
        resource: Optional[str] = None,
        workload_type: Optional[str] = None,
    ) -> Any:
        ...


class RewardManagerLike(Protocol):
    def reward_relay(
        self,
        node_address: str,
        packets: int,
        *,
        upstream_event_ids: Optional[List[str]] = None,
        upstream_source_agents: Optional[List[str]] = None,
        upstream_claim_gate: Optional[Dict[str, Any]] = None,
        upstream_cross_plane_claim_gate: Optional[Dict[str, Any]] = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class SpineIdentity:
    """Canonical identity passed through every spine stage."""

    node_id: str
    spiffe_id: str
    did: str = ""
    wallet_address: Optional[str] = None

    def validation_errors(self) -> List[str]:
        errors: List[str] = []
        if not self.node_id:
            errors.append("node_id is required")
        if not self.spiffe_id:
            errors.append("spiffe_id is required")
        elif not self.spiffe_id.startswith("spiffe://"):
            errors.append("spiffe_id must start with spiffe://")
        if self.did and not self.did.startswith("did:"):
            errors.append("did must start with did:")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "spiffe_id": self.spiffe_id,
            "did": self.did,
            "wallet_address": self.wallet_address,
        }


@dataclass(frozen=True)
class SpineRequest:
    """One action request flowing through the integration spine."""

    request_id: str
    identity: SpineIdentity
    action: str
    resource: str
    workload_type: Optional[str] = None
    reward_packets: int = 0
    reward_address: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SafeActuatorEvidenceMetadata:
    """Redacted claim/evidence metadata carried by guarded action results."""

    claim_gate: Dict[str, Any] = field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    source_agents: List[str] = field(default_factory=list)
    event_ids: List[str] = field(default_factory=list)
    claim_boundary: str = ""
    redacted: bool = True

    @classmethod
    def from_value(cls, value: Any) -> "SafeActuatorEvidenceMetadata":
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            return cls()

        envelope = value.get("safe_actuator_evidence") or value.get(
            "evidence_metadata"
        )
        raw = envelope if isinstance(envelope, dict) else value
        evidence = _safe_dict(raw.get("evidence"))
        claim_gate = _safe_dict(raw.get("claim_gate"))
        cross_plane_claim_gate = _safe_dict(raw.get("cross_plane_claim_gate"))

        event_ids = _safe_string_list(raw.get("event_ids")) or _safe_string_list(
            evidence.get("event_ids")
        )
        source_agents = _safe_string_list(
            raw.get("source_agents")
        ) or _safe_string_list(evidence.get("source_agents"))
        claim_boundary = str(
            raw.get("claim_boundary")
            or claim_gate.get("claim_boundary")
            or evidence.get("claim_boundary")
            or ""
        )

        return cls(
            claim_gate=claim_gate,
            cross_plane_claim_gate=cross_plane_claim_gate,
            evidence=evidence,
            source_agents=source_agents,
            event_ids=event_ids,
            claim_boundary=claim_boundary,
            redacted=raw.get("redacted") is not False,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": SAFE_ACTUATOR_EVIDENCE_METADATA_SCHEMA,
            "claim_gate": dict(self.claim_gate),
            "cross_plane_claim_gate": dict(self.cross_plane_claim_gate),
            "evidence": dict(self.evidence),
            "source_agents": list(self.source_agents),
            "event_ids": list(self.event_ids),
            "claim_boundary": self.claim_boundary,
            "redacted": self.redacted,
        }


@dataclass(frozen=True)
class SafeActuatorResult:
    success: bool
    reason: str = ""
    simulated: bool = False
    evidence_metadata: SafeActuatorEvidenceMetadata = field(
        default_factory=SafeActuatorEvidenceMetadata
    )


def _safe_actuator_context_keys(context: Any) -> List[str]:
    if not isinstance(context, dict):
        return []
    return sorted(str(key) for key in context.keys())[:50]


def _safe_actuator_adapter_evidence_metadata(
    *,
    surface: str,
    action: str,
    context: Dict[str, Any],
    success: bool,
    reason: str,
    simulated: bool,
    executor_configured: bool,
    executor_callable: bool,
    executor_invoked: bool,
) -> SafeActuatorEvidenceMetadata:
    blockers: List[str] = []
    if not executor_configured:
        blockers.append("executor_not_configured")
    if executor_configured and not executor_callable:
        blockers.append("executor_not_callable")
    if executor_invoked and not success:
        blockers.append("local_executor_result_not_successful")
    if simulated:
        blockers.append("local_executor_result_simulated")

    claim_gate = {
        "schema": "x0tta6bl4.safe_actuator.adapter_claim_gate.v1",
        "surface": surface,
        "safe_actuator_result_recorded": True,
        "local_safe_actuator_adapter_claim_allowed": True,
        "local_executor_configured": executor_configured,
        "local_executor_callable": executor_callable,
        "local_executor_invoked": executor_invoked,
        "local_executor_result_claim_allowed": executor_invoked and success,
        "safe_actuator_result_successful": success,
        "simulated_result": simulated,
        "safe_actuator_result_simulated": simulated,
        "dataplane_delivery_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "external_dpi_bypass_claim_allowed": False,
        "external_settlement_finality_claim_allowed": False,
        "revenue_recognition_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blocked_claim_ids": list(SPINE_STRONG_CLAIM_IDS),
        "blockers": blockers,
        "claim_boundary": SAFE_ACTUATOR_ADAPTER_CLAIM_BOUNDARY,
        "redacted": True,
    }
    return SafeActuatorEvidenceMetadata(
        claim_gate=claim_gate,
        cross_plane_claim_gate={
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "surface": surface,
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": list(SPINE_STRONG_CLAIM_IDS),
            "blockers": ["safe_actuator_adapter_local_metadata_only"],
            "claim_boundary": SAFE_ACTUATOR_ADAPTER_CLAIM_BOUNDARY,
        },
        evidence={
            "component": "src.integration.spine.SafeActuator",
            "surface": surface,
            "resource": str(context.get("resource", "")) if isinstance(context, dict) else "",
            "action_present": bool(str(action).strip()),
            "action_redacted": True,
            "context_keys": _safe_actuator_context_keys(context),
            "context_keys_total": len(_safe_actuator_context_keys(context)),
            "raw_context_values_redacted": True,
            "reason_present": bool(reason),
            "raw_reason_redacted": True,
            "raw_result_values_redacted": True,
            "local_result_success": success,
            "simulated": simulated,
            "executor_configured": executor_configured,
            "executor_callable": executor_callable,
            "executor_invoked": executor_invoked,
        },
        source_agents=[surface],
        claim_boundary=SAFE_ACTUATOR_ADAPTER_CLAIM_BOUNDARY,
        redacted=True,
    )


@dataclass(frozen=True)
class SpineOutcome:
    request_id: str
    status: str
    allowed: bool
    policy_allowed: bool
    action_executed: bool
    settlement_recorded: bool
    reason: str
    event_ids: List[str] = field(default_factory=list)
    matched_rules: List[str] = field(default_factory=list)
    reward_packets: int = 0
    reward_address: Optional[str] = None
    claim_boundary: str = CLAIM_BOUNDARY
    claim_gate: Dict[str, Any] = field(default_factory=dict)
    cross_plane_claim_gate: Dict[str, Any] = field(default_factory=dict)
    safe_actuator_evidence_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "allowed": self.allowed,
            "policy_allowed": self.policy_allowed,
            "action_executed": self.action_executed,
            "settlement_recorded": self.settlement_recorded,
            "reason": self.reason,
            "event_ids": list(self.event_ids),
            "matched_rules": list(self.matched_rules),
            "reward_packets": self.reward_packets,
            "reward_address": self.reward_address,
            "claim_boundary": self.claim_boundary,
            "claim_gate": dict(self.claim_gate),
            "cross_plane_claim_gate": dict(self.cross_plane_claim_gate),
            "safe_actuator_evidence_metadata": dict(
                self.safe_actuator_evidence_metadata
            ),
        }


class SafeActuator:
    """Adapter that normalizes actuator execution and blocks missing executors."""

    surface = "src.integration.spine.SafeActuator"

    def __init__(self, executor: Any = None):
        self.executor = executor
        self.thinking_coach = AgentThinkingCoach(
            agent_id="safe-actuator",
            role="security",
            capabilities=("ops", "zero-trust"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "safe_actuator_init",
                "goal": "Initialize guarded actuator adapter safely",
                "signals": {
                    "executor_configured": executor is not None,
                    "executor_callable": bool(
                        hasattr(executor, "execute") or callable(executor)
                    ),
                },
                "safety_boundary": (
                    "Keep raw actions, context values, executor output, and "
                    "exception text out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_actions": True,
                    "redact_context_values": True,
                    "redact_executor_output": True,
                    "redact_exception_text": True,
                    "preserve_fail_closed_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and local result flags.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def execute(self, action: str, context: Dict[str, Any]) -> SafeActuatorResult:
        if self.executor is None:
            reason = "safe actuator executor is not configured"
            self._record_thinking(
                "safe_actuator_blocked",
                "Block actuator execution without configured executor",
                {
                    "action_hash": _safe_hash(action),
                    "executor_configured": False,
                    "executor_callable": False,
                    **_safe_context_summary(context),
                },
            )
            return SafeActuatorResult(
                False,
                reason,
                evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                    surface=self.surface,
                    action=action,
                    context=context,
                    success=False,
                    reason=reason,
                    simulated=False,
                    executor_configured=False,
                    executor_callable=False,
                    executor_invoked=False,
                ),
            )

        try:
            if hasattr(self.executor, "execute"):
                raw = self.executor.execute(action, context)
            elif callable(self.executor):
                raw = self.executor(action, context)
            else:
                reason = "safe actuator executor is not callable"
                self._record_thinking(
                    "safe_actuator_blocked",
                    "Block actuator execution with non-callable executor",
                    {
                        "action_hash": _safe_hash(action),
                        "executor_configured": True,
                        "executor_callable": False,
                        **_safe_context_summary(context),
                    },
                )
                return SafeActuatorResult(
                    False,
                    reason,
                    evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                        surface=self.surface,
                        action=action,
                        context=context,
                        success=False,
                        reason=reason,
                        simulated=False,
                        executor_configured=True,
                        executor_callable=False,
                        executor_invoked=False,
                    ),
                )
        except Exception as exc:  # pragma: no cover - exact exception is caller-owned
            reason = f"safe actuator exception: {exc}"
            self._record_thinking(
                "safe_actuator_exception",
                "Fail closed on actuator exception safely",
                {
                    "action_hash": _safe_hash(action),
                    "executor_configured": True,
                    "executor_callable": True,
                    "error_type": type(exc).__name__,
                    **_safe_context_summary(context),
                },
            )
            return SafeActuatorResult(
                False,
                reason,
                evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                    surface=self.surface,
                    action=action,
                    context=context,
                    success=False,
                    reason=reason,
                    simulated=False,
                    executor_configured=True,
                    executor_callable=True,
                    executor_invoked=True,
                ),
            )

        simulated = bool(getattr(self.executor, "was_simulated", False))
        if isinstance(raw, SafeActuatorResult):
            self._record_thinking(
                "safe_actuator_result_normalized",
                "Normalize direct SafeActuatorResult safely",
                {
                    "action_hash": _safe_hash(action),
                    "success": raw.success,
                    "simulated": raw.simulated,
                    **_safe_context_summary(context),
                },
            )
            return raw
        if isinstance(raw, dict):
            success = bool(raw.get("success", raw.get("ok", False)))
            reason = str(raw.get("reason", ""))
            simulated_result = bool(raw.get("simulated", simulated))
            self._record_thinking(
                "safe_actuator_result_normalized",
                "Normalize dict actuator result safely",
                {
                    "action_hash": _safe_hash(action),
                    "success": success,
                    "simulated": simulated_result,
                    "result_key_count_bucket": _safe_count_bucket(len(raw)),
                    "result_key_hashes": [
                        _safe_hash(key) for key in sorted(raw.keys())[:20]
                    ],
                    **_safe_context_summary(context),
                },
            )
            return SafeActuatorResult(
                success=success,
                reason=reason,
                simulated=simulated_result,
                evidence_metadata=SafeActuatorEvidenceMetadata.from_value(raw),
            )
        success = bool(raw)
        self._record_thinking(
            "safe_actuator_executed",
            "Execute guarded actuator safely",
            {
                "action_hash": _safe_hash(action),
                "success": success,
                "simulated": simulated,
                **_safe_context_summary(context),
            },
        )
        return SafeActuatorResult(
            success,
            simulated=simulated,
            evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                surface=self.surface,
                action=action,
                context=context,
                success=success,
                reason="",
                simulated=simulated,
                executor_configured=True,
                executor_callable=True,
                executor_invoked=True,
            ),
        )


class AsyncSafeActuator:
    """Async adapter that normalizes actuator execution and blocks missing executors."""

    surface = "src.integration.spine.AsyncSafeActuator"

    def __init__(self, executor: Any = None):
        self.executor = executor
        self.thinking_coach = AgentThinkingCoach(
            agent_id="async-safe-actuator",
            role="security",
            capabilities=("ops", "zero-trust"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "async_safe_actuator_init",
                "goal": "Initialize async guarded actuator adapter safely",
                "signals": {
                    "executor_configured": executor is not None,
                    "executor_callable": bool(
                        hasattr(executor, "execute") or callable(executor)
                    ),
                },
                "safety_boundary": (
                    "Keep raw actions, context values, executor output, and "
                    "exception text out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_actions": True,
                    "redact_context_values": True,
                    "redact_executor_output": True,
                    "redact_exception_text": True,
                    "preserve_fail_closed_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and local result flags.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    async def execute(self, action: str, context: Dict[str, Any]) -> SafeActuatorResult:
        if self.executor is None:
            reason = "async safe actuator executor is not configured"
            self._record_thinking(
                "async_safe_actuator_blocked",
                "Block async actuator execution without configured executor",
                {
                    "action_hash": _safe_hash(action),
                    "executor_configured": False,
                    "executor_callable": False,
                    **_safe_context_summary(context),
                },
            )
            return SafeActuatorResult(
                False,
                reason,
                evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                    surface=self.surface,
                    action=action,
                    context=context,
                    success=False,
                    reason=reason,
                    simulated=False,
                    executor_configured=False,
                    executor_callable=False,
                    executor_invoked=False,
                ),
            )

        try:
            if hasattr(self.executor, "execute"):
                raw = self.executor.execute(action, context)
            elif callable(self.executor):
                raw = self.executor(action, context)
            else:
                reason = "async safe actuator executor is not callable"
                self._record_thinking(
                    "async_safe_actuator_blocked",
                    "Block async actuator execution with non-callable executor",
                    {
                        "action_hash": _safe_hash(action),
                        "executor_configured": True,
                        "executor_callable": False,
                        **_safe_context_summary(context),
                    },
                )
                return SafeActuatorResult(
                    False,
                    reason,
                    evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                        surface=self.surface,
                        action=action,
                        context=context,
                        success=False,
                        reason=reason,
                        simulated=False,
                        executor_configured=True,
                        executor_callable=False,
                        executor_invoked=False,
                    ),
                )
            if asyncio.iscoroutine(raw):
                raw = await raw
        except Exception as exc:  # pragma: no cover - exact exception is caller-owned
            reason = f"async safe actuator exception: {exc}"
            self._record_thinking(
                "async_safe_actuator_exception",
                "Fail closed on async actuator exception safely",
                {
                    "action_hash": _safe_hash(action),
                    "executor_configured": True,
                    "executor_callable": True,
                    "error_type": type(exc).__name__,
                    **_safe_context_summary(context),
                },
            )
            return SafeActuatorResult(
                False,
                reason,
                evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                    surface=self.surface,
                    action=action,
                    context=context,
                    success=False,
                    reason=reason,
                    simulated=False,
                    executor_configured=True,
                    executor_callable=True,
                    executor_invoked=True,
                ),
            )

        simulated = bool(getattr(self.executor, "was_simulated", False))
        if isinstance(raw, SafeActuatorResult):
            self._record_thinking(
                "async_safe_actuator_result_normalized",
                "Normalize direct async SafeActuatorResult safely",
                {
                    "action_hash": _safe_hash(action),
                    "success": raw.success,
                    "simulated": raw.simulated,
                    **_safe_context_summary(context),
                },
            )
            return raw
        if isinstance(raw, dict):
            success = bool(raw.get("success", raw.get("ok", False)))
            reason = str(raw.get("reason", raw.get("error", "")) or "")
            simulated_result = bool(raw.get("simulated", simulated))
            self._record_thinking(
                "async_safe_actuator_result_normalized",
                "Normalize async dict actuator result safely",
                {
                    "action_hash": _safe_hash(action),
                    "success": success,
                    "simulated": simulated_result,
                    "result_key_count_bucket": _safe_count_bucket(len(raw)),
                    "result_key_hashes": [
                        _safe_hash(key) for key in sorted(raw.keys())[:20]
                    ],
                    **_safe_context_summary(context),
                },
            )
            return SafeActuatorResult(
                success=success,
                reason=reason,
                simulated=simulated_result,
                evidence_metadata=SafeActuatorEvidenceMetadata.from_value(raw),
            )
        success = bool(raw)
        self._record_thinking(
            "async_safe_actuator_executed",
            "Execute async guarded actuator safely",
            {
                "action_hash": _safe_hash(action),
                "success": success,
                "simulated": simulated,
                **_safe_context_summary(context),
            },
        )
        return SafeActuatorResult(
            success,
            simulated=simulated,
            evidence_metadata=_safe_actuator_adapter_evidence_metadata(
                surface=self.surface,
                action=action,
                context=context,
                success=success,
                reason="",
                simulated=simulated,
                executor_configured=True,
                executor_callable=True,
                executor_invoked=True,
            ),
        )


def _flag_true(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _settlement_error(raw: Any) -> str:
    if raw is None:
        return ""
    if raw is False:
        return "reward manager returned false"
    if isinstance(raw, dict):
        for key in ("simulated", "dry_run", "dryRun", "fake", "mocked"):
            if key in raw and _flag_true(raw.get(key)):
                return f"reward manager returned {key}=true"
        for key in ("success", "ok", "settlement_recorded"):
            if key in raw and raw.get(key) is False:
                return f"reward manager returned {key}=false"
        status = str(raw.get("status", "")).strip().lower()
        if status in {
            "failed",
            "error",
            "blocked",
            "denied",
            "rejected",
            "simulated",
            "dry_run",
            "dry-run",
            "mocked",
            "fake",
        }:
            return f"reward manager returned status={status}"
        mode = str(raw.get("mode", "")).strip().lower()
        if mode in {"simulated", "simulation", "dry_run", "dry-run", "mock", "fake"}:
            return f"reward manager returned mode={mode}"
        for key in ("submitted_transaction", "transaction_submitted", "receipt_verified", "live_rpc_verified"):
            if key in raw and raw.get(key) is False:
                return f"reward manager returned {key}=false"
    for attr in ("simulated", "dry_run", "fake", "mocked"):
        if hasattr(raw, attr) and _flag_true(getattr(raw, attr)):
            return f"reward manager returned {attr}=true"
    for attr in ("success", "ok", "settlement_recorded"):
        if hasattr(raw, attr) and getattr(raw, attr) is False:
            return f"reward manager returned {attr}=false"
    status = str(getattr(raw, "status", "")).strip().lower()
    if status in {
        "failed",
        "error",
        "blocked",
        "denied",
        "rejected",
        "simulated",
        "dry_run",
        "dry-run",
        "mocked",
        "fake",
    }:
        return f"reward manager returned status={status}"
    mode = str(getattr(raw, "mode", "")).strip().lower()
    if mode in {"simulated", "simulation", "dry_run", "dry-run", "mock", "fake"}:
        return f"reward manager returned mode={mode}"
    for attr in ("submitted_transaction", "transaction_submitted", "receipt_verified", "live_rpc_verified"):
        if hasattr(raw, attr) and getattr(raw, attr) is False:
            return f"reward manager returned {attr}=false"
    return ""


class IntegrationSpine:
    """Auditable fail-closed pipeline across the required project layers."""

    def __init__(
        self,
        *,
        event_bus: EventBus,
        policy_engine: Optional[PolicyEngineLike],
        actuator: Optional[SafeActuator] = None,
        reward_manager: Optional[RewardManagerLike] = None,
        source_agent: str = "integration-spine",
    ):
        self.event_bus = event_bus
        self.policy_engine = policy_engine
        self.actuator = actuator or SafeActuator()
        self.reward_manager = reward_manager
        self.source_agent = source_agent
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"integration-spine:{_safe_hash(source_agent)}",
            role="coordinator",
            capabilities=("security", "zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "integration_spine_init",
                "goal": "Initialize fail-closed integration spine safely",
                "signals": {
                    "source_agent_hash": _safe_hash(source_agent),
                    "policy_engine_configured": policy_engine is not None,
                    "actuator_configured": self.actuator is not None,
                    "reward_manager_configured": reward_manager is not None,
                },
                "safety_boundary": (
                    "Keep raw request ids, identities, actions, resources, "
                    "metadata, reward addresses, policy reasons, and event ids "
                    "out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_request_ids": True,
                    "redact_identities": True,
                    "redact_actions": True,
                    "redact_resources": True,
                    "redact_metadata_values": True,
                    "redact_reward_addresses": True,
                    "redact_policy_reasons": True,
                    "redact_event_ids": True,
                    "preserve_fail_closed_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, statuses, and claim flags.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def process(self, request: SpineRequest) -> SpineOutcome:
        event_ids: List[str] = []
        self._record_thinking(
            "integration_spine_request_received",
            "Receive integration spine request safely",
            {
                **_safe_request_summary(request),
                "policy_engine_configured": self.policy_engine is not None,
                "reward_manager_configured": self.reward_manager is not None,
            },
        )

        identity_errors = request.identity.validation_errors()
        if identity_errors:
            event_ids.append(
                self._publish(
                    EventType.TASK_BLOCKED,
                    request,
                    "identity_rejected",
                    {"errors": identity_errors},
                )
            )
            return self._outcome(
                request,
                status="IDENTITY_REJECTED",
                allowed=False,
                policy_allowed=False,
                action_executed=False,
                settlement_recorded=False,
                reason="; ".join(identity_errors),
                event_ids=event_ids,
            )

        event_ids.append(self._publish(EventType.COORDINATION_REQUEST, request, "received"))

        if self.policy_engine is None:
            event_ids.append(self._publish(EventType.TASK_BLOCKED, request, "policy_missing"))
            return self._outcome(
                request,
                status="POLICY_ENGINE_MISSING",
                allowed=False,
                policy_allowed=False,
                action_executed=False,
                settlement_recorded=False,
                reason="policy engine is not configured",
                event_ids=event_ids,
            )

        try:
            decision = self.policy_engine.evaluate(
                request.identity.spiffe_id,
                resource=request.resource,
                workload_type=request.workload_type,
            )
        except Exception as exc:
            event_ids.append(
                self._publish(
                    EventType.TASK_BLOCKED,
                    request,
                    "policy_error",
                    {"error": str(exc)},
                )
            )
            return self._outcome(
                request,
                status="POLICY_ERROR",
                allowed=False,
                policy_allowed=False,
                action_executed=False,
                settlement_recorded=False,
                reason=f"policy evaluation failed: {exc}",
                event_ids=event_ids,
            )

        policy_allowed = bool(getattr(decision, "allowed", False))
        matched_rules = list(getattr(decision, "matched_rules", []) or [])
        if not policy_allowed:
            reason = str(getattr(decision, "reason", "policy denied request"))
            event_ids.append(
                self._publish(
                    EventType.TASK_BLOCKED,
                    request,
                    "policy_denied",
                    {"reason": reason, "matched_rules": matched_rules},
                )
            )
            return self._outcome(
                request,
                status="POLICY_DENIED",
                allowed=False,
                policy_allowed=False,
                action_executed=False,
                settlement_recorded=False,
                reason=reason,
                event_ids=event_ids,
                matched_rules=matched_rules,
            )

        event_ids.append(
            self._publish(
                EventType.PIPELINE_STAGE_START,
                request,
                "actuator_start",
                {"matched_rules": matched_rules},
            )
        )

        actuator_claim_gate = _spine_claim_gate(
            status="actuator_context",
            policy_allowed=True,
            action_executed=False,
            settlement_recorded=False,
            surface="integration_spine.actuator_context",
        )
        actuator_cross_plane_claim_gate = _spine_cross_plane_claim_gate(
            surface="integration_spine.actuator_context"
        )
        context = {
            "request_id": request.request_id,
            "identity": request.identity.to_dict(),
            "resource": request.resource,
            "workload_type": request.workload_type,
            "metadata": dict(request.metadata),
            "upstream_event_ids": list(event_ids),
            "upstream_source_agents": [self.source_agent],
            "claim_boundary": CLAIM_BOUNDARY,
            "claim_gate": actuator_claim_gate,
            "cross_plane_claim_gate": actuator_cross_plane_claim_gate,
            "policy": {
                "allowed": True,
                "matched_rules": matched_rules,
                "reason": getattr(decision, "reason", None),
            },
        }
        action_result = self.actuator.execute(request.action, context)
        safe_actuator_evidence_metadata = action_result.evidence_metadata.to_dict()
        if not action_result.success or action_result.simulated:
            status = "ACTUATOR_SIMULATED" if action_result.simulated else "ACTUATOR_FAILED"
            event_ids.append(
                self._publish(
                    EventType.TASK_FAILED,
                    request,
                    "actuator_failed",
                    {
                        "status": status,
                        "reason": action_result.reason,
                        "simulated": action_result.simulated,
                        "safe_actuator": True,
                        "safe_actuator_evidence_metadata": safe_actuator_evidence_metadata,
                    },
                )
            )
            return self._outcome(
                request,
                status=status,
                allowed=False,
                policy_allowed=True,
                action_executed=False,
                settlement_recorded=False,
                reason=action_result.reason or status.lower(),
                event_ids=event_ids,
                matched_rules=matched_rules,
                safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
            )

        settlement_recorded = False
        reward_address = request.reward_address or request.identity.wallet_address
        if request.reward_packets > 0:
            if not reward_address:
                event_ids.append(
                    self._publish(
                        EventType.TASK_BLOCKED,
                        request,
                        "settlement_missing_address",
                        {
                            "safe_actuator": True,
                            "safe_actuator_evidence_metadata": safe_actuator_evidence_metadata,
                        },
                    )
                )
                return self._outcome(
                    request,
                    status="SETTLEMENT_BLOCKED_MISSING_ADDRESS",
                    allowed=False,
                    policy_allowed=True,
                    action_executed=True,
                    settlement_recorded=False,
                    reason="reward address is required when reward_packets > 0",
                    event_ids=event_ids,
                    matched_rules=matched_rules,
                    safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
                )
            if self.reward_manager is None:
                event_ids.append(
                    self._publish(
                        EventType.TASK_BLOCKED,
                        request,
                        "settlement_missing_manager",
                        {
                            "safe_actuator": True,
                            "safe_actuator_evidence_metadata": safe_actuator_evidence_metadata,
                        },
                    )
                )
                return self._outcome(
                    request,
                    status="SETTLEMENT_BLOCKED_NOT_CONFIGURED",
                    allowed=False,
                    policy_allowed=True,
                    action_executed=True,
                    settlement_recorded=False,
                    reason="reward manager is not configured",
                    event_ids=event_ids,
                    matched_rules=matched_rules,
                    reward_address=reward_address,
                    safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
                )
            try:
                reward_claim_gate = _spine_claim_gate(
                    status="reward_context",
                    policy_allowed=True,
                    action_executed=True,
                    settlement_recorded=False,
                    surface="integration_spine.reward_context",
                )
                reward_cross_plane_claim_gate = _spine_cross_plane_claim_gate(
                    surface="integration_spine.reward_context"
                )
                try:
                    reward_result = self.reward_manager.reward_relay(
                        reward_address,
                        request.reward_packets,
                        upstream_event_ids=list(event_ids),
                        upstream_source_agents=[self.source_agent],
                        upstream_claim_gate=reward_claim_gate,
                        upstream_cross_plane_claim_gate=reward_cross_plane_claim_gate,
                    )
                except TypeError as exc:
                    if "unexpected keyword argument" not in str(exc):
                        raise
                    try:
                        reward_result = self.reward_manager.reward_relay(
                            reward_address,
                            request.reward_packets,
                            upstream_event_ids=list(event_ids),
                            upstream_source_agents=[self.source_agent],
                        )
                    except TypeError as fallback_exc:
                        if "unexpected keyword argument" not in str(fallback_exc):
                            raise
                        reward_result = self.reward_manager.reward_relay(
                            reward_address,
                            request.reward_packets,
                        )
                settlement_error = _settlement_error(reward_result)
                if settlement_error:
                    event_ids.append(
                        self._publish(
                            EventType.TASK_FAILED,
                            request,
                            "settlement_failed",
                            {
                                "error": settlement_error,
                                "safe_actuator": True,
                                "safe_actuator_evidence_metadata": safe_actuator_evidence_metadata,
                            },
                        )
                    )
                    return self._outcome(
                        request,
                        status="SETTLEMENT_FAILED",
                        allowed=False,
                        policy_allowed=True,
                        action_executed=True,
                        settlement_recorded=False,
                        reason=settlement_error,
                        event_ids=event_ids,
                        matched_rules=matched_rules,
                        reward_address=reward_address,
                        safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
                    )
                settlement_recorded = True
            except Exception as exc:  # pragma: no cover - exact backend is caller-owned
                event_ids.append(
                        self._publish(
                            EventType.TASK_FAILED,
                            request,
                            "settlement_failed",
                            {
                                "error": str(exc),
                                "safe_actuator": True,
                                "safe_actuator_evidence_metadata": safe_actuator_evidence_metadata,
                            },
                        )
                    )
                return self._outcome(
                    request,
                    status="SETTLEMENT_FAILED",
                    allowed=False,
                    policy_allowed=True,
                    action_executed=True,
                    settlement_recorded=False,
                    reason=f"settlement failed: {exc}",
                    event_ids=event_ids,
                    matched_rules=matched_rules,
                    reward_address=reward_address,
                    safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
                )

        event_ids.append(
            self._publish(
                EventType.PIPELINE_STAGE_END,
                request,
                "completed",
                {
                    "settlement_recorded": settlement_recorded,
                    "safe_actuator": True,
                    "safe_actuator_evidence_metadata": safe_actuator_evidence_metadata,
                },
            )
        )
        return self._outcome(
            request,
            status="COMPLETED",
            allowed=True,
            policy_allowed=True,
            action_executed=True,
            settlement_recorded=settlement_recorded,
            reason="request completed through integration spine",
            event_ids=event_ids,
            matched_rules=matched_rules,
            reward_address=reward_address,
            safe_actuator_evidence_metadata=safe_actuator_evidence_metadata,
        )

    def _publish(
        self,
        event_type: EventType,
        request: SpineRequest,
        stage: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> str:
        data = {
            "request_id": request.request_id,
            "stage": stage,
            "identity": request.identity.to_dict(),
            "action": request.action,
            "resource": request.resource,
            "workload_type": request.workload_type,
            "reward_packets": request.reward_packets,
            "claim_boundary": CLAIM_BOUNDARY,
            "claim_gate": _spine_claim_gate(
                status=stage,
                policy_allowed=False,
                action_executed=False,
                settlement_recorded=False,
                surface="integration_spine.event",
            ),
            "cross_plane_claim_gate": _spine_cross_plane_claim_gate(
                surface="integration_spine.event"
            ),
        }
        if extra:
            data.update(extra)
        event = self.event_bus.publish(event_type, self.source_agent, data)
        return event.event_id

    def _outcome(
        self,
        request: SpineRequest,
        *,
        status: str,
        allowed: bool,
        policy_allowed: bool,
        action_executed: bool,
        settlement_recorded: bool,
        reason: str,
        event_ids: List[str],
        matched_rules: Optional[List[str]] = None,
        reward_address: Optional[str] = None,
        safe_actuator_evidence_metadata: Optional[Dict[str, Any]] = None,
    ) -> SpineOutcome:
        self._record_thinking(
            "integration_spine_outcome",
            "Finalize integration spine decision safely",
            {
                **_safe_request_summary(request),
                "status": status,
                "allowed": allowed,
                "policy_allowed": policy_allowed,
                "action_executed": action_executed,
                "settlement_recorded": settlement_recorded,
                "reason_present": bool(reason),
                "reason_hash": _safe_hash(reason),
                "event_count_bucket": _safe_count_bucket(len(event_ids)),
                "event_id_hashes": [_safe_hash(event_id) for event_id in event_ids[:20]],
                "matched_rule_count_bucket": _safe_count_bucket(
                    len(matched_rules or [])
                ),
                "matched_rule_hashes": [
                    _safe_hash(rule) for rule in (matched_rules or [])[:20]
                ],
                "reward_address_hash": _safe_hash(
                    reward_address
                    or request.reward_address
                    or request.identity.wallet_address
                ),
                "has_safe_actuator_evidence": bool(safe_actuator_evidence_metadata),
                "claim_gate_local_only": True,
                "cross_plane_claims_blocked": True,
            },
        )
        return SpineOutcome(
            request_id=request.request_id,
            status=status,
            allowed=allowed,
            policy_allowed=policy_allowed,
            action_executed=action_executed,
            settlement_recorded=settlement_recorded,
            reason=reason,
            event_ids=event_ids,
            matched_rules=matched_rules or [],
            reward_packets=request.reward_packets,
            reward_address=reward_address or request.reward_address or request.identity.wallet_address,
            claim_gate=_spine_claim_gate(
                status=status,
                policy_allowed=policy_allowed,
                action_executed=action_executed,
                settlement_recorded=settlement_recorded,
                surface="integration_spine.outcome",
            ),
            cross_plane_claim_gate=_spine_cross_plane_claim_gate(
                surface="integration_spine.outcome"
            ),
            safe_actuator_evidence_metadata=safe_actuator_evidence_metadata or {},
        )
