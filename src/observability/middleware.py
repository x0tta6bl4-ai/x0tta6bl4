"""
FastAPI Middleware for OpenTelemetry Tracing

Provides automatic request tracing for FastAPI applications.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send, Message

from .tracing import (
    Span,
    SpanKind,
    SpanStatusCode,
    TracerProvider,
    get_tracer,
    extract_trace_context,
    inject_trace_context,
)

logger = logging.getLogger(__name__)


@dataclass
class RequestTracer:
    """Traces HTTP requests."""
    
    # Headers to extract from incoming requests
    INCOMING_TRACE_HEADERS = {
        "traceparent",
        "tracestate",
        "x-request-id",
        "x-b3-traceid",
        "x-b3-spanid",
        "x-b3-sampled",
    }
    
    # Headers to inject into outgoing requests
    OUTGOING_TRACE_HEADERS = {
        "traceparent",
        "tracestate",
    }
    
    # Sensitive headers to redact
    SENSITIVE_HEADERS = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "x-auth-token",
    }
    
    @classmethod
    def extract_context(cls, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Extract trace context from request headers."""
        context = extract_trace_context(headers)
        if context:
            return {
                "trace_id": context.trace_id,
                "span_id": context.span_id,
                "trace_flags": context.trace_flags,
            }
        return None
    
    @classmethod
    def inject_context(cls, headers: Dict[str, str]) -> Dict[str, str]:
        """Inject trace context into request headers."""
        return inject_trace_context(headers)
    
    @classmethod
    def redact_headers(cls, headers: Dict[str, str]) -> Dict[str, str]:
        """Redact sensitive headers."""
        return {
            k: "[REDACTED]" if k.lower() in cls.SENSITIVE_HEADERS else v
            for k, v in headers.items()
        }


class TracingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic request tracing.
    
    Features:
    - Automatic span creation for each request
    - Trace context propagation
    - Request/response attribute capture
    - Error tracking
    - Performance metrics
    
    Usage:
        app = FastAPI()
        app.add_middleware(TracingMiddleware, service_name="my-service")
    """
    
    def __init__(
        self,
        app: ASGIApp,
        service_name: str = "maas-x0tta6bl4",
        excluded_paths: Optional[Set[str]] = None,
        request_attributes: bool = True,
        response_attributes: bool = True,
        capture_headers: bool = True,
        capture_body: bool = False,
        max_body_size: int = 64 * 1024,  # 64KB
    ):
        super().__init__(app)
        self.service_name = service_name
        self.excluded_paths = excluded_paths or {"/health", "/metrics", "/ready"}
        self.request_attributes = request_attributes
        self.response_attributes = response_attributes
        self.capture_headers = capture_headers
        self.capture_body = capture_body
        self.max_body_size = max_body_size
        
        self._tracer = None
    
    def _get_tracer(self):
        """Get or create tracer."""
        if self._tracer is None:
            self._tracer = get_tracer(self.service_name)
        return self._tracer
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with tracing."""
        # Skip excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        tracer = self._get_tracer()
        
        # Extract trace context from headers
        headers = dict(request.headers)
        parent_context = RequestTracer.extract_context(headers)
        
        # Create span name from request
        span_name = self._get_span_name(request)
        
        # Start span
        with tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.SERVER,
            attributes=self._get_request_attributes(request),
        ) as span:
            # Add request ID if not present
            request_id = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
            span.set_attribute("http.request_id", request_id)
            
            # Track timing
            start_time = time.time()
            
            try:
                # Process request
                response = await call_next(request)
                
                # Add response attributes
                if self.response_attributes:
                    span.set_attributes(self._get_response_attributes(response))
                
                span.set_status(SpanStatusCode.OK)
                return response
            
            except Exception as e:
                span.record_exception(e)
                span.set_status(SpanStatusCode.ERROR, str(e))
                raise
            
            finally:
                # Record duration
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("http.duration_ms", round(duration_ms, 2))
    
    def _get_span_name(self, request: Request) -> str:
        """Generate span name from request."""
        method = request.method
        path = request.url.path
        
        # Try to get route name if available
        route = getattr(request, "route", None)
        if route and hasattr(route, "path"):
            path = route.path
        
        return f"{method} {path}"
    
    def _get_request_attributes(self, request: Request) -> Dict[str, Any]:
        """Extract attributes from request."""
        attrs = {
            "http.method": request.method,
            "http.url": str(request.url),
            "http.scheme": request.url.scheme,
            "http.host": request.url.hostname or "unknown",
            "http.target": request.url.path,
            "http.flavor": f"{request.scope.get('http_version', '1.1')}",
            "net.peer.ip": self._get_client_ip(request),
        }
        
        # Add user agent
        user_agent = request.headers.get("user-agent")
        if user_agent:
            attrs["http.user_agent"] = user_agent[:256]  # Truncate long user agents
        
        # Add headers if enabled
        if self.capture_headers:
            headers = RequestTracer.redact_headers(dict(request.headers))
            for key, value in headers.items():
                attrs[f"http.request.header.{key.lower()}"] = value
        
        # Add query parameters
        if request.query_params:
            attrs["http.query"] = str(request.query_params)
        
        # Add content length
        content_length = request.headers.get("content-length")
        if content_length:
            attrs["http.request_content_length"] = int(content_length)
        
        return attrs
    
    def _get_response_attributes(self, response: Response) -> Dict[str, Any]:
        """Extract attributes from response."""
        attrs = {
            "http.status_code": response.status_code,
            "http.status_text": self._get_status_text(response.status_code),
        }
        
        # Add response headers if enabled
        if self.capture_headers:
            for key, value in response.headers.items():
                if key.lower() not in RequestTracer.SENSITIVE_HEADERS:
                    attrs[f"http.response.header.{key.lower()}"] = value
        
        # Add content length
        content_length = response.headers.get("content-length")
        if content_length:
            attrs["http.response_content_length"] = int(content_length)
        
        return attrs
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        # Check for real IP header
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to direct client
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_status_text(self, status_code: int) -> str:
        """Get status text for HTTP status code."""
        status_texts = {
            200: "OK",
            201: "Created",
            204: "No Content",
            301: "Moved Permanently",
            302: "Found",
            304: "Not Modified",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            405: "Method Not Allowed",
            409: "Conflict",
            422: "Unprocessable Entity",
            429: "Too Many Requests",
            500: "Internal Server Error",
            501: "Not Implemented",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout",
        }
        return status_texts.get(status_code, "Unknown")


