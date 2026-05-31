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
    socket_path.write_text("", encoding="utf-8")
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
        return SPIREAgentManager(
            config_path=config_path,
            socket_path=socket_path,
            **kwargs,
        )


def test_start_agent_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    manager = _manager(tmp_path)
    process = MagicMock()
    process.pid = 4242
    process.poll.return_value = None

    with patch("src.security.spiffe.agent.manager.subprocess.Popen", return_value=process) as popen:
        result = manager.start()

    assert result is True
    popen.assert_called_once()
    events = manager.event_bus.get_event_history(source_agent="spire-agent-manager")
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages
    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "node-spire-1"
    assert payload["spiffe_id"] == SPIFFE_ID
    assert payload["did"] == "did:mesh:identity:spire-agent-manager"
    assert payload["wallet_address"] == "0xspire"
    assert payload["resource"] == "identity:spire_agent:start_agent"
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    assert payload["claim_boundary"]


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
