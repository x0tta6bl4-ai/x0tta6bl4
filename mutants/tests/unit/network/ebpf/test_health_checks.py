"""
Tests for eBPF health checks module.

These tests cover:
- HealthCheckResult dataclass
- Health status enum
- EBPFHealthChecker functionality
- Integration with orchestrator
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.network.ebpf.health_checks import (
    HealthStatus,
    HealthCheckResult,
    EBPFHealthChecker
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_initialization(self):
        """Test initializing HealthCheckResult."""
        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            component="test-component",
            message="Test message",
            timestamp=1234567890.123,
            duration_ms=100.5
        )
        assert result.status == HealthStatus.HEALTHY
        assert result.component == "test-component"
        assert result.message == "Test message"
        assert result.timestamp == 1234567890.123
        assert result.duration_ms == 100.5

    def test_to_dict(self):
        """Test converting to dictionary."""
        result = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            component="test-component",
            message="Test message",
            timestamp=1234567890.123,
            duration_ms=100.5,
            details={"key": "value"}
        )
        dict_result = result.to_dict()
        assert dict_result["status"] == "degraded"
        assert dict_result["component"] == "test-component"
        assert dict_result["message"] == "Test message"
        assert dict_result["timestamp"] == 1234567890.123
        assert dict_result["duration_ms"] == 100.5
        assert dict_result["details"] == {"key": "value"}


class TestEBPFHealthChecker:
    """Tests for EBPFHealthChecker class."""

    @pytest.fixture
    def mock_loader(self):
        """Create mock EBPFLoader."""
        loader = MagicMock()
        loader.list_loaded_programs.return_value = []
        loader.attached_interfaces = {}
        return loader

    @pytest.fixture
    def mock_metrics(self):
        """Create mock EBPFMetricsExporter."""
        metrics = MagicMock()
        metrics.get_metrics_summary.return_value = {
            "registered_maps": 0,
            "prometheus_metrics": 0
        }
        metrics.get_degradation_status.return_value = {
            "prometheus_available": True,
            "consecutive_failures": 0,
            "level": "full"
        }
        return metrics

    @pytest.fixture
    def mock_cilium(self):
        """Create mock CiliumLikeIntegration."""
        cilium = MagicMock()
        cilium.get_flow_metrics.return_value = {"flows": []}
        return cilium

    @pytest.fixture
    def mock_fallback(self):
        """Create mock DynamicFallbackController."""
        fallback = MagicMock()
        fallback.get_status.return_value = {
            "active_fallback": False,
            "fallback_count": 0,
            "last_fallback_time": None,
            "available_interfaces": [],
            "unavailable_interfaces": []
        }
        return fallback

    @pytest.fixture
    def mock_mapek(self):
        """Create mock EBPFMAPEKIntegration."""
        mapek = MagicMock()
        mapek.is_operational.return_value = True
        return mapek

    @pytest.fixture
    def mock_ring_buffer(self):
        """Create mock RingBufferReader."""
        ring_buffer = MagicMock()
        ring_buffer.running = True
        ring_buffer.event_handlers = {}
        return ring_buffer

    @pytest.fixture
    def health_checker(self, mock_loader, mock_metrics, mock_cilium,
                      mock_fallback, mock_mapek, mock_ring_buffer):
        """Create EBPFHealthChecker instance."""
        return EBPFHealthChecker(
            mock_loader,
            mock_metrics,
            mock_cilium,
            mock_fallback,
            mock_mapek,
            mock_ring_buffer
        )

    def test_initialization(self, health_checker):
        """Test initializing health checker."""
        assert health_checker is not None
        assert hasattr(health_checker, 'check_all')
        assert hasattr(health_checker, 'check_loader')
        assert hasattr(health_checker, 'check_metrics')
        assert hasattr(health_checker, 'check_cilium')
        assert hasattr(health_checker, 'check_fallback')
        assert hasattr(health_checker, 'check_mapek')
        assert hasattr(health_checker, 'check_ring_buffer')

    @pytest.mark.asyncio
    async def test_check_loader_healthy(self, health_checker, mock_loader):
        """Test check_loader returns healthy when programs are loaded."""
        mock_loader.list_loaded_programs.return_value = [{"id": "program1"}]
        mock_loader.attached_interfaces = {"eth0": []}

        result = await health_checker.check_loader()
        assert result.status == HealthStatus.HEALTHY
        assert "1 eBPF programs" in result.message
        assert result.details["program_count"] == 1
        assert result.details["interfaces"] == ["eth0"]

    @pytest.mark.asyncio
    async def test_check_loader_degraded(self, health_checker, mock_loader):
        """Test check_loader returns degraded when no programs are loaded."""
        mock_loader.list_loaded_programs.return_value = []
        mock_loader.attached_interfaces = {}

        result = await health_checker.check_loader()
        assert result.status == HealthStatus.DEGRADED
        assert "No eBPF programs loaded" in result.message
        assert result.details["program_count"] == 0
        assert result.details["interfaces"] == []

    @pytest.mark.asyncio
    async def test_check_metrics_healthy(self, health_checker, mock_metrics):
        """Test check_metrics returns healthy when metrics are available."""
        mock_metrics.get_degradation_status.return_value = {
            "prometheus_available": True,
            "consecutive_failures": 0,
            "level": "full"
        }

        result = await health_checker.check_metrics()
        assert result.status == HealthStatus.HEALTHY
        assert "Metrics exporter healthy" in result.message

    @pytest.mark.asyncio
    async def test_check_metrics_degraded(self, health_checker, mock_metrics):
        """Test check_metrics returns degraded when Prometheus is unavailable."""
        mock_metrics.get_degradation_status.return_value = {
            "prometheus_available": False,
            "consecutive_failures": 0,
            "level": "degraded"
        }

        result = await health_checker.check_metrics()
        assert result.status == HealthStatus.DEGRADED
        assert "Prometheus metrics not available" in result.message

    @pytest.mark.asyncio
    async def test_check_cilium_healthy(self, health_checker, mock_cilium):
        """Test check_cilium returns healthy when flow metrics are available."""
        mock_cilium.get_flow_metrics.return_value = {"flows": ["flow1", "flow2"]}

        result = await health_checker.check_cilium()
        assert result.status == HealthStatus.HEALTHY
        assert "2 active flows" in result.message
        assert result.details["flow_count"] == 2

    @pytest.mark.asyncio
    async def test_check_cilium_degraded(self, health_checker, mock_cilium):
        """Test check_cilium returns degraded when no flow metrics available."""
        mock_cilium.get_flow_metrics.return_value = {"flows": []}

        result = await health_checker.check_cilium()
        assert result.status == HealthStatus.DEGRADED
        assert "No network flow metrics available" in result.message

    @pytest.mark.asyncio
    async def test_check_fallback_healthy(self, health_checker, mock_fallback):
        """Test check_fallback returns healthy when no fallback is active."""
        mock_fallback.get_status.return_value = {
            "active_fallback": False,
            "fallback_count": 0,
            "last_fallback_time": None,
            "available_interfaces": ["eth0"],
            "unavailable_interfaces": []
        }

        result = await health_checker.check_fallback()
        assert result.status == HealthStatus.HEALTHY
        assert "Dynamic fallback mechanism idle" in result.message
        assert result.details["active_fallback"] == False
        assert result.details["fallback_count"] == 0

    @pytest.mark.asyncio
    async def test_check_fallback_degraded(self, health_checker, mock_fallback):
        """Test check_fallback returns degraded when fallback is active."""
        mock_fallback.get_status.return_value = {
            "active_fallback": True,
            "fallback_count": 1,
            "last_fallback_time": "2024-01-19T10:00:00Z",
            "available_interfaces": ["eth0"],
            "unavailable_interfaces": ["eth1"]
        }

        result = await health_checker.check_fallback()
        assert result.status == HealthStatus.DEGRADED
        assert "Dynamic fallback mechanism active" in result.message
        assert result.details["active_fallback"] == True
        assert result.details["fallback_count"] == 1

    @pytest.mark.asyncio
    async def test_check_mapek_healthy(self, health_checker, mock_mapek):
        """Test check_mapek returns healthy when operational."""
        mock_mapek.is_operational.return_value = True

        result = await health_checker.check_mapek()
        assert result.status == HealthStatus.HEALTHY
        assert "MAPE-K integration operational" in result.message
        assert result.details["operational"] == True

    @pytest.mark.asyncio
    async def test_check_mapek_degraded(self, health_checker, mock_mapek):
        """Test check_mapek returns degraded when not operational."""
        mock_mapek.is_operational.return_value = False

        result = await health_checker.check_mapek()
        assert result.status == HealthStatus.DEGRADED
        assert "MAPE-K integration non-operational" in result.message
        assert result.details["operational"] == False

    @pytest.mark.asyncio
    async def test_check_ring_buffer_healthy(self, health_checker, mock_ring_buffer):
        """Test check_ring_buffer returns healthy when running."""
        mock_ring_buffer.running = True

        result = await health_checker.check_ring_buffer()
        assert result.status == HealthStatus.HEALTHY
        assert "Ring buffer reader active" in result.message
        assert result.details["running"] == True

    @pytest.mark.asyncio
    async def test_check_ring_buffer_degraded(self, health_checker, mock_ring_buffer):
        """Test check_ring_buffer returns degraded when inactive."""
        mock_ring_buffer.running = False

        result = await health_checker.check_ring_buffer()
        assert result.status == HealthStatus.DEGRADED
        assert "Ring buffer reader inactive" in result.message
        assert result.details["running"] == False

    @pytest.mark.asyncio
    async def test_check_all_components(self, health_checker):
        """Test checking all components health."""
        results = await health_checker.check_all()

        assert len(results) == 6
        assert "loader" in results
        assert "metrics" in results
        assert "cilium" in results
        assert "fallback" in results
        assert "mapek" in results
        assert "ring_buffer" in results

        for component, result in results.items():
            assert result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
            assert len(result.message) > 0
            assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_check_and_report(self, health_checker):
        """Test generating Prometheus-compatible report."""
        report = await health_checker.check_and_report()

        assert "ebpf_health_total" in report
        assert "ebpf_health_healthy" in report
        assert "ebpf_health_degraded" in report
        assert "ebpf_health_unhealthy" in report

        for component in ["loader", "metrics", "cilium", "fallback", "mapek", "ring_buffer"]:
            assert f"ebpf_health_{component}" in report

    @pytest.mark.asyncio
    async def test_cache_functionality(self, health_checker):
        """Test that health check results are cached."""
        await health_checker.check_all()
        cache = health_checker.get_cache()
        assert len(cache) == 6
        last_check = health_checker.get_last_check_time()
        assert last_check > 0

        await asyncio.sleep(0.1)
        await health_checker.check_all()
        new_last_check = health_checker.get_last_check_time()
        assert new_last_check > last_check

    @pytest.mark.asyncio
    async def test_exception_handling(self, health_checker, mock_loader):
        """Test that health check handles component exceptions."""
        mock_loader.list_loaded_programs.side_effect = Exception("Test exception")

        result = await health_checker.check_loader()
        assert result.status == HealthStatus.UNHEALTHY
        assert "Health check failed" in result.message
        assert "Test exception" in str(result.details["exception"])

    @pytest.mark.asyncio
    async def test_combined_health_levels(self, health_checker, mock_loader,
                                           mock_metrics, mock_cilium):
        """Test health check correctly combines different component health levels."""
        mock_loader.list_loaded_programs.return_value = []
        mock_metrics.get_degradation_status.return_value = {
            "prometheus_available": True,
            "consecutive_failures": 0,
            "level": "full"
        }
        mock_cilium.get_flow_metrics.return_value = {"flows": []}

        results = await health_checker.check_all()
        assert results["loader"].status == HealthStatus.DEGRADED
        assert results["metrics"].status == HealthStatus.HEALTHY
        assert results["cilium"].status == HealthStatus.DEGRADED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])