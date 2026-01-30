"""
OpenTelemetry Tracing Middleware for FastAPI

Provides automatic request/response tracing with:
- Request duration tracking
- HTTP method and path attributes
- Status code recording
- Error tracking
- Correlation ID propagation
"""
import time
import logging
import uuid
from typing import Optional, Callable
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Context variable for request correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# OpenTelemetry imports (optional)
OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    OTEL_AVAILABLE = True
except ImportError:
    logger.debug("OpenTelemetry not available - tracing middleware will be no-op")


def get_correlation_id() -> Optional[str]:
    """Get current request correlation ID."""
    return correlation_id_var.get()


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for automatic request tracing with OpenTelemetry.

    Features:
    - Automatic span creation for each request
    - Request/response attribute recording
    - Error tracking with stack traces
    - Correlation ID propagation
    - W3C Trace Context support
    """

    def __init__(
        self,
        app,
        service_name: str = "x0tta6bl4",
        excluded_paths: Optional[list] = None,
        record_request_body: bool = False,
        record_response_body: bool = False
    ):
        super().__init__(app)
        self.service_name = service_name
        self.excluded_paths = excluded_paths or ["/health", "/metrics"]
        self.record_request_body = record_request_body
        self.record_response_body = record_response_body

        if OTEL_AVAILABLE:
            self.tracer = trace.get_tracer(__name__)
            self.propagator = TraceContextTextMapPropagator()
            logger.info(f"Tracing middleware initialized for {service_name}")
        else:
            self.tracer = None
            self.propagator = None
            logger.warning("Tracing middleware running in no-op mode (OpenTelemetry not available)")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip tracing for excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)

        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        correlation_id_var.set(correlation_id)

        # If OpenTelemetry not available, just add correlation ID
        if not OTEL_AVAILABLE or not self.tracer:
            start_time = time.time()
            response = await call_next(request)
            duration = time.time() - start_time

            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-Duration"] = f"{duration:.3f}s"

            logger.debug(
                f"{request.method} {path} - {response.status_code} "
                f"({duration:.3f}s) [correlation_id={correlation_id}]"
            )
            return response

        # Extract trace context from headers
        ctx = self.propagator.extract(carrier=dict(request.headers))

        # Create span for this request
        span_name = f"{request.method} {path}"

        with self.tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=trace.SpanKind.SERVER
        ) as span:
            # Set request attributes
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.path", path)
            span.set_attribute("http.host", request.url.hostname or "unknown")
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("correlation_id", correlation_id)

            # Client info
            if request.client:
                span.set_attribute("http.client_ip", request.client.host)

            # User agent
            user_agent = request.headers.get("User-Agent", "")
            if user_agent:
                span.set_attribute("http.user_agent", user_agent[:200])

            # Query params count
            span.set_attribute("http.query_params_count", len(request.query_params))

            start_time = time.time()

            try:
                response = await call_next(request)
                duration = time.time() - start_time

                # Set response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_content_type",
                                   response.headers.get("content-type", "unknown"))

                # Mark span status based on HTTP status
                if response.status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR, f"HTTP {response.status_code}"))
                elif response.status_code >= 400:
                    span.set_status(Status(StatusCode.ERROR, f"Client error {response.status_code}"))
                else:
                    span.set_status(Status(StatusCode.OK))

                # Add correlation ID and timing to response
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Request-Duration"] = f"{duration:.3f}s"

                # Inject trace context into response for downstream propagation
                trace_context = {}
                self.propagator.inject(trace_context)
                if "traceparent" in trace_context:
                    response.headers["X-Trace-ID"] = trace_context.get("traceparent", "")

                span.set_attribute("http.duration_ms", duration * 1000)

                return response

            except Exception as e:
                duration = time.time() - start_time

                # Record exception in span
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.set_attribute("http.duration_ms", duration * 1000)

                logger.error(f"Request failed: {e}", exc_info=True)
                raise


class DatabaseTracingMiddleware:
    """
    Helper for database query tracing.

    Usage:
        with db_tracer.trace_query("SELECT * FROM users"):
            result = db.execute(query)
    """

    def __init__(self, service_name: str = "x0tta6bl4-db"):
        self.service_name = service_name
        if OTEL_AVAILABLE:
            self.tracer = trace.get_tracer(__name__)
        else:
            self.tracer = None

    def trace_query(self, operation: str, table: str = "unknown"):
        """Context manager for tracing database queries."""
        if not OTEL_AVAILABLE or not self.tracer:
            from contextlib import nullcontext
            return nullcontext()

        span = self.tracer.start_span(
            f"db.{operation}",
            kind=trace.SpanKind.CLIENT
        )
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", operation)
        span.set_attribute("db.table", table)
        span.set_attribute("correlation_id", get_correlation_id() or "unknown")

        return span


class ExternalAPITracingMiddleware:
    """
    Helper for external API call tracing.

    Usage:
        with api_tracer.trace_call("stripe", "create_checkout"):
            response = stripe.checkout.create(...)
    """

    def __init__(self):
        if OTEL_AVAILABLE:
            self.tracer = trace.get_tracer(__name__)
            self.propagator = TraceContextTextMapPropagator()
        else:
            self.tracer = None
            self.propagator = None

    def trace_call(self, service: str, operation: str, url: str = ""):
        """Context manager for tracing external API calls."""
        if not OTEL_AVAILABLE or not self.tracer:
            from contextlib import nullcontext
            return nullcontext()

        span = self.tracer.start_span(
            f"external.{service}.{operation}",
            kind=trace.SpanKind.CLIENT
        )
        span.set_attribute("external.service", service)
        span.set_attribute("external.operation", operation)
        if url:
            span.set_attribute("external.url", url)
        span.set_attribute("correlation_id", get_correlation_id() or "unknown")

        return span

    def inject_headers(self, headers: dict) -> dict:
        """Inject trace context into outgoing request headers."""
        if not self.propagator:
            return headers

        self.propagator.inject(headers)
        return headers


# Global instances for easy import
db_tracer = DatabaseTracingMiddleware()
api_tracer = ExternalAPITracingMiddleware()


__all__ = [
    "TracingMiddleware",
    "DatabaseTracingMiddleware",
    "ExternalAPITracingMiddleware",
    "get_correlation_id",
    "db_tracer",
    "api_tracer",
]
