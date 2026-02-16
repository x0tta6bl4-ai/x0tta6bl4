"""
Unit tests for Token Bridge (off-chain ↔ on-chain sync).
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from src.dao.token import MeshToken
from src.dao.token_bridge import (BridgeConfig, BridgeDirection,
                                  BridgeTransaction, EpochRewardScheduler,
                                  TokenBridge)


class TestTokenBridge(unittest.TestCase):
    """Test TokenBridge without actual blockchain connection."""

    def setUp(self):
        self.token = MeshToken()
        self.config = BridgeConfig(
            rpc_url="http://localhost:8545",
            contract_address="0x1234567890123456789012345678901234567890",
            private_key="0x" + "1" * 64,
            chain_id=31337,
        )
        self.bridge = TokenBridge(self.token, self.config)

    def test_address_registration(self):
        """Test node_id ↔ eth_address mapping."""
        self.bridge.register_address(
            "node-1", "0xABCDEF1234567890ABCDEF1234567890ABCDEF12"
        )

        # Get eth address
        eth_addr = self.bridge.get_eth_address("node-1")
        self.assertIsNotNone(eth_addr)
        self.assertTrue(eth_addr.startswith("0x"))

        # Get node_id from address
        node_id = self.bridge.get_node_id(eth_addr)
        self.assertEqual(node_id, "node-1")

    def test_address_not_found(self):
        """Test lookup for unregistered address."""
        self.assertIsNone(self.bridge.get_eth_address("unknown-node"))
        self.assertIsNone(
            self.bridge.get_node_id("0x0000000000000000000000000000000000000000")
        )

    def test_event_handler_registration(self):
        """Test registering event handlers."""
        handler_called = []

        def on_stake(event):
            handler_called.append(event)

        self.bridge.on_event("Staked", on_stake)

        self.assertEqual(len(self.bridge._event_handlers["Staked"]), 1)

    def test_tx_history(self):
        """Test transaction history tracking."""
        # Manually add a transaction
        tx = BridgeTransaction(
            tx_id="test_tx_1",
            direction=BridgeDirection.FROM_CHAIN,
            from_address="0x123",
            to_address="0x456",
            amount=100.0,
            event_type="Transfer",
            timestamp=1234567890,
            block_number=12345,
            tx_hash="0xabc123",
            status="confirmed",
        )
        self.bridge._tx_history.append(tx)

        history = self.bridge.get_tx_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].tx_id, "test_tx_1")

    def test_pending_txs(self):
        """Test filtering pending transactions."""
        self.bridge._tx_history.append(
            BridgeTransaction(
                tx_id="tx1",
                direction=BridgeDirection.TO_CHAIN,
                from_address="",
                to_address="",
                amount=0,
                event_type="",
                timestamp=0,
                status="pending",
            )
        )
        self.bridge._tx_history.append(
            BridgeTransaction(
                tx_id="tx2",
                direction=BridgeDirection.TO_CHAIN,
                from_address="",
                to_address="",
                amount=0,
                event_type="",
                timestamp=0,
                status="confirmed",
            )
        )

        pending = self.bridge.get_pending_txs()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].tx_id, "tx1")


class TestBridgeSyncLogic(unittest.TestCase):
    """Test sync logic without blockchain."""

    def setUp(self):
        self.token = MeshToken()
        self.config = BridgeConfig()
        self.bridge = TokenBridge(self.token, self.config)

        # Register test addresses
        self.bridge.register_address(
            "node-1", "0x1111111111111111111111111111111111111111"
        )
        self.bridge.register_address(
            "node-2", "0x2222222222222222222222222222222222222222"
        )

    def test_sync_stake_creates_balance(self):
        """Sync stake should create balance if needed."""
        # Run sync
        asyncio.run(
            self.bridge._sync_stake(
                "0x1111111111111111111111111111111111111111",
                500 * 10**18,  # 500 X0T in wei
                is_stake=True,
            )
        )

        # Check local state
        self.assertEqual(self.token.staked_amount("node-1"), 500.0)

    def test_sync_transfer_mints_for_deposit(self):
        """Transfer from unknown address should mint (deposit from exchange)."""
        # Run sync - from unknown address to known node
        asyncio.run(
            self.bridge._sync_transfer(
                "0x9999999999999999999999999999999999999999",  # Unknown
                "0x1111111111111111111111111111111111111111",  # node-1
                1000 * 10**18,
            )
        )

        # node-1 should have received tokens
        self.assertEqual(self.token.balance_of("node-1"), 1000.0)

    def test_sync_transfer_between_known_nodes(self):
        """Transfer between known nodes should sync locally."""
        # Give node-1 some tokens first
        self.token.mint("node-1", 500, "test")

        # Sync transfer
        asyncio.run(
            self.bridge._sync_transfer(
                "0x1111111111111111111111111111111111111111",
                "0x2222222222222222222222222222222222222222",
                200 * 10**18,
            )
        )

        # Check balances
        self.assertEqual(self.token.balance_of("node-1"), 300.0)
        self.assertEqual(self.token.balance_of("node-2"), 200.0)


class TestBridgeWithMockWeb3(unittest.TestCase):
    """Test bridge with mocked Web3."""

    def setUp(self):
        self.token = MeshToken()
        self.config = BridgeConfig(
            contract_address="0x1234567890123456789012345678901234567890",
            private_key="0x" + "1" * 64,
        )
        self.bridge = TokenBridge(self.token, self.config)

        # Register addresses
        self.bridge.register_address(
            "node-1", "0x1111111111111111111111111111111111111111"
        )
        self.bridge.register_address(
            "node-2", "0x2222222222222222222222222222222222222222"
        )

    @patch("src.dao.token_bridge.TokenBridge._init_web3")
    def test_get_chain_stats_without_connection(self, mock_init):
        """Should return empty dict if not connected."""
        mock_init.return_value = False

        stats = self.bridge.get_chain_stats()
        self.assertEqual(stats, {})

    @patch("src.dao.token_bridge.TokenBridge._init_web3")
    def test_push_rewards_without_connection(self, mock_init):
        """Should return None if not connected."""
        mock_init.return_value = False

        result = asyncio.run(self.bridge.push_rewards_to_chain({"node-1": 100}))
        self.assertIsNone(result)


class TestEpochRewardScheduler(unittest.TestCase):
    """Test automatic epoch reward scheduler."""

    def setUp(self):
        self.token = MeshToken()
        self.config = BridgeConfig()
        self.bridge = TokenBridge(self.token, self.config)

        # Mock uptime provider
        self.uptimes = {"node-1": 0.95, "node-2": 0.80}
        self.uptime_provider = Mock(return_value=self.uptimes)

        self.scheduler = EpochRewardScheduler(self.bridge, self.uptime_provider)

    def test_scheduler_creation(self):
        """Scheduler should be created with bridge and provider."""
        self.assertIsNotNone(self.scheduler.bridge)
        self.assertIsNotNone(self.scheduler.uptime_provider)

    def test_uptime_provider_called(self):
        """Uptime provider should be callable."""
        result = self.scheduler.uptime_provider()
        self.assertEqual(result, self.uptimes)
        self.uptime_provider.assert_called_once()

    def test_scheduler_stop(self):
        """Scheduler should stop when requested."""
        self.scheduler._running = True
        self.scheduler.stop()
        self.assertFalse(self.scheduler._running)


class TestBridgeIntegration(unittest.TestCase):
    """Integration tests for bridge with MeshToken."""

    def test_full_sync_cycle(self):
        """Test complete sync cycle: chain event → local update."""
        token = MeshToken()
        config = BridgeConfig()
        bridge = TokenBridge(token, config)

        # Register nodes
        bridge.register_address("alice", "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        bridge.register_address("bob", "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB")

        # Simulate deposit from exchange to alice
        asyncio.run(
            bridge._sync_transfer(
                "0x0000000000000000000000000000000000000000",  # From exchange
                "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # To alice
                10000 * 10**18,
            )
        )

        # Alice stakes
        asyncio.run(
            bridge._sync_stake(
                "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                5000 * 10**18,
                is_stake=True,
            )
        )

        # Alice transfers to bob
        asyncio.run(
            bridge._sync_transfer(
                "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "0xBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                1000 * 10**18,
            )
        )

        # Verify final state
        # Alice: 10000 (deposit) - 5000 (stake) - 1000 (transfer) = 4000
        # But stake uses balance, so: 10000 - 1000 = 9000 balance, 5000 staked
        # Actually stake mints if needed, so:
        # After deposit: alice = 10000
        # After stake: alice balance = 10000 (mint 5000 if needed, then stake 5000)
        # Wait, let's trace through:

        # 1. Deposit: alice gets 10000 minted
        self.assertEqual(token.balance_of("alice"), 4000.0)  # After transfer
        self.assertEqual(token.staked_amount("alice"), 5000.0)
        self.assertEqual(token.balance_of("bob"), 1000.0)

    def test_multiple_address_mappings(self):
        """Test handling multiple node registrations."""
        token = MeshToken()
        bridge = TokenBridge(token, BridgeConfig())

        # Register many nodes
        for i in range(10):
            addr = f"0x{i:040x}"
            bridge.register_address(f"node-{i}", addr)

        # Verify all mappings
        for i in range(10):
            addr = bridge.get_eth_address(f"node-{i}")
            self.assertIsNotNone(addr)

            node_id = bridge.get_node_id(addr)
            self.assertEqual(node_id, f"node-{i}")


class TestBridgeConfig(unittest.TestCase):
    """Test bridge configuration."""

    def test_default_config(self):
        """Default config should have sensible values."""
        config = BridgeConfig()

        self.assertEqual(config.chain_id, 84532)  # Base Sepolia
        self.assertEqual(config.poll_interval, 12)
        self.assertEqual(config.confirmations, 2)

    def test_custom_config(self):
        """Custom config should override defaults."""
        config = BridgeConfig(
            rpc_url="https://polygon-rpc.com", chain_id=137, poll_interval=2
        )

        self.assertEqual(config.chain_id, 137)
        self.assertEqual(config.poll_interval, 2)


if __name__ == "__main__":
    unittest.main()
