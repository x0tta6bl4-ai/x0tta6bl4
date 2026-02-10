"""Unit tests for src/dao/token_rewards.py - TokenRewards system.

Tests the X0T token reward calculation, settlement, balance tracking,
earnings projections, and blockchain integration paths.

NOTE: web3 is mocked at the conftest level via sys.modules, so
WEB3_AVAILABLE is True in the module under test. We rely on the
private_key guard to keep self.web3 = None for non-blockchain tests.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.dao.token_rewards import TokenRewards


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CONTRACT_ADDR = "0x" + "a" * 40
NODE_ADDR = "0x" + "b" * 40
FAKE_PRIVATE_KEY = "0x" + "c" * 64


def _make_rewards(private_key=None, rpc_url=None):
    """Create a TokenRewards instance without blockchain connection."""
    return TokenRewards(CONTRACT_ADDR, private_key=private_key, rpc_url=rpc_url)


# ===========================================================================
# TestTokenRewardsInit
# ===========================================================================

class TestTokenRewardsInit:
    """Tests for TokenRewards.__init__ default values and parameter handling."""

    def test_default_values(self):
        """Balance=1000.0, pending=0.0, total_distributed=0.0, daily_earnings=0.0."""
        tr = _make_rewards()
        assert tr.balance == Decimal("1000.0")
        assert tr.pending_rewards == Decimal("0.0")
        assert tr.total_distributed == Decimal("0.0")
        assert tr.daily_earnings == Decimal("0.0")

    def test_contract_address_stored(self):
        """contract_address is stored as provided."""
        tr = _make_rewards()
        assert tr.contract_address == CONTRACT_ADDR

    def test_private_key_from_parameter(self):
        """When private_key is passed explicitly, it is used (not env)."""
        tr = TokenRewards(CONTRACT_ADDR, private_key="my_secret_key")
        assert tr.private_key == "my_secret_key"

    def test_tx_history_starts_empty(self):
        """tx_history is an empty list on init."""
        tr = _make_rewards()
        assert tr.tx_history == []
        assert isinstance(tr.tx_history, list)


# ===========================================================================
# TestRewardRelay
# ===========================================================================

class TestRewardRelay:
    """Tests for the reward_relay method - reward calculation and settlement."""

    def test_reward_calculation_100_packets(self):
        """100 packets at 0.0001 X0T/packet = 0.01 X0T added to balance."""
        tr = _make_rewards()
        initial_balance = tr.balance
        tr.reward_relay(NODE_ADDR, 100)
        expected_reward = Decimal("0.01")
        assert tr.balance == initial_balance + expected_reward

    def test_pending_rewards_zero_after_settle(self):
        """After reward_relay, pending_rewards is reset to 0."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 100)
        assert tr.pending_rewards == Decimal("0.0")

    def test_total_distributed_increases(self):
        """total_distributed increases by the reward amount after relay."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 500)
        expected = Decimal("500") * Decimal("0.0001")
        assert tr.total_distributed == expected

    def test_daily_earnings_accumulates(self):
        """Multiple reward_relay calls accumulate daily_earnings."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 100)
        tr.reward_relay(NODE_ADDR, 200)
        tr.reward_relay(NODE_ADDR, 300)
        expected = Decimal("600") * Decimal("0.0001")  # 0.06
        assert tr.daily_earnings == expected

    def test_large_packet_count(self):
        """1,000,000 packets = 100 X0T reward."""
        tr = _make_rewards()
        initial_balance = tr.balance
        tr.reward_relay(NODE_ADDR, 1_000_000)
        expected_reward = Decimal("1000000") * Decimal("0.0001")
        assert expected_reward == Decimal("100")
        assert tr.balance == initial_balance + expected_reward
        assert tr.total_distributed == expected_reward


# ===========================================================================
# TestSettleRewards
# ===========================================================================

