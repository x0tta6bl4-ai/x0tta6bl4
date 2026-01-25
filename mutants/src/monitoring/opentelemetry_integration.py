"""
OpenTelemetry Distributed Tracing Integration

Provides comprehensive distributed tracing, metrics collection, and observability
for the entire system including traces, spans, metrics, and logs correlation.
"""

import logging
import time
import asyncio
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from functools import wraps
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class SpanKind(Enum):
    """Types of spans"""
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class SpanStatus(Enum):
    """Status of a span"""
    UNSET = "UNSET"
    OK = "OK"
    ERROR = "ERROR"


@dataclass
class SpanAttribute:
    """Span attribute"""
    key: str
    value: Any


@dataclass
class SpanEvent:
    """Event within a span"""
    name: str
    timestamp: datetime
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """Represents a distributed trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: datetime
    end_time: Optional[datetime] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    duration_ms: float = 0.0
    
    def end(self):
        """End the span"""
        self.end_time = datetime.utcnow()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
    
    def add_event(self, name: str, attributes: Dict[str, Any] = None):
        """Add event to span"""
        event = SpanEvent(
            name=name,
            timestamp=datetime.utcnow(),
            attributes=attributes or {}
        )
        self.events.append(event)
    
    def set_attribute(self, key: str, value: Any):
        """Set span attribute"""
        self.attributes[key] = value
    
    def set_status(self, status: SpanStatus, description: str = ""):
        """Set span status"""
        self.status = status
        if description:
            self.attributes["status_description"] = description


class TraceContext:
    """Manages trace context"""
    
    def __init__(self):
        self.current_trace_id: Optional[str] = None
        self.current_span_id: Optional[str] = None
        self.span_stack: List[str] = []
    
    def start_trace(self, trace_id: str) -> None:
        """Start a new trace"""
        self.current_trace_id = trace_id
    
    def push_span(self, span_id: str) -> None:
        """Push span onto stack"""
        self.span_stack.append(span_id)
        self.current_span_id = span_id
    
    def pop_span(self) -> Optional[str]:
        """Pop span from stack"""
        if self.span_stack:
            return self.span_stack.pop()
        return None
    
    def get_parent_span_id(self) -> Optional[str]:
        """Get parent span ID"""
        if len(self.span_stack) > 1:
            return self.span_stack[-2]
        return None


class TracingProvider:
    """Central tracing provider"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.spans: Dict[str, Span] = {}
        self.traces: Dict[str, List[str]] = {}
        self.context = TraceContext()
        self.exporters: List[Any] = []
        self.metrics: Dict[str, Any] = {
            "total_spans": 0,
            "total_traces": 0,
            "errors": 0
        }
    
    def create_span(
        self,
        trace_id: str,
        span_name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Dict[str, Any] = None
    ) -> Span:
        """Create a new span"""
        import uuid
        span_id = str(uuid.uuid4())
        parent_span_id = self.context.current_span_id
        
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            name=span_name,
            kind=kind,
            start_time=datetime.utcnow(),
            attributes=attributes or {}
        )
        
        self.spans[span_id] = span
        self.context.push_span(span_id)
        
        if trace_id not in self.traces:
            self.traces[trace_id] = []
        self.traces[trace_id].append(span_id)
        
        self.metrics["total_spans"] += 1
        
        return span
    
    def end_span(self, span: Span):
        """End a span"""
        span.end()
        self.context.pop_span()
        
        if span.status == SpanStatus.ERROR:
            self.metrics["errors"] += 1
        
        self._export_span(span)
    
    def _export_span(self, span: Span):
        """Export span to all registered exporters"""
        for exporter in self.exporters:
            try:
                exporter.export(span)
            except Exception as e:
                logger.error(f"Failed to export span: {e}")
    
    def add_exporter(self, exporter):
        """Add span exporter"""
        self.exporters.append(exporter)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get tracing metrics"""
        return {
            **self.metrics,
            "total_traces": len(self.traces)
        }
    
    def get_trace(self, trace_id: str) -> Optional[List[Span]]:
        """Get all spans for a trace"""
        span_ids = self.traces.get(trace_id, [])
        return [self.spans[sid] for sid in span_ids if sid in self.spans]


class SpanExporter:
    """Base class for span exporters"""
    
    def export(self, span: Span):
        """Export span"""
        raise NotImplementedError


class ConsoleSpanExporter(SpanExporter):
    """Exports spans to console"""
    
    def export(self, span: Span):
        """Export span to console"""
        status_str = f"[{span.status.value}]" if span.status != SpanStatus.UNSET else ""
        logger.info(
            f"{status_str} Trace: {span.trace_id} | "
            f"Span: {span.name} | "
            f"Duration: {span.duration_ms:.2f}ms"
        )


class MemorySpanExporter(SpanExporter):
    """Stores spans in memory"""
    
    def __init__(self, max_size: int = 10000):
        self.spans: List[Dict[str, Any]] = []
        self.max_size = max_size
    
    def export(self, span: Span):
        """Export span to memory"""
        span_data = {
            "trace_id": span.trace_id,
            "span_id": span.span_id,
            "name": span.name,
            "kind": span.kind.value,
            "duration_ms": span.duration_ms,
            "status": span.status.value,
            "attributes": span.attributes,
            "event_count": len(span.events)
        }
        
        self.spans.append(span_data)
        
        if len(self.spans) > self.max_size:
            self.spans = self.spans[-self.max_size:]
    
    def get_spans(self) -> List[Dict[str, Any]]:
        """Get exported spans"""
        return self.spans


class MeterProvider:
    """Provides metrics collection"""
    
    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}
    
    def create_counter(self, name: str, description: str = ""):
        """Create a counter metric"""
        self.metrics[name] = {
            "type": "counter",
            "value": 0,
            "description": description
        }
        return Counter(self, name)
    
    def create_histogram(self, name: str, description: str = ""):
        """Create a histogram metric"""
        self.metrics[name] = {
            "type": "histogram",
            "values": [],
            "description": description
        }
        return Histogram(self, name)
    
    def create_gauge(self, name: str, description: str = ""):
        """Create a gauge metric"""
        self.metrics[name] = {
            "type": "gauge",
            "value": 0,
            "description": description
        }
        return Gauge(self, name)
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metrics"""
        return self.metrics


