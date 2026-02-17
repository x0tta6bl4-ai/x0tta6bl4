from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from contextlib import contextmanager

import pytest

import src.monitoring.tracing as mod


class _FakeStatusCode:
    OK = "OK"
    ERROR = "ERROR"


class _FakeStatus:
    def __init__(self, code, description=None):
        self.code = code
        self.description = description


class _FakeSpan:
    def __init__(self, name: str):
        self.name = name
        self.attributes = {}
        self.events = []
        self.status = None
        self.exceptions = []
        self.context = types.SimpleNamespace(trace_id=0xABC, span_id=0x123)

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def add_event(self, name, attributes=None, timestamp=None):
        self.events.append((name, attributes or {}, timestamp))

    def set_status(self, status):
        self.status = status

    def record_exception(self, exc):
        self.exceptions.append(exc)

    def get_span_context(self):
        return self.context


class _FakeSpanCM:
    def __init__(self, span: _FakeSpan, raise_on_enter: bool = False):
        self.span = span
        self.raise_on_enter = raise_on_enter

    def __enter__(self):
        if self.raise_on_enter:
            raise RuntimeError("enter failed")
        return self.span

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeTracer:
    def __init__(self):
        self.spans = []
        self.raise_on_enter = False

    def start_as_current_span(self, name):
        span = _FakeSpan(name)
        self.spans.append(span)
        return _FakeSpanCM(span, raise_on_enter=self.raise_on_enter)


class _FakeProvider:
    def __init__(self, resource=None, sampler=None):
        self.resource = resource
        self.sampler = sampler
        self.processors = []

    def add_span_processor(self, processor):
        self.processors.append(processor)


class _FakeHTTPXInstrumentor:
    def __init__(self):
        self.instrumented = False

    def instrument(self):
        self.instrumented = True


class _FakeFastAPIInstrumentor:
    called = 0

    @classmethod
    def instrument(cls):
        cls.called += 1


class _FakeTraceModule:
    def __init__(self):
        self.provider = None
        self.tracer = _FakeTracer()
        self.current_span = _FakeSpan("current")

    def set_tracer_provider(self, provider):
        self.provider = provider

    def get_tracer(self, *_args, **_kwargs):
        return self.tracer

    def get_current_span(self):
        return self.current_span


class _Recorder:
    def __init__(self):
        self.values = []

    def __call__(self, value=None):
        self.values.append(value)
        return value


def _patch_otel(monkeypatch):
    fake_trace = _FakeTraceModule()
    set_global_calls = _Recorder()
    detach_calls = _Recorder()

    monkeypatch.setattr(mod, "OPENTELEMETRY_AVAILABLE", True)
    monkeypatch.setattr(mod, "trace", fake_trace)
    monkeypatch.setattr(mod, "Context", dict)
    monkeypatch.setattr(mod, "attach", lambda ctx: f"token:{id(ctx)}")
    monkeypatch.setattr(mod, "detach", lambda token: detach_calls(token))
    monkeypatch.setattr(mod, "set_value", lambda key, value: {key: value})

    monkeypatch.setattr(mod, "SERVICE_NAME", "service.name", raising=False)
    monkeypatch.setattr(mod, "SERVICE_VERSION", "service.version", raising=False)
    monkeypatch.setattr(
        mod, "Resource", types.SimpleNamespace(create=lambda attrs: attrs), raising=False
    )

    monkeypatch.setattr(mod, "ALWAYS_ON", "always_on", raising=False)
    monkeypatch.setattr(mod, "ALWAYS_OFF", "always_off", raising=False)
    monkeypatch.setattr(
        mod, "TraceIdRatioBased", lambda ratio: ("ratio", ratio), raising=False
    )
    monkeypatch.setattr(mod, "ParentBased", lambda root=None: ("parent", root), raising=False)

    monkeypatch.setattr(mod, "TracerProvider", _FakeProvider, raising=False)
    monkeypatch.setattr(
        mod,
        "BatchSpanProcessor",
        lambda exporter, **kwargs: ("batch", exporter, kwargs),
        raising=False,
    )
    monkeypatch.setattr(
        mod, "ConsoleSpanExporter", lambda: "console_exporter", raising=False
    )
    monkeypatch.setattr(mod, "JaegerExporter", lambda **kwargs: ("jaeger", kwargs), raising=False)
    monkeypatch.setattr(mod, "ZipkinExporter", lambda **kwargs: ("zipkin", kwargs), raising=False)
    monkeypatch.setattr(mod, "OTLPSpanExporter", lambda **kwargs: ("otlp", kwargs), raising=False)

    monkeypatch.setattr(
        mod, "TraceContextTextMapPropagator", lambda: "tracecontext", raising=False
    )
    monkeypatch.setattr(mod, "B3MultiFormat", lambda: "b3", raising=False)
    monkeypatch.setattr(
        mod,
        "CompositeHTTPPropagator",
        lambda items: ("composite", tuple(items)),
        raising=False,
    )
    monkeypatch.setattr(
        mod, "set_global_textmap", lambda propagator: set_global_calls(propagator), raising=False
    )

    monkeypatch.setattr(mod, "FastAPIInstrumentor", _FakeFastAPIInstrumentor, raising=False)
    monkeypatch.setattr(mod, "HTTPXClientInstrumentor", _FakeHTTPXInstrumentor, raising=False)

    monkeypatch.setattr(mod, "Status", _FakeStatus, raising=False)
    monkeypatch.setattr(mod, "StatusCode", _FakeStatusCode, raising=False)

    monkeypatch.setattr(mod, "extract", lambda carrier: {"extracted": carrier}, raising=False)

    def _inject(carrier):
        carrier["traceparent"] = "00-abc-123-01"

    monkeypatch.setattr(mod, "inject", _inject, raising=False)

    return fake_trace, set_global_calls, detach_calls


