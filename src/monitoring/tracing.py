"""
OpenTelemetry Tracing Implementation - Production Ready

Full OpenTelemetry tracing for x0tta6bl4:
- Distributed tracing with context propagation
- MAPE-K cycle spans
- Network adaptation spans
- RAG retrieval spans
- Custom spans for all components
- Trace sampling configuration
- Integration with Jaeger/Zipkin/OTLP
- FastAPI middleware integration
"""
import logging
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager
from functools import wraps
import os

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.context import Context, attach, detach, set_value
    from opentelemetry.propagate import extract, inject, set_global_textmap
    from opentelemetry.propagators.composite import CompositeHTTPPropagator
    from opentelemetry.propagators.b3 import B3MultiFormat
    from opentelemetry.propagators.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.sampling import (
        TraceIdRatioBased, 
        ALWAYS_ON, 
        ALWAYS_OFF,
        ParentBased
    )
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.exporter.zipkin.json import ZipkinExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    trace = None  # type: ignore
    Status = None  # type: ignore
    StatusCode = None  # type: ignore
    Context = None  # type: ignore
    extract = None  # type: ignore
    inject = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    ConsoleSpanExporter = None  # type: ignore
    JaegerExporter = None  # type: ignore
    ZipkinExporter = None  # type: ignore
    OTLPSpanExporter = None  # type: ignore
    TraceIdRatioBased = None  # type: ignore
    ALWAYS_ON = None  # type: ignore
    ALWAYS_OFF = None  # type: ignore
    Resource = None  # type: ignore
    FastAPIInstrumentor = None  # type: ignore
    HTTPXClientInstrumentor = None  # type: ignore