class Counter:
    """Counter metric"""
    
    def __init__(self, provider: MeterProvider, name: str):
        self.provider = provider
        self.name = name
    
    def add(self, value: float = 1):
        """Increment counter"""
        if self.name in self.provider.metrics:
            self.provider.metrics[self.name]["value"] += value


class Histogram:
    """Histogram metric"""
    
    def __init__(self, provider: MeterProvider, name: str):
        self.provider = provider
        self.name = name
    
    def record(self, value: float):
        """Record value"""
        if self.name in self.provider.metrics:
            self.provider.metrics[self.name]["values"].append(value)
    
    def get_stats(self) -> Dict[str, float]:
        """Get histogram statistics"""
        if self.name not in self.provider.metrics:
            return {}
        
        values = self.provider.metrics[self.name]["values"]
        if not values:
            return {}
        
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values)
        }


class Gauge:
    """Gauge metric"""
    
    def __init__(self, provider: MeterProvider, name: str):
        self.provider = provider
        self.name = name
    
    def set(self, value: float):
        """Set gauge value"""
        if self.name in self.provider.metrics:
            self.provider.metrics[self.name]["value"] = value


class InstrumentationHelper:
    """Helper for instrumenting functions"""
    
    def __init__(self, provider: TracingProvider):
        self.provider = provider
    
    def trace_function(self, span_name: str = None):
        """Decorator to trace function execution"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                import uuid
                trace_id = str(uuid.uuid4())
                name = span_name or func.__name__
                
                span = self.provider.create_span(
                    trace_id,
                    name,
                    kind=SpanKind.INTERNAL
                )
                
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(SpanStatus.OK)
                    return result
                except Exception as e:
                    span.set_status(SpanStatus.ERROR, str(e))
                    raise
                finally:
                    self.provider.end_span(span)
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                import uuid
                trace_id = str(uuid.uuid4())
                name = span_name or func.__name__
                
                span = self.provider.create_span(
                    trace_id,
                    name,
                    kind=SpanKind.INTERNAL
                )
                
                try:
                    result = func(*args, **kwargs)
                    span.set_status(SpanStatus.OK)
                    return result
                except Exception as e:
                    span.set_status(SpanStatus.ERROR, str(e))
                    raise
                finally:
                    self.provider.end_span(span)
            
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            else:
                return sync_wrapper
        
        return decorator
    
    @contextmanager
    def trace_context(self, trace_id: str, span_name: str):
        """Context manager for tracing"""
        span = self.provider.create_span(
            trace_id,
            span_name,
            kind=SpanKind.INTERNAL
        )
        
        try:
            yield span
            span.set_status(SpanStatus.OK)
        except Exception as e:
            span.set_status(SpanStatus.ERROR, str(e))
            raise
        finally:
            self.provider.end_span(span)


class ObservabilityCollector:
    """Collects comprehensive observability data"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.tracer = TracingProvider(service_name)
        self.meter = MeterProvider()
        self.instrumentation = InstrumentationHelper(self.tracer)
        
        self.tracer.add_exporter(ConsoleSpanExporter())
        self.memory_exporter = MemorySpanExporter()
        self.tracer.add_exporter(self.memory_exporter)
    
    def get_full_observability_data(self) -> Dict[str, Any]:
        """Get complete observability snapshot"""
        return {
            "service": self.service_name,
            "tracing": {
                "metrics": self.tracer.get_metrics(),
                "span_count": len(self.tracer.spans),
                "trace_count": len(self.tracer.traces)
            },
            "metrics": self.meter.get_metrics(),
            "spans": self.memory_exporter.get_spans()[:100]
        }


_global_collector: Optional[ObservabilityCollector] = None


def initialize_observability(service_name: str) -> ObservabilityCollector:
    """Initialize global observability"""
    global _global_collector
    _global_collector = ObservabilityCollector(service_name)
    return _global_collector


def get_observability_collector() -> Optional[ObservabilityCollector]:
    """Get global observability collector"""
    return _global_collector