class TestSettleRewards:
    """Tests for _settle_rewards - balance and distribution tracking."""

    def test_does_nothing_when_pending_zero(self):
        """_settle_rewards with pending_rewards=0 does not change balance."""
        tr = _make_rewards()
        initial_balance = tr.balance
        initial_distributed = tr.total_distributed
        tr._settle_rewards(NODE_ADDR)
        assert tr.balance == initial_balance
        assert tr.total_distributed == initial_distributed

    def test_adds_pending_to_balance_and_distributed(self):
        """_settle_rewards adds pending_rewards to balance and total_distributed."""
        tr = _make_rewards()
        tr.pending_rewards = Decimal("5.5")
        initial_balance = tr.balance
        tr._settle_rewards(NODE_ADDR)
        assert tr.balance == initial_balance + Decimal("5.5")
        assert tr.total_distributed == Decimal("5.5")

    def test_resets_pending_after_settle(self):
        """pending_rewards is set to 0 after _settle_rewards."""
        tr = _make_rewards()
        tr.pending_rewards = Decimal("10.0")
        tr._settle_rewards(NODE_ADDR)
        assert tr.pending_rewards == Decimal("0.0")


# ===========================================================================
# TestGetBalance
# ===========================================================================

class TestGetBalance:
    """Tests for get_balance - formatted string output."""

    def test_initial_balance_formatted(self):
        """Initial balance returns '1000.0000' as formatted string."""
        tr = _make_rewards()
        result = tr.get_balance(NODE_ADDR)
        assert result == "1000.0000"

    def test_balance_after_rewards(self):
        """Balance updates correctly after reward_relay and is properly formatted."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 10000)  # 1.0 X0T
        result = tr.get_balance(NODE_ADDR)
        assert result == "1001.0000"


# ===========================================================================
# TestGetDailyEarnings
# ===========================================================================

class TestGetDailyEarnings:
    """Tests for get_daily_earnings - formatted daily earnings."""

    def test_initial_daily_earnings(self):
        """Daily earnings starts at '0.0000'."""
        tr = _make_rewards()
        result = tr.get_daily_earnings(NODE_ADDR)
        assert result == "0.0000"

    def test_daily_earnings_after_relay(self):
        """Daily earnings reflects accumulated rewards from relay calls."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 5000)  # 0.5 X0T
        result = tr.get_daily_earnings(NODE_ADDR)
        assert result == "0.5000"


# ===========================================================================
# TestGetMonthlyProjection
# ===========================================================================

class TestGetMonthlyProjection:
    """Tests for get_monthly_projection - daily * 30 calculation."""

    def test_initial_monthly_projection(self):
        """Monthly projection is '0.00' when no earnings."""
        tr = _make_rewards()
        result = tr.get_monthly_projection(NODE_ADDR)
        assert result == "0.00"

    def test_monthly_projection_after_relay(self):
        """Monthly projection = daily_earnings * 30, formatted to 2 decimal places."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 10000)  # daily = 1.0 X0T
        result = tr.get_monthly_projection(NODE_ADDR)
        # 1.0 * 30 = 30.00
        assert result == "30.00"


# ===========================================================================
# TestGetBlockchainBalance
# ===========================================================================

class TestGetBlockchainBalance:
    """Tests for get_blockchain_balance - fallback and blockchain paths."""

    def test_fallback_to_local_balance_without_web3(self):
        """When web3 is None, returns local balance formatted."""
        tr = _make_rewards()
        assert tr.web3 is None
        result = tr.get_blockchain_balance()
        assert result == "1000.0000"

    def test_fallback_after_rewards(self):
        """Fallback local balance reflects rewards when web3 is not configured."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 20000)  # 2.0 X0T
        result = tr.get_blockchain_balance()
        assert result == "1002.0000"


# ===========================================================================
# TestBlockchainIntegration
# ===========================================================================

class TestBlockchainIntegration:
    """Tests for blockchain-related behavior and edge cases."""

    def test_send_blockchain_reward_returns_none_without_web3(self):
        """_send_blockchain_reward returns None when self.web3 is None."""
        tr = _make_rewards()
        assert tr.web3 is None
        result = tr._send_blockchain_reward(NODE_ADDR, Decimal("1.0"))
        assert result is None

    def test_tx_history_empty_without_blockchain(self):
        """tx_history remains empty when no blockchain transactions occur."""
        tr = _make_rewards()
        tr.reward_relay(NODE_ADDR, 500)
        tr.reward_relay(NODE_ADDR, 1000)
        assert tr.tx_history == []
        assert len(tr.tx_history) == 0
