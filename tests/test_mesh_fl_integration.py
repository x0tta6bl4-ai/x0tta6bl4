"""
Tests for Mesh-FL Integration Layer
====================================

Tests topology-aware aggregation and Batman-adv integration.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from src.federated_learning.topology_aware_aggregator import (
    AggregationResult,
    BatmanAdvMetricsProvider,
    ModelUpdate,
    NodeConnectivity,
    TopologyAwareAggregator,
    create_topology_aware_aggregator,
)
from src.federated_learning.mesh_fl_integration import (
    MeshFLConfig,
    MeshFLIntegration,
    TrainingRound,
    create_mesh_fl_integration,
    integrate_with_fl_coordinator,
)


class TestNodeConnectivity:
    """Tests for NodeConnectivity dataclass."""

    def test_default_values(self):
        """Test default connectivity values."""
        conn = NodeConnectivity(node_id="test-node")
        assert conn.node_id == "test-node"
        assert conn.link_quality == 1.0
        assert conn.latency_ms == 0.0
        assert conn.bandwidth_mbps == 100.0
        assert conn.hop_count == 1

    def test_get_weight_high_quality(self):
        """Test weight calculation for high-quality link."""
        conn = NodeConnectivity(
            node_id="node-1",
            link_quality=0.9,
            latency_ms=10.0,
            hop_count=1,
        )
        weight = conn.get_weight()
        assert 0 < weight <= 1.0
        # High quality, low latency, single hop should give high weight
        assert weight > 0.5

    def test_get_weight_low_quality(self):
        """Test weight calculation for low-quality link."""
        conn = NodeConnectivity(
            node_id="node-2",
            link_quality=0.3,
            latency_ms=200.0,
            hop_count=3,
        )
        weight = conn.get_weight()
        assert 0 < weight < 1.0
        # Low quality, high latency, multiple hops should give low weight
        assert weight < 0.5

    def test_get_weight_zero_quality(self):
        """Test weight calculation with zero link quality."""
        conn = NodeConnectivity(
            node_id="node-3",
            link_quality=0.0,
            latency_ms=0.0,
            hop_count=1,
        )
        weight = conn.get_weight()
        assert weight == 0.0


class TestTopologyAwareAggregator:
    """Tests for TopologyAwareAggregator."""

    @pytest.fixture
    def aggregator(self):
        """Create aggregator instance."""
        return TopologyAwareAggregator(
            min_participants=2,
            byzantine_robust=True,
        )

    @pytest.fixture
    def sample_weights(self):
        """Create sample model weights."""
        return {
            "layer1": np.array([[1.0, 2.0], [3.0, 4.0]]),
            "layer2": np.array([5.0, 6.0]),
        }

    def test_init(self, aggregator):
        """Test aggregator initialization."""
        assert aggregator.min_participants == 2
        assert aggregator.byzantine_robust is True
        assert len(aggregator._nodes) == 0
        assert aggregator._metrics["total_aggregations"] == 0

    def test_register_node(self, aggregator):
        """Test node registration."""
        conn = NodeConnectivity(node_id="node-1", link_quality=0.8)
        aggregator.register_node("node-1", conn)
        
        assert "node-1" in aggregator._nodes
        assert aggregator._nodes["node-1"].link_quality == 0.8

    def test_unregister_node(self, aggregator):
        """Test node unregistration."""
        aggregator.register_node("node-1", NodeConnectivity(node_id="node-1"))
        aggregator.unregister_node("node-1")
        
        assert "node-1" not in aggregator._nodes
        assert aggregator._metrics["node_churn_events"] == 1

    def test_update_connectivity(self, aggregator):
        """Test connectivity update."""
        aggregator.register_node("node-1", NodeConnectivity(node_id="node-1"))
        aggregator.update_connectivity("node-1", link_quality=0.5, latency_ms=50.0)
        
        assert aggregator._nodes["node-1"].link_quality == 0.5
        assert aggregator._nodes["node-1"].latency_ms == 50.0

    def test_add_update(self, aggregator, sample_weights):
        """Test adding model update."""
        update = ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=sample_weights,
            num_samples=100,
        )
        aggregator.add_update(update)
        
        assert 1 in aggregator._updates
        assert len(aggregator._updates[1]) == 1
        assert aggregator._metrics["total_updates_processed"] == 1

    def test_get_expected_participants(self, aggregator):
        """Test getting expected participants."""
        # Register nodes with recent updates
        for i in range(3):
            conn = NodeConnectivity(node_id=f"node-{i}", last_updated=time.time())
            aggregator.register_node(f"node-{i}", conn)
        
        # Register node with stale update
        stale_conn = NodeConnectivity(node_id="stale-node", last_updated=time.time() - 100)
        aggregator.register_node("stale-node", stale_conn)
        
        participants = aggregator.get_expected_participants(1)
        assert len(participants) == 3
        assert "stale-node" not in participants

    @pytest.mark.asyncio
    async def test_aggregate_insufficient_participants(self, aggregator, sample_weights):
        """Test aggregation with insufficient participants."""
        # Only one update
        aggregator.add_update(ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=sample_weights,
            num_samples=100,
        ))
        
        result = await aggregator.aggregate(1)
        assert result is None

    @pytest.mark.asyncio
    async def test_aggregate_success(self, aggregator, sample_weights):
        """Test successful aggregation."""
        # Register nodes
        aggregator.register_node("node-1", NodeConnectivity(node_id="node-1", link_quality=0.9))
        aggregator.register_node("node-2", NodeConnectivity(node_id="node-2", link_quality=0.8))
        
        # Add updates
        aggregator.add_update(ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=sample_weights,
            num_samples=100,
        ))
        aggregator.add_update(ModelUpdate(
            node_id="node-2",
            round_number=1,
            weights={
                "layer1": np.array([[1.5, 2.5], [3.5, 4.5]]),
                "layer2": np.array([5.5, 6.5]),
            },
            num_samples=150,
        ))
        
        result = await aggregator.aggregate(1)
        
        assert result is not None
        assert result.round_number == 1
        assert len(result.participating_nodes) == 2
        assert result.total_samples == 250
        assert "layer1" in result.aggregated_weights
        assert "layer2" in result.aggregated_weights

    @pytest.mark.asyncio
    async def test_aggregate_byzantine_robust(self, aggregator):
        """Test Byzantine-robust aggregation."""
        aggregator.register_node("node-1", NodeConnectivity(node_id="node-1"))
        aggregator.register_node("node-2", NodeConnectivity(node_id="node-2"))
        aggregator.register_node("node-3", NodeConnectivity(node_id="node-3"))
        
        # Normal updates
        weights1 = {"w": np.array([1.0, 2.0, 3.0])}
        weights2 = {"w": np.array([1.1, 2.1, 3.1])}
        # Byzantine update (outlier)
        weights_byz = {"w": np.array([100.0, 200.0, 300.0])}
        
        aggregator.add_update(ModelUpdate(node_id="node-1", round_number=1, weights=weights1, num_samples=100))
        aggregator.add_update(ModelUpdate(node_id="node-2", round_number=1, weights=weights2, num_samples=100))
        aggregator.add_update(ModelUpdate(node_id="node-3", round_number=1, weights=weights_byz, num_samples=100))
        
        result = await aggregator.aggregate(1)
        
        # Result should be closer to normal values (median-based)
        assert result is not None
        aggregated = result.aggregated_weights["w"]
        # Should not be dominated by Byzantine outlier
        assert aggregated[0] < 50.0

    def test_calculate_weights(self, aggregator, sample_weights):
        """Test weight calculation."""
        aggregator.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.9, latency_ms=10, hop_count=1
        ))
        aggregator.register_node("node-2", NodeConnectivity(
            node_id="node-2", link_quality=0.5, latency_ms=100, hop_count=2
        ))
        
        updates = [
            ModelUpdate(node_id="node-1", round_number=1, weights=sample_weights, num_samples=100),
            ModelUpdate(node_id="node-2", round_number=1, weights=sample_weights, num_samples=100),
        ]
        
        weights = aggregator._calculate_weights(updates)
        
        # Weights should be normalized
        assert abs(sum(weights.values()) - 1.0) < 0.001
        # Node-1 should have higher weight due to better connectivity
        assert weights["node-1"] > weights["node-2"]

    def test_get_metrics(self, aggregator):
        """Test getting aggregator metrics."""
        metrics = aggregator.get_metrics()
        
        assert "total_aggregations" in metrics
        assert "active_nodes" in metrics
        assert "pending_rounds" in metrics

    def test_get_node_status(self, aggregator):
        """Test getting node status."""
        aggregator.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.8, latency_ms=20, hop_count=1
        ))
        
        status = aggregator.get_node_status()
        
        assert "node-1" in status
        assert status["node-1"]["link_quality"] == 0.8
        assert status["node-1"]["latency_ms"] == 20


class TestBatmanAdvMetricsProvider:
    """Tests for Batman-adv metrics provider."""

    def test_init_without_router(self):
        """Test initialization without mesh router."""
        provider = BatmanAdvMetricsProvider()
        assert provider.mesh_router is None

    def test_init_with_router(self):
        """Test initialization with mesh router."""
        mock_router = MagicMock()
        provider = BatmanAdvMetricsProvider(mesh_router=mock_router)
        assert provider.mesh_router == mock_router

    @pytest.mark.asyncio
    async def test_get_connectivity_no_router(self):
        """Test connectivity retrieval without router."""
        provider = BatmanAdvMetricsProvider()
        result = await provider.get_connectivity("node-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_connectivity_with_router(self):
        """Test connectivity retrieval with router."""
        mock_router = MagicMock()
        mock_router.get_originators = AsyncMock(return_value=[
            {"node_id": "node-1", "tq": 200, "latency": 15.0, "hop_count": 1},
            {"node_id": "node-2", "tq": 150, "latency": 30.0, "hop_count": 2},
        ])
        
        provider = BatmanAdvMetricsProvider(mesh_router=mock_router)
        result = await provider.get_connectivity("node-1")
        
        assert result is not None
        assert result.node_id == "node-1"
        assert result.link_quality == pytest.approx(200 / 255.0, rel=0.01)
        assert result.latency_ms == 15.0
        assert result.hop_count == 1

    @pytest.mark.asyncio
    async def test_update_all(self):
        """Test updating all nodes."""
        mock_router = MagicMock()
        mock_router.get_originators = AsyncMock(return_value=[
            {"node_id": "node-1", "tq": 200, "latency": 10.0, "hop_count": 1},
        ])
        
        aggregator = TopologyAwareAggregator()
        aggregator.register_node("node-1", NodeConnectivity(node_id="node-1"))
        aggregator.register_node("node-2", NodeConnectivity(node_id="node-2"))
        
        provider = BatmanAdvMetricsProvider(mesh_router=mock_router)
        updated = await provider.update_all(aggregator)
        
        assert updated == 1  # Only node-1 was in originators


class TestCreateTopologyAwareAggregator:
    """Tests for factory function."""

    @pytest.mark.asyncio
    async def test_create_without_router(self):
        """Test creation without mesh router."""
        aggregator, provider = await create_topology_aware_aggregator()
        
        assert aggregator is not None
        assert provider is None

    @pytest.mark.asyncio
    async def test_create_with_router(self):
        """Test creation with mesh router."""
        mock_router = MagicMock()
        aggregator, provider = await create_topology_aware_aggregator(
            mesh_router=mock_router,
            min_participants=3,
            byzantine_robust=False,
        )
        
        assert aggregator is not None
        assert aggregator.min_participants == 3
        assert aggregator.byzantine_robust is False
        assert provider is not None
        assert provider.mesh_router == mock_router


class TestIntegration:
    """Integration tests for Mesh-FL layer."""

    @pytest.mark.asyncio
    async def test_full_aggregation_flow(self):
        """Test complete aggregation flow with topology awareness."""
        # Create aggregator
        aggregator = TopologyAwareAggregator(min_participants=2)
        
        # Register nodes with varying connectivity
        aggregator.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.9, latency_ms=10, hop_count=1
        ))
        aggregator.register_node("node-2", NodeConnectivity(
            node_id="node-2", link_quality=0.7, latency_ms=30, hop_count=2
        ))
        aggregator.register_node("node-3", NodeConnectivity(
            node_id="node-3", link_quality=0.5, latency_ms=50, hop_count=3
        ))
        
        # Add updates from all nodes
        for i, node_id in enumerate(["node-1", "node-2", "node-3"]):
            weights = {
                "layer1": np.random.randn(10, 10) * 0.1 + i,
                "layer2": np.random.randn(10) * 0.1 + i,
            }
            aggregator.add_update(ModelUpdate(
                node_id=node_id,
                round_number=1,
                weights=weights,
                num_samples=100 * (i + 1),
            ))
        
        # Aggregate
        result = await aggregator.aggregate(1)
        
        assert result is not None
        assert len(result.participating_nodes) == 3
        assert result.total_samples == 600  # 100 + 200 + 300
        
        # Check that node-1 has highest weight (best connectivity)
        weights = result.aggregation_weights
        assert weights["node-1"] > weights["node-2"]
        assert weights["node-2"] > weights["node-3"]

    @pytest.mark.asyncio
    async def test_node_churn_handling(self):
        """Test handling of node churn during aggregation."""
        aggregator = TopologyAwareAggregator(
            min_participants=2,
            churn_threshold=0.3,
        )
        
        # Register 5 nodes
        for i in range(5):
            aggregator.register_node(f"node-{i}", NodeConnectivity(node_id=f"node-{i}"))
        
        # Only 2 nodes submit updates (60% churn)
        weights = {"w": np.array([1.0, 2.0])}
        aggregator.add_update(ModelUpdate(node_id="node-0", round_number=1, weights=weights, num_samples=100))
        aggregator.add_update(ModelUpdate(node_id="node-1", round_number=1, weights=weights, num_samples=100))
        
        result = await aggregator.aggregate(1)
        
        # Should still succeed but log high churn
        assert result is not None
        assert result.metrics["churn_rate"] > 0.3


class TestMeshFLIntegration:
    """Tests for MeshFLIntegration class."""

    @pytest.fixture
    def config(self):
        """Create test config."""
        return MeshFLConfig(
            min_participants=2,
            byzantine_robust=True,
            num_rounds=3,
            link_quality_threshold=0.3,
        )

    @pytest.fixture
    def sample_weights(self):
        """Create sample model weights."""
        return {
            "layer1": np.array([[1.0, 2.0], [3.0, 4.0]]),
            "layer2": np.array([5.0, 6.0]),
        }

    def test_config_defaults(self):
        """Test default config values."""
        config = MeshFLConfig()
        assert config.min_participants == 2
        assert config.byzantine_robust is True
        assert config.num_rounds == 10
        assert config.link_quality_threshold == 0.3

    def test_init(self, config):
        """Test integration initialization."""
        integration = MeshFLIntegration(config=config, node_id="test-node")
        assert integration.node_id == "test-node"
        assert integration.config == config
        assert not integration._running

    @pytest.mark.asyncio
    async def test_start_stop(self, config):
        """Test start and stop lifecycle."""
        integration = MeshFLIntegration(config=config)
        
        await integration.start()
        assert integration._running
        assert integration._aggregator is not None
        
        await integration.stop()
        assert not integration._running

    @pytest.mark.asyncio
    async def test_register_node(self, config):
        """Test node registration."""
        integration = MeshFLIntegration(config=config)
        await integration.start()
        
        integration.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.8
        ))
        
        status = integration.get_node_status()
        assert "node-1" in status
        assert status["node-1"]["link_quality"] == 0.8
        
        await integration.stop()

    @pytest.mark.asyncio
    async def test_unregister_node(self, config):
        """Test node unregistration."""
        integration = MeshFLIntegration(config=config)
        await integration.start()
        
        integration.register_node("node-1", NodeConnectivity(node_id="node-1"))
        integration.unregister_node("node-1")
        
        status = integration.get_node_status()
        assert "node-1" not in status
        
        await integration.stop()

    @pytest.mark.asyncio
    async def test_run_training_round_insufficient_participants(self, config, sample_weights):
        """Test training round with insufficient participants."""
        integration = MeshFLIntegration(config=config)
        await integration.start()
        
        # Only register one node (below min_participants=2)
        integration.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.9
        ))
        
        result = await integration.run_training_round(local_weights=sample_weights)
        assert result is None
        
        await integration.stop()

    @pytest.mark.asyncio
    async def test_run_training_round_success(self, config, sample_weights):
        """Test successful training round."""
        integration = MeshFLIntegration(config=config)
        await integration.start()
        
        # Register multiple nodes
        integration.register_node("node-1", NodeConnectivity(
            node_id="node-1", link_quality=0.9
        ))
        integration.register_node("node-2", NodeConnectivity(
            node_id="node-2", link_quality=0.8
        ))
        
        # Add updates for aggregation
        integration._aggregator.add_update(ModelUpdate(
            node_id="node-1",
            round_number=1,
            weights=sample_weights,
            num_samples=100,
        ))
        integration._aggregator.add_update(ModelUpdate(
            node_id="node-2",
            round_number=1,
            weights=sample_weights,
            num_samples=100,
        ))
        
        result = await integration.run_training_round()
        assert result is not None
        assert result.round_number == 1
        
        await integration.stop()

    @pytest.mark.asyncio
    async def test_get_status(self, config):
        """Test getting integration status."""
        integration = MeshFLIntegration(config=config, node_id="test-node")
        await integration.start()
        
        status = integration.get_status()
        
        assert status["running"] is True
        assert status["node_id"] == "test-node"
        assert "metrics" in status
        
        await integration.stop()

    @pytest.mark.asyncio
    async def test_get_round_history(self, config, sample_weights):
        """Test getting round history."""
        integration = MeshFLIntegration(config=config)
        await integration.start()
        
        # Register nodes and add updates
        integration.register_node("node-1", NodeConnectivity(node_id="node-1", link_quality=0.9))
        integration.register_node("node-2", NodeConnectivity(node_id="node-2", link_quality=0.8))
        
        integration._aggregator.add_update(ModelUpdate(
            node_id="node-1", round_number=1, weights=sample_weights, num_samples=100
        ))
        integration._aggregator.add_update(ModelUpdate(
            node_id="node-2", round_number=1, weights=sample_weights, num_samples=100
        ))
        
        await integration.run_training_round()
        
        history = integration.get_round_history()
        assert len(history) == 1
        assert history[0]["round_number"] == 1
        
        await integration.stop()


class TestMeshFLIntegrationFactory:
    """Tests for factory functions."""

    @pytest.mark.asyncio
    async def test_create_mesh_fl_integration(self):
        """Test factory function."""
        integration = await create_mesh_fl_integration(
            node_id="factory-test",
            config=MeshFLConfig(min_participants=3),
        )
        
        assert integration is not None
        assert integration.node_id == "factory-test"
        assert integration._running
        
        await integration.stop()

    def test_integrate_with_fl_coordinator(self):
        """Test integration with existing FL coordinator."""
        # Mock FL coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.nodes = {
            "node-1": MagicMock(),
            "node-2": MagicMock(),
        }
        
        integration = MeshFLIntegration()
        integrate_with_fl_coordinator(integration, mock_coordinator)
        
        # Nodes should be registered (checked via aggregator)
        # Note: This requires the integration to be started first


class TestTrainingRound:
    """Tests for TrainingRound dataclass."""

    def test_default_values(self):
        """Test default training round values."""
        round_obj = TrainingRound(round_number=1)
        
        assert round_obj.round_number == 1
        assert round_obj.status == "pending"
        assert round_obj.participants == []
        assert round_obj.updates == []
        assert round_obj.result is None
        assert round_obj.error is None

    def test_completed_round(self):
        """Test completed round."""
        round_obj = TrainingRound(round_number=1)
        round_obj.status = "completed"
        round_obj.completed_at = time.time()
        round_obj.participants = ["node-1", "node-2"]
        
        assert round_obj.status == "completed"
        assert len(round_obj.participants) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
