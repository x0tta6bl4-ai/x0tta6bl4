from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from contextlib import contextmanager

import pytest

import src.monitoring.opentelemetry_tracing as mod


class _FakeSpan:
    def __init__(self, name: str):
        self.name = name
        self.attributes = {}
        self.failed_keys = []

    def set_attribute(self, key, value):
        if key == "bad":
            self.failed_keys.append(key)
            raise RuntimeError("bad attribute")
        self.attributes[key] = value


class _FakeSpanCM:
    def __init__(self, span):
        self.span = span

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeTracer:
    def __init__(self):
        self.started = []

    def start_as_current_span(self, name):
        span = _FakeSpan(name)
        self.started.append(span)
        return _FakeSpanCM(span)


class _FakeProvider:
    def __init__(self):
        self.processors = []

    def add_span_processor(self, processor):
        self.processors.append(processor)


def _patch_otel_runtime(monkeypatch):
    fake_trace = types.SimpleNamespace()
    fake_trace.provider = None
    fake_trace.tracer = _FakeTracer()
    fake_trace.set_tracer_provider = lambda p: setattr(fake_trace, "provider", p)
    fake_trace.get_tracer = lambda _name: fake_trace.tracer

    fake_metrics = types.SimpleNamespace()
    fake_metrics.provider = None
    fake_metrics.set_meter_provider = lambda p: setattr(fake_metrics, "provider", p)
    fake_metrics.get_meter = lambda _name: "meter-instance"

    monkeypatch.setattr(mod, "OTEL_AVAILABLE", True)
    monkeypatch.setattr(mod, "trace", fake_trace)
    monkeypatch.setattr(mod, "metrics", fake_metrics)
    monkeypatch.setattr(mod, "TracerProvider", _FakeProvider)
    monkeypatch.setattr(mod, "BatchSpanProcessor", lambda exporter: ("batch", exporter))
    monkeypatch.setattr(mod, "JaegerExporter", lambda **kwargs: ("jaeger", kwargs))
    monkeypatch.setattr(mod, "PrometheusMetricReader", lambda: "prom-reader")
    monkeypatch.setattr(
        mod,
        "MeterProvider",
        lambda metric_readers: ("meter-provider", tuple(metric_readers)),
    )
    return fake_trace, fake_metrics


