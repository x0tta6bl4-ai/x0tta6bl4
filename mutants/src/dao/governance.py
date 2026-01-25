"""
DAO Governance Module for x0tta6bl4.
Implements decentralized decision making via weighted voting.
Now with Quadratic Voting support.
"""
import logging
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.dao.quadratic_voting import QuadraticVoting, Vote

logger = logging.getLogger(__name__)
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result

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
    voter_tokens: Dict[str, float] = field(default_factory=dict)  # Quadratic voting: tokens per voter
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
    Now with Quadratic Voting support.
    """
    def xǁGovernanceEngineǁ__init____mutmut_orig(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = sum(self.voting_power.values())
    def xǁGovernanceEngineǁ__init____mutmut_1(self, node_id: str):
        self.node_id = None
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = sum(self.voting_power.values())
    def xǁGovernanceEngineǁ__init____mutmut_2(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = None
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = sum(self.voting_power.values())
    def xǁGovernanceEngineǁ__init____mutmut_3(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = None
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = sum(self.voting_power.values())
    def xǁGovernanceEngineǁ__init____mutmut_4(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = None
        # Total token supply (for quorum calculation)
        self.total_supply = sum(self.voting_power.values())
    def xǁGovernanceEngineǁ__init____mutmut_5(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = None
    def xǁGovernanceEngineǁ__init____mutmut_6(self, node_id: str):
        self.node_id = node_id
        self.proposals: Dict[str, Proposal] = {}
        # Initialize voting power from a simulated node list
        self.voting_power: Dict[str, float] = self._get_initial_voting_power()
        # Initialize Quadratic Voting
        self.quadratic_voting = QuadraticVoting()
        # Total token supply (for quorum calculation)
        self.total_supply = sum(None)
    
    xǁGovernanceEngineǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁ__init____mutmut_1': xǁGovernanceEngineǁ__init____mutmut_1, 
        'xǁGovernanceEngineǁ__init____mutmut_2': xǁGovernanceEngineǁ__init____mutmut_2, 
        'xǁGovernanceEngineǁ__init____mutmut_3': xǁGovernanceEngineǁ__init____mutmut_3, 
        'xǁGovernanceEngineǁ__init____mutmut_4': xǁGovernanceEngineǁ__init____mutmut_4, 
        'xǁGovernanceEngineǁ__init____mutmut_5': xǁGovernanceEngineǁ__init____mutmut_5, 
        'xǁGovernanceEngineǁ__init____mutmut_6': xǁGovernanceEngineǁ__init____mutmut_6
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁGovernanceEngineǁ__init____mutmut_orig)
    xǁGovernanceEngineǁ__init____mutmut_orig.__name__ = 'xǁGovernanceEngineǁ__init__'

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_orig(self) -> Dict[str, float]:
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

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_1(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "XXnode-1XX": 100.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_2(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "NODE-1": 100.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_3(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 101.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_4(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "XXnode-2XX": 150.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_5(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "NODE-2": 150.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_6(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 151.0,
            "node-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_7(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "XXnode-3XX": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_8(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "NODE-3": 80.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_9(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "node-3": 81.0,
            "node-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_10(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "XXnode-4XX": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_11(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "NODE-4": 200.0,
        }

    def xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_12(self) -> Dict[str, float]:
        """
        Gets initial voting power. In a real scenario, this would come from a
        token contract or a dynamic node registry. Here we simulate a few nodes.
        """
        # This is a more realistic mock than an empty dict
        return {
            "node-1": 100.0,
            "node-2": 150.0,
            "node-3": 80.0,
            "node-4": 201.0,
        }
    
    xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_1': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_1, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_2': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_2, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_3': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_3, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_4': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_4, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_5': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_5, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_6': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_6, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_7': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_7, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_8': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_8, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_9': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_9, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_10': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_10, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_11': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_11, 
        'xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_12': xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_12
    }
    
    def _get_initial_voting_power(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _get_initial_voting_power.__signature__ = _mutmut_signature(xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_orig)
    xǁGovernanceEngineǁ_get_initial_voting_power__mutmut_orig.__name__ = 'xǁGovernanceEngineǁ_get_initial_voting_power'

    def xǁGovernanceEngineǁcreate_proposal__mutmut_orig(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_1(self, title: str, description: str, duration_seconds: float = 3601, actions: List[Dict] = None) -> Proposal:
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_2(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = None
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_3(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(None)}_{self.node_id}"
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_4(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = None
        
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_5(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = None
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_6(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=None,
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_7(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=None,
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_8(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=None,
            proposer=self.node_id,
            start_time=now,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_9(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=None,
            start_time=now,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_10(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            start_time=None,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_11(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            start_time=now,
            end_time=None,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_12(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
            actions=None,
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_13(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
            state=None
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_14(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_15(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
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

    def xǁGovernanceEngineǁcreate_proposal__mutmut_16(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            proposer=self.node_id,
            start_time=now,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_17(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            start_time=now,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_18(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            end_time=now + duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_19(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            start_time=now,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_20(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_21(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
            )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_22(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
        """Create a new governance proposal."""
        proposal_id = f"prop_{int(time.time())}_{self.node_id}"
        now = time.time()
        
        proposal = Proposal(
            id=proposal_id,
            title=title,
            description=description,
            proposer=self.node_id,
            start_time=now,
            end_time=now - duration_seconds,
            actions=actions or [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_23(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
            actions=actions and [],
            state=ProposalState.ACTIVE
        )
        self.proposals[proposal_id] = proposal
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_24(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
        self.proposals[proposal_id] = None
        logger.info(f"Created proposal {proposal_id}: {title}")
        return proposal

    def xǁGovernanceEngineǁcreate_proposal__mutmut_25(self, title: str, description: str, duration_seconds: float = 3600, actions: List[Dict] = None) -> Proposal:
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
        logger.info(None)
        return proposal
    
    xǁGovernanceEngineǁcreate_proposal__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁcreate_proposal__mutmut_1': xǁGovernanceEngineǁcreate_proposal__mutmut_1, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_2': xǁGovernanceEngineǁcreate_proposal__mutmut_2, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_3': xǁGovernanceEngineǁcreate_proposal__mutmut_3, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_4': xǁGovernanceEngineǁcreate_proposal__mutmut_4, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_5': xǁGovernanceEngineǁcreate_proposal__mutmut_5, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_6': xǁGovernanceEngineǁcreate_proposal__mutmut_6, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_7': xǁGovernanceEngineǁcreate_proposal__mutmut_7, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_8': xǁGovernanceEngineǁcreate_proposal__mutmut_8, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_9': xǁGovernanceEngineǁcreate_proposal__mutmut_9, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_10': xǁGovernanceEngineǁcreate_proposal__mutmut_10, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_11': xǁGovernanceEngineǁcreate_proposal__mutmut_11, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_12': xǁGovernanceEngineǁcreate_proposal__mutmut_12, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_13': xǁGovernanceEngineǁcreate_proposal__mutmut_13, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_14': xǁGovernanceEngineǁcreate_proposal__mutmut_14, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_15': xǁGovernanceEngineǁcreate_proposal__mutmut_15, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_16': xǁGovernanceEngineǁcreate_proposal__mutmut_16, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_17': xǁGovernanceEngineǁcreate_proposal__mutmut_17, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_18': xǁGovernanceEngineǁcreate_proposal__mutmut_18, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_19': xǁGovernanceEngineǁcreate_proposal__mutmut_19, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_20': xǁGovernanceEngineǁcreate_proposal__mutmut_20, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_21': xǁGovernanceEngineǁcreate_proposal__mutmut_21, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_22': xǁGovernanceEngineǁcreate_proposal__mutmut_22, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_23': xǁGovernanceEngineǁcreate_proposal__mutmut_23, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_24': xǁGovernanceEngineǁcreate_proposal__mutmut_24, 
        'xǁGovernanceEngineǁcreate_proposal__mutmut_25': xǁGovernanceEngineǁcreate_proposal__mutmut_25
    }
    
    def create_proposal(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁcreate_proposal__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁcreate_proposal__mutmut_mutants"), args, kwargs, self)
        return result 
    
    create_proposal.__signature__ = _mutmut_signature(xǁGovernanceEngineǁcreate_proposal__mutmut_orig)
    xǁGovernanceEngineǁcreate_proposal__mutmut_orig.__name__ = 'xǁGovernanceEngineǁcreate_proposal'

    def xǁGovernanceEngineǁcast_vote__mutmut_orig(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

    def xǁGovernanceEngineǁcast_vote__mutmut_1(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 2.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

    def xǁGovernanceEngineǁcast_vote__mutmut_2(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id in self.proposals:
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

    def xǁGovernanceEngineǁcast_vote__mutmut_3(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(None)
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
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

    def xǁGovernanceEngineǁcast_vote__mutmut_4(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return True
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
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

    def xǁGovernanceEngineǁcast_vote__mutmut_5(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = None
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
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

    def xǁGovernanceEngineǁcast_vote__mutmut_6(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state == ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
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

    def xǁGovernanceEngineǁcast_vote__mutmut_7(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(None)
            return False
            
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

    def xǁGovernanceEngineǁcast_vote__mutmut_8(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return True
            
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

    def xǁGovernanceEngineǁcast_vote__mutmut_9(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
        if time.time() >= proposal.end_time:
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

    def xǁGovernanceEngineǁcast_vote__mutmut_10(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
        if time.time() > proposal.end_time:
            self._tally_votes(None)
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

    def xǁGovernanceEngineǁcast_vote__mutmut_11(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
        if proposal_id not in self.proposals:
            logger.warning(f"Unknown proposal: {proposal_id}")
            return False
            
        proposal = self.proposals[proposal_id]
        
        if proposal.state != ProposalState.ACTIVE:
            logger.warning(f"Voting closed for {proposal_id} (State: {proposal.state})")
            return False
            
        if time.time() > proposal.end_time:
            self._tally_votes(proposal)
            logger.warning(None)
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

    def xǁGovernanceEngineǁcast_vote__mutmut_12(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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
            return True

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

    def xǁGovernanceEngineǁcast_vote__mutmut_13(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = None
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_14(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = None  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_15(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(None, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_16(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, None)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_17(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_18(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, )  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_19(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(1.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_20(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = None
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_21(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(None) if tokens > 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_22(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens >= 0 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_23(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 1 else 0.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_24(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 1.0
        
        logger.info(
            f"Vote cast by {voter_id} on {proposal_id}: {vote.value} "
            f"(tokens={tokens:.1f}, voting_power={voting_power:.2f})"
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_25(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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

        # Record vote and tokens for quadratic voting
        proposal.votes[voter_id] = vote
        proposal.voter_tokens[voter_id] = max(0.0, tokens)  # Ensure non-negative
        
        # Calculate quadratic voting power for logging
        from math import sqrt
        voting_power = sqrt(tokens) if tokens > 0 else 0.0
        
        logger.info(
            None
        )
        return True

    def xǁGovernanceEngineǁcast_vote__mutmut_26(self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0) -> bool:
        """
        Cast a vote on a proposal with quadratic voting support.
        
        Args:
            proposal_id: ID of the proposal
            voter_id: ID of the voter
            vote: Vote type (YES, NO, ABSTAIN)
            tokens: Number of tokens held by voter (for quadratic voting)
        
        Returns:
            True if vote was recorded, False otherwise
        """
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
        return False
    
    xǁGovernanceEngineǁcast_vote__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁcast_vote__mutmut_1': xǁGovernanceEngineǁcast_vote__mutmut_1, 
        'xǁGovernanceEngineǁcast_vote__mutmut_2': xǁGovernanceEngineǁcast_vote__mutmut_2, 
        'xǁGovernanceEngineǁcast_vote__mutmut_3': xǁGovernanceEngineǁcast_vote__mutmut_3, 
        'xǁGovernanceEngineǁcast_vote__mutmut_4': xǁGovernanceEngineǁcast_vote__mutmut_4, 
        'xǁGovernanceEngineǁcast_vote__mutmut_5': xǁGovernanceEngineǁcast_vote__mutmut_5, 
        'xǁGovernanceEngineǁcast_vote__mutmut_6': xǁGovernanceEngineǁcast_vote__mutmut_6, 
        'xǁGovernanceEngineǁcast_vote__mutmut_7': xǁGovernanceEngineǁcast_vote__mutmut_7, 
        'xǁGovernanceEngineǁcast_vote__mutmut_8': xǁGovernanceEngineǁcast_vote__mutmut_8, 
        'xǁGovernanceEngineǁcast_vote__mutmut_9': xǁGovernanceEngineǁcast_vote__mutmut_9, 
        'xǁGovernanceEngineǁcast_vote__mutmut_10': xǁGovernanceEngineǁcast_vote__mutmut_10, 
        'xǁGovernanceEngineǁcast_vote__mutmut_11': xǁGovernanceEngineǁcast_vote__mutmut_11, 
        'xǁGovernanceEngineǁcast_vote__mutmut_12': xǁGovernanceEngineǁcast_vote__mutmut_12, 
        'xǁGovernanceEngineǁcast_vote__mutmut_13': xǁGovernanceEngineǁcast_vote__mutmut_13, 
        'xǁGovernanceEngineǁcast_vote__mutmut_14': xǁGovernanceEngineǁcast_vote__mutmut_14, 
        'xǁGovernanceEngineǁcast_vote__mutmut_15': xǁGovernanceEngineǁcast_vote__mutmut_15, 
        'xǁGovernanceEngineǁcast_vote__mutmut_16': xǁGovernanceEngineǁcast_vote__mutmut_16, 
        'xǁGovernanceEngineǁcast_vote__mutmut_17': xǁGovernanceEngineǁcast_vote__mutmut_17, 
        'xǁGovernanceEngineǁcast_vote__mutmut_18': xǁGovernanceEngineǁcast_vote__mutmut_18, 
        'xǁGovernanceEngineǁcast_vote__mutmut_19': xǁGovernanceEngineǁcast_vote__mutmut_19, 
        'xǁGovernanceEngineǁcast_vote__mutmut_20': xǁGovernanceEngineǁcast_vote__mutmut_20, 
        'xǁGovernanceEngineǁcast_vote__mutmut_21': xǁGovernanceEngineǁcast_vote__mutmut_21, 
        'xǁGovernanceEngineǁcast_vote__mutmut_22': xǁGovernanceEngineǁcast_vote__mutmut_22, 
        'xǁGovernanceEngineǁcast_vote__mutmut_23': xǁGovernanceEngineǁcast_vote__mutmut_23, 
        'xǁGovernanceEngineǁcast_vote__mutmut_24': xǁGovernanceEngineǁcast_vote__mutmut_24, 
        'xǁGovernanceEngineǁcast_vote__mutmut_25': xǁGovernanceEngineǁcast_vote__mutmut_25, 
        'xǁGovernanceEngineǁcast_vote__mutmut_26': xǁGovernanceEngineǁcast_vote__mutmut_26
    }
    
    def cast_vote(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁcast_vote__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁcast_vote__mutmut_mutants"), args, kwargs, self)
        return result 
    
    cast_vote.__signature__ = _mutmut_signature(xǁGovernanceEngineǁcast_vote__mutmut_orig)
    xǁGovernanceEngineǁcast_vote__mutmut_orig.__name__ = 'xǁGovernanceEngineǁcast_vote'

    def xǁGovernanceEngineǁcheck_proposals__mutmut_orig(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE and now > proposal.end_time:
                self._tally_votes(proposal)

    def xǁGovernanceEngineǁcheck_proposals__mutmut_1(self):
        """Check active proposals and close/tally them if time expired."""
        now = None
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE and now > proposal.end_time:
                self._tally_votes(proposal)

    def xǁGovernanceEngineǁcheck_proposals__mutmut_2(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE or now > proposal.end_time:
                self._tally_votes(proposal)

    def xǁGovernanceEngineǁcheck_proposals__mutmut_3(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state != ProposalState.ACTIVE and now > proposal.end_time:
                self._tally_votes(proposal)

    def xǁGovernanceEngineǁcheck_proposals__mutmut_4(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE and now >= proposal.end_time:
                self._tally_votes(proposal)

    def xǁGovernanceEngineǁcheck_proposals__mutmut_5(self):
        """Check active proposals and close/tally them if time expired."""
        now = time.time()
        for proposal in self.proposals.values():
            if proposal.state == ProposalState.ACTIVE and now > proposal.end_time:
                self._tally_votes(None)
    
    xǁGovernanceEngineǁcheck_proposals__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁcheck_proposals__mutmut_1': xǁGovernanceEngineǁcheck_proposals__mutmut_1, 
        'xǁGovernanceEngineǁcheck_proposals__mutmut_2': xǁGovernanceEngineǁcheck_proposals__mutmut_2, 
        'xǁGovernanceEngineǁcheck_proposals__mutmut_3': xǁGovernanceEngineǁcheck_proposals__mutmut_3, 
        'xǁGovernanceEngineǁcheck_proposals__mutmut_4': xǁGovernanceEngineǁcheck_proposals__mutmut_4, 
        'xǁGovernanceEngineǁcheck_proposals__mutmut_5': xǁGovernanceEngineǁcheck_proposals__mutmut_5
    }
    
    def check_proposals(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁcheck_proposals__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁcheck_proposals__mutmut_mutants"), args, kwargs, self)
        return result 
    
    check_proposals.__signature__ = _mutmut_signature(xǁGovernanceEngineǁcheck_proposals__mutmut_orig)
    xǁGovernanceEngineǁcheck_proposals__mutmut_orig.__name__ = 'xǁGovernanceEngineǁcheck_proposals'

    def xǁGovernanceEngineǁ_tally_votes__mutmut_orig(self, proposal: Proposal):
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_1(self, proposal: Proposal):
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
        
        counts = None
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_2(self, proposal: Proposal):
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
        total = None
        
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_3(self, proposal: Proposal):
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
        
        if total != 0:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_4(self, proposal: Proposal):
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
        
        if total == 1:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_5(self, proposal: Proposal):
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
            proposal.state = None
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_6(self, proposal: Proposal):
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
            logger.info(None)
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_7(self, proposal: Proposal):
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
        yes_weighted = None
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_8(self, proposal: Proposal):
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
        yes_weighted = 1.0
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_9(self, proposal: Proposal):
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
        no_weighted = None
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_10(self, proposal: Proposal):
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
        no_weighted = 1.0
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_11(self, proposal: Proposal):
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
        total_weighted = None
        
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_12(self, proposal: Proposal):
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
        total_weighted = 1.0
        
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_13(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = None
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_14(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(None)
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_15(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is not None:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_16(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = None
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_17(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(None, 0.0)
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_18(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, None)
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_19(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(0.0)
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_20(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, )
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_21(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 1.0)
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_22(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = None
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_23(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(None) if tokens > 0 else 0.0
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_24(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens >= 0 else 0.0
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_25(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 1 else 0.0
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_26(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 1.0
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_27(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 0.0
            
            total_weighted = voting_power
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_28(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 0.0
            
            total_weighted -= voting_power
            
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_29(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 0.0
            
            total_weighted += voting_power
            
            if vote != VoteType.YES:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_30(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 0.0
            
            total_weighted += voting_power
            
            if vote == VoteType.YES:
                yes_weighted = voting_power
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_31(self, proposal: Proposal):
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
            # Get tokens from proposal (set during cast_vote) or fallback to voting_power
            tokens = proposal.voter_tokens.get(voter_id)
            if tokens is None:
                # Fallback: use voting_power from engine (for backward compatibility)
                tokens = self.voting_power.get(voter_id, 0.0)
            
            # Quadratic Voting: voting_power = sqrt(tokens)
            voting_power = sqrt(tokens) if tokens > 0 else 0.0
            
            total_weighted += voting_power
            
            if vote == VoteType.YES:
                yes_weighted -= voting_power
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_32(self, proposal: Proposal):
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
            elif vote != VoteType.NO:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_33(self, proposal: Proposal):
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
                no_weighted = voting_power
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_34(self, proposal: Proposal):
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
                no_weighted -= voting_power
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_35(self, proposal: Proposal):
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
        if total_weighted != 0:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_36(self, proposal: Proposal):
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
        if total_weighted == 1:
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_37(self, proposal: Proposal):
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
            proposal.state = None
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_38(self, proposal: Proposal):
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
            logger.info(None)
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_39(self, proposal: Proposal):
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
        
        support = None
        
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_40(self, proposal: Proposal):
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
        
        support = yes_weighted * total_weighted
        
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

    def xǁGovernanceEngineǁ_tally_votes__mutmut_41(self, proposal: Proposal):
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
        
        support = yes_weighted / total_weighted
        
        # Log quadratic voting metrics
        logger.info(
            None
        )
        
        if support > proposal.threshold:
            proposal.state = ProposalState.PASSED
            logger.info(f"Proposal {proposal.id} PASSED ({support:.1%} weighted support)")
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)")

    def xǁGovernanceEngineǁ_tally_votes__mutmut_42(self, proposal: Proposal):
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
        
        support = yes_weighted / total_weighted
        
        # Log quadratic voting metrics
        logger.info(
            f"Quadratic Voting tally for {proposal.id}: "
            f"YES={yes_weighted:.2f}, NO={no_weighted:.2f}, "
            f"Total={total_weighted:.2f}, Support={support:.1%}"
        )
        
        if support >= proposal.threshold:
            proposal.state = ProposalState.PASSED
            logger.info(f"Proposal {proposal.id} PASSED ({support:.1%} weighted support)")
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)")

    def xǁGovernanceEngineǁ_tally_votes__mutmut_43(self, proposal: Proposal):
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
        
        support = yes_weighted / total_weighted
        
        # Log quadratic voting metrics
        logger.info(
            f"Quadratic Voting tally for {proposal.id}: "
            f"YES={yes_weighted:.2f}, NO={no_weighted:.2f}, "
            f"Total={total_weighted:.2f}, Support={support:.1%}"
        )
        
        if support > proposal.threshold:
            proposal.state = None
            logger.info(f"Proposal {proposal.id} PASSED ({support:.1%} weighted support)")
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)")

    def xǁGovernanceEngineǁ_tally_votes__mutmut_44(self, proposal: Proposal):
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
        
        support = yes_weighted / total_weighted
        
        # Log quadratic voting metrics
        logger.info(
            f"Quadratic Voting tally for {proposal.id}: "
            f"YES={yes_weighted:.2f}, NO={no_weighted:.2f}, "
            f"Total={total_weighted:.2f}, Support={support:.1%}"
        )
        
        if support > proposal.threshold:
            proposal.state = ProposalState.PASSED
            logger.info(None)
        else:
            proposal.state = ProposalState.REJECTED
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)")

    def xǁGovernanceEngineǁ_tally_votes__mutmut_45(self, proposal: Proposal):
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
            proposal.state = None
            logger.info(f"Proposal {proposal.id} REJECTED ({support:.1%} weighted support)")

    def xǁGovernanceEngineǁ_tally_votes__mutmut_46(self, proposal: Proposal):
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
            logger.info(None)
    
    xǁGovernanceEngineǁ_tally_votes__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁ_tally_votes__mutmut_1': xǁGovernanceEngineǁ_tally_votes__mutmut_1, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_2': xǁGovernanceEngineǁ_tally_votes__mutmut_2, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_3': xǁGovernanceEngineǁ_tally_votes__mutmut_3, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_4': xǁGovernanceEngineǁ_tally_votes__mutmut_4, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_5': xǁGovernanceEngineǁ_tally_votes__mutmut_5, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_6': xǁGovernanceEngineǁ_tally_votes__mutmut_6, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_7': xǁGovernanceEngineǁ_tally_votes__mutmut_7, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_8': xǁGovernanceEngineǁ_tally_votes__mutmut_8, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_9': xǁGovernanceEngineǁ_tally_votes__mutmut_9, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_10': xǁGovernanceEngineǁ_tally_votes__mutmut_10, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_11': xǁGovernanceEngineǁ_tally_votes__mutmut_11, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_12': xǁGovernanceEngineǁ_tally_votes__mutmut_12, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_13': xǁGovernanceEngineǁ_tally_votes__mutmut_13, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_14': xǁGovernanceEngineǁ_tally_votes__mutmut_14, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_15': xǁGovernanceEngineǁ_tally_votes__mutmut_15, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_16': xǁGovernanceEngineǁ_tally_votes__mutmut_16, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_17': xǁGovernanceEngineǁ_tally_votes__mutmut_17, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_18': xǁGovernanceEngineǁ_tally_votes__mutmut_18, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_19': xǁGovernanceEngineǁ_tally_votes__mutmut_19, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_20': xǁGovernanceEngineǁ_tally_votes__mutmut_20, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_21': xǁGovernanceEngineǁ_tally_votes__mutmut_21, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_22': xǁGovernanceEngineǁ_tally_votes__mutmut_22, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_23': xǁGovernanceEngineǁ_tally_votes__mutmut_23, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_24': xǁGovernanceEngineǁ_tally_votes__mutmut_24, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_25': xǁGovernanceEngineǁ_tally_votes__mutmut_25, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_26': xǁGovernanceEngineǁ_tally_votes__mutmut_26, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_27': xǁGovernanceEngineǁ_tally_votes__mutmut_27, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_28': xǁGovernanceEngineǁ_tally_votes__mutmut_28, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_29': xǁGovernanceEngineǁ_tally_votes__mutmut_29, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_30': xǁGovernanceEngineǁ_tally_votes__mutmut_30, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_31': xǁGovernanceEngineǁ_tally_votes__mutmut_31, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_32': xǁGovernanceEngineǁ_tally_votes__mutmut_32, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_33': xǁGovernanceEngineǁ_tally_votes__mutmut_33, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_34': xǁGovernanceEngineǁ_tally_votes__mutmut_34, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_35': xǁGovernanceEngineǁ_tally_votes__mutmut_35, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_36': xǁGovernanceEngineǁ_tally_votes__mutmut_36, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_37': xǁGovernanceEngineǁ_tally_votes__mutmut_37, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_38': xǁGovernanceEngineǁ_tally_votes__mutmut_38, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_39': xǁGovernanceEngineǁ_tally_votes__mutmut_39, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_40': xǁGovernanceEngineǁ_tally_votes__mutmut_40, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_41': xǁGovernanceEngineǁ_tally_votes__mutmut_41, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_42': xǁGovernanceEngineǁ_tally_votes__mutmut_42, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_43': xǁGovernanceEngineǁ_tally_votes__mutmut_43, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_44': xǁGovernanceEngineǁ_tally_votes__mutmut_44, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_45': xǁGovernanceEngineǁ_tally_votes__mutmut_45, 
        'xǁGovernanceEngineǁ_tally_votes__mutmut_46': xǁGovernanceEngineǁ_tally_votes__mutmut_46
    }
    
    def _tally_votes(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁ_tally_votes__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁ_tally_votes__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _tally_votes.__signature__ = _mutmut_signature(xǁGovernanceEngineǁ_tally_votes__mutmut_orig)
    xǁGovernanceEngineǁ_tally_votes__mutmut_orig.__name__ = 'xǁGovernanceEngineǁ_tally_votes'

    def xǁGovernanceEngineǁexecute_proposal__mutmut_orig(self, proposal_id: str) -> bool:
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

    def xǁGovernanceEngineǁexecute_proposal__mutmut_1(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id in self.proposals:
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

    def xǁGovernanceEngineǁexecute_proposal__mutmut_2(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return True
        
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

    def xǁGovernanceEngineǁexecute_proposal__mutmut_3(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = None
        if proposal.state != ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return False
            
        logger.info(f"Executing actions for {proposal_id}")
        for action in proposal.actions:
            logger.info(f"Action: {action}")
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_4(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.state == ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return False
            
        logger.info(f"Executing actions for {proposal_id}")
        for action in proposal.actions:
            logger.info(f"Action: {action}")
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_5(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.state != ProposalState.PASSED:
            logger.warning(None)
            return False
            
        logger.info(f"Executing actions for {proposal_id}")
        for action in proposal.actions:
            logger.info(f"Action: {action}")
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_6(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.state != ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return True
            
        logger.info(f"Executing actions for {proposal_id}")
        for action in proposal.actions:
            logger.info(f"Action: {action}")
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_7(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.state != ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return False
            
        logger.info(None)
        for action in proposal.actions:
            logger.info(f"Action: {action}")
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_8(self, proposal_id: str) -> bool:
        """Execute actions of a passed proposal."""
        if proposal_id not in self.proposals:
            return False
        
        proposal = self.proposals[proposal_id]
        if proposal.state != ProposalState.PASSED:
            logger.warning(f"Cannot execute {proposal_id}: State is {proposal.state}")
            return False
            
        logger.info(f"Executing actions for {proposal_id}")
        for action in proposal.actions:
            logger.info(None)
            # Dispatch to relevant component (e.g. NodeManager config update)
            
        proposal.state = ProposalState.EXECUTED
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_9(self, proposal_id: str) -> bool:
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
            
        proposal.state = None
        return True

    def xǁGovernanceEngineǁexecute_proposal__mutmut_10(self, proposal_id: str) -> bool:
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
        return False
    
    xǁGovernanceEngineǁexecute_proposal__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁGovernanceEngineǁexecute_proposal__mutmut_1': xǁGovernanceEngineǁexecute_proposal__mutmut_1, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_2': xǁGovernanceEngineǁexecute_proposal__mutmut_2, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_3': xǁGovernanceEngineǁexecute_proposal__mutmut_3, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_4': xǁGovernanceEngineǁexecute_proposal__mutmut_4, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_5': xǁGovernanceEngineǁexecute_proposal__mutmut_5, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_6': xǁGovernanceEngineǁexecute_proposal__mutmut_6, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_7': xǁGovernanceEngineǁexecute_proposal__mutmut_7, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_8': xǁGovernanceEngineǁexecute_proposal__mutmut_8, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_9': xǁGovernanceEngineǁexecute_proposal__mutmut_9, 
        'xǁGovernanceEngineǁexecute_proposal__mutmut_10': xǁGovernanceEngineǁexecute_proposal__mutmut_10
    }
    
    def execute_proposal(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁGovernanceEngineǁexecute_proposal__mutmut_orig"), object.__getattribute__(self, "xǁGovernanceEngineǁexecute_proposal__mutmut_mutants"), args, kwargs, self)
        return result 
    
    execute_proposal.__signature__ = _mutmut_signature(xǁGovernanceEngineǁexecute_proposal__mutmut_orig)
    xǁGovernanceEngineǁexecute_proposal__mutmut_orig.__name__ = 'xǁGovernanceEngineǁexecute_proposal'
