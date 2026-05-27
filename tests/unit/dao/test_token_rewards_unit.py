"""Unit tests for src/dao/token_rewards.py - TokenRewards system.

Tests the X0T token reward calculation, settlement, balance tracking,
earnings projections, and blockchain integration paths.

NOTE: web3 is mocked at the conftest level via sys.modules, so
WEB3_AVAILABLE is True in the module under test. We rely on the
private_key guard to keep self.web3 = None for non-blockchain tests.
"""

from decimal import Decimal


from src.coordination.events import EventBus, EventType
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

    def test_reward_relay_reports_local_accounting_without_chain_tx(self):
        """Local-only settlement is explicit so production callers cannot treat it as a chain receipt."""
        tr = _make_rewards()
        result = tr.reward_relay(NODE_ADDR, 100)

        assert result["ok"] is True
        assert result["status"] == "local_accounting_only"
        assert result["settlement_recorded"] is True
        assert result["local_accounting_recorded"] is True
        assert result["submitted_transaction"] is False
        assert result["simulated"] is True
        assert result["transaction_hash"] == ""

    def test_reward_relay_publishes_canonical_event_when_event_bus_is_bound(self, tmp_path):
        """Reward settlement can be correlated through the shared EventBus when callers opt in."""
        bus = EventBus(project_root=str(tmp_path))
        tr = TokenRewards(
            CONTRACT_ADDR,
            private_key=None,
            event_bus=bus,
            source_agent="token-rewards-test",
            node_id="node-1",
            spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/relay",
            did="did:mesh:pqc:node-1",
            wallet_address=NODE_ADDR,
        )

        result = tr.reward_relay(NODE_ADDR, 100)

        events = bus.get_event_history(event_type=EventType.REWARD_RELAY_RECORDED)
        assert len(events) == 1
        event = events[0]
        assert result["event_id"] == event.event_id
        assert event.source_agent == "token-rewards-test"
        assert event.data["identity"] == {
            "node_id": "node-1",
            "spiffe_id": "spiffe://mesh.x0tta6bl4.mesh/workload/relay",
            "did": "did:mesh:pqc:node-1",
            "wallet_address": NODE_ADDR,
            "reward_address": NODE_ADDR,
        }
        assert event.data["packets"] == 100
        assert event.data["amount"] == "0.0100"
        assert event.data["status"] == "local_accounting_only"
        assert event.data["simulated"] is True
        assert event.data["submitted_transaction"] is False


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
        result = tr._settle_rewards(NODE_ADDR)
        assert tr.balance == initial_balance
        assert tr.total_distributed == initial_distributed
        assert result["status"] == "noop"
        assert result["settlement_recorded"] is False

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

    def test_settle_rewards_reports_blockchain_submission_when_tx_hash_exists(self):
        """A configured blockchain path returns the transaction hash for upstream settlement gates."""
        tr = _make_rewards()
        tr.web3 = object()
        tr.contract = object()
        tr.account = object()
        tr.pending_rewards = Decimal("1.25")
        tx_hash = "0x" + "d" * 64
        tr._send_blockchain_reward = lambda node_address, amount: tx_hash

        result = tr._settle_rewards(NODE_ADDR)

        assert result["ok"] is True
        assert result["status"] == "blockchain_submitted"
        assert result["submitted_transaction"] is True
        assert result["simulated"] is False
        assert result["transaction_hash"] == tx_hash
        assert tr.tx_history == [
            {
                "hash": tx_hash,
                "amount": "1.25",
                "to": NODE_ADDR,
                "timestamp": tr.tx_history[0]["timestamp"],
            }
        ]

    def test_settle_rewards_publishes_blocked_event_when_blockchain_submission_fails(self, tmp_path):
        bus = EventBus(project_root=str(tmp_path))
        tr = TokenRewards(
            CONTRACT_ADDR,
            private_key=None,
            event_bus=bus,
            source_agent="token-rewards-test",
            node_id="node-1",
            spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/relay",
            did="did:mesh:pqc:node-1",
            wallet_address=NODE_ADDR,
        )
        tr.web3 = object()
        tr.contract = object()
        tr.account = object()
        tr.pending_rewards = Decimal("1.25")
        tr._send_blockchain_reward = lambda node_address, amount: None

        result = tr._settle_rewards(NODE_ADDR, packets=12500)

        events = bus.get_event_history(event_type=EventType.REWARD_RELAY_BLOCKED)
        assert len(events) == 1
        event = events[0]
        assert result["event_id"] == event.event_id
        assert result["ok"] is False
        assert event.data["status"] == "blockchain_submission_failed"
        assert event.data["settlement_recorded"] is False
        assert event.data["submitted_transaction"] is False
        assert event.data["simulated"] is False
        assert event.data["reason"] == "blockchain transaction hash was not returned"
