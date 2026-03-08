"""Unit tests for src/api/maas/mesh_instance.py."""

from datetime import datetime, timedelta

import pytest

from src.api.maas.mesh_instance import MeshInstance


@pytest.mark.asyncio
async def test_provision_sets_active_and_creates_nodes():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=3)
    await inst.provision()

    assert inst.status == "active"
    assert len(inst.node_instances) == 3
    assert inst.target_nodes == 3


@pytest.mark.asyncio
async def test_scale_down_keeps_at_least_one_node():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=2)
    await inst.provision()

    new_total = inst.scale("scale_down", 999)
    assert new_total == 1
    assert inst.target_nodes >= 1


def test_add_and_remove_node_update_target_nodes():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=1)
    inst.add_node("mesh-1-node-extra")

    assert "mesh-1-node-extra" in inst.node_instances
    assert inst.target_nodes == 1

    removed = inst.remove_node("mesh-1-node-extra")
    assert removed is True
    assert inst.target_nodes == 1


def test_get_consciousness_metrics_state_aware():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=1)
    inst.created_at = datetime.utcnow() - timedelta(hours=2)
    inst.node_instances = {
        "n1": {"status": "healthy"},
        "n2": {"status": "healthy"},
        "n3": {"status": "degraded"},
        "n4": {"status": "failed"},
    }

    metrics = inst.get_consciousness_metrics()
    assert metrics["nodes_total"] == 4
    assert metrics["nodes_healthy"] == 2
    assert metrics["state"] == "AWARE"
    assert 0.0 <= metrics["entropy"] <= 1.0


def test_get_mape_k_state_aggressiveness_high_when_unhealthy():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=1)
    inst.node_instances = {
        "n1": {"status": "failed"},
        "n2": {"status": "healthy"},
    }

    state = inst.get_mape_k_state()
    assert state["phase"] == "MONITOR"
    assert state["interval_seconds"] == 10
    assert state["directives"]["self_healing_aggressiveness"] == "medium"


def test_get_network_metrics_reflects_health():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=1)
    inst.node_instances = {"n1": {"status": "healthy"}, "n2": {"status": "failed"}}

    metrics = inst.get_network_metrics()
    assert metrics["nodes_active"] == 2
    assert metrics["throughput_mbps"] == 20.0
    assert metrics["packet_loss_pct"] == 0.5


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_terminate_clears_nodes_and_sets_status():
    inst = MeshInstance(mesh_id="mesh-term", name="m", owner_id="u", nodes=3)
    await inst.provision()
    assert inst.status == "active"
    await inst.terminate()
    assert inst.status == "terminated"
    assert inst.node_instances == {}


@pytest.mark.asyncio
async def test_scale_up_adds_nodes():
    inst = MeshInstance(mesh_id="mesh-up", name="m", owner_id="u", nodes=2)
    await inst.provision()
    new_count = inst.scale("scale_up", 3)
    assert new_count == 5
    assert inst.target_nodes == 5


def test_scale_unknown_action_is_noop():
    inst = MeshInstance(mesh_id="mesh-noop", name="m", owner_id="u", nodes=3)
    inst.node_instances = {f"n{i}": {"status": "healthy"} for i in range(3)}
    before = len(inst.node_instances)
    result = inst.scale("unknown_action", 2)
    assert result == before


def test_remove_nonexistent_node_returns_false():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    assert inst.remove_node("ghost-node") is False


def test_add_node_with_metadata_merges():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.add_node("n-custom", {"region": "eu-west", "latency_ms": 5.0})
    node = inst.node_instances["n-custom"]
    assert node["region"] == "eu-west"
    assert node["latency_ms"] == 5.0
    assert node["status"] == "healthy"


def test_get_health_score_empty_returns_zero():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    assert inst.get_health_score() == 0.0


def test_get_health_score_all_healthy_returns_one():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.node_instances = {f"n{i}": {"status": "healthy"} for i in range(5)}
    assert inst.get_health_score() == 1.0


def test_get_health_score_partial():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.node_instances = {
        "n1": {"status": "healthy"},
        "n2": {"status": "healthy"},
        "n3": {"status": "degraded"},
        "n4": {"status": "degraded"},
    }
    assert inst.get_health_score() == pytest.approx(0.5)


def test_consciousness_state_transcendent():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.created_at = datetime.utcnow() - timedelta(hours=2)
    inst.node_instances = {f"n{i}": {"status": "healthy"} for i in range(20)}
    metrics = inst.get_consciousness_metrics()
    assert metrics["state"] == "TRANSCENDENT"
    assert metrics["phi_ratio"] == pytest.approx(1.618)


def test_consciousness_state_flow():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.created_at = datetime.utcnow() - timedelta(hours=2)
    # health = 0.84 (16/19 - just below 0.95)
    healthy = {f"n{i}": {"status": "healthy"} for i in range(8)}
    degraded = {f"d{i}": {"status": "degraded"} for i in range(2)}
    inst.node_instances = {**healthy, **degraded}
    metrics = inst.get_consciousness_metrics()
    assert metrics["state"] == "FLOW"


def test_consciousness_state_dormant():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.created_at = datetime.utcnow() - timedelta(hours=2)
    inst.node_instances = {
        "n1": {"status": "degraded"},
        "n2": {"status": "degraded"},
        "n3": {"status": "healthy"},
    }
    metrics = inst.get_consciousness_metrics()
    assert metrics["state"] == "DORMANT"


def test_mape_k_high_aggressiveness_when_health_below_half():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.node_instances = {
        "n1": {"status": "failed"},
        "n2": {"status": "failed"},
        "n3": {"status": "failed"},
    }
    state = inst.get_mape_k_state()
    assert state["directives"]["self_healing_aggressiveness"] == "high"
    assert state["directives"]["scaling_recommendation"] == "scale_up"


def test_mape_k_low_aggressiveness_when_healthy():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.node_instances = {f"n{i}": {"status": "healthy"} for i in range(5)}
    state = inst.get_mape_k_state()
    assert state["directives"]["self_healing_aggressiveness"] == "low"
    assert state["interval_seconds"] == 30


def test_node_count_param_overrides_nodes():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=5, node_count=2)
    assert inst.target_nodes == 2


def test_get_uptime_increases_over_time():
    from datetime import datetime, timedelta
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.created_at = datetime.utcnow() - timedelta(seconds=100)
    assert inst.get_uptime() >= 100.0


def test_network_metrics_packet_loss_low_when_healthy():
    inst = MeshInstance(mesh_id="mesh-1", name="m", owner_id="u", nodes=0)
    inst.node_instances = {f"n{i}": {"status": "healthy"} for i in range(10)}
    metrics = inst.get_network_metrics()
    assert metrics["packet_loss_pct"] == 0.01

