
import unittest
import sys
import os
import time

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

try:
    from dao.governance import GovernanceEngine, VoteType, ProposalState
    from security.pqc_identity import PQCNodeIdentity
    from libx0t.security.post_quantum import LIBOQS_AVAILABLE
except ImportError:
    # Fallback
    from src.dao.governance import GovernanceEngine, VoteType, ProposalState
    from src.security.pqc_identity import PQCNodeIdentity
    from src.libx0t.security.post_quantum import LIBOQS_AVAILABLE

class TestPQCGovernance(unittest.TestCase):

    def setUp(self):
        if not LIBOQS_AVAILABLE:
            self.skipTest("liboqs-python not available")
        
        self.engine = GovernanceEngine(node_id="coordinator")
        self.voter_id = "voter-007"
        self.voter_identity = PQCNodeIdentity(self.voter_id)
        
        # Create a test proposal
        self.proposal = self.engine.create_proposal(
            title="Update Mesh Threshold",
            description="Increase anomaly threshold to 0.85",
            duration_seconds=100
        )

    def test_cast_vote_with_valid_pqc_signature(self):
        """Test voting with a valid PQC signature."""
        proposal_id = self.proposal.id
        vote_value = VoteType.YES.value
        
        # Construct the payload that cast_vote expects to be signed
        payload = f"{proposal_id}:{self.voter_id}:{vote_value}".encode('utf-8')
        
        # Sign with voter's PQC identity
        signature = self.voter_identity.security.sign(payload).hex()
        pubkey = self.voter_identity.security.get_public_keys()['sig_public_key']
        
        # Cast vote
        success = self.engine.cast_vote(
            proposal_id=proposal_id,
            voter_id=self.voter_id,
            vote=VoteType.YES,
            signature=signature,
            voter_pubkey=pubkey
        )
        
        self.assertTrue(success)
        self.assertEqual(self.proposal.votes[self.voter_id], VoteType.YES)

    def test_cast_vote_with_invalid_signature(self):
        """Test that an invalid signature rejects the vote."""
        proposal_id = self.proposal.id
        
        # Wrong payload
        payload = b"wrong-data"
        signature = self.voter_identity.security.sign(payload).hex()
        pubkey = self.voter_identity.security.get_public_keys()['sig_public_key']
        
        success = self.engine.cast_vote(
            proposal_id=proposal_id,
            voter_id=self.voter_id,
            vote=VoteType.YES,
            signature=signature,
            voter_pubkey=pubkey
        )
        
        self.assertFalse(success)
        self.assertNotIn(self.voter_id, self.proposal.votes)

    def test_cast_vote_tampered_data(self):
        """Test that tampering with vote parameters invalidates the PQC signature."""
        proposal_id = self.proposal.id
        
        # Sign YES
        payload = f"{proposal_id}:{self.voter_id}:{VoteType.YES.value}".encode('utf-8')
        signature = self.voter_identity.security.sign(payload).hex()
        pubkey = self.voter_identity.security.get_public_keys()['sig_public_key']
        
        # Try to cast NO with the signature meant for YES
        success = self.engine.cast_vote(
            proposal_id=proposal_id,
            voter_id=self.voter_id,
            vote=VoteType.NO, # Tampered!
            signature=signature,
            voter_pubkey=pubkey
        )
        
        self.assertFalse(success)

if __name__ == '__main__':
    unittest.main()
