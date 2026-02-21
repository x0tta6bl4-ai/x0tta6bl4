"""
MaaS Signed Playbooks (Production) — x0tta6bl4
============================================

PQC-signed commands for agents with in-memory delivery queues and optional
SQLAlchemy audit persistence.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import require_role, require_permission
from src.api.maas_security import token_signer
from src.database import PlaybookAck, SignedPlaybook, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/playbooks", tags=["MaaS Playbooks"])


# Backward-compatible in-memory stores used by direct-call unit tests.
_playbook_store: Dict[str, Dict[str, Any]] = {}
_node_queues: Dict[str, List[str]] = {}
_playbook_acks: Dict[str, Dict[str, Any]] = {}


class PlaybookAction(BaseModel):
    action: str = Field(..., pattern="^(restart|upgrade|update_config|exec|ban_peer)$")
    params: Dict[str, Any] = Field(default_factory=dict)


class PlaybookCreateRequest(BaseModel):
    name: str = Field(..., min_length=3)
    target_nodes: List[str] = Field(..., min_items=1)
    actions: List[PlaybookAction] = Field(..., min_items=1)
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


def _action_to_dict(action: PlaybookAction) -> Dict[str, Any]:
    if hasattr(action, "model_dump"):
        return action.model_dump()
    return action.dict()


@router.post("/create")
async def create_playbook(
    mesh_id: str,
    req: PlaybookCreateRequest,
    current_user: User = Depends(require_permission("playbook:create")),
    db: Session = Depends(get_db),
) -> PlaybookCreateResponse:
    playbook_id = f"pbk-{uuid.uuid4().hex[:8]}"
    expires_at = datetime.utcnow() + timedelta(seconds=req.expires_in_sec)

    payload_data = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "actions": [_action_to_dict(a) for a in req.actions],
        "target_nodes": req.target_nodes,
        "created_at": datetime.utcnow().isoformat(),
    }
    payload_json = json.dumps(payload_data, sort_keys=True)
    signed_data = token_signer.sign_token(payload_json, mesh_id)

    # In-memory store for agent delivery queue.
    record = {
        "playbook_id": playbook_id,
        "mesh_id": mesh_id,
        "name": req.name,
        "payload": payload_json,
        "signature": signed_data["signature"],
        "algorithm": signed_data["algorithm"],
        "target_nodes": list(req.target_nodes),
        "created_at": payload_data["created_at"],
        "expires_at": expires_at.isoformat(),
    }
    _playbook_store[playbook_id] = record
    for node_id in req.target_nodes:
        _node_queues.setdefault(node_id, []).append(playbook_id)

    # Persist for audit if a real DB session is provided.
    if _db_session_available(db):
        playbook = SignedPlaybook(
            id=playbook_id,
            mesh_id=mesh_id,
            name=req.name,
            payload=payload_json,
            signature=signed_data["signature"],
            algorithm=signed_data["algorithm"],
            expires_at=expires_at,
        )
        db.add(playbook)
        db.commit()

    actor = getattr(current_user, "email", "unknown")
    logger.info("📜 Signed playbook %s created by %s", playbook_id, actor)

    return PlaybookCreateResponse(
        playbook_id=playbook_id,
        name=req.name,
        payload=payload_json,
        signature=signed_data["signature"],
        algorithm=signed_data["algorithm"],
        expires_at=expires_at.isoformat(),
    )


@router.get("/poll/{mesh_id}/{node_id}")
async def poll_playbooks(mesh_id: str, node_id: str) -> Dict[str, Any]:
    """Poll pending playbooks for a node and pop delivered entries from queue."""
    queue = _node_queues.get(node_id, [])
    if not queue:
        return {"playbooks": []}

    now = datetime.utcnow()
    deliver: List[Dict[str, Any]] = []
    keep: List[str] = []

    for playbook_id in queue:
        pb = _playbook_store.get(playbook_id)
        if not pb:
            continue

        if pb.get("mesh_id") != mesh_id:
            keep.append(playbook_id)
            continue

        expires_at_raw = pb.get("expires_at")
        try:
            expires_at = datetime.fromisoformat(expires_at_raw) if expires_at_raw else now
        except ValueError:
            expires_at = now

        if expires_at <= now:
            continue

        deliver.append(
            {
                "playbook_id": pb["playbook_id"],
                "payload": pb["payload"],
                "signature": pb["signature"],
                "algorithm": pb["algorithm"],
                "expires_at": pb["expires_at"],
            }
        )

    _node_queues[node_id] = keep
    return {"playbooks": deliver}


@router.post("/ack/{playbook_id}/{node_id}")
async def acknowledge_playbook(
    playbook_id: str,
    node_id: str,
    status: str = "completed",
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Acknowledge playbook execution. Persists to DB for audit trail."""
    now = datetime.utcnow()

    # Update in-memory (fast path for same-process consumers)
    _playbook_acks.setdefault(playbook_id, {})[node_id] = {
        "status": status,
        "acknowledged_at": now.isoformat(),
    }

    # Persist to DB
    if _db_session_available(db):
        existing = (
            db.query(PlaybookAck)
            .filter(PlaybookAck.playbook_id == playbook_id, PlaybookAck.node_id == node_id)
            .first()
        )
        if existing:
            existing.status = status
            existing.acknowledged_at = now
        else:
            db.add(PlaybookAck(
                id=f"ack-{uuid.uuid4().hex[:8]}",
                playbook_id=playbook_id,
                node_id=node_id,
                status=status,
                acknowledged_at=now,
            ))
        db.commit()

    logger.info("✅ Playbook %s ack from node %s: %s", playbook_id, node_id, status)
    return {
        "status": "received",
        "playbook_id": playbook_id,
        "node_id": node_id,
    }


@router.get("/list/{mesh_id}")
async def list_playbooks(
    mesh_id: str,
    current_user: User = Depends(require_permission("playbook:view")),
    db: Session = Depends(get_db),
):
    """Audit log of playbooks for a mesh."""
    if _db_session_available(db) and hasattr(db, "query"):
        rows = db.query(SignedPlaybook).filter(SignedPlaybook.mesh_id == mesh_id).all()
        return [
            {
                "playbook_id": r.id,
                "name": r.name,
                "algorithm": r.algorithm,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    return [pb for pb in _playbook_store.values() if pb.get("mesh_id") == mesh_id]


@router.get("/status/{playbook_id}")
async def get_playbook_status(
    playbook_id: str,
    current_user: User = Depends(require_permission("playbook:view")),
    db: Session = Depends(get_db),
):
    """Get execution status across all target nodes for a playbook."""
    # Check DB first
    acks_db: Dict[str, Any] = {}
    if _db_session_available(db):
        rows = db.query(PlaybookAck).filter(PlaybookAck.playbook_id == playbook_id).all()
        for r in rows:
            acks_db[r.node_id] = {
                "status": r.status,
                "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
            }

    # Merge with in-memory (may have newer entries)
    acks_mem = _playbook_acks.get(playbook_id, {})
    merged = {**acks_db, **acks_mem}

    pb = _playbook_store.get(playbook_id)
    if not pb and _db_session_available(db):
        db_pb = db.query(SignedPlaybook).filter(SignedPlaybook.id == playbook_id).first()
        if db_pb:
            pb = {"playbook_id": db_pb.id, "name": db_pb.name}

    if not pb:
        raise HTTPException(status_code=404, detail="Playbook not found")

    return {
        "playbook_id": playbook_id,
        "name": pb.get("name", ""),
        "node_statuses": merged,
        "total_acks": len(merged),
    }