def test_module_import_success_path_with_fake_opentelemetry(monkeypatch):
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

    for module_name in list(sys.modules):
        if module_name == "opentelemetry" or module_name.startswith("opentelemetry."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)

    trace_mod = _ensure_module("opentelemetry.trace")
    setattr(trace_mod, "Status", type("Status", (), {}))
    setattr(trace_mod, "StatusCode", type("StatusCode", (), {}))

    context_mod = _ensure_module("opentelemetry.context")
    setattr(context_mod, "Context", dict)
    setattr(context_mod, "attach", lambda _ctx: "token")
    setattr(context_mod, "detach", lambda _token: None)
    setattr(context_mod, "set_value", lambda k, v: {k: v})

    jaeger_mod = _ensure_module("opentelemetry.exporter.jaeger.thrift")
    setattr(jaeger_mod, "JaegerExporter", type("JaegerExporter", (), {}))

    otlp_mod = _ensure_module("opentelemetry.exporter.otlp.proto.grpc.trace_exporter")
    setattr(otlp_mod, "OTLPSpanExporter", type("OTLPSpanExporter", (), {}))

    zipkin_mod = _ensure_module("opentelemetry.exporter.zipkin.json")
    setattr(zipkin_mod, "ZipkinExporter", type("ZipkinExporter", (), {}))

    fastapi_mod = _ensure_module("opentelemetry.instrumentation.fastapi")
    setattr(fastapi_mod, "FastAPIInstrumentor", type("FastAPIInstrumentor", (), {}))

    httpx_mod = _ensure_module("opentelemetry.instrumentation.httpx")
    setattr(httpx_mod, "HTTPXClientInstrumentor", type("HTTPXClientInstrumentor", (), {}))

    propagate_mod = _ensure_module("opentelemetry.propagate")
    setattr(propagate_mod, "extract", lambda *_args, **_kwargs: {})
    setattr(propagate_mod, "inject", lambda *_args, **_kwargs: None)
    setattr(propagate_mod, "set_global_textmap", lambda *_args, **_kwargs: None)

    b3_mod = _ensure_module("opentelemetry.propagators.b3")
    setattr(b3_mod, "B3MultiFormat", type("B3MultiFormat", (), {}))

    composite_mod = _ensure_module("opentelemetry.propagators.composite")
    setattr(
        composite_mod,
        "CompositeHTTPPropagator",
        type("CompositeHTTPPropagator", (), {}),
    )

    tracecontext_mod = _ensure_module("opentelemetry.propagators.tracecontext")
    setattr(
        tracecontext_mod,
        "TraceContextTextMapPropagator",
        type("TraceContextTextMapPropagator", (), {}),
    )

    resources_mod = _ensure_module("opentelemetry.sdk.resources")
    setattr(resources_mod, "SERVICE_NAME", "service.name")
    setattr(resources_mod, "SERVICE_VERSION", "service.version")
    setattr(resources_mod, "Resource", type("Resource", (), {}))

    sdk_trace_mod = _ensure_module("opentelemetry.sdk.trace")
    setattr(sdk_trace_mod, "TracerProvider", type("TracerProvider", (), {}))

    sdk_trace_export_mod = _ensure_module("opentelemetry.sdk.trace.export")
    setattr(
        sdk_trace_export_mod,
        "BatchSpanProcessor",
        type("BatchSpanProcessor", (), {}),
    )
    setattr(
        sdk_trace_export_mod,
        "ConsoleSpanExporter",
        type("ConsoleSpanExporter", (), {}),
    )

    sdk_sampling_mod = _ensure_module("opentelemetry.sdk.trace.sampling")
    setattr(sdk_sampling_mod, "ALWAYS_OFF", object())
    setattr(sdk_sampling_mod, "ALWAYS_ON", object())
    setattr(sdk_sampling_mod, "ParentBased", type("ParentBased", (), {}))
    setattr(
        sdk_sampling_mod,
        "TraceIdRatioBased",
        type("TraceIdRatioBased", (), {}),
    )

    module_name = "_tracing_success_import_cov"
    module_path = pathlib.Path(mod.__file__)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    reloaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reloaded)

    assert reloaded.OPENTELEMETRY_AVAILABLE is True
    assert reloaded.FastAPIInstrumentor is not None
    assert reloaded.HTTPXClientInstrumentor is not None


