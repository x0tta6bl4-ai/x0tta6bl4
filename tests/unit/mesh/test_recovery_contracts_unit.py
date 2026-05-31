from __future__ import annotations

import json
from unittest.mock import Mock

from src.coordination.events import EventBus, EventType
from src.mesh.recovery_contracts import NodeState, generate_node_id_hash
from src.mesh.recovery_orchestrator import (
    MESH_RECOVERY_SOURCE_AGENT,
    MeshRecoveryOrchestrator,
)
from src.mesh.recovery_policy import RecoveryPolicyManager
from src.services.service_event_trace import service_event_trace_history


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def degraded_state() -> NodeState:
    return NodeState(
        local_health="Degraded",
        packet_loss_pct=18.4,
        yggdrasil_status="Peers down",
    )


def healthy_state() -> NodeState:
    return NodeState(
        local_health="OK",
        packet_loss_pct=0.1,
        yggdrasil_status="Peers visible",
    )


def build_orchestrator(
    state_mock: Mock,
    restart_mock: Mock,
    clock: FakeClock,
    *,
    event_bus: EventBus | None = None,
):
    policy_manager = RecoveryPolicyManager(cooldown_seconds=600, clock=clock)
    orchestrator = MeshRecoveryOrchestrator(
        node_id="node-uuid-4444-8888",
        local_audit_secret="local-node-audit-salt",
        policy_manager=policy_manager,
        restart_action=restart_mock,
        get_node_state=state_mock,
        event_bus=event_bus,
        sleeper=lambda seconds: clock.advance(seconds),
        clock=clock,
    )
    return orchestrator, policy_manager


def test_node_id_hash_uses_hmac_and_does_not_expose_node_id() -> None:
    node_id = "node-uuid-4444-8888"
    digest = generate_node_id_hash(node_id, "local-node-audit-salt")

    assert len(digest) == 64
    assert node_id not in digest
    assert digest != generate_node_id_hash(node_id, "different-local-secret")


def test_first_restart_allowed_and_records_bounded_evidence() -> None:
    clock = FakeClock()
    restart_mock = Mock(return_value=0)
    state_mock = Mock(side_effect=[degraded_state(), healthy_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    assert evidence.policy_decision.allowed is True
    assert evidence.policy_decision.safe_mode_required is False
    assert evidence.claim_gate.local_peer_visible == "PROVEN"
    assert evidence.claim_gate.packet_loss_metric_decreased == "PROVEN"
    assert (
        evidence.claim_gate.customer_traffic_restored
        == "UNPROVEN_AWAITING_DATAPLANE_PROOF"
    )
    assert evidence.escalation_required is False
    assert restart_mock.call_count == 1
    assert evidence.raw_values_redacted is True


def test_recovery_success_publishes_redacted_eventbus_evidence(tmp_path) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(return_value=0)
    state_mock = Mock(side_effect=[degraded_state(), healthy_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
        event_bus=event_bus,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    events = event_bus.get_event_history(source_agent=MESH_RECOVERY_SOURCE_AGENT)
    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.PIPELINE_STAGE_END
    assert event.data["schema"] == "mesh_node_degradation_recovery.eventbus.v1"
    assert event.data["recovery_event_id"] == evidence.event_id
    assert event.data["node_id_hash"] == evidence.node_id_hash
    assert event.data["policy_allowed"] is True
    assert event.data["success"] is True
    assert (
        event.data["claim_gate"]["customer_traffic_restored"]
        == "UNPROVEN_AWAITING_DATAPLANE_PROOF"
    )
    assert "node-uuid-4444-8888" not in json.dumps(event.data, sort_keys=True)


def test_recovery_eventbus_source_is_visible_through_service_trace(tmp_path) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(return_value=0)
    state_mock = Mock(side_effect=[degraded_state(), healthy_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
        event_bus=event_bus,
    )

    orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )
    trace = service_event_trace_history(
        event_bus,
        service_name=MESH_RECOVERY_SOURCE_AGENT,
    )

    assert trace["status"] == "ok"
    assert trace["filter"]["source_agents"] == [MESH_RECOVERY_SOURCE_AGENT]
    assert trace["events_total"] == 1
    serialized = trace["events"][0]
    assert serialized["source_agent"] == MESH_RECOVERY_SOURCE_AGENT
    assert serialized["redacted"] is True
    summary = serialized["evidence_summary"]
    assert summary["runtime_evidence"]["bool_fields"]["policy_allowed"] is True
    assert summary["runtime_evidence"]["bool_fields"]["safe_mode_required"] is False
    assert summary["identity_evidence"]["hash_fields"] == ["node_id_hash"]


def test_second_restart_forbidden_and_requires_safe_mode() -> None:
    clock = FakeClock()
    restart_mock = Mock(return_value=0)
    state_mock = Mock(side_effect=[degraded_state(), healthy_state(), degraded_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
    )

    orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )
    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-02",
        incident_key="incident-vpn-loss",
    )

    assert evidence.policy_decision.allowed is False
    assert evidence.policy_decision.cooldown_active is True
    assert evidence.policy_decision.safe_mode_required is True
    assert evidence.action == "block_and_escalate"
    assert evidence.claim_gate.local_peer_visible == "UNPROVEN"
    assert evidence.escalation_required is True
    assert restart_mock.call_count == 1


def test_blocked_recovery_publishes_safe_mode_task_blocked_event(tmp_path) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(return_value=0)
    state_mock = Mock(side_effect=[degraded_state(), healthy_state(), degraded_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
        event_bus=event_bus,
    )

    orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )
    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-02",
        incident_key="incident-vpn-loss",
    )

    events = event_bus.get_event_history(source_agent=MESH_RECOVERY_SOURCE_AGENT)
    assert [event.event_type for event in events] == [
        EventType.PIPELINE_STAGE_END,
        EventType.TASK_BLOCKED,
    ]
    blocked_payload = events[-1].data
    assert blocked_payload["stage"] == "recovery_blocked"
    assert blocked_payload["status"] == "blocked"
    assert blocked_payload["safe_mode_required"] is True
    assert blocked_payload["cooldown_active"] is True
    assert blocked_payload["escalation_required"] is True
    assert blocked_payload["recovery_event_id"] == evidence.event_id
    assert restart_mock.call_count == 1


def test_revalidation_failure_escalates_and_keeps_claims_unproven() -> None:
    clock = FakeClock()
    restart_mock = Mock(return_value=0)
    state_mock = Mock(side_effect=[degraded_state(), degraded_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    assert evidence.policy_decision.allowed is True
    assert evidence.claim_gate.local_peer_visible == "UNPROVEN"
    assert evidence.claim_gate.packet_loss_metric_decreased == "UNPROVEN"
    assert (
        evidence.claim_gate.customer_traffic_restored
        == "UNPROVEN_AWAITING_DATAPLANE_PROOF"
    )
    assert evidence.after.local_health == "Degraded"
    assert evidence.escalation_required is True
