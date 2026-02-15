"""Unit tests for src/dao/token_bridge.py."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.dao.token_bridge import (
    BridgeConfig,
    BridgeDirection,
    BridgeTransaction,
    EpochRewardScheduler,
    TokenBridge,
)


# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
def mock_mesh_token():
    """Create a mock MeshToken."""
    token = MagicMock()
    token.balance_of.return_value = 0.0
    token.mint.return_value = None
    token.burn.return_value = None
    token.stake.return_value = None
    token.transfer.return_value = None
    token.stakes = {}
    return token


@pytest.fixture
def bridge_config():
    """Create a default BridgeConfig."""
    return BridgeConfig(
        rpc_url="https://sepolia.base.org",
        contract_address="0x1234567890abcdef1234567890abcdef12345678",
        private_key="0xdeadbeef" * 8,
        chain_id=84532,
        poll_interval=1,
        confirmations=2,
        gas_limit=200000,
        max_gas_price_gwei=50.0,
    )


@pytest.fixture
def bridge(mock_mesh_token, bridge_config):
    """Create a TokenBridge with mocked dependencies."""
    return TokenBridge(mock_mesh_token, bridge_config)


# ─── BridgeTransaction / BridgeConfig / BridgeDirection ──────────


class TestBridgeTransaction:
    def test_defaults(self):
        tx = BridgeTransaction(
            tx_id="t1",
            direction=BridgeDirection.TO_CHAIN,
            from_address="0xA",
            to_address="0xB",
            amount=1.0,
            event_type="Transfer",
            timestamp=1000.0,
        )
        assert tx.status == "pending"
        assert tx.block_number is None
        assert tx.tx_hash is None

    def test_all_fields(self):
        tx = BridgeTransaction(
            tx_id="t2",
            direction=BridgeDirection.FROM_CHAIN,
            from_address="0xA",
            to_address="0xB",
            amount=2.5,
            event_type="Staked",
            timestamp=2000.0,
            block_number=42,
            tx_hash="0xabc",
            status="confirmed",
        )
        assert tx.block_number == 42
        assert tx.tx_hash == "0xabc"
        assert tx.status == "confirmed"


class TestBridgeDirection:
    def test_values(self):
        assert BridgeDirection.TO_CHAIN.value == "to_chain"
        assert BridgeDirection.FROM_CHAIN.value == "from_chain"


class TestBridgeConfig:
    def test_defaults(self):
        cfg = BridgeConfig()
        assert cfg.rpc_url == ""
        assert cfg.chain_id == 84532
        assert cfg.poll_interval == 12
        assert cfg.confirmations == 2
        assert cfg.gas_limit == 200000
        assert cfg.max_gas_price_gwei == 50.0


# ─── TokenBridge init ────────────────────────────────────────────


class TestTokenBridgeInit:
    def test_initial_state(self, bridge, mock_mesh_token, bridge_config):
        assert bridge.mesh_token is mock_mesh_token
        assert bridge.config is bridge_config
        assert bridge.web3 is None
        assert bridge.contract is None
        assert bridge.account is None
        assert bridge._running is False
        assert bridge._last_block == 0
        assert bridge._tx_history == []
        assert bridge._address_mapping == {}
        assert bridge._initialized is False

    def test_event_handlers_initialized(self, bridge):
        expected = {"Staked", "Unstaked", "Transfer", "RelayPaid", "EpochRewardsDistributed"}
        assert set(bridge._event_handlers.keys()) == expected
        for handlers in bridge._event_handlers.values():
            assert handlers == []


# ─── _init_web3 ──────────────────────────────────────────────────


class TestInitWeb3:
    def test_already_initialized(self, bridge):
        bridge._initialized = True
        assert bridge._init_web3() is True

    @patch("src.dao.token_bridge.Web3", None)
    def test_import_error(self, bridge):
        """When web3 import fails inside _init_web3."""
        result = bridge._init_web3()
        # It will try to import web3 and either fail or get None
        # Depending on env, just verify it returns bool
        assert isinstance(result, bool)

    def test_web3_not_connected(self, bridge):
        mock_web3_cls = MagicMock()
        mock_web3_instance = MagicMock()
        mock_web3_instance.is_connected.return_value = False
        mock_web3_cls.return_value = mock_web3_instance
        mock_web3_cls.HTTPProvider = MagicMock()

        with patch.dict("sys.modules", {}):
            pass  # just to clear any cached state

        with patch("src.dao.token_bridge.Web3", mock_web3_cls):
            # We need to mock the import inside _init_web3
            mock_account_mod = MagicMock()
            with patch.object(bridge, '_initialized', False):
                # _init_web3 does `from web3 import Web3` and `from eth_account import Account`
                # We mock at the import level
                import builtins
                original_import = builtins.__import__

                def mock_import(name, *args, **kwargs):
                    if name == "web3":
                        mod = MagicMock()
                        mod.Web3 = mock_web3_cls
                        return mod
                    if name == "eth_account":
                        return MagicMock()
                    return original_import(name, *args, **kwargs)

                with patch("builtins.__import__", side_effect=mock_import):
                    result = bridge._init_web3()

        assert result is False

    def test_web3_connected_with_key_and_contract(self, bridge):
        mock_web3_instance = MagicMock()
        mock_web3_instance.is_connected.return_value = True

        mock_web3_cls = MagicMock()
        mock_web3_cls.return_value = mock_web3_instance
        mock_web3_cls.HTTPProvider = MagicMock()
        mock_web3_cls.to_checksum_address.return_value = "0xChecksumAddr"

        mock_account_cls = MagicMock()
        mock_account_obj = MagicMock()
        mock_account_obj.address = "0xMyAddr"
        mock_account_cls.from_key.return_value = mock_account_obj

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "web3":
                mod = MagicMock()
                mod.Web3 = mock_web3_cls
                return mod
            if name == "eth_account":
                mod = MagicMock()
                mod.Account = mock_account_cls
                return mod
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = bridge._init_web3()

        assert result is True
        assert bridge._initialized is True
        assert bridge.web3 is mock_web3_instance
        assert bridge.account is mock_account_obj

    def test_web3_connected_no_private_key(self, bridge):
        bridge.config.private_key = ""
        bridge.config.contract_address = ""

        mock_web3_instance = MagicMock()
        mock_web3_instance.is_connected.return_value = True

        mock_web3_cls = MagicMock()
        mock_web3_cls.return_value = mock_web3_instance
        mock_web3_cls.HTTPProvider = MagicMock()

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "web3":
                mod = MagicMock()
                mod.Web3 = mock_web3_cls
                return mod
            if name == "eth_account":
                return MagicMock()
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = bridge._init_web3()

        assert result is True
        assert bridge.account is None
        assert bridge.contract is None

    def test_web3_exception(self, bridge):
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "web3":
                raise RuntimeError("connection failed")
            if name == "eth_account":
                raise RuntimeError("connection failed")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = bridge._init_web3()

        assert result is False

    def test_import_error_path(self, bridge):
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("web3", "eth_account"):
                raise ImportError("no web3")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = bridge._init_web3()

        assert result is False


# ─── Address Mapping ─────────────────────────────────────────────


class TestAddressMapping:
    @patch("src.dao.token_bridge.WEB3_AVAILABLE", False)
    def test_register_address_no_web3_with_0x(self, bridge):
        bridge.register_address("node1", "0xAbCdEf1234567890")
        assert bridge._address_mapping["node1"] == "0xAbCdEf1234567890"

    @patch("src.dao.token_bridge.WEB3_AVAILABLE", False)
    def test_register_address_no_web3_without_0x(self, bridge):
        bridge.register_address("node1", "AbCdEf1234567890")
        assert bridge._address_mapping["node1"] == "0xAbCdEf1234567890"

    @patch("src.dao.token_bridge.WEB3_AVAILABLE", True)
    @patch("src.dao.token_bridge.Web3")
    def test_register_address_with_web3(self, mock_web3, bridge):
        mock_web3.to_checksum_address.return_value = "0xChecked"
        bridge.register_address("node1", "0xabc")
        assert bridge._address_mapping["node1"] == "0xChecked"

    def test_get_eth_address_found(self, bridge):
        bridge._address_mapping["node1"] = "0xAddr1"
        assert bridge.get_eth_address("node1") == "0xAddr1"

    def test_get_eth_address_not_found(self, bridge):
        assert bridge.get_eth_address("unknown") is None

    @patch("src.dao.token_bridge.WEB3_AVAILABLE", False)
    def test_get_node_id_found(self, bridge):
        bridge._address_mapping["node1"] = "0xAbC"
        # Case-insensitive match
        result = bridge.get_node_id("0xabc")
        assert result == "node1"

    @patch("src.dao.token_bridge.WEB3_AVAILABLE", False)
    def test_get_node_id_not_found(self, bridge):
        bridge._address_mapping["node1"] = "0xAbC"
        assert bridge.get_node_id("0x999") is None

    @patch("src.dao.token_bridge.WEB3_AVAILABLE", False)
    def test_get_node_id_without_0x_prefix(self, bridge):
        bridge._address_mapping["node1"] = "0xAbC"
        result = bridge.get_node_id("AbC")
        assert result == "node1"

    @patch("src.dao.token_bridge.WEB3_AVAILABLE", True)
    @patch("src.dao.token_bridge.Web3")
    def test_get_node_id_with_web3(self, mock_web3, bridge):
        mock_web3.to_checksum_address.return_value = "0xABC"
        bridge._address_mapping["node1"] = "0xABC"
        result = bridge.get_node_id("0xabc")
        assert result == "node1"


# ─── Event Handling ──────────────────────────────────────────────


class TestOnEvent:
    def test_register_known_event(self, bridge):
        handler = MagicMock()
        bridge.on_event("Staked", handler)
        assert handler in bridge._event_handlers["Staked"]

    def test_register_unknown_event_ignored(self, bridge):
        handler = MagicMock()
        bridge.on_event("UnknownEvent", handler)
        assert "UnknownEvent" not in bridge._event_handlers

    def test_register_multiple_handlers(self, bridge):
        h1, h2 = MagicMock(), MagicMock()
        bridge.on_event("Transfer", h1)
        bridge.on_event("Transfer", h2)
        assert len(bridge._event_handlers["Transfer"]) == 2


# ─── start / stop ────────────────────────────────────────────────


class TestStartStop:
    @pytest.mark.asyncio
    async def test_start_fails_without_web3(self, bridge):
        bridge._init_web3 = MagicMock(return_value=False)
        await bridge.start()
        assert bridge._running is False

    @pytest.mark.asyncio
    async def test_start_runs_and_stops(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        mock_web3 = MagicMock()
        mock_web3.eth.block_number = 100
        bridge.web3 = mock_web3

        call_count = 0

        async def fake_poll():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                bridge.stop()

        bridge._poll_events = fake_poll
        bridge.config.poll_interval = 0  # no delay

        await bridge.start()
        assert bridge._running is False
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_start_handles_poll_exception(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        mock_web3 = MagicMock()
        mock_web3.eth.block_number = 100
        bridge.web3 = mock_web3

        call_count = 0

        async def failing_poll():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("poll error")
            bridge.stop()

        bridge._poll_events = failing_poll
        bridge.config.poll_interval = 0

        await bridge.start()
        assert call_count >= 2  # Continued after error

    def test_stop(self, bridge):
        bridge._running = True
        bridge.stop()
        assert bridge._running is False


# ─── _poll_events ────────────────────────────────────────────────


class TestPollEvents:
    @pytest.mark.asyncio
    async def test_no_new_blocks(self, bridge):
        bridge.web3 = MagicMock()
        bridge.web3.eth.block_number = 10
        bridge._last_block = 10
        bridge._process_event_type = AsyncMock()

        await bridge._poll_events()
        bridge._process_event_type.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_blocks_processes_events(self, bridge):
        bridge.web3 = MagicMock()
        bridge.web3.eth.block_number = 15
        bridge._last_block = 10
        bridge._process_event_type = AsyncMock()

        await bridge._poll_events()

        assert bridge._process_event_type.call_count == 4  # 4 event types
        assert bridge._last_block == 15

        # Verify event types processed
        called_types = [c.args[0] for c in bridge._process_event_type.call_args_list]
        assert called_types == ["Staked", "Unstaked", "Transfer", "RelayPaid"]


# ─── _process_event_type ─────────────────────────────────────────


class TestProcessEventType:
    @pytest.mark.asyncio
    async def test_no_contract(self, bridge):
        bridge.contract = None
        bridge._handle_event = AsyncMock()
        await bridge._process_event_type("Staked", 1, 10)
        bridge._handle_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_events(self, bridge):
        mock_event = MagicMock()
        mock_filter = MagicMock()
        mock_filter.get_logs.return_value = [mock_event]

        bridge.contract = MagicMock()
        bridge.contract.events.Staked = mock_filter
        bridge._handle_event = AsyncMock()

        await bridge._process_event_type("Staked", 1, 10)

        mock_filter.get_logs.assert_called_once_with(fromBlock=1, toBlock=10)
        bridge._handle_event.assert_called_once_with("Staked", mock_event)

    @pytest.mark.asyncio
    async def test_handles_exception(self, bridge):
        bridge.contract = MagicMock()
        bridge.contract.events.Transfer = MagicMock(
            side_effect=RuntimeError("RPC error")
        )
        # Should not raise
        await bridge._process_event_type("Transfer", 1, 10)


# ─── _handle_event ───────────────────────────────────────────────


class TestHandleEvent:
    def _make_event(self, args_dict, block=100, tx_hash_bytes=b"\xab" * 32):
        class _EventArgs:
            def __init__(self, data):
                self._data = data

            def __getattr__(self, key):
                if key in self._data:
                    return self._data[key]
                raise AttributeError(key)

            def get(self, key, default=None):
                return self._data.get(key, default)

            def __getitem__(self, key):
                return self._data[key]

            def __iter__(self):
                return iter(self._data.items())

            def keys(self):
                return self._data.keys()

            def items(self):
                return self._data.items()

        event = MagicMock()
        # Allow both attribute and dict-style access.
        event.args = _EventArgs(args_dict)
        event.blockNumber = block
        event.transactionHash = MagicMock()
        event.transactionHash.hex.return_value = (
            tx_hash_bytes.hex()
            if isinstance(tx_hash_bytes, bytes)
            else tx_hash_bytes
        )
        return event

    @pytest.mark.asyncio
    async def test_staked_event(self, bridge):
        event = self._make_event({"user": "0xUser1", "amount": 1000000000000000000})
        bridge._sync_stake = AsyncMock()

        await bridge._handle_event("Staked", event)

        bridge._sync_stake.assert_called_once_with("0xUser1", 1000000000000000000, is_stake=True)
        assert len(bridge._tx_history) == 1
        assert bridge._tx_history[0].direction == BridgeDirection.FROM_CHAIN
        assert bridge._tx_history[0].status == "confirmed"

    @pytest.mark.asyncio
    async def test_unstaked_event(self, bridge):
        event = self._make_event({"user": "0xUser1", "amount": 500000000000000000})
        bridge._sync_stake = AsyncMock()

        await bridge._handle_event("Unstaked", event)

        bridge._sync_stake.assert_called_once_with("0xUser1", 500000000000000000, is_stake=False)

    @pytest.mark.asyncio
    async def test_transfer_event(self, bridge):
        event = self._make_event({"from": "0xA", "to": "0xB", "value": 2000000000000000000})
        bridge._sync_transfer = AsyncMock()

        await bridge._handle_event("Transfer", event)

        bridge._sync_transfer.assert_called_once_with("0xA", "0xB", 2000000000000000000)

    @pytest.mark.asyncio
    async def test_relay_paid_event(self, bridge):
        event = self._make_event({"payer": "0xP", "relayer": "0xR", "amount": 100000000000000000})
        bridge._sync_relay_payment = AsyncMock()

        await bridge._handle_event("RelayPaid", event)

        bridge._sync_relay_payment.assert_called_once_with("0xP", "0xR", 100000000000000000)

    @pytest.mark.asyncio
    async def test_sync_handler_called(self, bridge):
        handler = MagicMock()
        bridge.on_event("Staked", handler)
        bridge._sync_stake = AsyncMock()

        event = self._make_event({"user": "0xU", "amount": 0})
        await bridge._handle_event("Staked", event)

        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_async_handler_called(self, bridge):
        handler = AsyncMock()
        bridge.on_event("Staked", handler)
        bridge._sync_stake = AsyncMock()

        event = self._make_event({"user": "0xU", "amount": 0})
        await bridge._handle_event("Staked", event)

        handler.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_handler_exception_caught(self, bridge):
        handler = MagicMock(side_effect=RuntimeError("handler err"))
        bridge.on_event("Staked", handler)
        bridge._sync_stake = AsyncMock()

        event = self._make_event({"user": "0xU", "amount": 0})
        # Should not raise
        await bridge._handle_event("Staked", event)

    @pytest.mark.asyncio
    async def test_unknown_event_type_no_sync(self, bridge):
        """Event types not in the if/elif chain just get recorded."""
        event = self._make_event({"epoch": 5, "totalRewards": 100, "recipientCount": 3})
        # No sync method called, but tx recorded
        await bridge._handle_event("EpochRewardsDistributed", event)
        assert len(bridge._tx_history) == 1


# ─── _sync_stake ─────────────────────────────────────────────────


class TestSyncStake:
    @pytest.mark.asyncio
    async def test_unknown_address(self, bridge):
        bridge.get_node_id = MagicMock(return_value=None)
        await bridge._sync_stake("0xUnknown", 1000000000000000000, is_stake=True)
        bridge.mesh_token.mint.assert_not_called()

    @pytest.mark.asyncio
    async def test_stake_mint_and_stake(self, bridge, mock_mesh_token):
        bridge._address_mapping["node1"] = "0xAddr"
        bridge.get_node_id = MagicMock(return_value="node1")
        mock_mesh_token.balance_of.return_value = 0.0

        await bridge._sync_stake("0xAddr", 5_000_000_000_000_000_000, is_stake=True)

        mock_mesh_token.mint.assert_called_once_with("node1", 5.0, "bridge_sync")
        mock_mesh_token.stake.assert_called_once_with("node1", 5.0)

    @pytest.mark.asyncio
    async def test_stake_sufficient_balance(self, bridge, mock_mesh_token):
        bridge.get_node_id = MagicMock(return_value="node1")
        mock_mesh_token.balance_of.return_value = 10.0

        await bridge._sync_stake("0xAddr", 5_000_000_000_000_000_000, is_stake=True)

        mock_mesh_token.mint.assert_not_called()
        mock_mesh_token.stake.assert_called_once_with("node1", 5.0)

    @pytest.mark.asyncio
    async def test_stake_partial_mint(self, bridge, mock_mesh_token):
        bridge.get_node_id = MagicMock(return_value="node1")
        mock_mesh_token.balance_of.return_value = 3.0

        await bridge._sync_stake("0xAddr", 5_000_000_000_000_000_000, is_stake=True)

        mock_mesh_token.mint.assert_called_once_with("node1", 2.0, "bridge_sync")

    @pytest.mark.asyncio
    async def test_unstake(self, bridge, mock_mesh_token):
        bridge.get_node_id = MagicMock(return_value="node1")
        mock_mesh_token.stakes = {"node1": MagicMock()}

        await bridge._sync_stake("0xAddr", 1_000_000_000_000_000_000, is_stake=False)

        assert "node1" not in mock_mesh_token.stakes

    @pytest.mark.asyncio
    async def test_unstake_no_existing_stake(self, bridge, mock_mesh_token):
        bridge.get_node_id = MagicMock(return_value="node1")
        mock_mesh_token.stakes = {}

        # Should not raise
        await bridge._sync_stake("0xAddr", 1_000_000_000_000_000_000, is_stake=False)


# ─── _sync_transfer ──────────────────────────────────────────────


class TestSyncTransfer:
    @pytest.mark.asyncio
    async def test_both_known(self, bridge, mock_mesh_token):
        bridge._address_mapping = {"nodeA": "0xA", "nodeB": "0xB"}

        await bridge._sync_transfer("0xA", "0xB", 3_000_000_000_000_000_000)

        mock_mesh_token.transfer.assert_called_once_with("nodeA", "nodeB", 3.0)

    @pytest.mark.asyncio
    async def test_only_to_known(self, bridge, mock_mesh_token):
        bridge._address_mapping = {"nodeB": "0xB"}

        await bridge._sync_transfer("0xUnknown", "0xB", 2_000_000_000_000_000_000)

        mock_mesh_token.mint.assert_called_once_with("nodeB", 2.0, "bridge_deposit")
        mock_mesh_token.transfer.assert_not_called()

    @pytest.mark.asyncio
    async def test_neither_known(self, bridge, mock_mesh_token):
        bridge._address_mapping = {}

        await bridge._sync_transfer("0xA", "0xB", 1_000_000_000_000_000_000)

        mock_mesh_token.transfer.assert_not_called()
        mock_mesh_token.mint.assert_not_called()

    @pytest.mark.asyncio
    async def test_only_from_known(self, bridge, mock_mesh_token):
        bridge._address_mapping = {"nodeA": "0xA"}

        await bridge._sync_transfer("0xA", "0xUnknown", 1_000_000_000_000_000_000)

        mock_mesh_token.transfer.assert_not_called()
        mock_mesh_token.mint.assert_not_called()


# ─── _sync_relay_payment ─────────────────────────────────────────


class TestSyncRelayPayment:
    @pytest.mark.asyncio
    async def test_both_known(self, bridge):
        bridge._address_mapping = {"payer": "0xP", "relayer": "0xR"}
        # Just logs, should not raise
        await bridge._sync_relay_payment("0xP", "0xR", 1_000_000_000_000_000_000)

    @pytest.mark.asyncio
    async def test_unknown_addresses(self, bridge):
        bridge._address_mapping = {}
        await bridge._sync_relay_payment("0xP", "0xR", 1_000_000_000_000_000_000)
        # No error expected


# ─── push_rewards_to_chain ───────────────────────────────────────


class TestPushRewardsToChain:
    @pytest.mark.asyncio
    async def test_web3_not_initialized(self, bridge):
        bridge._init_web3 = MagicMock(return_value=False)
        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_no_contract(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = None
        bridge.account = MagicMock()
        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_no_account(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = None
        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_cannot_distribute(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = False

        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_no_valid_recipients(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
        bridge._address_mapping = {}  # No registered addresses

        result = await bridge.push_rewards_to_chain({"unknown_node": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_push(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"

        mock_web3 = MagicMock()
        bridge.web3 = mock_web3

        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
        bridge._address_mapping = {"node1": "0xN1", "node2": "0xN2"}

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xabcdef1234567890"
        mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash

        mock_receipt = MagicMock()
        mock_receipt.status = 1
        mock_receipt.blockNumber = 42
        mock_web3.eth.wait_for_transaction_receipt.return_value = mock_receipt

        result = await bridge.push_rewards_to_chain(
            {"node1": 100.0, "node2": 50.0},
            uptimes={"node1": 95, "node2": 80},
        )

        assert result == "0xabcdef1234567890"
        assert len(bridge._tx_history) == 1
        assert bridge._tx_history[0].direction == BridgeDirection.TO_CHAIN
        assert bridge._tx_history[0].amount == 150.0

    @pytest.mark.asyncio
    async def test_failed_receipt(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()

        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
        bridge._address_mapping = {"node1": "0xN1"}

        mock_receipt = MagicMock()
        mock_receipt.status = 0  # Failed
        bridge.web3.eth.wait_for_transaction_receipt.return_value = mock_receipt

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xfailed"
        bridge.web3.eth.send_raw_transaction.return_value = mock_tx_hash

        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_in_push(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()

        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
        bridge._address_mapping = {"node1": "0xN1"}

        bridge.contract.functions.distributeEpochRewards.return_value.build_transaction.side_effect = RuntimeError("gas error")

        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result is None

    @pytest.mark.asyncio
    async def test_push_with_no_uptimes(self, bridge):
        """When uptimes parameter is None, defaults to 100."""
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()

        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
        bridge._address_mapping = {"node1": "0xN1"}

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xaaa"
        bridge.web3.eth.send_raw_transaction.return_value = mock_tx_hash

        mock_receipt = MagicMock()
        mock_receipt.status = 1
        mock_receipt.blockNumber = 50
        bridge.web3.eth.wait_for_transaction_receipt.return_value = mock_receipt

        result = await bridge.push_rewards_to_chain({"node1": 100.0})
        assert result == "0xaaa"

        # Verify uptime default was 100
        call_args = bridge.contract.functions.distributeEpochRewards.call_args
        assert call_args[0][1] == [100]  # uptime_values


# ─── authorize_relayer ───────────────────────────────────────────


class TestAuthorizeRelayer:
    @pytest.mark.asyncio
    async def test_web3_not_initialized(self, bridge):
        bridge._init_web3 = MagicMock(return_value=False)
        result = await bridge.authorize_relayer("node1")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_eth_address(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge._address_mapping = {}
        result = await bridge.authorize_relayer("unknown_node")
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_authorize(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xauth123"
        bridge.web3.eth.send_raw_transaction.return_value = mock_tx_hash

        mock_receipt = MagicMock()
        mock_receipt.status = 1
        bridge.web3.eth.wait_for_transaction_receipt.return_value = mock_receipt

        result = await bridge.authorize_relayer("node1", authorized=True)
        assert result == "0xauth123"

    @pytest.mark.asyncio
    async def test_revoke_relayer(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        mock_tx_hash = MagicMock()
        mock_tx_hash.hex.return_value = "0xrevoke"
        bridge.web3.eth.send_raw_transaction.return_value = mock_tx_hash

        mock_receipt = MagicMock()
        mock_receipt.status = 1
        bridge.web3.eth.wait_for_transaction_receipt.return_value = mock_receipt

        result = await bridge.authorize_relayer("node1", authorized=False)
        assert result == "0xrevoke"

        # Verify it passed authorized=False to contract
        call_args = bridge.contract.functions.setRelayerAuthorized.call_args
        assert call_args[0] == ("0xN1", False)

    @pytest.mark.asyncio
    async def test_failed_receipt(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        mock_tx_hash = MagicMock()
        bridge.web3.eth.send_raw_transaction.return_value = mock_tx_hash

        mock_receipt = MagicMock()
        mock_receipt.status = 0
        bridge.web3.eth.wait_for_transaction_receipt.return_value = mock_receipt

        result = await bridge.authorize_relayer("node1")
        assert result is None

    @pytest.mark.asyncio
    async def test_exception(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.account = MagicMock()
        bridge.account.address = "0xBridgeAddr"
        bridge.web3 = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        bridge.contract.functions.setRelayerAuthorized.return_value.build_transaction.side_effect = RuntimeError("fail")

        result = await bridge.authorize_relayer("node1")
        assert result is None


# ─── sync_balance ────────────────────────────────────────────────


class TestSyncBalance:
    @pytest.mark.asyncio
    async def test_web3_not_initialized(self, bridge):
        bridge._init_web3 = MagicMock(return_value=False)
        result = await bridge.sync_balance("node1")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_eth_address(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge._address_mapping = {}
        result = await bridge.sync_balance("unknown")
        assert result is None

    @pytest.mark.asyncio
    async def test_sync_balance_higher_on_chain(self, bridge, mock_mesh_token):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        # On-chain: 10 tokens, local: 5 tokens
        bridge.contract.functions.balanceOf.return_value.call.return_value = 10_000_000_000_000_000_000
        mock_mesh_token.balance_of.return_value = 5.0

        result = await bridge.sync_balance("node1")
        assert result == 10.0
        mock_mesh_token.mint.assert_called_once_with("node1", 5.0, "chain_sync")

    @pytest.mark.asyncio
    async def test_sync_balance_lower_on_chain(self, bridge, mock_mesh_token):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        # On-chain: 3 tokens, local: 10 tokens
        bridge.contract.functions.balanceOf.return_value.call.return_value = 3_000_000_000_000_000_000
        mock_mesh_token.balance_of.return_value = 10.0

        result = await bridge.sync_balance("node1")
        assert result == 3.0
        mock_mesh_token.burn.assert_called_once_with("node1", 7.0, "chain_sync")

    @pytest.mark.asyncio
    async def test_sync_balance_equal(self, bridge, mock_mesh_token):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}

        bridge.contract.functions.balanceOf.return_value.call.return_value = 5_000_000_000_000_000_000
        mock_mesh_token.balance_of.return_value = 5.0

        result = await bridge.sync_balance("node1")
        assert result == 5.0
        mock_mesh_token.mint.assert_not_called()
        mock_mesh_token.burn.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_balance_exception(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge._address_mapping = {"node1": "0xN1"}
        bridge.contract.functions.balanceOf.return_value.call.side_effect = RuntimeError("RPC error")

        result = await bridge.sync_balance("node1")
        assert result is None


# ─── sync_all_balances ───────────────────────────────────────────


class TestSyncAllBalances:
    @pytest.mark.asyncio
    async def test_syncs_all(self, bridge):
        bridge._address_mapping = {"n1": "0x1", "n2": "0x2", "n3": "0x3"}
        bridge.sync_balance = AsyncMock(return_value=1.0)

        await bridge.sync_all_balances()
        assert bridge.sync_balance.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_mapping(self, bridge):
        bridge._address_mapping = {}
        bridge.sync_balance = AsyncMock()

        await bridge.sync_all_balances()
        bridge.sync_balance.assert_not_called()


# ─── get_chain_stats ─────────────────────────────────────────────


class TestGetChainStats:
    def test_web3_not_initialized(self, bridge):
        bridge._init_web3 = MagicMock(return_value=False)
        assert bridge.get_chain_stats() == {}

    def test_no_contract(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = None
        assert bridge.get_chain_stats() == {}

    def test_successful_stats(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()

        bridge.contract.functions.totalStaked.return_value.call.return_value = 1000_000_000_000_000_000_000
        bridge.contract.functions.currentEpoch.return_value.call.return_value = 5
        bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True

        stats = bridge.get_chain_stats()
        assert stats["total_staked"] == 1000.0
        assert stats["current_epoch"] == 5
        assert stats["can_distribute"] is True
        assert stats["chain_id"] == 84532

    def test_exception(self, bridge):
        bridge._init_web3 = MagicMock(return_value=True)
        bridge.contract = MagicMock()
        bridge.contract.functions.totalStaked.return_value.call.side_effect = RuntimeError("err")

        assert bridge.get_chain_stats() == {}


# ─── Transaction History ─────────────────────────────────────────


class TestTransactionHistory:
    def test_get_tx_history_empty(self, bridge):
        assert bridge.get_tx_history() == []

    def test_get_tx_history_with_limit(self, bridge):
        for i in range(10):
            bridge._tx_history.append(
                BridgeTransaction(
                    tx_id=f"t{i}",
                    direction=BridgeDirection.TO_CHAIN,
                    from_address="a",
                    to_address="b",
                    amount=float(i),
                    event_type="Transfer",
                    timestamp=float(i),
                )
            )
        result = bridge.get_tx_history(limit=3)
        assert len(result) == 3
        assert result[0].tx_id == "t7"
        assert result[2].tx_id == "t9"

    def test_get_tx_history_default_limit(self, bridge):
        for i in range(5):
            bridge._tx_history.append(
                BridgeTransaction(
                    tx_id=f"t{i}",
                    direction=BridgeDirection.TO_CHAIN,
                    from_address="a",
                    to_address="b",
                    amount=0.0,
                    event_type="Transfer",
                    timestamp=0.0,
                )
            )
        assert len(bridge.get_tx_history()) == 5

    def test_get_pending_txs(self, bridge):
        bridge._tx_history = [
            BridgeTransaction(
                tx_id="t1", direction=BridgeDirection.TO_CHAIN, from_address="a",
                to_address="b", amount=1.0, event_type="Transfer", timestamp=0.0,
                status="pending",
            ),
            BridgeTransaction(
                tx_id="t2", direction=BridgeDirection.FROM_CHAIN, from_address="a",
                to_address="b", amount=2.0, event_type="Staked", timestamp=0.0,
                status="confirmed",
            ),
            BridgeTransaction(
                tx_id="t3", direction=BridgeDirection.TO_CHAIN, from_address="a",
                to_address="b", amount=3.0, event_type="Transfer", timestamp=0.0,
                status="pending",
            ),
        ]
        pending = bridge.get_pending_txs()
        assert len(pending) == 2
        assert all(tx.status == "pending" for tx in pending)

    def test_get_pending_txs_none(self, bridge):
        bridge._tx_history = [
            BridgeTransaction(
                tx_id="t1", direction=BridgeDirection.TO_CHAIN, from_address="a",
                to_address="b", amount=1.0, event_type="Transfer", timestamp=0.0,
                status="confirmed",
            ),
        ]
        assert bridge.get_pending_txs() == []


# ─── EpochRewardScheduler ───────────────────────────────────────


class TestEpochRewardScheduler:
    @pytest.fixture
    def mock_bridge(self):
        b = MagicMock(spec=TokenBridge)
        b.get_chain_stats.return_value = {}
        b.push_rewards_to_chain = AsyncMock()
        return b

    @pytest.fixture
    def uptime_provider(self):
        return MagicMock(return_value={"node1": 0.95, "node2": 0.80})

    @pytest.fixture
    def scheduler(self, mock_bridge, uptime_provider):
        return EpochRewardScheduler(mock_bridge, uptime_provider)

    def test_init(self, scheduler, mock_bridge, uptime_provider):
        assert scheduler.bridge is mock_bridge
        assert scheduler.uptime_provider is uptime_provider
        assert scheduler._running is False

    def test_stop(self, scheduler):
        scheduler._running = True
        scheduler.stop()
        assert scheduler._running is False

    @pytest.mark.asyncio
    async def test_start_checks_stats(self, scheduler, mock_bridge):
        """Start runs loop, stops after one iteration."""
        call_count = 0

        def fake_stats():
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scheduler.stop()
            return {"can_distribute": False}

        mock_bridge.get_chain_stats = fake_stats

        # Patch sleep to return immediately
        with patch("src.dao.token_bridge.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.start()

        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_start_distributes_when_ready(self, scheduler, mock_bridge, uptime_provider):
        call_count = 0

        def fake_stats():
            nonlocal call_count
            call_count += 1
            scheduler.stop()
            return {"can_distribute": True}

        mock_bridge.get_chain_stats = fake_stats

        with patch("src.dao.token_bridge.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.start()

        mock_bridge.push_rewards_to_chain.assert_called_once()
        call_args = mock_bridge.push_rewards_to_chain.call_args
        assert call_args.kwargs["uptimes"] == {"node1": 95, "node2": 80}

    @pytest.mark.asyncio
    async def test_start_handles_exception(self, scheduler, mock_bridge):
        call_count = 0

        def failing_stats():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("stats error")
            scheduler.stop()
            return {}

        mock_bridge.get_chain_stats = failing_stats

        with patch("src.dao.token_bridge.asyncio.sleep", new_callable=AsyncMock):
            await scheduler.start()

        assert call_count >= 2  # continued after error

    @pytest.mark.asyncio
    async def test_distribute_epoch_no_uptimes(self, scheduler, mock_bridge):
        scheduler.uptime_provider = MagicMock(return_value={})
        await scheduler._distribute_epoch()
        mock_bridge.push_rewards_to_chain.assert_not_called()

    @pytest.mark.asyncio
    async def test_distribute_epoch_success(self, scheduler, mock_bridge, uptime_provider):
        mock_bridge.push_rewards_to_chain.return_value = "0xhash"

        await scheduler._distribute_epoch()

        mock_bridge.push_rewards_to_chain.assert_called_once_with(
            rewards={},
            uptimes={"node1": 95, "node2": 80},
        )

    @pytest.mark.asyncio
    async def test_distribute_epoch_failure(self, scheduler, mock_bridge, uptime_provider):
        mock_bridge.push_rewards_to_chain.return_value = None

        # Should not raise
        await scheduler._distribute_epoch()
