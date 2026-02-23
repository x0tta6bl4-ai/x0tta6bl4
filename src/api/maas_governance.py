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
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import GovernanceProposal, GovernanceVote, User, get_db
from src.api.maas_auth import get_current_user_from_maas, require_role
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/governance", tags=["MaaS Governance"])

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

def _execute_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("type", action.get("action_type", "unknown"))
    params = action.get("params", {})
    if action_type == "update_config":
        key = params.get("key", "")
        value = params.get("value")
        if key == "global_price_multiplier":
            logger.info("⚖️ DAO: Applying global price multiplier: %s", value)
            return {"action": action_type, "success": True, "detail": f"Multiplier {value} applied"}
        return {"action": action_type, "success": False, "detail": f"Unsupported config key: {key}"}
    if action_type == "rotate_keys":
        return {"action": action_type, "success": True, "detail": "Key rotation scheduled"}
    if action_type == "update_price":
        return {"action": action_type, "success": True, "detail": f"Price updated: {params}"}
    return {"action": action_type, "success": False, "detail": "Unknown action type"}

def _tally(proposal: GovernanceProposal) -> Dict[str, float]:
    tally: Dict[str, float] = {"yes": 0.0, "no": 0.0, "abstain": 0.0}
    for v in proposal.votes:
        qv = (v.tokens / 100.0) ** 0.5
        tally[v.vote] = tally.get(v.vote, 0.0) + qv
    return tally

def _resolve_state(proposal: GovernanceProposal) -> str:
    if proposal.state == "executed": return "executed"
    if datetime.utcnow() < proposal.end_time: return "active"
    tally = _tally(proposal)
    return "passed" if tally["yes"] > tally["no"] else "rejected"

@router.post("/proposals")
async def create_maas_proposal(
    req: ProposalCreate,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    if current_user.plan not in ("pro", "enterprise"):
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
    return {"proposal_id": proposal_id, "status": "active", "expires_at": end_dt.isoformat()}

@router.post("/proposals/{proposal_id}/vote")
async def cast_maas_vote(
    proposal_id: str,
    req: VoteRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if _resolve_state(p) != "active":
        raise HTTPException(status_code=400, detail="Invalid proposal state")

    existing = db.query(GovernanceVote).filter(
        GovernanceVote.proposal_id == proposal_id,
        GovernanceVote.voter_id == current_user.id
    ).first()
    if existing:
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
):
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if p.state == "executed":
        raise HTTPException(status_code=400, detail="Proposal already executed")
    if _resolve_state(p) != "passed":
        raise HTTPException(status_code=400, detail="Proposal must be passed to execute")

    actions = json.loads(p.actions_json) if p.actions_json else []
    results = [_execute_action(a) for a in actions]
    finality_hash = _compute_finality_hash(p, results)
    
    # PQC-sign the finality hash to ensure non-repudiation
    from src.core.app import pqc_sign
    pqc_attestation = pqc_sign(finality_hash.encode()).hex()

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
    return {"status": "executed", "finality_hash": finality_hash, "pqc_attestation": pqc_attestation}

@router.get("/proposals")
async def list_proposals(db: Session = Depends(get_db)):
    rows = db.query(GovernanceProposal).order_by(GovernanceProposal.created_at.desc()).all()
    return {"proposals": [{"id": p.id, "title": p.title, "state": _resolve_state(p)} for p in rows]}

@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str, db: Session = Depends(get_db)):
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    state = _resolve_state(p)
    if state != p.state and p.state == "active":
        p.state = state
        db.commit()
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
