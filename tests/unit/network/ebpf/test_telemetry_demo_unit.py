from __future__ import annotations

import importlib
import os
import random
import runpy
import sys
import types
from enum import Enum, IntEnum

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _FakePrometheus:
    def __init__(self):
        self.registered = []
        self.metrics = {}

    def register_metric(self, definition):
        self.registered.append(definition.name)

    def increment_metric(self, name, amount=1):
        self.metrics[name] = self.metrics.get(name, 0) + amount

    def set_metric(self, name, value):
        self.metrics[name] = value


class _FakePerfReader:
    def __init__(self):
        self.handlers = {}

    def register_handler(self, name, handler):
        self.handlers[name] = handler


class _FakeCollector:
    def __init__(self, config):
        self.config = config
        self.prometheus = _FakePrometheus()
        self.perf_reader = _FakePerfReader()
        self.started = False
        self.stopped = False
        self.programs = []
        self.perf_buffers = []
        self._stats = {"collection": {"total_collections": 1}}
        self._metrics = {
            "performance_monitor": {"cpu_usage_percent": 42},
            "network_monitor": {"packets_ingress_total": 7},
            "security_monitor": {"connection_attempts_total": 3},
        }

    def register_program(self, bpf, name, maps):
        self.programs.append((bpf, name, maps))

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def collect_all_metrics(self):
        return self._metrics

    def get_stats(self):
        return self._stats

    def start_perf_reading(self, perf_buffer_name):
        self.perf_buffers.append(perf_buffer_name)


def _build_fake_telemetry_module():
    fake = types.ModuleType("telemetry_module")

    class MetricType(Enum):
        COUNTER = "counter"
        GAUGE = "gauge"

    class EventSeverity(IntEnum):
        INFO = 1
        LOW = 2
        MEDIUM = 3
        HIGH = 4
        CRITICAL = 5

    class MetricDefinition:
        def __init__(self, name, type, description):
            self.name = name
            self.type = type
            self.description = description

    class TelemetryConfig:
        def __init__(self, **kwargs):
            self.prometheus_port = kwargs.get("prometheus_port", 9090)
            self.collection_interval = kwargs.get("collection_interval", 1.0)
            self.log_level = kwargs.get("log_level", "INFO")
            self.log_events = kwargs.get("log_events", False)

    class TelemetryEvent:
        def __init__(
            self,
            event_type="security",
            pid=0,
            severity=EventSeverity.INFO,
        ):
            self.event_type = event_type
            self.pid = pid
            self.severity = severity

    fake.MetricType = MetricType
    fake.EventSeverity = EventSeverity
    fake.MetricDefinition = MetricDefinition
    fake.TelemetryConfig = TelemetryConfig
    fake.TelemetryEvent = TelemetryEvent
    fake.EBPFTelemetryCollector = _FakeCollector
    fake.create_collector = lambda **kwargs: _FakeCollector(TelemetryConfig(**kwargs))
    fake.quick_start = lambda bpf, program_name, **kwargs: _FakeCollector(
        TelemetryConfig(**kwargs)
    )
    return fake


def test_fake_collector_start_stop_flags():
    collector = _FakeCollector(config=object())
    collector.start()
    collector.stop()
    assert collector.started is True
    assert collector.stopped is True


@pytest.fixture
def telemetry_demo_module(monkeypatch):
    fake_tm = _build_fake_telemetry_module()
    monkeypatch.setitem(sys.modules, "telemetry_module", fake_tm)
    monkeypatch.delitem(sys.modules, "src.network.ebpf.examples.telemetry_demo", raising=False)
    mod = importlib.import_module("src.network.ebpf.examples.telemetry_demo")
    monkeypatch.setattr(mod.signal, "signal", lambda *_args, **_kwargs: None)
    return mod, fake_tm


def _stop_after_one_sleep(monkeypatch, mod, demo):
    def _sleep(_seconds):
        demo.running = False

    monkeypatch.setattr(mod.time, "sleep", _sleep)


