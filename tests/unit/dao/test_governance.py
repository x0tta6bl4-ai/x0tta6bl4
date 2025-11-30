
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

if __name__ == '__main__':
    unittest.main()
