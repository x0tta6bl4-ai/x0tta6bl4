#!/usr/bin/env python3
"""
Unit tests for EBPFOrchestrator

Tests the unified control point for eBPF subsystem including:
- Lifecycle management (start/stop/restart)
- Component initialization
- Status reporting
- Health checks
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.ebpf.orchestrator import (ComponentStatus, EBPFOrchestrator,
                                           OrchestratorConfig,
                                           OrchestratorState,
                                           create_orchestrator)


class TestOrchestratorConfig:
    """Tests for OrchestratorConfig"""

    def test_default_config(self):
        """Test default configuration values"""
        config = OrchestratorConfig()

        assert config.interface == "eth0"
        assert config.enable_flow_observability is True
        assert config.enable_metrics_export is True
        assert config.enable_dynamic_fallback is True
        assert config.enable_mapek_integration is True
        assert config.prometheus_port == 9090
        assert config.latency_threshold_ms == 100.0
        assert config.monitoring_interval_seconds == 10.0
        assert config.auto_load_programs is True

    def test_custom_config(self):
        """Test custom configuration"""
        config = OrchestratorConfig(
            interface="wlan0",
            prometheus_port=9091,
            enable_flow_observability=False,
            latency_threshold_ms=50.0,
        )

        assert config.interface == "wlan0"
        assert config.prometheus_port == 9091
        assert config.enable_flow_observability is False
        assert config.latency_threshold_ms == 50.0


class TestOrchestratorInit:
    """Tests for EBPFOrchestrator initialization"""

    def test_init_default(self):
        """Test initialization with default config"""
        orchestrator = EBPFOrchestrator()

        assert orchestrator.state == OrchestratorState.STOPPED
        assert orchestrator.config.interface == "eth0"
        assert orchestrator._loader is None
        assert orchestrator._probes is None

    def test_init_custom_config(self):
        """Test initialization with custom config"""
        config = OrchestratorConfig(interface="wlan0")
        orchestrator = EBPFOrchestrator(config)

        assert orchestrator.config.interface == "wlan0"


class TestOrchestratorLifecycle:
    """Tests for orchestrator lifecycle management"""

    @pytest.mark.asyncio
    async def test_start_success(self):
        """Test successful start"""
        orchestrator = EBPFOrchestrator()

        # Mock component initialization
        with patch.object(
            orchestrator, "_initialize_components", new_callable=AsyncMock
        ):
            with patch.object(orchestrator, "_load_programs", new_callable=AsyncMock):
                with patch.object(
                    orchestrator, "_start_background_tasks", new_callable=AsyncMock
                ):
                    result = await orchestrator.start()

        assert result is True
        assert orchestrator.state == OrchestratorState.RUNNING
        assert orchestrator.start_time is not None

    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test start when already running"""
        orchestrator = EBPFOrchestrator()
        orchestrator.state = OrchestratorState.RUNNING

        result = await orchestrator.start()

        assert result is True

    @pytest.mark.asyncio
    async def test_stop_success(self):
        """Test successful stop"""
        orchestrator = EBPFOrchestrator()
        orchestrator.state = OrchestratorState.RUNNING

        with patch.object(
            orchestrator, "_stop_background_tasks", new_callable=AsyncMock
        ):
            with patch.object(
                orchestrator, "_cleanup_components", new_callable=AsyncMock
            ):
                result = await orchestrator.stop()

        assert result is True
        assert orchestrator.state == OrchestratorState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_already_stopped(self):
        """Test stop when already stopped"""
        orchestrator = EBPFOrchestrator()

        result = await orchestrator.stop()

        assert result is True

    @pytest.mark.asyncio
    async def test_restart(self):
        """Test restart functionality"""
        orchestrator = EBPFOrchestrator()

        with patch.object(orchestrator, "stop", new_callable=AsyncMock) as mock_stop:
            with patch.object(
                orchestrator, "start", new_callable=AsyncMock
            ) as mock_start:
                mock_stop.return_value = True
                mock_start.return_value = True

                result = await orchestrator.restart()

        assert result is True
        mock_stop.assert_called_once()
        mock_start.assert_called_once()


class TestOrchestratorStatus:
    """Tests for status reporting"""

    def test_get_status_stopped(self):
        """Test status when stopped"""
        orchestrator = EBPFOrchestrator()

        status = orchestrator.get_status()

        assert status["state"] == "stopped"
        assert "components" in status
        assert "programs" in status
        assert "metrics" in status

    def test_get_status_running(self):
        """Test status when running"""
        orchestrator = EBPFOrchestrator()
        orchestrator.state = OrchestratorState.RUNNING
        orchestrator.start_time = 1000.0

        with patch("time.time", return_value=1100.0):
            status = orchestrator.get_status()

        assert status["state"] == "running"
        assert status["uptime_seconds"] == 100.0


