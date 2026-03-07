"""
eBPF Metrics Exporter Package

A modular metrics export system for eBPF programs with:
- Prometheus integration with graceful degradation
- Metric validation and sanitization
- Retry logic with exponential backoff
- Structured logging with context
- Graceful shutdown handling

Example:
    >>> from src.network.ebpf.metrics import EBPFMetricsExporter
    >>> exporter = EBPFMetricsExporter(port=9090)
    >>> exporter.register_map("packet_counters", "xdp_counter")
    >>> metrics = exporter.export_metrics()

Modules:
    - models: Data structures (enums, dataclasses)
    - exceptions: Custom exception hierarchy
    - retry: Retry decorator with exponential backoff
    - sanitizer: Metric validation and sanitization
    - shutdown: Graceful shutdown handler
    - logging_utils: Structured logging wrapper
    - prometheus_exporter: Prometheus integration
    - exporter: Main EBPFMetricsExporter class
"""

from typing import Any

# Public API
__all__ = [
    # Main classes
    "EBPFMetricsExporter",
    "PrometheusExporter",
    "MetricSanitizer",
    "GracefulShutdown",
    "StructuredLogger",
    # Models
    "MetricValidationStatus",
    "MetricValidationResult",
    "ErrorCount",
    "RetryConfig",
    "DegradationLevel",
    "DegradationState",
    # Exceptions
    "EBPFMetricsError",
    "MapReadError",
    "BpftoolError",
    "PrometheusExportError",
    "MetricRegistrationError",
    "ParseError",
    "TimeoutError",
    # Utilities
    "with_retry",
    "PROMETHEUS_AVAILABLE",
]


def __getattr__(name: str) -> Any:
    """
    Lazy loading for memory efficiency.
    
    Modules are only imported when their contents are accessed,
    reducing initial memory footprint and import time.
    """
    # Main classes
    if name == "EBPFMetricsExporter":
        from .exporter import EBPFMetricsExporter
        return EBPFMetricsExporter
    
    if name == "PrometheusExporter":
        from .prometheus_exporter import PrometheusExporter
        return PrometheusExporter
    
    if name == "MetricSanitizer":
        from .sanitizer import MetricSanitizer
        return MetricSanitizer
    
    if name == "GracefulShutdown":
        from .shutdown import GracefulShutdown
        return GracefulShutdown
    
    if name == "StructuredLogger":
        from .logging_utils import StructuredLogger
        return StructuredLogger
    
    # Models
    if name in ("MetricValidationStatus", "MetricValidationResult", "ErrorCount",
                "RetryConfig", "DegradationLevel", "DegradationState"):
        from . import models
        return getattr(models, name)
    
    # Exceptions
    if name in ("EBPFMetricsError", "MapReadError", "BpftoolError",
                "PrometheusExportError", "MetricRegistrationError",
                "ParseError", "TimeoutError", "MetricsTimeoutError"):
        from . import exceptions
        return getattr(exceptions, name)
    
    # Utilities
    if name == "with_retry":
        from .retry import with_retry
        return with_retry
    
    if name == "PROMETHEUS_AVAILABLE":
        from .prometheus_exporter import PROMETHEUS_AVAILABLE
        return PROMETHEUS_AVAILABLE
    
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Package metadata
__version__ = "2.0.0"
__author__ = "MaaS Team"
