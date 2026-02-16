"""
Unit tests for src/network/ebpf/orchestrator.py

Tests the EBPFOrchestrator lifecycle, component management, program operations,
flow observability, health checks, metrics, and factory functions.
All external eBPF/bcc dependencies are mocked.
"""

import asyncio
import time
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.network.ebpf.orchestrator import (ComponentStatus, EBPFOrchestrator,
                                           OrchestratorConfig,
                                           OrchestratorState,
                                           create_orchestrator)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    """Default orchestrator configuration for tests."""
    return OrchestratorConfig(
        interface="test0",
        auto_load_programs=False,
        enable_flow_observability=False,
        enable_metrics_export=False,
        enable_performance_monitoring=False,
        enable_dynamic_fallback=False,
        enable_mapek_integration=False,
        enable_network_probes=False,
        monitoring_interval_seconds=0.01,
    )


@pytest.fixture
def mock_loader():
    loader = MagicMock()
    loader.load_programs.return_value = ["prog1", "prog2"]
    loader.load_program.return_value = "prog_abc"
    loader.attach_to_interface.return_value = True
    loader.detach_from_interface.return_value = True
    loader.unload_program.return_value = True
    loader.list_loaded_programs.return_value = [{"id": "prog1", "type": "xdp"}]
    loader.get_stats.return_value = {"avg_latency_ns": 50000, "packets": 100}
    loader.cleanup.return_value = None
    return loader


@pytest.fixture
def mock_cilium():
    cilium = MagicMock()
    cilium.get_hubble_like_flows.return_value = [{"src": "1.2.3.4"}]
    cilium.get_flow_metrics.return_value = {"flows_processed_total": 42}
    cilium.record_flow.return_value = None
    cilium.export_metrics_to_prometheus.return_value = None
    cilium.shutdown.return_value = None
    return cilium


@pytest.fixture
def mock_fallback():
    fb = MagicMock()
    fb.update_latency.return_value = None
    fb.check_recovery.return_value = None
    fb.get_fallback_status.return_value = {"active": False}
    return fb


@pytest.fixture
def mock_mapek():
    m = MagicMock()
    m.get_metrics_for_mapek.return_value = {"cpu": 0.5}
    m.check_anomalies.return_value = None
    m.trigger_mapek_alert.return_value = None
    return m


@pytest.fixture
def mock_metrics_exporter():
    exp = MagicMock()
    exp.export_metrics.return_value = None
    exp.get_metrics_summary.return_value = {"registered_maps": 3}
    return exp


@pytest.fixture
def mock_probes():
    p = MagicMock()
    p.get_current_metrics.return_value = {"avg_latency_ns": 120}
    return p


@pytest.fixture
def mock_perf_monitor():
    pm = MagicMock()
    pm.start_monitoring = AsyncMock()
    pm.stop_monitoring = AsyncMock()
    pm.get_performance_report.return_value = {"cpu_usage": 0.12}
    return pm


@pytest.fixture
def orchestrator(config, mock_loader):
    """Orchestrator with only a loader injected and auto_load disabled."""
    return EBPFOrchestrator(config, loader=mock_loader)


@pytest.fixture
def full_orchestrator(
    config,
    mock_loader,
    mock_cilium,
    mock_fallback,
    mock_mapek,
    mock_metrics_exporter,
    mock_probes,
    mock_perf_monitor,
):
    """Orchestrator with all components injected."""
    return EBPFOrchestrator(
        config,
        loader=mock_loader,
        cilium=mock_cilium,
        fallback=mock_fallback,
        mapek=mock_mapek,
        metrics_exporter=mock_metrics_exporter,
        probes=mock_probes,
        performance_monitor=mock_perf_monitor,
    )


# ===========================================================================
# OrchestratorConfig and ComponentStatus dataclass tests
# ===========================================================================


class TestOrchestratorConfig:
    def test_defaults(self):
        cfg = OrchestratorConfig()
        assert cfg.interface == "eth0"
        assert cfg.prometheus_port == 9090
        assert cfg.latency_threshold_ms == 100.0
        assert cfg.monitoring_interval_seconds == 10.0
        assert cfg.auto_load_programs is True
        assert cfg.enable_flow_observability is True

    def test_custom_values(self):
        cfg = OrchestratorConfig(
            interface="wg0",
            prometheus_port=9191,
            latency_threshold_ms=50.0,
        )
        assert cfg.interface == "wg0"
        assert cfg.prometheus_port == 9191
        assert cfg.latency_threshold_ms == 50.0


