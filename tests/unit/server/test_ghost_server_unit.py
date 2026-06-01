from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.server.ghost_server import GhostL3Server, _load_master_key_from_env


def _make_server(tmp_path, **kwargs):
    return GhostL3Server(
        master_key=b"0" * 32,
        event_bus=EventBus(str(tmp_path)),
        node_id="ghost-node-1",
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/ghost-l3-server",
        did="did:mesh:ghost:test",
        wallet_address="0xghost",
        **kwargs,
    )


def _patch_runtime_setup(server):
    return (
        patch("src.server.ghost_server.os.open", return_value=42),
        patch("src.server.ghost_server.fcntl.ioctl", return_value=0),
        patch("src.server.ghost_server.subprocess.run", return_value=MagicMock(returncode=0)),
        patch.object(server, "_enable_ip_forward", return_value=None),
    )


def _clear_master_key_env(monkeypatch):
    monkeypatch.delenv("GHOST_L3_MASTER_KEY_HEX", raising=False)
    monkeypatch.delenv("GHOST_L3_MASTER_KEY_B64", raising=False)
    monkeypatch.delenv("GHOST_L3_MASTER_KEY", raising=False)


def test_missing_master_key_fails_closed(monkeypatch):
    _clear_master_key_env(monkeypatch)

    with pytest.raises(RuntimeError, match="master key is required"):
        GhostL3Server(event_bus=None)


def test_load_master_key_from_hex_env(monkeypatch):
    _clear_master_key_env(monkeypatch)
    monkeypatch.setenv("GHOST_L3_MASTER_KEY_HEX", "41" * 32)

    assert _load_master_key_from_env() == b"A" * 32


def test_invalid_env_master_key_length_is_rejected(monkeypatch):
    _clear_master_key_env(monkeypatch)
    monkeypatch.setenv("GHOST_L3_MASTER_KEY_HEX", "41")

    with pytest.raises(ValueError, match="64 hex characters"):
        _load_master_key_from_env()


def test_setup_tun_publishes_events_with_identity(tmp_path):
    server = _make_server(tmp_path)

    with ExitStack() as stack:
        for item in _patch_runtime_setup(server):
            stack.enter_context(item)
        assert server.setup_tun() is True

    events = server.event_bus.get_event_history(
        source_agent="ghost-l3-server",
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
    assert payload["node_id"] == "ghost-node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/ghost-l3-server"
    assert payload["did"] == "did:mesh:ghost:test"
    assert payload["wallet_address"] == "0xghost"
    assert payload["resource"] == "server:ghost_l3:setup_tun"
    assert payload["context"]["tun_name"] == "x0t-srv0"
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.ghost_l3.safe_actuator_claim_gate.v1"
    assert claim_gate["local_tun_nat_setup_claim_allowed"] is True
    assert claim_gate["restored_dataplane_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["kernel_forwarding_correctness_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert payload["claim_gate"] == claim_gate
    assert payload["claim_boundary"]


def test_setup_tun_policy_denied_blocks_safe_actuator(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)

    def _must_not_execute(_action, _context):
        raise AssertionError("policy denied Ghost L3 setup should not reach actuator")

    server = _make_server(
        tmp_path,
        policy_engine=policy,
        require_policy=True,
        safe_actuator=SafeActuator(_must_not_execute),
    )

    assert server.setup_tun() is False

    blocked = server.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="ghost-l3-server",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["resource"] == "server:ghost_l3:setup_tun"
    assert blocked[-1].data["policy_allowed"] is False


def test_setup_tun_policy_allow_continues_to_safe_actuator(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-ghost-l3-setup",
            name="Allow Ghost L3 setup",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/ghost-l3-server",
            allowed_resources=["server:ghost_l3:setup_tun"],
            priority=1000,
        )
    )
    server = _make_server(
        tmp_path,
        policy_engine=policy,
        require_policy=True,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(True)
        ),
    )

    assert server.setup_tun() is True

    completed = server.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="ghost-l3-server",
    )
    assert completed[-1].data["policy_allowed"] is True
    assert completed[-1].data["matched_rules"] == ["allow-ghost-l3-setup"]
    assert completed[-1].data["safe_actuator_evidence_metadata"]["claim_gate"][
        "production_readiness_claim_allowed"
    ] is False


def test_setup_tun_simulated_safe_actuator_fails_closed(tmp_path):
    server = _make_server(
        tmp_path,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )

    assert server.setup_tun() is False

    failed = server.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="ghost-l3-server",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["success"] is False
    assert failed[-1].data["result"]["simulated"] is True
    claim_gate = failed[-1].data["safe_actuator_evidence_metadata"]["claim_gate"]
    assert claim_gate["local_tun_nat_setup_claim_allowed"] is False
    assert claim_gate["safe_actuator_result_simulated"] is True
    assert "safe_actuator_result_simulated" in claim_gate["blockers"]
    assert claim_gate["production_readiness_claim_allowed"] is False
