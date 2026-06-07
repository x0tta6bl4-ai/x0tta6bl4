import socket
from unittest.mock import MagicMock, patch

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.spiffe.agent.manager import (
    AttestationStrategy,
    SPIREAgentManager,
    WorkloadEntry,
)
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/spire-agent-manager"


def _allow_policy(resource: str):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id=f"allow-{resource}",
            name=f"Allow {resource}",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern=SPIFFE_ID,
            allowed_resources=[resource],
            priority=1000,
        )
    )
    return policy


def _manager(tmp_path, **overrides):
    config_path = tmp_path / "agent.conf"
    config_path.write_text("agent {}", encoding="utf-8")
    socket_path = tmp_path / "agent.sock"
    bound_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    bound_socket.bind(str(socket_path))
    kwargs = {
        "event_bus": EventBus(str(tmp_path)),
        "policy_engine": _allow_policy("identity:spire_agent:start_agent"),
        "require_policy": True,
        "source_agent": "spire-agent-manager",
        "node_id": "node-spire-1",
        "spiffe_id": SPIFFE_ID,
        "did": "did:mesh:identity:spire-agent-manager",
        "wallet_address": "0xspire",
    }
    kwargs.update(overrides)
    with patch(
        "src.security.spiffe.agent.manager.shutil.which",
        side_effect=lambda binary: f"/usr/bin/{binary}",
    ):
        manager = SPIREAgentManager(
            config_path=config_path,
            socket_path=socket_path,
            **kwargs,
        )
        manager._test_bound_socket = bound_socket
        return manager


def _metadata_dict(result):
    return result.evidence_metadata.to_dict()


