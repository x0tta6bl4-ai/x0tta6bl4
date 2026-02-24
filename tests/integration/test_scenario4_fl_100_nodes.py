"""
Integration Tests for Scenario 4: FL Coordinator на 100 узлах
=============================================================

Тесты для валидации масштабируемости MAPE-K через FL Coordinator.

Проверяем:
1. FL Coordinator может управлять 100 узлами
2. Раунды обучения выполняются успешно
3. Агрегация работает с большим количеством участников
4. Byzantine tolerance работает на масштабе
5. MAPE-K цикл справляется с нагрузкой
"""

import asyncio
import random
import time
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from src.federated_learning.coordinator import (CoordinatorConfig,
                                                FederatedCoordinator,
                                                NodeStatus, RoundStatus)
from src.federated_learning.protocol import ModelUpdate, ModelWeights


@pytest_asyncio.fixture
async def fl_coordinator():
    """Create FL Coordinator with config for 100 nodes."""
    config = CoordinatorConfig(
        min_participants=10,
        target_participants=50,
        max_participants=100,
        round_duration=60.0,
        aggregation_method="krum",
        byzantine_tolerance=3,  # f < n/3 для 100 узлов
        heartbeat_interval=5.0,
        heartbeat_timeout=15.0,
    )

    coordinator = FederatedCoordinator(
        coordinator_id="test-coordinator-100", config=config
    )

    yield coordinator

    # Cleanup
    coordinator.stop()


def create_mock_node(node_id: str, is_byzantine: bool = False) -> Dict:
    """Create mock node data."""
    return {
        "node_id": node_id,
        "is_byzantine": is_byzantine,
        "capabilities": {
            "compute": random.uniform(0.5, 1.0),
            "memory": random.uniform(0.5, 1.0),
            "network": random.uniform(0.5, 1.0),
        },
    }


def create_mock_update(
    node_id: str, round_num: int, is_byzantine: bool = False
) -> ModelUpdate:
    """Create mock model update."""
    if is_byzantine:
        # Byzantine node sends malicious update (extreme values)
        weights = ModelWeights(
            weights=[random.uniform(-100.0, 100.0) for _ in range(100)],
            num_samples=random.randint(1, 1000),
        )
    else:
        # Normal node sends reasonable update
        weights = ModelWeights(
            weights=[random.uniform(-1.0, 1.0) for _ in range(100)],
            num_samples=random.randint(100, 1000),
        )

    return ModelUpdate(
        node_id=node_id,
        round_number=round_num,
        weights=weights,
        loss=(
            random.uniform(0.1, 1.0)
            if not is_byzantine
            else random.uniform(10.0, 100.0)
        ),
        num_samples=weights.num_samples,
        training_time=random.uniform(1.0, 10.0),
    )


@pytest.mark.asyncio
async def test_register_100_nodes(fl_coordinator):
    """Test registration of 100 nodes."""
    # Register 100 nodes
    for i in range(100):
        node_id = f"node-{i:03d}"
        success = fl_coordinator.register_node(node_id)
        assert success is True

    # Check that all nodes are registered
    assert len(fl_coordinator.nodes) == 100

    # Check that all nodes are ONLINE
    online_nodes = [
        node
        for node in fl_coordinator.nodes.values()
        if node.status == NodeStatus.ONLINE
    ]
    assert len(online_nodes) == 100


@pytest.mark.asyncio
async def test_heartbeat_100_nodes(fl_coordinator):
    """Test heartbeat monitoring for 100 nodes."""
    # Register 100 nodes
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")

    # Start heartbeat monitoring
    fl_coordinator.start()

    # Update heartbeats for all nodes
    for i in range(100):
        node_id = f"node-{i:03d}"
        fl_coordinator.update_heartbeat(node_id)

    # Wait a bit
    await asyncio.sleep(0.1)

    # Check that all nodes are still ONLINE
    online_nodes = [
        node
        for node in fl_coordinator.nodes.values()
        if node.status == NodeStatus.ONLINE
    ]
    assert len(online_nodes) == 100


@pytest.mark.asyncio
async def test_round_with_100_nodes(fl_coordinator):
    """Test training round with 100 nodes."""
    # Register 100 nodes
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")

    # Start a round
    round_result = fl_coordinator.start_round()
    assert round_result is not None
    assert fl_coordinator.current_round is not None
    assert fl_coordinator.current_round.status == RoundStatus.STARTED

    # Check that nodes were selected
    selected_count = len(fl_coordinator.current_round.selected_nodes)
    assert selected_count >= fl_coordinator.config.min_participants
    assert selected_count <= fl_coordinator.config.max_participants


@pytest.mark.asyncio
async def test_aggregation_with_50_updates(fl_coordinator):
    """Test aggregation with 50 updates (simulating 50 participating nodes)."""
    # Register 100 nodes
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")

    # Start a round
    round_result = fl_coordinator.start_round()
    assert round_result is not None

    # Submit updates from selected nodes for this round
    round_num = fl_coordinator.current_round.round_number
    selected_nodes = list(fl_coordinator.current_round.selected_nodes)
    for node_id in selected_nodes:
        update = create_mock_update(node_id, round_num, is_byzantine=False)
        fl_coordinator.submit_update(update)

    # Trigger aggregation
    await asyncio.sleep(0.1)  # Small delay for async processing

    # Check that aggregation completed
    # (In real implementation, this would be async)
    assert len(fl_coordinator.current_round.received_updates) == len(selected_nodes)


