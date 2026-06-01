import pytest

from src.coordination.events import EventBus, EventType
from src.integration.spine import SafeActuatorResult
from src.security.zero_trust.policy_engine import PolicyAction, PolicyEngine, PolicyRule
from src.swarm.consensus_integration import ConsensusMode
from src.swarm.intelligence import (
    DecisionContext,
    DecisionResult,
    MAPEKIntegration,
    SwarmAction,
)


class FakeSwarm:
    node_id = "node-1"

    def __init__(self, approved=True):
        self.approved = approved
        self.actions = []

    async def propose_action(self, action):
        self.actions.append(action)
        return DecisionResult(
            decision_id="decision-1",
            approved=self.approved,
            context=DecisionContext(
                topic=action.action_type,
                description=action.description,
                data=action.parameters,
                priority=action.priority,
            ),
            consensus_mode=ConsensusMode.SIMPLE,
            latency_ms=1.0,
            reason="approved" if self.approved else "rejected by consensus",
        )


def _allow_policy():
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    policy.add_rule(
        PolicyRule(
            rule_id="allow-mapek-healing",
            name="Allow swarm MAPE-K healing",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://x0tta6bl4.mesh/workload/swarm-mapek",
            allowed_resources=["swarm:mapek:healing"],
            priority=1000,
        )
    )
    return policy


def _mapek(tmp_path, swarm=None, **kwargs):
    return MAPEKIntegration(
        swarm or FakeSwarm(),
        event_bus=EventBus(str(tmp_path)),
        spiffe_id="spiffe://x0tta6bl4.mesh/workload/swarm-mapek",
        did="did:mesh:swarm:mapek",
        wallet_address="0xmapek",
        **kwargs,
    )


def _healing_action():
    return SwarmAction(
        action_type="healing",
        description="Recover node",
        parameters={
            "node_id": "node-2",
            "api_token": "secret-token",
        },
        proposer_id="node-1",
    )


@pytest.mark.asyncio
async def test_mapek_execute_publishes_identity_policy_and_safe_actuator_events(tmp_path):
    swarm = FakeSwarm()
    mapek = _mapek(tmp_path, swarm=swarm, policy_engine=_allow_policy(), require_policy=True)

    result = await mapek.execute(_healing_action())

    assert result["success"] is True
    assert result["decision"]["approved"] is True
    assert result["safe_actuator"] is True
    assert len(swarm.actions) == 1

    events = mapek.event_bus.get_event_history(source_agent="swarm-mapek", limit=10)
    stages = [event.data["stage"] for event in events]
    assert "received" in stages
    assert "actuator_start" in stages
    assert "actuator_completed" in stages

    completed = [
        event for event in events
        if event.event_type == EventType.PIPELINE_STAGE_END
    ][-1]
    payload = completed.data
    assert payload["node_id"] == "node-1"
    assert payload["spiffe_id"] == "spiffe://x0tta6bl4.mesh/workload/swarm-mapek"
    assert payload["did"] == "did:mesh:swarm:mapek"
    assert payload["wallet_address"] == "0xmapek"
    assert payload["resource"] == "swarm:mapek:healing"
    assert payload["policy_allowed"] is True
    assert payload["matched_rules"] == ["allow-mapek-healing"]
    assert payload["safe_actuator"] is True
    assert payload["context"]["parameters"]["api_token"] == "<redacted>"
    assert payload["claim_boundary"]
    metadata = payload["safe_actuator_evidence_metadata"]
    assert metadata["schema"] == "x0tta6bl4.safe_actuator.evidence_metadata.v1"
    assert metadata["source_agents"] == ["swarm-mapek"]
    assert metadata["redacted"] is True
    claim_gate = metadata["claim_gate"]
    assert claim_gate["schema"] == "x0tta6bl4.swarm_mapek.safe_actuator_claim_gate.v1"
    assert claim_gate["safe_actuator_result_recorded"] is True
    assert claim_gate["local_swarm_action_observed_claim_allowed"] is True
    assert claim_gate["local_swarm_decision_result_claim_allowed"] is True
    assert claim_gate["cluster_wide_consensus_finality_claim_allowed"] is False
    assert claim_gate["production_action_applied_claim_allowed"] is False
    assert claim_gate["restored_dataplane_claim_allowed"] is False
    assert claim_gate["customer_traffic_restored_claim_allowed"] is False
    assert claim_gate["external_settlement_finality_claim_allowed"] is False
    assert claim_gate["production_readiness_claim_allowed"] is False
    cross_plane = metadata["cross_plane_claim_gate"]
    assert cross_plane["allowed"] is False
    evidence = metadata["evidence"]
    assert evidence["action_type"] == "healing"
    assert evidence["resource"] == "swarm:mapek:healing"
    assert evidence["action_resource"] == "healing"
    assert evidence["decision_result_present"] is True
    assert evidence["decision_approved"] is True
    assert evidence["consensus_mode"] == "simple"
    assert evidence["parameters_redacted"] is True
    assert evidence["identity_values_redacted"] is True
    assert evidence["raw_context_values_redacted"] is True
    assert evidence["raw_result_values_redacted"] is True
    assert "secret-token" not in str(metadata)
    assert result["safe_actuator_evidence_metadata"]["claim_gate"] == claim_gate