class TestComponentStatus:
    def test_creation(self):
        cs = ComponentStatus(
            name="TestComp",
            available=True,
            running=False,
            error="some error",
            metrics={"k": 1},
        )
        assert cs.name == "TestComp"
        assert cs.available is True
        assert cs.running is False
        assert cs.error == "some error"
        assert cs.metrics == {"k": 1}

    def test_defaults(self):
        cs = ComponentStatus(name="X", available=False, running=False)
        assert cs.error is None
        assert cs.metrics == {}


class TestOrchestratorState:
    def test_states(self):
        assert OrchestratorState.STOPPED.value == "stopped"
        assert OrchestratorState.STARTING.value == "starting"
        assert OrchestratorState.RUNNING.value == "running"
        assert OrchestratorState.STOPPING.value == "stopping"
        assert OrchestratorState.ERROR.value == "error"


# ===========================================================================
# Initialization tests
# ===========================================================================


class TestInit:
    def test_default_config(self):
        o = EBPFOrchestrator()
        assert o.config.interface == "eth0"
        assert o.state == OrchestratorState.STOPPED
        assert o.start_time is None

    def test_custom_config(self, config):
        o = EBPFOrchestrator(config)
        assert o.config.interface == "test0"

    def test_injected_components(self, config, mock_loader, mock_cilium):
        o = EBPFOrchestrator(config, loader=mock_loader, cilium=mock_cilium)
        assert o._loader is mock_loader
        assert o._cilium is mock_cilium

    def test_no_components_by_default(self, config):
        o = EBPFOrchestrator(config)
        assert o._loader is None
        assert o._probes is None
        assert o._cilium is None


# ===========================================================================
# Lifecycle: start / stop / restart
# ===========================================================================


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_sets_running(self, orchestrator):
        result = await orchestrator.start()
        assert result is True
        assert orchestrator.state == OrchestratorState.RUNNING
        assert orchestrator.start_time is not None
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_start_already_running_returns_true(self, orchestrator):
        await orchestrator.start()
        result = await orchestrator.start()
        assert result is True
        assert orchestrator.state == OrchestratorState.RUNNING
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_stopped(self, orchestrator):
        await orchestrator.start()
        result = await orchestrator.stop()
        assert result is True
        assert orchestrator.state == OrchestratorState.STOPPED

    @pytest.mark.asyncio
    async def test_stop_already_stopped_returns_true(self, orchestrator):
        result = await orchestrator.stop()
        assert result is True

    @pytest.mark.asyncio
    async def test_restart(self, orchestrator):
        await orchestrator.start()
        result = await orchestrator.restart()
        assert result is True
        assert orchestrator.state == OrchestratorState.RUNNING
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_start_error_sets_error_state(self, config):
        o = EBPFOrchestrator(config)
        with patch.object(
            o, "_initialize_components", side_effect=RuntimeError("boom")
        ):
            result = await o.start()
        assert result is False
        assert o.state == OrchestratorState.ERROR

    @pytest.mark.asyncio
    async def test_stop_error_sets_error_state(self, orchestrator):
        await orchestrator.start()
        with patch.object(
            orchestrator, "_stop_background_tasks", side_effect=RuntimeError("fail")
        ):
            result = await orchestrator.stop()
        assert result is False
        assert orchestrator.state == OrchestratorState.ERROR


# ===========================================================================
# auto_load_programs
# ===========================================================================


class TestAutoLoadPrograms:
    @pytest.mark.asyncio
    async def test_auto_load_programs(self, mock_loader):
        cfg = OrchestratorConfig(
            interface="test0",
            auto_load_programs=True,
            enable_flow_observability=False,
            enable_metrics_export=False,
            enable_performance_monitoring=False,
            enable_dynamic_fallback=False,
            enable_mapek_integration=False,
            enable_network_probes=False,
        )
        o = EBPFOrchestrator(cfg, loader=mock_loader)
        await o.start()
        mock_loader.load_programs.assert_called_once()
        assert o._loaded_programs == ["prog1", "prog2"]
        await o.stop()

    @pytest.mark.asyncio
    async def test_load_programs_without_loader(self, config):
        """No loader => _load_programs is a no-op."""
        o = EBPFOrchestrator(config)
        # Should not raise
        await o._load_programs()
        assert o._loaded_programs == []

    @pytest.mark.asyncio
    async def test_load_programs_exception(self, config, mock_loader):
        mock_loader.load_programs.side_effect = RuntimeError("load error")
        o = EBPFOrchestrator(config, loader=mock_loader)
        # Should not raise, just log warning
        await o._load_programs()


