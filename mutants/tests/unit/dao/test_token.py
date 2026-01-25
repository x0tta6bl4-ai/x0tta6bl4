"""
Unit tests for MeshToken (x0tta6bl4 token economics).
"""
import unittest
import time
from src.dao.token import MeshToken, ResourceType, create_token_integrated_governance


class TestMeshToken(unittest.TestCase):
    
    def setUp(self):
        self.token = MeshToken()
        # Give some initial tokens to test nodes
        self.token.mint("node-1", 10000, "initial")
        self.token.mint("node-2", 5000, "initial")
        self.token.mint("node-3", 2000, "initial")
    
    # ─────────────────────────────────────────────────────────────
    # Basic Token Operations
    # ─────────────────────────────────────────────────────────────
    
    def test_balance_of(self):
        """Balance correctly reflects minted tokens."""
        self.assertEqual(self.token.balance_of("node-1"), 10000)
        self.assertEqual(self.token.balance_of("node-2"), 5000)
        self.assertEqual(self.token.balance_of("unknown"), 0)
    
    def test_transfer_success(self):
        """Transfer moves tokens between nodes."""
        result = self.token.transfer("node-1", "node-2", 1000)
        
        self.assertTrue(result)
        self.assertEqual(self.token.balance_of("node-1"), 9000)
        self.assertEqual(self.token.balance_of("node-2"), 6000)
    
    def test_transfer_insufficient_balance(self):
        """Transfer fails if sender has insufficient balance."""
        result = self.token.transfer("node-3", "node-1", 5000)
        
        self.assertFalse(result)
        self.assertEqual(self.token.balance_of("node-3"), 2000)  # Unchanged
    
    def test_transfer_invalid_amount(self):
        """Transfer fails for zero or negative amounts."""
        self.assertFalse(self.token.transfer("node-1", "node-2", 0))
        self.assertFalse(self.token.transfer("node-1", "node-2", -100))
    
    def test_burn_reduces_supply(self):
        """Burn removes tokens from circulation."""
        initial_supply = self.token.total_supply
        
        result = self.token.burn("node-1", 500, "test_burn")
        
        self.assertTrue(result)
        self.assertEqual(self.token.balance_of("node-1"), 9500)
        self.assertEqual(self.token.total_supply, initial_supply - 500)
    
    # ─────────────────────────────────────────────────────────────
    # Staking
    # ─────────────────────────────────────────────────────────────
    
    def test_stake_success(self):
        """Staking locks tokens and grants voting power."""
        result = self.token.stake("node-1", 1000)
        
        self.assertTrue(result)
        self.assertEqual(self.token.balance_of("node-1"), 9000)  # Deducted
        self.assertEqual(self.token.staked_amount("node-1"), 1000)
        self.assertEqual(self.token.voting_power("node-1"), 1000)
    
    def test_stake_below_minimum(self):
        """Staking below minimum fails."""
        result = self.token.stake("node-1", 50)  # MIN_STAKE = 100
        
        self.assertFalse(result)
        self.assertEqual(self.token.staked_amount("node-1"), 0)
    
    def test_stake_insufficient_balance(self):
        """Staking more than balance fails."""
        result = self.token.stake("node-3", 5000)  # Only has 2000
        
        self.assertFalse(result)
    
    def test_stake_accumulates(self):
        """Multiple stakes accumulate."""
        self.token.stake("node-1", 500)
        self.token.stake("node-1", 500)
        
        self.assertEqual(self.token.staked_amount("node-1"), 1000)
        self.assertEqual(self.token.balance_of("node-1"), 9000)
    
    def test_unstake_locked(self):
        """Cannot unstake during lock period."""
        self.token.stake("node-1", 1000)
        
        # Immediately try to unstake (should fail due to lock)
        result = self.token.unstake("node-1", 500)
        
        self.assertFalse(result)
        self.assertEqual(self.token.staked_amount("node-1"), 1000)
    
    def test_unstake_after_lock(self):
        """Can unstake after lock period expires."""
        self.token.stake("node-1", 1000)
        
        # Manually expire the lock for testing
        self.token.stakes["node-1"].lock_until = time.time() - 1
        
        result = self.token.unstake("node-1", 500)
        
        self.assertTrue(result)
        self.assertEqual(self.token.staked_amount("node-1"), 500)
        self.assertEqual(self.token.balance_of("node-1"), 9500)
    
    def test_total_staked(self):
        """Total staked aggregates all stakes."""
        self.token.stake("node-1", 1000)
        self.token.stake("node-2", 500)
        
        self.assertEqual(self.token.total_staked(), 1500)
    
    # ─────────────────────────────────────────────────────────────
    # Resource Payments
    # ─────────────────────────────────────────────────────────────
    
    def test_resource_price_calculation(self):
        """Resource prices calculated correctly."""
        bandwidth_price = self.token.get_resource_price(ResourceType.BANDWIDTH, 1000)  # 1000 MB
        self.assertEqual(bandwidth_price, 1.0)  # 0.001 * 1000
        
        relay_price = self.token.get_resource_price(ResourceType.RELAY, 10000)  # 10k relays
        self.assertEqual(relay_price, 1.0)  # 0.0001 * 10000
    
    def test_pay_for_resource(self):
        """Resource payment transfers to provider and burns fee."""
        initial_supply = self.token.total_supply
        
        # node-1 pays node-2 for 1000 MB bandwidth
        result = self.token.pay_for_resource(
            payer_node="node-1",
            provider_node="node-2",
            resource_type=ResourceType.BANDWIDTH,
            amount=1000
        )
        
        self.assertTrue(result)
        
        # Price = 1.0, Fee = 0.01 (1%), Total = 1.01
        self.assertAlmostEqual(self.token.balance_of("node-1"), 10000 - 1.01, places=4)
        self.assertAlmostEqual(self.token.balance_of("node-2"), 5000 + 1.0, places=4)
        self.assertAlmostEqual(self.token.total_supply, initial_supply - 0.01, places=4)
    
    def test_pay_for_resource_insufficient_balance(self):
        """Resource payment fails if payer has insufficient balance."""
        # node-3 only has 2000, try to pay for huge amount
        result = self.token.pay_for_resource(
            payer_node="node-3",
            provider_node="node-1",
            resource_type=ResourceType.COMPUTE,
            amount=1_000_000  # Would cost 10,000 tokens
        )
        
        self.assertFalse(result)
        self.assertEqual(self.token.balance_of("node-3"), 2000)  # Unchanged
    
    # ─────────────────────────────────────────────────────────────
    # Rewards Distribution
    # ─────────────────────────────────────────────────────────────
    
    def test_epoch_rewards_distribution(self):
        """Rewards distributed proportionally to stake * uptime."""
        # Setup stakes
        self.token.stake("node-1", 1000)  # 1000 staked
        self.token.stake("node-2", 500)   # 500 staked
        
        # Force epoch to be complete
        self.token.last_epoch_time = time.time() - self.token.EPOCH_DURATION_SECONDS - 1
        
        # Distribute with uptimes
        uptimes = {
            "node-1": 1.0,   # 100% uptime
            "node-2": 0.5,   # 50% uptime
        }
        
        rewards = self.token.distribute_epoch_rewards(uptimes)
        
        # node-1 score = 1000 * 1.0 = 1000
        # node-2 score = 500 * 0.5 = 250
        # Total score = 1250
        # node-1 reward = (1000/1250) * 10000 = 8000
        # node-2 reward = (250/1250) * 10000 = 2000
        
        self.assertIn("node-1", rewards)
        self.assertIn("node-2", rewards)
        self.assertAlmostEqual(rewards["node-1"], 8000, places=0)
        self.assertAlmostEqual(rewards["node-2"], 2000, places=0)
    
    def test_epoch_rewards_no_stakers(self):
        """No rewards if no one is staking."""
        self.token.last_epoch_time = time.time() - self.token.EPOCH_DURATION_SECONDS - 1
        
        rewards = self.token.distribute_epoch_rewards({"node-1": 1.0})
        
        self.assertEqual(rewards, {})
    
    # ─────────────────────────────────────────────────────────────
    # Governance Integration
    # ─────────────────────────────────────────────────────────────
    
    def test_governance_integration(self):
        """GovernanceEngine voting power syncs with token stakes."""
        self.token.stake("node-1", 1000)
        self.token.stake("node-2", 500)
        
        gov = create_token_integrated_governance(self.token, "node-1")
        
        self.assertEqual(gov.voting_power["node-1"], 1000)
        self.assertEqual(gov.voting_power["node-2"], 500)
    
    def test_governance_voting_power_updates_on_stake(self):
        """Voting power updates when stake changes."""
        gov = create_token_integrated_governance(self.token, "node-1")
        
        # Initially no stakes
        self.assertEqual(gov.voting_power.get("node-1", 0), 0)
        
        # Stake and verify sync
        self.token.stake("node-1", 1000)
        self.assertEqual(gov.voting_power["node-1"], 1000)
        
        # Stake more
        self.token.stake("node-1", 500)
        self.assertEqual(gov.voting_power["node-1"], 1500)


class TestTokenCallbacks(unittest.TestCase):
    """Test callback/hook functionality."""
    
    def test_transfer_callback(self):
        """Transfer triggers callback."""
        token = MeshToken()
        token.mint("node-1", 1000, "test")
        
        transfers = []
        token.on_transfer(lambda f, t, a: transfers.append((f, t, a)))
        
        token.transfer("node-1", "node-2", 100)
        
        self.assertEqual(len(transfers), 1)
        self.assertEqual(transfers[0], ("node-1", "node-2", 100))
    
    def test_stake_change_callback(self):
        """Stake change triggers callback."""
        token = MeshToken()
        token.mint("node-1", 1000, "test")
        
        stake_changes = []
        token.on_stake_change(lambda n, a: stake_changes.append((n, a)))
        
        token.stake("node-1", 500)
        
        self.assertEqual(len(stake_changes), 1)
        self.assertEqual(stake_changes[0], ("node-1", 500))


if __name__ == "__main__":
    unittest.main()
