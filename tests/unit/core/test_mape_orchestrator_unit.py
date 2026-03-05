"""Unit tests for src/core/mape_orchestrator.py - MAPEOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import os

from src.core.mape_orchestrator import (
    MAPEOrchestrator,
    HealingAction,
    HealingActionType,
    AlertSeverity,
    CircuitBreaker,
    SystemState,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""
    
    @pytest.fixture
    def breaker(self):
        """Create circuit breaker with test config."""
        return CircuitBreaker(
            failure_threshold=3,
            recovery_timeout_seconds=0.1,
            half_open_max_calls=2
        )
    
    def test_initial_state_closed(self, breaker):
        """Test initial state is closed."""
        assert breaker.get_state() == "closed"
        assert not breaker.is_open
    
    @pytest.mark.asyncio
    async def test_opens_after_failures(self, breaker):
        """Test circuit opens after threshold failures."""
        for _ in range(3):
            await breaker.record_failure()
        
        assert breaker.get_state() == "open"
        assert breaker.is_open
    
    @pytest.mark.asyncio
    async def test_success_resets_failures(self, breaker):
        """Test success resets failure count."""
        await breaker.record_failure()
        await breaker.record_failure()
        await breaker.record_success()
        
        assert breaker.get_state() == "closed"
        assert not breaker.is_open
    
    @pytest.mark.asyncio
    async def test_recovery_timeout(self, breaker):
        """Test recovery after timeout."""
        # Trigger failure
        await breaker.record_failure()
        await breaker.record_failure()
        await breaker.record_failure()
        
        assert breaker.get_state() == "open"
        
        # Wait for recovery timeout
        import asyncio
        await asyncio.sleep(0.15)
        
        # Should transition to half-open (not fully closed yet)
        assert not breaker.is_open


class TestHealingAction:
    """Tests for HealingAction dataclass."""
    
    def test_healing_action_creation(self):
        """Test creating healing action."""
        action = HealingAction(
            action_type=HealingActionType.RE_ROUTE,
            target="mesh-network",
            reason="High latency detected",
            severity=AlertSeverity.WARNING,
            estimated_impact=0.5
        )
        
        assert action.action_type == HealingActionType.RE_ROUTE
        assert action.target == "mesh-network"
        assert action.severity == AlertSeverity.WARNING
        assert action.estimated_impact == 0.5
    
    def test_healing_action_default_values(self):
        """Test default values."""
        action = HealingAction(
            action_type=HealingActionType.NONE,
            target="test",
            reason="test"
        )
        
        assert action.severity == AlertSeverity.WARNING
        assert action.estimated_impact == 0.0


class TestMAPEOrchestrator:
    """Tests for MAPEOrchestrator class."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock clients."""
        prometheus = MagicMock()
        prometheus.query = AsyncMock(return_value={
            "latency_p95_value": 50,
            "packet_loss_value": 0.5,
            "cpu_usage_value": 40,
            "memory_usage_value": 50,
        })
        
        mesh = MagicMock()
        mesh.apply_routing = AsyncMock()
        
        dao = MagicMock()
        dao.log_event = AsyncMock()
        
        ipfs = MagicMock()
        ipfs.snapshot = AsyncMock()
        
        return prometheus, mesh, dao, ipfs
    
    @pytest.fixture
    def orchestrator(self, mock_clients):
        """Create orchestrator with mock clients."""
        prometheus, mesh, dao, ipfs = mock_clients
        # Set environment to non-production for testing
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            return MAPEOrchestrator(prometheus, mesh, dao, ipfs)
    
    @pytest.mark.asyncio
    async def test_monitor_cycle(self, orchestrator, mock_clients):
        """Test monitor cycle collects metrics."""
        prometheus, _, _, _ = mock_clients
        
        metrics = await orchestrator.monitor_cycle()
        
        assert "latency_p95_value" in metrics
        prometheus.query.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_analyze_cycle_no_action_needed(self, orchestrator):
        """Test analyze cycle with healthy metrics."""
        metrics = {
            "latency_p95_value": 50,
            "packet_loss_value": 0.5,
            "cpu_usage_value": 40,
        }
        
        actions = await orchestrator.analyze_cycle(metrics)
        
        assert len(actions) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_cycle_high_latency(self, orchestrator):
        """Test analyze cycle with high latency - uses fallback due to ML model."""
        # Mock the GraphSAGE model to raise exception (forces fallback)
        orchestrator.graphsage.predict_enhanced = MagicMock(side_effect=Exception("ML model unavailable"))
        
        metrics = {
            "latency_p95_value": 150,  # Above threshold
            "packet_loss_value": 0.5,
            "cpu_usage_value": 40,
        }
        
        actions = await orchestrator.analyze_cycle(metrics)
        
        assert len(actions) > 0
        assert any(a.action_type == HealingActionType.RE_ROUTE for a in actions)
    
    @pytest.mark.asyncio
    async def test_analyze_cycle_high_cpu(self, orchestrator):
        """Test analyze cycle with high CPU - uses fallback due to ML model."""
        # Mock the GraphSAGE model to raise exception (forces fallback)
        orchestrator.graphsage.predict_enhanced = MagicMock(side_effect=Exception("ML model unavailable"))
        
        metrics = {
            "latency_p95_value": 50,
            "packet_loss_value": 0.5,
            "cpu_usage_value": 90,  # Above threshold
        }
        
        actions = await orchestrator.analyze_cycle(metrics)
        
        assert any(a.action_type == HealingActionType.SCALE_UP for a in actions)
    
    @pytest.mark.asyncio
    async def test_execute_cycle(self, orchestrator, mock_clients):
        """Test execute cycle runs actions."""
        _, mesh, dao, _ = mock_clients
        
        actions = [
            HealingAction(
                action_type=HealingActionType.RE_ROUTE,
                target="mesh",
                reason="Test action"
            )
        ]
        
        await orchestrator.execute_cycle(actions)
        
        mesh.apply_routing.assert_called_once()
        dao.log_event.assert_called()
        # Note: ipfs.snapshot is called in a separate snapshot method, not execute_cycle
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, orchestrator):
        """Test circuit breaker blocks actions when open."""
        # Force circuit breaker to open
        for _ in range(5):
            await orchestrator._circuit_breaker.record_failure()
        
        # Try to run analyze - should return empty
        metrics = {"latency_p95_value": 150}
        actions = await orchestrator.analyze_cycle(metrics)
        
        assert len(actions) == 0
    
    def test_get_metrics(self, orchestrator):
        """Test getting orchestrator metrics."""
        metrics = orchestrator.get_metrics()
        
        assert "total_healing_actions" in metrics
        assert "successful_healing_actions" in metrics
        assert "success_rate" in metrics
        assert "circuit_breaker_state" in metrics
    
    @pytest.mark.asyncio
    async def test_check_health_healthy(self, orchestrator):
        """Test health check with healthy metrics."""
        metrics = {
            "latency_p95_value": 50,
            "packet_loss_value": 0.5,
            "cpu_usage_value": 40,
            "memory_usage_value": 50,
        }
        
        is_healthy = await orchestrator._check_health(metrics)
        
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_check_health_unhealthy(self, orchestrator):
        """Test health check with unhealthy metrics."""
        metrics = {
            "latency_p95_value": 150,  # Above threshold
            "packet_loss_value": 0.5,
            "cpu_usage_value": 40,
            "memory_usage_value": 50,
        }
        
        is_healthy = await orchestrator._check_health(metrics)
        
        assert is_healthy is False


