from __future__ import annotations

import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from src.coordination.events import EventBus, EventType
from src.mesh.recovery_contracts import (
    BoundedClaims,
    NodeState,
    build_post_action_dataplane_claim_gate,
    generate_node_id_hash,
)
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


def degraded_peer_visible_low_loss_state() -> NodeState:
    return NodeState(
        local_health="Degraded",
        packet_loss_pct=0.1,
        yggdrasil_status="Peers visible",
    )


def build_orchestrator(
    state_mock: Mock,
    restart_mock: Mock,
    clock: FakeClock,
    *,
    dataplane_probe: Mock | None = None,
    event_bus: EventBus | None = None,
):
    policy_manager = RecoveryPolicyManager(cooldown_seconds=600, clock=clock)
    orchestrator = MeshRecoveryOrchestrator(
        node_id="node-uuid-4444-8888",
        local_audit_secret="local-node-audit-salt",
        policy_manager=policy_manager,
        restart_action=restart_mock,
        get_node_state=state_mock,
        dataplane_probe=dataplane_probe,
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


def test_policy_execution_limit_is_human_readable_for_default_window() -> None:
    policy_manager = RecoveryPolicyManager(cooldown_seconds=600)

    assert policy_manager.execution_limit_checked == "1_attempt_per_10_minutes"


def test_shared_post_action_dataplane_claim_gate_requires_redacted_event_evidence() -> None:
    gate = build_post_action_dataplane_claim_gate(
        probe_attempted=True,
        dataplane_confirmed=True,
        evidence={
            "source_agents": ["real-network-adapter"],
            "event_ids": ["evt-proof-1"],
            "events_total": 1,
            "event_ids_count": 1,
            "redacted": True,
        },
        claim_boundary="bounded dataplane proof only",
    )

    assert gate.schema == "x0tta6bl4.post_action_dataplane_claim_gate.v1"
    assert gate.decision == "RESTORED_DATAPLANE_CLAIM_ALLOWED"
    assert gate.restored_dataplane_claim_allowed is True
    assert gate.post_action_dataplane_revalidated is True
    assert gate.traffic_delivery_claim_allowed is False
    assert gate.customer_traffic_claim_allowed is False
    assert gate.external_reachability_claim_allowed is False
    assert gate.production_readiness_claim_allowed is False
    assert gate.blockers == []


def test_shared_post_action_dataplane_claim_gate_blocks_overclaim_without_evidence() -> None:
    gate = build_post_action_dataplane_claim_gate(
        probe_attempted=True,
        dataplane_confirmed=True,
        evidence={
            "source_agents": [],
            "event_ids": [],
            "events_total": 0,
            "event_ids_count": 0,
            "redacted": True,
        },
        claim_boundary="bounded dataplane proof only",
    )

    assert gate.decision == "LOCAL_RECOVERY_LIFECYCLE_ONLY"
    assert gate.dataplane_confirmed is True
    assert gate.restored_dataplane_claim_allowed is False
    assert gate.post_action_dataplane_revalidated is False
    assert "post_action_probe_evidence_missing" in gate.blockers
    assert "post_action_probe_source_agent_missing" in gate.blockers


def test_shared_post_action_dataplane_claim_gate_blocks_non_dataplane_actions() -> None:
    gate = build_post_action_dataplane_claim_gate(
        probe_required=False,
        probe_enabled=False,
        probe_target_present=False,
        probe_attempted=False,
        dataplane_confirmed=False,
        evidence={},
        claim_boundary="bounded dataplane proof only",
    )

    assert gate.required_for_restored_dataplane_claim is False
    assert gate.restored_dataplane_claim_allowed is False
    assert gate.blockers == [
        "action_type_does_not_require_dataplane_restoration_claim"
    ]


def test_recovery_contracts_reject_hidden_overclaim_fields() -> None:
    with pytest.raises(ValidationError):
        BoundedClaims(
            local_peer_visible="PROVEN",
            yggdrasil_status_improved="PROVEN",
            packet_loss_metric_decreased="PROVEN",
            customer_traffic_restored="UNPROVEN_AWAITING_DATAPLANE_PROOF",
            live_customer_traffic_confirmed=True,
        )

    with pytest.raises(ValidationError):
        NodeState(
            local_health="OK",
            packet_loss_pct=0.1,
            yggdrasil_status="Peers visible",
            production_ready=True,
        )


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
    assert orchestrator.last_thinking_context["role"] == "healing"
    assert (
        orchestrator.last_thinking_context["applied"]["framing"]["problem"]
        == "mesh_node_recovery_flow"
    )
    assert evidence.post_action_dataplane_revalidation is not None
    assert evidence.post_action_dataplane_revalidation.status == "not_attempted"
    assert (
        evidence.post_action_dataplane_revalidation.restored_dataplane_claim_allowed
        is False
    )
    assert (
        evidence.post_action_dataplane_revalidation.customer_traffic_claim_allowed
        is False
    )


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
    assert event.data["thinking"]["profile"]["role"] == "healing"
    assert event.data["node_id_hash"] == evidence.node_id_hash
    assert event.data["policy_allowed"] is True
    assert event.data["success"] is True
    assert event.data["dataplane_confirmed"] is False
    assert event.data["post_action_dataplane_revalidated"] is False
    assert (
        event.data["post_action_dataplane_revalidation"][
            "restored_dataplane_claim_allowed"
        ]
        is False
    )
    assert (
        event.data["claim_gate"]["customer_traffic_restored"]
        == "UNPROVEN_AWAITING_DATAPLANE_PROOF"
    )
    assert "node-uuid-4444-8888" not in json.dumps(event.data, sort_keys=True)


def test_recovery_eventbus_records_service_identity_presence_without_values(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "MESH_RECOVERY_ORCHESTRATOR_SPIFFE_ID",
        "spiffe://x0tta6bl4.mesh/workload/mesh-recovery-orchestrator",
    )
    monkeypatch.setenv(
        "MESH_RECOVERY_ORCHESTRATOR_DID",
        "did:mesh:recovery:orchestrator",
    )
    monkeypatch.setenv(
        "MESH_RECOVERY_ORCHESTRATOR_WALLET_ADDRESS",
        "0xRecoveryWallet",
    )
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

    assert evidence.service_identity.service_name == MESH_RECOVERY_SOURCE_AGENT
    assert evidence.service_identity.spiffe_id_configured is True
    assert evidence.service_identity.did_configured is True
    assert evidence.service_identity.wallet_address_configured is True
    assert evidence.service_identity.raw_identity_values_redacted is True
    evidence_json = evidence.model_dump_json()
    assert (
        "spiffe://x0tta6bl4.mesh/workload/mesh-recovery-orchestrator"
        not in evidence_json
    )
    assert "did:mesh:recovery:orchestrator" not in evidence_json
    assert "0xRecoveryWallet" not in evidence_json

    payload = event_bus.get_event_history(
        source_agent=MESH_RECOVERY_SOURCE_AGENT,
    )[0].data
    assert payload["service_identity"] == {
        "schema": "x0tta6bl4.service_identity_evidence.v1",
        "service_name": MESH_RECOVERY_SOURCE_AGENT,
        "spiffe_id_configured": True,
        "did_configured": True,
        "wallet_address_configured": True,
        "raw_identity_values_redacted": True,
        "redacted": True,
    }
    assert payload["identity_fields_present"] == {
        "node_id_hash": True,
        "spiffe_id": True,
        "did": True,
        "wallet_address": True,
    }
    serialized = json.dumps(payload, sort_keys=True)
    assert (
        "spiffe://x0tta6bl4.mesh/workload/mesh-recovery-orchestrator"
        not in serialized
    )
    assert "did:mesh:recovery:orchestrator" not in serialized
    assert "0xRecoveryWallet" not in serialized


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


def test_recovery_dataplane_probe_can_allow_restored_dataplane_claim(
    tmp_path,
) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(return_value=0)
    dataplane_probe = Mock(
        return_value={
            "status": "ok",
            "dataplane_confirmed": True,
            "evidence": {
                "source_agents": ["bounded-dataplane-probe"],
                "event_ids": ["evt-proof-01"],
                "events_total": 1,
                "claim_boundary": "bounded dataplane probe evidence only",
                "redacted": True,
            },
        }
    )
    state_mock = Mock(side_effect=[degraded_state(), healthy_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
        dataplane_probe=dataplane_probe,
        event_bus=event_bus,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    revalidation = evidence.post_action_dataplane_revalidation
    assert revalidation is not None
    assert revalidation.status == "success"
    assert revalidation.dataplane_confirmed is True
    assert revalidation.restored_dataplane_claim_allowed is True
    assert revalidation.customer_traffic_claim_allowed is False
    assert (
        evidence.claim_gate.customer_traffic_restored
        == "UNPROVEN_AWAITING_DATAPLANE_PROOF"
    )
    assert evidence.escalation_required is False
    assert dataplane_probe.call_count == 1

    event = event_bus.get_event_history(source_agent=MESH_RECOVERY_SOURCE_AGENT)[0]
    assert event.event_type == EventType.PIPELINE_STAGE_END
    assert event.data["dataplane_confirmed"] is True
    assert event.data["post_action_dataplane_revalidated"] is True
    assert event.data["post_action_dataplane_revalidation"]["claim_gate"][
        "customer_traffic_claim_allowed"
    ] is False

    trace = service_event_trace_history(
        event_bus,
        service_name=MESH_RECOVERY_SOURCE_AGENT,
    )
    summary = trace["events"][0]["evidence_summary"]
    post_action = summary["post_action_dataplane_revalidation"]
    assert post_action["dataplane_confirmed"] is True
    assert post_action["restored_dataplane_claim_allowed"] is True
    assert (
        summary["cross_plane_evidence_profile"]["dataplane_confirmed"] is True
    )


def test_recovery_dataplane_probe_without_redacted_event_evidence_escalates(
    tmp_path,
) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(return_value=0)
    dataplane_probe = Mock(
        return_value={
            "status": "ok",
            "dataplane_confirmed": True,
            "evidence": {
                "source_agents": [],
                "event_ids": [],
                "events_total": 0,
                "redacted": True,
            },
        }
    )
    state_mock = Mock(side_effect=[degraded_state(), healthy_state()])
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
        dataplane_probe=dataplane_probe,
        event_bus=event_bus,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    revalidation = evidence.post_action_dataplane_revalidation
    assert revalidation is not None
    assert revalidation.status == "failed"
    assert revalidation.dataplane_confirmed is True
    assert revalidation.restored_dataplane_claim_allowed is False
    assert "post_action_probe_evidence_missing" in revalidation.claim_gate.blockers
    assert "post_action_probe_source_agent_missing" in revalidation.claim_gate.blockers
    assert evidence.escalation_required is True

    event = event_bus.get_event_history(source_agent=MESH_RECOVERY_SOURCE_AGENT)[0]
    assert event.event_type == EventType.TASK_BLOCKED
    assert event.data["stage"] == "recovery_escalated"


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


def test_restart_action_exception_records_redacted_escalation_event(tmp_path) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(side_effect=RuntimeError("secret node-uuid-4444-8888"))
    state_mock = Mock(side_effect=[degraded_state(), degraded_state()])
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

    assert evidence.return_code == 1
    assert evidence.action_error is True
    assert evidence.action_error_type == "RuntimeError"
    assert evidence.action_error_redacted is True
    assert evidence.post_action_safe_mode_required is True
    assert evidence.escalation_required is True
    assert restart_mock.call_count == 1

    event = event_bus.get_event_history(source_agent=MESH_RECOVERY_SOURCE_AGENT)[0]
    assert event.event_type == EventType.TASK_BLOCKED
    assert event.data["stage"] == "recovery_escalated"
    assert event.data["return_code"] == 1
    assert event.data["action_error"] is True
    assert event.data["action_error_type"] == "RuntimeError"
    assert event.data["action_error_redacted"] is True

    serialized = json.dumps(event.data, sort_keys=True)
    assert "secret node-uuid-4444-8888" not in serialized
    assert "node-uuid-4444-8888" not in serialized


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


def test_revalidation_requires_local_health_ok_before_success_or_dataplane_probe(
    tmp_path,
) -> None:
    clock = FakeClock()
    event_bus = EventBus(project_root=str(tmp_path))
    restart_mock = Mock(return_value=0)
    dataplane_probe = Mock(
        return_value={
            "status": "ok",
            "dataplane_confirmed": True,
            "evidence": {
                "source_agents": ["bounded-dataplane-probe"],
                "event_ids": ["evt-proof-01"],
                "events_total": 1,
                "redacted": True,
            },
        }
    )
    state_mock = Mock(
        side_effect=[degraded_state(), degraded_peer_visible_low_loss_state()]
    )
    orchestrator, _policy_manager = build_orchestrator(
        state_mock,
        restart_mock,
        clock,
        dataplane_probe=dataplane_probe,
        event_bus=event_bus,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    assert evidence.claim_gate.local_peer_visible == "PROVEN"
    assert evidence.claim_gate.packet_loss_metric_decreased == "PROVEN"
    assert evidence.claim_gate.yggdrasil_status_improved == "UNPROVEN"
    assert evidence.after.local_health == "Degraded"
    assert evidence.post_action_safe_mode_required is True
    assert evidence.escalation_required is True
    assert dataplane_probe.call_count == 0

    revalidation = evidence.post_action_dataplane_revalidation
    assert revalidation is not None
    assert revalidation.status == "not_attempted"
    assert revalidation.reason == "local_revalidation_failed"
    assert revalidation.restored_dataplane_claim_allowed is False

    event = event_bus.get_event_history(source_agent=MESH_RECOVERY_SOURCE_AGENT)[0]
    assert event.event_type == EventType.TASK_BLOCKED
    assert event.data["stage"] == "recovery_escalated"
    assert event.data["safe_mode_required"] is True
    assert event.data["policy_safe_mode_required"] is False
    assert event.data["post_action_safe_mode_required"] is True
