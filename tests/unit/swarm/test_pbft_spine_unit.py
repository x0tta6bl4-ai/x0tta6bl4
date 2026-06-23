from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.swarm.pbft import PBFTMessage, PBFTNode, PBFTPhase


def _make_entry(node):
    entry = node._get_or_create_entry(1)
    entry.phase = PBFTPhase.PREPARE
    entry.digest = "test-digest"
    entry.pre_prepare_msg = PBFTMessage(
        msg_type="pre_prepare",
        view=0,
        sequence=1,
        digest="test-digest",
        sender_id="node-1",
        request={
            "operation": {
                "type": "scale",
                "api_token": "secret-token",
            }
        },
    )
    return entry


def _make_node(tmp_path, **kwargs):
    return PBFTNode(
        node_id="node-1",
        peers={"node-2", "node-3", "node-4"},
        f=1,
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/swarm-pbft",
        did="did:mesh:swarm:test",
        wallet_address="0xswarm",
        **kwargs,
    )


def test_pbft_execute_publishes_events_with_identity(tmp_path):
    node = _make_node(tmp_path)
    node.set_callbacks(on_execute=lambda op: {"status": "done", "operation": op})
    entry = _make_entry(node)

    node._execute(entry)

    assert entry.executed is True
    assert entry.result["status"] == "done"
    events = node.event_bus.get_event_history(
        source_agent="swarm-pbft",
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
    assert payload["node_id"] == "node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/swarm-pbft"
    assert payload["did"] == "did:mesh:swarm:test"
    assert payload["wallet_address"] == "0xswarm"
    assert payload["resource"] == "swarm:pbft:execute"
    assert payload["context"]["operation"]["api_token"] == "<redacted>"
    assert payload["claim_boundary"]


def test_pbft_policy_denied_blocks_execution_callback(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    node = _make_node(tmp_path, policy_engine=policy, require_policy=True)
    called = []
    node.set_callbacks(on_execute=lambda op: called.append(op))
    entry = _make_entry(node)

    node._execute(entry)

    assert called == []
    assert entry.executed is True
    assert entry.result["success"] is False
    assert "No rules matched" in entry.result["error"]
    blocked = node.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="swarm-pbft",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["resource"] == "swarm:pbft:execute"
    assert blocked[-1].data["policy_allowed"] is False


def test_pbft_policy_allow_executes_callback(tmp_path):
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-pbft-execute",
            name="Allow PBFT execution",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/swarm-pbft",
            allowed_resources=["swarm:pbft:execute"],
            priority=1000,
        )
    )
    node = _make_node(tmp_path, policy_engine=policy, require_policy=True)
    node.set_callbacks(on_execute=lambda op: {"status": "executed", "operation": op})
    entry = _make_entry(node)

    node._execute(entry)

    assert entry.result["status"] == "executed"
    completed = node.event_bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="swarm-pbft",
    )
    assert completed[-1].data["policy_allowed"] is True
    assert completed[-1].data["matched_rules"] == ["allow-pbft-execute"]


def test_pbft_simulated_safe_actuator_fails_closed(tmp_path):
    node = _make_node(
        tmp_path,
        safe_actuator=SafeActuator(
            lambda _action, _context: SafeActuatorResult(
                success=True,
                reason="dry run",
                simulated=True,
            )
        ),
    )
    node.set_callbacks(on_execute=lambda op: {"status": "should-not-be-result"})
    entry = _make_entry(node)

    node._execute(entry)

    assert entry.executed is True
    assert entry.result["success"] is False
    assert entry.result["simulated"] is True
    failed = node.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="swarm-pbft",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["success"] is False
