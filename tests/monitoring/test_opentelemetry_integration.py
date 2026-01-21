"""
Test suite for OpenTelemetry distributed tracing integration.

Tests tracing, spans, metrics, and observability collection.
"""

import pytest
import asyncio
from datetime import datetime
from src.monitoring.opentelemetry_integration import (
    SpanKind,
    SpanStatus,
    Span,
    SpanEvent,
    TraceContext,
    TracingProvider,
    ConsoleSpanExporter,
    MemorySpanExporter,
    MeterProvider,
    Counter,
    Histogram,
    Gauge,
    InstrumentationHelper,
    ObservabilityCollector,
    initialize_observability,
    get_observability_collector
)


class TestSpanKind:
    """Test SpanKind enum"""
    
    def test_span_kinds_exist(self):
        assert SpanKind.INTERNAL.value == "INTERNAL"
        assert SpanKind.SERVER.value == "SERVER"
        assert SpanKind.CLIENT.value == "CLIENT"
        assert SpanKind.PRODUCER.value == "PRODUCER"
        assert SpanKind.CONSUMER.value == "CONSUMER"


class TestSpanStatus:
    """Test SpanStatus enum"""
    
    def test_span_status_values(self):
        assert SpanStatus.UNSET.value == "UNSET"
        assert SpanStatus.OK.value == "OK"
        assert SpanStatus.ERROR.value == "ERROR"


class TestSpan:
    """Test Span class"""
    
    def test_span_creation(self):
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id="parent123",
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        assert span.trace_id == "trace123"
        assert span.span_id == "span123"
        assert span.name == "test_span"
        assert span.kind == SpanKind.INTERNAL
    
    def test_span_end(self):
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        assert span.end_time is None
        span.end()
        
        assert span.end_time is not None
        assert span.duration_ms >= 0
    
    def test_span_add_event(self):
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        span.add_event("event1", {"key": "value"})
        
        assert len(span.events) == 1
        assert span.events[0].name == "event1"
    
    def test_span_set_attribute(self):
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        span.set_attribute("key1", "value1")
        
        assert span.attributes["key1"] == "value1"
    
    def test_span_set_status(self):
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        span.set_status(SpanStatus.OK)
        
        assert span.status == SpanStatus.OK
    
    def test_span_set_error_status(self):
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        span.set_status(SpanStatus.ERROR, "Test error")
        
        assert span.status == SpanStatus.ERROR
        assert span.attributes["status_description"] == "Test error"


class TestTraceContext:
    """Test TraceContext"""
    
    def test_context_initialization(self):
        ctx = TraceContext()
        
        assert ctx.current_trace_id is None
        assert ctx.current_span_id is None
        assert len(ctx.span_stack) == 0
    
    def test_start_trace(self):
        ctx = TraceContext()
        
        ctx.start_trace("trace123")
        
        assert ctx.current_trace_id == "trace123"
    
    def test_push_pop_span(self):
        ctx = TraceContext()
        
        ctx.push_span("span1")
        assert ctx.current_span_id == "span1"
        
        ctx.push_span("span2")
        assert ctx.current_span_id == "span2"
        
        popped = ctx.pop_span()
        assert popped == "span2"
        
        ctx.push_span("span1")
        assert ctx.current_span_id == "span1"
    
    def test_get_parent_span_id(self):
        ctx = TraceContext()
        
        ctx.push_span("span1")
        ctx.push_span("span2")
        
        parent = ctx.get_parent_span_id()
        assert parent == "span1"


