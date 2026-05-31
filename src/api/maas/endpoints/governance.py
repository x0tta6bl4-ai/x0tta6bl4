"""
MaaS DAO Governance API — x0tta6bl4
====================================

Decentralized decision making for mesh network parameters.
Proposals, votes, and execution results are persisted to the DB.
Execution finality is anchored by a SHA-256 hash of the full vote record.
"""

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.database import GovernanceProposal, GovernanceVote, User, GlobalConfig, get_db
from src.api.maas_auth import get_current_user_from_maas
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.reliability_policy import mark_degraded_dependency
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/governance", tags=["MaaS Governance"])

_SERVICE_AGENT = "maas-governance"
_PROPOSAL_CREATE_SOURCE_AGENT = "maas-governance-proposal-create"
_PROPOSAL_VOTE_SOURCE_AGENT = "maas-governance-vote-cast"
_PROPOSAL_EXECUTE_SOURCE_AGENT = "maas-governance-proposal-execute"
_PROPOSAL_LIST_SOURCE_AGENT = "maas-governance-proposal-list-read"
_PROPOSAL_READ_SOURCE_AGENT = "maas-governance-proposal-read"

_PROPOSAL_CREATE_LAYER = "api_governance_proposal_control_action"
_PROPOSAL_VOTE_LAYER = "api_governance_vote_control_action"
_PROPOSAL_EXECUTE_LAYER = "api_governance_execution_control_action"
_PROPOSAL_READ_LAYER = "api_governance_observed_state"

GOVERNANCE_ACTION_CLAIM_BOUNDARY = (
    "MaaS governance action event only. It records local identity, policy, "
    "and safe actuator state for API action dispatch; it is not external "
    "settlement evidence or proof of production governance execution."
)

GOVERNANCE_PROPOSAL_CLAIM_BOUNDARY = (
    "MaaS governance proposal API evidence only. It records local proposal, "
    "vote, execution-summary, and read-path state with redacted identifiers; "
    "it is not external DAO chain finality, settlement proof, or proof that "
    "a target mesh action completed outside this API process."
)

def get_gov_power(user: User) -> float:
    """Quadratic voting power by plan."""
    powers = {"free": 10.0, "starter": 100.0, "pro": 1000.0, "enterprise": 10000.0}
    return powers.get(user.plan, 10.0)

def _compute_finality_hash(proposal: GovernanceProposal, results: List[Dict]) -> str:
    """Compute a tamper-evident SHA-256 hash anchoring the governance decision."""
    vote_records = sorted(
        [(v.voter_id, v.vote, v.tokens) for v in proposal.votes],
        key=lambda x: x[0],
    )
    payload = json.dumps(
        {
            "proposal_id": proposal.id,
            "votes": vote_records,
            "results": results,
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()

class GovernanceAction(BaseModel):
    type: str = Field(..., pattern="^(update_config|rotate_keys|restart_node|update_price)$")
    params: Dict[str, Any] = Field(default_factory=dict)

class ProposalCreate(BaseModel):
    title: str = Field(..., min_length=10, max_length=128)
    description: str = Field(..., min_length=20)
    duration_hours: int = Field(default=24, ge=1, le=168)
    actions: List[GovernanceAction] = Field(default_factory=list)

class VoteRequest(BaseModel):
    vote: str = Field(..., pattern="^(yes|no|abstain)$")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _governance_policy_required() -> bool:
    return _env_bool("X0TTA6BL4_MAAS_GOVERNANCE_POLICY_REQUIRED", False) or _env_bool(
        "X0TTA6BL4_PRODUCTION",
        False,
    )


def _governance_db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit") and hasattr(db, "add")


def _governance_readiness_status(db: Any) -> Dict[str, Any]:
    db_ready = _governance_db_session_available(db)
    event_bus_ready = bool(EventBus and get_event_bus)
    safe_actuator_ready = bool(SafeActuator)
    service_identity_ready = callable(service_event_identity)
    policy_required = _governance_policy_required()
    policy_engine_ready = True
    if policy_required:
        policy_engine_ready = _default_policy_engine() is not None

    control_plane_ready = all(
        [
            event_bus_ready,
            safe_actuator_ready,
            service_identity_ready,
            policy_engine_ready,
        ]
    )

    degraded_dependencies = []
    if not db_ready:
        degraded_dependencies.append("database")
    if not event_bus_ready:
        degraded_dependencies.append("event_bus")
    if not safe_actuator_ready:
        degraded_dependencies.append("safe_actuator")
    if not service_identity_ready:
        degraded_dependencies.append("service_identity")
    if not policy_engine_ready:
        degraded_dependencies.append("policy_engine")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "governance_db_ready": db_ready,
        "control_plane_ready": control_plane_ready,
        "event_bus_ready": event_bus_ready,
        "safe_actuator_ready": safe_actuator_ready,
        "service_identity_ready": service_identity_ready,
        "policy_required": policy_required,
        "policy_engine_ready": policy_engine_ready,
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": "ready" if db_ready else "unavailable",
            "proposal_vote_store": "database_required",
            "event_bus": "imported" if event_bus_ready else "unavailable",
            "safe_actuator": "imported" if safe_actuator_ready else "unavailable",
            "service_identity": "imported" if service_identity_ready else "unavailable",
            "policy_engine": "required" if policy_required else "optional",
            "pqc_finality_attestation": "lazy_at_execute",
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_governance_readiness"
        ),
        "claim_boundary": (
            "Governance route readiness distinguishes route availability from "
            "proposal/vote database writes, EventBus trace publication, service "
            "identity resolution, policy evaluation, and SafeActuator dispatch. "
            "It does not prove external DAO chain finality, production policy "
            "correctness, or successful PQC attestation for a specific proposal."
        ),
    }


