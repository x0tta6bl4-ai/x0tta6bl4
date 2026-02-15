"""
Quadratic Voting for DAO Governance
====================================

Implements quadratic voting algorithm:
- Cost = (Votes)²
- Voting power = √(tokens_held)
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Monitoring metrics
try:
    from src.monitoring import record_dao_vote

    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False

    def record_dao_vote(*args, **kwargs):
        pass


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

    def validate_vote(
        self, voter_tokens: int, votes: int, vote_type: str = "FOR"
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
            record_dao_vote(vote_type, "standard")

        return is_valid

    def calculate_voting_power(self, votes: List[Vote]) -> Dict[str, int]:
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
            "for_votes": for_votes,
            "against_votes": against_votes,
            "total_votes": for_votes + against_votes,
        }

    def calculate_support_percentage(self, votes: List[Vote]) -> float:
        """
        Calculate support percentage.

        Args:
            votes: List of votes

        Returns:
            Support percentage (0.0-100.0)
        """
        voting_power = self.calculate_voting_power(votes)

        total = voting_power["for_votes"] + voting_power["against_votes"]
        if total == 0:
            return 0.0

        return (voting_power["for_votes"] / total) * 100.0

    def check_quorum(
        self, votes: List[Vote], total_supply: int, quorum_percentage: float = 33.0
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
        quorum_threshold = self.tokens_to_votes(
            int(total_supply * quorum_percentage / 100)
        )

        return voting_power["total_votes"] >= quorum_threshold

    def check_supermajority(
        self, votes: List[Vote], supermajority_percentage: float = 67.0
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
        Vote("node-c", "proposal-1", 1, 1, False),
    ]

    voting_power = qv.calculate_voting_power(votes)
    support = qv.calculate_support_percentage(votes)

    print(f"Voting power: {voting_power}")
    print(f"Support: {support:.1f}%")
    print(f"Quorum (33%): {qv.check_quorum(votes, 1000, 33.0)}")
    print(f"Supermajority (67%): {qv.check_supermajority(votes, 67.0)}")
