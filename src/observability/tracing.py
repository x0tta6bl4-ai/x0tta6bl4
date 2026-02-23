"""
OpenTelemetry Tracing Configuration and Utilities

Provides distributed tracing with automatic span creation and context propagation.
"""

import functools
import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union
import uuid

logger = logging.getLogger(__name__)

# Type variables for generics
F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")


class SpanKind(str, Enum):
    """Kind of span."""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatusCode(str, Enum):
    """Status code for spans."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanContext:
    """Context for a span."""
    trace_id: str
    span_id: str
    trace_flags: int = 0
    trace_state: Dict[str, str] = field(default_factory=dict)
    is_remote: bool = False
    
    def to_w3c_traceparent(self) -> str:
        """Generate W3C traceparent header."""
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags:02x}"


@dataclass
class Span:
    """Represents a tracing span."""
    name: str
    context: SpanContext
    kind: SpanKind = SpanKind.INTERNAL
    parent: Optional["Span"] = None
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    status_code: SpanStatusCode = SpanStatusCode.UNSET
    status_description: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_attribute(self, key: str, value: Any) -> "Span":
        """Set an attribute on the span."""
        self.attributes[key] = value
        return self
    
    def set_attributes(self, attributes: Dict[str, Any]) -> "Span":
        """Set multiple attributes on the span."""
        self.attributes.update(attributes)
        return self
    
    def add_event(
        self,
        name: str,
        attributes: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None
    ) -> "Span":
        """Add an event to the span."""
        self.events.append({
            "name": name,
            "timestamp": (timestamp or datetime.utcnow()).isoformat(),
            "attributes": attributes or {},
        })
        return self
    
    def set_status(
        self,
        status_code: SpanStatusCode,
        description: Optional[str] = None
    ) -> "Span":
        """Set the status of the span."""
        self.status_code = status_code
        self.status_description = description
        return self
    
    def record_exception(
        self,
        exception: Exception,
        attributes: Optional[Dict[str, Any]] = None
    ) -> "Span":
        """Record an exception on the span."""
        self.add_event(
            "exception",
            attributes={
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
                "exception.stacktrace": getattr(exception, "__traceback__", None),
                **(attributes or {}),
            }
        )
        self.set_status(SpanStatusCode.ERROR, str(exception))
        return self
    
    def end(self, end_time: Optional[datetime] = None) -> None:
        """End the span."""
        self.end_time = end_time or datetime.utcnow()
    
    def duration_ms(self) -> Optional[float]:
        """Get span duration in milliseconds."""
        if self.end_time is None:
            return None
        delta = self.end_time - self.start_time
        return delta.total_seconds() * 1000
    
    def is_recording(self) -> bool:
        """Check if span is still recording."""
        return self.end_time is None


@dataclass
class TracingConfig:
    """Configuration for tracing."""
    service_name: str = "maas-x0tta6bl4"
    service_version: str = "1.0.0"
    environment: str = "development"
    
    # Sampling configuration
    sample_rate: float = 1.0  # 1.0 = 100% sampling
    
    # Exporter configuration
    exporter_type: str = "otlp"  # otlp, jaeger, console, multi
    otlp_endpoint: str = "http://localhost:4317"
    jaeger_agent_host: str = "localhost"
    jaeger_agent_port: int = 6831
    
    # Resource attributes
    resource_attributes: Dict[str, str] = field(default_factory=dict)
    
    # Propagation format
    propagation_format: str = "w3c"  # w3c, b3, jaeger
    
    # Batch processing
    batch_export: bool = True
    batch_size: int = 512
    export_timeout_ms: int = 30000
    schedule_delay_ms: int = 5000
    
    @classmethod
    def from_env(cls) -> "TracingConfig":
        """Create configuration from environment variables."""
        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "maas-x0tta6bl4"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "1.0.0"),
            environment=os.getenv("ENVIRONMENT", "development"),
            sample_rate=float(os.getenv("OTEL_SAMPLE_RATE", "1.0")),
            exporter_type=os.getenv("OTEL_EXPORTER_TYPE", "otlp"),
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
            jaeger_agent_host=os.getenv("OTEL_EXPORTER_JAEGER_HOST", "localhost"),
            jaeger_agent_port=int(os.getenv("OTEL_EXPORTER_JAEGER_PORT", "6831")),
            propagation_format=os.getenv("OTEL_PROPAGATION_FORMAT", "w3c"),
        )


class TracerProvider:
    """
    Provider for tracers.
    
    Manages span creation, context propagation, and export.
    """
    
    _instance: Optional["TracerProvider"] = None
    
    def __init__(self, config: Optional[TracingConfig] = None):
        self.config = config or TracingConfig.from_env()
        self._spans: List[Span] = []
        self._current_span: Optional[Span] = None
        self._exporter: Optional[Any] = None
        self._initialized = False
    
    @classmethod
    def get_instance(cls) -> "TracerProvider":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def initialize(self) -> None:
        """Initialize the tracer provider."""
        if self._initialized:
            return
        
        # Initialize exporter based on config
        from .exporters import get_exporter
        self._exporter = get_exporter(self.config)
        
        self._initialized = True
        logger.info(
            f"TracerProvider initialized: service={self.config.service_name}, "
            f"exporter={self.config.exporter_type}"
        )
    
    def get_tracer(
        self,
        name: Optional[str] = None,
        version: Optional[str] = None
    ) -> "Tracer":
        """Get a tracer instance."""
        if not self._initialized:
            self.initialize()
        
        return Tracer(
            name=name or self.config.service_name,
            version=version or self.config.service_version,
            provider=self,
        )
    
    def create_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Optional[Span] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Create a new span."""
        # Generate trace and span IDs
        trace_id = parent.context.trace_id if parent else self._generate_trace_id()
        span_id = self._generate_span_id()
        
        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
        )
        
        span = Span(
            name=name,
            context=context,
            kind=kind,
            parent=parent,
            attributes={
                "service.name": self.config.service_name,
                "service.version": self.config.service_version,
                "environment": self.config.environment,
                **(attributes or {}),
            },
        )
        
        self._spans.append(span)
        return span
    
    def _generate_trace_id(self) -> str:
        """Generate a trace ID."""
        return uuid.uuid4().hex.zfill(32)
    
    def _generate_span_id(self) -> str:
        """Generate a span ID."""
        return uuid.uuid4().hex[:16].zfill(16)
    
    def export_span(self, span: Span) -> None:
        """Export a completed span."""
        if self._exporter and span.end_time:
            try:
                self._exporter.export([span])
            except Exception as e:
                logger.error(f"Failed to export span: {e}")
    
    def shutdown(self) -> None:
        """Shutdown the provider and flush remaining spans."""
        if self._exporter:
            try:
                self._exporter.shutdown()
            except Exception as e:
                logger.error(f"Failed to shutdown exporter: {e}")
        
        self._initialized = False
        logger.info("TracerProvider shutdown complete")