def test_module_import_variants_cover_optional_import_paths(monkeypatch):
    def _ensure_module(name: str):
        existing = sys.modules.get(name)
        if existing is not None:
            return existing
        module = types.ModuleType(name)
        module.__path__ = []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, name, module)
        parent, _, child = name.rpartition(".")
        if parent:
            parent_mod = _ensure_module(parent)
            setattr(parent_mod, child, module)
        return module

    def _clear_otel_modules():
        for module_name in list(sys.modules):
            if module_name == "opentelemetry" or module_name.startswith("opentelemetry."):
                monkeypatch.delitem(sys.modules, module_name, raising=False)

    _clear_otel_modules()

    opentelemetry_mod = _ensure_module("opentelemetry")
    setattr(opentelemetry_mod, "metrics", _ensure_module("opentelemetry.metrics"))
    setattr(opentelemetry_mod, "trace", _ensure_module("opentelemetry.trace"))

    sdk_metrics_mod = _ensure_module("opentelemetry.sdk.metrics")
    setattr(sdk_metrics_mod, "MeterProvider", type("MeterProvider", (), {}))
    sdk_metrics_export_mod = _ensure_module("opentelemetry.sdk.metrics.export")
    setattr(
        sdk_metrics_export_mod,
        "PeriodicExportingMetricReader",
        type("PeriodicExportingMetricReader", (), {}),
    )
    sdk_trace_mod = _ensure_module("opentelemetry.sdk.trace")
    setattr(sdk_trace_mod, "TracerProvider", type("TracerProvider", (), {}))
    sdk_trace_export_mod = _ensure_module("opentelemetry.sdk.trace.export")
    setattr(
        sdk_trace_export_mod,
        "BatchSpanProcessor",
        type("BatchSpanProcessor", (), {}),
    )

    jaeger_mod = _ensure_module("opentelemetry.exporter.jaeger.thrift")
    setattr(jaeger_mod, "JaegerExporter", type("JaegerExporter", (), {}))
    prometheus_mod = _ensure_module("opentelemetry.exporter.prometheus")
    setattr(
        prometheus_mod,
        "PrometheusMetricReader",
        type("PrometheusMetricReader", (), {}),
    )

    fastapi_mod = _ensure_module("opentelemetry.instrumentation.fastapi")
    setattr(fastapi_mod, "FastAPIInstrumentor", type("FastAPIInstrumentor", (), {}))
    httpx_mod = _ensure_module("opentelemetry.instrumentation.httpx")
    setattr(httpx_mod, "HTTPXClientInstrumentor", type("HTTPXClientInstrumentor", (), {}))
    requests_mod = _ensure_module("opentelemetry.instrumentation.requests")
    setattr(requests_mod, "RequestsInstrumentor", type("RequestsInstrumentor", (), {}))
    sqlalchemy_mod = _ensure_module("opentelemetry.instrumentation.sqlalchemy")
    setattr(
        sqlalchemy_mod,
        "SQLAlchemyInstrumentor",
        type("SQLAlchemyInstrumentor", (), {}),
    )

    module_path = pathlib.Path(mod.__file__)
    success_spec = importlib.util.spec_from_file_location(
        "_otel_tracing_optional_success_cov",
        module_path,
    )
    assert success_spec is not None and success_spec.loader is not None
    success_module = importlib.util.module_from_spec(success_spec)
    success_spec.loader.exec_module(success_module)

    assert success_module.OTEL_AVAILABLE is True
    assert success_module.JAEGER_AVAILABLE is True
    assert success_module.PROMETHEUS_EXPORTER_AVAILABLE is True
    assert success_module.OTLP_AVAILABLE is False
    assert success_module.RequestsInstrumentor is not None

    _clear_otel_modules()
    bare_otel = types.ModuleType("opentelemetry")
    monkeypatch.setitem(sys.modules, "opentelemetry", bare_otel)

    failure_spec = importlib.util.spec_from_file_location(
        "_otel_tracing_optional_failure_cov",
        module_path,
    )
    assert failure_spec is not None and failure_spec.loader is not None
    failure_module = importlib.util.module_from_spec(failure_spec)
    failure_spec.loader.exec_module(failure_module)

    assert failure_module.OTEL_AVAILABLE is False


def test_manager_init_success_with_metrics(monkeypatch):
    fake_trace, fake_metrics = _patch_otel_runtime(monkeypatch)
    manager = mod.OTelTracingManager(service_name="svc", enable_metrics=True)

    assert manager.enabled is True
    assert manager.tracer is fake_trace.tracer
    assert manager.meter == "meter-instance"
    assert fake_trace.provider is not None
    assert fake_trace.provider.processors
    assert fake_metrics.provider[0] == "meter-provider"


def test_manager_init_exception_disables(monkeypatch):
    monkeypatch.setattr(mod, "OTEL_AVAILABLE", True)
    monkeypatch.setattr(mod, "JaegerExporter", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("jaeger down")))
    manager = mod.OTelTracingManager(service_name="svc")
    assert manager.enabled is False