class TracingManager:
    """
    OpenTelemetry Tracing Manager.
    
    Provides distributed tracing for x0tta6bl4 components.
    """
    
    def __init__(
        self,
        service_name: str = "x0tta6bl4",
        service_version: str = "3.1",
        jaeger_endpoint: Optional[str] = None,
        zipkin_endpoint: Optional[str] = None,
        otlp_endpoint: Optional[str] = None,
        enable_console: bool = False,
        trace_sampling_ratio: float = 1.0,
        enable_fastapi_instrumentation: bool = True
    ):
        """
        Initialize tracing manager with full distributed tracing support.
        
        Args:
            service_name: Service name for traces
            service_version: Service version
            jaeger_endpoint: Jaeger collector endpoint (e.g., "http://localhost:14268/api/traces")
            zipkin_endpoint: Zipkin collector endpoint (e.g., "http://localhost:9411/api/v2/spans")
            otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
            enable_console: Enable console exporter for debugging
            trace_sampling_ratio: Sampling ratio (0.0-1.0, default: 1.0 = 100%)
            enable_fastapi_instrumentation: Enable automatic FastAPI instrumentation
        """
        self.service_name = service_name
        self.service_version = service_version
        self.tracer: Optional[Any] = None
        self.sampling_ratio = trace_sampling_ratio
        
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("⚠️ OpenTelemetry not available. Install: pip install opentelemetry-api opentelemetry-sdk")
            return
        
        try:
            # Create resource with service metadata
            resource = Resource.create({
                SERVICE_NAME: service_name,
                SERVICE_VERSION: service_version,
                "deployment.environment": os.getenv("ENVIRONMENT", "production"),
                "service.namespace": "x0tta6bl4-mesh"
            })
            
            # Configure advanced sampling with ParentBased support
            # ParentBased sampler respects parent trace decisions for distributed tracing
            if trace_sampling_ratio >= 1.0:
                base_sampler = ALWAYS_ON
            elif trace_sampling_ratio <= 0.0:
                base_sampler = ALWAYS_OFF
            else:
                base_sampler = TraceIdRatioBased(trace_sampling_ratio)
            
            # Use ParentBased sampler for production (respects parent trace decisions)
            # This ensures consistent sampling across distributed services
            sampler = ParentBased(root=base_sampler)
            
            # Create tracer provider with sampling
            provider = TracerProvider(resource=resource, sampler=sampler)
            
            # Add exporters
            exporters_configured = False
            
            if otlp_endpoint:
                try:
                    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                    # Configure BatchSpanProcessor with optimized settings for production
                    batch_processor = BatchSpanProcessor(
                        otlp_exporter,
                        max_queue_size=2048,  # Larger queue for high throughput
                        export_timeout_millis=30000,  # 30s timeout
                        schedule_delay_millis=5000  # 5s batch interval
                    )
                    provider.add_span_processor(batch_processor)
                    logger.info(f"✅ OTLP exporter configured: {otlp_endpoint} (optimized batch settings)")
                    exporters_configured = True
                except Exception as e:
                    logger.warning(f"⚠️ Failed to configure OTLP exporter: {e}")
            
            if jaeger_endpoint:
                try:
                    jaeger_exporter = JaegerExporter(
                        agent_host_name=jaeger_endpoint.split("://")[1].split(":")[0] if "://" in jaeger_endpoint else "localhost",
                        agent_port=14268,
                        collector_endpoint=jaeger_endpoint
                    )
                    # Optimized batch processor for Jaeger
                    batch_processor = BatchSpanProcessor(
                        jaeger_exporter,
                        max_queue_size=2048,
                        export_timeout_millis=30000,
                        schedule_delay_millis=5000
                    )
                    provider.add_span_processor(batch_processor)
                    logger.info(f"✅ Jaeger exporter configured: {jaeger_endpoint} (optimized batch settings)")
                    exporters_configured = True
                except Exception as e:
                    logger.warning(f"⚠️ Failed to configure Jaeger exporter: {e}")
            
            if zipkin_endpoint:
                try:
                    zipkin_exporter = ZipkinExporter(endpoint=zipkin_endpoint)
                    # Optimized batch processor for Zipkin
                    batch_processor = BatchSpanProcessor(
                        zipkin_exporter,
                        max_queue_size=2048,
                        export_timeout_millis=30000,
                        schedule_delay_millis=5000
                    )
                    provider.add_span_processor(batch_processor)
                    logger.info(f"✅ Zipkin exporter configured: {zipkin_endpoint} (optimized batch settings)")
                    exporters_configured = True
                except Exception as e:
                    logger.warning(f"⚠️ Failed to configure Zipkin exporter: {e}")
            
            if enable_console or not exporters_configured:
                console_exporter = ConsoleSpanExporter()
                provider.add_span_processor(BatchSpanProcessor(console_exporter))
                logger.info("✅ Console exporter enabled")
            
            # Set global tracer provider
            trace.set_tracer_provider(provider)
            
            # Configure context propagation (W3C TraceContext + B3)
            propagator = CompositeHTTPPropagator([
                TraceContextTextMapPropagator(),
                B3MultiFormat()
            ])
            set_global_textmap(propagator)
            logger.info("✅ Context propagation configured (W3C TraceContext + B3)")
            
            # Get tracer
            self.tracer = trace.get_tracer(service_name, service_version)
            
            # Enable FastAPI instrumentation if requested
            if enable_fastapi_instrumentation and FastAPIInstrumentor:
                try:
                    FastAPIInstrumentor.instrument()
                    HTTPXClientInstrumentor().instrument()
                    logger.info("✅ FastAPI and HTTPX instrumentation enabled")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to enable FastAPI instrumentation: {e}")
            
            logger.info(f"✅ OpenTelemetry tracing initialized for {service_name} v{service_version} (sampling: {trace_sampling_ratio*100}%)")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize OpenTelemetry tracing: {e}")
            self.tracer = None
    
    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Create a tracing span.
        
        Args:
            name: Span name
            attributes: Span attributes
        
        Example:
            with tracing_manager.span("mape_k_cycle"):
                # Your code here
        """
        if not self.tracer:
            yield
            return
        
        try:
            with self.tracer.start_as_current_span(name) as span:
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, str(value))
                yield span
        except Exception as e:
            logger.warning(f"Tracing span error: {e}")
            yield
    
    def trace_mape_k_cycle(self, phase: str, metrics: Optional[Dict[str, Any]] = None, parent_span: Optional[Any] = None):
        """
        Trace MAPE-K cycle phase with full context.
        
        Args:
            phase: Phase name (monitor, analyze, plan, execute, knowledge)
            metrics: Optional metrics to add as attributes
            parent_span: Parent span for distributed tracing
        
        Returns:
            Context manager for the span
        """
        if not self.tracer:
            @contextmanager
            def noop():
                yield None
            return noop()
        
        @contextmanager
        def span_context():
            try:
                span_name = f"mape_k.{phase}"
                with self.tracer.start_as_current_span(span_name) as span:
                    span.set_attribute("mape_k.phase", phase)
                    span.set_attribute("mape_k.cycle_id", metrics.get("cycle_id", "unknown") if metrics else "unknown")
                    
                    if metrics:
                        for key, value in metrics.items():
                            if key != "cycle_id":  # Already set above
                                span.set_attribute(f"mape_k.{key}", str(value))
                    
                    # Add phase-specific attributes
                    if phase == "monitor":
                        span.set_attribute("mape_k.metrics_count", len(metrics) if metrics else 0)
                    elif phase == "analyze":
                        span.set_attribute("mape_k.anomalies_detected", metrics.get("anomalies_count", 0) if metrics else 0)
                    elif phase == "plan":
                        span.set_attribute("mape_k.strategies_considered", metrics.get("strategies_count", 0) if metrics else 0)
                    elif phase == "execute":
                        span.set_attribute("mape_k.action_type", metrics.get("action", "unknown") if metrics else "unknown")
                    elif phase == "knowledge":
                        span.set_attribute("mape_k.knowledge_updated", metrics.get("knowledge_updated", False) if metrics else False)
                    
                    yield span
            except Exception as e:
                logger.warning(f"MAPE-K tracing error: {e}")
                yield None
        
        return span_context()
    
    @contextmanager
    def trace_full_mape_k_cycle(self, cycle_id: str, node_id: str):
        """
        Trace complete MAPE-K cycle with all phases.
        
        Args:
            cycle_id: Unique cycle identifier
            node_id: Node identifier
        
        Returns:
            Context manager for the full cycle span
        """
        if not self.tracer:
            @contextmanager
            def noop():
                yield None
            return noop()
        
        @contextmanager
        def cycle_span():
            try:
                with self.tracer.start_as_current_span("mape_k.full_cycle") as cycle_span:
                    cycle_span.set_attribute("mape_k.cycle_id", cycle_id)
                    cycle_span.set_attribute("mape_k.node_id", node_id)
                    cycle_span.set_attribute("mape_k.phases", "monitor,analyze,plan,execute,knowledge")
                    yield cycle_span
            except Exception as e:
                logger.warning(f"Full MAPE-K cycle tracing error: {e}")
                yield None
        
        return cycle_span()
    
    def trace_network_adaptation(self, action: str, details: Optional[Dict[str, Any]] = None):
        """
        Trace network adaptation action.
        
        Args:
            action: Action name (route_switch, failover, etc.)
            details: Optional details to add as attributes
        """
        if not self.tracer:
            return
        
        try:
            with self.tracer.start_as_current_span(f"network.adaptation.{action}") as span:
                span.set_attribute("network.action", action)
                if details:
                    for key, value in details.items():
                        span.set_attribute(f"network.{key}", str(value))
        except Exception as e:
            logger.warning(f"Network adaptation tracing error: {e}")
    
    def trace_rag_retrieval(self, query: str, results_count: int, latency_ms: float):
        """
        Trace RAG retrieval operation.
        
        Args:
            query: Query string
            results_count: Number of results
            latency_ms: Latency in milliseconds
        """
        if not self.tracer:
            return
        
        try:
            with self.tracer.start_as_current_span("rag.retrieval") as span:
                span.set_attribute("rag.query_length", len(query))
                span.set_attribute("rag.results_count", results_count)
                span.set_attribute("rag.latency_ms", latency_ms)
        except Exception as e:
            logger.warning(f"RAG tracing error: {e}")
    
    def trace_function(self, span_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
        """
        Decorator for automatic function tracing.
        
        Args:
            span_name: Custom span name (default: function name)
            attributes: Additional span attributes
        
        Example:
            @tracing_manager.trace_function(span_name="custom_operation")
            def my_function():
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.tracer:
                    return func(*args, **kwargs)
                
                name = span_name or f"{func.__module__}.{func.__name__}"
                with self.tracer.start_as_current_span(name) as span:
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, str(value))
                    
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    
                    try:
                        result = func(*args, **kwargs)
                        span.set_status(Status(StatusCode.OK))
                        return result
                    except Exception as e:
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.record_exception(e)
                        raise
            
            return wrapper
        return decorator
    
    def create_span_from_context(self, span_name: str, context: Optional[Context] = None, attributes: Optional[Dict[str, Any]] = None):
        """
        Create a span from existing context (for distributed tracing).
        
        Args:
            span_name: Span name
            context: Existing context (extracted from headers)
            attributes: Span attributes
        
        Returns:
            Context manager for the span
        """
        if not self.tracer:
            @contextmanager
            def noop():
                yield None
            return noop()
        
        @contextmanager
        def span_context():
            try:
                if context:
                    token = attach(context)
                else:
                    token = None
                
                with self.tracer.start_as_current_span(span_name) as span:
                    if attributes:
                        for key, value in attributes.items():
                            span.set_attribute(key, str(value))
                    yield span
            finally:
                if token:
                    detach(token)
        
        return span_context()
    
    def extract_context_from_headers(self, headers: Dict[str, str]) -> Optional[Context]:
        """
        Extract trace context from HTTP headers.
        
        Args:
            headers: HTTP headers dictionary
        
        Returns:
            Extracted context or None
        """
        if not OPENTELEMETRY_AVAILABLE or not extract:
            return None
        
        try:
            # Convert headers to format expected by extract
            carrier = {k.lower(): v for k, v in headers.items()}
            context = extract(carrier)
            return context
        except Exception as e:
            logger.warning(f"Failed to extract context from headers: {e}")
            return None
    
    def inject_context_to_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """
        Inject trace context into HTTP headers.
        
        Args:
            headers: HTTP headers dictionary
        
        Returns:
            Headers with injected trace context
        """
        if not OPENTELEMETRY_AVAILABLE or not inject:
            return headers
        
        try:
            carrier = {}
            inject(carrier)
            # Merge with existing headers
            headers.update({k: v for k, v in carrier.items() if isinstance(v, str)})
            return headers
        except Exception as e:
            logger.warning(f"Failed to inject context to headers: {e}")
            return headers
    
    def add_span_event(self, span: Any, name: str, attributes: Optional[Dict[str, Any]] = None, timestamp: Optional[float] = None):
        """
        Add an event to a span.
        
        Args:
            span: Span object
            name: Event name
            attributes: Event attributes
            timestamp: Optional timestamp (Unix timestamp)
        """
        if not span:
            return
        
        try:
            span.add_event(name, attributes=attributes or {}, timestamp=timestamp)
        except Exception as e:
            logger.warning(f"Failed to add span event: {e}")
    
    def get_current_span(self) -> Optional[Any]:
        """
        Get the current active span.
        
        Returns:
            Current span or None
        """
        if not OPENTELEMETRY_AVAILABLE or not self.tracer:
            return None
        
        try:
            return trace.get_current_span()
        except Exception:
            return None
    
    def get_current_trace_id(self) -> Optional[str]:
        """
        Get the current trace ID.
        
        Returns:
            Trace ID as hex string or None
        """
        span = self.get_current_span()
        if not span:
            return None
        
        try:
            context = span.get_span_context()
            return format(context.trace_id, '032x')
        except Exception:
            return None
    
    def get_current_span_id(self) -> Optional[str]:
        """
        Get the current span ID.
        
        Returns:
            Span ID as hex string or None
        """
        span = self.get_current_span()
        if not span:
            return None
        
        try:
            context = span.get_span_context()
            return format(context.span_id, '016x')
        except Exception:
            return None


