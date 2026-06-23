from unittest.mock import MagicMock

import pytest

from src.coordination.events import EventBus, EventType
from src.dao.token_bridge import BridgeConfig, TokenBridge
from src.integration.spine import AsyncSafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


def _allow_policy(operation="push_rewards_to_chain"):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-token-bridge-{operation}",
            name=f"Allow TokenBridge {operation}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/token-bridge",
            allowed_resources=[f"dao:token_bridge:{operation}"],
            priority=1000,
        )
    )
    return policy


def _bridge(tmp_path, **kwargs):
    mesh_token = MagicMock()
    mesh_token.balance_of.return_value = 0.0
    return TokenBridge(
        mesh_token,
        BridgeConfig(
            rpc_url="https://sepolia.base.org",
            contract_address="0x1234567890abcdef1234567890abcdef12345678",
            private_key="0xdeadbeef",
        ),
        node_id="bridge-node-1",
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/token-bridge",
        did="did:mesh:token:bridge",
        wallet_address="0xbridge",
        **kwargs,
    )


def _configure_reward_success(bridge):
    bridge._init_web3 = MagicMock(return_value=True)
    bridge.contract = MagicMock()
    bridge.account = MagicMock()
    bridge.account.address = "0xBridgeAddr"
    bridge.web3 = MagicMock()
    bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True
    bridge._address_mapping = {"node1": "0xN1"}

    tx_hash = MagicMock()
    tx_hash.hex.return_value = "0xreward123"
    bridge.web3.eth.send_raw_transaction.return_value = tx_hash

    receipt = MagicMock()
    receipt.status = 1
    receipt.blockNumber = 42
    bridge.web3.eth.wait_for_transaction_receipt.return_value = receipt


@pytest.mark.asyncio
async def test_token_bridge_reward_write_publishes_identity_policy_actuator_and_reward_events(tmp_path):
    bridge = _bridge(
        tmp_path,
        policy_engine=_allow_policy(),
        require_policy=True,
    )
    _configure_reward_success(bridge)

    result = await bridge.push_rewards_to_chain({"node1": 100.0}, uptimes={"node1": 95})

    assert result == "0xreward123"
    events = bridge.event_bus.get_event_history(source_agent="token-bridge", limit=10)
    stages = [event.data.get("stage") for event in events if "stage" in event.data]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "bridge-node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/token-bridge"
    assert payload["did"] == "did:mesh:token:bridge"
    assert payload["wallet_address"] == "0xbridge"
    assert payload["resource"] == "dao:token_bridge:push_rewards_to_chain"
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-token-bridge-push_rewards_to_chain"]
    assert payload["safe_actuator"] is True
    assert payload["submitted_transaction"] is True
    assert payload["transaction_hash"] == "0xreward123"
    assert payload["claim_boundary"]

    reward_events = bridge.event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_RECORDED,
        source_agent="token-bridge",
    )
    assert reward_events[-1].data["settlement_recorded"] is True
    assert reward_events[-1].data["transaction_hash"] == "0xreward123"
    assert reward_events[-1].data["identity"]["spiffe_id"] == payload["spiffe_id"]


@pytest.mark.asyncio
async def test_token_bridge_policy_denial_blocks_before_web3_and_reward_settlement(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    bridge = _bridge(tmp_path, policy_engine=policy, require_policy=True)
    bridge._init_web3 = MagicMock(return_value=True)

    result = await bridge.push_rewards_to_chain({"node1": 100.0})

    assert result is None
    bridge._init_web3.assert_not_called()
    blocked = bridge.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="token-bridge",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False

    reward_blocked = bridge.event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_BLOCKED,
        source_agent="token-bridge",
    )
    assert reward_blocked[-1].data["settlement_recorded"] is False


@pytest.mark.asyncio
async def test_token_bridge_simulated_actuator_blocks_reward_submission(tmp_path):
    bridge = _bridge(
        tmp_path,
        safe_actuator=AsyncSafeActuator(
            lambda _operation, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )
    bridge._init_web3 = MagicMock(return_value=True)

    result = await bridge.push_rewards_to_chain({"node1": 100.0})

    assert result is None
    bridge._init_web3.assert_not_called()
    failed = bridge.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="token-bridge",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["submitted_transaction"] is False

    reward_blocked = bridge.event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_BLOCKED,
        source_agent="token-bridge",
    )
    assert reward_blocked[-1].data["simulated"] is True
    assert reward_blocked[-1].data["settlement_recorded"] is False


@pytest.mark.asyncio
async def test_token_bridge_explicit_escrow_simulation_is_evented_as_blocked(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.config.allow_simulated_chain_writes = True
    bridge._init_web3 = MagicMock(return_value=False)

    result = await bridge.lock_escrow_on_chain("escrow-1", "node1", 10.0)

    assert isinstance(result, str)
    assert result.startswith("sim_tx_")
    failed = bridge.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="token-bridge",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["transaction_hash"] is None
    assert failed[-1].data["simulated"] is True

    held = bridge.event_bus.get_event_history(
        event_type=EventType.MARKETPLACE_ESCROW_HELD,
        source_agent="token-bridge",
    )
    assert held == []
    blocked = bridge.event_bus.get_event_history(
        event_type=EventType.MARKETPLACE_ESCROW_BLOCKED,
        source_agent="token-bridge",
    )
    assert blocked[-1].data["escrow_id"] == "escrow-1"
    assert blocked[-1].data["status"] == "blocked"
    assert blocked[-1].data["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/token-bridge"
