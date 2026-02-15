"""
Unit tests for relay rewards integration in NodeManager.
"""

import unittest

from src.dao.token import MeshToken
from src.network.batman.node_manager import NodeManager


class TestRelayRewards(unittest.TestCase):
    """Test relay packet rewards."""

    def setUp(self):
        self.token = MeshToken()
        self.manager = NodeManager(mesh_id="test-mesh", local_node_id="relay-node")
        self.manager.set_token(self.token)

        # Give source node some tokens to pay for relay
        self.token.mint("source-node", 1000, "initial")

    def test_relay_earns_tokens(self):
        """Relay node earns X0T for relaying packets."""
        initial_balance = self.token.balance_of("relay-node")

        # Relay 100 packets
        for _ in range(100):
            result = self.manager.relay_packet(
                source_node="source-node", dest_node="dest-node"
            )
            self.assertTrue(result)

        # Check relay node earned tokens
        # Price per relay = 0.0001 X0T, 100 relays = 0.01 X0T (minus 1% fee burned)
        final_balance = self.token.balance_of("relay-node")
        self.assertGreater(final_balance, initial_balance)
        self.assertAlmostEqual(final_balance, 0.01, places=4)

    def test_relay_count_tracked(self):
        """Relay count is tracked correctly."""
        self.assertEqual(self.manager.get_relay_count(), 0)

        for _ in range(50):
            self.manager.relay_packet("source-node", "dest-node")

        self.assertEqual(self.manager.get_relay_count(), 50)

    def test_relay_earnings_estimate(self):
        """Relay earnings estimate is correct."""
        for _ in range(1000):
            self.manager.relay_packet("source-node", "dest-node")

        # 1000 relays * 0.0001 = 0.1 X0T
        earnings = self.manager.get_relay_earnings()
        self.assertAlmostEqual(earnings, 0.1, places=4)

    def test_relay_without_token(self):
        """Relay works without token system (no rewards)."""
        manager_no_token = NodeManager(
            mesh_id="test-mesh", local_node_id="relay-node-2"
        )

        # Should still work, just no rewards
        result = manager_no_token.relay_packet("source-node", "dest-node")
        self.assertTrue(result)
        self.assertEqual(manager_no_token.get_relay_count(), 1)
        self.assertEqual(manager_no_token.get_relay_earnings(), 0.0)

    def test_relay_to_external_node_works(self):
        """Can relay to external node (mesh routing handles discovery)."""
        result = self.manager.relay_packet("source-node", "external-node")
        self.assertTrue(result)

    def test_source_pays_for_relay(self):
        """Source node balance decreases when paying for relay."""
        initial_source_balance = self.token.balance_of("source-node")

        for _ in range(100):
            self.manager.relay_packet("source-node", "dest-node")

        # Source paid for 100 relays
        final_source_balance = self.token.balance_of("source-node")
        self.assertLess(final_source_balance, initial_source_balance)

        # Cost = 100 * 0.0001 * 1.01 (price + 1% fee) ≈ 0.0101
        expected_cost = 100 * 0.0001 * 1.01
        actual_cost = initial_source_balance - final_source_balance
        self.assertAlmostEqual(actual_cost, expected_cost, places=4)


class TestRelayRewardsIntegration(unittest.TestCase):
    """Integration tests for relay rewards with full token economics."""

    def test_relay_network_simulation(self):
        """Simulate a small relay network with token economics."""
        token = MeshToken()

        # Create 3 nodes
        nodes = {}
        for i in range(3):
            node_id = f"node-{i}"
            nodes[node_id] = NodeManager(mesh_id="test-mesh", local_node_id=node_id)
            nodes[node_id].set_token(token)
            token.mint(node_id, 10000, "initial")

        # Simulate traffic: node-0 sends to node-2 via node-1 (relay)
        for _ in range(1000):
            # node-1 relays packets from node-0 to node-2
            nodes["node-1"].relay_packet("node-0", "node-2")

        # Check balances
        # node-0 paid for 1000 relays
        # node-1 earned from 1000 relays
        # node-2 unchanged

        self.assertLess(token.balance_of("node-0"), 10000)
        self.assertGreater(token.balance_of("node-1"), 10000)
        self.assertEqual(token.balance_of("node-2"), 10000)

        # Verify relay count
        self.assertEqual(nodes["node-1"].get_relay_count(), 1000)


if __name__ == "__main__":
    unittest.main()
