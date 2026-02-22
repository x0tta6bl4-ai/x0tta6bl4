"""Focused unit coverage for remaining swarm/mesh/federated modules."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

consensus_integration = pytest.importorskip("src.swarm.consensus_integration")
paxos = pytest.importorskip("src.swarm.paxos")
pbft = pytest.importorskip("src.swarm.pbft")
ygg = pytest.importorskip("src.mesh.yggdrasil_optimizer")
lora_fl = pytest.importorskip("src.federated_learning.lora_fl_integration")


def test_lora_weight_update_conversion_and_aggregation(tmp_path):
    u1 = lora_fl.create_lora_update(
        node_id="n1",
        round_number=1,
        lora_weights={"layer1": {"lora_A": [1.0, 2.0], "lora_B": [3.0, 4.0]}},
        num_samples=10,
        training_loss=0.2,
    )
    u2 = lora_fl.create_lora_update(
        node_id="n2",
        round_number=1,
        lora_weights={"layer1": {"lora_A": [2.0, 4.0], "lora_B": [6.0, 8.0]}},
        num_samples=30,
        training_loss=0.1,
    )

    model_update = u1.to_model_update()
    restored = lora_fl.LoRAWeightUpdate.from_model_update(model_update)
    assert restored.node_id == "n1"
    assert "layer1" in restored.lora_weights

    aggregator = lora_fl.LoRAWeightAggregator(aggregation_method="fedavg", clip_norm=0.0)
    weights, result = aggregator.aggregate([u1, u2])
    assert result.success is True
    assert result.updates_received == 2
    assert "layer1" in weights
    assert pytest.approx(weights["layer1"]["lora_A"][0], rel=1e-6) == 1.75

    weights2, result2 = lora_fl.aggregate_lora_weights([u1, u2], clip_norm=0.0)
    assert result2.success is True
    assert "layer1" in weights2

    cfg = lora_fl.FederatedLoRAConfig(adapter_storage_path=tmp_path)
    assert isinstance(cfg.adapter_storage_path, Path)
    assert cfg.lora_config is not None


def test_yggdrasil_optimizer_predictor_and_reports():
    config = ygg.OptimizationConfig(min_samples=1, max_alternative_routes=5, route_timeout_seconds=1)
    optimizer = ygg.YggdrasilOptimizer(config)

    route_a = ygg.RouteMetrics(
        route_id="r-a",
        destination="dest-1",
        next_hop="hop-a",
        latency_ms=12.0,
        packet_loss=0.05,
        bandwidth_mbps=90.0,
        hop_count=1,
    )
    route_b = ygg.RouteMetrics(
        route_id="r-b",
        destination="dest-1",
        next_hop="hop-b",
        latency_ms=250.0,
        packet_loss=12.0,
        bandwidth_mbps=10.0,
        hop_count=3,
    )
    route_a.compute_scores()
    route_b.compute_scores()
    assert route_a.classify_quality() in {ygg.RouteQuality.EXCELLENT, ygg.RouteQuality.GOOD}
    assert route_b.classify_quality() == ygg.RouteQuality.CRITICAL

    callback_calls = {"count": 0}
    optimizer.add_optimization_callback(lambda _: callback_calls.__setitem__("count", callback_calls["count"] + 1))

    optimizer.register_route(route_a)
    optimizer.register_route(route_b)
    optimizer.update_route_metrics("r-a", latency_ms=15.0, packet_loss=0.1, bandwidth_mbps=100.0, jitter_ms=1.0)
    optimizer.update_route_metrics("r-b", latency_ms=300.0, packet_loss=20.0, bandwidth_mbps=5.0, jitter_ms=40.0)

    assert optimizer.predict_latency("r-a") is not None
    assert optimizer.get_prediction_confidence("r-a") >= 0.0

    best = optimizer.select_best_route("dest-1")
    assert best is not None
    alternatives = optimizer.get_alternative_routes("dest-1")
    assert len(alternatives) >= 1

    # Mark one route stale to trigger refresh recommendation.
    route_b.last_updated = datetime.utcnow() - timedelta(seconds=10)
    result = optimizer.optimize_routes()
    assert result["total_routes"] == 2
    assert callback_calls["count"] >= 1
    assert result["recommendations"]

    report = optimizer.get_route_report("dest-1")
    assert report["total_routes"] == 2
    optimizer.stop_monitoring()


@pytest.mark.asyncio
async def test_paxos_pbft_and_consensus_integration_basics(monkeypatch):
    # Paxos primitives.
    p1 = paxos.ProposalNumber(1, "a")
    p2 = paxos.ProposalNumber(2, "a")
    assert p1 < p2
    assert paxos.ProposalNumber.from_dict(p1.to_dict()) == p1

    msg = paxos.PaxosMessage("prepare", p1, "inst-1", "a", value={"x": 1})
    assert msg.to_dict()["type"] == "prepare"

    node = paxos.PaxosNode(node_id="a", peers=set())
    instance = node._get_or_create_instance("inst-1")
    instance.promise_values = {
        "n1": (paxos.ProposalNumber(1, "n1"), "v1"),
        "n2": (paxos.ProposalNumber(3, "n2"), "v2"),
    }
    assert node._get_value_from_promises(instance) == "v2"

    node._handle_promise(
        {
            "type": "promise",
            "proposal_number": p1.to_dict(),
            "instance_id": "inst-2",
            "sender_id": "n9",
            "value": None,
        }
    )
    node._handle_accepted(
        {
            "type": "accepted",
            "proposal_number": p1.to_dict(),
            "instance_id": "inst-2",
            "sender_id": "n9",
            "value": "x",
        }
    )
    tracked = node.get_instance("inst-2")
    assert "n9" in tracked.promises_received
    assert "n9" in tracked.accepts_received

    multi = paxos.MultiPaxos(node_id="a", peers=set(), leader_id="b")
    success, value = await multi.propose("ignored")
    assert success is False and value is None
    assert multi.get_log_entry(0) is None

    # PBFT primitives.
    req = pbft.PBFTRequest(client_id="client-1", timestamp=1, operation={"op": "set"})
    digest = req.compute_digest()
    assert len(digest) == 32

    pbft_msg = pbft.PBFTMessage(
        msg_type="prepare",
        view=0,
        sequence=1,
        digest=digest,
        sender_id="n1",
    )
    assert len(pbft_msg.compute_digest()) == 16
    assert pbft_msg.to_dict()["type"] == "prepare"

    pbft_node = pbft.PBFTNode(node_id="n1", peers={"n2", "n3", "n4"}, f=1)
    old_view = pbft_node.view
    pbft_node.start_view_change()
    assert pbft_node.view == old_view + 1
    entry = pbft_node._get_or_create_entry(1)
    assert entry.view == pbft_node.view
    entry.executed = True
    assert pbft_node.get_executed() == [1]

    # Consensus integration simple/weighted decisions.
    manager = consensus_integration.SwarmConsensusManager(
        node_id="a1",
        default_mode=consensus_integration.ConsensusMode.SIMPLE,
    )
    manager.add_agent(consensus_integration.AgentInfo(agent_id="a1", name="A1", capabilities={"routing"}, weight=1.0))
    manager.add_agent(consensus_integration.AgentInfo(agent_id="a2", name="A2", capabilities={"routing"}, weight=2.0))

    captured = []
    manager.set_callbacks(on_decision=lambda d: captured.append(d.decision_id))

    monkeypatch.setattr("random.choice", lambda seq: seq[0])
    d1 = await manager.decide("routing", ["p1", "p2"], mode=consensus_integration.ConsensusMode.SIMPLE)
    d2 = await manager.decide("routing", ["p1", "p2"], mode=consensus_integration.ConsensusMode.WEIGHTED)

    assert d1.success is True and d1.winner == "p1"
    assert d2.success is True and d2.winner == "p1"
    assert len(captured) == 2

    weighted_vote = consensus_integration.WeightedVote(voter_id="a1", choice="p1", weight=1.5)
    assert weighted_vote.to_dict()["weight"] == 1.5
    assert manager.get_stats()["total_decisions"] == 2
