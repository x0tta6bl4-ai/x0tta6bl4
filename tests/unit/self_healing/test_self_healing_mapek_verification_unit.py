from __future__ import annotations

from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.self_healing.mape_k import SelfHealingManager


def test_run_cycle_publishes_bounded_healing_verified_event(tmp_path) -> None:
    """Post-action verification proves only local recovered state."""

    bus = EventBus(project_root=str(tmp_path))
    manager = SelfHealingManager(node_id="node-secret", event_bus=bus)

    with (
        patch.object(
            manager.monitor,
            "check",
            side_effect=[
                {"anomaly_detected": True, "issue": "Network Loss"},
                {"anomaly_detected": False, "issue": "Healthy"},
            ],
        ),
        patch.object(manager.analyzer, "analyze", return_value="Network Loss"),
        patch.object(manager.planner, "plan", return_value="Switch route"),
        patch.object(manager.executor, "execute", return_value=True),
    ):
        manager.run_cycle({"packet_loss_percent": 18.5, "node_id": "raw-node"})
        manager.run_cycle({"packet_loss_percent": 0.4, "node_id": "raw-node"})

    verified = bus.get_event_history(
        EventType.HEALING_VERIFIED,
        source_agent="self-healing-mapek",
        limit=10,
    )
    assert len(verified) == 1
    data = verified[0].data
    assert data["operation"] == "verify"
    assert data["status"] == "verified"
    assert data["read_only"] is True
    assert data["observed_state"] is True
    assert data["success"] is True
    assert data["claim_gate"]["schema"] == (
        "x0tta6bl4.self_healing_mapek.verification_claim_gate.v1"
    )
    assert data["claim_gate"]["local_healing_verification_claim_allowed"] is True
    assert data["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert data["claim_gate"]["production_readiness_claim_allowed"] is False
    assert data["thinking"]["profile"]["role"] == "healing"
    assert data["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "self_healing_mapek_verify"
    )
    assert "raw-node" not in str(data)


def test_run_cycle_does_not_verify_partial_metric_improvement_above_threshold(
    tmp_path,
) -> None:
    """A smaller bad value is not proof of recovery while still anomalous."""

    bus = EventBus(project_root=str(tmp_path))
    manager = SelfHealingManager(node_id="node-secret", event_bus=bus)

    with (
        patch.object(
            manager.monitor,
            "check",
            side_effect=[
                {"anomaly_detected": True, "issue": "Network Loss"},
                {"anomaly_detected": True, "issue": "Network Loss"},
                {"anomaly_detected": True, "issue": "Network Loss"},
            ],
        ),
        patch.object(manager.analyzer, "analyze", return_value="Network Loss"),
        patch.object(manager.planner, "plan", return_value="Switch route"),
        patch.object(manager.executor, "execute", return_value=True) as execute,
    ):
        manager.run_cycle({"packet_loss_percent": 18.5})
        manager.run_cycle({"packet_loss_percent": 17.0})
        manager.run_cycle({"packet_loss_percent": 17.0})

    failed = [
        event
        for event in bus.get_event_history(
            EventType.TASK_FAILED,
            source_agent="self-healing-mapek",
            limit=10,
        )
        if event.data.get("operation") == "verify"
    ]
    assert len(failed) == 1
    data = failed[0].data
    assert data["status"] == "not_verified"
    assert data["success"] is False
    assert data["claim_gate"]["local_healing_verification_claim_allowed"] is False
    assert "post_action_local_state_not_recovered" in data["claim_gate"]["blockers"]
    assert data["last_thinking_context"]["applied"]["framing"]["problem"] == (
        "self_healing_mapek_verify"
    )
    assert execute.call_count == 1

    blocked = [
        event
        for event in bus.get_event_history(
            EventType.TASK_FAILED,
            source_agent="self-healing-mapek",
            limit=10,
        )
        if event.data.get("stage") == "execute_blocked_by_cooldown"
    ]
    assert len(blocked) == 1
    blocked_data = blocked[0].data
    assert blocked_data["status"] == "blocked_by_cooldown"
    assert blocked_data["success"] is False
    assert blocked_data["safe_actuator"] is True
    assert blocked_data["control_action"] is True
    assert blocked_data["claim_gate"]["remediation_cooldown_active"] is True
    assert blocked_data["claim_gate"]["local_control_action_claim_allowed"] is False
    assert blocked_data["claim_gate"]["restored_dataplane_claim_allowed"] is False
    assert blocked_data["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert blocked_data["claim_gate"]["production_readiness_claim_allowed"] is False
    assert "remediation_cooldown_active" in blocked_data["claim_gate"]["blockers"]
    assert blocked_data["safe_actuator_evidence_metadata"]["redacted"] is True
    assert (
        blocked_data["safe_actuator_evidence_metadata"]["claim_gate"][
            "safe_actuator_result_recorded"
        ]
        is False
    )
    assert blocked_data["oscillation_guard"]["blocked"] is True
    assert blocked_data["oscillation_guard"]["reason"] == (
        "failed_verification_retry_blocked"
    )
    assert blocked_data["oscillation_guard"]["raw_values_redacted"] is True
    assert "node-secret" not in str(blocked_data)
    assert "raw-node" not in str(blocked_data)
