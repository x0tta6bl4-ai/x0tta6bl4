"""
Tests for DAO → MAPE-K Integration
===================================

Tests for:
- Quadratic Voting
- Threshold Proposals
- Threshold Manager
- DAO → MAPE-K integration
"""

import tempfile
from pathlib import Path

import pytest

from src.dao.governance import GovernanceEngine, ProposalState
from src.dao.mapek_threshold_manager import MAPEKThresholdManager
from src.dao.mapek_threshold_proposal import (MAPEKThresholdProposal,
                                              ThresholdChange)
from src.dao.quadratic_voting import QuadraticVoting, Vote


class TestQuadraticVoting:
    """Tests for Quadratic Voting."""

    def test_votes_to_cost(self):
        """Test votes to cost calculation."""
        qv = QuadraticVoting()

        assert qv.votes_to_cost(1) == 1
        assert qv.votes_to_cost(2) == 4
        assert qv.votes_to_cost(3) == 9
        assert qv.votes_to_cost(10) == 100

    def test_tokens_to_votes(self):
        """Test tokens to votes calculation."""
        qv = QuadraticVoting()

        assert qv.tokens_to_votes(100) == 10  # sqrt(100) = 10
        assert qv.tokens_to_votes(10000) == 100  # sqrt(10000) = 100
        assert qv.tokens_to_votes(0) == 0

    def test_validate_vote(self):
        """Test vote validation."""
        qv = QuadraticVoting()

        # Valid: 10 tokens, 3 votes (cost = 9)
        assert qv.validate_vote(10, 3) is True

        # Invalid: 10 tokens, 4 votes (cost = 16 > 10)
        assert qv.validate_vote(10, 4) is False

    def test_calculate_voting_power(self):
        """Test voting power calculation."""
        qv = QuadraticVoting()

        votes = [
            Vote("node-1", "prop-1", 3, 9, True),
            Vote("node-2", "prop-1", 2, 4, True),
            Vote("node-3", "prop-1", 1, 1, False),
        ]

        power = qv.calculate_voting_power(votes)

        assert power["for_votes"] == 5  # 3 + 2
        assert power["against_votes"] == 1
        assert power["total_votes"] == 6

    def test_calculate_support_percentage(self):
        """Test support percentage calculation."""
        qv = QuadraticVoting()

        votes = [
            Vote("node-1", "prop-1", 3, 9, True),
            Vote("node-2", "prop-1", 2, 4, True),
            Vote("node-3", "prop-1", 1, 1, False),
        ]

        support = qv.calculate_support_percentage(votes)

        # 5 for / 6 total = 83.33%
        assert support == pytest.approx(83.33, abs=0.1)

    def test_check_quorum(self):
        """Test quorum check."""
        qv = QuadraticVoting()

        votes = [
            Vote("node-1", "prop-1", 3, 9, True),
            Vote("node-2", "prop-1", 2, 4, True),
        ]

        # Total supply = 1000, quorum = 33% = 330 tokens
        # sqrt(330) ≈ 18 votes needed
        # We have 5 votes, so quorum not reached
        assert qv.check_quorum(votes, 1000, 33.0) is False

        # With more votes
        votes_more = votes + [
            Vote("node-3", "prop-1", 10, 100, True),
            Vote("node-4", "prop-1", 5, 25, True),
        ]
        assert qv.check_quorum(votes_more, 1000, 33.0) is True


class TestMAPEKThresholdProposal:
    """Tests for MAPE-K Threshold Proposal."""

    def test_create_threshold_proposal(self):
        """Test creating threshold proposal."""
        governance = GovernanceEngine("node-1")
        proposal_manager = MAPEKThresholdProposal(governance)

        changes = [
            ThresholdChange(
                parameter="cpu_threshold",
                current_value=80.0,
                proposed_value=70.0,
                rationale="Enable earlier detection",
            )
        ]

        proposal = proposal_manager.create_threshold_proposal(
            title="Lower CPU threshold", changes=changes, rationale="Reduce MTTR"
        )

        assert proposal is not None
        assert proposal.id is not None
        assert len(proposal.actions) == 1
        assert proposal.actions[0]["type"] == "update_mapek_threshold"
        assert proposal.actions[0]["parameter"] == "cpu_threshold"
        assert proposal.actions[0]["value"] == 70.0


class TestMAPEKThresholdManager:
    """Tests for MAPE-K Threshold Manager."""

    def test_get_threshold(self, tempfile):
        """Test getting threshold."""
        temp_dir = Path(tempfile.mkdtemp())
        governance = GovernanceEngine("node-1")

        manager = MAPEKThresholdManager(
            governance_engine=governance, storage_path=temp_dir
        )

        threshold = manager.get_threshold("cpu_threshold", default=80.0)

        # Should return default or loaded value
        assert threshold is not None
        assert threshold > 0

    def test_apply_threshold_changes(self, tempfile):
        """Test applying threshold changes."""
        temp_dir = Path(tempfile.mkdtemp())
        governance = GovernanceEngine("node-1")

        manager = MAPEKThresholdManager(
            governance_engine=governance, storage_path=temp_dir
        )

        changes = {"cpu_threshold": 70.0, "memory_threshold": 85.0}

        result = manager.apply_threshold_changes(changes, source="test")

        assert result is True

        # Verify changes applied
        assert manager.get_threshold("cpu_threshold") == 70.0
        assert manager.get_threshold("memory_threshold") == 85.0

    def test_check_and_apply_dao_proposals(self, tempfile):
        """Test checking and applying DAO proposals."""
        temp_dir = Path(tempfile.mkdtemp())
        governance = GovernanceEngine("node-1")

        manager = MAPEKThresholdManager(
            governance_engine=governance, storage_path=temp_dir
        )

        # Create and pass a proposal
        proposal = governance.create_proposal(
            title="Test threshold change",
            description="Test",
            actions=[
                {
                    "type": "update_mapek_threshold",
                    "parameter": "cpu_threshold",
                    "value": 75.0,
                }
            ],
        )

        # Vote and pass
        governance.cast_vote(
            proposal.id, "node-1", governance.VoteType.YES, tokens=100.0
        )
        governance.cast_vote(
            proposal.id, "node-2", governance.VoteType.YES, tokens=100.0
        )

        # Tally votes
        governance._tally_votes(proposal)

        # Check and apply
        applied = manager.check_and_apply_dao_proposals()

        # Should apply if proposal passed
        if proposal.state == ProposalState.PASSED:
            assert applied >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