def test_signal_handler_stops_collector_and_exits(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("basic")

    stop_called = []
    demo.collector = types.SimpleNamespace(stop=lambda: stop_called.append(True))

    def _exit(code):
        raise SystemExit(code)

    monkeypatch.setattr(mod.sys, "exit", _exit)

    with pytest.raises(SystemExit) as exc:
        demo._signal_handler(2, None)

    assert exc.value.code == 0
    assert demo.running is False
    assert stop_called == [True]


def test_demo_basic_single_iteration(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("basic")
    _stop_after_one_sleep(monkeypatch, mod, demo)

    demo.demo_basic()

    assert demo.collector.started is True
    assert "demo_counter_total" in demo.collector.prometheus.registered
    assert "demo_gauge_value" in demo.collector.prometheus.registered
    assert demo.collector.prometheus.metrics["demo_counter_total"] == 1
    assert "demo_gauge_value" in demo.collector.prometheus.metrics


def test_demo_basic_logs_stats_on_tenth_iteration(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("basic")
    sleep_calls = {"n": 0}

    def _sleep(_seconds):
        sleep_calls["n"] += 1
        if sleep_calls["n"] >= 10:
            demo.running = False

    monkeypatch.setattr(mod.time, "sleep", _sleep)
    demo.demo_basic()

    assert sleep_calls["n"] == 10
    assert demo.collector.prometheus.metrics["demo_counter_total"] == 10


def test_demo_performance_import_error(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("performance")

    monkeypatch.setitem(sys.modules, "bcc", None)
    demo.demo_performance()

    assert demo.collector is None


def test_demo_network_import_error(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("network")

    monkeypatch.setitem(sys.modules, "bcc", None)
    demo.demo_network()

    assert demo.collector is None


def test_demo_security_import_error(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("security")

    monkeypatch.setitem(sys.modules, "bcc", None)
    demo.demo_security()

    assert demo.collector is None


def test_demo_performance_stub_when_program_missing(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("performance")

    fake_bcc = types.ModuleType("bcc")
    fake_bcc.BPF = lambda **_kwargs: object()
    monkeypatch.setitem(sys.modules, "bcc", fake_bcc)
    monkeypatch.setattr(mod.Path, "exists", lambda _self: False)
    _stop_after_one_sleep(monkeypatch, mod, demo)

    demo.demo_performance()

    assert demo.collector.started is True
    assert "cpu_usage_percent" in demo.collector.prometheus.registered
    assert "memory_usage_percent" in demo.collector.prometheus.registered
    assert "context_switches_per_sec" in demo.collector.prometheus.registered


def test_demo_performance_real_mode_and_fallback(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module

    class _FakeBPF:
        def __init__(self, src_file):
            self.src_file = src_file

    fake_bcc = types.ModuleType("bcc")
    fake_bcc.BPF = _FakeBPF
    monkeypatch.setitem(sys.modules, "bcc", fake_bcc)
    monkeypatch.setattr(mod.Path, "exists", lambda _self: True)

    demo = mod.TelemetryDemo("performance")
    _stop_after_one_sleep(monkeypatch, mod, demo)
    demo.demo_performance()
    assert demo.collector.programs[0][1] == "performance_monitor"

    called_stub = []

    class _BrokenBPF:
        def __init__(self, src_file):
            raise RuntimeError(f"cannot load {src_file}")

    fake_bcc.BPF = _BrokenBPF
    demo2 = mod.TelemetryDemo("performance")
    monkeypatch.setattr(demo2, "demo_performance_stub", lambda: called_stub.append(True))
    demo2.demo_performance()
    assert called_stub == [True]


def test_demo_performance_network_security_stub_helpers(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module

    for demo_type, method_name, metric_name in [
        ("performance", "demo_performance_stub", "cpu_usage_percent"),
        ("network", "demo_network_stub", "packets_ingress_total"),
        ("security", "demo_security_stub", "connection_attempts_total"),
    ]:
        demo = mod.TelemetryDemo(demo_type)
        _stop_after_one_sleep(monkeypatch, mod, demo)
        getattr(demo, method_name)()
        assert metric_name in demo.collector.prometheus.metrics


def test_demo_network_modes(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module

    class _FakeBPF:
        def __init__(self, src_file):
            self.src_file = src_file

    fake_bcc = types.ModuleType("bcc")
    fake_bcc.BPF = _FakeBPF
    monkeypatch.setitem(sys.modules, "bcc", fake_bcc)

    demo_stub = mod.TelemetryDemo("network")
    monkeypatch.setattr(mod.Path, "exists", lambda _self: False)
    _stop_after_one_sleep(monkeypatch, mod, demo_stub)
    demo_stub.demo_network()
    assert "packets_ingress_total" in demo_stub.collector.prometheus.registered
    assert "active_connections" in demo_stub.collector.prometheus.registered

    demo_real = mod.TelemetryDemo("network")
    monkeypatch.setattr(mod.Path, "exists", lambda _self: True)
    _stop_after_one_sleep(monkeypatch, mod, demo_real)
    demo_real.demo_network()
    assert demo_real.collector.programs[0][1] == "network_monitor"

    called_stub = []

    class _BrokenBPF:
        def __init__(self, src_file):
            raise RuntimeError("broken")

    fake_bcc.BPF = _BrokenBPF
    demo_fallback = mod.TelemetryDemo("network")
    monkeypatch.setattr(demo_fallback, "demo_network_stub", lambda: called_stub.append(True))
    demo_fallback.demo_network()
    assert called_stub == [True]


def test_demo_security_modes_and_event_handler(monkeypatch, telemetry_demo_module):
    mod, fake_tm = telemetry_demo_module

    class _FakeBPF:
        def __init__(self, src_file):
            self.src_file = src_file

    fake_bcc = types.ModuleType("bcc")
    fake_bcc.BPF = _FakeBPF
    monkeypatch.setitem(sys.modules, "bcc", fake_bcc)

    demo_stub = mod.TelemetryDemo("security")
    monkeypatch.setattr(mod.Path, "exists", lambda _self: False)
    _stop_after_one_sleep(monkeypatch, mod, demo_stub)
    demo_stub.demo_security()
    assert "security_event" in demo_stub.collector.perf_reader.handlers

    handler = demo_stub.collector.perf_reader.handlers["security_event"]
    high_event = fake_tm.TelemetryEvent(
        event_type="auth_fail",
        pid=1234,
        severity=fake_tm.EventSeverity.HIGH,
    )
    handler(high_event)

    demo_real = mod.TelemetryDemo("security")
    monkeypatch.setattr(mod.Path, "exists", lambda _self: True)
    _stop_after_one_sleep(monkeypatch, mod, demo_real)
    demo_real.demo_security()
    assert demo_real.collector.programs[0][1] == "security_monitor"
    assert "security_events" in demo_real.collector.perf_buffers
    real_handler = demo_real.collector.perf_reader.handlers["security_event"]
    real_handler(
        fake_tm.TelemetryEvent(
            event_type="kernel_alert",
            pid=99,
            severity=fake_tm.EventSeverity.HIGH,
        )
    )

    called_stub = []

    class _BrokenBPF:
        def __init__(self, src_file):
            raise RuntimeError("broken")

    fake_bcc.BPF = _BrokenBPF
    demo_fallback = mod.TelemetryDemo("security")
    monkeypatch.setattr(demo_fallback, "demo_security_stub", lambda: called_stub.append(True))
    demo_fallback.demo_security()
    assert called_stub == [True]


def test_demo_security_stub_threshold_counters(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("security")

    fake_bcc = types.ModuleType("bcc")
    fake_bcc.BPF = lambda **_kwargs: object()
    monkeypatch.setitem(sys.modules, "bcc", fake_bcc)
    monkeypatch.setattr(mod.Path, "exists", lambda _self: False)

    randints = [4, 2]
    randoms = [0.0, 0.0, 0.0]
    monkeypatch.setattr(random, "randint", lambda _a, _b: randints.pop(0))
    monkeypatch.setattr(random, "random", lambda: randoms.pop(0))
    _stop_after_one_sleep(monkeypatch, mod, demo)

    demo.demo_security()

    metrics = demo.collector.prometheus.metrics
    assert metrics["connection_attempts_total"] == 4
    assert metrics["failed_auth_attempts_total"] == 2
    assert metrics["suspicious_file_access_total"] == 1
    assert metrics["privilege_escalation_attempts_total"] == 1


def test_demo_all_single_iteration(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("all")
    _stop_after_one_sleep(monkeypatch, mod, demo)

    demo.demo_all()

    assert demo.collector.started is True
    assert "cpu_usage_percent" in demo.collector.prometheus.registered
    assert "packets_total" in demo.collector.prometheus.registered
    assert "security_events_total" in demo.collector.prometheus.registered


def test_demo_all_records_security_event_branch(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("all")
    _stop_after_one_sleep(monkeypatch, mod, demo)

    monkeypatch.setattr(random, "uniform", lambda _a, _b: 55.0)
    monkeypatch.setattr(random, "randint", lambda _a, _b: 11)
    monkeypatch.setattr(random, "random", lambda: 0.0)

    demo.demo_all()

    assert demo.collector.prometheus.metrics["security_events_total"] == 1


@pytest.mark.parametrize(
    ("demo_type", "method_name"),
    [
        ("basic", "demo_basic"),
        ("performance", "demo_performance"),
        ("network", "demo_network"),
        ("security", "demo_security"),
        ("all", "demo_all"),
    ],
)
def test_run_dispatches_to_selected_demo(
    monkeypatch, telemetry_demo_module, demo_type, method_name
):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo(demo_type)
    calls = []

    for name in ["demo_basic", "demo_performance", "demo_network", "demo_security", "demo_all"]:
        monkeypatch.setattr(demo, name, lambda n=name: calls.append(n))

    demo.run()
    assert calls == [method_name]


def test_run_unknown_demo_exits(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    demo = mod.TelemetryDemo("unknown")

    def _exit(code):
        raise SystemExit(code)

    monkeypatch.setattr(mod.sys, "exit", _exit)
    with pytest.raises(SystemExit) as exc:
        demo.run()

    assert exc.value.code == 1


def test_main_parses_args_and_runs_demo(monkeypatch, telemetry_demo_module):
    mod, _fake_tm = telemetry_demo_module
    calls = []

    class _DummyDemo:
        def __init__(self, demo_type):
            calls.append(("init", demo_type))

        def run(self):
            calls.append(("run", None))

    monkeypatch.setattr(mod, "TelemetryDemo", _DummyDemo)
    monkeypatch.setattr(mod.os, "geteuid", lambda: 1000)
    monkeypatch.setattr(
        mod.sys,
        "argv",
        ["telemetry_demo.py", "--demo", "basic", "--port", "9191", "--interval", "0.5", "--debug"],
    )

    mod.main()

    assert calls == [("init", "basic"), ("run", None)]


def test_dunder_main_executes_main_entrypoint(monkeypatch, telemetry_demo_module):
    mod, fake_tm = telemetry_demo_module
    monkeypatch.setitem(sys.modules, "telemetry_module", fake_tm)
    monkeypatch.setitem(sys.modules, "bcc", None)
    monkeypatch.setattr(mod.signal, "signal", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    monkeypatch.setattr(
        sys,
        "argv",
        ["telemetry_demo.py", "--demo", "performance"],
    )

    runpy.run_path(mod.__file__, run_name="__main__")
