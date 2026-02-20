"""Extended unit tests for eBPF Monitoring Integration."""
import os
import time
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.monitoring_integration import (
    EBPFMonitoringIntegration,
    EBPF_AVAILABLE,
)


class TestEBPFMonitoringInit:
    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_basic_init(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            interface="eth0",
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert m.interface == "eth0"
        assert m.loaded_programs == {}
        assert m.enabled_programs == []

    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", False)
    def test_raises_without_ebpf(self):
        with pytest.raises(ImportError):
            EBPFMonitoringIntegration()


class TestLoadXdpCounter:
    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_program_not_found(self, mock_exp, mock_reader, mock_loader):
        loader = MagicMock()
        loader.programs_dir = MagicMock()
        loader.programs_dir.__truediv__ = MagicMock()
        path = MagicMock()
        path.exists.return_value = False
        loader.programs_dir.__truediv__.return_value = path
        mock_loader.return_value = loader
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=True,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert "xdp_counter" not in m.loaded_programs

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_load_success(self, mock_exp, mock_reader, mock_loader):
        loader = MagicMock()
        path = MagicMock()
        path.exists.return_value = True
        loader.programs_dir.__truediv__ = MagicMock(return_value=path)
        loader.load_program.return_value = "prog-id-1"
        loader.attach_to_interface.return_value = True
        mock_loader.return_value = loader
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=True,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert "xdp_counter" in m.loaded_programs
        assert "xdp_counter" in m.enabled_programs

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_attach_fails(self, mock_exp, mock_reader, mock_loader):
        loader = MagicMock()
        path = MagicMock()
        path.exists.return_value = True
        loader.programs_dir.__truediv__ = MagicMock(return_value=path)
        loader.load_program.return_value = "prog-id-1"
        loader.attach_to_interface.return_value = False
        mock_loader.return_value = loader
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=True,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert "xdp_counter" not in m.enabled_programs


class TestGetPacketCounters:
    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_no_xdp_counter(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert m.get_packet_counters() is None

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_read_error(self, mock_exp, mock_reader, mock_loader):
        reader = MagicMock()
        reader.read_map.side_effect = Exception("read fail")
        mock_reader.return_value = reader
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        m.loaded_programs["xdp_counter"] = "prog-1"
        assert m.get_packet_counters() is None


class TestGetMetrics:
    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_basic_metrics(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        metrics = m.get_metrics()
        assert "interface" in metrics
        assert "enabled_programs" in metrics
        assert "timestamp" in metrics

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_with_graphsage(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        m.graphsage_streaming = MagicMock()
        m.graphsage_streaming.get_metrics.return_value = {"flow_count": 10}
        metrics = m.get_metrics()
        assert "graphsage_streaming" in metrics

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_with_cilium(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        m.cilium_integration = MagicMock()
        m.cilium_integration.get_flow_metrics.return_value = {"flows": 5}
        metrics = m.get_metrics()
        assert "cilium_flows" in metrics


class TestExportAndShutdown:
    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_export_success(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert m.export_to_prometheus() is True

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_export_failure(self, mock_exp, mock_reader, mock_loader):
        exp = MagicMock()
        exp.export_metrics.side_effect = Exception("fail")
        mock_exp.return_value = exp
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        assert m.export_to_prometheus() is False

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_shutdown(self, mock_exp, mock_reader, mock_loader):
        loader = MagicMock()
        loader.loaded_programs = {"prog-1": {"attached_to": "eth0"}}
        mock_loader.return_value = loader
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        m.loaded_programs = {"xdp_counter": "prog-1"}
        m.shutdown()
        loader.unload_program.assert_called_once()
        assert m.loaded_programs == {}

    @patch("src.network.ebpf.monitoring_integration.EBPFLoader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMapReader")
    @patch("src.network.ebpf.monitoring_integration.EBPFMetricsExporter")
    @patch("src.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
    def test_shutdown_with_cilium(self, mock_exp, mock_reader, mock_loader):
        m = EBPFMonitoringIntegration(
            enable_xdp_counter=False,
            enable_graphsage_streaming=False,
            enable_cilium_integration=False,
        )
        m.cilium_integration = MagicMock()
        m.shutdown()
        m.cilium_integration.shutdown.assert_called_once()
