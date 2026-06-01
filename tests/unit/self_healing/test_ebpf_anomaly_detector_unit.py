import importlib
import os
from unittest.mock import MagicMock

import pytest

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

_MODULE = None


def _import_module():
    global _MODULE
    if _MODULE is not None:
        return _MODULE
    try:
        _MODULE = importlib.import_module("src.self_healing.ebpf_anomaly_detector")
        return _MODULE
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")


def _make_loader():
    loader = MagicMock()
    loader.cleanup = MagicMock()
    loader.load_programs = MagicMock()
    return loader


def _make_executor(tmp_path, **kwargs):
    mod = _import_module()
    kwargs.setdefault(
        "safe_actuator",
        SafeActuator(lambda _action, _context: SafeActuatorResult(success=True)),
    )
    return mod.EBPFExecutor(
        _make_loader(),
        event_bus=EventBus(str(tmp_path)),
        node_id="ebpf-node-1",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/ebpf-self-healing",
        did="did:mesh:ebpf:test",
        wallet_address="0xebpf",
        **kwargs,
    )


def test_import_smoke():
    mod = _import_module()
    assert mod is not None


def test_executor_publishes_events_with_identity(tmp_path):
    executor = _make_executor(tmp_path)
    action = {
        "action": "adjust_route_weights",
        "interface": "eth0",
        "priority": "MEDIUM",
        "api_token": "secret",
    }

    assert executor.execute(action) is True

    events = executor.event_bus.get_event_history(
        source_agent="ebpf-self-healing",
        limit=10,
    )
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ]
    payload = completed[-1].data
    assert payload["node_id"] == "ebpf-node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/ebpf-self-healing"
    assert payload["did"] == "did:mesh:ebpf:test"
    assert payload["wallet_address"] == "0xebpf"
    assert payload["resource"] == "self_healing:ebpf:adjust_route_weights"
    assert payload["context"]["api_token"] == "<redacted>"
    assert payload["claim_boundary"]
    assert payload["claim_gate"]["schema"] == (
        "x0tta6bl4.self_healing.ebpf_recovery_claim_gate.v1"
    )
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["claim_gate"]["schema"] == (
        "x0tta6bl4.self_healing.ebpf.safe_actuator_claim_gate.v1"
    )
    assert metadata["claim_gate"]["local_ebpf_recovery_action_succeeded"] is True
    assert metadata["claim_gate"]["safe_actuator_result_recorded"] is True
    assert metadata["claim_gate"]["redacted"] is True
    assert metadata["claim_gate"]["restored_dataplane_claim_allowed"] is False
    assert metadata["claim_gate"]["route_convergence_claim_allowed"] is False
    assert metadata["claim_gate"]["kernel_forwarding_correctness_claim_allowed"] is False
    assert metadata["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert metadata["claim_gate"]["production_readiness_claim_allowed"] is False
    assert "restored dataplane" in metadata["claim_boundary"]
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True
    assert metadata["evidence"]["resource"] == "self_healing:ebpf:adjust_route_weights"
    assert payload["claim_gate"]["claim_allowed"] == {
        "local_ebpf_recovery_lifecycle": True,
        "local_safe_actuator_success": True,
        "restored_dataplane": False,
        "route_convergence": False,
        "kernel_forwarding_correctness": False,
        "dataplane_delivery": False,
        "traffic_delivery": False,
        "live_customer_traffic": False,
        "external_dpi_bypass": False,
        "settlement_finality": False,
        "production_readiness": False,
    }
    assert payload["restored_dataplane_claim_allowed"] is False
    assert payload["route_convergence_claim_allowed"] is False
    assert payload["kernel_forwarding_correctness_claim_allowed"] is False
    assert payload["dataplane_delivery_claim_allowed"] is False
    assert payload["traffic_delivery_claim_allowed"] is False
    assert payload["production_readiness_claim_allowed"] is False


def test_executor_policy_denied_blocks_safe_actuator(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)

    def _must_not_execute(_action, _context):
        raise AssertionError("policy denied eBPF action should not reach actuator")

    executor = _make_executor(
        tmp_path,
        policy_engine=policy,
        require_policy=True,
        safe_actuator=SafeActuator(_must_not_execute),
    )

    assert executor.execute({"action": "adjust_route_weights", "interface": "eth0"}) is False

    blocked = executor.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="ebpf-self-healing",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["resource"] == "self_healing:ebpf:adjust_route_weights"
    assert blocked[-1].data["policy_allowed"] is False


def test_executor_policy_allow_continues_through_safe_actuator(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-ebpf-route-weights",
            name="Allow eBPF route adjustment",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/ebpf-self-healing",
            allowed_resources=["self_healing:ebpf:adjust_route_weights"],
            priority=1000,
        )
    )
    executor = _make_executor(
        tmp_path,
        policy_engine=policy,
        require_policy=True,
    )

    assert executor.execute({"action": "adjust_route_weights", "interface": "eth0"}) is True

    completed = executor.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ebpf-self-healing",
    )
    assert completed[-1].data["policy_allowed"] is True
    assert completed[-1].data["matched_rules"] == ["allow-ebpf-route-weights"]