class TestTracingProvider:
    """Test TracingProvider"""
    
    def test_provider_initialization(self):
        provider = TracingProvider("test_service")
        
        assert provider.service_name == "test_service"
        assert len(provider.spans) == 0
        assert len(provider.traces) == 0
    
    def test_create_span(self):
        provider = TracingProvider("test_service")
        
        span = provider.create_span(
            "trace123",
            "test_span",
            kind=SpanKind.INTERNAL
        )
        
        assert span.trace_id == "trace123"
        assert span.name == "test_span"
        assert span.span_id in provider.spans
    
    def test_end_span(self):
        provider = TracingProvider("test_service")
        
        span = provider.create_span(
            "trace123",
            "test_span",
            kind=SpanKind.INTERNAL
        )
        
        span.set_status(SpanStatus.OK)
        provider.end_span(span)
        
        assert span.end_time is not None
    
    def test_end_span_error_tracking(self):
        provider = TracingProvider("test_service")
        
        span = provider.create_span(
            "trace123",
            "test_span",
            kind=SpanKind.INTERNAL
        )
        
        span.set_status(SpanStatus.ERROR)
        provider.end_span(span)
        
        metrics = provider.get_metrics()
        assert metrics["errors"] == 1
    
    def test_get_trace(self):
        provider = TracingProvider("test_service")
        
        span1 = provider.create_span("trace123", "span1")
        span2 = provider.create_span("trace123", "span2")
        
        provider.end_span(span1)
        provider.end_span(span2)
        
        trace_spans = provider.get_trace("trace123")
        
        assert len(trace_spans) == 2
    
    def test_add_exporter(self):
        provider = TracingProvider("test_service")
        exporter = MemorySpanExporter()
        
        provider.add_exporter(exporter)
        
        assert len(provider.exporters) == 1


class TestConsoleSpanExporter:
    """Test ConsoleSpanExporter"""
    
    def test_export_span(self):
        exporter = ConsoleSpanExporter()
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        span.end()
        exporter.export(span)


class TestMemorySpanExporter:
    """Test MemorySpanExporter"""
    
    def test_export_span(self):
        exporter = MemorySpanExporter()
        span = Span(
            trace_id="trace123",
            span_id="span123",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.INTERNAL,
            start_time=datetime.utcnow()
        )
        
        span.end()
        exporter.export(span)
        
        spans = exporter.get_spans()
        assert len(spans) == 1
        assert spans[0]["name"] == "test_span"
    
    def test_export_multiple_spans(self):
        exporter = MemorySpanExporter()
        
        for i in range(5):
            span = Span(
                trace_id="trace123",
                span_id=f"span{i}",
                parent_span_id=None,
                name=f"span_{i}",
                kind=SpanKind.INTERNAL,
                start_time=datetime.utcnow()
            )
            span.end()
            exporter.export(span)
        
        spans = exporter.get_spans()
        assert len(spans) == 5


class TestMeterProvider:
    """Test MeterProvider"""
    
    def test_create_counter(self):
        provider = MeterProvider()
        counter = provider.create_counter("test_counter")
        
        assert counter is not None
        assert "test_counter" in provider.metrics
    
    def test_create_histogram(self):
        provider = MeterProvider()
        histogram = provider.create_histogram("test_histogram")
        
        assert histogram is not None
        assert "test_histogram" in provider.metrics
    
    def test_create_gauge(self):
        provider = MeterProvider()
        gauge = provider.create_gauge("test_gauge")
        
        assert gauge is not None
        assert "test_gauge" in provider.metrics
    
    def test_get_metrics(self):
        provider = MeterProvider()
        provider.create_counter("counter1")
        provider.create_histogram("histogram1")
        
        metrics = provider.get_metrics()
        
        assert "counter1" in metrics
        assert "histogram1" in metrics


class TestCounter:
    """Test Counter metric"""
    
    def test_counter_add(self):
        provider = MeterProvider()
        counter = provider.create_counter("test_counter")
        
        counter.add(1)
        counter.add(1)
        counter.add(5)
        
        assert provider.metrics["test_counter"]["value"] == 7


class TestHistogram:
    """Test Histogram metric"""
    
    def test_histogram_record(self):
        provider = MeterProvider()
        histogram = provider.create_histogram("test_histogram")
        
        histogram.record(10)
        histogram.record(20)
        histogram.record(30)
        
        stats = histogram.get_stats()
        
        assert stats["count"] == 3
        assert stats["sum"] == 60
        assert stats["min"] == 10
        assert stats["max"] == 30
        assert stats["avg"] == 20


