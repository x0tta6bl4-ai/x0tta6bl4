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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/governance", tags=["MaaS Governance"])


# ---------------------------------------------------------------------------
# Voting power
# ---------------------------------------------------------------------------

def get_gov_power(user: User) -> float:
    """Quadratic voting power by plan."""
    powers = {"free": 10.0, "starter": 100.0, "pro": 1000.0, "enterprise": 10000.0}
    return powers.get(user.plan, 10.0)


# ---------------------------------------------------------------------------
# Finality hash
# ---------------------------------------------------------------------------

def _compute_finality_hash(proposal: GovernanceProposal, results: List[Dict]) -> str:
    """
    Compute a tamper-evident SHA-256 hash anchoring the governance decision.

    Hash inputs (deterministic):
      - proposal_id
      - sorted vote records: [(voter_id, vote, tokens)]
      - execution results: [{"action": ..., "success": ...}]
    """
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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Action execution (same as before)
# ---------------------------------------------------------------------------

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
        logger.info("🔑 DAO: Key rotation triggered")
        return {"action": action_type, "success": True, "detail": "Key rotation scheduled"}

    if action_type == "update_price":
        logger.info("💰 DAO: Price update triggered")
        return {"action": action_type, "success": True, "detail": f"Price updated: {params}"}

    return {"action": action_type, "success": False, "detail": "Unknown action type"}


# ---------------------------------------------------------------------------
# Proposal state helpers
# ---------------------------------------------------------------------------

def _tally(proposal: GovernanceProposal) -> Dict[str, float]:
    """Return quadratic vote tallies {yes, no, abstain}."""
    tally: Dict[str, float] = {"yes": 0.0, "no": 0.0, "abstain": 0.0}
    for v in proposal.votes:
        qv = (v.tokens / 100.0) ** 0.5   # quadratic: sqrt(raw_power)
        tally[v.vote] = tally.get(v.vote, 0.0) + qv
    return tally


def _resolve_state(proposal: GovernanceProposal) -> str:
    """Resolve proposal state based on votes and deadline."""
    if proposal.state in ("executed",):
        return proposal.state
    if datetime.utcnow() < proposal.end_time and proposal.state == "active":
        return "active"
    if proposal.state == "active":
        tally = _tally(proposal)
        return "passed" if tally["yes"] > tally["no"] else "rejected"
    return proposal.state


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/proposals")
async def create_maas_proposal(
    req: ProposalCreate,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """Create a new DAO proposal (Pro/Enterprise only)."""
    if current_user.plan not in ("pro", "enterprise"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only PRO or ENTERPRISE users can create proposals",
        )

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

    logger.info("🏛️ Proposal %s created by %s", proposal_id, current_user.email)
    return {
        "proposal_id": proposal_id,
        "status": "active",
        "expires_at": end_dt.isoformat(),
    }


@router.get("/proposals")
async def list_proposals(db: Session = Depends(get_db)):
    """List all proposals with current state."""
    rows = db.query(GovernanceProposal).order_by(GovernanceProposal.created_at.desc()).all()
    result = []
    for p in rows:
        state = _resolve_state(p)
        if state != p.state and p.state == "active":
            p.state = state
            db.commit()
        tally = _tally(p)
        result.append({
            "id": p.id,
            "title": p.title,
            "state": state,
            "votes": tally,
            "votes_count": len(p.votes),
            "end_time": p.end_time.isoformat(),
        })
    return {"proposals": result}


@router.get("/proposals/{proposal_id}")
async def get_proposal(proposal_id: str, db: Session = Depends(get_db)):
    """Get full proposal details including vote breakdown."""
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")

    state = _resolve_state(p)
    if state != p.state and p.state == "active":
        p.state = state
        db.commit()

    tally = _tally(p)
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "state": state,
        "actions": json.loads(p.actions_json) if p.actions_json else [],
        "votes": tally,
        "votes_count": len(p.votes),
        "end_time": p.end_time.isoformat(),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "execution_hash": p.execution_hash,
        "executed_at": p.executed_at.isoformat() if p.executed_at else None,
    }


@router.post("/proposals/{proposal_id}/vote")
async def cast_maas_vote(
    proposal_id: str,
    req: VoteRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """Vote on an active proposal using quadratic voting."""
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if _resolve_state(p) != "active":
        raise HTTPException(status_code=400, detail="Proposal is not active")

    # One vote per user per proposal
    existing = (
        db.query(GovernanceVote)
        .filter(
            GovernanceVote.proposal_id == proposal_id,
            GovernanceVote.voter_id == current_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already voted on this proposal")

    power = get_gov_power(current_user)
    vote_row = GovernanceVote(
        id=f"vote-{uuid.uuid4().hex[:8]}",
        proposal_id=proposal_id,
        voter_id=current_user.id,
        vote=req.vote,
        tokens=int(power * 100),
    )
    db.add(vote_row)
    db.commit()

    logger.info("🗳️ Vote recorded: %s on %s (%s)", current_user.id, proposal_id, req.vote)
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
    """Execute a PASSED proposal and anchor the decision with a finality hash."""
    p = db.query(GovernanceProposal).filter(GovernanceProposal.id == proposal_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")

    state = _resolve_state(p)
    if state == "executed":
        raise HTTPException(status_code=400, detail="Proposal already executed")
    if state != "passed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute proposal in state '{state}' (must be 'passed')",
        )

    actions = json.loads(p.actions_json) if p.actions_json else []
    results = [_execute_action(a) for a in actions]

    finality_hash = _compute_finality_hash(p, results)

    p.state = "executed"
    p.execution_hash = finality_hash
    p.executed_at = datetime.utcnow()
    db.commit()

    logger.info(
        "⚖️ Proposal %s executed. Finality hash: %s", proposal_id, finality_hash
    )
    return {
        "status": "executed",
        "proposal_id": proposal_id,
        "finality_hash": finality_hash,
        "results": results,
    }
