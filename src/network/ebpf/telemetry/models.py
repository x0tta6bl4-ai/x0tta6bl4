"""
Telemetry Data Models.

Data structures for eBPF telemetry collection.
"""
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List


class MetricType(Enum):
    """Type of metric."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MapType(Enum):
    """eBPF map types."""
    HASH = "hash"
    ARRAY = "array"
    PERCPU_ARRAY = "percpu_array"
    RINGBUF = "ringbuf"
    PERF_EVENT_ARRAY = "perf_event_array"
    LRU_HASH = "lru_hash"


class EventSeverity(Enum):
    """Severity level for security events."""
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


@dataclass
class TelemetryConfig:
    """Configuration for telemetry collector."""
    # Collection settings
    collection_interval: float = 1.0  # seconds
    batch_size: int = 100
    max_queue_size: int = 10000

    # Performance settings
    max_workers: int = 4
    read_timeout: float = 5.0  # seconds
    poll_timeout: int = 100  # milliseconds

    # Prometheus settings
    prometheus_port: int = 9090
    prometheus_host: str = "0.0.0.0"  # nosec B104

    # Security settings
    enable_validation: bool = True
    enable_sanitization: bool = True
    max_metric_value: float = 1e15
    sanitize_paths: bool = True

    # Error handling
    max_retries: int = 3
    retry_delay: float = 0.5  # seconds
    enable_fallback: bool = True

    # Logging
    log_level: str = "INFO"
    log_events: bool = False


@dataclass
class MetricDefinition:
    """Definition of a metric."""
    name: str
    type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    help_text: str = ""


@dataclass
class MapMetadata:
    """Metadata about an eBPF map."""
    name: str
    map_type: MapType
    key_size: int
    value_size: int
    max_entries: int
    program_name: str = ""
    description: str = ""


@dataclass
class TelemetryEvent:
    """Telemetry event from eBPF."""
    event_type: str
    timestamp_ns: int
    cpu_id: int
    pid: int = 0
    data: Dict[str, Any] = field(default_factory=dict)
    severity: EventSeverity = EventSeverity.INFO


@dataclass
class CollectionStats:
    """Statistics about metric collection."""
    total_collections: int = 0
    successful_collections: int = 0
    failed_collections: int = 0
    total_metrics_collected: int = 0
    total_events_processed: int = 0
    last_collection_time: float = 0.0
    average_collection_time: float = 0.0
    collection_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling deque."""
        result = asdict(self)
        result['collection_times'] = list(self.collection_times)
        return result
