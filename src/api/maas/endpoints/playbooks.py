"""
MaaS Signed Playbooks (Production) — x0tta6bl4
============================================

PQC-signed commands for agents with in-memory delivery queues and optional
SQLAlchemy persistence for audit/history.
"""

import json
import logging
import uuid
import hashlib
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.cross_plane_claim_gate import readiness_cross_plane_claim_gate_metadata
from src.api.maas_auth import require_permission
from src.api.maas_security import token_signer
from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.reliability_policy import mark_degraded_dependency
from src.database import PlaybookAck, SignedPlaybook, User, get_db
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter( tags=["MaaS Playbooks"])

_playbook_store: Dict[str, Dict[str, Any]] = {}
_node_queues: Dict[str, List[str]] = {}
_playbook_acks: Dict[str, Dict[str, Dict[str, Any]]] = {}
_playbook_deliveries: Dict[str, Set[str]] = {}
_ALLOWED_ACK_STATUSES = {"completed", "failed", "partial"}
_PLAYBOOK_CREATE_SOURCE_AGENT = "maas-playbooks-create"
_PLAYBOOK_CREATE_LAYER = "api_playbook_signed_command_control"
_PLAYBOOK_POLL_SOURCE_AGENT = "maas-playbooks-poll"
_PLAYBOOK_POLL_LAYER = "api_playbook_signed_command_dispatch"
_PLAYBOOK_ACK_SOURCE_AGENT = "maas-playbooks-ack"
_PLAYBOOK_ACK_LAYER = "api_playbook_ack_control"
_PLAYBOOK_LIST_SOURCE_AGENT = "maas-playbooks-list-read"
_PLAYBOOK_LIST_LAYER = "api_playbook_observed_state"
_PLAYBOOK_STATUS_SOURCE_AGENT = "maas-playbooks-status-read"
_PLAYBOOK_STATUS_LAYER = "api_playbook_observed_state"
_PLAYBOOK_CLAIM_BOUNDARY = (
    "MaaS playbook evidence records bounded local signed-command metadata from "
    "token_signer, in-memory queues, SignedPlaybook/PlaybookAck rows, and audit-log "
    "surfaces. It does not expose raw emails, user IDs, mesh IDs, node IDs, "
    "playbook IDs, playbook names, payloads, signatures, action params, join tokens, "
    "API keys, session tokens, or prove that target agents executed the command."
)


class PlaybookAction(BaseModel):
    action: str = Field(..., pattern="^(restart|upgrade|update_config|exec|ban_peer)$")
    params: Dict[str, Any] = Field(default_factory=dict)


class PlaybookCreateRequest(BaseModel):
    name: str = Field(..., min_length=3)
    target_nodes: List[str] = Field(..., min_length=1)
    actions: List[PlaybookAction] = Field(..., min_length=1)
    expires_in_sec: int = Field(default=3600, ge=60, le=86400)


class PlaybookCreateResponse(BaseModel):
    playbook_id: str
    name: str
    payload: str
    signature: str
    algorithm: str
    expires_at: str