def test_start_agent_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    manager = _manager(tmp_path)
    process = MagicMock()
    process.pid = 4242
    process.poll.return_value = None

    with patch(
        "src.security.spiffe.agent.manager.subprocess.Popen", return_value=process
    ) as popen:
        result = manager.start()

    assert result is True
    popen.assert_called_once()
    events = manager.event_bus.get_event_history(source_agent="spire-agent-manager")
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages
    completed = [
        event for event in events if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "node-spire-1"
    assert payload["spiffe_id"] == SPIFFE_ID
    assert payload["did"] == "did:mesh:identity:spire-agent-manager"
    assert payload["wallet_address"] == "0xspire"
    assert payload["resource"] == "identity:spire_agent:start_agent"
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    assert payload["thinking"]["profile"]["role"] == "security"
    assert "zero_trust_review" in payload["thinking"]["techniques"]
    assert (
        payload["last_thinking_context"]["applied"]["framing"]["problem"]
        == "spire_agent_control_action"
    )
    assert payload["claim_boundary"]
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.spire_agent.safe_actuator_claim_gate.v1"
    assert claim_gate["local_spire_agent_cli_action_succeeded"] is True
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["safe_actuator_simulated"] is False
    assert claim_gate["live_spire_mtls_claim_allowed"] is False
    assert claim_gate["workload_svid_possession_claim_allowed"] is False
    assert claim_gate["workload_identity_trust_finality_claim_allowed"] is False
    assert claim_gate["node_attestation_finality_claim_allowed"] is False
    assert claim_gate["dataplane_delivery_claim_allowed"] is False
    assert claim_gate["customer_traffic_claim_allowed"] is False
    assert claim_gate["production_identity_readiness_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert metadata["evidence"]["raw_command_output_redacted"] is True


def test_register_workload_policy_denial_blocks_spire_server_command(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
    )
    entry = WorkloadEntry(
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/api",
        parent_id="spiffe://x0tta6bl4.mesh/node/worker-1",
        selectors={"unix:uid": "1000"},
    )

    with patch("src.security.spiffe.agent.manager.subprocess.run") as run:
        result = manager.register_workload(entry)

    assert result is False
    run.assert_not_called()
    blocked = manager.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="spire-agent-manager",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False
    assert blocked[-1].data["resource"] == "identity:spire_agent:register_workload"
    metadata = blocked[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.spire_agent.safe_actuator_claim_gate.v1"
    assert claim_gate["operation"] == "register_workload"
    assert claim_gate["local_spire_agent_cli_action_succeeded"] is False
    assert claim_gate["live_spire_mtls_claim_allowed"] is False
    assert claim_gate["workload_svid_possession_claim_allowed"] is False
    assert claim_gate["node_attestation_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False


def test_join_token_attestation_redacts_token_in_event_payload(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_agent:attest_node"),
    )

    result = manager.attest_node(AttestationStrategy.JOIN_TOKEN, token="secret-token")

    assert result is True
    assert manager._join_token == "secret-token"
    completed = manager.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="spire-agent-manager",
    )
    payload = completed[-1].data
    assert payload["stage"] == "actuator_completed"
    assert payload["resource"] == "identity:spire_agent:attest_node"
    assert payload["context"]["token"] == "<redacted>"


def test_join_token_replay_is_blocked_before_attestation_action(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_agent:attest_node"),
    )

    first = manager.attest_node(AttestationStrategy.JOIN_TOKEN, token="secret-token")
    second = manager.attest_node(AttestationStrategy.JOIN_TOKEN, token="secret-token")

    assert first is True
    assert second is False
    blocked = manager.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="spire-agent-manager",
    )
    payload = blocked[-1].data
    assert payload["stage"] == "join_token_guard_blocked"
    assert payload["reason"] == "join_token_replay_detected"
    assert payload["context"]["token"] == "<redacted>"
    assert (
        payload["last_thinking_context"]["applied"]["framing"]["problem"]
        == "spire_agent_control_action"
    )
    assert "secret-token" not in str(payload)


def test_simulated_actuator_blocks_agent_start(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=None,
        require_policy=False,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )

    with patch("src.security.spiffe.agent.manager.subprocess.Popen") as popen:
        result = manager.start()

    assert result is False
    popen.assert_not_called()
    failed = manager.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="spire-agent-manager",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["success"] is False
    assert failed[-1].data["simulated"] is True
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.spire_agent.safe_actuator_claim_gate.v1"
    assert claim_gate["local_spire_agent_cli_action_succeeded"] is False
    assert claim_gate["safe_actuator_simulated"] is True
    assert claim_gate["live_spire_mtls_claim_allowed"] is False
    assert claim_gate["node_attestation_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False


def test_stop_agent_runs_through_safe_actuator(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_agent:stop_agent"),
    )
    process = MagicMock()
    process.pid = 31337
    process.poll.side_effect = [None, 0]
    manager.agent_process = process

    with patch("src.security.spiffe.agent.manager.os.getpgid", return_value=31337):
        with patch("src.security.spiffe.agent.manager.os.killpg") as killpg:
            result = manager.stop()

    assert result is True
    killpg.assert_called_once()
    completed = manager.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="spire-agent-manager",
    )
    payload = completed[-1].data
    assert payload["stage"] == "actuator_completed"
    assert payload["resource"] == "identity:spire_agent:stop_agent"
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True


def test_attest_join_token_internal_result_carries_bounded_metadata(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_agent:attest_node"),
    )

    result = manager._attest_join_token_internal(
        "secret-token",
        agent_running=False,
        operation="attest_node",
        context={"agent_running": False, "token": "secret-token"},
    )

    assert result.success is True
    metadata = _metadata_dict(result)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.spire_agent.safe_actuator_claim_gate.v1"
    assert claim_gate["operation"] == "attest_node"
    assert claim_gate["local_spire_agent_cli_action_succeeded"] is True
    assert claim_gate["workload_svid_possession_claim_allowed"] is False
    assert claim_gate["node_attestation_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    assert metadata["evidence"]["context_keys"] == ["agent_running", "token"]
    assert metadata["evidence"]["raw_context_values_redacted"] is True
    assert "secret-token" not in str(metadata)


def test_register_workload_internal_failure_result_carries_bounded_metadata(tmp_path):
    manager = _manager(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_agent:register_workload"),
    )
    entry = WorkloadEntry(
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/secret-api",
        parent_id="spiffe://x0tta6bl4.mesh/node/secret-worker",
        selectors={"unix:uid": "1000"},
    )

    with patch(
        "src.security.spiffe.agent.manager.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        result = manager._register_workload_internal(
            entry,
            operation="register_workload",
            context={
                "spiffe_id": entry.spiffe_id,
                "parent_id": entry.parent_id,
                "selectors": dict(entry.selectors),
                "ttl": entry.ttl,
            },
        )

    assert result.success is False
    metadata = _metadata_dict(result)
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.spire_agent.safe_actuator_claim_gate.v1"
    assert claim_gate["operation"] == "register_workload"
    assert claim_gate["local_spire_agent_cli_action_succeeded"] is False
    assert claim_gate["live_spire_mtls_claim_allowed"] is False
    assert claim_gate["workload_identity_trust_finality_claim_allowed"] is False
    assert claim_gate["production_identity_readiness_claim_allowed"] is False
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
    assert metadata["evidence"]["context_keys"] == [
        "parent_id",
        "selectors",
        "spiffe_id",
        "ttl",
    ]
    assert metadata["evidence"]["raw_command_output_redacted"] is True
    assert "secret-api" not in str(metadata)
    assert "secret-worker" not in str(metadata)
