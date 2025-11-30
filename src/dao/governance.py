"""
DAO Governance Module for x0tta6bl4.
Implements decentralized decision making via weighted voting.
"""
import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

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

class GovernanceEngine:
    """
    Manages proposals and voting for the Mesh DAO.
    """
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Mock token balances/voting power for now (1 node = 1 vote)
        self.voting_power: Dict[str, float] = {} 

    def create_proposal(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            start_time=now,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def cast_vote(self, proposal_id: str, voter_id: str, vote: VoteType) -> bool:
        """Cast a vote on a proposal."""
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
        if time.time() > proposal.end_time:
            self._tally_votes(proposal)
            logger.warning(f"Voting period ended for {proposal_id}")
            return False

        proposal.votes[voter_id] = vote
        logger.info(f"Vote cast by {voter_id} on {proposal_id}: {vote.value}")
        return True

    def check_proposals(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE and now > proposal.end_time:
                self._tally_votes(proposal)

    def _tally_votes(self, proposal: Proposal):
        """Tally votes and update proposal state."""
        counts = proposal.vote_counts()
        total = proposal.total_votes()
        
        # Simple 1-node-1-vote logic for now
        # In real DAO, we would sum weighted voting power
        
        # Check quorum (not implemented fully without total network size knowledge)
        # Assuming total network size is known or we just look at ratio
        
        if total == 0:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} rejected (no votes)")
            return

        support = counts[VoteType.YES] / total
        
        if support > proposal.threshold:
            proposal.state = ProposalState.PASSED
            logger.info(f"Proposal {proposal.id} PASSED ({support:.1%} support)")
            # Schedule execution?
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} support)")

    def execute_proposal(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.state != ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return False
            
        logger.info(f"Executing actions for {proposal_id}")
        for action in proposal.actions:
            logger.info(f"Action: {action}")
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True