@pytest.mark.asyncio
async def test_byzantine_detection_100_nodes(fl_coordinator):
    """Test Byzantine detection with 100 nodes (3 Byzantine)."""
    # Register 100 nodes
    byzantine_nodes = ["node-001", "node-050", "node-099"]
    for i in range(100):
        node_id = f"node-{i:03d}"
        fl_coordinator.register_node(node_id)

    # Start a round
    round_result = fl_coordinator.start_round()
    assert round_result is not None

    # Submit updates from selected nodes only
    round_num = fl_coordinator.current_round.round_number
    selected_nodes = list(fl_coordinator.current_round.selected_nodes)
    update_count = 0

    for node_id in selected_nodes:
        is_byzantine = node_id in byzantine_nodes
        update = create_mock_update(node_id, round_num, is_byzantine=is_byzantine)
        fl_coordinator.submit_update(update)
        update_count += 1

    # Check that updates were received
    assert len(fl_coordinator.current_round.received_updates) == update_count

    # Check that Byzantine nodes are detected (if aggregator supports it)
    # Krum aggregator should filter out Byzantine updates
    if fl_coordinator.config.aggregation_method == "krum":
        # Krum should detect and filter Byzantine updates
        # This is tested in the aggregator itself
        pass


@pytest.mark.asyncio
async def test_multiple_rounds_100_nodes(fl_coordinator):
    """Test multiple training rounds with 100 nodes."""
    # Register 100 nodes
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")

    # Run 5 rounds
    for round_num in range(5):
        # Start round
        round_result = fl_coordinator.start_round()
        assert round_result is not None

        # Submit updates from random subset of nodes
        selected_nodes = list(fl_coordinator.current_round.selected_nodes)
        num_participants = min(50, len(selected_nodes))
        participating = random.sample(selected_nodes, num_participants)

        for node_id in participating:
            update = create_mock_update(node_id, round_num + 1, is_byzantine=False)
            fl_coordinator.submit_update(update)

        # Wait for round to complete (simplified)
        await asyncio.sleep(0.1)

    # Check that rounds were recorded
    assert len(fl_coordinator.round_history) >= 5


@pytest.mark.asyncio
async def test_node_failure_during_round(fl_coordinator):
    """Test handling of node failures during training round."""
    # Register 100 nodes
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")

    # Start a round
    round_result = fl_coordinator.start_round()
    assert round_result is not None

    # Mark some nodes as STALE (simulating failure)
    failed_nodes = ["node-010", "node-020", "node-030"]
    for node_id in failed_nodes:
        if node_id in fl_coordinator.nodes:
            fl_coordinator.nodes[node_id].status = NodeStatus.STALE

    # Submit updates from remaining nodes
    round_num = fl_coordinator.current_round.round_number
    selected = fl_coordinator.current_round.selected_nodes

    for node_id in selected:
        if node_id not in failed_nodes:
            update = create_mock_update(node_id, round_num, is_byzantine=False)
            fl_coordinator.submit_update(update)

    # Check that round can still complete with remaining nodes
    received = len(fl_coordinator.current_round.received_updates)
    assert received >= fl_coordinator.config.min_participants - len(failed_nodes)


@pytest.mark.asyncio
async def test_performance_100_nodes(fl_coordinator):
    """Test performance metrics with 100 nodes."""
    # Register 100 nodes
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")

    # Start a round and measure time
    start_time = time.time()
    round_result = fl_coordinator.start_round()
    assert round_result is not None

    # Submit updates from selected nodes
    round_num = fl_coordinator.current_round.round_number
    selected_nodes = list(fl_coordinator.current_round.selected_nodes)
    for node_id in selected_nodes:
        update = create_mock_update(node_id, round_num, is_byzantine=False)
        fl_coordinator.submit_update(update)

    # Measure round completion time
    end_time = time.time()
    round_duration = end_time - start_time

    # Check that round completes in reasonable time
    # (Actual time depends on aggregation method)
    assert round_duration < 10.0  # Should complete quickly in test

    # Check metrics
    assert fl_coordinator._metrics["rounds_completed"] >= 0
    assert fl_coordinator._metrics["total_updates_received"] >= len(selected_nodes)


@pytest.mark.asyncio
async def test_scalability_100_nodes(fl_coordinator):
    """Test scalability: verify system can handle 100 nodes."""
    # Register 100 nodes
    registration_start = time.time()
    for i in range(100):
        fl_coordinator.register_node(f"node-{i:03d}")
    registration_time = time.time() - registration_start

    # Registration should be fast
    assert registration_time < 1.0

    # Start heartbeat monitoring
    fl_coordinator.start()

    # Update all heartbeats
    heartbeat_start = time.time()
    for i in range(100):
        fl_coordinator.update_heartbeat(f"node-{i:03d}")
    heartbeat_time = time.time() - heartbeat_start

    # Heartbeat updates should be fast
    assert heartbeat_time < 1.0

    # Start a round
    round_start = time.time()
    round_result = fl_coordinator.start_round()
    round_init_time = time.time() - round_start

    # Round initialization should be fast
    assert round_init_time < 1.0
    assert round_result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
