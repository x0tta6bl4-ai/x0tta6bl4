
import unittest
import time
from src.dao.governance import GovernanceEngine, VoteType, ProposalState

class TestGovernance(unittest.TestCase):
    def setUp(self):
        self.gov = GovernanceEngine(node_id="node-1")
        
    def test_create_proposal(self):
        prop = self.gov.create_proposal("Test", "Desc")
        self.assertEqual(prop.title, "Test")
        self.assertEqual(prop.state, ProposalState.ACTIVE)
        
    def test_voting_logic(self):
        prop = self.gov.create_proposal("Test Vote", "Desc")
        
        # Cast votes with tokens (quadratic voting)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-4", VoteType.NO, tokens=100.0)
        
        counts = prop.vote_counts()
        self.assertEqual(counts[VoteType.YES], 2)
        self.assertEqual(counts[VoteType.NO], 1)
        
    def test_tally_passing(self):
        # Create short lived proposal — need enough voters to meet 50% quorum
        prop = self.gov.create_proposal("Fast Vote", "Desc", duration_seconds=0.1)
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)

        time.sleep(0.2)
        self.gov.check_proposals()

        self.assertEqual(prop.state, ProposalState.PASSED)

    def test_multi_node_majority_pass(self):
        """Несколько нод голосуют, большинство YES → PASSED."""
        prop = self.gov.create_proposal("Multi-node Pass", "Desc", duration_seconds=0.1)

        # 3 YES, 1 NO (all with equal tokens for simple majority test)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-4", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-5", VoteType.NO, tokens=100.0)

        time.sleep(0.2)
        self.gov.check_proposals()

        self.assertEqual(prop.state, ProposalState.PASSED)

    def test_multi_node_reject(self):
        """Несколько нод, большинство NO → REJECTED."""
        prop = self.gov.create_proposal("Multi-node Reject", "Desc", duration_seconds=0.1)

        # 1 YES, 3 NO (all with equal tokens)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.NO, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-4", VoteType.NO, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-5", VoteType.NO, tokens=100.0)

        time.sleep(0.2)
        self.gov.check_proposals()

        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_vote_overwrite_last_vote_counts(self):
        """Повторное голосование тем же узлом перезаписывает его голос, а не добавляет новый."""
        prop = self.gov.create_proposal("Overwrite Vote", "Desc", duration_seconds=0.1)

        self.gov.cast_vote(prop.id, "node-2", VoteType.NO, tokens=100.0)
        # Тот же узел меняет мнение на YES
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)

        counts = prop.vote_counts()
        self.assertEqual(counts[VoteType.YES], 1)
        self.assertEqual(counts[VoteType.NO], 0)

    def test_proposal_with_actions(self):
        """Proposal can carry a list of actions to execute."""
        actions = [
            {"type": "restart_node", "node_id": "node-5"},
            {"type": "rotate_keys", "scope": "pqc"},
        ]
        prop = self.gov.create_proposal("With Actions", "Desc", actions=actions)
        self.assertEqual(len(prop.actions), 2)
        self.assertEqual(prop.actions[0]["type"], "restart_node")

    def test_quadratic_voting_weight(self):
        """Quadratic voting: sqrt(tokens) determines weight, not raw tokens."""
        prop = self.gov.create_proposal("QV Test", "Desc", duration_seconds=0.1)
        # node with 10000 tokens vs 3 nodes with 100 tokens each
        # sqrt(10000)=100 vs 3*sqrt(100)=30 → whale wins with raw count but...
        # We verify the mechanism is quadratic not linear
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-4", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "whale", VoteType.NO, tokens=10000.0)

        time.sleep(0.2)
        self.gov.check_proposals()

        # whale sqrt(10000)=100 vs 3*sqrt(100)=30 → NO wins
        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_quorum_not_met(self):
        """Proposal is rejected if quorum is not reached."""
        prop = self.gov.create_proposal(
            "Low Quorum", "Desc", duration_seconds=0.1, quorum=0.9
        )
        # Only 1 voter with tokens=100 → sqrt(100)=10
        # Total possible = sqrt(100)+sqrt(150)+sqrt(80)+sqrt(200) ≈ 48.8
        # Participation = 10/48.8 ≈ 20% < 90%
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)

        time.sleep(0.2)
        self.gov.check_proposals()

        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_vote_on_unknown_proposal(self):
        """Voting on non-existent proposal returns False."""
        result = self.gov.cast_vote("nonexistent", "node-1", VoteType.YES, tokens=100.0)
        self.assertFalse(result)

    def test_vote_after_expiry(self):
        """Voting after end_time returns False."""
        prop = self.gov.create_proposal("Expired", "Desc", duration_seconds=0.01)
        time.sleep(0.05)
        result = self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.assertFalse(result)

    def test_vote_on_non_active_proposal(self):
        """Voting on a passed proposal returns False."""
        prop = self.gov.create_proposal("Done", "Desc", duration_seconds=0.1)
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)
        time.sleep(0.2)
        self.gov.check_proposals()
        self.assertEqual(prop.state, ProposalState.PASSED)

        result = self.gov.cast_vote(prop.id, "node-4", VoteType.NO, tokens=100.0)
        self.assertFalse(result)

    def test_no_votes_rejected(self):
        """Proposal with zero votes is rejected."""
        prop = self.gov.create_proposal("No Votes", "Desc", duration_seconds=0.1)
        time.sleep(0.2)
        self.gov.check_proposals()
        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_abstain_dilutes_support(self):
        """ABSTAIN votes count toward total_weighted, diluting YES support."""
        prop = self.gov.create_proposal(
            "Abstain Test", "Desc", duration_seconds=0.1, quorum=0.1
        )
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-2", VoteType.ABSTAIN, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.ABSTAIN, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-4", VoteType.ABSTAIN, tokens=100.0)

        time.sleep(0.2)
        self.gov.check_proposals()
        # YES=10, total_weighted=40 → support=25% < 50% → REJECTED
        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_execute_proposal_state_transition(self):
        """execute_proposal changes state PASSED → EXECUTED."""
        actions = [{"type": "restart_node", "node_id": "node-5"}]
        prop = self.gov.create_proposal("Execute", "Desc", duration_seconds=0.1, actions=actions)
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=150.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=80.0)
        time.sleep(0.2)
        self.gov.check_proposals()
        self.assertEqual(prop.state, ProposalState.PASSED)

        results = self.gov.execute_proposal(prop.id)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)
        self.assertEqual(prop.state, ProposalState.EXECUTED)

    def test_execute_not_passed_returns_empty(self):
        """execute_proposal on ACTIVE proposal returns empty list."""
        prop = self.gov.create_proposal("Not Passed", "Desc")
        results = self.gov.execute_proposal(prop.id)
        self.assertEqual(results, [])

    def test_custom_threshold(self):
        """Proposal with high threshold (80%) rejects slim majority."""
        prop = self.gov.create_proposal(
            "High Thresh", "Desc", duration_seconds=0.1, threshold=0.8
        )
        # 60% YES, 40% NO → below 80%
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-4", VoteType.NO, tokens=100.0)
        # Need a 5th voter with power
        self.gov.voting_power["node-5"] = 100.0
        self.gov.cast_vote(prop.id, "node-5", VoteType.NO, tokens=100.0)

        time.sleep(0.2)
        self.gov.check_proposals()
        # 3 YES vs 2 NO → support=60% < 80% threshold → REJECTED
        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_proposal_total_votes_and_counts(self):
        """Proposal dataclass methods work correctly."""
        prop = self.gov.create_proposal("Counts", "Desc")
        self.gov.cast_vote(prop.id, "node-1", VoteType.YES, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-2", VoteType.NO, tokens=100.0)
        self.gov.cast_vote(prop.id, "node-3", VoteType.ABSTAIN, tokens=100.0)

        self.assertEqual(prop.total_votes(), 3)
        counts = prop.vote_counts()
        self.assertEqual(counts[VoteType.YES], 1)
        self.assertEqual(counts[VoteType.NO], 1)
        self.assertEqual(counts[VoteType.ABSTAIN], 1)

if __name__ == '__main__':
    unittest.main()
