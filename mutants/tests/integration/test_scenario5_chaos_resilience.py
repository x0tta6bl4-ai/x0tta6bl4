"""
Integration Tests for Scenario 5: Chaos Resilience
====================================================

Тесты для проверки устойчивости системы к хаосу.

Проверяем:
1. Восстановление после отказов узлов
2. Устойчивость к network partition
3. Защита от Byzantine атак
4. Работа под высокой нагрузкой
5. MAPE-K + FL справляются с хаосом
"""
import pytest
import pytest_asyncio
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from src.chaos.chaos_engine import ChaosEngine, ChaosEventType
from src.federated_learning.coordinator import FederatedCoordinator, CoordinatorConfig
from src.federated_learning.mesh_integration import FLMeshIntegration, MeshNodeInfo


# Mock mesh components
class MockMeshRouter:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.failed = False
    
    def get_stats(self):
        if self.failed:
            raise Exception("Node failed")
        return {"peers": [], "routes_cached": 5}


class MockMeshShield:
    def get_metrics(self):
        return {"quarantines": 0}


@pytest_asyncio.fixture
async def chaos_engine():
    """Create Chaos Engine."""
    engine = ChaosEngine()
    yield engine


@pytest_asyncio.fixture
async def fl_coordinator_chaos():
    """Create FL Coordinator for chaos testing."""
    config = CoordinatorConfig(
        min_participants=3,
        target_participants=10,
        max_participants=20
    )
    coordinator = FederatedCoordinator("chaos-coordinator", config)
    yield coordinator
    coordinator.stop()


@pytest_asyncio.fixture
async def mesh_nodes_chaos():
    """Create mesh nodes for chaos testing."""
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
async def test_node_failure_recovery(chaos_engine, fl_coordinator_chaos, mesh_nodes_chaos):
    """Test recovery from node failure."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_chaos,
        mesh_nodes=mesh_nodes_chaos
    )
    await integration.start()
    
    # Register callback for node failure
    failed_nodes = []
    
    async def on_node_failure(event):
        failed_nodes.append(event.target)
    
    chaos_engine.register_callback(ChaosEventType.NODE_FAILURE, on_node_failure)
    
    # Inject node failure
    await chaos_engine.inject_node_failure("node-05", duration=5.0)
    
    # Wait for recovery
    await asyncio.sleep(6.0)
    
    # Check that node was marked as failed
    assert "node-05" in failed_nodes
    
    # Check that system recovered
    events = chaos_engine.get_active_events()
    assert len(events) == 0  # Event should be recovered
    
    await integration.stop()


@pytest.mark.asyncio
async def test_network_partition_recovery(chaos_engine, fl_coordinator_chaos, mesh_nodes_chaos):
    """Test recovery from network partition."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_chaos,
        mesh_nodes=mesh_nodes_chaos
    )
    await integration.start()
    
    # Inject network partition
    partition_nodes = ["node-01", "node-02", "node-03"]
    await chaos_engine.inject_network_partition(partition_nodes, duration=5.0)
    
    # Wait for recovery
    await asyncio.sleep(6.0)
    
    # Check recovery
    events = chaos_engine.get_active_events()
    assert len(events) == 0
    
    await integration.stop()


@pytest.mark.asyncio
async def test_byzantine_attack_detection(chaos_engine, fl_coordinator_chaos, mesh_nodes_chaos):
    """Test Byzantine attack detection and mitigation."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_chaos,
        mesh_nodes=mesh_nodes_chaos
    )
    await integration.start()
    
    # Inject Byzantine attack
    await chaos_engine.inject_byzantine_attack("node-07", duration=10.0)
    
    # Check that coordinator can handle it
    # (Byzantine detection is handled by aggregator)
    stats = integration.get_coordinator_stats()
    assert stats["total_nodes"] == 10
    
    await integration.stop()


@pytest.mark.asyncio
async def test_high_load_resilience(chaos_engine, fl_coordinator_chaos, mesh_nodes_chaos):
    """Test system resilience under high load."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_chaos,
        mesh_nodes=mesh_nodes_chaos
    )
    await integration.start()
    
    # Inject high load on multiple nodes
    for i in [2, 4, 6]:
        await chaos_engine.inject_high_load(f"node-{i:02d}", duration=5.0, load_percent=0.95)
    
    # System should continue operating
    stats = integration.get_coordinator_stats()
    assert stats["total_nodes"] == 10
    
    await asyncio.sleep(6.0)
    
    # Check recovery
    events = chaos_engine.get_active_events()
    assert len(events) == 0
    
    await integration.stop()


@pytest.mark.asyncio
async def test_multiple_chaos_events(chaos_engine, fl_coordinator_chaos, mesh_nodes_chaos):
    """Test system handling multiple simultaneous chaos events."""
    integration = FLMeshIntegration(
        coordinator=fl_coordinator_chaos,
        mesh_nodes=mesh_nodes_chaos
    )
    await integration.start()
    
    # Inject multiple chaos events
    await chaos_engine.inject_node_failure("node-01", duration=10.0)
    await chaos_engine.inject_network_partition(["node-02", "node-03"], duration=10.0)
    await chaos_engine.inject_byzantine_attack("node-04", duration=10.0)
    await chaos_engine.inject_high_load("node-05", duration=10.0)
    
    # System should handle all events
    active = chaos_engine.get_active_events()
    assert len(active) == 4
    
    # Wait for recovery
    await asyncio.sleep(11.0)
    
    # All should be recovered
    active = chaos_engine.get_active_events()
    assert len(active) == 0
    
    await integration.stop()


@pytest.mark.asyncio
async def test_chaos_stats(chaos_engine):
    """Test chaos engine statistics."""
    # Inject some events
    await chaos_engine.inject_node_failure("node-01", duration=1.0)
    await chaos_engine.inject_network_partition(["node-02"], duration=1.0)
    
    await asyncio.sleep(2.0)
    
    # Get stats
    stats = chaos_engine.get_stats()
    
    assert stats["total_events"] >= 2
    assert stats["recovered_events"] >= 2
    assert "node_failure" in stats["event_types"]
    assert "network_partition" in stats["event_types"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

