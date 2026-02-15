"""
Structured logging configuration for x0tta6bl4.

Provides:
- JSON-based structured logging
- Log levels configuration
- Multiple handlers (console, file, remote)
- Correlation IDs for request tracking
- Sensitive data masking
"""

import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, Optional

import structlog


@lru_cache
def get_log_level() -> str:
    """Get log level from environment"""
    return os.getenv("LOG_LEVEL", "INFO").upper()


def mask_sensitive_data(data: str) -> str:
    """Mask sensitive data in logs including passwords, tokens, secrets, and IP addresses"""
    patterns = [
        # Authentication credentials
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', "password=***"),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', "token=***"),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', "api_key=***"),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', "authorization=***"),
        (r'secret["\']?\s*[:=]\s*["\']?[^"\'\s]+', "secret=***"),
        (r'private[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', "private_key=***"),
        (r'passwd["\']?\s*[:=]\s*["\']?[^"\'\s]+', "passwd=***"),
        # IP address masking (preserve private ranges, mask public)
        (r"\b(\d{1,3}\.\d{1,3}\.\d{1,3})\.\d{1,3}\b", r"\1.***"),
        # Email masking
        (r"\b([a-zA-Z0-9._%+-])[^@]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b", r"\1***@\2"),
        # JWT tokens (three base64 parts separated by dots)
        (r"eyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*", "***JWT_TOKEN***"),
    ]

    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)

    return data


class StructuredJsonFormatter(logging.Formatter):
    """Format logs as structured JSON for ELK/Loki"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        extra_fields = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            ]
        }

        log_entry.update(extra_fields)

        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)

        return serialized


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )

        return True


def setup_logging(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.

    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port

    Returns:
        Configured logger instance
    """

    if log_level is None:
        log_level = get_log_level()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=100 * 1024 * 1024, backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)

    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                "x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s"
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")

    return logger


def setup_structlog():
    """Setup structlog for structured logging"""

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Get configured logger instance"""
    return logging.getLogger(name)


class RequestIdContextVar:
    """Store request ID in logging context"""

    _context = {}

    @classmethod
    def set(cls, request_id: str):
        """Set request ID for current context"""
        cls._context[id(cls)] = request_id

    @classmethod
    def get(cls) -> Optional[str]:
        """Get request ID from current context"""
        return cls._context.get(id(cls))

    @classmethod
    def clear(cls):
        """Clear request ID from context"""
        cls._context.pop(id(cls), None)


class LoggingMiddleware:
    """ASGI middleware for structured request/response logging"""

    def __init__(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = logger or get_logger("x0tta6bl4.http")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time
        import uuid

        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)

        path = scope.get("path", "")
        method = scope.get("method", "")

        start_time = time.time()
        status_code = 200

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

        except Exception as e:
            status_code = 500
            raise

        finally:
            duration_ms = (time.time() - start_time) * 1000

            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                },
            )

            RequestIdContextVar.clear()


# Application startup
if __name__ == "__main__":
    setup_structlog()
    logger = setup_logging("x0tta6bl4", log_file="/var/log/x0tta6bl4/app.log")

    logger.info("Logging configured")
    logger.debug("Debug message")
    logger.warning("Password=secret123 should be masked")
    logger.error("Error with token=abc123def456")