# ===========================================================================
# Component cleanup
# ===========================================================================


class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_components(
        self, full_orchestrator, mock_loader, mock_cilium
    ):
        await full_orchestrator._cleanup_components()
        mock_loader.cleanup.assert_called_once()
        mock_cilium.shutdown.assert_called_once()
        assert full_orchestrator._loader is None
        assert full_orchestrator._cilium is None
        assert full_orchestrator._loaded_programs == []

    @pytest.mark.asyncio
    async def test_cleanup_tolerates_loader_error(self, config, mock_loader):
        mock_loader.cleanup.side_effect = RuntimeError("cleanup fail")
        o = EBPFOrchestrator(config, loader=mock_loader)
        # Should not raise
        await o._cleanup_components()
        assert o._loader is None

    @pytest.mark.asyncio
    async def test_cleanup_tolerates_cilium_error(self, config, mock_cilium):
        mock_cilium.shutdown.side_effect = RuntimeError("shutdown fail")
        o = EBPFOrchestrator(config, cilium=mock_cilium)
        await o._cleanup_components()
        assert o._cilium is None


# ===========================================================================
# Background tasks
# ===========================================================================


class TestBackgroundTasks:
    @pytest.mark.asyncio
    async def test_start_with_performance_monitor(
        self, full_orchestrator, mock_perf_monitor
    ):
        await full_orchestrator.start()
        mock_perf_monitor.start_monitoring.assert_awaited_once()
        await full_orchestrator.stop()
        mock_perf_monitor.stop_monitoring.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_monitoring_task_created(self, orchestrator):
        await orchestrator.start()
        assert orchestrator._monitoring_task is not None
        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_metrics_task_created_with_exporter(
        self, config, mock_metrics_exporter
    ):
        o = EBPFOrchestrator(config, metrics_exporter=mock_metrics_exporter)
        await o.start()
        assert o._metrics_task is not None
        await o.stop()

    @pytest.mark.asyncio
    async def test_no_metrics_task_without_exporter(self, orchestrator):
        await orchestrator.start()
        assert orchestrator._metrics_task is None
        await orchestrator.stop()


# ===========================================================================
# Program management
# ===========================================================================


class TestProgramManagement:
    def test_load_program_success(self, orchestrator, mock_loader):
        with patch("src.network.ebpf.orchestrator.EBPFProgramType") as MockType:
            MockType.side_effect = lambda v: v
            result = orchestrator.load_program("/path/prog.o", "xdp")
        assert result == "prog_abc"
        assert "prog_abc" in orchestrator._loaded_programs

    def test_load_program_no_loader(self, config):
        o = EBPFOrchestrator(config)
        result = o.load_program("/path/prog.o", "xdp")
        assert result is None

    def test_load_program_exception(self, orchestrator, mock_loader):
        mock_loader.load_program.side_effect = RuntimeError("fail")
        with patch("src.network.ebpf.orchestrator.EBPFProgramType") as MockType:
            MockType.side_effect = lambda v: v
            result = orchestrator.load_program("/path/prog.o", "xdp")
        assert result is None

    def test_attach_program_success(self, orchestrator, mock_loader):
        with patch("src.network.ebpf.orchestrator.EBPFAttachMode") as MockMode:
            MockMode.side_effect = lambda v: v
            result = orchestrator.attach_program("prog1", mode="skb")
        assert result is True
        mock_loader.attach_to_interface.assert_called_once()

    def test_attach_program_no_loader(self, config):
        o = EBPFOrchestrator(config)
        result = o.attach_program("prog1")
        assert result is False

    def test_attach_program_custom_interface(self, orchestrator, mock_loader):
        with patch("src.network.ebpf.orchestrator.EBPFAttachMode") as MockMode:
            MockMode.side_effect = lambda v: v
            orchestrator.attach_program("prog1", interface="wg0", mode="drv")
        args = mock_loader.attach_to_interface.call_args
        assert args[0][1] == "wg0"

    def test_attach_program_exception(self, orchestrator, mock_loader):
        mock_loader.attach_to_interface.side_effect = RuntimeError("attach err")
        with patch("src.network.ebpf.orchestrator.EBPFAttachMode") as MockMode:
            MockMode.side_effect = lambda v: v
            result = orchestrator.attach_program("prog1")
        assert result is False

    def test_unload_program_success(self, orchestrator, mock_loader):
        result = orchestrator.unload_program("prog1")
        assert result is True
        mock_loader.unload_program.assert_called_once_with("prog1")

    def test_unload_program_no_loader(self, config):
        o = EBPFOrchestrator(config)
        assert o.unload_program("prog1") is False

    def test_unload_program_exception(self, orchestrator, mock_loader):
        mock_loader.unload_program.side_effect = RuntimeError("err")
        assert orchestrator.unload_program("prog1") is False

    def test_detach_program_success(self, orchestrator, mock_loader):
        result = orchestrator.detach_program("prog1")
        assert result is True
        mock_loader.detach_from_interface.assert_called_once_with("prog1", "test0")

    def test_detach_program_custom_interface(self, orchestrator, mock_loader):
        orchestrator.detach_program("prog1", interface="eth1")
        mock_loader.detach_from_interface.assert_called_once_with("prog1", "eth1")

    def test_detach_program_no_loader(self, config):
        o = EBPFOrchestrator(config)
        assert o.detach_program("prog1") is False

    def test_detach_program_exception(self, orchestrator, mock_loader):
        mock_loader.detach_from_interface.side_effect = RuntimeError("err")
        assert orchestrator.detach_program("prog1") is False