def test_init_without_opentelemetry(monkeypatch):
    monkeypatch.setattr(mod, "OPENTELEMETRY_AVAILABLE", False)
    manager = mod.TracingManager()
    assert manager.tracer is None


def test_init_with_exporters_and_context_propagation(monkeypatch):
    fake_trace, set_global_calls, _detach_calls = _patch_otel(monkeypatch)

    manager = mod.TracingManager(
        service_name="svc",
        service_version="1.0",
        jaeger_endpoint="http://localhost:14268/api/traces",
        zipkin_endpoint="http://localhost:9411/api/v2/spans",
        otlp_endpoint="http://localhost:4317",
        enable_console=True,
        trace_sampling_ratio=0.5,
        enable_fastapi_instrumentation=True,
    )

    assert manager.tracer is fake_trace.tracer
    assert fake_trace.provider is not None
    assert len(fake_trace.provider.processors) >= 3
    assert set_global_calls.values


def test_init_exporter_errors_and_fallback_console(monkeypatch):
    fake_trace, _set_global_calls, _detach_calls = _patch_otel(monkeypatch)

    monkeypatch.setattr(mod, "OTLPSpanExporter", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("otlp fail")))
    monkeypatch.setattr(mod, "JaegerExporter", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("jaeger fail")))
    monkeypatch.setattr(mod, "ZipkinExporter", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("zipkin fail")))

    manager = mod.TracingManager(
        enable_console=False,
        otlp_endpoint="http://collector:4317",
        jaeger_endpoint="http://jaeger:14268/api/traces",
        zipkin_endpoint="http://zipkin:9411/api/v2/spans",
        trace_sampling_ratio=0.0,
    )
    assert manager.tracer is fake_trace.tracer
    assert fake_trace.provider is not None
    assert len(fake_trace.provider.processors) >= 1


def test_init_fastapi_instrumentation_failure_and_outer_init_failure(monkeypatch):
    _patch_otel(monkeypatch)

    class _BrokenFastAPI:
        @classmethod
        def instrument(cls):
            raise RuntimeError("fastapi broken")

    class _BrokenHTTPX:
        def instrument(self):
            raise RuntimeError("httpx broken")

    monkeypatch.setattr(mod, "FastAPIInstrumentor", _BrokenFastAPI, raising=False)
    monkeypatch.setattr(mod, "HTTPXClientInstrumentor", _BrokenHTTPX, raising=False)

    manager = mod.TracingManager(enable_console=True, enable_fastapi_instrumentation=True)
    assert manager.tracer is not None
    with pytest.raises(RuntimeError):
        _BrokenHTTPX().instrument()

    _patch_otel(monkeypatch)
    monkeypatch.setattr(
        mod,
        "TracerProvider",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("provider fail")),
        raising=False,
    )
    failed = mod.TracingManager(enable_console=True)
    assert failed.tracer is None


def test_span_context_manager_and_error_path(monkeypatch):
    _patch_otel(monkeypatch)
    manager = mod.TracingManager(enable_console=True)

    with manager.span("test.span", {"x": 1}) as span:
        assert span.name == "test.span"
        assert span.attributes["x"] == "1"

    manager.tracer.raise_on_enter = True
    with manager.span("broken") as span:
        assert span is None


def test_trace_mape_k_cycle_and_full_cycle(monkeypatch):
    _patch_otel(monkeypatch)
    manager = mod.TracingManager(enable_console=True)

    phases = ["monitor", "analyze", "plan", "execute", "knowledge"]
    for phase in phases:
        with manager.trace_mape_k_cycle(phase, {"cycle_id": "c1", "anomalies_count": 3}) as span:
            assert span is not None

    with manager.trace_full_mape_k_cycle("cycle-1", "node-1") as span:
        assert span.attributes["mape_k.cycle_id"] == "cycle-1"

    manager.tracer.raise_on_enter = True
    with manager.trace_mape_k_cycle("monitor") as span:
        assert span is None


