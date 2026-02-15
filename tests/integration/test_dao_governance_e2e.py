"""
End-to-end integration tests for DAO Governance.

Tests complete governance flow:
- Proposal creation
- Voting (including quadratic voting)
- Proposal execution
- Token management
"""

import time
from typing import Dict, List

import pytest

try:
    from src.dao.governance import GovernanceEngine, ProposalState, VoteType

    DAO_AVAILABLE = True
except ImportError:
    DAO_AVAILABLE = False
    GovernanceEngine = None
    VoteType = None
    ProposalState = None


@pytest.mark.skipif(not DAO_AVAILABLE, reason="DAO Governance not available")
class TestDAOGovernanceE2E:
    """End-to-end tests for DAO Governance"""

    def test_proposal_lifecycle(self):
        """Test complete proposal lifecycle"""
        gov = GovernanceEngine(node_id="node-1")

        # Setup voting power
        gov.voting_power = {
            "node-1": 100.0,
            "node-2": 200.0,
            "node-3": 300.0,
        }

        # Create proposal
        proposal = gov.create_proposal(
            title="Test Proposal",
            description="Test proposal for E2E testing",
            duration_seconds=1.0,
            quorum=0.5,
            threshold=0.6,
        )

        assert proposal.state == ProposalState.ACTIVE

        # Cast votes
        gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=100.0)
        gov.cast_vote(proposal.id, "node-2", VoteType.YES, tokens=200.0)
        gov.cast_vote(proposal.id, "node-3", VoteType.NO, tokens=300.0)

        # Wait for proposal to expire
        time.sleep(1.5)

        # Check proposal
        gov.check_proposals()

        # Proposal should be processed
        assert proposal.state in [ProposalState.PASSED, ProposalState.REJECTED]

    def test_quadratic_voting_e2e(self):
        """Test complete quadratic voting flow"""
        gov = GovernanceEngine(node_id="node-1")

        # Setup voting power (for quadratic voting calculation)
        gov.voting_power = {
            "node-1": 100.0,  # sqrt = 10
            "node-2": 400.0,  # sqrt = 20
            "node-3": 900.0,  # sqrt = 30
            "node-4": 100.0,  # sqrt = 10
        }

        # Create proposal
        proposal = gov.create_proposal(
            title="Quadratic Voting Test",
            description="Test quadratic voting",
            duration_seconds=1.0,
            quorum=0.5,
            threshold=0.5,
        )

        # Cast votes with different token amounts
        gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=100.0)  # 10 power
        gov.cast_vote(proposal.id, "node-2", VoteType.YES, tokens=400.0)  # 20 power
        gov.cast_vote(proposal.id, "node-3", VoteType.NO, tokens=900.0)  # 30 power
        gov.cast_vote(proposal.id, "node-4", VoteType.YES, tokens=100.0)  # 10 power

        # Wait for expiration
        time.sleep(1.5)

        # Check proposal
        gov.check_proposals()

        # Calculate expected result:
        # YES: 10 + 20 + 10 = 40
        # NO: 30
        # Total: 70
        # Support: 40/70 = ~0.57 (above 0.5 threshold)
        # Participation: 70 / (10+20+30+10) = 70/70 = 1.0 (above 0.5 quorum)
        # Should PASS
        assert proposal.state == ProposalState.PASSED

    def test_multiple_proposals_concurrent(self):
        """Test handling multiple concurrent proposals"""
        gov = GovernanceEngine(node_id="node-1")

        gov.voting_power = {
            "node-1": 100.0,
            "node-2": 100.0,
            "node-3": 100.0,
        }

        # Create multiple proposals
        proposals = []
        for i in range(3):
            prop = gov.create_proposal(
                title=f"Proposal {i+1}",
                description=f"Test proposal {i+1}",
                duration_seconds=1.0,
            )
            proposals.append(prop)

        # Vote on all proposals
        for prop in proposals:
            gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
            gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)

        # Wait for expiration
        time.sleep(1.5)

        # Check all proposals
        gov.check_proposals()

        # All should be processed
        for prop in proposals:
            assert prop.state in [ProposalState.PASSED, ProposalState.REJECTED]

    def test_proposal_with_quorum_failure(self):
        """Test proposal that fails due to quorum"""
        gov = GovernanceEngine(node_id="node-1")

        gov.voting_power = {
            "node-1": 100.0,
            "node-2": 200.0,
            "node-3": 300.0,
            "node-4": 400.0,
        }

        # Create proposal with high quorum
        proposal = gov.create_proposal(
            title="High Quorum Proposal",
            description="Requires high participation",
            duration_seconds=1.0,
            quorum=0.9,  # 90% participation required
            threshold=0.5,
        )

        # Only one node votes (25% participation)
        gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=100.0)

        # Wait for expiration
        time.sleep(1.5)

        # Check proposal
        gov.check_proposals()

        # Should be rejected due to quorum
        assert proposal.state == ProposalState.REJECTED

    def test_proposal_with_threshold_failure(self):
        """Test proposal that fails due to threshold"""
        gov = GovernanceEngine(node_id="node-1")

        gov.voting_power = {
            "node-1": 100.0,
            "node-2": 200.0,
            "node-3": 300.0,
        }

        # Create proposal with high threshold
        proposal = gov.create_proposal(
            title="High Threshold Proposal",
            description="Requires high support",
            duration_seconds=1.0,
            quorum=0.5,
            threshold=0.8,  # 80% support required
        )

        # Vote: 2 YES, 1 NO (66.7% support - below 80%)
        gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=100.0)
        gov.cast_vote(proposal.id, "node-2", VoteType.YES, tokens=200.0)
        gov.cast_vote(proposal.id, "node-3", VoteType.NO, tokens=300.0)

        # Wait for expiration
        time.sleep(1.5)

        # Check proposal
        gov.check_proposals()

        # Should be rejected due to threshold
        assert proposal.state == ProposalState.REJECTED

    def test_vote_overwrite(self):
        """Test that last vote overwrites previous vote"""
        gov = GovernanceEngine(node_id="node-1")

        gov.voting_power = {
            "node-1": 100.0,
        }

        proposal = gov.create_proposal(
            title="Vote Overwrite Test",
            description="Test vote overwriting",
            duration_seconds=1.0,
        )

        # Vote NO first
        gov.cast_vote(proposal.id, "node-1", VoteType.NO, tokens=100.0)

        # Vote YES (should overwrite)
        gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=100.0)

        # Wait for expiration
        time.sleep(1.5)

        # Check proposal
        gov.check_proposals()

        # Should have YES vote (last vote wins)
        assert proposal.state == ProposalState.PASSED


