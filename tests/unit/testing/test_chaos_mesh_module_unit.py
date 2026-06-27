import importlib
import os
from dataclasses import dataclass

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_import_smoke():
    try:
        mod = importlib.import_module("src.testing.chaos_mesh")
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None


@dataclass
class _Node:
    is_online: bool = True


class _NodeManager:
    def __init__(self, states):
        self.nodes = {
            node_id: _Node(is_online=is_online)
            for node_id, is_online in states.items()
        }


def test_mesh_health_uses_node_online_ratio():
    mod = importlib.import_module("src.testing.chaos_mesh")
    manager = _NodeManager(
        {
            "node-a": True,
            "node-b": True,
            "node-c": True,
            "node-d": False,
        }
    )

    chaos = mod.ChaosMesh(manager, min_online_ratio=0.75)

    assert chaos._check_mesh_health() is True
    snapshot = chaos._mesh_health_snapshot()
    assert snapshot["online_nodes"] == 3
    assert snapshot["total_nodes"] == 4
    assert snapshot["online_ratio"] == 0.75


def test_mesh_health_fails_when_online_ratio_below_threshold():
    mod = importlib.import_module("src.testing.chaos_mesh")
    manager = _NodeManager(
        {
            "node-a": True,
            "node-b": False,
            "node-c": False,
            "node-d": True,
        }
    )

    chaos = mod.ChaosMesh(manager, min_online_ratio=0.75)

    assert chaos._check_mesh_health(targets=["node-b", "node-c"]) is False
    snapshot = chaos._mesh_health_snapshot()
    assert snapshot["offline_nodes"] == ["node-b", "node-c"]
    assert snapshot["healthy"] is False


def test_synthetic_nodes_are_measured_after_fault_injection():
    mod = importlib.import_module("src.testing.chaos_mesh")
    chaos = mod.ChaosMesh(
        node_manager=None,
        synthetic_node_count=4,
        min_online_ratio=0.75,
    )

    assert chaos._check_mesh_health() is True

    chaos._simulate_pod_delete(["node-0", "node-1"])

    assert chaos._check_mesh_health(targets=["node-0", "node-1"]) is False