class Tracer:
    """
    Tracer for creating spans.
    """
    
    def __init__(
        self,
        name: str,
        version: str,
        provider: TracerProvider
    ):
        self.name = name
        self.version = version
        self.provider = provider
    
    def start_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent: Optional[Span] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Span:
        """Start a new span."""
        return self.provider.create_span(
            name=name,
            kind=kind,
            parent=parent,
            attributes=attributes,
        )
    
    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
    ):
        """Start a span and set it as current."""
        span = self.start_span(name, kind, attributes=attributes)
        
        # Set as current span
        old_span = self.provider._current_span
        self.provider._current_span = span
        
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            raise
        finally:
            span.end()
            self.provider.export_span(span)
            self.provider._current_span = old_span


# Global tracer provider
_provider: Optional[TracerProvider] = None


def get_tracer(name: Optional[str] = None) -> Tracer:
    """Get a tracer instance."""
    global _provider
    if _provider is None:
        _provider = TracerProvider.get_instance()
        _provider.initialize()
    return _provider.get_tracer(name)


def start_span(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
) -> Span:
    """Start a new span using the global tracer."""
    tracer = get_tracer()
    return tracer.start_span(name, kind, attributes=attributes)


@contextmanager
def traced_context(
    name: str,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
):
    """Context manager for tracing a block of code."""
    tracer = get_tracer()
    with tracer.start_as_current_span(name, kind, attributes) as span:
        yield span


def trace_method(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace a method.
    
    Usage:
        @trace_method("process_request")
        async def handle_request(request):
            ...
    """
    def decorator(func: F) -> F:
        span_name = name or f"{func.__module__}.{func.__name__}"
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            with traced_context(span_name, kind, attributes) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(SpanStatusCode.OK)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with traced_context(span_name, kind, attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(SpanStatusCode.OK)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def get_current_span() -> Optional[Span]:
    """Get the current active span."""
    global _provider
    if _provider is None:
        return None
    return _provider._current_span


def inject_trace_context(headers: Dict[str, str]) -> Dict[str, str]:
    """Inject trace context into headers for propagation."""
    span = get_current_span()
    if span:
        headers["traceparent"] = span.context.to_w3c_traceparent()
        headers["tracestate"] = ",".join(
            f"{k}={v}" for k, v in span.context.trace_state.items()
        )
    return headers


def extract_trace_context(headers: Dict[str, str]) -> Optional[SpanContext]:
    """Extract trace context from headers."""
    traceparent = headers.get("traceparent")
    if not traceparent:
        return None
    
    try:
        parts = traceparent.split("-")
        if len(parts) >= 3:
            return SpanContext(
                trace_id=parts[1],
                span_id=parts[2],
                trace_flags=int(parts[3], 16) if len(parts) > 3 else 0,
            )
    except Exception as e:
        logger.warning(f"Failed to parse traceparent: {e}")
    
    return None
