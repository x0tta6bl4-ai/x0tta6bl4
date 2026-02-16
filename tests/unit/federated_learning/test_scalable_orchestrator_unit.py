"""Unit tests for ScalableFLOrchestrator and related classes."""

import asyncio
import hashlib
import time
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.federated_learning.scalable_orchestrator import (
    AdaptiveClientSampler, BulkAggregationTask, ByzantineRobustAggregator,
    CoordinatorProxy, GradientCompressor, NodeMetadata, ScalableFLOrchestrator,
    ScalableNodeRegistry)

# ============================================================================
# ScalableNodeRegistry Tests
# ============================================================================


class TestScalableNodeRegistry:
    def test_init_defaults(self):
        registry = ScalableNodeRegistry()
        assert registry.num_virtual_nodes == 160
        assert registry.ring == {}
        assert registry.nodes == {}

    def test_init_custom_virtual_nodes(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=50)
        assert registry.num_virtual_nodes == 50

    def test_hash_deterministic(self):
        h1 = ScalableNodeRegistry._hash("test-key")
        h2 = ScalableNodeRegistry._hash("test-key")
        assert h1 == h2

    def test_hash_different_keys(self):
        h1 = ScalableNodeRegistry._hash("key-a")
        h2 = ScalableNodeRegistry._hash("key-b")
        assert h1 != h2

    def test_add_node(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-1", capacity=500)

        assert "node-1" in registry.nodes
        assert registry.nodes["node-1"].capacity == 500
        assert registry.nodes["node-1"].node_id == "node-1"
        # 10 virtual nodes should be in the ring
        assert len(registry.ring) == 10
        # All virtual nodes map to node-1
        assert all(v == "node-1" for v in registry.ring.values())

    def test_add_node_default_capacity(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=5)
        registry.add_node("node-x")
        assert registry.nodes["node-x"].capacity == 1000

    def test_add_multiple_nodes(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-a")
        registry.add_node("node-b")
        assert len(registry.nodes) == 2
        assert len(registry.ring) == 20

    def test_remove_node(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-1")
        registry.add_node("node-2")

        registry.remove_node("node-1")

        assert "node-1" not in registry.nodes
        assert len(registry.ring) == 10
        assert all(v == "node-2" for v in registry.ring.values())

    def test_remove_nonexistent_node(self):
        registry = ScalableNodeRegistry()
        # Should not raise
        registry.remove_node("nonexistent")

    def test_get_node_empty_ring(self):
        registry = ScalableNodeRegistry()
        assert registry.get_node("some-key") is None

    def test_get_node_single_node(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-only")
        # Any key should map to the only node
        assert registry.get_node("any-key") == "node-only"
        assert registry.get_node("another-key") == "node-only"

    def test_get_node_multiple_nodes(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=100)
        registry.add_node("node-a")
        registry.add_node("node-b")
        registry.add_node("node-c")

        result = registry.get_node("test-key")
        assert result in {"node-a", "node-b", "node-c"}

    def test_get_node_wrap_around(self):
        """Test that get_node wraps around the ring."""
        registry = ScalableNodeRegistry(num_virtual_nodes=5)
        registry.add_node("node-1")
        # get_node should always return a valid node
        for i in range(20):
            assert registry.get_node(f"key-{i}") == "node-1"

    def test_get_top_n_nodes_empty_ring(self):
        registry = ScalableNodeRegistry()
        assert registry.get_top_n_nodes("key", n=3) == []

    def test_get_top_n_nodes_single_node(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-only")
        result = registry.get_top_n_nodes("key", n=3)
        assert result == ["node-only"]

    def test_get_top_n_nodes_returns_unique(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=50)
        registry.add_node("node-a")
        registry.add_node("node-b")
        registry.add_node("node-c")

        result = registry.get_top_n_nodes("key", n=3)
        assert len(result) == len(set(result))  # all unique
        assert len(result) <= 3

    def test_get_top_n_nodes_respects_n_limit(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=50)
        for i in range(10):
            registry.add_node(f"node-{i}")

        result = registry.get_top_n_nodes("key", n=3)
        assert len(result) == 3

    def test_get_top_n_nodes_fewer_than_n(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-a")
        registry.add_node("node-b")

        result = registry.get_top_n_nodes("key", n=5)
        assert len(result) == 2

    def test_get_stats_empty(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=32)
        stats = registry.get_stats()
        assert stats["total_nodes"] == 0
        assert stats["total_capacity"] == 0
        assert stats["virtual_nodes_per_physical"] == 32
        assert stats["nodes"] == {}

    def test_get_stats_with_nodes(self):
        registry = ScalableNodeRegistry(num_virtual_nodes=10)
        registry.add_node("node-a", capacity=200)
        registry.add_node("node-b", capacity=300)

        stats = registry.get_stats()
        assert stats["total_nodes"] == 2
        assert stats["total_capacity"] == 500
        assert "node-a" in stats["nodes"]
        assert "node-b" in stats["nodes"]


# ============================================================================
# NodeMetadata Tests
# ============================================================================


class TestNodeMetadata:
    def test_defaults(self):
        meta = NodeMetadata(node_id="n1", capacity=100, joined_at=1000.0)
        assert meta.node_id == "n1"
        assert meta.capacity == 100
        assert meta.joined_at == 1000.0
        assert meta.samples_contributed == 0
        assert meta.rounds_participated == 0
        assert meta.cpu_load == 0.0
        assert meta.memory_load == 0.0

    def test_custom_values(self):
        meta = NodeMetadata(
            node_id="n2",
            capacity=500,
            joined_at=2000.0,
            last_heartbeat=2001.0,
            samples_contributed=42,
            rounds_participated=5,
            cpu_load=0.75,
            memory_load=0.6,
        )
        assert meta.samples_contributed == 42
        assert meta.cpu_load == 0.75


# ============================================================================
# BulkAggregationTask Tests
# ============================================================================


class TestBulkAggregationTask:
    def test_defaults(self):
        task = BulkAggregationTask(task_id="t1", round_number=1, coordinator_id="c1")
        assert task.task_id == "t1"
        assert task.round_number == 1
        assert task.assigned_nodes == set()
        assert task.received_nodes == set()
        assert task.updates == {}
        assert task.aggregation_method == "fedavg"

    def test_is_overdue_false(self):
        task = BulkAggregationTask(
            task_id="t1",
            round_number=1,
            coordinator_id="c1",
            deadline=time.time() + 3600,
        )
        assert task.is_overdue() is False

    def test_is_overdue_true(self):
        task = BulkAggregationTask(
            task_id="t1",
            round_number=1,
            coordinator_id="c1",
            deadline=time.time() - 10,
        )
        assert task.is_overdue() is True

    def test_is_complete_empty(self):
        task = BulkAggregationTask(task_id="t1", round_number=1, coordinator_id="c1")
        task.assigned_nodes = set()
        # max(1, 0//2) = 1, received=0 => not complete
        assert task.is_complete() is False

    def test_is_complete_majority_met(self):
        task = BulkAggregationTask(task_id="t1", round_number=1, coordinator_id="c1")
        task.assigned_nodes = {"a", "b", "c", "d"}
        # required = max(1, 4//2) = 2
        task.received_nodes = {"a", "b"}
        assert task.is_complete() is True

    def test_is_complete_not_enough(self):
        task = BulkAggregationTask(task_id="t1", round_number=1, coordinator_id="c1")
        task.assigned_nodes = {"a", "b", "c", "d"}
        task.received_nodes = {"a"}
        assert task.is_complete() is False

    def test_is_complete_single_assigned(self):
        task = BulkAggregationTask(task_id="t1", round_number=1, coordinator_id="c1")
        task.assigned_nodes = {"a"}
        # required = max(1, 1//2) = max(1, 0) = 1
        task.received_nodes = {"a"}
        assert task.is_complete() is True


# ============================================================================
# CoordinatorProxy Tests
# ============================================================================


class TestCoordinatorProxy:
    def test_init(self):
        proxy = CoordinatorProxy(coordinator_id="c1", max_capacity=100)
        assert proxy.coordinator_id == "c1"
        assert proxy.max_capacity == 100
        assert proxy.nodes == set()

    @pytest.mark.asyncio
    async def test_register_node_success(self):
        proxy = CoordinatorProxy(coordinator_id="c1", max_capacity=2)
        assert await proxy.register_node("node-a") is True
        assert "node-a" in proxy.nodes

    @pytest.mark.asyncio
    async def test_register_node_at_capacity(self):
        proxy = CoordinatorProxy(coordinator_id="c1", max_capacity=1)
        await proxy.register_node("node-a")
        assert await proxy.register_node("node-b") is False
        assert "node-b" not in proxy.nodes

    @pytest.mark.asyncio
    async def test_start_round(self):
        proxy = CoordinatorProxy(coordinator_id="c1")
        result = await proxy.start_round(1, ["node-a", "node-b"])
        assert result is True

    @pytest.mark.asyncio
    async def test_collect_updates_empty(self):
        proxy = CoordinatorProxy(coordinator_id="c1")
        result = await proxy.collect_updates(1)
        assert result == {}

    @pytest.mark.asyncio
    async def test_collect_updates_with_data(self):
        proxy = CoordinatorProxy(coordinator_id="c1")
        proxy.updates[1] = {"node-a": [1, 2, 3]}
        result = await proxy.collect_updates(1)
        assert result == {"node-a": [1, 2, 3]}

    @pytest.mark.asyncio
    async def test_aggregate(self):
        proxy = CoordinatorProxy(coordinator_id="c1")
        result = await proxy.aggregate(1)
        assert result is True

    def test_get_status(self):
        proxy = CoordinatorProxy(coordinator_id="c1", max_capacity=100)
        proxy.nodes = {"a", "b"}
        status = proxy.get_status()
        assert status["coordinator_id"] == "c1"
        assert status["nodes"] == 2
        assert status["capacity"] == 100
        assert status["load"] == pytest.approx(0.02)


# ============================================================================
# ScalableFLOrchestrator Tests
# ============================================================================


class TestScalableFLOrchestratorInit:
    def test_init_defaults(self):
        orch = ScalableFLOrchestrator(orchestrator_id="master")
        assert orch.orchestrator_id == "master"
        assert orch.num_coordinators == 4
        assert orch.max_nodes_per_coordinator == 500
        assert len(orch.coordinators) == 4
        assert orch.active_tasks == {}
        assert orch.completed_tasks == []

    def test_init_custom(self):
        orch = ScalableFLOrchestrator(
            orchestrator_id="orch-1",
            num_coordinators=2,
            max_nodes_per_coordinator=100,
        )
        assert len(orch.coordinators) == 2
        assert all(c.max_capacity == 100 for c in orch.coordinators.values())

    def test_init_coordinators_named(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=3)
        assert "coordinator-0" in orch.coordinators
        assert "coordinator-1" in orch.coordinators
        assert "coordinator-2" in orch.coordinators


class TestScalableFLOrchestratorSelectCoordinator:
    def test_select_least_loaded(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=3)
        # Load coordinator-0 and coordinator-1
        orch.coordinators["coordinator-0"].nodes = {"a", "b", "c"}
        orch.coordinators["coordinator-1"].nodes = {"d", "e"}
        orch.coordinators["coordinator-2"].nodes = set()

        assert orch._select_coordinator() == "coordinator-2"

    def test_select_with_equal_load(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)
        # Both empty — should pick one deterministically (min of keys)
        result = orch._select_coordinator()
        assert result in {"coordinator-0", "coordinator-1"}


class TestScalableFLOrchestratorRegisterNode:
    @pytest.mark.asyncio
    async def test_register_node(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)
        coordinator_id = await orch.register_node("node-1", capacity=200)

        assert coordinator_id in orch.coordinators
        assert "node-1" in orch.registry.nodes
        assert orch.registry.nodes["node-1"].capacity == 200

    @pytest.mark.asyncio
    async def test_register_multiple_nodes_balances(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)
        await orch.register_node("node-a")
        await orch.register_node("node-b")

        # Each coordinator should have 1 node
        loads = [len(c.nodes) for c in orch.coordinators.values()]
        assert sorted(loads) == [1, 1]


class TestScalableFLOrchestratorDistributeNodes:
    def test_distribute_nodes(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=4)
        nodes = {"node-0", "node-1", "node-2", "node-3"}
        dist = orch._distribute_nodes(nodes)

        # All nodes should be distributed
        all_nodes = []
        for node_list in dist.values():
            all_nodes.extend(node_list)
        assert set(all_nodes) == nodes

    def test_distribute_empty(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)
        dist = orch._distribute_nodes(set())
        assert dict(dist) == {}


class TestScalableFLOrchestratorAdaptiveSelection:
    def test_no_eligible_nodes(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        # No nodes registered
        result = orch._adaptive_node_selection(10)
        assert result == set()

    def test_skip_overloaded_cpu(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        orch.registry.add_node("node-heavy")
        orch.registry.nodes["node-heavy"].cpu_load = 0.9

        result = orch._adaptive_node_selection(5)
        assert result == set()

    def test_skip_overloaded_memory(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        orch.registry.add_node("node-mem")
        orch.registry.nodes["node-mem"].memory_load = 0.85

        result = orch._adaptive_node_selection(5)
        assert result == set()

    def test_selects_eligible_nodes(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        for i in range(5):
            orch.registry.add_node(f"node-{i}", capacity=1000)
            orch.registry.nodes[f"node-{i}"].cpu_load = 0.1
            orch.registry.nodes[f"node-{i}"].memory_load = 0.1

        with patch("src.federated_learning.scalable_orchestrator.np") as mock_np:
            mock_np.random.choice.return_value = np.array(
                ["node-0", "node-1", "node-2"]
            )
            result = orch._adaptive_node_selection(3)
            assert len(result) == 3
            mock_np.random.choice.assert_called_once()

    def test_target_larger_than_available(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        orch.registry.add_node("node-0", capacity=1000)

        with patch("src.federated_learning.scalable_orchestrator.np") as mock_np:
            mock_np.random.choice.return_value = np.array(["node-0"])
            result = orch._adaptive_node_selection(10)
            # Should request min(10, 1) = 1
            call_args = mock_np.random.choice.call_args
            assert call_args[1]["size"] == 1


class TestScalableFLOrchestratorStartTrainingRound:
    @pytest.mark.asyncio
    async def test_start_training_round(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)
        for i in range(4):
            orch.registry.add_node(f"node-{i}")

        with patch.object(
            orch, "_adaptive_node_selection", return_value={"node-0", "node-1"}
        ):
            task = await orch.start_training_round(
                round_number=1, target_participants=2
            )

        assert task.task_id == "round-1"
        assert task.round_number == 1
        assert task.assigned_nodes == {"node-0", "node-1"}
        assert "round-1" in orch.active_tasks

    @pytest.mark.asyncio
    async def test_start_training_round_no_nodes(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)

        with patch.object(orch, "_adaptive_node_selection", return_value=set()):
            task = await orch.start_training_round(
                round_number=1, target_participants=5
            )

        assert task.assigned_nodes == set()

    @pytest.mark.asyncio
    async def test_start_training_round_coordinator_exception(self):
        """Coordinator exceptions should be handled via return_exceptions=True."""
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)

        # Make one coordinator fail
        orch.coordinators["coordinator-0"].start_round = AsyncMock(
            side_effect=RuntimeError("connection lost")
        )

        with patch.object(orch, "_adaptive_node_selection", return_value={"node-a"}):
            # Should not raise due to return_exceptions=True
            task = await orch.start_training_round(
                round_number=1, target_participants=1
            )
            assert task is not None


class TestScalableFLOrchestratorCollectUpdates:
    @pytest.mark.asyncio
    async def test_collect_unknown_task(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        result = await orch.collect_updates("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_collect_updates_complete_immediately(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=1)

        task = BulkAggregationTask(
            task_id="round-1", round_number=1, coordinator_id="m"
        )
        task.assigned_nodes = {"node-a", "node-b"}
        orch.active_tasks["round-1"] = task

        # Coordinator returns updates for both nodes
        orch.coordinators["coordinator-0"].collect_updates = AsyncMock(
            return_value={"node-a": [1], "node-b": [2]}
        )

        result = await orch.collect_updates("round-1", timeout_sec=5)
        assert result is not None
        assert result.received_nodes == {"node-a", "node-b"}

    @pytest.mark.asyncio
    async def test_collect_updates_timeout(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=1)

        task = BulkAggregationTask(
            task_id="round-1", round_number=1, coordinator_id="m"
        )
        task.assigned_nodes = {"node-a", "node-b", "node-c", "node-d"}
        orch.active_tasks["round-1"] = task

        # Coordinator returns nothing
        orch.coordinators["coordinator-0"].collect_updates = AsyncMock(return_value={})

        # Use very short timeout
        with patch(
            "src.federated_learning.scalable_orchestrator.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            result = await orch.collect_updates("round-1", timeout_sec=0.01)

        assert result is not None
        assert len(result.received_nodes) == 0

    @pytest.mark.asyncio
    async def test_collect_updates_ignores_exceptions(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)

        task = BulkAggregationTask(
            task_id="round-1", round_number=1, coordinator_id="m"
        )
        task.assigned_nodes = {"node-a", "node-b"}
        orch.active_tasks["round-1"] = task

        # One coordinator returns data, other throws exception
        orch.coordinators["coordinator-0"].collect_updates = AsyncMock(
            return_value={"node-a": [1]}
        )
        orch.coordinators["coordinator-1"].collect_updates = AsyncMock(
            side_effect=RuntimeError("network error")
        )

        result = await orch.collect_updates("round-1", timeout_sec=5)
        # node-a should be collected, exception should be ignored
        assert "node-a" in result.received_nodes


class TestScalableFLOrchestratorAggregateRound:
    @pytest.mark.asyncio
    async def test_aggregate_unknown_task(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m")
        result = await orch.aggregate_round("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_aggregate_success(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)

        task = BulkAggregationTask(
            task_id="round-1", round_number=1, coordinator_id="m"
        )
        orch.active_tasks["round-1"] = task

        result = await orch.aggregate_round("round-1")
        assert result is True
        assert "round-1" not in orch.active_tasks
        assert len(orch.completed_tasks) == 1
        assert orch.completed_tasks[0] is task

    @pytest.mark.asyncio
    async def test_aggregate_coordinator_error(self):
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=2)

        task = BulkAggregationTask(
            task_id="round-1", round_number=1, coordinator_id="m"
        )
        orch.active_tasks["round-1"] = task

        # Make one coordinator fail
        orch.coordinators["coordinator-0"].aggregate = AsyncMock(
            side_effect=RuntimeError("agg failed")
        )

        result = await orch.aggregate_round("round-1")
        assert result is False
        assert orch.metrics["aggregation_errors"] == 1

    @pytest.mark.asyncio
    async def test_aggregate_gather_exception(self):
        """Test the outer try/except for unexpected errors."""
        orch = ScalableFLOrchestrator(orchestrator_id="m", num_coordinators=1)

        task = BulkAggregationTask(
            task_id="round-1", round_number=1, coordinator_id="m"
        )
        orch.active_tasks["round-1"] = task

        # Patch asyncio.gather to raise
        with patch(
            "src.federated_learning.scalable_orchestrator.asyncio.gather",
            new_callable=AsyncMock,
            side_effect=Exception("unexpected"),
        ):
            result = await orch.aggregate_round("round-1")
            assert result is False
            assert orch.metrics["aggregation_errors"] >= 1


class TestScalableFLOrchestratorGetStatus:
    def test_get_status(self):
        orch = ScalableFLOrchestrator(orchestrator_id="master-1", num_coordinators=2)
        status = orch.get_status()
        assert status["orchestrator_id"] == "master-1"
        assert status["active_tasks"] == 0
        assert status["completed_tasks"] == 0
        assert "registry" in status
        assert "metrics" in status
        assert len(status["coordinators"]) == 2


# ============================================================================
# ByzantineRobustAggregator Tests
# ============================================================================


class TestByzantineRobustAggregator:
    def test_krum_basic(self):
        updates = [
            np.array([1.0, 1.0]),
            np.array([1.1, 0.9]),
            np.array([0.9, 1.1]),
            np.array([100.0, 100.0]),  # Byzantine
        ]
        result = ByzantineRobustAggregator.krum_aggregation(updates, num_byzantine=1)
        # Should select one of the honest updates (not the outlier)
        assert np.linalg.norm(result - np.array([100.0, 100.0])) > 1.0

    def test_krum_fallback_median(self):
        """When n <= num_byzantine + 2, falls back to median."""
        updates = [
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
        ]
        result = ByzantineRobustAggregator.krum_aggregation(updates, num_byzantine=1)
        expected = np.median(np.array(updates), axis=0)
        np.testing.assert_array_almost_equal(result, expected)

    def test_krum_exact_boundary(self):
        """n == num_byzantine + 2 should use median."""
        updates = [
            np.array([1.0]),
            np.array([2.0]),
            np.array([3.0]),
        ]
        result = ByzantineRobustAggregator.krum_aggregation(updates, num_byzantine=1)
        expected = np.median(np.array(updates), axis=0)
        np.testing.assert_array_almost_equal(result, expected)

    def test_multikrum_basic(self):
        updates = [
            np.array([1.0, 1.0]),
            np.array([1.1, 0.9]),
            np.array([0.9, 1.1]),
            np.array([100.0, 100.0]),  # Byzantine
        ]
        result = ByzantineRobustAggregator.multikrum_aggregation(
            updates, num_byzantine=1, m=2
        )
        # Average of 2 best should be close to honest cluster
        assert np.linalg.norm(result - np.array([1.0, 1.0])) < 5.0

    def test_multikrum_fallback_mean(self):
        """When n <= num_byzantine + 2, falls back to mean."""
        updates = [
            np.array([1.0, 2.0]),
            np.array([3.0, 4.0]),
        ]
        result = ByzantineRobustAggregator.multikrum_aggregation(
            updates, num_byzantine=1, m=1
        )
        expected = np.mean(updates, axis=0)
        np.testing.assert_array_almost_equal(result, expected)

    def test_multikrum_m_equals_1(self):
        """m=1 should behave similar to krum (single selection)."""
        updates = [
            np.array([1.0]),
            np.array([1.1]),
            np.array([1.05]),
            np.array([100.0]),
        ]
        result = ByzantineRobustAggregator.multikrum_aggregation(
            updates, num_byzantine=1, m=1
        )
        # Should select one of the honest updates
        assert result[0] < 50.0


# ============================================================================
# GradientCompressor Tests
# ============================================================================


class TestGradientCompressor:
    def test_top_k_sparsify_basic(self):
        gradient = np.array([1.0, 5.0, 2.0, 8.0, 0.5, 3.0, 7.0, 0.1, 4.0, 6.0])
        sparse, metadata = GradientCompressor.top_k_sparsify(gradient, k_percent=0.3)

        assert sparse.shape == gradient.shape
        # Only 3 values should be non-zero (30% of 10)
        nonzero_count = np.count_nonzero(sparse)
        assert nonzero_count == 3
        assert metadata["compression_ratio"] == 0.3
        assert metadata["original_size"] == 10
        assert metadata["compressed_size"] == 3

    def test_top_k_sparsify_preserves_top_values(self):
        gradient = np.array([1.0, 10.0, 2.0, 9.0])
        sparse, _ = GradientCompressor.top_k_sparsify(gradient, k_percent=0.5)
        # Top 2 by magnitude: 10.0 and 9.0
        assert sparse[1] == 10.0
        assert sparse[3] == 9.0
        assert sparse[0] == 0.0
        assert sparse[2] == 0.0

    def test_top_k_sparsify_min_k_1(self):
        """k should be at least 1."""
        gradient = np.array([5.0, 3.0])
        sparse, metadata = GradientCompressor.top_k_sparsify(gradient, k_percent=0.0)
        # k = max(1, int(2*0.0)) = max(1, 0) = 1
        assert np.count_nonzero(sparse) == 1
        assert metadata["compressed_size"] == 1

    def test_top_k_sparsify_2d(self):
        gradient = np.array([[1.0, 5.0], [2.0, 8.0]])
        sparse, metadata = GradientCompressor.top_k_sparsify(gradient, k_percent=0.5)
        assert sparse.shape == (2, 2)
        assert np.count_nonzero(sparse) == 2

    def test_top_k_bandwidth_reduction(self):
        gradient = np.ones(100)
        _, metadata = GradientCompressor.top_k_sparsify(gradient, k_percent=0.1)
        assert metadata["bandwidth_reduction_percent"] == pytest.approx(90.0)

    def test_quantize_to_int8(self):
        gradient = np.array([1.0, -0.5, 0.25, 0.0])
        quantized, scale = GradientCompressor.quantize_to_int8(gradient)

        assert quantized.dtype == np.int8
        assert scale == 1.0
        assert quantized[0] == 127  # 1.0 / 1.0 * 127
        assert quantized[1] == -64  # round(-0.5 / 1.0 * 127) = round(-63.5) = -64

    def test_dequantize_from_int8(self):
        quantized = np.array([127, -127, 0], dtype=np.int8)
        scale = 2.0
        result = GradientCompressor.dequantize_from_int8(quantized, scale)

        assert result.dtype == np.float32
        np.testing.assert_array_almost_equal(result, [2.0, -2.0, 0.0])

    def test_quantize_dequantize_roundtrip(self):
        gradient = np.array([1.0, -0.5, 0.25, 0.75])
        quantized, scale = GradientCompressor.quantize_to_int8(gradient)
        recovered = GradientCompressor.dequantize_from_int8(quantized, scale)

        # Approximate roundtrip (quantization introduces error)
        np.testing.assert_array_almost_equal(gradient, recovered, decimal=1)


# ============================================================================
# AdaptiveClientSampler Tests
# ============================================================================


class TestAdaptiveClientSampler:
    def test_init(self):
        sampler = AdaptiveClientSampler(total_clients=100)
        assert sampler.total_clients == 100

    def test_select_clients_basic(self):
        sampler = AdaptiveClientSampler(total_clients=10)
        selected = sampler.select_clients(round_num=1, target_fraction=0.3)
        # 10 * 0.3 = 3
        assert len(selected) == 3
        assert all(c.startswith("client_") for c in selected)

    def test_select_clients_minimum_one(self):
        sampler = AdaptiveClientSampler(total_clients=10)
        selected = sampler.select_clients(round_num=1, target_fraction=0.01)
        # max(1, int(10 * 0.01)) = max(1, 0) = 1
        assert len(selected) == 1

    def test_select_clients_all(self):
        sampler = AdaptiveClientSampler(total_clients=5)
        selected = sampler.select_clients(round_num=1, target_fraction=1.0)
        assert len(selected) == 5

    def test_select_clients_with_convergence_scores(self):
        sampler = AdaptiveClientSampler(total_clients=5)
        # Give client_2 the highest score
        sampler.convergence_scores["client_2"] = 10.0
        sampler.convergence_scores["client_4"] = 5.0

        selected = sampler.select_clients(round_num=1, target_fraction=0.4)
        # Should select top 2 (5 * 0.4 = 2)
        assert len(selected) == 2
        assert selected[0] == "client_2"
        assert selected[1] == "client_4"

    def test_select_clients_exclude_stragglers(self):
        sampler = AdaptiveClientSampler(total_clients=3)
        # Give all equal convergence scores
        for i in range(3):
            sampler.convergence_scores[f"client_{i}"] = 1.0

        # Mark client_0 as straggler for many rounds
        sampler.straggler_history["client_0"] = [1, 2, 3, 4, 5]

        selected = sampler.select_clients(
            round_num=5, target_fraction=0.67, exclude_stragglers=True
        )
        # 3 * 0.67 = 2 clients
        assert len(selected) == 2
        # client_0 should be penalized (straggler_ratio = 5/5 = 1.0, score *= 0)
        assert "client_0" not in selected

    def test_select_clients_no_straggler_penalty_when_disabled(self):
        sampler = AdaptiveClientSampler(total_clients=3)
        for i in range(3):
            sampler.convergence_scores[f"client_{i}"] = 1.0
        sampler.straggler_history["client_0"] = [1, 2, 3, 4, 5]

        selected = sampler.select_clients(
            round_num=5, target_fraction=1.0, exclude_stragglers=False
        )
        # Without penalty, all should be equal and selected
        assert len(selected) == 3
        assert "client_0" in selected

    def test_update_convergence_score(self):
        sampler = AdaptiveClientSampler(total_clients=10)
        sampler.update_convergence_score("client_0", improvement=1.0)
        # 0.7 * 0.0 + 0.3 * 1.0 = 0.3
        assert sampler.convergence_scores["client_0"] == pytest.approx(0.3)

        sampler.update_convergence_score("client_0", improvement=1.0)
        # 0.7 * 0.3 + 0.3 * 1.0 = 0.51
        assert sampler.convergence_scores["client_0"] == pytest.approx(0.51)

    def test_update_convergence_score_zero_improvement(self):
        sampler = AdaptiveClientSampler(total_clients=10)
        sampler.convergence_scores["client_0"] = 1.0
        sampler.update_convergence_score("client_0", improvement=0.0)
        # 0.7 * 1.0 + 0.3 * 0.0 = 0.7
        assert sampler.convergence_scores["client_0"] == pytest.approx(0.7)

    def test_mark_straggler(self):
        sampler = AdaptiveClientSampler(total_clients=10)
        sampler.mark_straggler("client_5", round_num=3)
        sampler.mark_straggler("client_5", round_num=7)

        assert sampler.straggler_history["client_5"] == [3, 7]

    def test_mark_straggler_unknown_client(self):
        sampler = AdaptiveClientSampler(total_clients=10)
        sampler.mark_straggler("client_99", round_num=1)
        assert sampler.straggler_history["client_99"] == [1]
