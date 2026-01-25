"""
Tests для Chaos Controller
"""

import pytest
import asyncio
from src.chaos.controller import (
    ChaosController,
    ChaosExperiment,
    ExperimentType,
    RecoveryMetrics
)


@pytest.fixture
def chaos_controller():
    """Fixture для ChaosController"""
    return ChaosController()


@pytest.fixture
def node_failure_experiment():
    """Fixture для node failure experiment"""
    return ChaosExperiment(
        experiment_type=ExperimentType.NODE_FAILURE,
        duration=10,
        target_nodes=["node-001"],
        parameters={}
    )


@pytest.mark.asyncio
async def test_node_failure_experiment(chaos_controller, node_failure_experiment):
    """Test node failure experiment"""
    metrics = await chaos_controller.run_experiment(node_failure_experiment)
    
    assert metrics.experiment_type == ExperimentType.NODE_FAILURE
    assert metrics.mttr > 0
    assert metrics.nodes_affected == 1
    assert isinstance(metrics.recovery_success, bool)


@pytest.mark.asyncio
async def test_network_partition_experiment(chaos_controller):
    """Test network partition experiment"""
    experiment = ChaosExperiment(
        experiment_type=ExperimentType.NETWORK_PARTITION,
        duration=15,
        target_nodes=["node-001", "node-002"],
        parameters={"partition_groups": [["node-001"], ["node-002"]]}
    )
    
    metrics = await chaos_controller.run_experiment(experiment)
    
    assert metrics.experiment_type == ExperimentType.NETWORK_PARTITION
    assert metrics.nodes_affected == 2


@pytest.mark.asyncio
async def test_high_latency_experiment(chaos_controller):
    """Test high latency experiment"""
    experiment = ChaosExperiment(
        experiment_type=ExperimentType.HIGH_LATENCY,
        duration=20,
        target_nodes=[],
        parameters={"latency_ms": 500}
    )
    
    metrics = await chaos_controller.run_experiment(experiment)
    
    assert metrics.experiment_type == ExperimentType.HIGH_LATENCY


def test_recovery_stats(chaos_controller):
    """Test recovery statistics"""
    stats = chaos_controller.get_recovery_stats()
    
    assert 'total_experiments' in stats
    assert 'success_rate' in stats
    assert 'avg_mttr' in stats


def test_experiment_history(chaos_controller):
    """Test experiment history"""
    history = chaos_controller.get_experiment_history()
    
    assert isinstance(history, list)

