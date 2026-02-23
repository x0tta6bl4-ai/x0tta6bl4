"""
MaaS Signed Playbooks (Production) — x0tta6bl4
============================================

PQC-signed commands for agents with in-memory delivery queues and optional
SQLAlchemy persistence for audit/history.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import get_current_user_from_maas, require_permission
from src.api.maas_security import token_signer
from src.database import PlaybookAck, SignedPlaybook, User, get_db
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/playbooks", tags=["MaaS Playbooks"])

_playbook_store: Dict[str, Dict[str, Any]] = {}
_node_queues: Dict[str, List[str]] = {}
_playbook_acks: Dict[str, Dict[str, Dict[str, Any]]] = {}
_playbook_deliveries: Dict[str, Set[str]] = {}


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


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "add") and hasattr(db, "commit")


def _db_query_available(db: Any) -> bool:
    return _db_session_available(db) and hasattr(db, "query")


def _action_to_dict(action: Any) -> Dict[str, Any]:
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


def _is_expired(playbook: Dict[str, Any], now: datetime) -> bool:
    raw_expires = playbook.get("expires_at")
    if not raw_expires:
        return False
    if isinstance(raw_expires, datetime):
        expires_at = raw_expires
    else:
        expires_at = datetime.fromisoformat(str(raw_expires))
    return expires_at <= now


def _queue_playbook_for_targets(playbook_id: str, target_nodes: List[str]) -> None:
    delivered_nodes = _playbook_deliveries.get(playbook_id, set())
    for node_id in target_nodes:
        if node_id in delivered_nodes:
            continue
        queue = _node_queues.setdefault(node_id, [])
        if playbook_id not in queue:
            queue.append(playbook_id)


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


@router.post("/create", response_model=PlaybookCreateResponse)
async def create_playbook(
    mesh_id: str,
    req: PlaybookCreateRequest,
    current_user: User = Depends(require_permission("playbook:create")),
    db: Session = Depends(get_db),
):
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

    _playbook_store[playbook_id] = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "name": req.name,
        "payload": payload_json,
        "signature": signed_data["signature"],
        "algorithm": signed_data["algorithm"],
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
                signature=signed_data["signature"],
                algorithm=signed_data["algorithm"],
                expires_at=expires_at_dt,
            )
        )
        db.commit()

        _safe_record_audit(
            db,
            action="PLAYBOOK_CREATED",
            user_id=current_user.id,
            payload={"playbook_id": playbook_id, "mesh_id": mesh_id, "targets": req.target_nodes},
            status_code=201,
        )

    return PlaybookCreateResponse(
        playbook_id=playbook_id,
        name=req.name,
        payload=payload_json,
        signature=signed_data["signature"],
        algorithm=signed_data["algorithm"],
        expires_at=expires_at_dt.isoformat(),
    )


@router.get("/poll/{mesh_id}/{node_id}")
async def poll_playbooks(mesh_id: str, node_id: str, db: Session = Depends(get_db)):
    """Poll pending valid playbooks for a node."""
    _seed_store_from_db(mesh_id, db)
    now = datetime.utcnow()
    queue = list(_node_queues.get(node_id, []))

    deliverable: List[Dict[str, Any]] = []
    remaining: List[str] = []

    for playbook_id in queue:
        playbook = _playbook_store.get(playbook_id)
        if not playbook:
            continue
        if playbook.get("mesh_id") != mesh_id:
            remaining.append(playbook_id)
            continue
        if _is_expired(playbook, now):
            continue

        acked_in_memory = node_id in _playbook_acks.get(playbook_id, {})
        acked_in_db = _db_ack_exists(db, playbook_id, node_id)
        if acked_in_memory or acked_in_db:
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
    return {"playbooks": deliverable}


@router.post("/ack/{playbook_id}/{node_id}")
async def acknowledge_playbook(
    playbook_id: str,
    node_id: str,
    status: str = "completed",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Acknowledge playbook execution. Persists to DB for audit trail."""
    now = datetime.utcnow()
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
    return {"status": "received", "playbook_id": playbook_id, "node_id": node_id}


@router.get("/list/{mesh_id}")
async def list_playbooks(
    mesh_id: str,
    current_user: User = Depends(require_permission("playbook:view")),
    db: Session = Depends(get_db),
):
    """Audit log of playbooks for a mesh."""
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

    return rows


@router.get("/status/{playbook_id}")
async def get_playbook_status(
    playbook_id: str,
    current_user: User = Depends(require_permission("playbook:view")),
    db: Session = Depends(get_db),
):
    """Get execution status across all target nodes for a playbook."""
    playbook = _playbook_store.get(playbook_id)
    if not playbook and _db_query_available(db):
        db_row = db.query(SignedPlaybook).filter(SignedPlaybook.id == playbook_id).first()
        if db_row:
            playbook = {
                "playbook_id": db_row.id,
                "name": db_row.name,
            }

    if not playbook:
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

    return {
        "playbook_id": playbook_id,
        "name": playbook.get("name", ""),
        "node_statuses": node_statuses,
        "total_acks": len(node_statuses),
    }