class AsyncTracingMiddleware:
    """
    ASGI middleware for tracing.
    
    Lower-level middleware that works with any ASGI application.
    """
    
    def __init__(
        self,
        app: ASGIApp,
        service_name: str = "maas-x0tta6bl4",
    ):
        self.app = app
        self.service_name = service_name
        self._tracer = None
    
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process ASGI request."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get tracer
        if self._tracer is None:
            self._tracer = get_tracer(self.service_name)
        
        # Extract trace context
        headers = dict(scope.get("headers", []))
        headers = {k.decode(): v.decode() for k, v in headers}
        parent_context = RequestTracer.extract_context(headers)
        
        # Create span
        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        span_name = f"{method} {path}"
        
        with self._tracer.start_as_current_span(
            name=span_name,
            kind=SpanKind.SERVER,
        ) as span:
            # Add basic attributes
            span.set_attributes({
                "http.method": method,
                "http.url": str(scope.get("root_path", "")) + path,
                "http.scheme": scope.get("scheme", "http"),
                "net.peer.ip": self._get_client_ip(scope),
            })
            
            # Wrap send to capture response
            status_code = None
            
            async def send_wrapper(message: Message) -> None:
                nonlocal status_code
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    span.set_attribute("http.status_code", status_code)
                await send(message)
            
            try:
                await self.app(scope, receive, send_wrapper)
                if status_code and status_code < 400:
                    span.set_status(SpanStatusCode.OK)
                elif status_code and status_code >= 500:
                    span.set_status(SpanStatusCode.ERROR, f"HTTP {status_code}")
            except Exception as e:
                span.record_exception(e)
                raise
    
    def _get_client_ip(self, scope: Scope) -> str:
        """Get client IP from scope."""
        client = scope.get("client")
        if client:
            return client[0]
        return "unknown"


def setup_tracing(
    app: Any,
    service_name: str = "maas-x0tta6bl4",
    excluded_paths: Optional[Set[str]] = None,
) -> None:
    """
    Setup tracing for a FastAPI application.
    
    Usage:
        from fastapi import FastAPI
        from src.observability import setup_tracing
        
        app = FastAPI()
        setup_tracing(app, service_name="my-service")
    """
    # Add middleware
    app.add_middleware(
        TracingMiddleware,
        service_name=service_name,
        excluded_paths=excluded_paths,
    )
    
    logger.info(f"Tracing middleware configured for {service_name}")
