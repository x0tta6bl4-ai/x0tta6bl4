"""
Quadratic Voting for DAO Governance
====================================

Implements quadratic voting algorithm:
- Cost = (Votes)²
- Voting power = √(tokens_held)
"""
import logging
import math
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Monitoring metrics
try:
    from src.monitoring import record_dao_vote
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    def record_dao_vote(*args, **kwargs): pass
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


@dataclass
class Vote:
    """Single vote in quadratic voting."""
    voter: str
    proposal_id: str
    votes: int  # Number of votes cast
    cost: int  # Cost in tokens (votes²)
    support: bool  # True = FOR, False = AGAINST


class QuadraticVoting:
    """
    Quadratic Voting implementation.
    
    Formula:
    - Cost = (Votes)²
    - Voting power = √(tokens_held)
    - Max votes = √(tokens_held)
    """
    
    @staticmethod
    def votes_to_cost(votes: int) -> int:
        """
        Calculate cost for given number of votes.
        
        Args:
            votes: Number of votes
            
        Returns:
            Cost in tokens (votes²)
        """
        return votes * votes
    
    @staticmethod
    def tokens_to_votes(tokens: int) -> int:
        """
        Calculate maximum votes from token balance.
        
        Args:
            tokens: Token balance
            
        Returns:
            Maximum votes (√tokens)
        """
        if tokens <= 0:
            return 0
        return int(math.sqrt(tokens))
    
    @staticmethod
    def cost_to_votes(cost: int) -> int:
        """
        Calculate votes from cost.
        
        Args:
            cost: Cost in tokens
            
        Returns:
            Number of votes (√cost)
        """
        if cost <= 0:
            return 0
        return int(math.sqrt(cost))
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_orig(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_1(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'XXFORXX'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_2(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'for'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_3(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = None
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_4(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(None)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_5(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = None
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_6(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(None)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_7(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = None
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_8(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes or cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_9(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes < max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_10(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost < voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_11(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(None, 'standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_12(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, None)
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_13(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote('standard')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_14(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, )
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_15(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'XXstandardXX')
        
        return is_valid
    
    def xǁQuadraticVotingǁvalidate_vote__mutmut_16(
        self,
        voter_tokens: int,
        votes: int,
        vote_type: str = 'FOR'
    ) -> bool:
        """
        Validate if voter has enough tokens for votes.
        
        Args:
            voter_tokens: Voter's token balance
            votes: Number of votes to cast
            vote_type: 'FOR', 'AGAINST', or 'ABSTAIN'
            
        Returns:
            True if valid
        """
        max_votes = self.tokens_to_votes(voter_tokens)
        cost = self.votes_to_cost(votes)
        
        is_valid = votes <= max_votes and cost <= voter_tokens
        
        if is_valid:
            record_dao_vote(vote_type, 'STANDARD')
        
        return is_valid
    
    xǁQuadraticVotingǁvalidate_vote__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁQuadraticVotingǁvalidate_vote__mutmut_1': xǁQuadraticVotingǁvalidate_vote__mutmut_1, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_2': xǁQuadraticVotingǁvalidate_vote__mutmut_2, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_3': xǁQuadraticVotingǁvalidate_vote__mutmut_3, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_4': xǁQuadraticVotingǁvalidate_vote__mutmut_4, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_5': xǁQuadraticVotingǁvalidate_vote__mutmut_5, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_6': xǁQuadraticVotingǁvalidate_vote__mutmut_6, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_7': xǁQuadraticVotingǁvalidate_vote__mutmut_7, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_8': xǁQuadraticVotingǁvalidate_vote__mutmut_8, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_9': xǁQuadraticVotingǁvalidate_vote__mutmut_9, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_10': xǁQuadraticVotingǁvalidate_vote__mutmut_10, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_11': xǁQuadraticVotingǁvalidate_vote__mutmut_11, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_12': xǁQuadraticVotingǁvalidate_vote__mutmut_12, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_13': xǁQuadraticVotingǁvalidate_vote__mutmut_13, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_14': xǁQuadraticVotingǁvalidate_vote__mutmut_14, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_15': xǁQuadraticVotingǁvalidate_vote__mutmut_15, 
        'xǁQuadraticVotingǁvalidate_vote__mutmut_16': xǁQuadraticVotingǁvalidate_vote__mutmut_16
    }
    
    def validate_vote(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁQuadraticVotingǁvalidate_vote__mutmut_orig"), object.__getattribute__(self, "xǁQuadraticVotingǁvalidate_vote__mutmut_mutants"), args, kwargs, self)
        return result 
    
    validate_vote.__signature__ = _mutmut_signature(xǁQuadraticVotingǁvalidate_vote__mutmut_orig)
    xǁQuadraticVotingǁvalidate_vote__mutmut_orig.__name__ = 'xǁQuadraticVotingǁvalidate_vote'
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_orig(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_1(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = None
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_2(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 1
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_3(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = None
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_4(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 1
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_5(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes = vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_6(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes -= vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_7(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes = vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_8(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes -= vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_9(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'XXfor_votesXX': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_10(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'FOR_VOTES': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_11(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'XXagainst_votesXX': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_12(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'AGAINST_VOTES': against_votes,
            'total_votes': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_13(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'XXtotal_votesXX': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_14(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'TOTAL_VOTES': for_votes + against_votes
        }
    
    def xǁQuadraticVotingǁcalculate_voting_power__mutmut_15(
        self,
        votes: List[Vote]
    ) -> Dict[str, int]:
        """
        Calculate total voting power (in votes) for each side.
        
        Args:
            votes: List of votes
            
        Returns:
            Dict with 'for_votes' and 'against_votes'
        """
        for_votes = 0
        against_votes = 0
        
        for vote in votes:
            if vote.support:
                for_votes += vote.votes
            else:
                against_votes += vote.votes
        
        return {
            'for_votes': for_votes,
            'against_votes': against_votes,
            'total_votes': for_votes - against_votes
        }
    
    xǁQuadraticVotingǁcalculate_voting_power__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁQuadraticVotingǁcalculate_voting_power__mutmut_1': xǁQuadraticVotingǁcalculate_voting_power__mutmut_1, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_2': xǁQuadraticVotingǁcalculate_voting_power__mutmut_2, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_3': xǁQuadraticVotingǁcalculate_voting_power__mutmut_3, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_4': xǁQuadraticVotingǁcalculate_voting_power__mutmut_4, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_5': xǁQuadraticVotingǁcalculate_voting_power__mutmut_5, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_6': xǁQuadraticVotingǁcalculate_voting_power__mutmut_6, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_7': xǁQuadraticVotingǁcalculate_voting_power__mutmut_7, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_8': xǁQuadraticVotingǁcalculate_voting_power__mutmut_8, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_9': xǁQuadraticVotingǁcalculate_voting_power__mutmut_9, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_10': xǁQuadraticVotingǁcalculate_voting_power__mutmut_10, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_11': xǁQuadraticVotingǁcalculate_voting_power__mutmut_11, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_12': xǁQuadraticVotingǁcalculate_voting_power__mutmut_12, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_13': xǁQuadraticVotingǁcalculate_voting_power__mutmut_13, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_14': xǁQuadraticVotingǁcalculate_voting_power__mutmut_14, 
        'xǁQuadraticVotingǁcalculate_voting_power__mutmut_15': xǁQuadraticVotingǁcalculate_voting_power__mutmut_15
    }
    
    def calculate_voting_power(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁQuadraticVotingǁcalculate_voting_power__mutmut_orig"), object.__getattribute__(self, "xǁQuadraticVotingǁcalculate_voting_power__mutmut_mutants"), args, kwargs, self)
        return result 
    
    calculate_voting_power.__signature__ = _mutmut_signature(xǁQuadraticVotingǁcalculate_voting_power__mutmut_orig)
    xǁQuadraticVotingǁcalculate_voting_power__mutmut_orig.__name__ = 'xǁQuadraticVotingǁcalculate_voting_power'
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_orig(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_1(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = None
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_2(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(None)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_3(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = None
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_4(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] - voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_5(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['XXfor_votesXX'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_6(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['FOR_VOTES'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_7(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['XXagainst_votesXX']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_8(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['AGAINST_VOTES']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_9(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total != 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_10(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 1:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_11(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 1.0
        
        return (voting_power['for_votes'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_12(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) / 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_13(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] * total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_14(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['XXfor_votesXX'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_15(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['FOR_VOTES'] / total) * 100.0
    
    def xǁQuadraticVotingǁcalculate_support_percentage__mutmut_16(
        self,
        votes: List[Vote]
    ) -> float:
        """
        Calculate support percentage.
        
        Args:
            votes: List of votes
            
        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)
        
        total = voting_power['for_votes'] + voting_power['against_votes']
        if total == 0:
            return 0.0
        
        return (voting_power['for_votes'] / total) * 101.0
    
    xǁQuadraticVotingǁcalculate_support_percentage__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_1': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_1, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_2': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_2, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_3': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_3, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_4': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_4, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_5': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_5, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_6': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_6, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_7': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_7, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_8': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_8, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_9': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_9, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_10': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_10, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_11': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_11, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_12': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_12, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_13': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_13, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_14': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_14, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_15': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_15, 
        'xǁQuadraticVotingǁcalculate_support_percentage__mutmut_16': xǁQuadraticVotingǁcalculate_support_percentage__mutmut_16
    }
    
    def calculate_support_percentage(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁQuadraticVotingǁcalculate_support_percentage__mutmut_orig"), object.__getattribute__(self, "xǁQuadraticVotingǁcalculate_support_percentage__mutmut_mutants"), args, kwargs, self)
        return result 
    
    calculate_support_percentage.__signature__ = _mutmut_signature(xǁQuadraticVotingǁcalculate_support_percentage__mutmut_orig)
    xǁQuadraticVotingǁcalculate_support_percentage__mutmut_orig.__name__ = 'xǁQuadraticVotingǁcalculate_support_percentage'
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_orig(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_1(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 34.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_2(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = None
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_3(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(None)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_4(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = None
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_5(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(None)
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_6(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(None))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_7(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage * 100))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_8(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply / quorum_percentage / 100))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_9(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 101))
        
        return voting_power['total_votes'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_10(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['XXtotal_votesXX'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_11(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['TOTAL_VOTES'] >= quorum_threshold
    
    def xǁQuadraticVotingǁcheck_quorum__mutmut_12(
        self,
        votes: List[Vote],
        total_supply: int,
        quorum_percentage: float = 33.0
    ) -> bool:
        """
        Check if quorum is reached.
        
        Args:
            votes: List of votes
            total_supply: Total token supply
            quorum_percentage: Required quorum percentage
            
        Returns:
            True if quorum reached
        """
        voting_power = self.calculate_voting_power(votes)
        
        # Calculate quorum threshold (in votes, not tokens)
        quorum_threshold = self.tokens_to_votes(int(total_supply * quorum_percentage / 100))
        
        return voting_power['total_votes'] > quorum_threshold
    
    xǁQuadraticVotingǁcheck_quorum__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁQuadraticVotingǁcheck_quorum__mutmut_1': xǁQuadraticVotingǁcheck_quorum__mutmut_1, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_2': xǁQuadraticVotingǁcheck_quorum__mutmut_2, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_3': xǁQuadraticVotingǁcheck_quorum__mutmut_3, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_4': xǁQuadraticVotingǁcheck_quorum__mutmut_4, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_5': xǁQuadraticVotingǁcheck_quorum__mutmut_5, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_6': xǁQuadraticVotingǁcheck_quorum__mutmut_6, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_7': xǁQuadraticVotingǁcheck_quorum__mutmut_7, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_8': xǁQuadraticVotingǁcheck_quorum__mutmut_8, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_9': xǁQuadraticVotingǁcheck_quorum__mutmut_9, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_10': xǁQuadraticVotingǁcheck_quorum__mutmut_10, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_11': xǁQuadraticVotingǁcheck_quorum__mutmut_11, 
        'xǁQuadraticVotingǁcheck_quorum__mutmut_12': xǁQuadraticVotingǁcheck_quorum__mutmut_12
    }
    
    def check_quorum(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁQuadraticVotingǁcheck_quorum__mutmut_orig"), object.__getattribute__(self, "xǁQuadraticVotingǁcheck_quorum__mutmut_mutants"), args, kwargs, self)
        return result 
    
    check_quorum.__signature__ = _mutmut_signature(xǁQuadraticVotingǁcheck_quorum__mutmut_orig)
    xǁQuadraticVotingǁcheck_quorum__mutmut_orig.__name__ = 'xǁQuadraticVotingǁcheck_quorum'
    
    def xǁQuadraticVotingǁcheck_supermajority__mutmut_orig(
        self,
        votes: List[Vote],
        supermajority_percentage: float = 67.0
    ) -> bool:
        """
        Check if supermajority is reached.
        
        Args:
            votes: List of votes
            supermajority_percentage: Required supermajority percentage
            
        Returns:
            True if supermajority reached
        """
        support = self.calculate_support_percentage(votes)
        return support >= supermajority_percentage
    
    def xǁQuadraticVotingǁcheck_supermajority__mutmut_1(
        self,
        votes: List[Vote],
        supermajority_percentage: float = 68.0
    ) -> bool:
        """
        Check if supermajority is reached.
        
        Args:
            votes: List of votes
            supermajority_percentage: Required supermajority percentage
            
        Returns:
            True if supermajority reached
        """
        support = self.calculate_support_percentage(votes)
        return support >= supermajority_percentage
    
    def xǁQuadraticVotingǁcheck_supermajority__mutmut_2(
        self,
        votes: List[Vote],
        supermajority_percentage: float = 67.0
    ) -> bool:
        """
        Check if supermajority is reached.
        
        Args:
            votes: List of votes
            supermajority_percentage: Required supermajority percentage
            
        Returns:
            True if supermajority reached
        """
        support = None
        return support >= supermajority_percentage
    
    def xǁQuadraticVotingǁcheck_supermajority__mutmut_3(
        self,
        votes: List[Vote],
        supermajority_percentage: float = 67.0
    ) -> bool:
        """
        Check if supermajority is reached.
        
        Args:
            votes: List of votes
            supermajority_percentage: Required supermajority percentage
            
        Returns:
            True if supermajority reached
        """
        support = self.calculate_support_percentage(None)
        return support >= supermajority_percentage
    
    def xǁQuadraticVotingǁcheck_supermajority__mutmut_4(
        self,
        votes: List[Vote],
        supermajority_percentage: float = 67.0
    ) -> bool:
        """
        Check if supermajority is reached.
        
        Args:
            votes: List of votes
            supermajority_percentage: Required supermajority percentage
            
        Returns:
            True if supermajority reached
        """
        support = self.calculate_support_percentage(votes)
        return support > supermajority_percentage
    
    xǁQuadraticVotingǁcheck_supermajority__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁQuadraticVotingǁcheck_supermajority__mutmut_1': xǁQuadraticVotingǁcheck_supermajority__mutmut_1, 
        'xǁQuadraticVotingǁcheck_supermajority__mutmut_2': xǁQuadraticVotingǁcheck_supermajority__mutmut_2, 
        'xǁQuadraticVotingǁcheck_supermajority__mutmut_3': xǁQuadraticVotingǁcheck_supermajority__mutmut_3, 
        'xǁQuadraticVotingǁcheck_supermajority__mutmut_4': xǁQuadraticVotingǁcheck_supermajority__mutmut_4
    }
    
    def check_supermajority(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁQuadraticVotingǁcheck_supermajority__mutmut_orig"), object.__getattribute__(self, "xǁQuadraticVotingǁcheck_supermajority__mutmut_mutants"), args, kwargs, self)
        return result 
    
    check_supermajority.__signature__ = _mutmut_signature(xǁQuadraticVotingǁcheck_supermajority__mutmut_orig)
    xǁQuadraticVotingǁcheck_supermajority__mutmut_orig.__name__ = 'xǁQuadraticVotingǁcheck_supermajority'


# Example usage
if __name__ == "__main__":
    qv = QuadraticVoting()
    
    # Example: Node A has 100 tokens
    node_a_tokens = 100
    node_a_max_votes = qv.tokens_to_votes(node_a_tokens)  # √100 = 10
    print(f"Node A: {node_a_tokens} tokens → {node_a_max_votes} max votes")
    
    # Example: Node A casts 3 votes
    votes_cast = 3
    cost = qv.votes_to_cost(votes_cast)  # 3² = 9 tokens
    print(f"Node A casts {votes_cast} votes → costs {cost} tokens")
    
    # Example: Voting
    votes = [
        Vote("node-a", "proposal-1", 3, 9, True),
        Vote("node-b", "proposal-1", 2, 4, True),
        Vote("node-c", "proposal-1", 1, 1, False)
    ]
    
    voting_power = qv.calculate_voting_power(votes)
    support = qv.calculate_support_percentage(votes)
    
    print(f"Voting power: {voting_power}")
    print(f"Support: {support:.1f}%")
    print(f"Quorum (33%): {qv.check_quorum(votes, 1000, 33.0)}")
    print(f"Supermajority (67%): {qv.check_supermajority(votes, 67.0)}")