class TestGauge:
    """Test Gauge metric"""
    
    def test_gauge_set(self):
        provider = MeterProvider()
        gauge = provider.create_gauge("test_gauge")
        
        gauge.set(42)
        
        assert provider.metrics["test_gauge"]["value"] == 42


class TestInstrumentationHelper:
    """Test InstrumentationHelper"""
    
    def test_trace_function_decorator_sync(self):
        provider = TracingProvider("test_service")
        helper = InstrumentationHelper(provider)
        
        @helper.trace_function("test_func")
        def test_func():
            return "result"
        
        result = test_func()
        
        assert result == "result"
        assert len(provider.spans) == 1
    
    @pytest.mark.asyncio
    async def test_trace_function_decorator_async(self):
        provider = TracingProvider("test_service")
        helper = InstrumentationHelper(provider)
        
        @helper.trace_function("async_func")
        async def async_func():
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await async_func()
        
        assert result == "async_result"
        assert len(provider.spans) == 1
    
    def test_trace_function_error_handling(self):
        provider = TracingProvider("test_service")
        helper = InstrumentationHelper(provider)
        
        @helper.trace_function("failing_func")
        def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_func()
        
        assert len(provider.spans) == 1
        span = list(provider.spans.values())[0]
        assert span.status == SpanStatus.ERROR
    
    def test_trace_context_manager(self):
        provider = TracingProvider("test_service")
        helper = InstrumentationHelper(provider)
        
        with helper.trace_context("trace123", "context_span"):
            pass
        
        assert len(provider.spans) == 1


class TestObservabilityCollector:
    """Test ObservabilityCollector"""
    
    def test_collector_initialization(self):
        collector = ObservabilityCollector("test_service")
        
        assert collector.service_name == "test_service"
        assert collector.tracer is not None
        assert collector.meter is not None
    
    def test_full_observability_data(self):
        collector = ObservabilityCollector("test_service")
        
        span = collector.tracer.create_span(
            "trace123",
            "test_span",
            kind=SpanKind.INTERNAL
        )
        span.end()
        
        data = collector.get_full_observability_data()
        
        assert data["service"] == "test_service"
        assert "tracing" in data
        assert "metrics" in data
        assert "spans" in data


class TestGlobalCollector:
    """Test global observability collector"""
    
    def test_initialize_observability(self):
        collector = initialize_observability("test_service")
        
        assert collector is not None
        assert collector.service_name == "test_service"
    
    def test_get_observability_collector(self):
        initialize_observability("test_service")
        collector = get_observability_collector()
        
        assert collector is not None
        assert collector.service_name == "test_service"


class TestObservabilityIntegration:
    """Integration tests for observability"""
    
    @pytest.mark.asyncio
    async def test_complete_tracing_workflow(self):
        collector = ObservabilityCollector("test_service")
        helper = collector.instrumentation
        
        @helper.trace_function("outer_operation")
        async def outer_operation():
            await asyncio.sleep(0.01)
            
            @helper.trace_function("inner_operation")
            async def inner_operation():
                await asyncio.sleep(0.01)
                return "result"
            
            return await inner_operation()
        
        result = await outer_operation()
        
        assert result == "result"
        assert len(collector.tracer.spans) >= 2
    
    def test_metrics_and_tracing_together(self):
        collector = ObservabilityCollector("test_service")
        
        counter = collector.meter.create_counter("requests")
        histogram = collector.meter.create_histogram("latency_ms")
        
        for i in range(10):
            counter.add(1)
            histogram.record(50 + i * 5)
        
        span = collector.tracer.create_span(
            "trace123",
            "test_span"
        )
        span.set_attribute("request_count", 10)
        collector.tracer.end_span(span)
        
        data = collector.get_full_observability_data()
        
        assert data["metrics"]["requests"]["value"] == 10
        assert len(data["spans"]) >= 1
