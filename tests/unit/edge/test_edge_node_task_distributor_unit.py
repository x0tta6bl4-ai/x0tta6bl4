"""Focused unit tests for edge node and task distributor modules."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.edge.edge_node import (
    EdgeNode,
    EdgeNodeConfig,
    EdgeNodeManager,
    EdgeNodeState,
    EdgeTask,
    NodeResources,
    TaskPriority,
)
from src.edge.task_distributor import DistributionConfig, DistributionStrategy, TaskDistributor


def test_edge_models_config_task_and_resources():
    cfg = EdgeNodeConfig(node_id="", name="", advertise_host="edge.local", listen_port=9091)
    assert cfg.node_id.startswith("edge-")
    assert cfg.name == cfg.node_id

    task = EdgeTask(task_id="t1", task_type="compute", payload={"x": 1})
    assert task.is_completed is False
    assert task.is_failed is False
    task.started_at = datetime.utcnow()
    task.completed_at = task.started_at + timedelta(seconds=2)
    assert task.duration_seconds == 2

    task.error = "boom"
    assert task.is_failed is True

    resources = NodeResources(cpu_percent=10.0, memory_percent=20.0, available_slots=3)
    as_dict = resources.to_dict()
    assert as_dict["cpu_percent"] == 10.0
    assert as_dict["available_slots"] == 3


@pytest.mark.asyncio
async def test_edge_node_queue_cache_and_capability_checks():
    node = EdgeNode(
        EdgeNodeConfig(
            max_queue_size=1,
            max_concurrent_tasks=2,
            result_cache_ttl_seconds=10,
            capabilities={"compute"},
        )
    )
    node.state = EdgeNodeState.READY
    node._resources.available_slots = 2

    missing_cap = EdgeTask(
        task_id="missing",
        task_type="gpu",
        payload={},
        required_capabilities={"gpu"},
    )
    with pytest.raises(ValueError, match="Missing capabilities"):
        await node.submit_task(missing_cap)

    t1 = EdgeTask(task_id="ok1", task_type="compute", payload={})
    assert await node.submit_task(t1) == "ok1"

    t2 = EdgeTask(task_id="ok2", task_type="compute", payload={})
    with pytest.raises(RuntimeError, match="Task queue is full"):
        await node.submit_task(t2)

    assert await node.cancel_task("ok1") is True
    assert await node.cancel_task("unknown") is False

    node.cache_result("k1", {"result": 1})
    assert node.get_cached_result("k1") == {"result": 1}

    old_ts = datetime.utcnow() - timedelta(seconds=20)
    node._result_cache["k1"] = ({"result": 1}, old_ts)
    assert node.get_cached_result("k1") is None

    node._resources.cpu_percent = 99.0
    assert node.can_accept_task() is False


@pytest.mark.asyncio
async def test_edge_node_manager_and_task_distributor_flow():
    manager = EdgeNodeManager()

    n1 = manager.register_node(
        endpoint="http://n1.local:8001",
        capabilities=["compute", "gpu"],
        max_concurrent_tasks=4,
        metadata={"tier": "a"},
    )
    n2 = manager.register_node(
        endpoint="http://n2.local:8002",
        capabilities=["compute"],
        max_concurrent_tasks=2,
    )

    n1.state = EdgeNodeState.READY
    n2.state = EdgeNodeState.READY
    n1._resources.available_slots = 4
    n2._resources.available_slots = 1

    assert manager.get_best_node(required_capabilities={"gpu"}).config.node_id == n1.config.node_id
    assert manager.list_nodes(capability_filter="compute")
    assert manager.get_node_resources(n1.config.node_id)["network_mbps"] >= 0.0

    distributor = TaskDistributor(
        node_manager=manager,
        config=DistributionConfig(strategy=DistributionStrategy.ROUND_ROBIN, max_retries=1),
    )
    task = EdgeTask(
        task_id="dist-1",
        task_type="compute",
        payload={"p": 1},
        priority=TaskPriority.HIGH,
        required_capabilities={"compute"},
    )

    success, node_id = await distributor.distribute_task(task)
    assert success is True
    assert node_id in {n1.config.node_id, n2.config.node_id}

    distributor.set_strategy(DistributionStrategy.HASH_BASED, {"retry_delay_seconds": 0.01})
    assert distributor.get_strategy() == DistributionStrategy.HASH_BASED
    assert distributor.get_task_status("dist-1") is not None
    assert distributor.cancel_task("dist-1") is True
    assert distributor.cancel_task("missing") is False

    result = distributor.get_task_result("dist-1")
    assert result["status"] in {"cancelled", "completed"}

    metrics = distributor.get_metrics_summary()
    assert metrics["total_distributed"] >= 1
    assert metrics["strategy"] == "hash_based"

    assert manager.deregister_node(n2.config.node_id) is True
    assert manager.deregister_node("missing") is False
