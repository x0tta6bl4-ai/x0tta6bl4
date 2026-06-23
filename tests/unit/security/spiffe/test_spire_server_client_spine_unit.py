from types import SimpleNamespace
from unittest.mock import patch

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.spiffe.server.client import SPIREServerClient
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule


SPIFFE_ID = "spiffe://x0tta6bl4.mesh/workload/spire-server-client"


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


def _client(tmp_path, **overrides):
    kwargs = {
        "event_bus": EventBus(str(tmp_path)),
        "policy_engine": _allow_policy("identity:spire_server:create_entry"),
        "require_policy": True,
        "source_agent": "spire-server-client",
        "node_id": "node-spire-server-1",
        "spiffe_id": SPIFFE_ID,
        "did": "did:mesh:identity:spire-server-client",
        "wallet_address": "0xspireserver",
    }
    kwargs.update(overrides)
    return SPIREServerClient(spire_server_bin="spire-server", **kwargs)


def test_create_entry_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    client = _client(tmp_path)

    with patch(
        "src.security.spiffe.server.client.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout="Entry created: eid\n", stderr=""),
    ) as run:
        entry_id = client.create_entry(
            "spiffe://x0tta6bl4.mesh/workload/api",
            "spiffe://x0tta6bl4.mesh/node/worker-1",
            {"unix:uid": "1000"},
            ttl=60,
            admin=True,
        )

    assert entry_id == "eid"
    assert "-admin" in run.call_args.args[0]
    events = client.event_bus.get_event_history(source_agent="spire-server-client")
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages
    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "node-spire-server-1"
    assert payload["spiffe_id"] == SPIFFE_ID
    assert payload["did"] == "did:mesh:identity:spire-server-client"
    assert payload["wallet_address"] == "0xspireserver"
    assert payload["resource"] == "identity:spire_server:create_entry"
    assert payload["context"]["selectors"] == {"unix:uid": "1000"}
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True
    assert payload["claim_boundary"]


def test_delete_entry_policy_denial_blocks_spire_server_command(tmp_path):
    client = _client(
        tmp_path,
        policy_engine=PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False),
    )

    with patch("src.security.spiffe.server.client.subprocess.run") as run:
        result = client.delete_entry("entry-1")

    assert result is False
    run.assert_not_called()
    blocked = client.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="spire-server-client",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["policy_allowed"] is False
    assert blocked[-1].data["resource"] == "identity:spire_server:delete_entry"


def test_simulated_actuator_blocks_create_entry(tmp_path):
    client = _client(
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

    with patch("src.security.spiffe.server.client.subprocess.run") as run:
        result = client.create_entry(
            "spiffe://x0tta6bl4.mesh/workload/api",
            "spiffe://x0tta6bl4.mesh/node/worker-1",
            {"unix:uid": "1000"},
        )

    assert result is None
    run.assert_not_called()
    failed = client.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="spire-server-client",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["success"] is False
    assert failed[-1].data["simulated"] is True


def test_list_entries_runs_through_safe_actuator(tmp_path):
    client = _client(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_server:list_entries"),
    )
    output = """Entry ID: e1
SPIFFE ID: spiffe://x0tta6bl4.mesh/workload/api
Parent ID: spiffe://x0tta6bl4.mesh/node/worker-1
Selectors: unix:uid:1000
TTL: 60
Admin: false
"""

    with patch(
        "src.security.spiffe.server.client.subprocess.run",
        return_value=SimpleNamespace(returncode=0, stdout=output, stderr=""),
    ):
        entries = client.list_entries()

    assert len(entries) == 1
    assert entries[0].entry_id == "e1"
    completed = client.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="spire-server-client",
    )
    payload = completed[-1].data
    assert payload["stage"] == "actuator_completed"
    assert payload["resource"] == "identity:spire_server:list_entries"
    assert payload["policy_allowed"] is True
    assert payload["safe_actuator"] is True


def test_get_server_status_records_failed_health_without_losing_status(tmp_path):
    client = _client(
        tmp_path,
        policy_engine=_allow_policy("identity:spire_server:get_server_status"),
    )

    with patch(
        "src.security.spiffe.server.client.subprocess.run",
        return_value=SimpleNamespace(returncode=1, stdout="", stderr="not healthy"),
    ):
        status = client.get_server_status()

    assert status == {
        "healthy": False,
        "address": "127.0.0.1:8081",
        "output": "not healthy",
    }
    failed = client.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="spire-server-client",
    )
    assert failed[-1].data["stage"] == "actuator_failed"
    assert failed[-1].data["resource"] == "identity:spire_server:get_server_status"
