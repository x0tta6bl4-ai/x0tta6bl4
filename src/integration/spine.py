"""Fail-closed integration spine for x0tta6bl4 control actions.

This module wires the local building blocks into one auditable path:
identity -> event bus -> policy engine -> safe actuator -> settlement/reward.
It does not submit transactions or mutate production by itself.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from src.coordination.events import EventBus, EventType

SAFE_ACTUATOR_EVIDENCE_METADATA_SCHEMA = "x0tta6bl4.safe_actuator.evidence_metadata.v2.0"


CLAIM_BOUNDARY = (
    "Local integration spine contract only. It proves fail-closed wiring "
    "between identity, event bus, policy engine, safe actuator, and "
    "settlement/reward adapters; it does not prove production rollout, "
    "customer traffic, or live on-chain settlement."
)


class PolicyEngineLike(Protocol):
    def evaluate(
        self,
        peer_spiffe_id: str,
        resource: Optional[str] = None,
        workload_type: Optional[str] = None,
    ) -> Any:
        ...


class RewardManagerLike(Protocol):
    def reward_relay(self, node_address: str, packets: int) -> Any:
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
class SafeActuatorResult:
    success: bool
    reason: str = ""
    simulated: bool = False


# Backward-compatible alias used by dao bridge, deployment modules
SafeActuatorEvidenceMetadata = SafeActuatorResult


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
        }


class SafeActuator:
    """Adapter that normalizes actuator execution and blocks missing executors."""

    def __init__(self, executor: Any = None):
        self.executor = executor

    def execute(self, action: str, context: Dict[str, Any]) -> SafeActuatorResult:
        if self.executor is None:
            return SafeActuatorResult(False, "safe actuator executor is not configured")

        try:
            if hasattr(self.executor, "execute"):
                raw = self.executor.execute(action, context)
            elif callable(self.executor):
                raw = self.executor(action, context)
            else:
                return SafeActuatorResult(False, "safe actuator executor is not callable")
        except Exception as exc:  # pragma: no cover - exact exception is caller-owned
            return SafeActuatorResult(False, f"safe actuator exception: {exc}")

        simulated = bool(getattr(self.executor, "was_simulated", False))
        if isinstance(raw, SafeActuatorResult):
            return raw
        if isinstance(raw, dict):
            return SafeActuatorResult(
                success=bool(raw.get("success", raw.get("ok", False))),
                reason=str(raw.get("reason", "")),
                simulated=bool(raw.get("simulated", simulated)),
            )
        return SafeActuatorResult(bool(raw), simulated=simulated)


class AsyncSafeActuator:
    """Async adapter that normalizes actuator execution and blocks missing executors."""

    def __init__(self, executor: Any = None):
        self.executor = executor

    async def execute(self, action: str, context: Dict[str, Any]) -> SafeActuatorResult:
        if self.executor is None:
            return SafeActuatorResult(False, "async safe actuator executor is not configured")

        try:
            if hasattr(self.executor, "execute"):
                raw = self.executor.execute(action, context)
            elif callable(self.executor):
                raw = self.executor(action, context)
            else:
                return SafeActuatorResult(False, "async safe actuator executor is not callable")
            if asyncio.iscoroutine(raw):
                raw = await raw
        except Exception as exc:  # pragma: no cover - exact exception is caller-owned
            return SafeActuatorResult(False, f"async safe actuator exception: {exc}")

        simulated = bool(getattr(self.executor, "was_simulated", False))
        if isinstance(raw, SafeActuatorResult):
            return raw
        if isinstance(raw, dict):
            return SafeActuatorResult(
                success=bool(raw.get("success", raw.get("ok", False))),
                reason=str(raw.get("reason", raw.get("error", "")) or ""),
                simulated=bool(raw.get("simulated", simulated)),
            )
        return SafeActuatorResult(bool(raw), simulated=simulated)


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

    def process(self, request: SpineRequest) -> SpineOutcome:
        event_ids: List[str] = []

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

        context = {
            "request_id": request.request_id,
            "identity": request.identity.to_dict(),
            "resource": request.resource,
            "workload_type": request.workload_type,
            "metadata": dict(request.metadata),
            "policy": {
                "allowed": True,
                "matched_rules": matched_rules,
                "reason": getattr(decision, "reason", None),
            },
        }
        action_result = self.actuator.execute(request.action, context)
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
            )

        settlement_recorded = False
        reward_address = request.reward_address or request.identity.wallet_address
        if request.reward_packets > 0:
            if not reward_address:
                event_ids.append(self._publish(EventType.TASK_BLOCKED, request, "settlement_missing_address"))
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
                )
            if self.reward_manager is None:
                event_ids.append(self._publish(EventType.TASK_BLOCKED, request, "settlement_missing_manager"))
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
                )
            try:
                reward_result = self.reward_manager.reward_relay(reward_address, request.reward_packets)
                settlement_error = _settlement_error(reward_result)
                if settlement_error:
                    event_ids.append(
                        self._publish(
                            EventType.TASK_FAILED,
                            request,
                            "settlement_failed",
                            {"error": settlement_error},
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
                    )
                settlement_recorded = True
            except Exception as exc:  # pragma: no cover - exact backend is caller-owned
                event_ids.append(
                    self._publish(
                        EventType.TASK_FAILED,
                        request,
                        "settlement_failed",
                        {"error": str(exc)},
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
                )

        event_ids.append(
            self._publish(
                EventType.PIPELINE_STAGE_END,
                request,
                "completed",
                {"settlement_recorded": settlement_recorded},
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
    ) -> SpineOutcome:
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
        )
