import pytest
import uuid
from datetime import datetime, timedelta
from src.monitoring.tracing_optimizer import (
    SamplingStrategy,
    Span,
    Trace,
    SamplingCalculator,
    LatencyAnalyzer,
    RootCauseAnalyzer,
    TracingOptimizer,
    get_tracing_optimizer
)


class TestSpan:
    def test_span_creation(self):
        span = Span(
            trace_id="trace_1",
            span_id="span_1",
            parent_span_id=None,
            operation_name="http_request",
            service_name="api",
            start_time=datetime.utcnow()
        )
        assert span.trace_id == "trace_1"
        assert span.operation_name == "http_request"
    
    def test_span_duration(self):
        start = datetime.utcnow()
        span = Span(
            trace_id="trace_1",
            span_id="span_1",
            parent_span_id=None,
            operation_name="op",
            service_name="svc",
            start_time=start,
            end_time=start + timedelta(milliseconds=100)
        )
        assert 95 < span.duration_ms < 105


class TestTrace:
    def test_trace_creation(self):
        trace = Trace(trace_id="trace_1")
        assert trace.trace_id == "trace_1"
        assert trace.span_count == 0
    
    def test_trace_metrics(self):
        trace = Trace(trace_id="trace_1")
        start = datetime.utcnow()
        
        span1 = Span(
            trace_id="trace_1",
            span_id="span_1",
            parent_span_id=None,
            operation_name="op1",
            service_name="svc1",
            start_time=start,
            end_time=start + timedelta(milliseconds=50)
        )
        
        span2 = Span(
            trace_id="trace_1",
            span_id="span_2",
            parent_span_id="span_1",
            operation_name="op2",
            service_name="svc2",
            start_time=start + timedelta(milliseconds=10),
            end_time=start + timedelta(milliseconds=60)
        )
        
        trace.spans = [span1, span2]
        assert trace.span_count == 2
        assert trace.service_count == 2


class TestSamplingCalculator:
    def test_all_sampling(self):
        calc = SamplingCalculator()
        assert calc.should_sample("trace_1", "svc", 100, False, SamplingStrategy.ALL) is True
    
    def test_none_sampling(self):
        calc = SamplingCalculator()
        assert calc.should_sample("trace_1", "svc", 100, False, SamplingStrategy.NONE) is False
    
    def test_error_based_sampling(self):
        calc = SamplingCalculator()
        assert calc.should_sample("trace_1", "svc", 100, True, SamplingStrategy.ERROR_BASED) is True
        assert calc.should_sample("trace_1", "svc", 100, False, SamplingStrategy.ERROR_BASED) is False


class TestLatencyAnalyzer:
    def test_record_span_latency(self):
        analyzer = LatencyAnalyzer()
        analyzer.record_span_latency("http_request", "api", 100.0)
        analyzer.record_span_latency("http_request", "api", 150.0)
        
        stats = analyzer.get_operation_stats("http_request")
        assert stats["count"] == 2
        assert stats["min"] == 100.0
    
    def test_get_operation_stats(self):
        analyzer = LatencyAnalyzer()
        for i in range(100):
            analyzer.record_span_latency("op", "svc", 100.0 + i)
        
        stats = analyzer.get_operation_stats("op")
        assert "p50" in stats
        assert "p95" in stats
        assert "p99" in stats
        assert 100 <= stats["p50"] <= 200


class TestRootCauseAnalyzer:
    def test_analyze_error_trace(self):
        rca = RootCauseAnalyzer()
        trace = Trace(trace_id="trace_1")
        
        start = datetime.utcnow()
        error_span = Span(
            trace_id="trace_1",
            span_id="span_1",
            parent_span_id=None,
            operation_name="db_query",
            service_name="database",
            start_time=start,
            end_time=start + timedelta(milliseconds=100),
            status="error",
            error_message="Connection timeout"
        )
        
        trace.spans = [error_span]
        
        analysis = rca.analyze_error_trace(trace)
        assert "root_cause_service" in analysis
        assert analysis["root_cause_service"] == "database"
    
    def test_find_slow_spans(self):
        rca = RootCauseAnalyzer()
        trace = Trace(trace_id="trace_1")
        
        start = datetime.utcnow()
        spans = []
        for i in range(10):
            span = Span(
                trace_id="trace_1",
                span_id=f"span_{i}",
                parent_span_id=None,
                operation_name="op",
                service_name="svc",
                start_time=start,
                end_time=start + timedelta(milliseconds=100 + i * 10)
            )
            spans.append(span)
        
        trace.spans = spans
        slow = rca.find_slow_spans(trace, percentile=50)
        assert len(slow) > 0


class TestTracingOptimizer:
    def test_create_span(self):
        optimizer = TracingOptimizer()
        span = optimizer.create_span("trace_1", "span_1", "http_request", "api")
        assert span.operation_name == "http_request"
    
    def test_end_span(self):
        optimizer = TracingOptimizer()
        span = optimizer.create_span("trace_1", "span_1", "op", "svc")
        optimizer.end_span(span, "ok")
        
        assert span.end_time is not None
        assert span.status == "ok"
    
    def test_should_sample_trace(self):
        optimizer = TracingOptimizer()
        result = optimizer.should_sample_trace("trace_1", 100.0, False, "svc")
        assert isinstance(result, bool)
    
    def test_analyze_trace(self):
        optimizer = TracingOptimizer()
        
        span = optimizer.create_span("trace_1", "span_1", "op", "svc")
        optimizer.end_span(span)
        
        analysis = optimizer.analyze_trace("trace_1")
        assert "trace_id" in analysis
        assert "span_count" in analysis
    
    def test_get_performance_report(self):
        optimizer = TracingOptimizer()
        
        for i in range(5):
            span = optimizer.create_span(f"trace_{i}", f"span_{i}", "op", "svc")
            optimizer.end_span(span)
        
        report = optimizer.get_performance_report()
        assert "total_traces" in report
        assert "services" in report


class TestSingleton:
    def test_get_singleton(self):
        opt1 = get_tracing_optimizer()
        opt2 = get_tracing_optimizer()
        assert opt1 is opt2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