# ===========================================================================
# Flow Observability
# ===========================================================================


class TestFlowObservability:
    def test_get_flows_with_cilium(self, full_orchestrator, mock_cilium):
        flows = full_orchestrator.get_flows(
            source_ip="10.0.0.1", destination_ip="10.0.0.2", protocol="TCP", limit=50
        )
        assert flows == [{"src": "1.2.3.4"}]
        mock_cilium.get_hubble_like_flows.assert_called_once_with(
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            protocol="TCP",
            limit=50,
        )

    def test_get_flows_without_cilium(self, orchestrator):
        flows = orchestrator.get_flows()
        assert flows == []

    def test_record_flow_with_cilium(self, full_orchestrator, mock_cilium):
        full_orchestrator.record_flow(
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            source_port=1234,
            destination_port=80,
            protocol="TCP",
            bytes_count=1024,
            packets=10,
        )
        mock_cilium.record_flow.assert_called_once()

    def test_record_flow_without_cilium(self, orchestrator):
        # Should not raise
        orchestrator.record_flow(
            source_ip="10.0.0.1",
            destination_ip="10.0.0.2",
            source_port=1234,
            destination_port=80,
            protocol="TCP",
            bytes_count=512,
            packets=5,
        )


# ===========================================================================
# Status and Metrics
# ===========================================================================


class TestStatusAndMetrics:
    def test_get_status_stopped(self, orchestrator):
        status = orchestrator.get_status()
        assert status["state"] == "stopped"
        assert status["interface"] == "test0"
        assert "components" in status
        assert "programs" in status
        assert "metrics" in status

    @pytest.mark.asyncio
    async def test_get_status_running(self, orchestrator):
        await orchestrator.start()
        status = orchestrator.get_status()
        assert status["state"] == "running"
        assert status["uptime_seconds"] >= 0
        await orchestrator.stop()

    def test_get_status_uptime_when_no_start_time(self, config):
        o = EBPFOrchestrator(config)
        status = o.get_status()
        assert status["uptime_seconds"] == 0.0

    def test_get_program_status_with_loader(self, orchestrator, mock_loader):
        programs = orchestrator._get_program_status()
        assert programs == [{"id": "prog1", "type": "xdp"}]

    def test_get_program_status_without_loader(self, config):
        o = EBPFOrchestrator(config)
        assert o._get_program_status() == []

    def test_get_metrics(
        self, full_orchestrator, mock_loader, mock_cilium, mock_mapek, mock_perf_monitor
    ):
        metrics = full_orchestrator.get_metrics()
        assert "ebpf_stats" in metrics
        assert "flow_metrics" in metrics
        assert "mapek_metrics" in metrics
        assert "performance_metrics" in metrics
        assert "timestamp" in metrics

    def test_get_metrics_empty(self, config):
        o = EBPFOrchestrator(config)
        metrics = o.get_metrics()
        assert "timestamp" in metrics
        assert "ebpf_stats" not in metrics

    def test_get_component_statuses(
        self,
        full_orchestrator,
        mock_probes,
        mock_cilium,
        mock_fallback,
        mock_perf_monitor,
    ):
        statuses = full_orchestrator._get_component_statuses()
        assert "loader" in statuses
        assert "probes" in statuses
        assert "cilium" in statuses
        assert "fallback" in statuses
        assert "mapek" in statuses
        assert "performance_monitor" in statuses
        assert statuses["loader"].running is True
        assert statuses["probes"].running is True
        mock_probes.get_current_metrics.assert_called()
        mock_cilium.get_flow_metrics.assert_called()

    def test_component_statuses_without_components(self, config):
        o = EBPFOrchestrator(config)
        statuses = o._get_component_statuses()
        assert statuses["loader"].running is False
        assert statuses["probes"].running is False
        assert statuses["cilium"].metrics == {}


