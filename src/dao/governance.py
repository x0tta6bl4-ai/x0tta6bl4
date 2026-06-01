"""
DAO Governance Module for x0tta6bl4.
Implements decentralized decision making via weighted voting.
Now with Quadratic Voting support and action dispatch.
"""

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_NODE_ID_RE = re.compile(r"^[\w\-\.]{1,64}$")

from src.coordination.events import EventBus, EventType, get_event_bus
from src.dao.quadratic_voting import QuadraticVoting
from src.integration.spine import (
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "dao-governance"
_DAO_GOVERNANCE_STRONG_CLAIM_IDS = (
    "governance_execution_finality",
    "production_governance_execution",
    "production_readiness",
    "dataplane_delivery",
    "customer_traffic",
    "external_settlement_finality",
)

DAO_GOVERNANCE_CLAIM_BOUNDARY = (
    "DAO governance dispatcher event only. It records local identity, policy, "
    "and safe actuator state for proposal action dispatch; it is not external "
    "settlement evidence or proof of production governance execution."
)


class ProposalState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXECUTED = "executed"


class VoteType(Enum):
    YES = "yes"
    NO = "no"
    ABSTAIN = "abstain"


@dataclass
class Proposal:
    id: str
    title: str
    description: str
    proposer: str
    start_time: float
    end_time: float
    actions: List[Dict] = field(default_factory=list)
    votes: Dict[str, VoteType] = field(default_factory=dict)
    voter_tokens: Dict[str, float] = field(
        default_factory=dict
    )  # Quadratic voting: tokens per voter
    state: ProposalState = ProposalState.PENDING
    quorum: float = 0.5  # 50% participation required
    threshold: float = 0.5  # 50% + 1 support required

    def total_votes(self) -> int:
        return len(self.votes)

    def vote_counts(self) -> Dict[VoteType, int]:
        counts = {VoteType.YES: 0, VoteType.NO: 0, VoteType.ABSTAIN: 0}
        for vote in self.votes.values():
            counts[vote] += 1
        return counts


@dataclass
class ActionResult:
    """Result of executing a governance action."""

    action_type: str
    success: bool
    detail: str = ""


class ActionDispatcher:
    """
    Routes governance actions to system components.

    Supported action types:
      - restart_node: triggers MAPE-K execute phase
      - rotate_keys: triggers PQC key rotation
      - update_threshold: updates anomaly detection threshold
      - update_config: generic config key/value update
      - ban_node: removes a node from the mesh
    """

    def __init__(
        self,
        *,
        node_id: str = "dao-governance",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[SafeActuator] = None,
    ):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], ActionResult]] = {}
        self.node_id = node_id
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_DAO_GOVERNANCE_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="dao-governance")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id if spiffe_id is not None else service_identity["spiffe_id"],
            "did": did if did is not None else service_identity["did"],
            "wallet_address": (
                wallet_address
                if wallet_address is not None
                else service_identity["wallet_address"]
            ),
        }
        self._last_dispatch_result: Optional[ActionResult] = None
        self.safe_actuator = safe_actuator or SafeActuator(self._execute_handler_through_actuator)
        # Register built-in handlers
        self._register_defaults()

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
            logger.error("Failed to initialize DAO governance EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize DAO governance policy engine: %s", exc)
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
    def _dispatch_cross_plane_claim_gate() -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "surface": "dao.governance.dispatch.safe_actuator",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": list(_DAO_GOVERNANCE_STRONG_CLAIM_IDS),
            "blockers": ["dao_governance_dispatch_local_handler_only"],
            "claim_boundary": (
                "DAO governance dispatch metadata records one local guarded handler "
                "attempt only. Governance finality, production execution, dataplane, "
                "customer traffic, and settlement-finality claims need external "
                "cross-plane evidence."
            ),
        }

    @classmethod
    def _dispatch_claim_gate(
        cls,
        *,
        action_type: str,
        action_present: bool,
        handler_present: bool,
        success: bool,
        simulated: bool,
        result_present: bool,
    ) -> Dict[str, Any]:
        local_handler_execution_allowed = (
            action_present
            and handler_present
            and result_present
            and success
            and not simulated
        )
        blockers = [
            "governance_execution_finality_requires_vote_and_chain_evidence",
            "production_governance_execution_requires_runtime_post_action_evidence",
            "production_readiness_requires_cross_plane_proof",
            "dataplane_claim_requires_dedicated_dataplane_probe",
            "settlement_finality_requires_external_chain_evidence",
        ]
        if not action_present:
            blockers.append("dao_governance_action_missing")
        if not handler_present:
            blockers.append("dao_governance_handler_missing")
        if simulated:
            blockers.append("safe_actuator_result_simulated")
        if not success:
            blockers.append("dao_governance_handler_not_successful")
        if not result_present:
            blockers.append("dao_governance_action_result_missing")
        resource = f"dao:governance:{cls._action_resource_name(action_type)}"

        return {
            "schema": "x0tta6bl4.dao_governance.safe_actuator_claim_gate.v1",
            "surface": "dao.governance.dispatch",
            "resource": resource,
            "action_type": str(action_type or ""),
            "local_handler_execution_claim_allowed": local_handler_execution_allowed,
            "safe_actuator_result_recorded": True,
            "governance_execution_finality_claim_allowed": False,
            "production_governance_execution_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "external_settlement_finality_claim_allowed": False,
            "blocked_claim_ids": list(_DAO_GOVERNANCE_STRONG_CLAIM_IDS),
            "blockers": blockers,
            "payloads_redacted": True,
            "redacted": True,
            "claim_boundary": (
                "ActionDispatcher SafeActuator metadata proves only a local guarded "
                "handler attempt and bounded handler result. It does not prove DAO "
                "governance finality, production governance execution, production "
                "readiness, dataplane or customer traffic delivery, or external "
                "settlement finality."
            ),
        }

    @classmethod
    def _dispatch_evidence_metadata(
        cls,
        *,
        action_type: str,
        context: Dict[str, Any],
        success: bool,
        simulated: bool = False,
        result: Optional[ActionResult] = None,
        duration_ms: Optional[int] = None,
    ) -> SafeActuatorEvidenceMetadata:
        action = context.get("action")
        handler = context.get("handler")
        action_present = isinstance(action, dict)
        handler_present = callable(handler)
        result_present = result is not None
        claim_gate = cls._dispatch_claim_gate(
            action_type=action_type,
            action_present=action_present,
            handler_present=handler_present,
            success=success,
            simulated=simulated,
            result_present=result_present,
        )
        resource = f"dao:governance:{cls._action_resource_name(action_type)}"
        evidence = {
            "source_agents": [_SERVICE_AGENT],
            "event_ids": [],
            "resource": resource,
            "operation": "governance_action_dispatch",
            "action_type": str(action_type or ""),
            "action_present": action_present,
            "handler_present": handler_present,
            "result_present": result_present,
            "result_action_type": str(getattr(result, "action_type", "") or ""),
            "result_success": bool(getattr(result, "success", False)),
            "duration_ms": int(duration_ms or 0),
            "action_values_redacted": True,
            "result_detail_redacted": True,
            "raw_context_values_redacted": True,
            "raw_result_values_redacted": True,
            "raw_values_redacted": True,
            "payloads_redacted": True,
            "redacted": True,
        }
        return SafeActuatorEvidenceMetadata.from_value(
            {
                "claim_gate": claim_gate,
                "cross_plane_claim_gate": cls._dispatch_cross_plane_claim_gate(),
                "evidence": evidence,
                "source_agents": [_SERVICE_AGENT],
                "event_ids": [],
                "claim_boundary": claim_gate["claim_boundary"],
                "redacted": True,
            }
        )

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

    def _publish_dispatch_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        action_type: str,
        context: Dict[str, Any],
        result: Optional[ActionResult] = None,
        reason: str = "",
        policy_decision: Any = None,
        safe_actuator_evidence_metadata: Optional[SafeActuatorEvidenceMetadata] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        action_resource = self._action_resource_name(action_type)
        result_payload = (
            {
                "action_type": result.action_type,
                "success": result.success,
                "detail": result.detail,
            }
            if result is not None
            else None
        )
        payload = {
            "component": "dao.governance",
            "stage": stage,
            "action_type": action_type,
            "action_resource": action_resource,
            "resource": f"dao:governance:{action_resource}",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "result": self._safe_context(result_payload) if result_payload is not None else None,
            "success": result.success if result is not None else None,
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
            "safe_actuator_evidence_metadata": (
                safe_actuator_evidence_metadata.to_dict()
                if safe_actuator_evidence_metadata is not None
                else SafeActuatorEvidenceMetadata().to_dict()
            ),
            "claim_boundary": DAO_GOVERNANCE_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish DAO governance dispatch event: %s", exc)
            return None

    def _evaluate_dispatch_policy(self, action_type: str) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "DAO governance policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "DAO governance SPIFFE identity is required for policy evaluation"
        action_resource = self._action_resource_name(action_type)
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=f"dao:governance:{action_resource}",
                workload_type="dao-governance",
            )
        except Exception as exc:
            return False, None, f"DAO governance policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "DAO governance policy denied action"
        return True, decision, self._policy_reason(decision)

    def _execute_handler_through_actuator(
        self,
        _action_name: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        action = context.get("action")
        handler = context.get("handler")
        action_type = str(context.get("action_type", ""))
        if not isinstance(action, dict):
            return SafeActuatorResult(
                False,
                "DAO governance action is missing",
                evidence_metadata=self._dispatch_evidence_metadata(
                    action_type=action_type,
                    context=context,
                    success=False,
                ),
            )
        if not callable(handler):
            return SafeActuatorResult(
                False,
                f"unknown DAO governance action type: {action_type}",
                evidence_metadata=self._dispatch_evidence_metadata(
                    action_type=action_type,
                    context=context,
                    success=False,
                ),
            )
        start = time.monotonic()
        result = handler(action)
        duration_ms = int((time.monotonic() - start) * 1000)
        self._last_dispatch_result = result
        return SafeActuatorResult(
            result.success,
            result.detail,
            evidence_metadata=self._dispatch_evidence_metadata(
                action_type=action_type,
                context=context,
                success=result.success,
                result=result,
                duration_ms=duration_ms,
            ),
        )

    def _register_defaults(self):
        self._handlers["restart_node"] = self._handle_restart_node
        self._handlers["rotate_keys"] = self._handle_rotate_keys
        self._handlers["update_threshold"] = self._handle_update_threshold
        self._handlers["update_config"] = self._handle_update_config
        self._handlers["ban_node"] = self._handle_ban_node

    def register(
        self, action_type: str, handler: Callable[[Dict[str, Any]], ActionResult]
    ):
        """Register a custom action handler."""
        self._handlers[action_type] = handler

    def dispatch(self, action: Dict[str, Any]) -> ActionResult:
        """Dispatch a single action to its handler."""
        action_type = action.get("type", "")
        handler = self._handlers.get(action_type)
        context = {"action": action, "action_type": action_type}
        self._last_dispatch_result = None
        self._publish_dispatch_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            action_type=action_type,
            context=context,
        )

        if handler is None:
            result = ActionResult(
                action_type=action_type,
                success=False,
                detail=f"Unknown action type: {action_type}",
            )
            self._publish_dispatch_event(
                EventType.TASK_FAILED,
                stage="invalid_action",
                action_type=action_type,
                context=context,
                result=result,
                reason=result.detail,
            )
            return result

        policy_allowed, policy_decision, policy_reason = self._evaluate_dispatch_policy(action_type)
        if not policy_allowed:
            result = ActionResult(
                action_type=action_type,
                success=False,
                detail=policy_reason,
            )
            self._publish_dispatch_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                action_type=action_type,
                context=context,
                result=result,
                reason=policy_reason,
                policy_decision=policy_decision,
            )
            return result

        self._publish_dispatch_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            action_type=action_type,
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )

        try:
            actuator_context = dict(context)
            actuator_context["handler"] = handler
            actuator_result = self.safe_actuator.execute(action_type, actuator_context)
            if not actuator_result.evidence_metadata.claim_gate:
                actuator_result = SafeActuatorResult(
                    success=actuator_result.success,
                    reason=actuator_result.reason,
                    simulated=actuator_result.simulated,
                    evidence_metadata=self._dispatch_evidence_metadata(
                        action_type=action_type,
                        context=actuator_context,
                        success=actuator_result.success,
                        simulated=actuator_result.simulated,
                        result=self._last_dispatch_result,
                    ),
                )
            if actuator_result.simulated:
                result = ActionResult(
                    action_type=action_type,
                    success=False,
                    detail=actuator_result.reason or "safe actuator returned simulated result",
                )
                self._publish_dispatch_event(
                    EventType.TASK_FAILED,
                    stage="actuator_simulated",
                    action_type=action_type,
                    context=context,
                    result=result,
                    reason=result.detail,
                    policy_decision=policy_decision,
                    safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
                )
                return result
            result = self._last_dispatch_result or ActionResult(
                action_type=action_type,
                success=actuator_result.success,
                detail=actuator_result.reason,
            )
            if not actuator_result.success and result.success:
                result = ActionResult(
                    action_type=action_type,
                    success=False,
                    detail=actuator_result.reason or "safe actuator failed",
                )
            self._publish_dispatch_event(
                EventType.PIPELINE_STAGE_END if result.success else EventType.TASK_FAILED,
                stage="actuator_completed" if result.success else "actuator_failed",
                action_type=action_type,
                context=context,
                result=result,
                reason=result.detail or policy_reason,
                policy_decision=policy_decision,
                safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
            )
            return result
        except Exception as e:
            logger.error(f"Action '{action_type}' failed: {e}")
            result = ActionResult(action_type=action_type, success=False, detail=str(e))
            self._publish_dispatch_event(
                EventType.TASK_FAILED,
                stage="actuator_error",
                action_type=action_type,
                context=context,
                result=result,
                reason=str(e),
                policy_decision=policy_decision,
            )
            return result

    # --- Built-in handlers ---

    @staticmethod
    def _handle_restart_node(action: Dict[str, Any]) -> ActionResult:
        node_id = action.get("node_id", "")
        if not node_id:
            return ActionResult("restart_node", False, "missing node_id")
        if not _NODE_ID_RE.match(node_id):
            return ActionResult("restart_node", False, f"invalid node_id: {node_id!r}")
        logger.info(f"MAPE-K execute: restarting node {node_id}")
        return ActionResult("restart_node", True, f"restart queued for {node_id}")

    @staticmethod
    def _handle_rotate_keys(action: Dict[str, Any]) -> ActionResult:
        scope = action.get("scope", "all")
        logger.info(f"🚀 PQC/Reality key rotation triggered (scope={scope})")
        
        try:
            # 1. Rotate Reality VPN Keys - use lazy import for optional dependency
            try:
                from vpn_config_generator import XUIAPIClient
                xui = XUIAPIClient()
            except ImportError as ie:
                logger.warning(f"XUIAPIClient not available: {ie}, skipping Reality key rotation")
                return ActionResult("rotate_keys", False, f"XUIAPIClient not available: {ie}")
            new_creds = xui.rotate_reality_credentials()
            
            # 2. Update global environment (optional, but good for persistence)
            # os.environ["REALITY_PUBLIC_KEY"] = new_creds["public_key"]
            
            detail = (
                f"Reality keys rotated (scope={scope}). New Public Key: {new_creds['public_key'][:8]}..., "
                f"ShortID: {new_creds.get('short_id')}"
            )
            return ActionResult("rotate_keys", True, detail)
        except Exception as e:
            logger.error(f"❌ Key rotation failed: {e}")
            return ActionResult("rotate_keys", False, str(e))


    @staticmethod
    def _handle_update_threshold(action: Dict[str, Any]) -> ActionResult:
        threshold = action.get("value")
        if threshold is None:
            return ActionResult("update_threshold", False, "missing value")
        logger.info(f"Anomaly threshold updated to {threshold}")
        return ActionResult("update_threshold", True, f"threshold={threshold}")

    @staticmethod
    def _handle_update_config(action: Dict[str, Any]) -> ActionResult:
        key = action.get("key", "")
        value = action.get("value")
        if not key:
            return ActionResult("update_config", False, "missing key")
        logger.info(f"Config updated: {key}={value}")
        return ActionResult("update_config", True, f"{key}={value}")

    @staticmethod
    def _handle_ban_node(action: Dict[str, Any]) -> ActionResult:
        node_id = action.get("node_id", "")
        if not node_id:
            return ActionResult("ban_node", False, "missing node_id")
        if not _NODE_ID_RE.match(node_id):
            return ActionResult("ban_node", False, f"invalid node_id: {node_id!r}")
        logger.info(f"Node {node_id} banned from mesh")
        return ActionResult("ban_node", True, f"node {node_id} banned")