def _redacted_sha256_prefix(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _playbook_event_bus_from_request(request: Request | None) -> EventBus | None:
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
        logger.error("Failed to initialize MaaS playbooks EventBus: %s", exc)
        return None


def _playbook_actor_summary(user: Any) -> Dict[str, Any]:
    if user is None:
        return {
            "actor_user_id_hash": None,
            "actor_email_hash": None,
            "actor_email_present": False,
            "actor_role": "",
        }
    email = str(getattr(user, "email", "") or "").strip().lower()
    return {
        "actor_user_id_hash": _redacted_sha256_prefix(getattr(user, "id", None)),
        "actor_email_hash": _redacted_sha256_prefix(email),
        "actor_email_present": bool(email),
        "actor_role": str(getattr(user, "role", "") or "")[:40],
    }


def _algorithm_bucket(value: Any) -> str:
    algorithm = str(value or "").upper()
    if algorithm.startswith("ML-DSA"):
        return "ML-DSA"
    if algorithm.startswith("HMAC"):
        return "HMAC"
    if not algorithm:
        return "missing"
    return "other"


def _ack_status_bucket(value: Any) -> str:
    status = str(value or "").strip().lower()
    return status if status in _ALLOWED_ACK_STATUSES else "other"


def _action_counts(actions: list[Any] | None) -> Dict[str, int]:
    counts = {
        "restart": 0,
        "upgrade": 0,
        "update_config": 0,
        "exec": 0,
        "ban_peer": 0,
        "other": 0,
    }
    for action in actions or []:
        name = action.action if isinstance(action, PlaybookAction) else getattr(action, "action", "")
        key = str(name or "").strip()
        if key in counts and key != "other":
            counts[key] += 1
        else:
            counts["other"] += 1
    return counts


def _publish_playbook_event(
    request: Request | None,
    *,
    source_agent: str,
    layer: str,
    stage: str,
    operation: str,
    status: str,
    current_user: Any = None,
    mesh_id: Any = None,
    node_id: Any = None,
    playbook_id: Any = None,
    target_nodes: list[str] | None = None,
    actions: list[Any] | None = None,
    algorithm: Any = None,
    ack_status: Any = None,
    queue_depth_before: int | None = None,
    queue_depth_after: int | None = None,
    deliverable_count: int | None = None,
    skipped_invalid_signature_count: int = 0,
    skipped_expired_count: int = 0,
    skipped_acknowledged_count: int = 0,
    skipped_wrong_mesh_count: int = 0,
    playbook_count: int | None = None,
    ack_count: int | None = None,
    db_backed: bool | None = None,
    audit_log_attempted: bool = False,
    signature_present: bool | None = None,
    http_status_code: int | None = None,
    duration_ms: float = 0.0,
    reason: str = "",
) -> str | None:
    event_bus = _playbook_event_bus_from_request(request)
    if event_bus is None:
        return None

    target_list = list(target_nodes or [])
    payload = {
        "component": "api.maas_playbooks",
        "stage": stage,
        "operation": operation,
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "status": str(status or "")[:40],
        "duration_ms": round(duration_ms, 3),
        **_playbook_actor_summary(current_user),
        "mesh_id_hash": _redacted_sha256_prefix(mesh_id),
        "node_id_hash": _redacted_sha256_prefix(node_id),
        "playbook_id_hash": _redacted_sha256_prefix(playbook_id),
        "target_count": len(target_list),
        "target_hashes": [_redacted_sha256_prefix(node) for node in target_list[:20]],
        "action_counts": _action_counts(actions),
        "algorithm_bucket": _algorithm_bucket(algorithm),
        "ack_status_bucket": _ack_status_bucket(ack_status),
        "queue_depth_before": queue_depth_before,
        "queue_depth_after": queue_depth_after,
        "deliverable_count": deliverable_count,
        "skipped_invalid_signature_count": max(0, int(skipped_invalid_signature_count)),
        "skipped_expired_count": max(0, int(skipped_expired_count)),
        "skipped_acknowledged_count": max(0, int(skipped_acknowledged_count)),
        "skipped_wrong_mesh_count": max(0, int(skipped_wrong_mesh_count)),
        "playbook_count": playbook_count,
        "ack_count": ack_count,
        "db_backed": db_backed,
        "audit_log_attempted": audit_log_attempted,
        "signature_present": signature_present,
        "http_status_code": http_status_code,
        "read_only": source_agent in {
            _PLAYBOOK_LIST_SOURCE_AGENT,
            _PLAYBOOK_STATUS_SOURCE_AGENT,
        },
        "observed_state": source_agent in {
            _PLAYBOOK_LIST_SOURCE_AGENT,
            _PLAYBOOK_STATUS_SOURCE_AGENT,
        },
        "safe_actuator": False,
        "control_action": source_agent in {
            _PLAYBOOK_CREATE_SOURCE_AGENT,
            _PLAYBOOK_POLL_SOURCE_AGENT,
            _PLAYBOOK_ACK_SOURCE_AGENT,
        },
        "raw_identifiers_redacted": True,
        "raw_credentials_redacted": True,
        "reason": str(reason or "")[:160],
        "claim_boundary": _PLAYBOOK_CLAIM_BOUNDARY,
    }
    try:
        event = event_bus.publish(
            EventType.PIPELINE_STAGE_END,
            source_agent,
            payload,
            priority=5,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish MaaS playbook event: %s", exc)
        return None


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "add") and hasattr(db, "commit")


def _db_query_available(db: Any) -> bool:
    return _db_session_available(db) and hasattr(db, "query")


def _memory_queue_available() -> bool:
    return (
        isinstance(_playbook_store, dict)
        and isinstance(_node_queues, dict)
        and isinstance(_playbook_acks, dict)
        and isinstance(_playbook_deliveries, dict)
    )


def _token_signer_available() -> bool:
    return (
        callable(getattr(token_signer, "sign_token", None))
        and callable(getattr(token_signer, "verify_token", None))
    )


def _playbook_readiness_status(db: Any) -> Dict[str, Any]:
    memory_queue_ready = _memory_queue_available()
    token_signer_ready = _token_signer_available()
    playbook_db_ready = _db_query_available(db)
    audit_log_ready = _db_session_available(db) and callable(record_audit_log)
    playbook_dispatch_ready = memory_queue_ready and token_signer_ready
    persistent_playbook_ready = playbook_db_ready and audit_log_ready
    playbook_control_plane_ready = playbook_dispatch_ready and persistent_playbook_ready

    degraded_dependencies = []
    if not memory_queue_ready:
        degraded_dependencies.append("in_memory_playbook_queue")
    if not token_signer_ready:
        degraded_dependencies.append("token_signer")
    if not playbook_db_ready:
        degraded_dependencies.append("database")
    if not audit_log_ready:
        degraded_dependencies.append("audit_log")

    queue_depth = (
        sum(len(queue) for queue in _node_queues.values())
        if isinstance(_node_queues, dict)
        else 0
    )

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "playbook_control_plane_ready": playbook_control_plane_ready,
        "playbook_dispatch_ready": playbook_dispatch_ready,
        "persistent_playbook_ready": persistent_playbook_ready,
        "memory_queue_ready": memory_queue_ready,
        "token_signer_ready": token_signer_ready,
        "playbook_db_ready": playbook_db_ready,
        "audit_log_ready": audit_log_ready,
        "queue_depth": queue_depth,
        "cached_playbooks": len(_playbook_store),
        "pending_ack_sets": len(_playbook_acks),
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "in_memory_playbook_queue": (
                "Node polling uses in-memory playbook queues for immediate delivery."
            ),
            "token_signer": (
                "Playbooks must be signed and verified before agents execute them."
            ),
            "database": (
                "SignedPlaybook and PlaybookAck rows provide durable command "
                "history, polling seed state, and acknowledgement lookup."
            ),
            "audit_log": (
                "PLAYBOOK_CREATED audit records are persisted only when a "
                "database-backed audit path is available."
            ),
        },
        "cross_plane_claim_gate": readiness_cross_plane_claim_gate_metadata(
            surface="maas_playbook_readiness"
        ),
        "claim_boundary": (
            "Playbook readiness distinguishes route availability from signed "
            "command dispatch, in-memory queue state, durable playbook history, "
            "and acknowledgement persistence. It does not prove that agents are "
            "online, that a specific node has polled, or that PQC rather than "
            "HMAC fallback was used for a specific playbook."
        ),
    }


