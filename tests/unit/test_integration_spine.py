import json

from src.coordination.events import EventBus, EventType
from src.dao.token_rewards import TokenRewards
from src.integration.code_wiring import build_report as build_code_wiring_report
from src.integration.code_wiring import main as code_wiring_main
from src.integration.spine import (
    IntegrationSpine,
    SafeActuator,
    SafeActuatorResult,
    SpineIdentity,
    SpineRequest,
)
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


class _FakeExecutor:
    def __init__(self, result=True):
        self.result = result
        self.calls = []
        self.was_simulated = False

    def execute(self, action, context):
        self.calls.append((action, context))
        return self.result


class _FakeRewards:
    def __init__(self):
        self.calls = []
        self.kwargs = []

    def reward_relay(self, node_address, packets, **kwargs):
        self.calls.append((node_address, packets))
        self.kwargs.append(kwargs)


class _ReturningRewards:
    def __init__(self, result):
        self.result = result
        self.calls = []
        self.kwargs = []

    def reward_relay(self, node_address, packets, **kwargs):
        self.calls.append((node_address, packets))
        self.kwargs.append(kwargs)
        return self.result


def _allowing_policy():
    engine = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    engine.add_rule(
        PolicyRule(
            rule_id="allow-relay",
            name="Allow relay workload",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://mesh.x0tta6bl4.mesh/workload/*",
            allowed_resources=["mesh/relay"],
            priority=500,
        )
    )
    return engine


def _request(**overrides):
    data = {
        "request_id": "req-1",
        "identity": SpineIdentity(
            node_id="node-1",
            spiffe_id="spiffe://mesh.x0tta6bl4.mesh/workload/relay",
            did="did:mesh:pqc:node-1:abc123",
            wallet_address="0x" + "b" * 40,
        ),
        "action": "Switch route",
        "resource": "mesh/relay",
        "workload_type": "relay",
        "reward_packets": 250,
    }
    data.update(overrides)
    return SpineRequest(**data)


