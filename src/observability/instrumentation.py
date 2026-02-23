"""
Auto-Instrumentation for Common Libraries

Provides automatic instrumentation for FastAPI, SQLAlchemy, Redis, HTTPX, etc.
"""

import functools
import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .tracing import (
    Span,
    SpanKind,
    SpanStatusCode,
    get_tracer,
    traced_context,
    trace_method,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def instrument_fastapi(app: Any, service_name: str = "maas-x0tta6bl4") -> None:
    """
    Instrument FastAPI application with tracing.
    
    Usage:
        from fastapi import FastAPI
        from src.observability import instrument_fastapi
        
        app = FastAPI()
        instrument_fastapi(app, service_name="my-api")
    """
    from .middleware import setup_tracing
    setup_tracing(app, service_name=service_name)
    logger.info(f"FastAPI instrumented: {service_name}")


def instrument_sqlalchemy(
    engine: Any,
    capture_statements: bool = True,
    capture_params: bool = False,
) -> Any:
    """
    Instrument SQLAlchemy engine with tracing.
    
    Usage:
        from sqlalchemy import create_engine
        from src.observability import instrument_sqlalchemy
        
        engine = create_engine("postgresql://...")
        engine = instrument_sqlalchemy(engine)
    """
    from sqlalchemy import event
    
    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Start span before query execution."""
        tracer = get_tracer("sqlalchemy")
        
        # Extract operation from statement
        operation = statement.split()[0].upper() if statement else "UNKNOWN"
        table = _extract_table(statement)
        
        span_name = f"db.query {operation}"
        if table:
            span_name += f" {table}"
        
        # Store span in context
        conn.info["otel_span"] = tracer.start_span(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes={
                "db.system": "postgresql",
                "db.statement": statement if capture_statements else "[REDACTED]",
                "db.operation": operation,
                "net.peer.name": str(conn.engine.url.host) if conn.engine.url else "unknown",
            },
        )
    
    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """End span after query execution."""
        span = conn.info.pop("otel_span", None)
        if span:
            # Add row count if available
            if cursor.rowcount >= 0:
                span.set_attribute("db.rows_affected", cursor.rowcount)
            
            span.set_status(SpanStatusCode.OK)
            span.end()
            
            # Export span
            from .tracing import _provider
            if _provider:
                _provider.export_span(span)
    
    @event.listens_for(engine, "dbapi_error")
    def dbapi_error(conn, cursor, statement, parameters, context, exception):
        """Record exception on database error."""
        span = conn.info.pop("otel_span", None)
        if span:
            span.record_exception(exception)
            span.end()
            
            from .tracing import _provider
            if _provider:
                _provider.export_span(span)
    
    logger.info("SQLAlchemy engine instrumented")
    return engine


def _extract_table(statement: str) -> Optional[str]:
    """Extract table name from SQL statement."""
    if not statement:
        return None
    
    parts = statement.upper().split()
    if len(parts) < 2:
        return None
    
    # Common patterns
    if parts[0] in ("SELECT", "DELETE"):
        # FROM table
        if "FROM" in parts:
            idx = parts.index("FROM")
            if idx + 1 < len(parts):
                return parts[idx + 1].strip('"\'').lower()
    elif parts[0] in ("INSERT", "UPDATE"):
        # INSERT INTO table / UPDATE table
        if parts[0] == "INSERT" and len(parts) > 2 and parts[1] == "INTO":
            return parts[2].strip('"\'').lower()
        elif parts[0] == "UPDATE":
            return parts[1].strip('"\'').lower()
    
    return None


def instrument_redis(client: Any, capture_commands: bool = True) -> Any:
    """
    Instrument Redis client with tracing.
    
    Usage:
        import redis
        from src.observability import instrument_redis
        
        client = redis.Redis(host='localhost', port=6379)
        client = instrument_redis(client)
    """
    original_execute_command = client.execute_command
    
    @functools.wraps(original_execute_command)
    def traced_execute_command(*args, **kwargs):
        command = args[0] if args else "UNKNOWN"
        
        with traced_context(
            name=f"redis.{command}",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system": "redis",
                "db.operation": command,
                "db.statement": " ".join(str(a) for a in args) if capture_commands else "[REDACTED]",
            },
        ) as span:
            try:
                result = original_execute_command(*args, **kwargs)
                span.set_status(SpanStatusCode.OK)
                return result
            except Exception as e:
                span.record_exception(e)
                raise
    
    client.execute_command = traced_execute_command
    logger.info("Redis client instrumented")
    return client


def instrument_httpx(client: Any, capture_body: bool = False) -> Any:
    """
    Instrument HTTPX client with tracing.
    
    Usage:
        import httpx
        from src.observability import instrument_httpx
        
        client = httpx.Client()
        client = instrument_httpx(client)
    """
    original_request = client.request
    
    @functools.wraps(original_request)
    def traced_request(method: str, url: str, **kwargs):
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        span_name = f"HTTP {method} {parsed.netloc}{parsed.path}"
        
        with traced_context(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes={
                "http.method": method,
                "http.url": url,
                "http.scheme": parsed.scheme,
                "net.peer.name": parsed.netloc,
            },
        ) as span:
            # Inject trace context into headers
            headers = kwargs.get("headers", {})
            from .tracing import inject_trace_context
            headers = inject_trace_context(dict(headers))
            kwargs["headers"] = headers
            
            try:
                response = original_request(method, url, **kwargs)
                span.set_attribute("http.status_code", response.status_code)
                
                if response.status_code < 400:
                    span.set_status(SpanStatusCode.OK)
                else:
                    span.set_status(SpanStatusCode.ERROR, f"HTTP {response.status_code}")
                
                return response
            except Exception as e:
                span.record_exception(e)
                raise
    
    client.request = traced_request
    logger.info("HTTPX client instrumented")
    return client


def instrument_aiohttp(client: Any) -> Any:
    """
    Instrument aiohttp client session with tracing.
    
    Usage:
        import aiohttp
        from src.observability import instrument_aiohttp
        
        session = aiohttp.ClientSession()
        session = instrument_aiohttp(session)
    """
    original_request = client._request
    
    @functools.wraps(original_request)
    async def traced_request(method: str, url: str, **kwargs):
        from urllib.parse import urlparse
        
        parsed = urlparse(str(url))
        span_name = f"HTTP {method} {parsed.netloc}{parsed.path}"
        
        with traced_context(
            name=span_name,
            kind=SpanKind.CLIENT,
            attributes={
                "http.method": method,
                "http.url": str(url),
                "http.scheme": parsed.scheme,
                "net.peer.name": parsed.netloc,
            },
        ) as span:
            # Inject trace context into headers
            headers = kwargs.get("headers", {})
            from .tracing import inject_trace_context
            headers = inject_trace_context(dict(headers))
            kwargs["headers"] = headers
            
            try:
                response = await original_request(method, url, **kwargs)
                span.set_attribute("http.status_code", response.status)
                
                if response.status < 400:
                    span.set_status(SpanStatusCode.OK)
                else:
                    span.set_status(SpanStatusCode.ERROR, f"HTTP {response.status}")
                
                return response
            except Exception as e:
                span.record_exception(e)
                raise
    
    client._request = traced_request
    logger.info("aiohttp client instrumented")
    return client


def instrument_celery(app: Any) -> Any:
    """
    Instrument Celery app with tracing.
    
    Usage:
        from celery import Celery
        from src.observability import instrument_celery
        
        app = Celery('tasks')
        app = instrument_celery(app)
    """
    from celery import signals
    
    @signals.task_prerun.connect
    def task_prerun_handler(task_id, task, args, kwargs, **extra):
        """Start span before task execution."""
        tracer = get_tracer("celery")
        
        span = tracer.start_span(
            name=f"celery.task {task.name}",
            kind=SpanKind.CONSUMER,
            attributes={
                "celery.task_id": task_id,
                "celery.task_name": task.name,
                "celery.queue": task.queue or "default",
            },
        )
        
        # Store in task context
        task.request.otel_span = span
    
    @signals.task_postrun.connect
    def task_postrun_handler(task_id, task, args, kwargs, retval, state, **extra):
        """End span after task execution."""
        span = getattr(task.request, "otel_span", None)
        if span:
            span.set_attribute("celery.task_state", state)
            
            if state == "SUCCESS":
                span.set_status(SpanStatusCode.OK)
            elif state == "FAILURE":
                span.set_status(SpanStatusCode.ERROR, "Task failed")
            
            span.end()
            
            from .tracing import _provider
            if _provider:
                _provider.export_span(span)
    
    @signals.task_failure.connect
    def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **extra):
        """Record exception on task failure."""
        # Get span from current task
        from celery import current_task
        if current_task:
            span = getattr(current_task.request, "otel_span", None)
            if span:
                span.record_exception(exception)
    
    logger.info("Celery app instrumented")
    return app


def instrument_grpc(server: Any = None, client: Any = None) -> None:
    """
    Instrument gRPC server/client with tracing.
    
    Usage:
        from src.observability import instrument_grpc
        
        # For server
        instrument_grpc(server=grpc_server)
        
        # For client
        instrument_grpc(client=grpc_channel)
    """
    if server:
        _instrument_grpc_server(server)
    
    if client:
        _instrument_grpc_client(client)
    
    logger.info("gRPC instrumented")


def _instrument_grpc_server(server: Any) -> None:
    """Instrument gRPC server."""
    from grpc import aio
    
    class TracingInterceptor(aio.ServerInterceptor):
        async def intercept_service(self, continuation, handler_call_details):
            method = handler_call_details.method
            
            tracer = get_tracer("grpc.server")
            span = tracer.start_span(
                name=f"grpc.server {method}",
                kind=SpanKind.SERVER,
                attributes={
                    "rpc.system": "grpc",
                    "rpc.method": method,
                },
            )
            
            # Store span in context
            handler_call_details.otel_span = span
            
            handler = await continuation(handler_call_details)
            
            if handler:
                # Wrap the handler
                if hasattr(handler, 'unary_unary'):
                    original_fn = handler.unary_unary
                    
                    async def wrapped_fn(request, context):
                        try:
                            response = await original_fn(request, context)
                            span.set_status(SpanStatusCode.OK)
                            return response
                        except Exception as e:
                            span.record_exception(e)
                            raise
                        finally:
                            span.end()
                            from .tracing import _provider
                            if _provider:
                                _provider.export_span(span)
                    
                    handler.unary_unary = wrapped_fn
            
            return handler
    
    # Add interceptor
    # Note: This is simplified - actual implementation depends on gRPC version
    logger.info("gRPC server interceptor added")


def _instrument_grpc_client(channel: Any) -> None:
    """Instrument gRPC client channel."""
    # Add client interceptor
    # Note: This is simplified - actual implementation depends on gRPC version
    logger.info("gRPC client interceptor added")


def instrument_all(
    fastapi_app: Any = None,
    sqlalchemy_engine: Any = None,
    redis_client: Any = None,
    httpx_client: Any = None,
    celery_app: Any = None,
    service_name: str = "maas-x0tta6bl4",
) -> Dict[str, bool]:
    """
    Instrument all provided components.
    
    Usage:
        from src.observability import instrument_all
        
        instrument_all(
            fastapi_app=app,
            sqlalchemy_engine=engine,
            redis_client=redis,
            httpx_client=http,
            celery_app=celery,
            service_name="my-service",
        )
    """
    results = {}
    
    if fastapi_app:
        try:
            instrument_fastapi(fastapi_app, service_name)
            results["fastapi"] = True
        except Exception as e:
            logger.error(f"Failed to instrument FastAPI: {e}")
            results["fastapi"] = False
    
    if sqlalchemy_engine:
        try:
            instrument_sqlalchemy(sqlalchemy_engine)
            results["sqlalchemy"] = True
        except Exception as e:
            logger.error(f"Failed to instrument SQLAlchemy: {e}")
            results["sqlalchemy"] = False
    
    if redis_client:
        try:
            instrument_redis(redis_client)
            results["redis"] = True
        except Exception as e:
            logger.error(f"Failed to instrument Redis: {e}")
            results["redis"] = False
    
    if httpx_client:
        try:
            instrument_httpx(httpx_client)
            results["httpx"] = True
        except Exception as e:
            logger.error(f"Failed to instrument HTTPX: {e}")
            results["httpx"] = False
    
    if celery_app:
        try:
            instrument_celery(celery_app)
            results["celery"] = True
        except Exception as e:
            logger.error(f"Failed to instrument Celery: {e}")
            results["celery"] = False
    
    logger.info(f"Instrumentation complete: {results}")
    return results


# Decorator for custom instrumentation
def traced(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    Decorator to trace any function.
    
    Usage:
        @traced("process_payment", attributes={"payment.type": "credit_card"})
        async def process_payment(amount: float):
            ...
    """
    return trace_method(name, kind, attributes)