def _action_to_dict(action: Any) -> Dict[str, Any]:
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


def _is_expired(playbook: Dict[str, Any], now: datetime) -> bool:
    raw_expires = playbook.get("expires_at")
    if not raw_expires:
        return False
    try:
        if isinstance(raw_expires, datetime):
            expires_at = raw_expires
        else:
            expires_at = datetime.fromisoformat(str(raw_expires))
        return expires_at <= now
    except Exception:
        # Fail closed on malformed expiry data.
        return True


def _queue_playbook_for_targets(playbook_id: str, target_nodes: List[str]) -> None:
    delivered_nodes = _playbook_deliveries.get(playbook_id, set())
    for node_id in target_nodes:
        if node_id in delivered_nodes:
            continue
        queue = _node_queues.setdefault(node_id, [])
        if playbook_id not in queue:
            queue.append(playbook_id)


def _normalize_target_nodes(raw_nodes: Any) -> List[str]:
    if not isinstance(raw_nodes, list):
        return []
    return [str(node) for node in raw_nodes if isinstance(node, str) and node]


def _get_playbook(playbook_id: str, db: Any) -> Dict[str, Any] | None:
    cached = _playbook_store.get(playbook_id)
    if cached:
        return cached

    if not _db_query_available(db):
        return None

    row = db.query(SignedPlaybook).filter(SignedPlaybook.id == playbook_id).first()
    if not row:
        return None

    payload_obj: Dict[str, Any] = {}
    try:
        payload_obj = json.loads(row.payload or "{}")
    except Exception:
        payload_obj = {}

    playbook = {
        "playbook_id": row.id,
        "mesh_id": row.mesh_id,
        "name": row.name,
        "payload": row.payload,
        "signature": row.signature,
        "algorithm": row.algorithm,
        "target_nodes": _normalize_target_nodes(payload_obj.get("target_nodes", [])),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
    }
    _playbook_store[playbook_id] = playbook
    return playbook


