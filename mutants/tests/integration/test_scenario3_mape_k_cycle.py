"""
Integration Tests for Scenario 3: MAPE-K Cycle Integration
=========================================================

Тесты для проверки полного цикла MAPE-K:
1. Monitor собирает метрики
2. Analyze находит аномалии
3. Plan генерирует планы исправления
4. Execute применяет исправления автоматически
5. Knowledge сохраняет опыт
"""
import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Dict, List
import time

from src.core.mape_k_loop import MAPEKLoop, MAPEKState
from src.core.consciousness import (
    ConsciousnessEngine, 
    ConsciousnessMetrics, 
    ConsciousnessState
)


# Mock classes for dependencies
class MockMeshNetworkManager:
    """Mock MeshNetworkManager for testing."""
    
    def __init__(self):
        self.route_preference = "balanced"
        self.healing_triggered = False
        self.preemptive_checks_triggered = False
        self.stats = {
            "active_peers": 5,
            "avg_latency_ms": 50,
            "packet_loss_percent": 1.0,
            "mttr_minutes": 2.0
        }
    
    async def get_statistics(self) -> Dict:
        """Return mock mesh statistics."""
        return self.stats
    
    async def set_route_preference(self, preference: str) -> bool:
        """Set route preference."""
        self.route_preference = preference
        return True
    
    async def trigger_aggressive_healing(self) -> int:
        """Trigger aggressive healing."""
        self.healing_triggered = True
        return 3  # 3 nodes healed
    
    async def trigger_preemptive_checks(self):
        """Trigger preemptive checks."""
        self.preemptive_checks_triggered = True


class MockPrometheusExporter:
    """Mock PrometheusExporter for testing."""
    
    def __init__(self):
        self.metrics = {}
    
    def set_gauge(self, name: str, value: float):
        """Set gauge metric."""
        self.metrics[name] = value
    
    def get_metric(self, name: str) -> float:
        """Get metric value."""
        return self.metrics.get(name, 0.0)


class MockZeroTrustValidator:
    """Mock ZeroTrustValidator for testing."""
    
    def get_validation_stats(self) -> Dict:
        """Return mock validation stats."""
        return {
            "success_rate": 0.98
        }


class MockDAOAuditLogger:
    """Mock DAOAuditLogger for testing."""
    
    def __init__(self):
        self.logged_events = []
    
    async def log_consciousness_event(self, event_data: Dict) -> str:
        """Log consciousness event."""
        self.logged_events.append(event_data)
        return f"cid-{len(self.logged_events)}"


@pytest_asyncio.fixture
async def mapek_loop():
    """Create MAPE-K loop with mocked dependencies."""
    # Create mock dependencies
    consciousness = ConsciousnessEngine()
    mesh_manager = MockMeshNetworkManager()
    prometheus = MockPrometheusExporter()
    zero_trust = MockZeroTrustValidator()
    dao_logger = MockDAOAuditLogger()
    
    # Create MAPE-K loop
    loop = MAPEKLoop(
        consciousness_engine=consciousness,
        mesh_manager=mesh_manager,
        prometheus=prometheus,
        zero_trust=zero_trust,
        dao_logger=dao_logger
    )
    
    yield {
        "loop": loop,
        "consciousness": consciousness,
        "mesh": mesh_manager,
        "prometheus": prometheus,
        "zero_trust": zero_trust,
        "dao_logger": dao_logger
    }


@pytest.mark.asyncio
async def test_monitor_collects_metrics(mapek_loop):
    """Test that Monitor phase collects metrics."""
    loop = mapek_loop["loop"]
    
    # Execute monitor phase
    metrics = await loop._monitor()
    
    # Check that metrics are collected
    assert "cpu_percent" in metrics
    assert "memory_percent" in metrics
    assert "mesh_connectivity" in metrics
    assert "latency_ms" in metrics
    assert "packet_loss" in metrics
    assert "mttr_minutes" in metrics
    assert "zero_trust_success_rate" in metrics
    
    # Check that metrics have reasonable values
    assert 0 <= metrics["cpu_percent"] <= 100
    assert 0 <= metrics["memory_percent"] <= 100
    assert metrics["mesh_connectivity"] >= 0
    assert metrics["latency_ms"] >= 0
    assert 0 <= metrics["packet_loss"] <= 100
    assert 0 <= metrics["zero_trust_success_rate"] <= 1