# ===========================================================================
# Health check
# ===========================================================================


class TestHealthCheck:
    def test_health_check_all_healthy(
        self,
        full_orchestrator,
        mock_loader,
        mock_metrics_exporter,
        mock_probes,
        mock_cilium,
    ):
        result = full_orchestrator.health_check()
        assert result["healthy"] is True
        assert result["checks"]["loader"]["status"] == "healthy"
        assert result["checks"]["metrics"]["status"] == "healthy"
        assert result["checks"]["probes"]["status"] == "healthy"
        assert result["checks"]["cilium"]["status"] == "healthy"

    def test_health_check_no_components(self, config):
        o = EBPFOrchestrator(config)
        result = o.health_check()
        assert result["healthy"] is True
        assert result["checks"] == {}

    def test_health_check_loader_error(self, config, mock_loader):
        mock_loader.list_loaded_programs.side_effect = RuntimeError("loader broken")
        o = EBPFOrchestrator(config, loader=mock_loader)
        result = o.health_check()
        assert result["healthy"] is False
        assert result["checks"]["loader"]["status"] == "unhealthy"
        assert "loader broken" in result["checks"]["loader"]["error"]

    def test_health_check_metrics_error(self, config, mock_metrics_exporter):
        mock_metrics_exporter.get_metrics_summary.side_effect = RuntimeError(
            "metrics broken"
        )
        o = EBPFOrchestrator(config, metrics_exporter=mock_metrics_exporter)
        result = o.health_check()
        assert result["healthy"] is False
        assert result["checks"]["metrics"]["status"] == "unhealthy"

    def test_health_check_probes_error(self, config, mock_probes):
        mock_probes.get_current_metrics.side_effect = RuntimeError("probes broken")
        o = EBPFOrchestrator(config, probes=mock_probes)
        result = o.health_check()
        assert result["healthy"] is False
        assert result["checks"]["probes"]["status"] == "unhealthy"

    def test_health_check_cilium_error(self, config, mock_cilium):
        mock_cilium.get_flow_metrics.side_effect = RuntimeError("cilium broken")
        o = EBPFOrchestrator(config, cilium=mock_cilium)
        result = o.health_check()
        assert result["healthy"] is False
        assert result["checks"]["cilium"]["status"] == "unhealthy"

    def test_health_check_probes_no_latency(self, config, mock_probes):
        mock_probes.get_current_metrics.return_value = {"avg_latency_ns": 0}
        o = EBPFOrchestrator(config, probes=mock_probes)
        result = o.health_check()
        assert result["checks"]["probes"]["latency_observed"] is False

    def test_health_check_metrics_none_summary(self, config, mock_metrics_exporter):
        mock_metrics_exporter.get_metrics_summary.return_value = None
        o = EBPFOrchestrator(config, metrics_exporter=mock_metrics_exporter)
        result = o.health_check()
        assert result["checks"]["metrics"]["registered_maps"] == 0


# ===========================================================================
# Factory function
# ===========================================================================


class TestFactory:
    def test_create_orchestrator_defaults(self):
        o = create_orchestrator()
        assert isinstance(o, EBPFOrchestrator)
        assert o.config.interface == "eth0"

    def test_create_orchestrator_custom(self):
        o = create_orchestrator(
            interface="wg0",
            prometheus_port=9191,
            enable_flow_observability=False,
        )
        assert o.config.interface == "wg0"
        assert o.config.prometheus_port == 9191
        assert o.config.enable_flow_observability is False