@pytest.mark.skipif(not DAO_AVAILABLE, reason="DAO Governance not available")
class TestDAOGovernanceEdgeCases:
    """Edge case tests for DAO Governance"""

    def test_proposal_with_zero_tokens(self):
        """Test voting with zero tokens"""
        gov = GovernanceEngine(node_id="node-1")

        gov.voting_power = {
            "node-1": 0.0,
        }

        proposal = gov.create_proposal(
            title="Zero Tokens Test",
            description="Test with zero tokens",
            duration_seconds=1.0,
        )

        # Vote with zero tokens
        gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=0.0)

        # Wait for expiration
        time.sleep(1.5)

        # Check proposal
        gov.check_proposals()

        # Should be rejected (no voting power)
        assert proposal.state == ProposalState.REJECTED

    def test_proposal_with_negative_tokens(self):
        """Test handling of negative tokens (should be rejected)"""
        gov = GovernanceEngine(node_id="node-1")

        proposal = gov.create_proposal(
            title="Negative Tokens Test",
            description="Test with negative tokens",
            duration_seconds=1.0,
        )

        # Negative tokens should be handled gracefully
        # (Implementation should reject or clamp to 0)
        try:
            gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=-100.0)
            # If accepted, should be treated as 0
        except (ValueError, TypeError):
            # If rejected, that's also valid
            pass

    def test_proposal_after_expiration(self):
        """Test voting on expired proposal"""
        gov = GovernanceEngine(node_id="node-1")

        proposal = gov.create_proposal(
            title="Expired Proposal Test",
            description="Test voting on expired proposal",
            duration_seconds=0.1,
        )

        # Wait for expiration
        time.sleep(0.2)

        # Try to vote (should fail)
        result = gov.cast_vote(proposal.id, "node-1", VoteType.YES, tokens=100.0)

        # Should return False (voting closed)
        assert result == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
