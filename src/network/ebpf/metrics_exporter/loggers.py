"""Structured logging for eBPF metrics."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict




class StructuredLogger:
    """Wrapper for structured logging with context"""

    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs):
        """Set persistent context for all log messages"""
        self._context.update(kwargs)

    def clear_context(self):
        """Clear persistent context"""
        self._context.clear()

    def _format_extra(self, extra: Optional[Dict] = None) -> Dict:
        """Combine persistent context with extra data"""
        result = self._context.copy()
        if extra:
            result.update(extra)
        return result

    def debug(self, msg: str, **extra):
        self.logger.debug(msg, extra=self._format_extra(extra))

    def info(self, msg: str, **extra):
        self.logger.info(msg, extra=self._format_extra(extra))

    def warning(self, msg: str, **extra):
        self.logger.warning(msg, extra=self._format_extra(extra))

    def error(self, msg: str, error: Optional[Exception] = None, **extra):
        if error:
            extra["error_type"] = type(error).__name__
            extra["error_message"] = str(error)
            if isinstance(error, EBPFMetricsError):
                extra["error_context"] = error.context
        self.logger.error(msg, extra=self._format_extra(extra))

    def critical(self, msg: str, error: Optional[Exception] = None, **extra):
        if error:
            extra["error_type"] = type(error).__name__
            extra["error_message"] = str(error)
        self.logger.critical(msg, extra=self._format_extra(extra))


# ==================== Prometheus Integration ====================

try:
    from prometheus_client import (REGISTRY, Counter, Gauge, Histogram,
                                   start_http_server)

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    Gauge = None
    Counter = None
    Histogram = None