def test_spine_wires_identity_event_policy_actuator_and_settlement(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    executor = _FakeExecutor()
    rewards = _FakeRewards()
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(executor),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "COMPLETED"
    assert outcome.allowed is True
    assert outcome.policy_allowed is True
    assert outcome.action_executed is True
    assert outcome.settlement_recorded is True
    assert outcome.matched_rules == ["allow-relay"]
    assert outcome.claim_gate["local_reward_adapter_record_claim_allowed"] is True
    assert outcome.claim_gate["external_settlement_finality_claim_allowed"] is False
    assert outcome.claim_gate["dataplane_delivery_claim_allowed"] is False
    assert outcome.cross_plane_claim_gate["allowed"] is False
    assert (
        outcome.safe_actuator_evidence_metadata["schema"]
        == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    )
    assert outcome.safe_actuator_evidence_metadata["redacted"] is True
    assert (
        outcome.safe_actuator_evidence_metadata["claim_gate"][
            "safe_actuator_result_recorded"
        ]
        is True
    )
    assert outcome.safe_actuator_evidence_metadata["cross_plane_claim_gate"]["allowed"] is False
    assert "settlement_finality" in outcome.cross_plane_claim_gate["requested_claim_ids"]
    assert rewards.calls == [("0x" + "b" * 40, 250)]
    assert rewards.kwargs[0]["upstream_event_ids"] == outcome.event_ids[:2]
    assert rewards.kwargs[0]["upstream_source_agents"] == ["integration-spine"]
    assert rewards.kwargs[0]["upstream_claim_gate"]["local_actuator_execution_claim_allowed"] is True
    assert rewards.kwargs[0]["upstream_claim_gate"]["external_settlement_finality_claim_allowed"] is False
    assert rewards.kwargs[0]["upstream_cross_plane_claim_gate"]["allowed"] is False
    assert executor.calls[0][0] == "Switch route"
    actuator_context = executor.calls[0][1]
    assert actuator_context["identity"]["node_id"] == "node-1"
    assert actuator_context["claim_gate"]["policy_decision_claim_allowed"] is True
    assert actuator_context["claim_gate"]["local_actuator_execution_claim_allowed"] is False
    assert actuator_context["claim_gate"]["external_settlement_finality_claim_allowed"] is False
    assert actuator_context["cross_plane_claim_gate"]["allowed"] is False
    assert actuator_context["upstream_event_ids"] == outcome.event_ids[:2]
    assert actuator_context["upstream_source_agents"] == ["integration-spine"]

    history = bus.get_event_history(limit=10)
    history_types = [event.event_type for event in history]
    assert history_types == [
        EventType.COORDINATION_REQUEST,
        EventType.PIPELINE_STAGE_START,
        EventType.PIPELINE_STAGE_END,
    ]
    for event in history:
        assert event.data["claim_gate"]["external_settlement_finality_claim_allowed"] is False
        assert event.data["claim_gate"]["dataplane_delivery_claim_allowed"] is False
        assert event.data["cross_plane_claim_gate"]["allowed"] is False
    completed_event = history[-1]
    assert completed_event.data["safe_actuator"] is True
    assert (
        completed_event.data["safe_actuator_evidence_metadata"]["schema"]
        == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    )
    assert (
        completed_event.data["safe_actuator_evidence_metadata"]["claim_gate"][
            "safe_actuator_result_recorded"
        ]
        is True
    )
    assert completed_event.data["safe_actuator_evidence_metadata"]["redacted"] is True
    assert len(outcome.event_ids) == 3


def test_spine_fails_closed_before_actuator_when_policy_denies(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    executor = _FakeExecutor()
    rewards = _FakeRewards()
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
        actuator=SafeActuator(executor),
        reward_manager=rewards,
    )

    outcome = spine.process(_request(resource="mesh/admin"))

    assert outcome.status == "POLICY_DENIED"
    assert outcome.allowed is False
    assert outcome.action_executed is False
    assert outcome.settlement_recorded is False
    assert executor.calls == []
    assert rewards.calls == []
    assert [event.event_type for event in bus.get_event_history(limit=10)] == [
        EventType.COORDINATION_REQUEST,
        EventType.TASK_BLOCKED,
    ]


def test_spine_rejects_invalid_identity_before_policy_action_and_settlement(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    executor = _FakeExecutor()
    rewards = _FakeRewards()
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(executor),
        reward_manager=rewards,
    )

    outcome = spine.process(
        _request(identity=SpineIdentity(node_id="", spiffe_id="mesh-node"))
    )

    assert outcome.status == "IDENTITY_REJECTED"
    assert outcome.policy_allowed is False
    assert outcome.action_executed is False
    assert outcome.settlement_recorded is False
    assert "node_id is required" in outcome.reason
    assert "spiffe_id must start with spiffe://" in outcome.reason
    assert executor.calls == []
    assert rewards.calls == []


def test_spine_blocks_settlement_when_actuator_fails(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    executor = _FakeExecutor(result=False)
    rewards = _FakeRewards()
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(executor),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "ACTUATOR_FAILED"
    assert outcome.policy_allowed is True
    assert outcome.action_executed is False
    assert outcome.settlement_recorded is False
    assert executor.calls
    assert rewards.calls == []


def test_spine_treats_simulated_actuator_as_not_production_safe(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    rewards = _FakeRewards()
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(
            lambda action, context: SafeActuatorResult(
                success=True,
                reason="dry run only",
                simulated=True,
            )
        ),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "ACTUATOR_SIMULATED"
    assert outcome.allowed is False
    assert outcome.settlement_recorded is False
    assert rewards.calls == []


def test_spine_fails_closed_when_reward_manager_returns_false(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    rewards = _ReturningRewards(False)
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(_FakeExecutor()),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "SETTLEMENT_FAILED"
    assert outcome.allowed is False
    assert outcome.action_executed is True
    assert outcome.settlement_recorded is False
    assert outcome.reason == "reward manager returned false"
    assert rewards.calls == [("0x" + "b" * 40, 250)]
    assert [event.event_type for event in bus.get_event_history(limit=10)] == [
        EventType.COORDINATION_REQUEST,
        EventType.PIPELINE_STAGE_START,
        EventType.TASK_FAILED,
    ]


def test_spine_fails_closed_when_reward_manager_returns_error_status(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    rewards = _ReturningRewards({"ok": False, "status": "failed"})
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(_FakeExecutor()),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "SETTLEMENT_FAILED"
    assert outcome.settlement_recorded is False
    assert outcome.reason == "reward manager returned ok=false"


def test_spine_fails_closed_when_reward_manager_returns_simulated_result(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    rewards = _ReturningRewards({"ok": True, "simulated": True, "status": "ok"})
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(_FakeExecutor()),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "SETTLEMENT_FAILED"
    assert outcome.allowed is False
    assert outcome.action_executed is True
    assert outcome.settlement_recorded is False
    assert outcome.reason == "reward manager returned simulated=true"
    assert rewards.calls == [("0x" + "b" * 40, 250)]
    assert [event.event_type for event in bus.get_event_history(limit=10)] == [
        EventType.COORDINATION_REQUEST,
        EventType.PIPELINE_STAGE_START,
        EventType.TASK_FAILED,
    ]


def test_spine_fails_closed_when_token_rewards_is_local_only(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    rewards = TokenRewards("0x" + "a" * 40, private_key=None)
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(_FakeExecutor()),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    assert outcome.status == "SETTLEMENT_FAILED"
    assert outcome.allowed is False
    assert outcome.settlement_recorded is False
    assert outcome.reason == "reward manager returned simulated=true"
    assert rewards.tx_history == []


def test_spine_passes_event_ids_to_reward_event_without_payload(tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    rewards = TokenRewards(
        "0x" + "a" * 40,
        private_key=None,
        event_bus=bus,
        source_agent="token-rewards-test",
        node_id="node-1",
    )
    spine = IntegrationSpine(
        event_bus=bus,
        policy_engine=_allowing_policy(),
        actuator=SafeActuator(_FakeExecutor()),
        reward_manager=rewards,
    )

    outcome = spine.process(_request())

    reward_event = bus.get_event_history(
        event_type=EventType.REWARD_RELAY_RECORDED,
        source_agent="token-rewards-test",
    )[0]
    upstream = reward_event.data["upstream_evidence"]

    assert outcome.status == "SETTLEMENT_FAILED"
    assert upstream["source_agents"] == ["integration-spine"]
    assert upstream["event_ids"] == outcome.event_ids[:2]
    assert upstream["claim_gate_summary"]["present"] is True
    assert upstream["claim_gate_summary"]["local_actuator_execution_claim_allowed"] is True
    assert upstream["claim_gate_summary"]["external_settlement_finality_claim_allowed"] is False
    assert upstream["cross_plane_claim_gate_summary"]["present"] is True
    assert upstream["cross_plane_claim_gate_summary"]["allowed"] is False
    assert upstream["payloads_redacted"] is True
    assert "Switch route" not in str(upstream)


def test_code_wiring_report_executes_all_required_spine_traces(tmp_path):
    report = build_code_wiring_report(tmp_path)
    summary = report["summary"]
    cases = {case["name"]: case for case in report["trace_cases"]}

    assert report["status"] == "VERIFIED HERE"
    assert report["ok"] is True
    assert report["decision"] == "LOCAL_CODE_WIRING_VERIFIED"
    assert report["goal_can_be_marked_complete"] is False
    assert report["mutates_runtime"] is False
    assert report["contacts_live_systems"] is False
    assert report["submits_transaction"] is False
    assert summary["required_wiring_keys_total"] == 5
    assert summary["wiring_keys_covered"] == 5
    assert summary["trace_cases_total"] == 7
    assert summary["trace_cases_failed"] == 0
    assert summary["canonical_identity_consistent"] is True
    assert summary["policy_before_actuator_verified"] is True
    assert summary["simulated_actuator_blocks_settlement"] is True
    assert summary["settlement_failure_fails_closed"] is True
    assert summary["simulated_settlement_fails_closed"] is True
    assert summary["token_rewards_local_only_fails_closed"] is True
    assert summary["token_rewards_event_bus_recorded"] is True
    assert set(report["wiring_covered"]) == {
        "identity",
        "event_bus",
        "policy_engine",
        "safe_actuator",
        "settlement_reward_loop",
    }

    success = cases["success_identity_event_policy_actuator_settlement"]
    assert success["event_sequence"] == [
        EventType.COORDINATION_REQUEST.value,
        EventType.PIPELINE_STAGE_START.value,
        EventType.PIPELINE_STAGE_END.value,
    ]
    assert success["event_ids_match_outcome"] is True
    assert success["executor_calls"] == 1
    assert success["reward_calls"] == 1
    assert success["settlement_recorded"] is True
    assert success["outcome_claim_gate_present"] is True
    assert success["event_claim_gates_present"] is True
    assert success["strong_claims_blocked"] is True
    assert success["actuator_context_claim_gate_present"] is True
    assert success["actuator_context_upstream_events_present"] is True
    assert success["reward_context_claim_gate_present"] is True
    assert success["reward_context_upstream_events_present"] is True
    assert summary["spine_claim_gates_preserved"] is True
    assert summary["actuator_context_claim_gates_preserved"] is True
    assert summary["reward_context_claim_gates_preserved"] is True
    assert summary["safe_actuator_evidence_metadata_retained"] is True
    assert success["event_safe_actuator_metadata_retained"] is True
    assert success["outcome_safe_actuator_metadata_retained"] is True

    policy_denied = cases["policy_denied_before_actuator_settlement"]
    assert policy_denied["event_sequence"] == [
        EventType.COORDINATION_REQUEST.value,
        EventType.TASK_BLOCKED.value,
    ]
    assert policy_denied["executor_calls"] == 0
    assert policy_denied["reward_calls"] == 0

    simulated = cases["simulated_actuator_blocks_settlement"]
    assert simulated["actual_status"] == "ACTUATOR_SIMULATED"
    assert simulated["reward_calls"] == 0
    assert simulated["event_safe_actuator_metadata_retained"] is True
    assert simulated["outcome_safe_actuator_metadata_retained"] is True

    simulated_settlement = cases["simulated_settlement_backend_fails_closed"]
    assert simulated_settlement["actual_status"] == "SETTLEMENT_FAILED"
    assert simulated_settlement["settlement_recorded"] is False
    assert simulated_settlement["reward_calls"] == 1

    token_rewards_local = cases["token_rewards_local_only_fails_closed"]
    assert token_rewards_local["actual_status"] == "SETTLEMENT_FAILED"
    assert token_rewards_local["settlement_recorded"] is False
    assert token_rewards_local["reward_calls"] == 1
    assert token_rewards_local["reward_event_count"] == 1
    assert token_rewards_local["event_sequence"] == [
        EventType.COORDINATION_REQUEST.value,
        EventType.PIPELINE_STAGE_START.value,
        EventType.REWARD_RELAY_RECORDED.value,
        EventType.TASK_FAILED.value,
    ]
    assert token_rewards_local["event_ids_match_outcome_spine_events"] is True


def test_code_wiring_cli_writes_current_artifact(tmp_path):
    code = code_wiring_main(
        [
            "--root",
            str(tmp_path),
            "--output-json",
            ".tmp/validation-shards/integration-spine-code-wiring-current.json",
            "--output-md",
            "docs/verification/integration-spine-code-wiring-2026-05-20.md",
            "--require-verified",
        ]
    )

    output = tmp_path / ".tmp/validation-shards/integration-spine-code-wiring-current.json"
    markdown = tmp_path / "docs/verification/integration-spine-code-wiring-2026-05-20.md"
    assert code == 0
    assert output.exists()
    assert markdown.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"].endswith("v2-repo-generated")
    assert payload["summary"]["trace_cases_failed"] == 0
    text = markdown.read_text(encoding="utf-8")
    assert "LOCAL_CODE_WIRING_VERIFIED" in text
    assert "Goal can be marked complete: `False`" in text
    assert "success_identity_event_policy_actuator_settlement" in text