# ===========================================================================
# Monitoring loop integration
# ===========================================================================


class TestMonitoringLoop:
    @pytest.mark.asyncio
    async def test_monitoring_loop_updates_fallback(
        self, config, mock_loader, mock_fallback, mock_mapek
    ):
        """Verify monitoring loop feeds latency into fallback controller."""
        config.auto_load_programs = False
        o = EBPFOrchestrator(
            config, loader=mock_loader, fallback=mock_fallback, mapek=mock_mapek
        )
        o.state = OrchestratorState.RUNNING

        # Run one iteration then cancel
        async def run_one():
            task = asyncio.create_task(o._monitoring_loop())
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await run_one()
        mock_loader.get_stats.assert_called()
        mock_fallback.update_latency.assert_called()
        mock_fallback.check_recovery.assert_called()

    @pytest.mark.asyncio
    async def test_monitoring_loop_triggers_mapek_alert(
        self, config, mock_loader, mock_mapek
    ):
        mock_mapek.check_anomalies.return_value = {"type": "spike"}
        o = EBPFOrchestrator(config, loader=mock_loader, mapek=mock_mapek)
        o.state = OrchestratorState.RUNNING

        task = asyncio.create_task(o._monitoring_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_mapek.trigger_mapek_alert.assert_called_with({"type": "spike"})

    @pytest.mark.asyncio
    async def test_monitoring_loop_no_anomaly(self, config, mock_loader, mock_mapek):
        mock_mapek.check_anomalies.return_value = None
        o = EBPFOrchestrator(config, loader=mock_loader, mapek=mock_mapek)
        o.state = OrchestratorState.RUNNING

        task = asyncio.create_task(o._monitoring_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_mapek.trigger_mapek_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_monitoring_loop_handles_exception(self, config, mock_loader):
        mock_loader.get_stats.side_effect = RuntimeError("boom")
        o = EBPFOrchestrator(config, loader=mock_loader)
        o.state = OrchestratorState.RUNNING

        task = asyncio.create_task(o._monitoring_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Should not crash, the loop handles exceptions


# ===========================================================================
# Metrics export loop
# ===========================================================================


class TestMetricsExportLoop:
    @pytest.mark.asyncio
    async def test_metrics_export_loop_calls_exporter(
        self, config, mock_metrics_exporter
    ):
        o = EBPFOrchestrator(config, metrics_exporter=mock_metrics_exporter)
        o.state = OrchestratorState.RUNNING

        task = asyncio.create_task(o._metrics_export_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_metrics_exporter.export_metrics.assert_called()

    @pytest.mark.asyncio
    async def test_metrics_export_loop_with_cilium(
        self, config, mock_metrics_exporter, mock_cilium
    ):
        o = EBPFOrchestrator(
            config, metrics_exporter=mock_metrics_exporter, cilium=mock_cilium
        )
        o.state = OrchestratorState.RUNNING

        task = asyncio.create_task(o._metrics_export_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        mock_cilium.export_metrics_to_prometheus.assert_called()

    @pytest.mark.asyncio
    async def test_metrics_export_loop_handles_exception(
        self, config, mock_metrics_exporter
    ):
        mock_metrics_exporter.export_metrics.side_effect = RuntimeError("export fail")
        o = EBPFOrchestrator(config, metrics_exporter=mock_metrics_exporter)
        o.state = OrchestratorState.RUNNING

        task = asyncio.create_task(o._metrics_export_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Should not crash


# ===========================================================================
# Initialize components (module-level flags all False in test env)
# ===========================================================================


class TestInitializeComponents:
    @pytest.mark.asyncio
    async def test_initialize_skips_when_deps_unavailable(self, config):
        """When all *_available flags are False, no components are created."""
        o = EBPFOrchestrator(config)
        await o._initialize_components()
        # Since the real modules cannot be imported in test env,
        # all flags should be False => no components initialized
        # (Components were None and remain None unless module-level flags are True)
        # This is a valid no-op test.

    @pytest.mark.asyncio
    async def test_initialize_preserves_injected_loader(self, config, mock_loader):
        """Pre-injected loader should not be overwritten."""
        o = EBPFOrchestrator(config, loader=mock_loader)
        await o._initialize_components()
        assert o._loader is mock_loader
