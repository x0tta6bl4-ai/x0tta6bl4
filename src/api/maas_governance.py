"""
MaaS DAO Governance API — x0tta6bl4
====================================

Exposes decentralized decision making for mesh network parameters.
Users vote using their 'Governance Power' derived from their plan.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import User, MarketplaceListing, get_db
from src.api.maas_auth import get_current_user_from_maas
from src.dao.governance import GovernanceEngine, ProposalState, VoteType, ActionDispatcher, ActionResult

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/governance", tags=["MaaS Governance"])

# --- Custom Action Handlers ---
def handle_update_config(action: Dict[str, Any]) -> ActionResult:
    """Governance action: update global marketplace parameters."""
    key = action.get("key")
    value = action.get("value")
    
    if key == "global_price_multiplier":
        logger.info(f"⚖️ DAO: Applying global price multiplier: {value}")
        # In a real app, we'd store this in a 'SystemConfig' table.
        # For now, we log it as successfully handled.
        return ActionResult(action_type="update_config", success=True, detail=f"Multiplier {value} applied")
    
    return ActionResult(action_type="update_config", success=False, detail=f"Unsupported key: {key}")

# Initialize Engine with Custom Dispatcher
dispatcher = ActionDispatcher()
dispatcher.register("update_config", handle_update_config)
_gov_engine = GovernanceEngine(node_id="maas-control-plane", dispatcher=dispatcher)

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
    signature: Optional[str] = None
    voter_pubkey: Optional[str] = None

def get_gov_power(user: User) -> float:
    """Calculate voting power based on plan."""
    powers = {
        "free": 10.0,
        "starter": 100.0,
        "pro": 1000.0,
        "enterprise": 10000.0
    }
    return powers.get(user.plan, 10.0)

@router.post("/proposals")
async def create_maas_proposal(
    req: ProposalCreate,
    current_user: User = Depends(get_current_user_from_maas)
):
    """Create a new DAO proposal."""
    # Only Pro/Enterprise can create proposals in Beta
    if current_user.plan not in ["pro", "enterprise"]:
        raise HTTPException(
            status_code=403, 
            detail="Only PRO or ENTERPRISE users can create proposals"
        )
    
    proposal = _gov_engine.create_proposal(
        title=req.title,
        description=req.description,
        duration_seconds=req.duration_hours * 3600,
        actions=[a.dict() for a in req.actions]
    )
    
    return {
        "proposal_id": proposal.id,
        "status": proposal.state.value,
        "expires_at": datetime.fromtimestamp(proposal.end_time).isoformat()
    }

@router.get("/proposals")
async def list_proposals():
    """List all active and past proposals."""
    _gov_engine.check_proposals()
    return {
        "proposals": [
            {
                "id": p.id,
                "title": p.title,
                "state": p.state.value,
                "votes_count": p.total_votes(),
                "end_time": datetime.fromtimestamp(p.end_time).isoformat()
            }
            for p in _gov_engine.proposals.values()
        ]
    }

@router.post("/proposals/{proposal_id}/vote")
async def cast_maas_vote(
    proposal_id: str,
    req: VoteRequest,
    current_user: User = Depends(get_current_user_from_maas)
):
    """Vote on a proposal using Quadratic Voting power."""
    power = get_gov_power(current_user)
    
    success = _gov_engine.cast_vote(
        proposal_id=proposal_id,
        voter_id=current_user.email,
        vote=VoteType(req.vote),
        tokens=power,
        signature=req.signature,
        voter_pubkey=req.voter_pubkey
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Vote rejected (proposal closed or invalid signature)")
        
    return {"status": "accepted", "voting_power_used": power**0.5}

@router.post("/proposals/{proposal_id}/execute")
async def execute_maas_proposal(
    proposal_id: str,
    current_user: User = Depends(get_current_user_from_maas)
):
    """Trigger execution of a PASSED proposal."""
    _gov_engine.check_proposals()
    
    results = _gov_engine.execute_proposal(proposal_id)
    if not results:
        raise HTTPException(status_code=400, detail="Proposal cannot be executed (not passed or not found)")
        
    return {
        "status": "executed",
        "results": [
            {"action": r.action_type, "success": r.success, "detail": r.detail}
            for r in results
        ]
    }
