import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.libx0t.network.ebpf.dynamic_fallback import DynamicFallbackController
from src.libx0t.network.ebpf.orchestrator import (
    EBPFOrchestrator as RuntimeOrchestrator,
    OrchestratorConfig as RuntimeOrchestratorConfig,
)
from src.libx0t.network.ebpf.performance_monitor import (
    AlertSeverity,
    EBPFPerformanceMonitor,
)
from src.libx0t.network.ebpf.telemetry_module import (
    EventSeverity as LibTelemetrySeverity,
    SecurityManager as LibTelemetrySecurityManager,
    TelemetryConfig as LibTelemetryConfig,
    TelemetryEvent as LibTelemetryEvent,
)
from src.network.ebpf.telemetry.models import (
    EventSeverity,
    TelemetryConfig,
    TelemetryEvent,
)
from src.network.ebpf.telemetry.security import SecurityManager


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


def test_libx0t_dynamic_fallback_thinking_redacts_node_id():
    triggered = []
    controller = DynamicFallbackController(
        latency_threshold_ms=10.0,
        cooldown_seconds=0.0,
    )
    controller.register_fallback_trigger(triggered.append)

    for _ in range(10):
        controller.update_latency("secret-node-id", 50.0)

    assert triggered == ["secret-node-id"]
    status = controller.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "healing"
    assert (
        status["last_thinking_context"]["applied"]["framing"]["constraints"][
            "mesh_reroute_delivery_proven"
        ]
        is False
    )
    _assert_redacted(status, "secret-node-id")


@pytest.mark.asyncio
async def test_libx0t_performance_monitor_thinking_marks_synthetic_metrics():
    monitor = EBPFPerformanceMonitor(prometheus_port=19090)

    await monitor._generate_alert(
        "secret alert title",
        "secret alert message",
        AlertSeverity.WARNING,
    )
    report = monitor.get_performance_report()

    assert report["metric_source"] == "synthetic_mock_generators"
    assert report["real_ebpf_map_evidence"] is False
    status = monitor.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    assert (
        status["last_thinking_context"]["applied"]["framing"]["constraints"][
            "synthetic_metrics_are_not_dataplane_proof"
        ]
        is True
    )
    _assert_redacted(status, "secret alert title", "secret alert message", "19090")


def test_telemetry_security_thinking_redacts_paths_metric_names_and_events():
    manager = SecurityManager(TelemetryConfig())
    assert manager.validate_metric_name("secret/metric") == (
        False,
        "Invalid character in metric name: /",
    )
    manager.sanitize_path("../secret/path/token.txt")
    assert manager.validate_event(
        TelemetryEvent(
            event_type="secret-event-type",
            timestamp_ns=1,
            cpu_id=1,
            pid=123,
            data={"secret": "secret-event-payload-value"},
            severity=EventSeverity.INFO,
        )
    )[0] is True

    status = manager.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        status,
        "secret/metric",
        "../secret/path/token.txt",
        "secret-event-type",
        "secret-event-payload-value",
    )

    lib_manager = LibTelemetrySecurityManager(LibTelemetryConfig())
    lib_manager.sanitize_string("../secret-string\x00")
    assert lib_manager.validate_event(
        LibTelemetryEvent(
            event_type="secret-lib-event",
            timestamp_ns=1,
            cpu_id=1,
            pid=123,
            data={"secret": "secret-lib-event-payload-value"},
            severity=LibTelemetrySeverity.INFO,
        )
    )[0] is True
    lib_status = lib_manager.get_thinking_status()
    assert lib_status["thinking"]["profile"]["role"] == "security"
    _assert_redacted(
        lib_status,
        "secret-string",
        "secret-lib-event",
        "secret-lib-event-payload-value",
    )


def test_libx0t_runtime_orchestrator_thinking_redacts_interface():
    orchestrator = RuntimeOrchestrator(
        RuntimeOrchestratorConfig(
            interface="secret-iface0",
            auto_load_programs=False,
            enable_flow_observability=False,
            enable_metrics_export=False,
            enable_performance_monitoring=False,
            enable_dynamic_fallback=False,
            enable_mapek_integration=False,
            enable_network_probes=False,
        )
    )

    status = orchestrator.get_status()
    assert status["interface"] == "secret-iface0"
    thinking = orchestrator.get_thinking_status()
    assert thinking["thinking"]["profile"]["role"] == "coordinator"
    _assert_redacted(thinking, "secret-iface0")


class _DummyComponent:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    async def start(self):
        return None

    async def stop(self):
        return None

    async def initialize(self):
        return None

    async def shutdown(self):
        return None

    async def load_program(self, program_name, program_path, **kwargs):
        return {"success": True}

    async def unload_program(self, program_name):
        return {"success": True}

    def get_status(self):
        return {"status": "ok"}

    def get_stats(self):
        return {"stats": 1}

    def get_flow_metrics(self):
        return {"flows": 1}

    def list_loaded_programs(self):
        return {"programs": []}


@pytest.mark.asyncio
async def test_libx0t_legacy_orchestrator_thinking_redacts_program_path():
    import src.libx0t.network.ebpf.ebpf_orchestrator as legacy

    with (
        patch.object(legacy, "EBPFLoader", _DummyComponent),
        patch.object(legacy, "MeshNetworkProbes", _DummyComponent),
        patch.object(legacy, "EBPFMetricsExporter", _DummyComponent),
        patch.object(legacy, "CiliumLikeIntegration", _DummyComponent),
        patch.object(legacy, "DynamicFallbackController", _DummyComponent),
        patch.object(legacy, "EBPFMAPEKIntegration", _DummyComponent),
        patch.object(legacy, "RingBufferReader", _DummyComponent),
    ):
        orchestrator = legacy.EBPFOrchestrator(
            legacy.OrchestratorConfig(interface="secret-iface1")
        )

    await orchestrator.load_program("secret-program", "/secret/path/program.o")
    thinking = orchestrator.get_thinking_status()
    assert thinking["thinking"]["profile"]["role"] == "coordinator"
    _assert_redacted(
        thinking,
        "secret-iface1",
        "secret-program",
        "/secret/path/program.o",
    )