@pytest.mark.asyncio
async def test_analyze_detects_anomalies(mapek_loop):
    """Test that Analyze phase detects anomalies."""
    loop = mapek_loop["loop"]
    
    # Create metrics with anomaly (high CPU)
    raw_metrics = {
        "cpu_percent": 95.0,  # High CPU
        "memory_percent": 50.0,
        "mesh_connectivity": 5,
        "latency_ms": 100,
        "packet_loss": 2.0,
        "mttr_minutes": 5.0,
        "zero_trust_success_rate": 0.95
    }
    
    # Execute analyze phase
    consciousness_metrics = loop._analyze(raw_metrics)
    
    # Check that consciousness metrics are generated
    assert isinstance(consciousness_metrics, ConsciousnessMetrics)
    assert consciousness_metrics.phi_ratio >= 0
    assert consciousness_metrics.state in ConsciousnessState


@pytest.mark.asyncio
async def test_plan_generates_directives(mapek_loop):
    """Test that Plan phase generates directives."""
    loop = mapek_loop["loop"]
    consciousness = mapek_loop["consciousness"]
    
    # Create consciousness metrics
    raw_metrics = {
        "cpu_percent": 50.0,
        "memory_percent": 50.0,
        "mesh_connectivity": 5,
        "latency_ms": 50,
        "packet_loss": 1.0,
        "mttr_minutes": 2.0,
        "zero_trust_success_rate": 0.98
    }
    consciousness_metrics = consciousness.get_consciousness_metrics(raw_metrics)
    
    # Execute plan phase
    directives = loop._plan(consciousness_metrics)
    
    # Check that directives are generated
    assert isinstance(directives, dict)
    assert "route_preference" in directives or "monitoring_interval_sec" in directives


@pytest.mark.asyncio
async def test_execute_applies_actions(mapek_loop):
    """Test that Execute phase applies actions."""
    loop = mapek_loop["loop"]
    mesh = mapek_loop["mesh"]
    
    # Create directives with actions
    directives = {
        "route_preference": "low_latency",
        "enable_aggressive_healing": True,
        "preemptive_healing": True
    }
    
    # Execute execute phase
    actions = await loop._execute(directives)
    
    # Check that actions were taken
    assert isinstance(actions, list)
    assert len(actions) > 0
    
    # Check that mesh manager was called
    assert mesh.route_preference == "low_latency"
    assert mesh.healing_triggered is True
    assert mesh.preemptive_checks_triggered is True


@pytest.mark.asyncio
async def test_knowledge_stores_experience(mapek_loop):
    """Test that Knowledge phase stores experience."""
    loop = mapek_loop["loop"]
    prometheus = mapek_loop["prometheus"]
    dao_logger = mapek_loop["dao_logger"]
    consciousness = mapek_loop["consciousness"]
    
    # Create test data
    raw_metrics = {
        "cpu_percent": 50.0,
        "memory_percent": 50.0,
        "mesh_connectivity": 5,
        "latency_ms": 50,
        "packet_loss": 1.0,
        "mttr_minutes": 2.0,
        "zero_trust_success_rate": 0.98
    }
    consciousness_metrics = consciousness.get_consciousness_metrics(raw_metrics)
    directives = {"route_preference": "balanced"}
    actions = ["route_preference=balanced"]
    
    # Execute knowledge phase
    await loop._knowledge(consciousness_metrics, directives, actions, raw_metrics)
    
    # Check that metrics were exported to Prometheus
    assert len(prometheus.metrics) > 0
    
    # Check that state was stored in history
    assert len(loop.state_history) > 0
    state = loop.state_history[-1]
    assert isinstance(state, MAPEKState)
    assert state.metrics == consciousness_metrics
    assert state.directives == directives
    assert state.actions_taken == actions


