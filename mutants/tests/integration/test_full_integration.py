"""
Полная интеграция всех компонентов
"""

import pytest
import asyncio
from src.self_healing.mape_k_integrated import IntegratedMAPEKCycle
from src.chaos.mesh_integration import MeshChaosIntegration
from src.network.ebpf.integration import EBPFProgramIntegration


@pytest.fixture
def integrated_cycle():
    """Fixture для интегрированного цикла"""
    return IntegratedMAPEKCycle(
        enable_observe_mode=True,
        enable_chaos=True,
        enable_ebpf_explainer=True
    )


def test_integrated_cycle_initialization(integrated_cycle):
    """Test инициализация интегрированного цикла"""
    assert integrated_cycle.observe_detector is not None
    assert integrated_cycle.chaos_controller is not None
    assert integrated_cycle.ebpf_explainer is not None


def test_integrated_anomaly_detection(integrated_cycle):
    """Test обнаружение аномалии через интегрированный цикл"""
    metrics = {
        'node_id': 'node-001',
        'cpu_percent': 95.0,
        'memory_percent': 87.0,
        'packet_loss_percent': 7.0,
        'latency_ms': 150.0
    }
    
    result = integrated_cycle.run_cycle(metrics)
    
    assert result['anomaly_detected'] == True
    assert 'analyzer_results' in result
    assert 'planner_results' in result
    assert 'executor_results' in result


def test_chaos_integration():
    """Test интеграция chaos controller с mesh"""
    integration = MeshChaosIntegration()
    assert integration.chaos_controller is not None


def test_ebpf_integration():
    """Test интеграция eBPF explainer"""
    integration = EBPFProgramIntegration()
    assert integration.explainer is not None


@pytest.mark.asyncio
async def test_full_cycle_with_chaos(integrated_cycle):
    """Test полный цикл с chaos experiment"""
    # Запустить chaos experiment
    result = await integrated_cycle.run_chaos_experiment("node_failure", 5)
    
    assert 'mttr' in result
    assert 'recovery_success' in result


def test_system_status(integrated_cycle):
    """Test получение статуса системы"""
    status = integrated_cycle.get_system_status()
    
    assert 'mape_k_cycle' in status
    assert 'observe_mode' in status
    assert 'chaos_engineering' in status
    assert 'ebpf_explainer' in status

