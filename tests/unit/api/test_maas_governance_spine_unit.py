from src.api.maas_governance import _execute_action
from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_engine import (
    PolicyDecision as ABACPolicyDecision,
    PolicyEffect,
)
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


class FakeDB:
    def __init__(self):
        self.added = []
        self.commits = 0

    def query(self, _model):
        return self

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return None

    def add(self, item):
        self.added.append(item)

    def commit(self):
        self.commits += 1


def _allow_policy():
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-maas-governance-update-config",
            name="Allow MaaS governance config update",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/maas-governance",
            allowed_resources=["api:maas_governance:update_config"],
            priority=1000,
        )
    )
    return policy


def _action():
    return {
        "type": "update_config",
        "params": {
            "key": "global_price_multiplier",
            "value": 1.25,
            "api_token": "secret-token",
        },
    }


def _execute(tmp_path, **kwargs):
    return _execute_action(
        _action(),
        kwargs.pop("db", None),
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-governance",
        did="did:mesh:maas:governance",
        wallet_address="0xgovernance",
        proposal_id="prop-1",
        user_id="user-1",
        **kwargs,
    )


def test_maas_governance_action_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    db = FakeDB()
    bus = EventBus(str(tmp_path))

    result = _execute_action(
        _action(),
        db,
        event_bus=bus,
        policy_engine=_allow_policy(),
        require_policy=True,
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-governance",
        did="did:mesh:maas:governance",
        wallet_address="0xgovernance",
        proposal_id="prop-1",
        user_id="user-1",
    )

    assert result["success"] is True
    assert db.commits == 1
    events = bus.get_event_history(source_agent="maas-governance", limit=10)
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "maas-governance"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/maas-governance"
    assert payload["did"] == "did:mesh:maas:governance"
    assert payload["wallet_address"] == "0xgovernance"
    assert payload["resource"] == "api:maas_governance:update_config"
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-maas-governance-update-config"]
    assert payload["safe_actuator"] is True
    assert payload["context"]["params"]["api_token"] == "<redacted>"
    assert payload["context"]["proposal_id"] != "prop-1"
    assert payload["context"]["user_id"] != "user-1"
    assert "prop-1" not in str(payload["context"])
    assert "user-1" not in str(payload["context"])
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == (
        "x0tta6bl4.maas_governance.safe_actuator_claim_gate.v1"
    )
    assert claim_gate["local_maas_governance_action_succeeded"] is True
    assert claim_gate["redacted"] is True
    assert claim_gate["dao_governance_finality_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_result_values_redacted"] is True
    assert metadata["evidence"]["resource"] == "api:maas_governance:update_config"
    assert "local, policy-gated API action dispatch" in metadata["claim_boundary"]
    assert payload["claim_boundary"]


def test_maas_governance_policy_denied_blocks_db_mutation(tmp_path):
    db = FakeDB()
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    bus = EventBus(str(tmp_path))

    result = _execute_action(
        _action(),
        db,
        event_bus=bus,
        policy_engine=policy,
        require_policy=True,
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-governance",
    )

    assert result["success"] is False
    assert "No rules matched" in result["detail"]
    assert db.commits == 0
    assert db.added == []
    blocked = bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="maas-governance",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False


def test_maas_governance_blocks_abac_deny_decision_shape(tmp_path):
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

    db = FakeDB()
    bus = EventBus(str(tmp_path))

    result = _execute_action(
        _action(),
        db,
        event_bus=bus,
        policy_engine=ABACDenyPolicy(),
        require_policy=True,
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-governance",
    )

    assert result["success"] is False
    assert result["detail"] == "ABAC deny"
    assert result["matched_rules"] == ["deny-all"]
    assert db.commits == 0
    blocked = bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="maas-governance",
    )
    assert blocked[-1].data["policy_allowed"] is False


def test_maas_governance_policy_engine_requires_spiffe_identity(tmp_path):
    db = FakeDB()
    bus = EventBus(str(tmp_path))

    result = _execute_action(
        _action(),
        db,
        event_bus=bus,
        policy_engine=_allow_policy(),
        spiffe_id="",
    )

    assert result["success"] is False
    assert "SPIFFE identity is required" in result["detail"]
    assert db.commits == 0
    blocked = bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="maas-governance",
    )
    assert blocked[-1].data["policy_allowed"] is None


def test_maas_governance_simulated_safe_actuator_fails_closed(tmp_path):
    db = FakeDB()
    bus = EventBus(str(tmp_path))
    actuator = SafeActuator(
        lambda _action, _context: SafeActuatorResult(
            success=True,
            reason="dry run",
            simulated=True,
        )
    )

    result = _execute_action(
        _action(),
        db,
        event_bus=bus,
        safe_actuator=actuator,
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-governance",
    )

    assert result["success"] is False
    assert result["simulated"] is True
    assert db.commits == 0
    failed = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="maas-governance",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    assert metadata["claim_gate"]["safe_actuator_result_recorded"] is True
    assert metadata["claim_gate"]["local_maas_governance_action_succeeded"] is False
    assert metadata["claim_gate"]["production_readiness_claim_allowed"] is False


def test_maas_governance_safe_actuator_failure_fails_closed(tmp_path):
    db = FakeDB()
    bus = EventBus(str(tmp_path))
    calls = []

    def executor(action, context):
        calls.append((action, context))
        return SafeActuatorResult(False, "blocked by actuator")

    result = _execute_action(
        _action(),
        db,
        event_bus=bus,
        safe_actuator=SafeActuator(executor),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/maas-governance",
    )

    assert result["success"] is False
    assert "blocked by actuator" in result["detail"]
    assert db.commits == 0
    assert len(calls) == 1
    failed = bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="maas-governance",
    )
    assert failed[-1].data["stage"] == "actuator_failed"