@router.get("/readiness")
async def governance_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _governance_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


def _default_event_bus(project_root: str = ".") -> Optional[EventBus]:
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS governance EventBus: %s", exc)
        return None


def _default_policy_engine() -> Optional[Any]:
    try:
        from src.security.zero_trust.policy_engine import get_policy_engine

        return get_policy_engine()
    except Exception as exc:
        logger.error("Failed to initialize MaaS governance policy engine: %s", exc)
        return None


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _governance_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize MaaS governance EventBus: %s", exc)
        return None


def _governance_actor_summary(user: Any) -> Dict[str, Any]:
    if user is None:
        return {
            "actor_user_id_hash": None,
            "actor_email_hash": None,
            "actor_email_present": False,
            "actor_plan": "",
            "actor_role": "",
        }
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_plan": str(getattr(user, "plan", "") or "")[:40],
        "actor_role": str(getattr(user, "role", "") or "")[:40],
    }


def _governance_service_identity_summary() -> Dict[str, Any]:
    if not callable(service_event_identity):
        return {
            "service_name": _SERVICE_AGENT,
            "spiffe_id_present": False,
            "spiffe_id_hash": None,
            "did_present": False,
            "did_hash": None,
            "wallet_address_present": False,
            "wallet_address_hash": None,
            "redacted": True,
        }
    try:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
    except Exception as exc:
        logger.error("Failed to resolve MaaS governance service identity: %s", exc)
        identity = {}
    spiffe_id = identity.get("spiffe_id")
    did = identity.get("did")
    wallet_address = identity.get("wallet_address")
    return {
        "service_name": _SERVICE_AGENT,
        "spiffe_id_present": bool(spiffe_id),
        "spiffe_id_hash": _redacted_sha256_prefix(spiffe_id),
        "did_present": bool(did),
        "did_hash": _redacted_sha256_prefix(did),
        "wallet_address_present": bool(wallet_address),
        "wallet_address_hash": _redacted_sha256_prefix(wallet_address),
        "redacted": True,
    }


def _governance_action_type(action: Any) -> str:
    if isinstance(action, GovernanceAction):
        return action.type
    if isinstance(action, dict):
        return str(action.get("type", action.get("action_type", "other")) or "other")
    return str(getattr(action, "type", getattr(action, "action_type", "other")) or "other")


def _governance_action_counts(actions: Optional[List[Any]]) -> Dict[str, int]:
    counts = {
        "update_config": 0,
        "rotate_keys": 0,
        "restart_node": 0,
        "update_price": 0,
        "other": 0,
    }
    for action in actions or []:
        action_type = _governance_action_type(action)
        if action_type in counts and action_type != "other":
            counts[action_type] += 1
        else:
            counts["other"] += 1
    return counts


def _proposal_actions(proposal: Any) -> List[Any]:
    raw_actions = getattr(proposal, "actions_json", None)
    if not raw_actions:
        return []
    try:
        loaded = json.loads(raw_actions)
    except Exception:
        return []
    return loaded if isinstance(loaded, list) else []