class TestMAPEWithCustomThresholds:
    """Tests for MAPE with custom thresholds."""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock clients."""
        prometheus = MagicMock()
        prometheus.query = AsyncMock(return_value={
            "latency_p95_value": 100,
            "packet_loss_value": 3.0,
        })
        
        mesh = MagicMock()
        mesh.apply_routing = AsyncMock()
        
        dao = MagicMock()
        dao.log_event = AsyncMock()
        
        ipfs = MagicMock()
        ipfs.snapshot = AsyncMock()
        
        return prometheus, mesh, dao, ipfs
    
    @pytest.mark.asyncio
    async def test_custom_thresholds(self, mock_clients):
        """Test orchestrator with custom thresholds."""
        prometheus, mesh, dao, ipfs = mock_clients
        
        with patch.dict(os.environ, {"ENVIRONMENT": "testing"}):
            orchestrator = MAPEOrchestrator(
                prometheus, mesh, dao, ipfs,
                thresholds={
                    "latency_p95_ms": 150,  # Higher threshold
                    "packet_loss_percent": 5.0,  # Higher threshold
                }
            )
        
        # 100ms latency should not trigger action with 150ms threshold
        metrics = {"latency_p95_value": 100, "packet_loss_value": 3.0}
        actions = await orchestrator.analyze_cycle(metrics)
        
        assert len(actions) == 0


class TestProductionSecurity:
    """Tests for production security features."""
    
    def test_rejects_mock_in_production(self):
        """Test that mock clients are rejected in production."""
        mock_client = MagicMock()
        mock_client.__class__.__name__ = "MockPrometheusClient"
        
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            with pytest.raises(RuntimeError, match="Fail-closed.*mock detected"):
                MAPEOrchestrator(
                    mock_client,
                    MagicMock(),
                    MagicMock(),
                    MagicMock()
                )
    
    def test_allows_real_clients_in_production(self):
        """Test real clients work in production."""
        class RealPrometheus:
            async def query(self, params):
                return {}
        
        class RealMesh:
            async def apply_routing(self, plan):
                pass
        
        class RealDAO:
            async def log_event(self, type, data):
                pass
        
        class RealIPFS:
            async def snapshot(self, name):
                pass
        
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            # Should not raise
            orchestrator = MAPEOrchestrator(
                RealPrometheus(),
                RealMesh(),
                RealDAO(),
                RealIPFS()
            )
            
            assert orchestrator is not None