# Global tracing manager instance
_tracing_manager: Optional[TracingManager] = None


def get_tracing_manager() -> Optional[TracingManager]:
    """Get global tracing manager instance"""
    return _tracing_manager


def initialize_tracing(
    service_name: str = "x0tta6bl4",
    service_version: str = "3.1",
    jaeger_endpoint: Optional[str] = None,
    zipkin_endpoint: Optional[str] = None,
    otlp_endpoint: Optional[str] = None,
    enable_console: bool = False,
    trace_sampling_ratio: Optional[float] = None,
    enable_fastapi_instrumentation: bool = True
) -> TracingManager:
    """
    Initialize global tracing manager with full distributed tracing support.
    
    Args:
        service_name: Service name
        service_version: Service version
        jaeger_endpoint: Jaeger collector endpoint
        zipkin_endpoint: Zipkin collector endpoint
        otlp_endpoint: OTLP collector endpoint
        enable_console: Enable console exporter
        trace_sampling_ratio: Sampling ratio (0.0-1.0). If None, uses env var OTEL_TRACES_SAMPLER_ARG or 1.0
        enable_fastapi_instrumentation: Enable automatic FastAPI instrumentation
    
    Returns:
        TracingManager instance
    """
    global _tracing_manager
    
    # Get sampling ratio from env or parameter
    if trace_sampling_ratio is None:
        trace_sampling_ratio = float(os.getenv("OTEL_TRACES_SAMPLER_ARG", "1.0"))
    
    _tracing_manager = TracingManager(
        service_name=service_name,
        service_version=service_version,
        jaeger_endpoint=jaeger_endpoint,
        zipkin_endpoint=zipkin_endpoint,
        otlp_endpoint=otlp_endpoint,
        enable_console=enable_console,
        trace_sampling_ratio=trace_sampling_ratio,
        enable_fastapi_instrumentation=enable_fastapi_instrumentation
    )
    
    return _tracing_manager

