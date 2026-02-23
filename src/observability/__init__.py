"""
OpenTelemetry Tracing Module for MaaS x0tta6bl4

Provides distributed tracing, metrics, and logging integration.
"""

from .tracing import (
    TracingConfig,
    TracerProvider,
    get_tracer,
    start_span,
    trace_method,
    traced_context,
)
from .middleware import TracingMiddleware, RequestTracer
from .exporters import (
    OTLPSpanExporter,
    JaegerExporter,
    ConsoleSpanExporter,
    MultiSpanExporter,
)
from .instrumentation import (
    instrument_fastapi,
    instrument_sqlalchemy,
    instrument_redis,
    instrument_httpx,
    instrument_all,
)

__all__ = [
    # Tracing
    "TracingConfig",
    "TracerProvider",
    "get_tracer",
    "start_span",
    "trace_method",
    "traced_context",
    # Middleware
    "TracingMiddleware",
    "RequestTracer",
    # Exporters
    "OTLPSpanExporter",
    "JaegerExporter",
    "ConsoleSpanExporter",
    "MultiSpanExporter",
    # Instrumentation
    "instrument_fastapi",
    "instrument_sqlalchemy",
    "instrument_redis",
    "instrument_httpx",
    "instrument_all",
]

__version__ = "1.0.0"