def _has_valid_signature(playbook: Dict[str, Any]) -> bool:
    payload = str(playbook.get("payload", ""))
    mesh_id = str(playbook.get("mesh_id", ""))
    signature = str(playbook.get("signature", "")).strip()
    algorithm = str(playbook.get("algorithm", "")).upper()

    if not payload or not mesh_id or not signature:
        return False

    if algorithm.startswith("HMAC"):
        try:
            return token_signer.verify_token(payload, mesh_id, signature)
        except Exception as exc:
            logger.warning("Playbook HMAC verification failed: %s", exc)
            return False

    if algorithm.startswith("ML-DSA"):
        try:
            token_signer._init_pqc()
            pqc_signer = getattr(token_signer, "_pqc_signer", None)
            signing_keypair = getattr(token_signer, "_signing_keypair", None)
            if not pqc_signer or not signing_keypair:
                return False
            signed_payload = f"{mesh_id}:{payload}".encode()
            return pqc_signer.verify(
                signed_payload,
                bytes.fromhex(signature),
                signing_keypair.public_key,
            )
        except Exception as exc:
            logger.warning("Playbook ML-DSA verification failed: %s", exc)
            return False

    # Fail closed for unknown algorithms.
    return False


def _seed_store_from_db(mesh_id: str, db: Any) -> None:
    if not _db_query_available(db):
        return

    now = datetime.utcnow()
    rows = db.query(SignedPlaybook).filter(
        SignedPlaybook.mesh_id == mesh_id,
        SignedPlaybook.expires_at > now,
    ).all()

    for row in rows:
        if row.id not in _playbook_store:
            payload = json.loads(row.payload)
            _playbook_store[row.id] = {
                "playbook_id": row.id,
                "mesh_id": row.mesh_id,
                "name": row.name,
                "payload": row.payload,
                "signature": row.signature,
                "algorithm": row.algorithm,
                "target_nodes": payload.get("target_nodes", []),
                "created_at": payload.get("created_at"),
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            }

        target_nodes = _playbook_store[row.id].get("target_nodes", [])
        if isinstance(target_nodes, list):
            _queue_playbook_for_targets(row.id, target_nodes)


def _db_ack_exists(db: Any, playbook_id: str, node_id: str) -> bool:
    if not _db_query_available(db):
        return False
    existing = db.query(PlaybookAck).filter(
        PlaybookAck.playbook_id == playbook_id,
        PlaybookAck.node_id == node_id,
    ).first()
    return existing is not None


