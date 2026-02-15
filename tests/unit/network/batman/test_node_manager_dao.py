import unittest

from src.network.batman.node_manager import NodeManager


class TestNodeManagerDAO(unittest.TestCase):
    def setUp(self):
        self.nm = NodeManager(mesh_id="mesh-dao", local_node_id="node-gov")

    def test_governance_init(self):
        self.assertIsNotNone(self.nm.governance)

    def test_proposal_flow(self):
        # Create proposal
        prop_id = self.nm.propose_network_update("Upgrade Firmware", {"version": "2.0"})
        self.assertIsNotNone(prop_id)

        # Vote
        result = self.nm.vote_on_proposal(prop_id, "YES")
        self.assertTrue(result)

        # Verify vote count
        prop = self.nm.governance.proposals[prop_id]
        counts = prop.vote_counts()
        self.assertEqual(counts[list(counts.keys())[0]], 1)  # YES


if __name__ == "__main__":
    unittest.main()
