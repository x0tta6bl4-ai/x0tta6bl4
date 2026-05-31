from __future__ import annotations

import json
from unittest.mock import Mock

from src.coordination.events import EventBus
from src.mesh.recovery_contracts import NodeState
from src.mesh.recovery_dataplane_probe import (
    build_recovery_dataplane_ping_probe,
    normalize_recovery_dataplane_probe_result,
)
from src.mesh.recovery_orchestrator import MeshRecoveryOrchestrator
from src.mesh.recovery_policy import RecoveryPolicyManager


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


def test_normalize_recovery_dataplane_probe_result_redacts_raw_target() -> None:
    result = normalize_recovery_dataplane_probe_result(
        {
            "status": "ok",
            "latency_ms": 0.5,
            "target": "10.0.0.7",
            "evidence": {
                "source_agents": ["real-network-adapter"],
                "event_ids": ["evt-1"],
                "events_total": 1,
                "claim_boundary": "bounded ping evidence only",
                "redacted": True,
            },
        }
    )

    assert result["dataplane_confirmed"] is True
    assert result["raw_target_redacted"] is True
    assert result["evidence"]["source_agents"] == ["real-network-adapter"]
    assert result["evidence"]["event_ids"] == ["evt-1"]
    assert result["claim_gate"] == {
        "schema": "x0tta6bl4.recovery_dataplane_probe.claim_gate.v1",
        "decision": "BOUNDED_DATAPLANE_PROBE_CLAIM_ALLOWED",
        "bounded_dataplane_probe_claim_allowed": True,
        "dataplane_confirmed": True,
        "eventbus_evidence_present": True,
        "source_agent_present": True,
        "evidence_redacted": True,
        "restored_dataplane_claim_allowed": False,
        "traffic_delivery_claim_allowed": False,
        "customer_traffic_claim_allowed": False,
        "production_slo_claim_allowed": False,
        "production_readiness_claim_allowed": False,
        "blockers": [],
        "claim_boundary": (
            "Recovery dataplane probe adapter metadata only. It normalizes an "
            "existing bounded dataplane probe result into redacted EventBus "
            "evidence references for recovery claim gates; it does not expose "
            "raw targets or prove customer traffic."
        ),
        "redacted": True,
    }
    assert "10.0.0.7" not in json.dumps(result, sort_keys=True)


def test_normalize_recovery_dataplane_probe_result_blocks_overclaim_without_event_evidence(
) -> None:
    result = normalize_recovery_dataplane_probe_result(
        {
            "status": "ok",
            "latency_ms": 0.5,
            "evidence": {
                "source_agents": [],
                "event_ids": [],
                "events_total": 0,
                "redacted": True,
            },
        }
    )

    gate = result["claim_gate"]
    assert result["dataplane_confirmed"] is True
    assert gate["bounded_dataplane_probe_claim_allowed"] is False
    assert gate["restored_dataplane_claim_allowed"] is False
    assert gate["customer_traffic_claim_allowed"] is False
    assert gate["production_readiness_claim_allowed"] is False
    assert "dataplane_probe_event_evidence_missing" in gate["blockers"]
    assert "dataplane_probe_source_agent_missing" in gate["blockers"]


def test_recovery_dataplane_ping_probe_runs_async_shared_probe(tmp_path) -> None:
    calls: list[dict[str, object]] = []

    async def fake_probe(target: str, **kwargs):
        calls.append({"target": target, **kwargs})
        return {
            "status": "ok",
            "latency_ms": 1.1,
            "packet_loss_percent": 0.0,
            "evidence": {
                "source_agents": ["real-network-adapter"],
                "event_ids": ["evt-ping-1"],
                "events_total": 1,
                "claim_boundary": "bounded ping evidence only",
                "redacted": True,
            },
        }

    bus = EventBus(project_root=str(tmp_path))
    probe = build_recovery_dataplane_ping_probe(
        "10.0.0.7",
        event_bus=bus,
        event_project_root=str(tmp_path),
        count=1,
        timeout_seconds=1,
        probe_func=fake_probe,
    )

    result = probe()

    assert result["status"] == "ok"
    assert result["dataplane_confirmed"] is True
    assert result["claim_gate"]["bounded_dataplane_probe_claim_allowed"] is True
    assert result["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert result["evidence"]["event_ids"] == ["evt-ping-1"]
    assert calls[0]["event_bus"] is bus
    assert calls[0]["event_project_root"] == str(tmp_path)
    assert calls[0]["count"] == 1
    assert calls[0]["timeout_seconds"] == 1
    assert "10.0.0.7" not in json.dumps(result, sort_keys=True)


def test_recovery_orchestrator_accepts_shared_probe_adapter(tmp_path) -> None:
    async def fake_probe(_target: str, **_kwargs):
        return {
            "status": "ok",
            "latency_ms": 1.1,
            "packet_loss_percent": 0.0,
            "evidence": {
                "source_agents": ["real-network-adapter"],
                "event_ids": ["evt-ping-1"],
                "events_total": 1,
                "claim_boundary": "bounded ping evidence only",
                "redacted": True,
            },
        }

    clock = FakeClock()
    bus = EventBus(project_root=str(tmp_path))
    state_mock = Mock(side_effect=[degraded_state(), healthy_state()])
    restart_mock = Mock(return_value=0)
    dataplane_probe = build_recovery_dataplane_ping_probe(
        "10.0.0.7",
        event_bus=bus,
        event_project_root=str(tmp_path),
        probe_func=fake_probe,
    )
    orchestrator = MeshRecoveryOrchestrator(
        node_id="node-uuid-4444-8888",
        local_audit_secret="local-node-audit-salt",
        policy_manager=RecoveryPolicyManager(cooldown_seconds=600, clock=clock),
        restart_action=restart_mock,
        get_node_state=state_mock,
        dataplane_probe=dataplane_probe,
        event_bus=bus,
        sleeper=lambda seconds: clock.advance(seconds),
        clock=clock,
    )

    evidence = orchestrator.run_recovery_flow(
        incident_id="inc-01",
        incident_key="incident-vpn-loss",
    )

    revalidation = evidence.post_action_dataplane_revalidation
    assert revalidation is not None
    assert revalidation.dataplane_confirmed is True
    assert revalidation.restored_dataplane_claim_allowed is True
    assert revalidation.customer_traffic_claim_allowed is False
    assert revalidation.evidence.source_agents == ["real-network-adapter"]
    assert revalidation.evidence.event_ids == ["evt-ping-1"]
    assert evidence.escalation_required is False
