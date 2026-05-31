from src.coordination.events import EventBus, EventType
from src.dao.governance import ActionDispatcher, ActionResult
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_engine import (
    PolicyDecision as ABACPolicyDecision,
    PolicyEffect,
)
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


def _allow_policy(action_type="update_config"):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-dao-{action_type}",
            name=f"Allow DAO {action_type}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/dao-governance",
            allowed_resources=[f"dao:governance:{action_type}"],
            priority=1000,
        )
    )
    return policy


def _dispatcher(tmp_path, **kwargs):
    return ActionDispatcher(
        node_id="dao-node-1",
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/dao-governance",
        did="did:mesh:dao:governance",
        wallet_address="0xdao",
        **kwargs,
    )


def _action():
    return {
        "type": "update_config",
        "key": "routing.ttl",
        "value": 60,
        "api_token": "secret-token",
    }


def test_dao_dispatcher_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    dispatcher = _dispatcher(
        tmp_path,
        policy_engine=_allow_policy(),
        require_policy=True,
    )

    result = dispatcher.dispatch(_action())

    assert result.success is True
    assert result.action_type == "update_config"
    events = dispatcher.event_bus.get_event_history(source_agent="dao-governance", limit=10)
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "dao-node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/dao-governance"
    assert payload["did"] == "did:mesh:dao:governance"
    assert payload["wallet_address"] == "0xdao"
    assert payload["resource"] == "dao:governance:update_config"
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-dao-update_config"]
    assert payload["safe_actuator"] is True
    assert payload["context"]["action"]["api_token"] == "<redacted>"
    assert payload["claim_boundary"]
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["source_agents"] == ["dao-governance"]
    assert metadata["redacted"] is True
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.dao_governance.safe_actuator_claim_gate.v1"
    assert claim_gate["local_handler_execution_claim_allowed"] is True
    assert claim_gate["governance_execution_finality_claim_allowed"] is False
    assert claim_gate["production_governance_execution_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
    evidence = metadata["evidence"]
    assert evidence["operation"] == "governance_action_dispatch"
    assert evidence["action_type"] == "update_config"
    assert evidence["action_present"] is True
    assert evidence["handler_present"] is True
    assert evidence["result_present"] is True
    assert evidence["result_success"] is True
    assert evidence["action_values_redacted"] is True
    assert evidence["result_detail_redacted"] is True
    assert "secret-token" not in str(metadata)


def test_dao_dispatcher_policy_denied_blocks_handler(tmp_path):
    calls = []

    def handler(action):
        calls.append(action)
        return ActionResult("update_config", True, "should not run")

    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    dispatcher = _dispatcher(
        tmp_path,
        policy_engine=policy,
        require_policy=True,
    )
    dispatcher.register("update_config", handler)

    result = dispatcher.dispatch(_action())

    assert result.success is False
    assert "No rules matched" in result.detail
    assert calls == []
    blocked = dispatcher.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="dao-governance",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False


def test_dao_dispatcher_blocks_abac_deny_decision_shape(tmp_path):
    calls = []

    class ABACDenyPolicy:
        def evaluate(self, *_args, **_kwargs):
            return ABACPolicyDecision(
                effect=PolicyEffect.DENY,
                policy_id="default-deny",
                rule_id="deny-all",
                reason="ABAC deny",
                attributes_evaluated=1,
                evaluation_time_ms=0.1,
            )

    def handler(action):
        calls.append(action)
        return ActionResult("update_config", True, "should not run")

    dispatcher = _dispatcher(
        tmp_path,
        policy_engine=ABACDenyPolicy(),
        require_policy=True,
    )
    dispatcher.register("update_config", handler)

    result = dispatcher.dispatch(_action())

    assert result.success is False
    assert result.detail == "ABAC deny"
    assert calls == []
    blocked = dispatcher.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="dao-governance",
    )
    assert blocked[-1].data["policy_allowed"] is False
    assert blocked[-1].data["matched_rules"] == ["deny-all"]


def test_dao_dispatcher_policy_engine_requires_spiffe_identity(tmp_path):
    dispatcher = ActionDispatcher(
        node_id="dao-node-1",
        event_bus=EventBus(str(tmp_path)),
        policy_engine=_allow_policy(),
        spiffe_id="",
    )

    result = dispatcher.dispatch(_action())

    assert result.success is False
    assert "SPIFFE identity is required" in result.detail
    blocked = dispatcher.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="dao-governance",
    )
    assert blocked[-1].data["policy_allowed"] is None


def test_dao_dispatcher_simulated_safe_actuator_fails_closed(tmp_path):
    calls = []

    def handler(action):
        calls.append(action)
        return ActionResult("update_config", True, "should not run")

    actuator = SafeActuator(
        lambda _action, _context: SafeActuatorResult(
            success=True,
            reason="dry run",
            simulated=True,
        )
    )
    dispatcher = _dispatcher(tmp_path, safe_actuator=actuator)
    dispatcher.register("update_config", handler)

    result = dispatcher.dispatch(_action())

    assert result.success is False
    assert "dry run" in result.detail
    assert calls == []
    failed = dispatcher.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="dao-governance",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["local_handler_execution_claim_allowed"] is False
    assert "safe_actuator_result_simulated" in claim_gate["blockers"]
    assert "dao_governance_action_result_missing" in claim_gate["blockers"]
    assert metadata["cross_plane_claim_gate"]["allowed"] is False


def test_dao_dispatcher_safe_actuator_failure_fails_closed(tmp_path):
    calls = []

    def executor(action, context):
        calls.append((action, context))
        return SafeActuatorResult(False, "blocked by actuator")

    dispatcher = _dispatcher(tmp_path, safe_actuator=SafeActuator(executor))

    result = dispatcher.dispatch(_action())

    assert result.success is False
    assert "blocked by actuator" in result.detail
    assert len(calls) == 1
    failed = dispatcher.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="dao-governance",
    )
    assert failed[-1].data["stage"] == "actuator_failed"
