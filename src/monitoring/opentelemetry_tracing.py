"""
OpenTelemetry Distributed Tracing Integration

Provides distributed tracing for x0tta6bl4 with spans for:
- MAPE-K autonomic loop (Monitor, Analyze, Plan, Execute, Knowledge)
- Mesh networking operations
- SPIFFE identity operations
- ML inference and training
- DAO governance
- eBPF program execution
"""

import logging
import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

# Optional OpenTelemetry imports
OTEL_AVAILABLE = False
JAEGER_AVAILABLE = False
PROMETHEUS_EXPORTER_AVAILABLE = False

try:
    from opentelemetry import metrics, trace
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OTEL_AVAILABLE = True
except ImportError:
    logger.debug("OpenTelemetry SDK not available")

# Optional Jaeger exporter (deprecated, prefer OTLP)
try:
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter

    JAEGER_AVAILABLE = True
except ImportError:
    JaegerExporter = None  # type: ignore

# Optional Prometheus exporter
try:
    from opentelemetry.exporter.prometheus import PrometheusMetricReader

    PROMETHEUS_EXPORTER_AVAILABLE = True
except ImportError:
    PrometheusMetricReader = None  # type: ignore

# Optional OTLP exporter (preferred)
try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
        OTLPSpanExporter

    OTLP_AVAILABLE = True
except ImportError:
    OTLPSpanExporter = None  # type: ignore
    OTLP_AVAILABLE = False

# Optional instrumentors
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
except ImportError:
    FastAPIInstrumentor = None  # type: ignore
    RequestsInstrumentor = None  # type: ignore
    HTTPXClientInstrumentor = None  # type: ignore

try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
except ImportError:
    SQLAlchemyInstrumentor = None  # type: ignore


class OTelTracingManager:
    """
    Manages OpenTelemetry tracing configuration and span creation.

    Supports:
    - Jaeger backend for distributed tracing
    - Automatic instrumentation of FastAPI, requests, SQLAlchemy
    - Custom spans for application logic
    - Metrics collection
    """

    def __init__(
        self,
        service_name: str = "x0tta6bl4",
        jaeger_host: str = "localhost",
        jaeger_port: int = 6831,
        enable_metrics: bool = True,
    ):
        """
        Initialize OpenTelemetry tracing.

        Args:
            service_name: Service name for tracing
            jaeger_host: Jaeger agent host
            jaeger_port: Jaeger agent port
            enable_metrics: Enable metrics collection
        """
        self.service_name = service_name
        self.enabled = OTEL_AVAILABLE
        self.tracer = None
        self.meter = None

        if not OTEL_AVAILABLE:
            logger.warning(
                "OpenTelemetry disabled - install dependencies to enable tracing"
            )
            return

        try:
            # Initialize Jaeger exporter
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
            )

            # Setup trace provider
            trace_provider = TracerProvider()
            trace_provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
            trace.set_tracer_provider(trace_provider)
            self.tracer = trace.get_tracer(__name__)

            # Setup metrics (optional)
            if enable_metrics:
                prometheus_reader = PrometheusMetricReader()
                meter_provider = MeterProvider(metric_readers=[prometheus_reader])
                metrics.set_meter_provider(meter_provider)
                self.meter = metrics.get_meter(__name__)

            logger.info(f"✅ OpenTelemetry initialized for {service_name}")
            self.enabled = True

        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}")
            self.enabled = False

    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        if not self.enabled:
            return

        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("✅ FastAPI instrumented with OpenTelemetry")
        except Exception as e:
            logger.warning(f"Failed to instrument FastAPI: {e}")

    def instrument_requests(self):
        """Instrument requests library."""
        if not self.enabled:
            return

        try:
            RequestsInstrumentor().instrument()
            logger.info("✅ Requests library instrumented")
        except Exception as e:
            logger.warning(f"Failed to instrument requests: {e}")

    def instrument_sqlalchemy(self, engine):
        """Instrument SQLAlchemy."""
        if not self.enabled:
            return

        try:
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("✅ SQLAlchemy instrumented")
        except Exception as e:
            logger.warning(f"Failed to instrument SQLAlchemy: {e}")

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """
        Context manager for creating spans.

        Usage:
            with tracer.span("operation_name", {"key": "value"}):
                # operation code
        """
        if not self.enabled:
            yield
            return

        with self.tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    try:
                        span.set_attribute(key, value)
                    except Exception as e:
                        logger.debug(f"Failed to set span attribute {key}: {e}")
            yield span

    def span_decorator(self, span_name: Optional[str] = None, **static_attributes):
        """
        Decorator for automatic span creation.

        Usage:
            @tracer.span_decorator("operation_name", service="mesh", node="node-a")
            def my_operation():
                pass
        """

        def decorator(func: Callable):
            name = span_name or func.__name__

            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled:
                    return func(*args, **kwargs)

                with self.span(name, static_attributes):
                    return func(*args, **kwargs)

            return wrapper

        return decorator