def test_instrumentation_methods_success_and_errors(monkeypatch):
    _patch_otel_runtime(monkeypatch)
    manager = mod.OTelTracingManager(service_name="svc")

    fastapi_calls = []
    requests_calls = []
    sqlalchemy_calls = []

    class _FastAPIOK:
        @staticmethod
        def instrument_app(app):
            fastapi_calls.append(app)

    class _RequestsOK:
        def instrument(self):
            requests_calls.append(True)

    class _SQLAlchemyOK:
        def instrument(self, engine):
            sqlalchemy_calls.append(engine)

    monkeypatch.setattr(mod, "FastAPIInstrumentor", _FastAPIOK)
    monkeypatch.setattr(mod, "RequestsInstrumentor", _RequestsOK)
    monkeypatch.setattr(mod, "SQLAlchemyInstrumentor", _SQLAlchemyOK)

    app = object()
    engine = object()
    manager.instrument_fastapi(app)
    manager.instrument_requests()
    manager.instrument_sqlalchemy(engine)
    assert fastapi_calls == [app]
    assert requests_calls == [True]
    assert sqlalchemy_calls == [engine]

    class _FastAPIBad:
        @staticmethod
        def instrument_app(_app):
            raise RuntimeError("bad fastapi")

    class _RequestsBad:
        def instrument(self):
            raise RuntimeError("bad requests")

    class _SQLAlchemyBad:
        def instrument(self, engine):
            raise RuntimeError("bad sqlalchemy")

    monkeypatch.setattr(mod, "FastAPIInstrumentor", _FastAPIBad)
    monkeypatch.setattr(mod, "RequestsInstrumentor", _RequestsBad)
    monkeypatch.setattr(mod, "SQLAlchemyInstrumentor", _SQLAlchemyBad)

    manager.instrument_fastapi(app)
    manager.instrument_requests()
    manager.instrument_sqlalchemy(engine)

    manager.enabled = False
    manager.instrument_fastapi(app)
    manager.instrument_requests()
    manager.instrument_sqlalchemy(engine)


def test_span_context_and_decorator(monkeypatch):
    _patch_otel_runtime(monkeypatch)
    manager = mod.OTelTracingManager(service_name="svc")

    with manager.span("test.span", {"ok": 1, "bad": 2}) as span:
        assert span.name == "test.span"
    assert span.attributes["ok"] == 1
    assert span.failed_keys == ["bad"]

    manager.enabled = False
    with manager.span("disabled") as span2:
        assert span2 is None

    manager.enabled = True
    calls = []

    @manager.span_decorator("decorated.span", kind="unit")
    def _decorated(x):
        calls.append(x)
        return x + 1

    assert _decorated(3) == 4
    assert calls == [3]

    manager.enabled = False

    @manager.span_decorator("disabled.span")
    def _plain(x):
        return x * 2

    assert _plain(5) == 10


def test_initialize_tracing_enabled_and_disabled(monkeypatch):
    calls = {"fastapi": 0, "requests": 0}

    class _EnabledManager:
        def __init__(self, service_name):
            self.service_name = service_name
            self.enabled = True

        def instrument_fastapi(self, app):
            calls["fastapi"] += 1

        def instrument_requests(self):
            calls["requests"] += 1

    monkeypatch.setattr(mod, "OTelTracingManager", _EnabledManager)
    mod._tracer_manager = None
    mod._mapek_spans = None
    mod._network_spans = None
    mod._spiffe_spans = None
    mod._ml_spans = None

    mod.initialize_tracing("svc-enabled", app=object())
    assert mod.get_tracer_manager() is not None
    assert mod.get_mapek_spans() is not None
    assert mod.get_network_spans() is not None
    assert mod.get_spiffe_spans() is not None
    assert mod.get_ml_spans() is not None
    assert calls["fastapi"] == 1
    assert calls["requests"] == 1

    class _DisabledManager:
        def __init__(self, service_name):
            self.service_name = service_name
            self.enabled = False

        def instrument_fastapi(self, app):
            raise AssertionError("should not be called")

        def instrument_requests(self):
            raise AssertionError("should not be called")

    monkeypatch.setattr(mod, "OTelTracingManager", _DisabledManager)
    mod._mapek_spans = None
    mod._network_spans = None
    mod._spiffe_spans = None
    mod._ml_spans = None
    mod.initialize_tracing("svc-disabled", app=object())
    assert mod.get_mapek_spans() is None
    assert mod.get_network_spans() is None
    assert mod.get_spiffe_spans() is None
    assert mod.get_ml_spans() is None

    disabled = _DisabledManager("svc-disabled")
    with pytest.raises(AssertionError):
        disabled.instrument_fastapi(object())
    with pytest.raises(AssertionError):
        disabled.instrument_requests()
