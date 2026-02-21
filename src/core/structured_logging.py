"""
Structured Logging Module for x0tta6bl4.

Provides JSON-formatted logging with:
- Structured fields (timestamp, level, module, trace_id, etc.)
- OpenTelemetry-compatible output
- Sensitive data masking
- Performance metrics integration
"""

import json
import logging
import os
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Dict, Optional, Set


# Context variables for request tracing
trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
node_id_var: ContextVar[Optional[str]] = ContextVar("node_id", default=None)


# Sensitive field names to mask
SENSITIVE_FIELDS: Set[str] = {
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "private_key", "privatekey", "secret_key", "secretkey", "access_token",
    "refresh_token", "auth", "authorization", "credential",
    "session_id", "sessionid", "cookie", "ssn", "social_security",
    "credit_card", "creditcard", "card_number", "cvv", "pin"
}

# Mask value
MASK = "***MASKED***"
_UNSET = object()


def mask_sensitive(data: Any, depth: int = 0) -> Any:
    """
    Recursively mask sensitive fields in data structures.
    
    Args:
        data: Data to mask (dict, list, or primitive)
        depth: Current recursion depth (max 10)
        
    Returns:
        Data with sensitive fields masked
    """
    if depth > 10:
        return data
    
    if isinstance(data, dict):
        masked = {}
        for key, value in data.items():
            key_lower = key.lower().replace("-", "_").replace(" ", "_")
            if key_lower in SENSITIVE_FIELDS:
                masked[key] = MASK
            else:
                masked[key] = mask_sensitive(value, depth + 1)
        return masked
    elif isinstance(data, list):
        return [mask_sensitive(item, depth + 1) for item in data]
    elif isinstance(data, str):
        # Check if string looks like a secret (long random string)
        if len(data) > 32 and all(c.isalnum() or c in "-_" for c in data):
            # Could be a token/key, but we don't mask by pattern
            # Only mask by field name
            pass
        return data
    else:
        return data


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Output format is compatible with:
    - Elasticsearch
    - Loki
    - OpenTelemetry
    - Datadog
    """
    
    def __init__(
        self,
        include_timestamp: bool = True,
        include_hostname: bool = True,
        include_process: bool = True,
        include_trace: bool = True,
        json_indent: Optional[int] = None,
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_hostname = include_hostname
        self.include_process = include_process
        self.include_trace = include_trace
        self.json_indent = json_indent
        
        # Get hostname once
        import socket
        self.hostname = socket.gethostname()
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Base fields
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add module info
        log_entry["module"] = record.module
        log_entry["function"] = record.funcName
        log_entry["line"] = record.lineno
        
        # Add hostname
        if self.include_hostname:
            log_entry["hostname"] = self.hostname
        
        # Add process info
        if self.include_process:
            log_entry["process_id"] = record.process
            log_entry["process_name"] = record.processName
            log_entry["thread_id"] = record.thread
            log_entry["thread_name"] = record.threadName
        
        # Add trace context
        if self.include_trace:
            trace_id = trace_id_var.get()
            span_id = span_id_var.get()
            node_id = node_id_var.get()
            
            if trace_id:
                log_entry["trace_id"] = trace_id
            if span_id:
                log_entry["span_id"] = span_id
            if node_id:
                log_entry["node_id"] = node_id
        
        # Add extra fields from record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "asctime"
            }:
                extra_fields[key] = value
        
        if extra_fields:
            # Mask sensitive data in extra fields
            log_entry["extra"] = mask_sensitive(extra_fields)
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stacktrace": self.formatException(record.exc_info),
            }
        
        # Add stack info if present
        if record.stack_info:
            log_entry["stack"] = self.formatStack(record.stack_info)
        
        return json.dumps(log_entry, indent=self.json_indent, default=str)


class StructuredLogger:
    """
    High-level structured logger with convenience methods.
    
    Usage:
        logger = StructuredLogger(__name__)
        logger.info("Request processed", extra={"duration_ms": 150, "status": 200})
        logger.error("Failed to connect", exc_info=True, extra={"host": "example.com"})
    """
    
    def __init__(
        self,
        name: str,
        level: int = logging.INFO,
        formatter: Optional[StructuredFormatter] = None,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # Add structured handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter or StructuredFormatter())
        self.logger.addHandler(handler)
        
        # Prevent propagation to root logger
        self.logger.propagate = False
    
    def _log(
        self,
        level: int,
        message: str,
        exc_info: bool = False,
        **kwargs: Any,
    ) -> None:
        """Internal log method."""
        # Extract known extra fields
        extra = kwargs.pop("extra", {})
        
        # Add remaining kwargs to extra
        for key, value in kwargs.items():
            extra[key] = value
        
        self.logger.log(level, message, exc_info=exc_info, extra=extra)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log error message."""
        self._log(logging.ERROR, message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs: Any) -> None:
        """Log critical message."""
        self._log(logging.CRITICAL, message, exc_info=exc_info, **kwargs)
    
    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self._log(logging.ERROR, message, exc_info=True, **kwargs)


