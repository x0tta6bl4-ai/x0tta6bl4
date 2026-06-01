import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.coordination.events import EventBus, EventType
from src.dao.token_bridge import BridgeConfig, EpochRewardScheduler, TokenBridge
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


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()[:16]


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


class _ChainEventArgs:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, key):
        if key in self._data:
            return self._data[key]
        raise AttributeError(key)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data.items())


def _chain_event(args, *, block=123, tx_hash="0xchain123"):
    event = MagicMock()
    event.args = _ChainEventArgs(args)
    event.blockNumber = block
    event.transactionHash = MagicMock()
    event.transactionHash.hex.return_value = tx_hash
    return event


def _metadata_dict(result):
    return result.evidence_metadata.to_dict()


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
    assert payload["service_name"] == "token-bridge"
    assert payload["layer"] == "dao_chain_bridge"
    assert payload["source_quality"] == "safe_actuator_submitted_transaction"
    assert payload["duration_ms"] >= 0
    assert payload["identity_hashes"]["node_id_hash"] == _hash("bridge-node-1")
    assert payload["identity_hashes"]["spiffe_id_hash"] == _hash(
        "spiffe://x0tta6bl4.mesh/workload/token-bridge"
    )
    assert payload["identity_fields_present"] == {
        "node_id": True,
        "spiffe_id": True,
        "did": True,
        "wallet_address": True,
    }
    assert payload["context"]["rewards"] == {
        "entries_total": 1,
        "entries_limit": 16,
        "entries_truncated": False,
        "key_hashes": [_hash("node1")],
        "numeric_values_total": 100.0,
        "numeric_values_count": 1,
        "raw_keys_redacted": True,
        "raw_values_redacted": True,
    }
    assert payload["context"]["uptimes"] == {
        "entries_total": 1,
        "entries_limit": 16,
        "entries_truncated": False,
        "key_hashes": [_hash("node1")],
        "numeric_values_total": 95.0,
        "numeric_values_count": 1,
        "raw_keys_redacted": True,
        "raw_values_redacted": True,
    }
    assert payload["context_values_redacted"] is True
    assert payload["context_payloads_redacted"] is True
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-token-bridge-push_rewards_to_chain"]
    assert payload["safe_actuator"] is True
    assert payload["safe_actuator_used"] is True
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.token_bridge.safe_actuator_claim_gate.v1"
    assert claim_gate["local_chain_write_attempt_succeeded"] is True
    assert claim_gate["pending_chain_submission_claim_allowed"] is True
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["live_token_settlement_finality_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["revenue_recognition_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_result_values_redacted"] is True
    assert payload["submitted_transaction"] is True
    assert payload["transaction_hash"] == "0xreward123"
    assert payload["transaction_hash_hash"]
    assert payload["result_summary"]["success"] is True
    assert payload["result_summary"]["simulated"] is False
    assert payload["result_summary"]["submitted_transaction"] is True
    assert payload["result_summary"]["transaction_hash_present"] is True
    assert (
        payload["result_summary"]["transaction_hash_hash"]
        == payload["transaction_hash_hash"]
    )
    assert payload["result_summary"]["raw_result_redacted"] is True
    assert payload["result_payload_redacted"] is True
    assert payload["claim_boundary"]
    assert "node1" not in str(payload["context"])

    reward_events = bridge.event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_RECORDED,
        source_agent="token-bridge",
    )
    assert reward_events[-1].data["settlement_recorded"] is True
    assert reward_events[-1].data["transaction_hash"] == "0xreward123"
    assert reward_events[-1].data["identity"]["spiffe_id"] == payload["spiffe_id"]
    assert completed.event_id in reward_events[-1].data["upstream_evidence"]["event_ids"]
    assert reward_events[-1].data["upstream_evidence"]["source_agents"] == ["token-bridge"]
    assert reward_events[-1].data["upstream_evidence"]["payloads_redacted"] is True
    assert completed.event_id in bridge.last_chain_write_event_ids
    assert reward_events[-1].event_id in bridge.last_chain_write_event_ids


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
    assert blocked[-1].data["source_quality"] == "policy_denied_before_actuator"
    assert blocked[-1].data["safe_actuator"] is True
    assert blocked[-1].data["safe_actuator_used"] is False
    metadata = blocked[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.token_bridge.safe_actuator_claim_gate.v1"
    assert claim_gate["local_chain_write_attempt_succeeded"] is False
    assert claim_gate["pending_chain_submission_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert blocked[-1].data["duration_ms"] >= 0
    assert blocked[-1].data["result_summary"]["success"] is False
    assert blocked[-1].data["result_summary"]["submitted_transaction"] is False

    reward_blocked = bridge.event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_BLOCKED,
        source_agent="token-bridge",
    )
    assert reward_blocked[-1].data["settlement_recorded"] is False
    assert blocked[-1].event_id in reward_blocked[-1].data["upstream_evidence"]["event_ids"]


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
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.token_bridge.safe_actuator_claim_gate.v1"
    assert claim_gate["safe_actuator_simulated"] is True
    assert claim_gate["pending_chain_submission_claim_allowed"] is False
    assert claim_gate["live_token_settlement_finality_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False

    reward_blocked = bridge.event_bus.get_event_history(
        event_type=EventType.REWARD_RELAY_BLOCKED,
        source_agent="token-bridge",
    )
    assert reward_blocked[-1].data["simulated"] is True
    assert reward_blocked[-1].data["settlement_recorded"] is False


@pytest.mark.asyncio
async def test_token_bridge_unsupported_chain_write_result_carries_evidence_metadata(tmp_path):
    bridge = _bridge(tmp_path)

    result = await bridge._execute_chain_write_through_actuator(
        "unknown_token_bridge_operation",
        {"node_id": "secret-node"},
    )

    assert result.success is False
    metadata = _metadata_dict(result)
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["redacted"] is True
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.token_bridge.safe_actuator_claim_gate.v1"
    assert claim_gate["operation"] == "unknown_token_bridge_operation"
    assert claim_gate["local_chain_write_attempt_succeeded"] is False
    assert claim_gate["pending_chain_submission_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
    assert metadata["evidence"]["operation"] == "unknown_token_bridge_operation"
    assert metadata["evidence"]["context_keys"] == ["node_id"]
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_result_values_redacted"] is True


def test_token_bridge_rewards_web3_failure_result_carries_evidence_metadata(tmp_path):
    bridge = _bridge(tmp_path)
    bridge._init_web3 = MagicMock(return_value=False)

    result = bridge._submit_rewards_transaction(
        "push_rewards_to_chain",
        {"rewards": {"secret-node": 10.0}, "uptimes": {"secret-node": 95}},
    )

    assert result.success is False
    metadata = _metadata_dict(result)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["operation"] == "push_rewards_to_chain"
    assert claim_gate["local_chain_write_attempt_succeeded"] is False
    assert claim_gate["pending_chain_submission_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert metadata["evidence"]["submitted_transaction"] is False
    assert metadata["evidence"]["transaction_hash_present"] is False
    assert metadata["evidence"]["context_keys"] == ["rewards", "uptimes"]
    assert "secret-node" not in str(metadata["evidence"])


def test_token_bridge_rewards_success_result_carries_submission_evidence_metadata(tmp_path):
    bridge = _bridge(tmp_path)
    _configure_reward_success(bridge)

    result = bridge._submit_rewards_transaction(
        "push_rewards_to_chain",
        {"rewards": {"node1": 10.0}, "uptimes": {"node1": 95}},
    )

    assert result.success is True
    metadata = _metadata_dict(result)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["operation"] == "push_rewards_to_chain"
    assert claim_gate["local_chain_write_attempt_succeeded"] is True
    assert claim_gate["pending_chain_submission_claim_allowed"] is True
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert metadata["evidence"]["submitted_transaction"] is True
    assert metadata["evidence"]["transaction_hash_present"] is True
    assert metadata["evidence"]["transaction_hash_hash"]


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
    assert failed[-1].data["source_quality"] == "safe_actuator_simulated_no_settlement"
    assert failed[-1].data["duration_ms"] >= 0
    assert failed[-1].data["simulated"] is True
    assert failed[-1].data["submitted_transaction"] is False
    assert failed[-1].data["context"]["escrow_id"] == f"sha256:{_hash('escrow-1')}"
    assert failed[-1].data["context"]["target_node_id"] == f"sha256:{_hash('node1')}"
    assert failed[-1].data["context"]["amount_xot"] == 10.0
    assert failed[-1].data["context_values_redacted"] is True
    assert failed[-1].data["result_summary"]["simulated"] is True
    assert failed[-1].data["result_summary"]["submitted_transaction"] is False
    assert failed[-1].data["result_summary"]["transaction_hash_present"] is False
    assert "escrow-1" not in str(failed[-1].data["context"])
    assert "node1" not in str(failed[-1].data["context"])

    held = bridge.event_bus.get_event_history(
        event_type=EventType.MARKETPLACE_ESCROW_HELD,
        source_agent="token-bridge",
    )
    assert held == []
    blocked = bridge.event_bus.get_event_history(
        event_type=EventType.MARKETPLACE_ESCROW_BLOCKED,
        source_agent="token-bridge",
    )
    blocked_payload = blocked[-1].data
    assert blocked_payload["escrow_id_hash"] == _hash("escrow-1")
    assert blocked[-1].data["status"] == "blocked"
    assert blocked_payload["spiffe_id_hash"] == _hash(
        "spiffe://x0tta6bl4.mesh/workload/token-bridge"
    )
    assert blocked_payload["raw_identifiers_redacted"] is True
    blocked_serialized = str(blocked_payload)
    assert "escrow-1" not in blocked_serialized
    assert "spiffe://x0tta6bl4.mesh/workload/token-bridge" not in blocked_serialized
    assert failed[-1].event_id in blocked[-1].data["upstream_evidence"]["event_ids"]
    assert blocked[-1].data["upstream_evidence"]["source_agents"] == ["token-bridge"]
    assert blocked[-1].data["upstream_evidence"]["payloads_redacted"] is True
    assert failed[-1].event_id in bridge.last_chain_write_event_ids
    assert blocked[-1].event_id in bridge.last_chain_write_event_ids


@pytest.mark.asyncio
async def test_token_bridge_from_chain_stake_event_publishes_redacted_sync_evidence(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.register_address("node1", "0xUser1")
    bridge.mesh_token.balance_of.return_value = 0.0

    event = _chain_event(
        {"user": "0xUser1", "amount": 1_000_000_000_000_000_000},
        tx_hash="0xstake123",
    )

    await bridge._handle_event("Staked", event)

    observed = [
        event
        for event in bridge.event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="token-bridge",
        )
        if event.data.get("stage") == "chain_event_observed"
    ][-1]
    payload = observed.data
    payload_text = str(payload)

    assert payload["resource"] == "dao:token_bridge:from_chain:staked"
    assert payload["event_name"] == "Staked"
    assert payload["transaction_hash"] == "0xstake123"
    assert payload["chain_arg_keys"] == ["user", "amount"]
    assert payload["chain_arg_values_redacted"] is True
    assert payload["safe_observation"] is True
    assert payload["identity"]["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/token-bridge"
    assert payload["sync_result"]["local_update"] == "stake_synced"
    assert payload["sync_result"]["amount_xot"] == 1.0
    assert len(payload["sync_result"]["address_hash"]) == 64
    assert "0xUser1" not in payload_text
    assert "node1" not in payload_text


@pytest.mark.asyncio
async def test_token_bridge_bridge_deposit_event_publishes_redacted_mint_evidence(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.register_address("node-deposit", "0xabc123")
    event = _chain_event(
        {
            "depositId": "0xdepositid",
            "depositor": "0xDepositor",
            "recipient": "0xabc123",
            "amount": 7_000_000_000_000_000_000,
            "nodeIdHash": "0xnodehash",
            "meshNodeId": "node-deposit",
        },
        block=250,
        tx_hash="0xbridgedeposit",
    )
    bridge._init_web3 = MagicMock(return_value=False)

    await bridge._handle_event("BridgeDeposit", event)

    bridge.mesh_token.mint.assert_called_once_with(
        "node-deposit",
        7.0,
        "bridge_deposit_sepolia",
    )
    observed = [
        event
        for event in bridge.event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="token-bridge",
        )
        if event.data.get("stage") == "chain_event_observed"
    ][-1]
    payload = observed.data
    payload_text = str(payload)

    assert payload["resource"] == "dao:token_bridge:from_chain:bridgedeposit"
    assert payload["event_name"] == "BridgeDeposit"
    assert payload["block_number"] == 250
    assert payload["transaction_hash"] == "0xbridgedeposit"
    assert payload["chain_arg_keys"] == ["recipient", "amount"]
    assert payload["sync_result"]["local_update"] == "bridge_deposit_minted"
    assert payload["sync_result"]["transaction_status"] == "confirmed"
    assert payload["sync_result"]["amount_xot"] == 7.0
    assert payload["chain_arg_values_redacted"] is True
    assert "0xabc123" not in payload_text
    assert "node-deposit" not in payload_text


@pytest.mark.asyncio
async def test_token_bridge_sync_balance_publishes_redacted_chain_read_evidence(tmp_path):
    bridge = _bridge(tmp_path)
    bridge._init_web3 = MagicMock(return_value=True)
    bridge.contract = MagicMock()
    bridge.register_address("node1", "0xBalance1")
    bridge.contract.functions.balanceOf.return_value.call.return_value = (
        10_000_000_000_000_000_000
    )
    bridge.mesh_token.balance_of.return_value = 5.0

    result = await bridge.sync_balance("node1")

    assert result == 10.0
    bridge.mesh_token.mint.assert_called_once_with("node1", 5.0, "chain_sync")
    observed = [
        event
        for event in bridge.event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="token-bridge",
        )
        if event.data.get("stage") == "chain_event_observed"
    ][-1]
    payload = observed.data
    payload_text = str(payload)

    assert payload["resource"] == "dao:token_bridge:from_chain:balanceof"
    assert payload["event_name"] == "balanceOf"
    assert payload["chain_arg_keys"] == ["account"]
    assert payload["chain_arg_values_redacted"] is True
    assert payload["sync_result"]["local_update"] == "balance_synced"
    assert payload["sync_result"]["update_action"] == "minted"
    assert payload["sync_result"]["balance_xot"] == 10.0
    assert payload["sync_result"]["delta_xot"] == 5.0
    assert "0xBalance1" not in payload_text
    assert "node1" not in payload_text


def test_token_bridge_get_chain_stats_publishes_redacted_read_evidence(tmp_path):
    bridge = _bridge(tmp_path)
    bridge._init_web3 = MagicMock(return_value=True)
    bridge.contract = MagicMock()
    bridge.contract.functions.totalStaked.return_value.call.return_value = (
        42_000_000_000_000_000_000
    )
    bridge.contract.functions.currentEpoch.return_value.call.return_value = 7
    bridge.contract.functions.canDistributeRewards.return_value.call.return_value = True

    stats = bridge.get_chain_stats()

    assert stats["total_staked"] == 42.0
    assert stats["current_epoch"] == 7
    assert stats["can_distribute"] is True
    assert stats["contract"] == bridge.config.contract_address
    observed = [
        event
        for event in bridge.event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="token-bridge",
        )
        if event.data.get("event_name") == "chainStats"
    ][-1]
    payload = observed.data
    payload_text = str(payload)

    assert payload["resource"] == "dao:token_bridge:from_chain:chainstats"
    assert payload["chain_arg_values_redacted"] is True
    assert payload["safe_observation"] is True
    assert payload["identity"]["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/token-bridge"
    assert payload["sync_result"]["local_update"] == "chain_stats_read"
    assert payload["sync_result"]["total_staked"] == 42.0
    assert payload["sync_result"]["current_epoch"] == 7
    assert payload["sync_result"]["can_distribute"] is True
    assert len(payload["sync_result"]["contract_address_hash"]) == 64
    assert bridge.config.contract_address not in payload_text


@pytest.mark.asyncio
async def test_epoch_reward_scheduler_publishes_redacted_decision_with_chain_write_evidence(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.push_rewards_to_chain = AsyncMock(return_value="0xepoch")
    bridge._last_chain_write_event_ids = ["evt-chain-write"]
    scheduler = EpochRewardScheduler(
        bridge,
        lambda: {"node-secret": 0.95},
    )
    contract_address = "0x9999999999999999999999999999999999999999"

    await scheduler._distribute_epoch(
        stats={
            "can_distribute": True,
            "current_epoch": 7,
            "total_staked": 42.0,
            "chain_id": 84532,
            "contract": contract_address,
        }
    )

    bridge.push_rewards_to_chain.assert_called_once_with(
        rewards={},
        uptimes={"node-secret": 95},
    )
    scheduler_events = [
        event
        for event in bridge.event_bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="token-bridge",
        )
        if event.data.get("component") == "dao.token_bridge.epoch_reward_scheduler"
    ]
    payload = scheduler_events[-1].data
    payload_text = str(payload)

    assert payload["stage"] == "reward_distribution_submitted"
    assert payload["submitted_transaction"] is True
    assert payload["transaction_hash"] == "0xepoch"
    assert payload["stats_summary"]["current_epoch"] == 7
    assert payload["stats_summary"]["total_staked"] == 42.0
    assert len(payload["stats_summary"]["contract_address_hash"]) == 64
    assert payload["uptime_summary"]["nodes_total"] == 1
    assert len(payload["uptime_summary"]["node_id_hashes"][0]) == 64
    assert payload["downstream_evidence"]["event_ids"] == ["evt-chain-write"]
    assert payload["chain_write_evidence"]["payloads_redacted"] is True
    assert payload["identity"]["did"] == "did:mesh:token:bridge"
    assert "node-secret" not in payload_text
    assert contract_address not in payload_text
