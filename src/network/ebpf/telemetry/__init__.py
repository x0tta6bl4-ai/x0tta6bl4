"""
eBPF Telemetry Package.

Comprehensive telemetry collection system for eBPF programs.

Components:
- models: Data structures (TelemetryConfig, MetricDefinition, etc.)
- security: SecurityManager for validation and sanitization
- map_reader: MapReader for eBPF map access
- perf_reader: PerfBufferReader for event streaming
- prometheus_exporter: PrometheusExporter for metrics export
- collector: EBPFTelemetryCollector main class
"""

from .models import (
    MetricType,
    MapType,
    EventSeverity,
    TelemetryConfig,
    MetricDefinition,
    MapMetadata,
    TelemetryEvent,
    CollectionStats,
)
from .security import SecurityManager
from .map_reader import MapReader, BCC_AVAILABLE
from .perf_reader import PerfBufferReader
from .prometheus_exporter import PrometheusExporter, PROMETHEUS_AVAILABLE
from .collector import (
    EBPFTelemetryCollector,
    create_collector,
    quick_start,
)

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
    # Components
    "SecurityManager",
    "MapReader",
    "PerfBufferReader",
    "PrometheusExporter",
    # Main class
    "EBPFTelemetryCollector",
    # Convenience functions
    "create_collector",
    "quick_start",
    # Availability flags
    "BCC_AVAILABLE",
    "PROMETHEUS_AVAILABLE",
]

__version__ = "2.0.0"