def set_trace_context(
    trace_id: Optional[str] | object = _UNSET,
    span_id: Optional[str] | object = _UNSET,
    node_id: Optional[str] | object = _UNSET,
) -> Dict[str, Optional[str]]:
    """
    Set trace context for current request/operation.
    
    Args:
        trace_id: OpenTelemetry trace ID
        span_id: OpenTelemetry span ID
        node_id: Mesh node ID
        
    Returns:
        Previous context values
    """
    previous = {
        "trace_id": trace_id_var.get(),
        "span_id": span_id_var.get(),
        "node_id": node_id_var.get(),
    }
    
    if trace_id is not _UNSET:
        trace_id_var.set(trace_id)
    if span_id is not _UNSET:
        span_id_var.set(span_id)
    if node_id is not _UNSET:
        node_id_var.set(node_id)
    
    return previous


def generate_trace_id() -> str:
    """Generate a new trace ID (UUID4 without dashes)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a new span ID (16 hex chars)."""
    return uuid.uuid4().hex[:16]


def get_logger(name: str, level: int = None) -> StructuredLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        level: Log level (default: from LOG_LEVEL env var or INFO)
        
    Returns:
        StructuredLogger instance
    """
    if level is None:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
    
    return StructuredLogger(name, level=level)


def timed(logger: Optional[StructuredLogger] = None):
    """
    Decorator to log function execution time.
    
    Usage:
        @timed()
        def slow_function():
            time.sleep(1)
        
        @timed(logger=get_logger(__name__))
        async def async_function():
            await asyncio.sleep(1)
    """
    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                log = logger or get_logger(func.__module__)
                log.info(
                    f"Function {func.__name__} completed",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="success",
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log = logger or get_logger(func.__module__)
                log.error(
                    f"Function {func.__name__} failed: {e}",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error_type=type(e).__name__,
                )
                raise
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                log = logger or get_logger(func.__module__)
                log.info(
                    f"Async function {func.__name__} completed",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="success",
                )
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log = logger or get_logger(func.__module__)
                log.error(
                    f"Async function {func.__name__} failed: {e}",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="error",
                    error_type=type(e).__name__,
                )
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class LogContext:
    """
    Context manager for setting trace context.
    
    Usage:
        with LogContext(node_id="node-1"):
            logger.info("Processing request")  # Will include node_id
        
        # Or with auto-generated trace ID
        with LogContext(trace_id="auto", node_id="node-1"):
            logger.info("Processing request")
    """
    
    def __init__(
        self,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        node_id: Optional[str] = None,
    ):
        self.trace_id = generate_trace_id() if trace_id == "auto" else trace_id
        self.span_id = generate_span_id() if span_id == "auto" else span_id
        self.node_id = node_id
        self.previous: Dict[str, Optional[str]] = {}
    
    def __enter__(self) -> "LogContext":
        self.previous = set_trace_context(
            trace_id=self.trace_id,
            span_id=self.span_id,
            node_id=self.node_id,
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        set_trace_context(**self.previous)


def configure_logging(
    level: int = None,
    json_indent: Optional[int] = None,
    include_hostname: bool = True,
    include_process: bool = True,
) -> None:
    """
    Configure root logger with structured logging.
    
    Args:
        level: Log level (default: from LOG_LEVEL env var or INFO)
        json_indent: JSON indentation (None for compact)
        include_hostname: Include hostname in logs
        include_process: Include process info in logs
    """
    if level is None:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    formatter = StructuredFormatter(
        json_indent=json_indent,
        include_hostname=include_hostname,
        include_process=include_process,
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


# Convenience function for FastAPI middleware
def create_logging_middleware(logger: Optional[StructuredLogger] = None):
    """
    Create FastAPI middleware for request logging.
    
    Usage:
        from fastapi import FastAPI
        app = FastAPI()
        
        @app.middleware("http")
        async def logging_middleware(request, call_next):
            return await create_logging_middleware()(request, call_next)
    """
    log = logger or get_logger("http")
    
    async def middleware(request, call_next):
        import time
        
        # Generate trace IDs
        trace_id = request.headers.get("X-Trace-ID", generate_trace_id())
        span_id = generate_span_id()
        
        with LogContext(trace_id=trace_id, span_id=span_id):
            start_time = time.perf_counter()
            
            log.info(
                "Request started",
                method=request.method,
                path=request.url.path,
                client=request.client.host if request.client else None,
            )
            
            try:
                response = await call_next(request)
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                log.info(
                    "Request completed",
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                )
                
                # Add trace ID to response
                response.headers["X-Trace-ID"] = trace_id
                return response
                
            except Exception as e:
                duration_ms = (time.perf_counter() - start_time) * 1000
                log.error(
                    "Request failed",
                    method=request.method,
                    path=request.url.path,
                    duration_ms=round(duration_ms, 2),
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                raise
    
    return middleware


# Initialize logging on module import if configured
if os.getenv("STRUCTURED_LOGGING", "false").lower() == "true":
    configure_logging()