def test_executor_simulated_safe_actuator_fails_closed(tmp_path):
    executor = _make_executor(
        tmp_path,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )

    assert executor.execute({"action": "adjust_route_weights", "interface": "eth0"}) is False

    failed = executor.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="ebpf-self-healing",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["success"] is False
    assert failed[-1].data["result"]["simulated"] is True
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    assert metadata["claim_gate"]["safe_actuator_result_recorded"] is True
    assert metadata["claim_gate"]["local_ebpf_recovery_action_succeeded"] is False
    assert metadata["claim_gate"]["production_readiness_claim_allowed"] is False


def test_internal_adjust_routes_flushes_route_cache(tmp_path):
    executor = _make_executor(tmp_path)
    executor._interface_exists = MagicMock(return_value=True)
    executor._run_command = MagicMock(return_value=True)

    assert executor._adjust_routes("eth0") is True

    executor._run_command.assert_called_once_with(["ip", "route", "flush", "cache"])


def test_internal_adjust_routes_fails_closed_for_missing_interface(tmp_path):
    executor = _make_executor(tmp_path)
    executor._interface_exists = MagicMock(return_value=False)
    executor._run_command = MagicMock(return_value=True)

    assert executor._adjust_routes("missing0") is False

    executor._run_command.assert_not_called()


def test_internal_enable_hw_offload_uses_ethtool(tmp_path):
    executor = _make_executor(tmp_path)
    executor._interface_exists = MagicMock(return_value=True)
    executor._run_command = MagicMock(return_value=True)

    assert executor._enable_hw_offload("eth0") is True

    executor._run_command.assert_called_once_with(
        ["ethtool", "-K", "eth0", "tso", "on", "gso", "on", "gro", "on"]
    )


def test_internal_throttle_traffic_uses_configured_tbf(tmp_path, monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_EBPF_THROTTLE_RATE", "25mbit")
    monkeypatch.setenv("X0TTA6BL4_EBPF_THROTTLE_BURST", "16kbit")
    monkeypatch.setenv("X0TTA6BL4_EBPF_THROTTLE_LATENCY", "250ms")
    executor = _make_executor(tmp_path)
    executor._interface_exists = MagicMock(return_value=True)
    executor._run_command = MagicMock(return_value=True)

    assert executor._throttle_traffic("eth0") is True

    executor._run_command.assert_called_once_with(
        [
            "tc",
            "qdisc",
            "replace",
            "dev",
            "eth0",
            "root",
            "tbf",
            "rate",
            "25mbit",
            "burst",
            "16kbit",
            "latency",
            "250ms",
        ]
    )