class MAPEKSpans:
    """Spans for MAPE-K autonomic loop phases."""

    def __init__(self, tracer_manager: OTelTracingManager):
        self.tracer = tracer_manager

    @contextmanager
    def monitor_phase(self, node_id: str, metrics_collected: int = 0):
        """Span for Monitor phase."""
        with self.tracer.span(
            "mape_k.monitor",
            {
                "node_id": node_id,
                "metrics_count": metrics_collected,
                "phase": "monitor",
            },
        ) as span:
            yield span

    @contextmanager
    def analyze_phase(self, node_id: str, anomalies: int = 0, confidence: float = 0.0):
        """Span for Analyze phase."""
        with self.tracer.span(
            "mape_k.analyze",
            {
                "node_id": node_id,
                "anomalies_detected": anomalies,
                "confidence": confidence,
                "phase": "analyze",
            },
        ) as span:
            yield span

    @contextmanager
    def plan_phase(self, node_id: str, actions: int = 0):
        """Span for Plan phase."""
        with self.tracer.span(
            "mape_k.plan",
            {"node_id": node_id, "actions_planned": actions, "phase": "plan"},
        ) as span:
            yield span

    @contextmanager
    def execute_phase(
        self, node_id: str, actions_executed: int = 0, success: bool = True
    ):
        """Span for Execute phase."""
        with self.tracer.span(
            "mape_k.execute",
            {
                "node_id": node_id,
                "actions_executed": actions_executed,
                "success": success,
                "phase": "execute",
            },
        ) as span:
            yield span

    @contextmanager
    def knowledge_phase(self, node_id: str, insights: int = 0):
        """Span for Knowledge phase."""
        with self.tracer.span(
            "mape_k.knowledge",
            {"node_id": node_id, "insights_stored": insights, "phase": "knowledge"},
        ) as span:
            yield span


class NetworkSpans:
    """Spans for mesh networking operations."""

    def __init__(self, tracer_manager: OTelTracingManager):
        self.tracer = tracer_manager

    @contextmanager
    def node_discovery(self, source_node: str, discovered_nodes: int = 0):
        """Span for node discovery."""
        with self.tracer.span(
            "mesh.node_discovery",
            {"source_node": source_node, "nodes_discovered": discovered_nodes},
        ) as span:
            yield span

    @contextmanager
    def route_calculation(self, source: str, destination: str, hops: int = 0):
        """Span for route calculation."""
        with self.tracer.span(
            "mesh.routing", {"source": source, "destination": destination, "hops": hops}
        ) as span:
            yield span

    @contextmanager
    def message_forwarding(self, from_node: str, to_node: str, message_id: str):
        """Span for message forwarding."""
        with self.tracer.span(
            "mesh.message_forward",
            {"from": from_node, "to": to_node, "message_id": message_id},
        ) as span:
            yield span


class SPIFFESpans:
    """Spans for SPIFFE/SPIRE identity operations."""

    def __init__(self, tracer_manager: OTelTracingManager):
        self.tracer = tracer_manager

    @contextmanager
    def svid_fetch(self, node_id: str, ttl_seconds: int = 0):
        """Span for SVID fetching."""
        with self.tracer.span(
            "spiffe.svid_fetch", {"node_id": node_id, "ttl_seconds": ttl_seconds}
        ) as span:
            yield span

    @contextmanager
    def svid_renewal(self, node_id: str, success: bool = True):
        """Span for SVID renewal."""
        with self.tracer.span(
            "spiffe.svid_renewal", {"node_id": node_id, "success": success}
        ) as span:
            yield span

    @contextmanager
    def mtls_handshake(self, client: str, server: str, duration_ms: float = 0):
        """Span for mTLS handshake."""
        with self.tracer.span(
            "spiffe.mtls_handshake",
            {"client": client, "server": server, "duration_ms": duration_ms},
        ) as span:
            yield span


class MLSpans:
    """Spans for ML model operations."""

    def __init__(self, tracer_manager: OTelTracingManager):
        self.tracer = tracer_manager

    @contextmanager
    def model_inference(
        self, model_name: str, input_size: int = 0, latency_ms: float = 0
    ):
        """Span for model inference."""
        with self.tracer.span(
            "ml.inference",
            {"model": model_name, "input_size": input_size, "latency_ms": latency_ms},
        ) as span:
            yield span

    @contextmanager
    def model_training(self, model_name: str, epoch: int = 0, loss: float = 0):
        """Span for model training."""
        with self.tracer.span(
            "ml.training", {"model": model_name, "epoch": epoch, "loss": loss}
        ) as span:
            yield span


# Global tracer manager instance
_tracer_manager = None
_mapek_spans = None
_network_spans = None
_spiffe_spans = None
_ml_spans = None


def initialize_tracing(service_name: str = "x0tta6bl4", app=None):
    """
    Initialize OpenTelemetry tracing for the application.

    Args:
        service_name: Service name for tracing
        app: FastAPI app instance (optional, for auto-instrumentation)
    """
    global _tracer_manager, _mapek_spans, _network_spans, _spiffe_spans, _ml_spans

    _tracer_manager = OTelTracingManager(service_name)

    if _tracer_manager.enabled:
        _mapek_spans = MAPEKSpans(_tracer_manager)
        _network_spans = NetworkSpans(_tracer_manager)
        _spiffe_spans = SPIFFESpans(_tracer_manager)
        _ml_spans = MLSpans(_tracer_manager)

        if app:
            _tracer_manager.instrument_fastapi(app)

        _tracer_manager.instrument_requests()
        logger.info(f"✅ OpenTelemetry tracing initialized")


def get_tracer_manager() -> Optional[OTelTracingManager]:
    """Get global tracer manager."""
    return _tracer_manager


def get_mapek_spans() -> Optional[MAPEKSpans]:
    """Get MAPE-K spans helper."""
    return _mapek_spans


def get_network_spans() -> Optional[NetworkSpans]:
    """Get network spans helper."""
    return _network_spans


def get_spiffe_spans() -> Optional[SPIFFESpans]:
    """Get SPIFFE spans helper."""
    return _spiffe_spans


def get_ml_spans() -> Optional[MLSpans]:
    """Get ML spans helper."""
    return _ml_spans


__all__ = [
    "OTelTracingManager",
    "MAPEKSpans",
    "NetworkSpans",
    "SPIFFESpans",
    "MLSpans",
    "initialize_tracing",
    "get_tracer_manager",
    "get_mapek_spans",
    "get_network_spans",
    "get_spiffe_spans",
    "get_ml_spans",
]