@pytest.mark.asyncio
async def test_mapek_policy_denied_blocks_swarm_action(tmp_path):
    swarm = FakeSwarm()
    policy = PolicyEngine(default_action=PolicyAction.DENY, enable_opa=False)
    mapek = _mapek(tmp_path, swarm=swarm, policy_engine=policy, require_policy=True)

    result = await mapek.execute(_healing_action())

    assert result["success"] is False
    assert "No rules matched" in result["error"]
    assert mapek._action_history[-1] == result
    assert swarm.actions == []
    blocked = mapek.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="swarm-mapek",
    )
    assert blocked[-1].data["stage"] == "policy_denied"
    assert blocked[-1].data["resource"] == "swarm:mapek:healing"
    assert blocked[-1].data["policy_allowed"] is False


@pytest.mark.asyncio
async def test_mapek_policy_engine_requires_spiffe_identity(tmp_path):
    swarm = FakeSwarm()
    mapek = MAPEKIntegration(
        swarm,
        event_bus=EventBus(str(tmp_path)),
        policy_engine=_allow_policy(),
    )
    mapek.identity["spiffe_id"] = ""

    result = await mapek.execute(_healing_action())

    assert result["success"] is False
    assert "SPIFFE identity is required" in result["error"]
    assert swarm.actions == []
    blocked = mapek.event_bus.get_event_history(
        event_type=EventType.TASK_BLOCKED,
        source_agent="swarm-mapek",
    )
    assert blocked[-1].data["policy_allowed"] is None


@pytest.mark.asyncio
async def test_mapek_simulated_safe_actuator_fails_closed(tmp_path):
    class SimulatedActuator:
        async def execute(self, _action_type, _context):
            return SafeActuatorResult(True, "dry run", simulated=True)

    swarm = FakeSwarm()
    mapek = _mapek(tmp_path, swarm=swarm, safe_actuator=SimulatedActuator())

    result = await mapek.execute(_healing_action())

    assert result["success"] is False
    assert result["simulated"] is True
    assert swarm.actions == []
    failed = mapek.event_bus.get_event_history(
        event_type=EventType.TASK_FAILED,
        source_agent="swarm-mapek",
    )
    assert failed[-1].data["stage"] == "actuator_simulated"
    assert failed[-1].data["success"] is False
    metadata = failed[-1].data["safe_actuator_evidence_metadata"]
    claim_gate = metadata["claim_gate"]
    assert claim_gate["local_swarm_action_observed_claim_allowed"] is True
    assert claim_gate["local_swarm_decision_result_claim_allowed"] is False
    assert "safe_actuator_result_simulated" in claim_gate["blockers"]
    assert metadata["cross_plane_claim_gate"]["allowed"] is False
