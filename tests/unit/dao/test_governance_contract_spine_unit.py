from unittest.mock import MagicMock

import pytest

from src.coordination.events import EventBus, EventType
from src.dao.governance_contract import GovernanceContract
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


def _allow_policy(operation="create_proposal"):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-governance-contract-{operation}",
            name=f"Allow GovernanceContract {operation}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/governance-contract",
            allowed_resources=[f"dao:governance_contract:{operation}"],
            priority=1000,
        )
    )
    return policy


def _contract(tmp_path, **kwargs):
    contract = GovernanceContract.__new__(GovernanceContract)
    contract.contract_address = "0x1111111111111111111111111111111111111111"
    contract.token_address = "0x2222222222222222222222222222222222222222"
    contract.rpc_url = "https://sepolia.base.org"
    contract.private_key = "0xprivate"
    contract.node_id = "governance-contract-node"
    contract.source_agent = "governance-contract"
    contract.event_project_root = "."
    contract.event_bus = kwargs.pop("event_bus", EventBus(str(tmp_path)))
    contract.policy_engine = kwargs.pop("policy_engine", None)
    contract.require_policy = kwargs.pop("require_policy", False)
    contract.identity = {
        "node_id": "governance-contract-node",
        "spiffe_id": kwargs.pop(
            "spiffe_id",
            "spiffe://x0tta6bl4.mesh/workload/governance-contract",
        ),
        "did": "did:mesh:governance:contract",
        "wallet_address": "0xgovernance",
    }
    contract.safe_actuator = kwargs.pop(
        "safe_actuator",
        SafeActuator(contract._execute_chain_write_through_actuator),
    )
    contract._last_chain_write_result = None
    contract._last_chain_write_exception = None

    contract.web3 = MagicMock()
    contract.web3.eth.get_transaction_count.return_value = 5
    contract.web3.eth.gas_price = 123
    contract.web3.eth.account.sign_transaction.return_value.rawTransaction = b"signed"
    tx_hash = MagicMock()
    tx_hash.hex.return_value = "0xcreate123"
    contract.web3.eth.send_raw_transaction.return_value = tx_hash
    contract.web3.eth.wait_for_transaction_receipt.return_value = MagicMock(status=1)

    contract.account = MagicMock()
    contract.account.address = "0xOperator"
    contract.contract = MagicMock()
    contract.contract.functions.proposalCount.return_value.call.return_value = 77
    return contract


def test_governance_contract_create_proposal_emits_identity_policy_and_actuator_events(tmp_path):
    contract = _contract(
        tmp_path,
        policy_engine=_allow_policy(),
        require_policy=True,
    )

    proposal_id = contract.create_proposal("Upgrade mesh", "Deploy hardened release", 3600)

    assert proposal_id == 77
    contract.web3.eth.send_raw_transaction.assert_called_once()
    events = contract.event_bus.get_event_history(source_agent="governance-contract", limit=10)
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "governance-contract-node"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/governance-contract"
    assert payload["did"] == "did:mesh:governance:contract"
    assert payload["wallet_address"] == "0xgovernance"
    assert payload["resource"] == "dao:governance_contract:create_proposal"
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-governance-contract-create_proposal"]
    assert payload["safe_actuator"] is True
    assert payload["submitted_transaction"] is True
    assert payload["transaction_hash"] == "0xcreate123"
    assert payload["claim_boundary"]
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["source_agents"] == ["governance-contract"]
    assert metadata["redacted"] is True
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == (
        "x0tta6bl4.governance_contract.safe_actuator_claim_gate.v1"
    )
    assert claim_gate["resource"] == "dao:governance_contract:create_proposal"
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["redacted"] is True
    assert claim_gate["local_transaction_submission_claim_allowed"] is True
    assert claim_gate["transaction_hash_observed_claim_allowed"] is True
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["governance_execution_finality_claim_allowed"] is False
    assert claim_gate["production_governance_execution_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
    evidence = metadata["evidence"]
    assert evidence["resource"] == "dao:governance_contract:create_proposal"
    assert evidence["operation"] == "create_proposal"
    assert evidence["operation_resource"] == "create_proposal"
    assert evidence["context_values_redacted"] is True
    assert evidence["raw_context_values_redacted"] is True
    assert evidence["raw_result_values_redacted"] is True
    assert evidence["transaction_hash_present"] is True
    assert evidence["transaction_hash_redacted"] is True
    assert evidence["submitted_transaction"] is True
    assert "0xcreate123" not in str(metadata)


def test_governance_contract_policy_denial_blocks_before_raw_transaction(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    contract = _contract(tmp_path, policy_engine=policy, require_policy=True)

    with pytest.raises(PermissionError):
        contract.cast_vote(42, 1)

    contract.web3.eth.send_raw_transaction.assert_not_called()
    blocked = contract.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="governance-contract",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False


def test_governance_contract_missing_spiffe_fails_closed_before_raw_transaction(tmp_path):
    contract = _contract(
        tmp_path,
        policy_engine=_allow_policy("execute_proposal"),
        spiffe_id="",
    )

    with pytest.raises(PermissionError):
        contract.execute_proposal(42)

    contract.web3.eth.send_raw_transaction.assert_not_called()
    blocked = contract.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="governance-contract",
    )
    assert "SPIFFE identity is required" in blocked[-1].data["reason"]
    assert blocked[-1].data["policy_allowed"] is None


def test_governance_contract_simulated_actuator_blocks_execution(tmp_path):
    contract = _contract(
        tmp_path,
        safe_actuator=SafeActuator(
            lambda _operation, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )

    with pytest.raises(RuntimeError, match="dry run"):
        contract.execute_proposal(42)

    contract.contract.functions.executeProposal.assert_not_called()
    contract.web3.eth.send_raw_transaction.assert_not_called()
    failed = contract.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="governance-contract",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["submitted_transaction"] is False
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["local_transaction_submission_claim_allowed"] is False
    assert "safe_actuator_result_simulated" in claim_gate["blockers"]
    assert "transaction_hash_missing" in claim_gate["blockers"]
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