def _safe_record_audit(
    db: Any,
    *,
    action: str,
    user_id: str,
    payload: Dict[str, Any],
    status_code: int,
) -> None:
    if not _db_session_available(db):
        return
    try:
        record_audit_log(
            db, None, action,
            user_id=user_id,
            payload=payload,
            status_code=status_code,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist audit log (%s): %s", action, exc)


@router.get("/readiness")
async def playbook_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _playbook_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


@router.post("/create", response_model=PlaybookCreateResponse)
async def create_playbook(
    mesh_id: str,
    req: PlaybookCreateRequest,
    current_user: User = Depends(require_permission("playbook:create")),
    db: Session = Depends(get_db),
    request: Request = None,
):
    started = time.monotonic()
    playbook_id = f"pbk-{uuid.uuid4().hex[:8]}"
    expires_at_dt = datetime.utcnow() + timedelta(seconds=req.expires_in_sec)
    actions_payload = [_action_to_dict(action) for action in req.actions]
    payload_data = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "actions": actions_payload,
        "target_nodes": req.target_nodes,
        "created_at": datetime.utcnow().isoformat(),
    }
    payload_json = json.dumps(payload_data, sort_keys=True)
    signed_data = token_signer.sign_token(payload_json, mesh_id)
    # Validate signature is present - required for security
    if not signed_data or "signature" not in signed_data:
        _publish_playbook_event(
            request,
            source_agent=_PLAYBOOK_CREATE_SOURCE_AGENT,
            layer=_PLAYBOOK_CREATE_LAYER,
            stage="playbook_create_control",
            operation="maas_playbook_create",
            status="failed",
            current_user=current_user,
            mesh_id=mesh_id,
            playbook_id=playbook_id,
            target_nodes=req.target_nodes,
            actions=list(req.actions),
            signature_present=False,
            db_backed=_db_session_available(db),
            http_status_code=500,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="missing_signature",
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate playbook signature",
        )
    signature_val = str(signed_data.get("signature", ""))
    algorithm_val = str(signed_data.get("algorithm", "HMAC-SHA256"))

    _playbook_store[playbook_id] = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "name": req.name,
        "payload": payload_json,
        "signature": signature_val,
        "algorithm": algorithm_val,
        "target_nodes": list(req.target_nodes),
        "created_at": payload_data["created_at"],
        "expires_at": expires_at_dt.isoformat(),
    }
    _queue_playbook_for_targets(playbook_id, req.target_nodes)

    if _db_session_available(db):
        db.add(
            SignedPlaybook(
                id=playbook_id,
                mesh_id=mesh_id,
                name=req.name,
                payload=payload_json,
                signature=signature_val,
                algorithm=algorithm_val,
                expires_at=expires_at_dt,
            )
        )
        db.commit()

        audit_attempted = True
        _safe_record_audit(
            db,
            action="PLAYBOOK_CREATED",
            user_id=current_user.id,
            payload={"playbook_id": playbook_id, "mesh_id": mesh_id, "targets": req.target_nodes},
            status_code=201,
        )
    else:
        audit_attempted = False

    _publish_playbook_event(
        request,
        source_agent=_PLAYBOOK_CREATE_SOURCE_AGENT,
        layer=_PLAYBOOK_CREATE_LAYER,
        stage="playbook_create_control",
        operation="maas_playbook_create",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        playbook_id=playbook_id,
        target_nodes=req.target_nodes,
        actions=list(req.actions),
        algorithm=algorithm_val,
        queue_depth_after=sum(len(queue) for queue in _node_queues.values()),
        db_backed=_db_session_available(db),
        audit_log_attempted=audit_attempted,
        signature_present=bool(signature_val),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="signed_playbook_create",
    )

    return PlaybookCreateResponse(
        playbook_id=playbook_id,
        name=req.name,
        payload=payload_json,
        signature=signature_val,
        algorithm=algorithm_val,
        expires_at=expires_at_dt.isoformat(),
    )