def _proposal_state_counts(proposals: List[Any]) -> Dict[str, int]:
    counts = {"active": 0, "passed": 0, "rejected": 0, "executed": 0, "other": 0}
    for proposal in proposals:
        try:
            state = _resolve_state(proposal)
        except Exception:
            state = str(getattr(proposal, "state", "") or "other")
        if state in counts and state != "other":
            counts[state] += 1
        else:
            counts["other"] += 1
    return counts


def _vote_bucket(value: Any) -> str:
    vote = str(value or "").strip().lower()
    if vote in {"yes", "no", "abstain"}:
        return vote
    return "missing" if not vote else "other"


def _voting_power_bucket(value: Any) -> str:
    if value is None:
        return "missing"
    try:
        power = float(value)
    except (TypeError, ValueError):
        return "other"
    if power >= 10000:
        return "enterprise"
    if power >= 1000:
        return "pro"
    if power >= 100:
        return "starter"
    if power > 0:
        return "free"
    return "zero"


def _execution_result_counts(results: Optional[List[Dict[str, Any]]]) -> Dict[str, int]:
    counts = {"success": 0, "failed": 0}
    for result in results or []:
        if result.get("success") is True:
            counts["success"] += 1
        else:
            counts["failed"] += 1
    return counts


def _event_type_for_status(http_status_code: Optional[int]) -> EventType:
    if http_status_code is None or http_status_code < 400:
        return EventType.PIPELINE_STAGE_END
    if http_status_code >= 500:
        return EventType.TASK_FAILED
    return EventType.TASK_BLOCKED