class TestOrchestratorHealthCheck:
    """Tests for health check functionality"""

    def test_health_check_no_components(self):
        """Test health check with no components"""
        orchestrator = EBPFOrchestrator()

        health = orchestrator.health_check()

        assert health["healthy"] is True
        assert health["state"] == "stopped"
        assert "checks" in health

    def test_health_check_with_loader(self):
        """Test health check with loader component"""
        orchestrator = EBPFOrchestrator()
        orchestrator._loader = Mock()
        orchestrator._loader.list_loaded_programs.return_value = [
            {"id": "prog1", "path": "/test/prog1.o"}
        ]

        health = orchestrator.health_check()

        assert health["healthy"] is True
        assert "loader" in health["checks"]
        assert health["checks"]["loader"]["status"] == "healthy"
        assert health["checks"]["loader"]["programs_loaded"] == 1

    def test_health_check_loader_error(self):
        """Test health check when loader has error"""
        orchestrator = EBPFOrchestrator()
        orchestrator._loader = Mock()
        orchestrator._loader.list_loaded_programs.side_effect = Exception("Test error")

        health = orchestrator.health_check()

        assert health["healthy"] is False
        assert health["checks"]["loader"]["status"] == "unhealthy"
        assert "error" in health["checks"]["loader"]


class TestOrchestratorProgramManagement:
    """Tests for program management"""

    def test_load_program_no_loader(self):
        """Test load_program when loader not available"""
        orchestrator = EBPFOrchestrator()

        result = orchestrator.load_program("test.o")

        assert result is None

    def test_load_program_success(self):
        """Test successful program loading"""
        orchestrator = EBPFOrchestrator()
        orchestrator._loader = Mock()
        orchestrator._loader.load_program.return_value = "xdp_test_123"

        result = orchestrator.load_program("test.o", "xdp")

        assert result == "xdp_test_123"
        assert "xdp_test_123" in orchestrator._loaded_programs

    def test_attach_program_no_loader(self):
        """Test attach_program when loader not available"""
        orchestrator = EBPFOrchestrator()

        result = orchestrator.attach_program("prog_id")

        assert result is False

    def test_detach_program_no_loader(self):
        """Test detach_program when loader not available"""
        orchestrator = EBPFOrchestrator()

        result = orchestrator.detach_program("prog_id")

        assert result is False


class TestOrchestratorFlowObservability:
    """Tests for flow observability features"""

    def test_get_flows_no_cilium(self):
        """Test get_flows when Cilium not available"""
        orchestrator = EBPFOrchestrator()

        flows = orchestrator.get_flows()

        assert flows == []

    def test_get_flows_with_cilium(self):
        """Test get_flows with Cilium integration"""
        orchestrator = EBPFOrchestrator()
        orchestrator._cilium = Mock()
        orchestrator._cilium.get_hubble_like_flows.return_value = [
            {"source": "192.168.1.1", "destination": "192.168.1.2"}
        ]

        flows = orchestrator.get_flows(source_ip="192.168.1.1")

        assert len(flows) == 1
        orchestrator._cilium.get_hubble_like_flows.assert_called_once()

    def test_record_flow_no_cilium(self):
        """Test record_flow when Cilium not available"""
        orchestrator = EBPFOrchestrator()

        # Should not raise
        orchestrator.record_flow(
            source_ip="192.168.1.1",
            destination_ip="192.168.1.2",
            source_port=12345,
            destination_port=80,
            protocol="TCP",
            bytes_count=1000,
            packets=10,
        )


class TestOrchestratorFactory:
    """Tests for factory function"""

    def test_create_orchestrator_default(self):
        """Test create_orchestrator with defaults"""
        orchestrator = create_orchestrator()

        assert isinstance(orchestrator, EBPFOrchestrator)
        assert orchestrator.config.interface == "eth0"

    def test_create_orchestrator_custom(self):
        """Test create_orchestrator with custom options"""
        orchestrator = create_orchestrator(
            interface="wlan0", prometheus_port=9091, enable_flow_observability=False
        )

        assert orchestrator.config.interface == "wlan0"
        assert orchestrator.config.prometheus_port == 9091
        assert orchestrator.config.enable_flow_observability is False


class TestComponentStatus:
    """Tests for ComponentStatus dataclass"""

    def test_component_status_creation(self):
        """Test ComponentStatus creation"""
        status = ComponentStatus(
            name="TestComponent",
            available=True,
            running=True,
            error=None,
            metrics={"test": 123},
        )

        assert status.name == "TestComponent"
        assert status.available is True
        assert status.running is True
        assert status.error is None
        assert status.metrics == {"test": 123}

    def test_component_status_with_error(self):
        """Test ComponentStatus with error"""
        status = ComponentStatus(
            name="FailedComponent",
            available=True,
            running=False,
            error="Connection failed",
        )

        assert status.running is False
        assert status.error == "Connection failed"


# Integration tests
@pytest.mark.asyncio
class TestOrchestratorIntegration:
    """Integration tests for orchestrator"""

    async def test_full_lifecycle(self):
        """Test full start/stop lifecycle"""
        config = OrchestratorConfig(
            auto_load_programs=False,
            enable_flow_observability=False,
            enable_metrics_export=False,
            enable_dynamic_fallback=False,
            enable_mapek_integration=False,
        )
        orchestrator = EBPFOrchestrator(config)

        # Start
        result = await orchestrator.start()
        assert result is True
        assert orchestrator.state == OrchestratorState.RUNNING

        # Get status
        status = orchestrator.get_status()
        assert status["state"] == "running"

        # Health check
        health = orchestrator.health_check()
        assert health["healthy"] is True

        # Stop
        result = await orchestrator.stop()
        assert result is True
        assert orchestrator.state == OrchestratorState.STOPPED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
