"""
Integration Tests for Scenario 4: FL-Mesh Integration
=====================================================

Тесты для проверки интеграции FL Coordinator с реальной mesh network.

Проверяем:
1. FL Workers регистрируются через mesh heartbeat
2. Сбор реальных метрик mesh для обучения
3. Раунды обучения на реальных данных
4. Распределение глобальной модели через mesh
5. Интеграция с MAPE-K циклом
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock
from typing import Dict

from src.federated_learning.coordinator import FederatedCoordinator, CoordinatorConfig
from src.federated_learning.mesh_worker import FLMeshWorker
from src.federated_learning.mesh_integration import (
    FLMeshIntegration,
    MeshNodeInfo,
    create_integration_from_mesh_nodes
)


# Mock mesh components
class MockMeshRouter:
    """Mock MeshRouter for testing."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peers = []
    
    def get_stats(self) -> Dict:
        return {
            "peers": [
                {"latency": 0.05, "node_id": "peer-1"},
                {"latency": 0.08, "node_id": "peer-2"}
            ],
            "routes_cached": 5
        }


class MockMeshShield:
    """Mock MeshShield for testing."""
    
    def get_metrics(self) -> Dict:
        return {
            "quarantines": 0,
            "mttr_avg": 2.5,
            "failures_detected": 0
        }


@pytest_asyncio.fixture
async def fl_coordinator():
    """Create FL Coordinator."""
    config = CoordinatorConfig(
        min_participants=3,
        target_participants=10,
        max_participants=20
    )
    coordinator = FederatedCoordinator("test-coordinator", config)
    yield coordinator
    coordinator.stop()


@pytest_asyncio.fixture
async def mesh_nodes():
    """Create mock mesh nodes."""
    nodes = {}
    for i in range(10):
        node_id = f"node-{i:02d}"
        router = MockMeshRouter(node_id)
        shield = MockMeshShield()
        nodes[node_id] = MeshNodeInfo(
            node_id=node_id,
            mesh_router=router,
            mesh_shield=shield
        )
    return nodes


@pytest.mark.asyncio
async def test_fl_worker_registration(fl_coordinator, mesh_nodes):
    """Test FL Worker registration through mesh."""
    node_info = list(mesh_nodes.values())[0]
    worker = FLMeshWorker(
        node_id=node_info.node_id,
        coordinator=fl_coordinator,
        mesh_router=node_info.mesh_router,
        mesh_shield=node_info.mesh_shield
    )
    
    await worker.start()
    
    # Check registration
    assert node_info.node_id in fl_coordinator.nodes
    assert worker.status.value == "registered"
    
    await worker.stop()


@pytest.mark.asyncio
async def test_metrics_collection(fl_coordinator, mesh_nodes):
    """Test collection of real mesh metrics."""
    node_info = list(mesh_nodes.values())[0]
    worker = FLMeshWorker(
        node_id=node_info.node_id,
        coordinator=fl_coordinator,
        mesh_router=node_info.mesh_router,
        mesh_shield=node_info.mesh_shield
    )
    
    await worker.start()
    
    # Collect metrics
    metrics = await worker._collect_metrics()
    
    assert metrics is not None
    assert metrics.node_id == node_info.node_id
    assert metrics.peers_count >= 0
    assert metrics.latency_ms >= 0
    
    await worker.stop()


@pytest.mark.asyncio
async def test_local_training_on_mesh_metrics(fl_coordinator, mesh_nodes):
    """Test local training on collected mesh metrics."""
    node_info = list(mesh_nodes.values())[0]
    worker = FLMeshWorker(
        node_id=node_info.node_id,
        coordinator=fl_coordinator,
        mesh_router=node_info.mesh_router,
        mesh_shield=node_info.mesh_shield
    )
    
    await worker.start()
    
    # Collect some metrics first
    for _ in range(20):
        metrics = await worker._collect_metrics()
        if metrics:
            worker.metrics_history.append(metrics)
        await asyncio.sleep(0.1)
    
    # Train local model
    update = await worker.train_local_model(round_number=1)
    
    assert update is not None
    assert update.node_id == node_info.node_id
    assert update.round_number == 1
    assert update.weights is not None
    assert len(update.weights.weights) > 0
    
    await worker.stop()


@pytest.mark.asyncio
async def test_mesh_integration_start(fl_coordinator, mesh_nodes):
    """Test FL-Mesh integration startup."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator,
        mesh_nodes=mesh_nodes
    )
    
    await integration.start()
    
    # Check that workers were created
    assert len(integration._workers) == len(mesh_nodes)
    
    # Check that all nodes are registered
    assert len(fl_coordinator.nodes) == len(mesh_nodes)
    
    await integration.stop()


@pytest.mark.asyncio
async def test_training_round_with_mesh_nodes(fl_coordinator, mesh_nodes):
    """Test training round with real mesh nodes."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator,
        mesh_nodes=mesh_nodes
    )
    
    await integration.start()
    
    # Collect metrics on all workers
    for worker in integration._workers.values():
        for _ in range(10):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.1)
    
    # Run training round
    result = await integration.run_training_round()
    
    assert result is not None
    assert result["participants"] > 0
    assert result["updates_received"] > 0
    
    await integration.stop()


@pytest.mark.asyncio
async def test_multiple_rounds_mesh_integration(fl_coordinator, mesh_nodes):
    """Test multiple training rounds with mesh integration."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator,
        mesh_nodes=mesh_nodes
    )
    
    await integration.start()
    
    # Collect metrics
    for worker in integration._workers.values():
        for _ in range(15):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.1)
    
    # Run multiple rounds
    results = await integration.run_multiple_rounds(num_rounds=3)
    
    assert len(results) == 3
    assert all(r["participants"] > 0 for r in results)
    
    await integration.stop()


@pytest.mark.asyncio
async def test_worker_status_reporting(fl_coordinator, mesh_nodes):
    """Test worker status reporting."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator,
        mesh_nodes=mesh_nodes
    )
    
    await integration.start()
    
    # Get worker status
    status = integration.get_worker_status()
    
    assert len(status) == len(mesh_nodes)
    for node_id, worker_status in status.items():
        assert worker_status["node_id"] == node_id
        assert "status" in worker_status
        assert "metrics_count" in worker_status
    
    await integration.stop()


@pytest.mark.asyncio
async def test_coordinator_stats(fl_coordinator, mesh_nodes):
    """Test coordinator statistics."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator,
        mesh_nodes=mesh_nodes
    )
    
    await integration.start()
    
    # Run a round
    for worker in integration._workers.values():
        for _ in range(10):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.1)
    
    await integration.run_training_round()
    
    # Get stats
    stats = integration.get_coordinator_stats()
    
    assert stats["total_nodes"] == len(mesh_nodes)
    assert stats["eligible_nodes"] > 0
    
    await integration.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

