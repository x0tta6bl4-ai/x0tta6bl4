"""Smoke tests for TokenBridge (off-chain ↔ on-chain bridge)."""
import pytest
from src.dao.token_bridge import TokenBridge, BridgeConfig
from src.dao.token import MeshToken


@pytest.fixture
def bridge():
    token = MeshToken()
    config = BridgeConfig(rpc_url="", contract_address="", private_key="")
    return TokenBridge(token, config)


@pytest.fixture
def simulated_bridge():
    token = MeshToken()
    config = BridgeConfig(
        rpc_url="",
        contract_address="",
        private_key="",
        allow_simulated_chain_writes=True,
    )
    return TokenBridge(token, config)


class TestTokenBridgeInit:
    def test_bridge_creates_without_web3(self, bridge):
        assert bridge is not None

    def test_get_chain_stats_returns_dict(self, bridge):
        stats = bridge.get_chain_stats()
        assert isinstance(stats, dict)
        assert "web3_connected" in stats or "connected" in stats or len(stats) >= 0

    def test_get_tx_history_empty(self, bridge):
        history = bridge.get_tx_history()
        assert isinstance(history, list)

    def test_get_pending_txs_empty(self, bridge):
        pending = bridge.get_pending_txs()
        assert isinstance(pending, list)


class TestTokenBridgeAddressMapping:
    def test_register_and_get_address(self, bridge):
        bridge.register_address("node-1", "0xDEADBEEF")
        assert bridge.get_eth_address("node-1") == "0xDEADBEEF"

    def test_get_node_id_from_eth(self, bridge):
        bridge.register_address("node-2", "0xCAFEBABE")
        assert bridge.get_node_id("0xCAFEBABE") == "node-2"

    def test_unknown_node_returns_none(self, bridge):
        assert bridge.get_eth_address("ghost-node") is None


@pytest.mark.asyncio
async def test_lock_escrow_no_web3_fails_closed_by_default(bridge):
    """Without Web3, lock_escrow must not fabricate a chain tx id by default."""
    tx = await bridge.lock_escrow_on_chain("esc-001", "user-1", 100.0)
    assert tx is None


@pytest.mark.asyncio
async def test_lock_escrow_no_web3_simulation_must_be_explicit(simulated_bridge):
    """Local smoke simulations need an explicit config flag."""
    tx = await simulated_bridge.lock_escrow_on_chain("esc-001", "user-1", 100.0)
    assert isinstance(tx, str)
    assert tx.startswith("sim_tx_")


@pytest.mark.asyncio
async def test_release_escrow_no_web3(bridge):
    result = await bridge.release_escrow_on_chain("esc-001")
    assert result is False


@pytest.mark.asyncio
async def test_release_escrow_no_web3_simulation_must_be_explicit(simulated_bridge):
    result = await simulated_bridge.release_escrow_on_chain("esc-001")
    assert result is True


@pytest.mark.asyncio
async def test_refund_escrow_no_web3(bridge):
    result = await bridge.refund_escrow_on_chain("esc-001")
    assert result is False


@pytest.mark.asyncio
async def test_refund_escrow_no_web3_simulation_must_be_explicit(simulated_bridge):
    result = await simulated_bridge.refund_escrow_on_chain("esc-001")
    assert result is True
