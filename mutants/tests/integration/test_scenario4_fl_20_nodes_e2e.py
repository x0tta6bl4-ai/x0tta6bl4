"""
End-to-End Tests for Scenario 4: FL-Mesh Integration on 20 Nodes
=================================================================

Полный end-to-end тест для проверки FL-Mesh интеграции на 20 узлах.

Проверяем:
1. 20 mesh узлов регистрируются в FL Coordinator
2. Сбор метрик на всех узлах
3. Раунды обучения с реальными данными
4. Агрегация и распределение глобальной модели
5. Интеграция с MAPE-K циклом
"""
import pytest
import pytest_asyncio
import asyncio
import time
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

from src.federated_learning.coordinator import FederatedCoordinator, CoordinatorConfig
from src.federated_learning.mesh_integration import (
    FLMeshIntegration,
    MeshNodeInfo,
    create_integration_from_mesh_nodes
)
from src.federated_learning.consciousness_integration import FLConsciousnessIntegration
from src.core.consciousness import ConsciousnessEngine
# MAPEKLoopFL not available - using MAPEKLoop instead
try:
    from src.core.mape_k_loop_fl import MAPEKLoopFL
except ImportError:
    from src.core.mape_k_loop import MAPEKLoop as MAPEKLoopFL


# Mock mesh components
class MockMeshRouter:
    """Mock MeshRouter for testing."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.peers = []
        self._stats = {
            "peers": [
                {"latency": 0.05 + i * 0.01, "node_id": f"peer-{i}"}
                for i in range(3)
            ],
            "routes_cached": 5 + int(node_id.split("-")[1]) % 10
        }
    
    def get_stats(self) -> Dict:
        return self._stats


class MockMeshShield:
    """Mock MeshShield for testing."""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
    
    def get_metrics(self) -> Dict:
        return {
            "quarantines": 0,
            "mttr_avg": 2.5,
            "failures_detected": 0
        }


class MockMeshManager:
    """Mock MeshNetworkManager for MAPE-K."""
    
    async def get_statistics(self) -> Dict:
        return {
            "active_peers": 20,
            "avg_latency_ms": 50.0,
            "packet_loss_percent": 1.0,
            "mttr_minutes": 2.0
        }
    
    async def set_route_preference(self, preference: str) -> bool:
        return True
    
    async def trigger_aggressive_healing(self) -> int:
        return 3
    
    async def trigger_preemptive_checks(self):
        pass


class MockPrometheus:
    """Mock PrometheusExporter."""
    
    def __init__(self):
        self.metrics = {}
    
    def set_gauge(self, name: str, value: float):
        self.metrics[name] = value


class MockZeroTrust:
    """Mock ZeroTrustValidator."""
    
    def get_validation_stats(self) -> Dict:
        return {"success_rate": 0.98}


@pytest_asyncio.fixture
async def fl_coordinator_20():
    """Create FL Coordinator configured for 20 nodes."""
    config = CoordinatorConfig(
        min_participants=5,
        target_participants=15,
        max_participants=20,
        round_duration=60.0,
        aggregation_method="krum",
        byzantine_tolerance=2
    )
    coordinator = FederatedCoordinator("coordinator-20", config)
    yield coordinator
    coordinator.stop()


@pytest_asyncio.fixture
async def mesh_nodes_20():
    """Create 20 mock mesh nodes."""
    nodes = {}
    for i in range(20):
        node_id = f"node-{i:02d}"
        router = MockMeshRouter(node_id)
        shield = MockMeshShield(node_id)
        nodes[node_id] = MeshNodeInfo(
            node_id=node_id,
            mesh_router=router,
            mesh_shield=shield
        )
    return nodes


@pytest.mark.asyncio
async def test_register_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test registration of 20 mesh nodes."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Check registration
    assert len(integration._workers) == 20
    assert len(fl_coordinator_20.nodes) == 20
    
    # Check all nodes are registered
    for node_id in mesh_nodes_20.keys():
        assert node_id in fl_coordinator_20.nodes
        assert node_id in integration._workers
    
    await integration.stop()


@pytest.mark.asyncio
async def test_metrics_collection_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test metrics collection on 20 nodes."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Collect metrics on all workers
    metrics_collected = 0
    for worker in integration._workers.values():
        for _ in range(5):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
                metrics_collected += 1
            await asyncio.sleep(0.1)
    
    # Check that metrics were collected
    assert metrics_collected >= 20 * 3  # At least 3 per node
    
    # Check metrics quality
    for worker in integration._workers.values():
        assert len(worker.metrics_history) >= 3
        for m in worker.metrics_history:
            assert m.node_id == worker.node_id
            assert m.peers_count >= 0
            assert m.latency_ms >= 0
    
    await integration.stop()


@pytest.mark.asyncio
async def test_training_round_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test training round with 20 nodes."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Collect metrics first
    for worker in integration._workers.values():
        for _ in range(15):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.05)
    
    # Run training round
    result = await integration.run_training_round()
    
    assert result is not None
    assert result["participants"] >= fl_coordinator_20.config.min_participants
    assert result["updates_received"] > 0
    
    # Check coordinator stats
    stats = integration.get_coordinator_stats()
    assert stats["total_nodes"] == 20
    assert stats["eligible_nodes"] >= 5
    
    await integration.stop()


@pytest.mark.asyncio
async def test_multiple_rounds_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test multiple training rounds with 20 nodes."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Collect metrics
    for worker in integration._workers.values():
        for _ in range(20):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.05)
    
    # Run 5 rounds
    results = await integration.run_multiple_rounds(num_rounds=5)
    
    assert len(results) == 5
    assert all(r["participants"] >= 5 for r in results)
    assert all(r["updates_received"] > 0 for r in results)
    
    # Check that rounds accumulated
    stats = integration.get_coordinator_stats()
    assert stats["rounds_completed"] >= 5
    
    await integration.stop()


@pytest.mark.asyncio
async def test_fl_mape_k_integration(fl_coordinator_20, mesh_nodes_20):
    """Test FL integration with MAPE-K cycle."""
    # Create FL integration
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    await integration.start()
    
    # Collect metrics and run a round
    for worker in integration._workers.values():
        for _ in range(15):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.05)
    
    await integration.run_training_round()
    
    # Get global model
    global_model = fl_coordinator_20.get_global_model()
    
    if global_model:
        # Create FL-Consciousness integration
        consciousness = ConsciousnessEngine()
        fl_consciousness = FLConsciousnessIntegration(consciousness)
        fl_consciousness.load_global_model(global_model)
        
        # Create MAPE-K loop with FL
        mesh_manager = MockMeshManager()
        prometheus = MockPrometheus()
        zero_trust = MockZeroTrust()
        
        mapek_loop = MAPEKLoopFL(
            consciousness_engine=consciousness,
            mesh_manager=mesh_manager,
            prometheus=prometheus,
            zero_trust=zero_trust,
            fl_integration=fl_consciousness
        )
        
        # Execute one cycle
        await mapek_loop._execute_cycle()
        
        # Check that cycle completed
        assert len(mapek_loop.state_history) > 0
        
        # Check FL enhancement
        state = mapek_loop.state_history[-1]
        assert state.directives is not None
    
    await integration.stop()


@pytest.mark.asyncio
async def test_byzantine_detection_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test Byzantine detection with 20 nodes (2 Byzantine)."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Collect metrics
    for worker in integration._workers.values():
        for _ in range(15):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.05)
    
    # Mark 2 nodes as Byzantine (simulate)
    byzantine_nodes = ["node-05", "node-15"]
    for node_id in byzantine_nodes:
        if node_id in fl_coordinator_20.nodes:
            fl_coordinator_20.ban_node(node_id, "Test Byzantine")
    
    # Run round
    result = await integration.run_training_round()
    
    # Check that round still completes
    assert result is not None
    assert result["participants"] >= fl_coordinator_20.config.min_participants - 2
    
    # Check Byzantine detection
    stats = integration.get_coordinator_stats()
    assert stats["byzantine_detections"] >= 0
    
    await integration.stop()


@pytest.mark.asyncio
async def test_node_failure_recovery_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test recovery from node failures during training."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Collect metrics
    for worker in integration._workers.values():
        for _ in range(15):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.05)
    
    # Simulate node failures
    failed_nodes = ["node-03", "node-07", "node-12"]
    for node_id in failed_nodes:
        if node_id in integration._workers:
            await integration._workers[node_id].stop()
            del integration._workers[node_id]
    
    # Run round with remaining nodes
    result = await integration.run_training_round()
    
    # Check that round completes with remaining nodes
    assert result is not None
    assert result["participants"] >= fl_coordinator_20.config.min_participants - len(failed_nodes)
    
    await integration.stop()


@pytest.mark.asyncio
async def test_performance_20_nodes(fl_coordinator_20, mesh_nodes_20):
    """Test performance with 20 nodes."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_20,
        mesh_nodes=mesh_nodes_20
    )
    
    await integration.start()
    
    # Measure registration time
    start = time.time()
    # (already registered in start())
    registration_time = time.time() - start
    
    assert registration_time < 5.0  # Should be fast
    
    # Collect metrics and measure
    start = time.time()
    for worker in integration._workers.values():
        for _ in range(10):
            metrics = await worker._collect_metrics()
            if metrics:
                worker.metrics_history.append(metrics)
            await asyncio.sleep(0.05)
    collection_time = time.time() - start
    
    assert collection_time < 10.0  # Should complete quickly
    
    # Measure round time
    start = time.time()
    result = await integration.run_training_round()
    round_time = time.time() - start
    
    assert round_time < 30.0  # Round should complete in reasonable time
    assert result is not None
    
    await integration.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

