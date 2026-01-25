"""
Tests for Digital Twins Simulator
"""
import pytest
import asyncio
from src.testing.digital_twins import (
    DigitalTwinsSimulator,
    ChaosScenario,
    DigitalTwinNode,
    ChaosTestResult
)


@pytest.fixture
def simulator():
    """Fixture для DigitalTwinsSimulator"""
    return DigitalTwinsSimulator(node_count=10)


@pytest.mark.asyncio
async def test_simulator_initialization(simulator):
    """Тест инициализации симулятора"""
    assert simulator is not None
    assert len(simulator.nodes) == 10
    assert all(isinstance(node, DigitalTwinNode) for node in simulator.nodes.values())


@pytest.mark.asyncio
async def test_chaos_test_node_down(simulator):
    """Тест chaos-теста: отключение узлов"""
    result = await simulator.run_chaos_test(
        scenario=ChaosScenario.NODE_DOWN,
        intensity=0.3,
        duration=10.0
    )
    
    assert result is not None
    assert isinstance(result, ChaosTestResult)
    assert result.scenario == ChaosScenario.NODE_DOWN
    assert 0.0 <= result.intensity <= 1.0
    assert result.recovery_time >= 0.0
    assert isinstance(result.success, bool)


@pytest.mark.asyncio
async def test_chaos_test_link_failure(simulator):
    """Тест chaos-теста: отказ связей"""
    result = await simulator.run_chaos_test(
        scenario=ChaosScenario.LINK_FAILURE,
        intensity=0.2,
        duration=10.0
    )
    
    assert result is not None
    assert result.scenario == ChaosScenario.LINK_FAILURE


@pytest.mark.asyncio
async def test_chaos_test_ddos(simulator):
    """Тест chaos-теста: DDoS"""
    result = await simulator.run_chaos_test(
        scenario=ChaosScenario.DDOS,
        intensity=0.4,
        duration=10.0
    )
    
    assert result is not None
    assert result.scenario == ChaosScenario.DDOS


@pytest.mark.asyncio
async def test_chaos_test_byzantine(simulator):
    """Тест chaos-теста: византийские узлы"""
    result = await simulator.run_chaos_test(
        scenario=ChaosScenario.BYZANTINE,
        intensity=0.1,
        duration=10.0
    )
    
    assert result is not None
    assert result.scenario == ChaosScenario.BYZANTINE


@pytest.mark.asyncio
async def test_chaos_test_resource_exhaustion(simulator):
    """Тест chaos-теста: исчерпание ресурсов"""
    result = await simulator.run_chaos_test(
        scenario=ChaosScenario.RESOURCE_EXHAUSTION,
        intensity=0.3,
        duration=10.0
    )
    
    assert result is not None
    assert result.scenario == ChaosScenario.RESOURCE_EXHAUSTION


def test_collect_metrics(simulator):
    """Тест сбора метрик"""
    metrics = simulator._collect_metrics()
    
    assert metrics is not None
    assert 'total_nodes' in metrics
    assert 'healthy_nodes' in metrics
    assert 'avg_cpu' in metrics
    assert 'avg_memory' in metrics
    assert 'avg_latency' in metrics
    assert 'network_health' in metrics


def test_get_chaos_statistics(simulator):
    """Тест получения статистики"""
    stats = simulator.get_chaos_statistics()
    
    # До запуска тестов статистика может быть пустой
    assert stats is not None
    assert isinstance(stats, dict)


@pytest.mark.asyncio
async def test_multiple_chaos_tests(simulator):
    """Тест множественных chaos-тестов"""
    results = []
    
    for scenario in [ChaosScenario.NODE_DOWN, ChaosScenario.LINK_FAILURE]:
        result = await simulator.run_chaos_test(scenario, 0.2, 5.0)
        results.append(result)
    
    assert len(results) == 2
    assert all(isinstance(r, ChaosTestResult) for r in results)
    
    # Проверяем статистику
    stats = simulator.get_chaos_statistics()
    assert stats['total_tests'] >= 2