@router.get("/poll/{mesh_id}/{node_id}")
async def poll_playbooks(
    mesh_id: str,
    node_id: str,
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Poll pending valid playbooks for a node."""
    started = time.monotonic()
    _seed_store_from_db(mesh_id, db)
    now = datetime.utcnow()
    queue = list(_node_queues.get(node_id, []))
    queue_depth_before = len(queue)
    skipped_invalid_signature_count = 0
    skipped_expired_count = 0
    skipped_acknowledged_count = 0
    skipped_wrong_mesh_count = 0

    deliverable: List[Dict[str, Any]] = []
    remaining: List[str] = []

    for playbook_id in queue:
        playbook = _get_playbook(playbook_id, db)
        if not playbook:
            continue
        if playbook.get("mesh_id") != mesh_id:
            skipped_wrong_mesh_count += 1
            remaining.append(playbook_id)
            continue
        targets = _normalize_target_nodes(playbook.get("target_nodes", []))
        if targets and node_id not in targets:
            continue
        if not _has_valid_signature(playbook):
            skipped_invalid_signature_count += 1
            logger.warning("Skipping playbook with invalid signature: %s", playbook_id)
            continue
        if _is_expired(playbook, now):
            skipped_expired_count += 1
            continue

        acked_in_memory = node_id in _playbook_acks.get(playbook_id, {})
        acked_in_db = _db_ack_exists(db, playbook_id, node_id)
        if acked_in_memory or acked_in_db:
            skipped_acknowledged_count += 1
            continue

        deliverable.append(
            {
                "playbook_id": playbook_id,
                "payload": playbook["payload"],
                "signature": playbook["signature"],
                "algorithm": playbook["algorithm"],
                "expires_at": playbook["expires_at"],
            }
        )
        _playbook_deliveries.setdefault(playbook_id, set()).add(node_id)
        # Pop on delivery: do not append back to remaining.

    _node_queues[node_id] = remaining
    _publish_playbook_event(
        request,
        source_agent=_PLAYBOOK_POLL_SOURCE_AGENT,
        layer=_PLAYBOOK_POLL_LAYER,
        stage="playbook_poll_dispatch",
        operation="maas_playbook_poll",
        status="success",
        mesh_id=mesh_id,
        node_id=node_id,
        queue_depth_before=queue_depth_before,
        queue_depth_after=len(remaining),
        deliverable_count=len(deliverable),
        skipped_invalid_signature_count=skipped_invalid_signature_count,
        skipped_expired_count=skipped_expired_count,
        skipped_acknowledged_count=skipped_acknowledged_count,
        skipped_wrong_mesh_count=skipped_wrong_mesh_count,
        db_backed=_db_query_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="node_poll_delivery",
    )
    return {"playbooks": deliverable}


@router.post("/ack/{playbook_id}/{node_id}")
async def acknowledge_playbook(
    playbook_id: str,
    node_id: str,
    status: str = Query(default="completed", pattern="^(completed|failed|partial)$"),
    db: Session = Depends(get_db),
    request: Request = None,
) -> Dict[str, Any]:
    """Acknowledge playbook execution. Persists to DB for audit trail."""
    started = time.monotonic()
    now = datetime.utcnow()
    playbook = _get_playbook(playbook_id, db)
    if not playbook:
        _publish_playbook_event(
            request,
            source_agent=_PLAYBOOK_ACK_SOURCE_AGENT,
            layer=_PLAYBOOK_ACK_LAYER,
            stage="playbook_ack_control",
            operation="maas_playbook_ack",
            status="denied",
            playbook_id=playbook_id,
            node_id=node_id,
            ack_status=status,
            db_backed=_db_query_available(db),
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="playbook_not_found",
        )
        raise HTTPException(status_code=404, detail="Playbook not found")
    if _is_expired(playbook, now):
        _publish_playbook_event(
            request,
            source_agent=_PLAYBOOK_ACK_SOURCE_AGENT,
            layer=_PLAYBOOK_ACK_LAYER,
            stage="playbook_ack_control",
            operation="maas_playbook_ack",
            status="denied",
            mesh_id=playbook.get("mesh_id"),
            playbook_id=playbook_id,
            node_id=node_id,
            ack_status=status,
            db_backed=_db_query_available(db),
            http_status_code=410,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="playbook_expired",
        )
        raise HTTPException(status_code=410, detail="Playbook expired")

    targets = _normalize_target_nodes(playbook.get("target_nodes", []))
    if targets and node_id not in targets:
        _publish_playbook_event(
            request,
            source_agent=_PLAYBOOK_ACK_SOURCE_AGENT,
            layer=_PLAYBOOK_ACK_LAYER,
            stage="playbook_ack_control",
            operation="maas_playbook_ack",
            status="denied",
            mesh_id=playbook.get("mesh_id"),
            playbook_id=playbook_id,
            node_id=node_id,
            target_nodes=targets,
            ack_status=status,
            db_backed=_db_query_available(db),
            http_status_code=403,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="node_not_targeted",
        )
        raise HTTPException(status_code=403, detail="Node is not a target for this playbook")

    if status not in _ALLOWED_ACK_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid playbook ack status")

    _playbook_acks.setdefault(playbook_id, {})[node_id] = {
        "status": status,
        "acknowledged_at": now.isoformat(),
    }
    _playbook_deliveries.setdefault(playbook_id, set()).add(node_id)

    if _db_query_available(db):
        existing = db.query(PlaybookAck).filter(
            PlaybookAck.playbook_id == playbook_id,
            PlaybookAck.node_id == node_id,
        ).first()
        if existing:
            existing.status = status
            existing.acknowledged_at = now
        else:
            db.add(
                PlaybookAck(
                    id=f"ack-{uuid.uuid4().hex[:8]}",
                    playbook_id=playbook_id,
                    node_id=node_id,
                    status=status,
                    acknowledged_at=now,
                )
            )
        db.commit()

    logger.info("Playbook %s ack from node %s: %s", playbook_id, node_id, status)
    _publish_playbook_event(
        request,
        source_agent=_PLAYBOOK_ACK_SOURCE_AGENT,
        layer=_PLAYBOOK_ACK_LAYER,
        stage="playbook_ack_control",
        operation="maas_playbook_ack",
        status="success",
        mesh_id=playbook.get("mesh_id"),
        playbook_id=playbook_id,
        node_id=node_id,
        target_nodes=targets,
        ack_status=status,
        db_backed=_db_query_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="playbook_acknowledged",
    )
    return {"status": "received", "playbook_id": playbook_id, "node_id": node_id}


@router.get("/list/{mesh_id}")
async def list_playbooks(
    mesh_id: str,
    current_user: User = Depends(require_permission("playbook:view")),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Audit log of playbooks for a mesh."""
    started = time.monotonic()
    rows: List[Dict[str, Any]] = []
    if _db_query_available(db):
        db_rows = db.query(SignedPlaybook).filter(SignedPlaybook.mesh_id == mesh_id).all()
        rows.extend(
            {
                "playbook_id": row.id,
                "name": row.name,
                "algorithm": row.algorithm,
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in db_rows
        )

    seen = {item["playbook_id"] for item in rows}
    for playbook in _playbook_store.values():
        if playbook.get("mesh_id") != mesh_id:
            continue
        playbook_id = playbook.get("playbook_id")
        if playbook_id in seen:
            continue
        rows.append(
            {
                "playbook_id": playbook_id,
                "name": playbook.get("name", ""),
                "algorithm": playbook.get("algorithm", ""),
                "expires_at": playbook.get("expires_at"),
                "created_at": playbook.get("created_at"),
            }
        )

    _publish_playbook_event(
        request,
        source_agent=_PLAYBOOK_LIST_SOURCE_AGENT,
        layer=_PLAYBOOK_LIST_LAYER,
        stage="playbook_list_read",
        operation="maas_playbook_list_read",
        status="success",
        current_user=current_user,
        mesh_id=mesh_id,
        playbook_count=len(rows),
        db_backed=_db_query_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="playbook_list_read",
    )
    return rows


@router.get("/status/{playbook_id}")
async def get_playbook_status(
    playbook_id: str,
    current_user: User = Depends(require_permission("playbook:view")),
    db: Session = Depends(get_db),
    request: Request = None,
):
    """Get execution status across all target nodes for a playbook."""
    started = time.monotonic()
    playbook = _playbook_store.get(playbook_id)
    if not playbook and _db_query_available(db):
        db_row = db.query(SignedPlaybook).filter(SignedPlaybook.id == playbook_id).first()
        if db_row:
            playbook = {
                "playbook_id": db_row.id,
                "name": db_row.name,
            }

    if not playbook:
        _publish_playbook_event(
            request,
            source_agent=_PLAYBOOK_STATUS_SOURCE_AGENT,
            layer=_PLAYBOOK_STATUS_LAYER,
            stage="playbook_status_read",
            operation="maas_playbook_status_read",
            status="denied",
            current_user=current_user,
            playbook_id=playbook_id,
            db_backed=_db_query_available(db),
            http_status_code=404,
            duration_ms=(time.monotonic() - started) * 1000.0,
            reason="playbook_not_found",
        )
        raise HTTPException(status_code=404, detail="Playbook not found")

    node_statuses: Dict[str, Dict[str, Any]] = {}
    if _db_query_available(db):
        rows = db.query(PlaybookAck).filter(PlaybookAck.playbook_id == playbook_id).all()
        for row in rows:
            node_statuses[row.node_id] = {
                "status": row.status,
                "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
            }

    memory_statuses = _playbook_acks.get(playbook_id, {})
    node_statuses.update(memory_statuses)

    _publish_playbook_event(
        request,
        source_agent=_PLAYBOOK_STATUS_SOURCE_AGENT,
        layer=_PLAYBOOK_STATUS_LAYER,
        stage="playbook_status_read",
        operation="maas_playbook_status_read",
        status="success",
        current_user=current_user,
        playbook_id=playbook_id,
        ack_count=len(node_statuses),
        db_backed=_db_query_available(db),
        http_status_code=200,
        duration_ms=(time.monotonic() - started) * 1000.0,
        reason="playbook_status_read",
    )
    return {
        "playbook_id": playbook_id,
        "name": playbook.get("name", ""),
        "node_statuses": node_statuses,
        "total_acks": len(node_statuses),
    }
