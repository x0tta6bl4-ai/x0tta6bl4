"""Runtime-thinking checks for libx0t eBPF monitoring integration."""

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.libx0t.network.ebpf.monitoring_integration import EBPFMonitoringIntegration


def _assert_libx0t_ebpf_thinking(status, operation):
    techniques = set(status["techniques"])
    assert status["profile"]["role"] == "monitoring"
    assert "mape_k" in techniques
    assert "mind_maps" in techniques
    assert "causal_analysis" in techniques
    assert "graphsage" in techniques
    assert "zero_trust_review" in techniques
    assert "reverse_planning" in techniques

    context = status["last_context"]
    assert context["role"] == "monitoring"
    assert context["applied"]["framing"]["problem"] == (
        "libx0t_ebpf_monitoring_integration_operation"
    )
    constraints = context["applied"]["framing"]["constraints"]
    assert constraints["operation"] == operation
    assert constraints["interface_redacted"] is True
    assert constraints["local_integration_is_not_dataplane_proof"] is True
    assert constraints["local_integration_is_not_kernel_load_proof"] is True
    assert "interface_hash" in constraints


@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFLoader")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFMapReader")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFMetricsExporter")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
def test_libx0t_monitoring_thinking_redacts_interface(
    mock_exp,
    mock_reader,
    mock_loader,
):
    monitor = EBPFMonitoringIntegration(
        interface="secret-if0",
        enable_xdp_counter=False,
        enable_graphsage_streaming=False,
        enable_cilium_integration=False,
    )

    status = monitor.get_thinking_status()
    _assert_libx0t_ebpf_thinking(status, "init")
    assert "secret-if0" not in str(status)


@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFLoader")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFMapReader")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFMetricsExporter")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
def test_libx0t_monitoring_load_success_redacts_program_id(
    mock_exp,
    mock_reader,
    mock_loader,
):
    loader = MagicMock()
    object_path = MagicMock()
    object_path.exists.return_value = True
    loader.programs_dir.__truediv__ = MagicMock(return_value=object_path)
    loader.load_program.return_value = "secret-program-id"
    loader.attach_to_interface.return_value = True
    mock_loader.return_value = loader

    monitor = EBPFMonitoringIntegration(
        interface="secret-if0",
        enable_xdp_counter=True,
        enable_graphsage_streaming=False,
        enable_cilium_integration=False,
    )

    assert "xdp_counter" in monitor.enabled_programs
    status = monitor.get_thinking_status()
    _assert_libx0t_ebpf_thinking(status, "load_xdp_counter")
    assert "secret-program-id" not in str(status)
    assert "secret-if0" not in str(status)


@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFLoader")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFMapReader")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPFMetricsExporter")
@patch("src.libx0t.network.ebpf.monitoring_integration.EBPF_AVAILABLE", True)
def test_libx0t_monitoring_map_error_redacts_error_text(
    mock_exp,
    mock_reader,
    mock_loader,
):
    reader = MagicMock()
    reader.read_map.side_effect = Exception("secret map failure detail")
    mock_reader.return_value = reader

    monitor = EBPFMonitoringIntegration(
        interface="secret-if0",
        enable_xdp_counter=False,
        enable_graphsage_streaming=False,
        enable_cilium_integration=False,
    )
    monitor.loaded_programs["xdp_counter"] = "secret-program-id"

    assert monitor.get_packet_counters() is None
    status = monitor.get_thinking_status()
    _assert_libx0t_ebpf_thinking(status, "get_packet_counters")
    rendered = str(status)
    assert "secret map failure detail" not in rendered
    assert "secret-program-id" not in rendered
    assert "secret-if0" not in rendered
