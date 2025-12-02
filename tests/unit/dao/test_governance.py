
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
        
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES)
        self.gov.cast_vote(prop.id, "node-4", VoteType.NO)
        
        counts = prop.vote_counts()
        self.assertEqual(counts[VoteType.YES], 2)
        self.assertEqual(counts[VoteType.NO], 1)
        
    def test_tally_passing(self):
        # Create short lived proposal
        prop = self.gov.create_proposal("Fast Vote", "Desc", duration_seconds=0.1)
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES)
        
        time.sleep(0.2)
        self.gov.check_proposals()
        
        self.assertEqual(prop.state, ProposalState.PASSED)

    def test_multi_node_majority_pass(self):
        """Несколько нод голосуют, большинство YES → PASSED."""
        prop = self.gov.create_proposal("Multi-node Pass", "Desc", duration_seconds=0.1)

        # 3 YES, 1 NO
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES)
        self.gov.cast_vote(prop.id, "node-3", VoteType.YES)
        self.gov.cast_vote(prop.id, "node-4", VoteType.YES)
        self.gov.cast_vote(prop.id, "node-5", VoteType.NO)

        time.sleep(0.2)
        self.gov.check_proposals()

        self.assertEqual(prop.state, ProposalState.PASSED)

    def test_multi_node_reject(self):
        """Несколько нод, большинство NO → REJECTED."""
        prop = self.gov.create_proposal("Multi-node Reject", "Desc", duration_seconds=0.1)

        # 1 YES, 3 NO
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES)
        self.gov.cast_vote(prop.id, "node-3", VoteType.NO)
        self.gov.cast_vote(prop.id, "node-4", VoteType.NO)
        self.gov.cast_vote(prop.id, "node-5", VoteType.NO)

        time.sleep(0.2)
        self.gov.check_proposals()

        self.assertEqual(prop.state, ProposalState.REJECTED)

    def test_vote_overwrite_last_vote_counts(self):
        """Повторное голосование тем же узлом перезаписывает его голос, а не добавляет новый."""
        prop = self.gov.create_proposal("Overwrite Vote", "Desc", duration_seconds=0.1)

        self.gov.cast_vote(prop.id, "node-2", VoteType.NO)
        # Тот же узел меняет мнение на YES
        self.gov.cast_vote(prop.id, "node-2", VoteType.YES)

        counts = prop.vote_counts()
        self.assertEqual(counts[VoteType.YES], 1)
        self.assertEqual(counts[VoteType.NO], 0)

if __name__ == '__main__':
    unittest.main()
