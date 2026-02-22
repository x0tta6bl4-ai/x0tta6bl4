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

