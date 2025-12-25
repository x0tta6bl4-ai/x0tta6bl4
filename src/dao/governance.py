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
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()

    def _get_initial_voting_power(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

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
        
        counts = proposal.vote_counts()
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
            # Get voting power (tokens) for this voter
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
        
        support = yes_weighted / total_weighted
        
        # Log quadratic voting metrics
        logger.info(
            f"Quadratic Voting tally for {proposal.id}: "
            f"YES={yes_weighted:.2f}, NO={no_weighted:.2f}, "
            f"Total={total_weighted:.2f}, Support={support:.1%}"
        )
        
        if support > proposal.threshold:
            proposal.state = ProposalState.PASSED
            logger.info(f"Proposal {proposal.id} PASSED ({support:.1%} weighted support)")
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)")

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
