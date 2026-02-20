"""
eBPF Telemetry Package for x0tta6bl4
=====================================

Comprehensive telemetry collection system for eBPF programs with:
- High-performance map reading
- Perf buffer event processing
- Prometheus metrics export
- Advanced error handling
- Security hardening

Usage:
    from src.network.ebpf.telemetry import (
        EBPFTelemetryCollector,
        TelemetryConfig,
        create_collector,
        quick_start,
    )

    # Quick start
    collector = create_collector(prometheus_port=9090)
    collector.register_program(bpf_program, "performance_monitor")
    collector.start()

    # Or with custom config
    config = TelemetryConfig(
        collection_interval=2.0,
        prometheus_port=9091,
        enable_validation=True,
    )
    collector = EBPFTelemetryCollector(config)
"""

import importlib.util
import sys

# Import models
from .models import (
    CollectionStats,
    EventSeverity,
    MapMetadata,
    MapType,
    MetricDefinition,
    MetricType,
    TelemetryConfig,
    TelemetryEvent,
)

# Import security
from .security import SecurityManager


def _module_available(module_name: str) -> bool:
    """Return True when module is available, including test-injected stubs."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ValueError):
        return module_name in sys.modules


# Check for optional dependencies
BCC_AVAILABLE = _module_available("bcc")
PROMETHEUS_AVAILABLE = _module_available("prometheus_client")

# Lazy imports for heavy modules
_map_reader = None
_perf_reader = None
_prometheus_exporter = None
_collector = None


def _get_map_reader():
    """Lazy import MapReader."""
    global _map_reader
    if _map_reader is None:
        from .map_reader import MapReader

        _map_reader = MapReader
    return _map_reader


def _get_perf_reader():
    """Lazy import PerfBufferReader."""
    global _perf_reader
    if _perf_reader is None:
        from .perf_reader import PerfBufferReader

        _perf_reader = PerfBufferReader
    return _perf_reader


def _get_prometheus_exporter():
    """Lazy import PrometheusExporter."""
    global _prometheus_exporter
    if _prometheus_exporter is None:
        from .prometheus_exporter import PrometheusExporter

        _prometheus_exporter = PrometheusExporter
    return _prometheus_exporter


def _get_collector():
    """Lazy import EBPFTelemetryCollector."""
    global _collector
    if _collector is None:
        from .collector import EBPFTelemetryCollector

        _collector = EBPFTelemetryCollector
    return _collector


# Create proxy classes for lazy loading
class MapReaderProxy:
    """Proxy for MapReader with lazy loading."""

    def __new__(cls, *args, **kwargs):
        return _get_map_reader()(*args, **kwargs)


class PerfBufferReaderProxy:
    """Proxy for PerfBufferReader with lazy loading."""

    def __new__(cls, *args, **kwargs):
        return _get_perf_reader()(*args, **kwargs)


class PrometheusExporterProxy:
    """Proxy for PrometheusExporter with lazy loading."""

    def __new__(cls, *args, **kwargs):
        return _get_prometheus_exporter()(*args, **kwargs)


class EBPFTelemetryCollectorProxy:
    """Proxy for EBPFTelemetryCollector with lazy loading."""

    def __new__(cls, *args, **kwargs):
        return _get_collector()(*args, **kwargs)


# Public aliases backed by lazy proxies
MapReader = MapReaderProxy
PerfBufferReader = PerfBufferReaderProxy
PrometheusExporter = PrometheusExporterProxy
EBPFTelemetryCollector = EBPFTelemetryCollectorProxy


# Convenience functions
def create_collector(
    prometheus_port: int = 9090, collection_interval: float = 1.0
) -> "EBPFTelemetryCollector":
    """
    Create a telemetry collector with default settings.

    Args:
        prometheus_port: Prometheus HTTP server port
        collection_interval: Metric collection interval in seconds

    Returns:
        EBPFTelemetryCollector instance
    """
    config = TelemetryConfig(
        prometheus_port=prometheus_port, collection_interval=collection_interval
    )
    return _get_collector()(config)


def quick_start(
    bpf_program, program_name: str, prometheus_port: int = 9090
) -> "EBPFTelemetryCollector":
    """
    Quick start telemetry collection for a single eBPF program.

    Args:
        bpf_program: BCC BPF program instance
        program_name: Name of the program
        prometheus_port: Prometheus HTTP server port

    Returns:
        EBPFTelemetryCollector instance
    """
    collector = create_collector(prometheus_port)
    collector.register_program(bpf_program, program_name)
    collector.start()
    return collector


__all__ = [
    # Models
    "MetricType",
    "MapType",
    "EventSeverity",
    "TelemetryConfig",
    "MetricDefinition",
    "MapMetadata",
    "TelemetryEvent",
    "CollectionStats",
    # Security
    "SecurityManager",
    # Components (lazy-loaded aliases)
    "MapReader",
    "PerfBufferReader",
    "PrometheusExporter",
    "EBPFTelemetryCollector",
    # Convenience
    "create_collector",
    "quick_start",
    # Feature flags
    "BCC_AVAILABLE",
    "PROMETHEUS_AVAILABLE",
]

__version__ = "3.2.1"