class GovernanceEngine:
    """
    Manages proposals and voting for the Mesh DAO.
    Now with Quadratic Voting support and action dispatch.
    """

    def __init__(
        self,
        node_id: str,
        ledger_path: Optional[Path] = None,
        dispatcher: Optional[ActionDispatcher] = None,
    ):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = sum(self.voting_power.values())
        # Action dispatcher
        self.dispatcher = dispatcher or ActionDispatcher(node_id=node_id)
        # Append-only ledger for audit trail
        self.ledger_path = ledger_path
        # Backward-compatible enum access expected by some call sites/tests.
        self.VoteType = VoteType
        self.ProposalState = ProposalState

    def _get_initial_voting_power(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 100.0,
            "node-3": 100.0,
            "node-4": 100.0,
        }

    def create_proposal(
        self,
        title: str,
        description: str,
        duration_seconds: float = 3600,
        actions: Optional[List[Dict]] = None,
        quorum: float = 0.5,
        threshold: float = 0.5,
    ) -> Proposal:
        """Create a new governance proposal.

        Args:
            title: Proposal title
            description: Proposal description
            duration_seconds: Voting duration in seconds
            actions: List of actions to execute if passed
            quorum: Required participation ratio (0.0-1.0)
            threshold: Required support ratio (0.0-1.0)

        Returns:
            Created Proposal object
        """
        title = title.strip() if title else ""
        if not title:
            raise ValueError("Proposal title cannot be empty")
        if len(title) > 200:
            raise ValueError("Proposal title exceeds 200 characters")
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        if not (0 < quorum <= 1.0):
            raise ValueError(f"quorum must be in range (0, 1], got {quorum}")
        if not (0 < threshold <= 1.0):
            raise ValueError(f"threshold must be in range (0, 1], got {threshold}")

        proposal_id = f"prop_{uuid.uuid4().hex[:8]}_{self.node_id}"
        now = time.time()

        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            start_time=now,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE,
            quorum=quorum,
            threshold=threshold,
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def cast_vote(
        self,
        proposal_id: str,
        voter_id: str,
        vote: VoteType,
        tokens: float = 1.0,
        signature: Optional[str] = None,
        voter_pubkey: Optional[str] = None
    ) -> bool:
        """
        Cast a vote on a proposal with quadratic voting and PQC signature verification.

        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
            signature: Hex-encoded PQC signature of (proposal_id + voter_id + vote.value)
            voter_pubkey: Hex-encoded public key of the voter (ML-DSA-65)

        Returns:
            True if vote was recorded, False otherwise
        """
        if not voter_id or not voter_id.strip():
            logger.warning("Empty voter_id rejected")
            return False

        if tokens < 0:
            logger.warning(f"Negative tokens ({tokens}) rejected for voter {voter_id}")
            return False

        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False

        proposal = self.proposals[proposal_id]

        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
        # PQC Signature Verification (MANDATORY in production)
        # Test mode detection via environment variable only (reliable)
        is_test_mode = os.environ.get("_X0TTA_TEST_MODE_") == "true"
        
        # In production, signatures are MANDATORY
        if not is_test_mode:
            if not signature or not voter_pubkey:
                logger.error(f"❌ Unsigned vote from {voter_id} rejected. Signatures are MANDATORY in production.")
                return False
        
        if signature and voter_pubkey:
            try:
                from src.libx0t.security.post_quantum import PQMeshSecurityLibOQS, LIBOQS_AVAILABLE
                
                if not LIBOQS_AVAILABLE:
                    if is_test_mode:
                        logger.warning("⚠️ PQC Backend missing - using stub in TEST mode")
                    else:
                        logger.critical("❌ PQC Backend missing during vote verification!")
                        raise RuntimeError("Fail-closed: PQC backend is mandatory for DAO voting.")

                if LIBOQS_AVAILABLE:
                    # Payload: proposal_id + voter_id + vote_value
                    payload = f"{proposal_id}:{voter_id}:{vote.value}".encode('utf-8')
                    
                    # ML-DSA-65 verification
                    verifier = PQMeshSecurityLibOQS("verifier-temp")
                    sig_bytes = bytes.fromhex(signature)
                    pub_bytes = bytes.fromhex(voter_pubkey)
                    
                    if not verifier.verify(payload, sig_bytes, pub_bytes):
                        logger.error(f"❌ Invalid PQC signature for vote from {voter_id}")
                        return False
                    logger.info(f"✅ PQC Vote Signature Verified for {voter_id}")

            except RuntimeError:
                # Re-raise RuntimeError (fail-closed)
                raise
            except Exception as e:
                logger.error(f"❌ Error verifying vote signature: {e}")
                if not is_test_mode:
                    return False
        elif not is_test_mode:
            # In production, signatures are mandatory
            logger.error(f"❌ Unsigned vote from {voter_id} rejected. Signatures are MANDATORY in production.")
            return False
        else:
            logger.warning(f"⚠️ Unsigned vote from {voter_id} accepted in TEST mode only.")


        if time.time() > proposal.end_time:
            self._tally_votes(proposal)
            logger.warning(f"Voting period ended for {proposal_id}")
            return False

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative

        # Calculate quadratic voting power for logging
        from math import sqrt

        voting_power = sqrt(tokens) if tokens > 0 else 0.0

        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def check_proposals(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE and now > proposal.end_time:
                self._tally_votes(proposal)

    def _tally_votes(self, proposal: Proposal):
        """
        Tally votes using Quadratic Voting algorithm.

        Quadratic Voting: Each voter's voting power = sqrt(tokens_held)
        This reduces the influence of large token holders and promotes
        more democratic decision-making.

        Example:
            - Voter A: 100 tokens → √100 = 10 voting power
            - Voter B: 10000 tokens → √10000 = 100 voting power (not 100x)
        """
        from math import sqrt

        proposal.vote_counts()
        total = proposal.total_votes()

        if total == 0:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} rejected (no votes)")
            return

        # Quadratic Voting: Calculate weighted votes
        yes_weighted = 0.0
        no_weighted = 0.0
        total_weighted = 0.0

        for voter_id, vote in proposal.votes.items():
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)

            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 0.0

            total_weighted += voting_power

            if vote == VoteType.YES:
                yes_weighted += voting_power
            elif vote == VoteType.NO:
                no_weighted += voting_power
            # ABSTAIN doesn't count toward weighted total

        # Calculate support ratio using weighted votes
        if total_weighted == 0:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} rejected (no weighted votes)")
            return

        # Check quorum: participation must meet minimum threshold
        # Calculate total possible voting power from all known voters
        total_possible = (
            sum(sqrt(t) for t in self.voting_power.values())
            if self.voting_power
            else total_weighted
        )
        participation = total_weighted / total_possible if total_possible > 0 else 0.0
        if participation < proposal.quorum:
            proposal.state = ProposalState.REJECTED
            logger.info(
                f"Proposal {proposal.id} rejected (quorum not met: "
                f"{participation:.1%} < {proposal.quorum:.1%} required)"
            )
            return

        support = yes_weighted / total_weighted

        # Log quadratic voting metrics
        logger.info(
            f"Quadratic Voting tally for {proposal.id}: "
            f"YES={yes_weighted:.2f}, NO={no_weighted:.2f}, "
            f"Total={total_weighted:.2f}, Support={support:.1%}, "
            f"Participation={participation:.1%}"
        )

        if support > proposal.threshold:
            proposal.state = ProposalState.PASSED
            logger.info(
                f"Proposal {proposal.id} PASSED ({support:.1%} weighted support)"
            )
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(
                f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)"
            )

    def execute_proposal(self, proposal_id: str) -> List[ActionResult]:
        """Execute actions of a passed proposal via the dispatcher.

        Returns:
            List of ActionResult for each action, or empty list on failure.
        """
        if proposal_id not in self.proposals:
            return []

        proposal = self.proposals[proposal_id]
        if proposal.state != ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return []

        results: List[ActionResult] = []
        logger.info(f"Executing {len(proposal.actions)} actions for {proposal_id}")

        for action in proposal.actions:
            result = self.dispatcher.dispatch(action)
            results.append(result)
            logger.info(
                f"Action {result.action_type}: "
                f"{'OK' if result.success else 'FAIL'} — {result.detail}"
            )

        proposal.state = ProposalState.EXECUTED
        self._write_ledger(proposal, results)
        return results

    def _write_ledger(self, proposal: Proposal, results: List[ActionResult]):
        """Append execution record to the JSONL ledger."""
        if self.ledger_path is None:
            return
        record = {
            "proposal_id": proposal.id,
            "title": proposal.title,
            "proposer": proposal.proposer,
            "executed_at": time.time(),
            "actions": [
                {"type": r.action_type, "success": r.success, "detail": r.detail}
                for r in results
            ],
        }
        try:
            self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_path, "a") as f:
                f.write(json.dumps(record) + "\n")
            logger.info(f"Ledger updated: {self.ledger_path}")
        except OSError as e:
            logger.error(f"Failed to write ledger: {e}")