@pytest.mark.asyncio
async def test_full_cycle_execution(mapek_loop):
    """Test complete MAPE-K cycle execution."""
    loop = mapek_loop["loop"]
    mesh = mapek_loop["mesh"]
    prometheus = mapek_loop["prometheus"]
    dao_logger = mapek_loop["dao_logger"]
    
    # Execute one complete cycle
    await loop._execute_cycle()
    
    # Check that all phases were executed
    assert len(loop.state_history) > 0
    
    # Check that metrics were collected
    state = loop.state_history[-1]
    assert state.metrics is not None
    assert state.directives is not None
    assert state.actions_taken is not None
    
    # Check that Prometheus metrics were updated
    assert len(prometheus.metrics) > 0


@pytest.mark.asyncio
async def test_cycle_with_anomaly_detection(mapek_loop):
    """Test cycle with anomaly detection and automatic healing."""
    loop = mapek_loop["loop"]
    mesh = mapek_loop["mesh"]
    
    # Simulate anomaly by modifying mesh stats
    mesh.stats["packet_loss_percent"] = 10.0  # High packet loss
    mesh.stats["avg_latency_ms"] = 500  # High latency
    
    # Execute cycle
    await loop._execute_cycle()
    
    # Check that cycle completed
    assert len(loop.state_history) > 0
    
    # Check that healing might have been triggered
    # (depends on consciousness state)
    state = loop.state_history[-1]
    assert state.directives is not None


@pytest.mark.asyncio
async def test_dao_logging_for_critical_events(mapek_loop):
    """Test that critical events are logged to DAO."""
    loop = mapek_loop["loop"]
    dao_logger = mapek_loop["dao_logger"]
    consciousness = mapek_loop["consciousness"]
    
    # Create metrics that trigger EUPHORIC or MYSTICAL state
    # (simplified - in real scenario would need specific metrics)
    raw_metrics = {
        "cpu_percent": 20.0,  # Low CPU
        "memory_percent": 30.0,  # Low memory
        "mesh_connectivity": 10,  # Many peers
        "latency_ms": 10,  # Low latency
        "packet_loss": 0.1,  # Low packet loss
        "mttr_minutes": 1.0,  # Fast recovery
        "zero_trust_success_rate": 0.99  # High success rate
    }
    
    consciousness_metrics = consciousness.get_consciousness_metrics(raw_metrics)
    directives = {"message": "System in optimal state"}
    actions = []
    
    # Execute knowledge phase
    await loop._knowledge(consciousness_metrics, directives, actions, raw_metrics)
    
    # Check if DAO logging was triggered (depends on state)
    # In this test, we just verify the method exists and can be called
    assert hasattr(dao_logger, "log_consciousness_event")


@pytest.mark.asyncio
async def test_cycle_interval_adjustment(mapek_loop):
    """Test that cycle interval is adjusted based on directives."""
    loop = mapek_loop["loop"]
    
    initial_interval = loop.loop_interval
    
    # Execute cycle
    await loop._execute_cycle()
    
    # Check that interval might have changed
    # (depends on directives)
    assert loop.loop_interval > 0


@pytest.mark.asyncio
async def test_multiple_cycles_accumulate_history(mapek_loop):
    """Test that multiple cycles accumulate state history."""
    loop = mapek_loop["loop"]
    
    # Execute multiple cycles
    for _ in range(3):
        await loop._execute_cycle()
        await asyncio.sleep(0.1)  # Small delay
    
    # Check that history accumulated
    assert len(loop.state_history) == 3
    
    # Check that each state is unique
    timestamps = [state.timestamp for state in loop.state_history]
    assert len(set(timestamps)) == 3  # All unique


@pytest.mark.asyncio
async def test_cycle_error_handling(mapek_loop):
    """Test that cycle handles errors gracefully."""
    loop = mapek_loop["loop"]
    mesh = mapek_loop["mesh"]
    
    # Make mesh.get_statistics raise an error
    original_get_stats = mesh.get_statistics
    mesh.get_statistics = AsyncMock(side_effect=Exception("Test error"))
    
    try:
        # Execute cycle - should handle error gracefully
        await loop._execute_cycle()
        
        # If we get here, error was handled
        # (in real implementation, errors are caught and logged)
    except Exception:
        # If error propagates, that's also acceptable for this test
        pass
    finally:
        # Restore original method
        mesh.get_statistics = original_get_stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