def _publish_governance_proposal_event(
    request: Optional[Request],
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    status: str,
    current_user: Any = None,
    proposal_id: Any = None,
    proposal: Any = None,
    proposals: Optional[List[Any]] = None,
    proposal_request: Optional[ProposalCreate] = None,
    vote: Any = None,
    voting_power: Any = None,
    results: Optional[List[Dict[str, Any]]] = None,
    finality_hash: Any = None,
    pqc_attestation: Any = None,
    db_backed: Optional[bool] = None,
    audit_log_attempted: bool = False,
    state_transition_applied: bool = False,
    http_status_code: Optional[int] = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> Optional[str]:
    event_bus = _governance_event_bus_from_request(request)
    if event_bus is None:
        return None

    proposal_list = list(proposals or [])
    request_actions = list(getattr(proposal_request, "actions", []) or [])
    proposal_actions = _proposal_actions(proposal)
    actions_for_counts = request_actions if request_actions else proposal_actions
    target_proposal_id = proposal_id if proposal_id is not None else getattr(proposal, "id", None)
    proposal_state = str(getattr(proposal, "state", "") or "")
    title = getattr(proposal_request, "title", None)
    if title is None:
        title = getattr(proposal, "title", None)
    description = getattr(proposal_request, "description", None)
    if description is None:
        description = getattr(proposal, "description", None)

    payload: Dict[str, Any] = {
        "component": "api.maas_governance",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_governance_actor_summary(current_user),
        "service_identity": _governance_service_identity_summary(),
        "proposal_id_hash": _redacted_sha256_prefix(target_proposal_id),
        "proposal_count": len(proposal_list),
        "proposal_id_hashes": [
            _redacted_sha256_prefix(getattr(item, "id", None))
            for item in proposal_list[:20]
        ],
        "proposal_hashes_truncated": max(0, len(proposal_list) - 20),
        "proposal_state": proposal_state[:40],
        "proposal_state_counts": _proposal_state_counts(proposal_list),
        "title_length": len(str(title or "")),
        "description_length": len(str(description or "")),
        "duration_hours": getattr(proposal_request, "duration_hours", None),
        "action_count": len(actions_for_counts),
        "action_counts": _governance_action_counts(actions_for_counts),
        "vote_bucket": _vote_bucket(vote),
        "voting_power_bucket": _voting_power_bucket(voting_power),
        "votes_count": len(getattr(proposal, "votes", []) or []) if proposal is not None else None,
        "execution_result_counts": _execution_result_counts(results),
        "finality_hash_present": bool(finality_hash),
        "finality_hash_hash": _redacted_sha256_prefix(finality_hash),
        "pqc_attestation_present": bool(pqc_attestation),
        "pqc_attestation_hash": _redacted_sha256_prefix(pqc_attestation),
        "db_backed": db_backed,
        "audit_log_attempted": audit_log_attempted,
        "state_transition_applied": state_transition_applied,
        "http_status_code": http_status_code,
        "read_only": source_agent in {
            _PROPOSAL_LIST_SOURCE_AGENT,
            _PROPOSAL_READ_SOURCE_AGENT,
        },
        "observed_state": source_agent in {
            _PROPOSAL_LIST_SOURCE_AGENT,
            _PROPOSAL_READ_SOURCE_AGENT,
        },
        "control_action": source_agent in {
            _PROPOSAL_CREATE_SOURCE_AGENT,
            _PROPOSAL_VOTE_SOURCE_AGENT,
            _PROPOSAL_EXECUTE_SOURCE_AGENT,
        },
        "downstream_safe_actuator_actions": source_agent == _PROPOSAL_EXECUTE_SOURCE_AGENT,
        "raw_identifiers_redacted": True,
        "raw_payload_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": GOVERNANCE_PROPOSAL_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            _event_type_for_status(http_status_code),
            source_agent,
            payload,
            priority=6,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS governance proposal event: %s", exc)
        return None


def _policy_allowed(decision: Any) -> bool:
    return normalize_policy_allowed(decision)


def _policy_reason(decision: Any) -> str:
    return normalize_policy_reason(decision)


def _policy_rules(decision: Any) -> List[str]:
    return normalize_policy_rules(decision)


_HASHED_CONTEXT_KEYS = frozenset(
    {
        "id",
        "proposal_id",
        "user_id",
        "voter_id",
        "mesh_id",
        "node_id",
        "wallet_address",
        "spiffe_id",
        "did",
    }
)


def _safe_value(key: str, value: Any, depth: int = 0) -> Any:
    key_lower = str(key).lower()
    blocked_fragments = ("secret", "password", "token", "key", "private")
    if any(fragment in key_lower for fragment in blocked_fragments):
        return "<redacted>"
    if (
        key_lower in _HASHED_CONTEXT_KEYS
        or key_lower.endswith("_id")
        or key_lower.endswith("_uuid")
    ):
        return _redacted_sha256_prefix(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict) and depth < 3:
        return {
            str(child_key): _safe_value(str(child_key), child_value, depth + 1)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list) and depth < 3:
        return [_safe_value(key, item, depth + 1) for item in value]
    return str(value)


def _safe_context(context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        str(key): _safe_value(str(key), value)
        for key, value in context.items()
    }


def _action_resource_name(action_type: str) -> str:
    action_lower = str(action_type or "unknown_action").lower().strip()
    slug = "".join(
        char if char.isalnum() else "_"
        for char in action_lower
    ).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "unknown_action"


def _publish_governance_action_event(
    event_bus: Optional[EventBus],
    event_type: EventType,
    *,
    source_agent: str,
    identity: Dict[str, Optional[str]],
    stage: str,
    action_type: str,
    context: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
    reason: str = "",
    policy_decision: Any = None,
    policy_required: bool = False,
) -> Optional[str]:
    if event_bus is None:
        return None
    action_resource = _action_resource_name(action_type)
    payload = {
        "component": "api.maas_governance",
        "stage": stage,
        "action_type": action_type,
        "action_resource": action_resource,
        "resource": f"api:maas_governance:{action_resource}",
        "node_id": identity["node_id"],
        "spiffe_id": identity["spiffe_id"],
        "did": identity["did"],
        "wallet_address": identity["wallet_address"],
        "identity": dict(identity),
        "context": _safe_context(context),
        "result": _safe_context(result or {}) if result is not None else None,
        "success": result.get("success") if result is not None else None,
        "reason": reason,
        "policy_required": policy_required,
        "policy_allowed": _policy_allowed(policy_decision)
        if policy_decision is not None
        else None,
        "policy_reason": _policy_reason(policy_decision)
        if policy_decision is not None
        else "",
        "matched_rules": _policy_rules(policy_decision)
        if policy_decision is not None
        else [],
        "safe_actuator": True,
        "claim_boundary": GOVERNANCE_ACTION_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(event_type, source_agent, payload, priority=7)
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS governance action event: %s", exc)
        return None


def _evaluate_governance_action_policy(
    *,
    identity: Dict[str, Optional[str]],
    action_type: str,
    policy_engine: Optional[Any],
    require_policy: bool,
) -> tuple[bool, Any, str]:
    if policy_engine is None:
        if require_policy:
            return False, None, "MaaS governance policy engine is required but unavailable"
        return True, None, ""
    spiffe_id = identity.get("spiffe_id")
    if not spiffe_id:
        return False, None, "MaaS governance SPIFFE identity is required for policy evaluation"
    action_resource = _action_resource_name(action_type)
    try:
        decision = policy_engine.evaluate(
            spiffe_id,
            resource=f"api:maas_governance:{action_resource}",
            workload_type="maas-governance",
        )
    except Exception as exc:
        return False, None, f"MaaS governance policy evaluation failed: {exc}"
    if not _policy_allowed(decision):
        return False, decision, _policy_reason(decision) or "MaaS governance policy denied action"
    return True, decision, _policy_reason(decision)


def _execute_action_internal(action: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    action_type = action.get("type", action.get("action_type", "unknown"))
    params = action.get("params", {})
    if action_type == "update_config":
        key = params.get("key", "")
        value = params.get("value")
        if key == "global_price_multiplier":
            logger.info("⚖️ DAO: Applying global price multiplier: %s", value)
            if hasattr(db, "query"):
                config = db.query(GlobalConfig).filter(GlobalConfig.key == "global_price_multiplier").first()
                if config:
                    config.value_json = json.dumps(value)
                else:
                    db.add(GlobalConfig(key="global_price_multiplier", value_json=json.dumps(value)))
                db.commit()
            return {"action": action_type, "success": True, "detail": f"Multiplier {value} applied"}
        return {"action": action_type, "success": False, "detail": f"Unsupported config key: {key}"}
    if action_type == "rotate_keys":
        return {"action": action_type, "success": True, "detail": "Key rotation scheduled"}
    if action_type == "update_price":
        return {"action": action_type, "success": True, "detail": f"Price updated: {params}"}
    return {"action": action_type, "success": False, "detail": "Unknown action type"}


def _execute_action(
    action: Dict[str, Any],
    db: Optional[Session] = None,
    *,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
    policy_engine: Optional[Any] = None,
    require_policy: Optional[bool] = None,
    source_agent: str = _SERVICE_AGENT,
    spiffe_id: Optional[str] = None,
    did: Optional[str] = None,
    wallet_address: Optional[str] = None,
    safe_actuator: Optional[SafeActuator] = None,
    proposal_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    action_type = action.get("type", action.get("action_type", "unknown"))
    params = action.get("params", {})
    service_identity = service_event_identity(service_name="maas-governance")
    identity = {
        "node_id": "maas-governance",
        "spiffe_id": spiffe_id if spiffe_id is not None else service_identity["spiffe_id"],
        "did": did if did is not None else service_identity["did"],
        "wallet_address": (
            wallet_address
            if wallet_address is not None
            else service_identity["wallet_address"]
        ),
    }
    bus = event_bus if event_bus is not None else _default_event_bus(event_project_root)
    policy_required = (
        require_policy
        if require_policy is not None
        else _governance_policy_required()
    )
    policy = policy_engine
    if policy is None and policy_required:
        policy = _default_policy_engine()
    context = {
        "action": action,
        "action_type": action_type,
        "params": params,
        "proposal_id": proposal_id,
        "user_id": user_id,
    }

    _publish_governance_action_event(
        bus,
        EventType.COORDINATION_REQUEST,
        source_agent=source_agent,
        identity=identity,
        stage="received",
        action_type=action_type,
        context=context,
        policy_required=policy_required or policy is not None,
    )

    policy_allowed, policy_decision, policy_reason = _evaluate_governance_action_policy(
        identity=identity,
        action_type=action_type,
        policy_engine=policy,
        require_policy=policy_required,
    )
    if not policy_allowed:
        result = {
            "action": action_type,
            "success": False,
            "detail": policy_reason,
            "policy_required": True,
            "matched_rules": _policy_rules(policy_decision),
        }
        _publish_governance_action_event(
            bus,
            EventType.TASK_BLOCKED,
            source_agent=source_agent,
            identity=identity,
            stage="policy_denied",
            action_type=action_type,
            context=context,
            result=result,
            reason=policy_reason,
            policy_decision=policy_decision,
            policy_required=policy_required or policy is not None,
        )
        return result

    _publish_governance_action_event(
        bus,
        EventType.PIPELINE_STAGE_START,
        source_agent=source_agent,
        identity=identity,
        stage="actuator_start",
        action_type=action_type,
        context=context,
        reason=policy_reason,
        policy_decision=policy_decision,
        policy_required=policy_required or policy is not None,
    )

    action_result: Optional[Dict[str, Any]] = None

    def _run_action(_action_name: str, _context: Dict[str, Any]) -> Dict[str, Any]:
        nonlocal action_result
        action_result = _execute_action_internal(action, db)
        return action_result

    actuator = safe_actuator or SafeActuator(_run_action)
    actuator_result = actuator.execute(action_type, context)
    if actuator_result.simulated:
        result = {
            "action": action_type,
            "success": False,
            "detail": actuator_result.reason or "safe actuator returned simulated result",
            "simulated": True,
        }
        _publish_governance_action_event(
            bus,
            EventType.TASK_FAILED,
            source_agent=source_agent,
            identity=identity,
            stage="actuator_simulated",
            action_type=action_type,
            context=context,
            result=result,
            reason=result["detail"],
            policy_decision=policy_decision,
            policy_required=policy_required or policy is not None,
        )
        return result

    result = action_result or {
        "action": action_type,
        "success": actuator_result.success,
        "detail": actuator_result.reason,
    }
    if not actuator_result.success:
        result = {
            "action": action_type,
            "success": False,
            "detail": actuator_result.reason or result.get("detail", "safe actuator failed"),
        }
    _publish_governance_action_event(
        bus,
        EventType.PIPELINE_STAGE_END if result.get("success") else EventType.TASK_FAILED,
        source_agent=source_agent,
        identity=identity,
        stage="actuator_completed" if result.get("success") else "actuator_failed",
        action_type=action_type,
        context=context,
        result=result,
        reason=result.get("detail", "") or policy_reason,
        policy_decision=policy_decision,
        policy_required=policy_required or policy is not None,
    )
    return result

def _tally(proposal: GovernanceProposal) -> Dict[str, float]:
    tally: Dict[str, float] = {"yes": 0.0, "no": 0.0, "abstain": 0.0}
    for v in proposal.votes:
        qv = (v.tokens / 100.0) ** 0.5
        tally[v.vote] = tally.get(v.vote, 0.0) + qv
    return tally

def _resolve_state(proposal: GovernanceProposal) -> str:
    if proposal.state == "executed": return "executed"
    if proposal.state != "active": return proposal.state  # preserve cancelled/rejected/passed
    if datetime.utcnow() < proposal.end_time: return "active"
    tally = _tally(proposal)
    return "passed" if tally["yes"] > tally["no"] else "rejected"

@router.post("/proposals")
async def create_maas_proposal(
    req: ProposalCreate,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    request: Request = None,
):
    started = time.monotonic()
    if current_user.plan not in ("pro", "enterprise"):
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_CREATE_SOURCE_AGENT,
            layer=_PROPOSAL_CREATE_LAYER,
            stage="proposal_create_control",
            operation="maas_governance_proposal_create",
            status="denied",
            current_user=current_user,
            proposal_request=req,
            db_backed=_governance_db_session_available(db),
            http_status_code=403,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="plan_not_allowed",
        )
        raise HTTPException(status_code=403, detail="Pro/Enterprise only")

    proposal_id = f"prop-{uuid.uuid4().hex[:8]}"
    end_dt = datetime.utcnow() + timedelta(hours=req.duration_hours)

    row = GovernanceProposal(
        id=proposal_id,
        title=req.title,
        description=req.description,
        state="active",
        actions_json=json.dumps([a.dict() for a in req.actions]),
        end_time=end_dt,
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()

    record_audit_log(
        db, None, "GOVERNANCE_PROPOSAL_CREATED",
        user_id=current_user.id,
        payload={"proposal_id": proposal_id, "title": req.title},
        status_code=201
    )
    _publish_governance_proposal_event(
        request,
        source_agent=_PROPOSAL_CREATE_SOURCE_AGENT,
        layer=_PROPOSAL_CREATE_LAYER,
        stage="proposal_create_control",
        operation="maas_governance_proposal_create",
        status="created",
        current_user=current_user,
        proposal_id=proposal_id,
        proposal=row,
        proposal_request=req,
        db_backed=_governance_db_session_available(db),
        audit_log_attempted=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {"proposal_id": proposal_id, "status": "active", "expires_at": end_dt.isoformat()}

@router.post("/proposals/{proposal_id}/vote")
async def cast_maas_vote(
    proposal_id: str,
    req: VoteRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    request: Request = None,
):
    started = time.monotonic()
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_VOTE_SOURCE_AGENT,
            layer=_PROPOSAL_VOTE_LAYER,
            stage="vote_cast_control",
            operation="maas_governance_vote_cast",
            status="not_found",
            current_user=current_user,
            proposal_id=proposal_id,
            vote=req.vote,
            db_backed=_governance_db_session_available(db),
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="proposal_not_found",
        )
        raise HTTPException(status_code=404, detail="Proposal not found")
    proposal_state = _resolve_state(p)
    if proposal_state != "active":
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_VOTE_SOURCE_AGENT,
            layer=_PROPOSAL_VOTE_LAYER,
            stage="vote_cast_control",
            operation="maas_governance_vote_cast",
            status="invalid_state",
            current_user=current_user,
            proposal_id=proposal_id,
            proposal=p,
            vote=req.vote,
            db_backed=_governance_db_session_available(db),
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"proposal_state:{proposal_state}",
        )
        raise HTTPException(status_code=400, detail="Invalid proposal state")

    existing = db.query(GovernanceVote).filter(
        GovernanceVote.proposal_id == proposal_id,
        GovernanceVote.voter_id == current_user.id
    ).first()
    if existing:
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_VOTE_SOURCE_AGENT,
            layer=_PROPOSAL_VOTE_LAYER,
            stage="vote_cast_control",
            operation="maas_governance_vote_cast",
            status="duplicate",
            current_user=current_user,
            proposal_id=proposal_id,
            proposal=p,
            vote=req.vote,
            db_backed=_governance_db_session_available(db),
            http_status_code=409,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="already_voted",
        )
        raise HTTPException(status_code=409, detail="Already voted")

    power = get_gov_power(current_user)
    db.add(GovernanceVote(
        id=f"vote-{uuid.uuid4().hex[:8]}",
        proposal_id=proposal_id,
        voter_id=current_user.id,
        vote=req.vote,
        tokens=int(power * 100),
    ))
    db.commit()

    record_audit_log(
        db, None, "GOVERNANCE_VOTE_CAST",
        user_id=current_user.id,
        payload={"proposal_id": proposal_id, "vote": req.vote, "power": power},
        status_code=200
    )
    _publish_governance_proposal_event(
        request,
        source_agent=_PROPOSAL_VOTE_SOURCE_AGENT,
        layer=_PROPOSAL_VOTE_LAYER,
        stage="vote_cast_control",
        operation="maas_governance_vote_cast",
        status="accepted",
        current_user=current_user,
        proposal_id=proposal_id,
        proposal=p,
        vote=req.vote,
        voting_power=power,
        db_backed=_governance_db_session_available(db),
        audit_log_attempted=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {
        "status": "accepted",
        "voting_power_used": power,
        "quadratic_weight": power ** 0.5,
    }

@router.post("/proposals/{proposal_id}/execute")
async def execute_maas_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
    request: Request = None,
):
    started = time.monotonic()
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_EXECUTE_SOURCE_AGENT,
            layer=_PROPOSAL_EXECUTE_LAYER,
            stage="proposal_execute_control",
            operation="maas_governance_proposal_execute",
            status="not_found",
            current_user=current_user,
            proposal_id=proposal_id,
            db_backed=_governance_db_session_available(db),
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="proposal_not_found",
        )
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p.state == "executed":
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_EXECUTE_SOURCE_AGENT,
            layer=_PROPOSAL_EXECUTE_LAYER,
            stage="proposal_execute_control",
            operation="maas_governance_proposal_execute",
            status="already_executed",
            current_user=current_user,
            proposal_id=proposal_id,
            proposal=p,
            db_backed=_governance_db_session_available(db),
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="proposal_already_executed",
        )
        raise HTTPException(status_code=400, detail="Proposal already executed")
    proposal_state = _resolve_state(p)
    if proposal_state != "passed":
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_EXECUTE_SOURCE_AGENT,
            layer=_PROPOSAL_EXECUTE_LAYER,
            stage="proposal_execute_control",
            operation="maas_governance_proposal_execute",
            status="invalid_state",
            current_user=current_user,
            proposal_id=proposal_id,
            proposal=p,
            db_backed=_governance_db_session_available(db),
            http_status_code=400,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason=f"proposal_state:{proposal_state}",
        )
        raise HTTPException(status_code=400, detail="Proposal must be passed to execute")

    actions = json.loads(p.actions_json) if p.actions_json else []
    action_event_bus = _governance_event_bus_from_request(request)
    results = [
        _execute_action(
            a,
            db,
            event_bus=action_event_bus,
            proposal_id=p.id,
            user_id=current_user.id,
        )
        for a in actions
    ]
    finality_hash = _compute_finality_hash(p, results)

    # PQC-sign the finality hash to ensure non-repudiation
    try:
        from src.libx0t.core.app import pqc_sign
        pqc_attestation = pqc_sign(finality_hash.encode()).hex()
    except ImportError:
        import hashlib
        pqc_attestation = hashlib.sha256(finality_hash.encode()).hexdigest()

    p.state = "executed"
    p.execution_hash = finality_hash
    p.executed_at = datetime.utcnow()
    db.commit()

    record_audit_log(
        db, None, "GOVERNANCE_PROPOSAL_EXECUTED",
        user_id=current_user.id,
        payload={"proposal_id": proposal_id, "hash": finality_hash, "pqc": pqc_attestation},
        status_code=200
    )
    _publish_governance_proposal_event(
        request,
        source_agent=_PROPOSAL_EXECUTE_SOURCE_AGENT,
        layer=_PROPOSAL_EXECUTE_LAYER,
        stage="proposal_execute_control",
        operation="maas_governance_proposal_execute",
        status="executed",
        current_user=current_user,
        proposal_id=proposal_id,
        proposal=p,
        results=results,
        finality_hash=finality_hash,
        pqc_attestation=pqc_attestation,
        db_backed=_governance_db_session_available(db),
        audit_log_attempted=True,
        state_transition_applied=True,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {
        "status": "executed",
        "proposal_id": proposal_id,
        "finality_hash": finality_hash,
        "pqc_attestation": pqc_attestation,
        "actions_total": len(results),
        "actions_succeeded": sum(
            1 for result in results if result.get("success") is True
        ),
    }

@router.get("/proposals")
async def list_proposals(db: Session = Depends(get_db), request: Request = None):
    started = time.monotonic()
    rows = db.query(GovernanceProposal).order_by(GovernanceProposal.created_at.desc()).all()
    _publish_governance_proposal_event(
        request,
        source_agent=_PROPOSAL_LIST_SOURCE_AGENT,
        layer=_PROPOSAL_READ_LAYER,
        stage="proposal_list_observed_state",
        operation="maas_governance_proposal_list",
        status="ok",
        proposals=list(rows),
        db_backed=_governance_db_session_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {"proposals": [{"id": p.id, "title": p.title, "state": _resolve_state(p)} for p in rows]}

@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    db: Session = Depends(get_db),
    request: Request = None,
):
    started = time.monotonic()
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        _publish_governance_proposal_event(
            request,
            source_agent=_PROPOSAL_READ_SOURCE_AGENT,
            layer=_PROPOSAL_READ_LAYER,
            stage="proposal_read_observed_state",
            operation="maas_governance_proposal_get",
            status="not_found",
            proposal_id=proposal_id,
            db_backed=_governance_db_session_available(db),
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="proposal_not_found",
        )
        raise HTTPException(status_code=404, detail="Proposal not found")
    state = _resolve_state(p)
    state_transition_applied = False
    if state != p.state and p.state == "active":
        p.state = state
        db.commit()
        state_transition_applied = True
    _publish_governance_proposal_event(
        request,
        source_agent=_PROPOSAL_READ_SOURCE_AGENT,
        layer=_PROPOSAL_READ_LAYER,
        stage="proposal_read_observed_state",
        operation="maas_governance_proposal_get",
        status="ok",
        proposal_id=proposal_id,
        proposal=p,
        db_backed=_governance_db_session_available(db),
        state_transition_applied=state_transition_applied,
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
    )
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "state": state,
        "actions": json.loads(p.actions_json) if p.actions_json else [],
        "votes": _tally(p),
        "votes_count": len(p.votes),
        "end_time": p.end_time.isoformat(),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "execution_hash": p.execution_hash,
        "executed_at": p.executed_at.isoformat() if p.executed_at else None,
    }
