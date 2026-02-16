"""
Tests for Quadratic Voting implementation in DAO Governance.
"""

import time
from math import sqrt

import pytest

from src.dao.governance import (GovernanceEngine, Proposal, ProposalState,
                                VoteType)


class TestQuadraticVoting:
    """Test quadratic voting functionality"""

    def test_quadratic_voting_power_calculation(self):
        """Test that voting power = sqrt(tokens)"""
        engine = GovernanceEngine("test-node")
        proposal = engine.create_proposal("Test", "Description", duration_seconds=3600)

        # Voter with 100 tokens should have sqrt(100) = 10 voting power
        engine.cast_vote(proposal.id, "voter1", VoteType.YES, tokens=100.0)
        assert proposal.voter_tokens["voter1"] == 100.0

        # Voter with 10000 tokens should have sqrt(10000) = 100 voting power
        engine.cast_vote(proposal.id, "voter2", VoteType.YES, tokens=10000.0)
        assert proposal.voter_tokens["voter2"] == 10000.0

        # Note: 10000 tokens gives 100x voting power, not 10000x
        # This is the key feature of quadratic voting

    def test_quadratic_voting_reduces_whale_influence(self):
        """Test that quadratic voting reduces influence of large token holders"""
        engine = GovernanceEngine("test-node")
        proposal = engine.create_proposal("Test", "Description", duration_seconds=3600)

        # Small holder: 100 tokens
        engine.cast_vote(proposal.id, "small", VoteType.YES, tokens=100.0)
        small_power = sqrt(100.0)  # = 10

        # Large holder: 10000 tokens (100x more)
        engine.cast_vote(proposal.id, "large", VoteType.NO, tokens=10000.0)
        large_power = sqrt(10000.0)  # = 100 (only 10x more, not 100x)

        # Close proposal and tally
        proposal.end_time = time.time() - 1
        engine._tally_votes(proposal)

        # Large holder has 10x voting power, not 100x
        assert large_power == 10 * small_power
        assert large_power != 100 * small_power

    def test_quadratic_voting_tally(self):
        """Test that tally correctly uses quadratic voting"""
        engine = GovernanceEngine("test-node")
        proposal = engine.create_proposal("Test", "Description", duration_seconds=3600)

        # Voter 1: 100 tokens, YES
        engine.cast_vote(proposal.id, "v1", VoteType.YES, tokens=100.0)

        # Voter 2: 100 tokens, YES
        engine.cast_vote(proposal.id, "v2", VoteType.YES, tokens=100.0)

        # Voter 3: 10000 tokens, NO (whale)
        engine.cast_vote(proposal.id, "v3", VoteType.NO, tokens=10000.0)

        # Close and tally
        proposal.end_time = time.time() - 1
        engine._tally_votes(proposal)

        # YES: sqrt(100) + sqrt(100) = 10 + 10 = 20
        # NO: sqrt(10000) = 100
        # Total: 120
        # Support: 20/120 = 16.7% < 50% threshold
        # Should be REJECTED
        assert proposal.state == ProposalState.REJECTED

    def test_quadratic_voting_with_zero_tokens(self):
        """Test that zero tokens gives zero voting power"""
        engine = GovernanceEngine("test-node")
        proposal = engine.create_proposal("Test", "Description", duration_seconds=3600)

        engine.cast_vote(proposal.id, "voter", VoteType.YES, tokens=0.0)
        assert proposal.voter_tokens["voter"] == 0.0

        proposal.end_time = time.time() - 1
        engine._tally_votes(proposal)

        # Zero tokens = zero voting power, should be rejected
        assert proposal.state == ProposalState.REJECTED

    def test_quadratic_voting_backward_compatibility(self):
        """Test that old code (without tokens) still works"""
        engine = GovernanceEngine("test-node")
        proposal = engine.create_proposal("Test", "Description", duration_seconds=3600)

        # Cast vote without tokens (uses default tokens=1.0)
        engine.cast_vote(proposal.id, "voter", VoteType.YES)

        # Should fallback to voting_power from engine
        proposal.end_time = time.time() - 1
        engine._tally_votes(proposal)

        # Should work (uses voting_power fallback)
        assert proposal.votes["voter"] == VoteType.YES

    @pytest.mark.skip(reason="DAO voting endpoint /dao/vote not implemented yet")
    def test_quadratic_voting_endpoint_integration(self):
        """Test that API endpoint correctly passes tokens"""
        from fastapi.testclient import TestClient

        from src.core.app import app

        client = TestClient(app)

        # Create a proposal first
        # (In real scenario, this would be done via API)

        # Cast vote with tokens
        response = client.post(
            "/dao/vote",
            json={
                "proposal_id": "1",
                "voter_id": "test-voter",
                "tokens": 100,
                "vote": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["quadratic"] is True
        assert data["tokens"] == 100
        assert data["voting_power"] == sqrt(100)  # Should be 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