def test_trace_network_rag_and_function_decorator(monkeypatch):
    _patch_otel(monkeypatch)
    manager = mod.TracingManager(enable_console=True)

    manager.trace_network_adaptation("failover", {"route": "a->b"})
    manager.trace_rag_retrieval("query", results_count=3, latency_ms=12.5)

    @manager.trace_function(span_name="decorated", attributes={"k": "v"})
    def ok_fn(value):
        return value + 1

    assert ok_fn(1) == 2

    @manager.trace_function(span_name="boom")
    def bad_fn():
        raise ValueError("bad")

    with pytest.raises(ValueError):
        bad_fn()


def test_context_extract_inject_create_span_events_and_ids(monkeypatch):
    fake_trace, _set_global_calls, detach_calls = _patch_otel(monkeypatch)
    manager = mod.TracingManager(enable_console=True)

    headers = {"X-Test": "1"}
    context = manager.extract_context_from_headers(headers)
    assert context["extracted"]["x-test"] == "1"

    merged = manager.inject_context_to_headers({"a": "b"})
    assert "traceparent" in merged

    with manager.create_span_from_context("from-context", context=context, attributes={"a": 1}) as span:
        assert span.attributes["a"] == "1"

    assert detach_calls.values

    with manager.create_span_from_context("no-context") as span:
        assert span is not None

    manager.add_span_event(fake_trace.current_span, "evt", {"x": "y"}, 123.0)
    assert fake_trace.current_span.events

    assert manager.get_current_span() is fake_trace.current_span
    assert manager.get_current_trace_id() == format(fake_trace.current_span.context.trace_id, "032x")
    assert manager.get_current_span_id() == format(fake_trace.current_span.context.span_id, "016x")

    fake_trace.current_span = None
    assert manager.get_current_trace_id() is None
    assert manager.get_current_span_id() is None


def test_extract_inject_and_get_current_span_failure_paths(monkeypatch):
    _patch_otel(monkeypatch)
    manager = mod.TracingManager(enable_console=True)

    monkeypatch.setattr(mod, "extract", lambda _carrier: (_ for _ in ()).throw(RuntimeError("extract fail")))
    assert manager.extract_context_from_headers({"a": "b"}) is None

    monkeypatch.setattr(mod, "inject", lambda _carrier: (_ for _ in ()).throw(RuntimeError("inject fail")))
    assert manager.inject_context_to_headers({"a": "b"}) == {"a": "b"}

    manager.add_span_event(None, "noop")

    monkeypatch.setattr(mod, "trace", types.SimpleNamespace(get_current_span=lambda: (_ for _ in ()).throw(RuntimeError("boom"))))
    assert manager.get_current_span() is None


def test_noop_paths_when_tracer_unavailable(monkeypatch):
    monkeypatch.setattr(mod, "OPENTELEMETRY_AVAILABLE", False)
    manager = mod.TracingManager()

    with manager.span("noop") as span:
        assert span is None

    with manager.trace_mape_k_cycle("monitor") as span:
        assert span is None

    with manager.trace_full_mape_k_cycle("c1", "n1") as span:
        assert span is None

    manager.trace_network_adaptation("action", {"k": "v"})
    manager.trace_rag_retrieval("q", 1, 1.0)

    @manager.trace_function(span_name="noop.decorator")
    def plain(value):
        return value * 2

    assert plain(3) == 6

    with manager.create_span_from_context("ctx.noop") as span:
        assert span is None

    assert manager.extract_context_from_headers({"A": "B"}) is None
    assert manager.inject_context_to_headers({"A": "B"}) == {"A": "B"}
    assert manager.get_current_span() is None


def test_trace_full_network_rag_event_and_id_error_paths(monkeypatch):
    fake_trace, _set_global_calls, _detach_calls = _patch_otel(monkeypatch)
    manager = mod.TracingManager(enable_console=True)

    manager.tracer.raise_on_enter = True
    with manager.trace_full_mape_k_cycle("cycle-x", "node-x") as span:
        assert span is None

    manager.trace_network_adaptation("route_switch", {"a": 1})
    manager.trace_rag_retrieval("query", results_count=1, latency_ms=2.0)

    class _BadSpan:
        def add_event(self, *_args, **_kwargs):
            raise RuntimeError("event fail")

    manager.add_span_event(_BadSpan(), "evt.bad")

    class _BadContextSpan:
        def get_span_context(self):
            raise RuntimeError("context fail")

    fake_trace.current_span = _BadContextSpan()
    assert manager.get_current_trace_id() is None
    assert manager.get_current_span_id() is None


def test_initialize_tracing_and_global_getter(monkeypatch):
    fake_trace, _set_global_calls, _detach_calls = _patch_otel(monkeypatch)

    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.25")
    manager = mod.initialize_tracing(service_name="svc", enable_console=True)
    assert manager.tracer is fake_trace.tracer
    assert mod.get_tracing_manager() is manager
