"""
eBPF Telemetry Module for x0tta6bl4
=====================================

Comprehensive telemetry collection system for eBPF programs with:
- High-performance map reading
- Perf buffer event processing
- Prometheus metrics export
- Advanced error handling
- Security hardening

Architecture:
--------------
Kernel Space (eBPF):
┌─────────────────────────────────────────────────────────────┐
│  eBPF Programs (performance_monitor, network_monitor, etc.) │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Tracepoints│  │  Kprobes    │  │  TC Hooks   │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         ▼                ▼                ▼                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  eBPF Maps (HASH, ARRAY, PERCPU_ARRAY, RINGBUF)    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ bpf() syscall / perf events
                            ▼
User Space (Python):
┌─────────────────────────────────────────────────────────────┐
│  EBPFTelemetryCollector                                     │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MapReader (bpftool, BCC, direct syscalls)          │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PerfBufferReader (high-throughput event stream)    │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  MetricsAggregator (normalization, aggregation)     │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  PrometheusExporter (HTTP endpoint)                 │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SecurityManager (validation, sanitization)         │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    Prometheus / Grafana

Date: February 2, 2026
Version: 2.0
Author: Senior Systems Engineer
"""

import hashlib
import json
import logging
import os
import struct
import subprocess
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.core.agent_thinking import AgentThinkingCoach
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_TELEMETRY_MODULE_SERVICE_NAME = "ebpf-telemetry-module"
EBPF_TELEMETRY_MODULE_LAYER = "network_ebpf_telemetry_module_observed_state"
EBPF_TELEMETRY_MODULE_CLAIM_BOUNDARY = (
    "Local legacy eBPF telemetry module evidence only. Events record BCC map "
    "reads, bpftool availability/read attempts, cache hits, multi-map summaries, "
    "and bounded output metadata with hashed map/command/result selectors; they "
    "do not prove that eBPF programs are attached, kernel maps contain production "
    "traffic, or collected values are customer-path truth."
)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return _sha256_text(str(value))


def _bounded_hashes(values: List[Any], limit: int = 20) -> Dict[str, Any]:
    selected = values[:limit]
    return {
        "hashes": [_hash_value(value) for value in selected],
        "count": len(values),
        "limit": limit,
        "truncated": len(values) > limit,
    }


def _output_metadata(value: Any, limit: int = 512) -> Dict[str, Any]:
    text = "" if value is None else str(value)
    encoded = text.encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest() if encoded else None,
        "sample_limit": limit,
        "sample_redacted": True,
        "truncated": len(encoded) > limit,
    }


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_TELEMETRY_MODULE_SERVICE_NAME)
    return {
        "service_name": EBPF_TELEMETRY_MODULE_SERVICE_NAME,
        "layer": EBPF_TELEMETRY_MODULE_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }

# Try to import BCC
BCC_AVAILABLE = False
try:
    from bcc import BPF, PerfSWConfig, PerfType

    BCC_AVAILABLE = True
    logger.info("✅ BCC available - full eBPF support")
except ImportError:
    BCC_AVAILABLE = False
    logger.warning("⚠️ BCC not available - using fallback methods")

# Try to import prometheus_client
PROMETHEUS_AVAILABLE = False
try:
    from prometheus_client import (CollectorRegistry, Counter, Gauge,
                                   Histogram, Summary, generate_latest,
                                   start_http_server)

    PROMETHEUS_AVAILABLE = True
    logger.info("✅ Prometheus client available")
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("⚠️ Prometheus client not available - metrics export limited")


# ============================================================================
# Data Structures
# ============================================================================


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


# ============================================================================
# Security and Validation
# ============================================================================


class SecurityManager:
    """
    Manages security aspects of telemetry collection.

    Responsibilities:
    - Input validation
    - Data sanitization
    - Path traversal prevention
    - Resource limits enforcement
    """

    def __init__(self, config: TelemetryConfig):
        self.config = config
        self.validation_errors: List[str] = []
        self.sanitized_count = 0

        # Blocked patterns for security
        self.blocked_patterns = [
            "../",
            "..\\",  # Path traversal
            "/proc/",
            "/sys/",  # Sensitive paths
            "\x00",  # Null bytes
        ]

        # Allowed metric name patterns
        self.allowed_metric_chars = set(
            "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789_:"
        )

        logger.info("SecurityManager initialized")

    def validate_metric_name(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate metric name for security.

        Args:
            name: Metric name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            return False, "Metric name cannot be empty"

        if len(name) > 200:
            return False, f"Metric name too long: {len(name)} > 200"

        # Check for valid characters
        for char in name:
            if char not in self.allowed_metric_chars:
                return False, f"Invalid character in metric name: {char}"

        # Check for reserved prefixes
        if name.startswith("__"):
            return False, "Metric name cannot start with '__'"

        return True, None

    def validate_metric_value(self, value: Any) -> Tuple[bool, Optional[str]]:
        """
        Validate metric value.

        Args:
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            return False, "Metric value cannot be None"

        # Check type
        if not isinstance(value, (int, float)):
            return False, f"Invalid metric type: {type(value)}"

        # Check for NaN/Inf
        if isinstance(value, float):
            if value != value:  # NaN check
                return False, "Metric value cannot be NaN"
            if abs(value) == float("inf"):
                return False, "Metric value cannot be infinite"

        # Check range
        if abs(value) > self.config.max_metric_value:
            return (
                False,
                f"Metric value exceeds maximum: {value} > {self.config.max_metric_value}",
            )

        return True, None

    def sanitize_string(self, s: str) -> str:
        """
        Sanitize string input.

        Args:
            s: String to sanitize

        Returns:
            Sanitized string
        """
        if not isinstance(s, str):
            return ""

        # Remove null bytes
        s = s.replace("\x00", "")

        # Limit length
        if len(s) > 1000:
            s = s[:1000]

        # Remove blocked patterns
        for pattern in self.blocked_patterns:
            s = s.replace(pattern, "")

        self.sanitized_count += 1
        return s

    def sanitize_path(self, path: str) -> str:
        """
        Sanitize file path to prevent traversal.

        Args:
            path: Path to sanitize

        Returns:
            Sanitized path
        """
        if not self.config.sanitize_paths:
            return path

        # Remove path traversal attempts
        path = path.replace("../", "").replace("..\\", "")

        # Ensure path doesn't start with /
        if path.startswith("/"):
            path = path[1:]

        # Limit to basename only
        path = os.path.basename(path)

        return path

    def validate_event(self, event: TelemetryEvent) -> Tuple[bool, Optional[str]]:
        """
        Validate telemetry event.

        Args:
            event: Event to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate event type
        if not event.event_type or not isinstance(event.event_type, str):
            return False, "Invalid event type"

        # Validate timestamp
        if event.timestamp_ns <= 0:
            return False, "Invalid timestamp"

        # Validate CPU ID
        if event.cpu_id < 0 or event.cpu_id > 255:
            return False, f"Invalid CPU ID: {event.cpu_id}"

        # Validate PID
        if event.pid < 0 or event.pid > 4194304:  # Max PID on Linux
            return False, f"Invalid PID: {event.pid}"

        # Validate severity
        if not isinstance(event.severity, EventSeverity):
            return False, "Invalid severity"

        return True, None

    def get_stats(self) -> Dict[str, Any]:
        """Get security statistics."""
        return {
            "validation_errors": len(self.validation_errors),
            "sanitized_count": self.sanitized_count,
            "config": {
                "enable_validation": self.config.enable_validation,
                "enable_sanitization": self.config.enable_sanitization,
                "max_metric_value": self.config.max_metric_value,
            },
        }


# ============================================================================
# Map Reader
# ============================================================================


class MapReader:
    """
    High-performance reader for eBPF maps.

    Supports multiple backends:
    1. BCC Python bindings (preferred)
    2. bpftool CLI (fallback)
    3. Direct syscalls (future)

    Optimizations:
    - Batch reading
    - Parallel processing
    - Caching
    - Zero-copy where possible
    """

    def __init__(
        self,
        config: TelemetryConfig,
        security: SecurityManager,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.config = config
        self.security = security
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = EBPF_TELEMETRY_MODULE_SERVICE_NAME
        self.thinking_coach = AgentThinkingCoach(
            agent_id=self.source_agent,
            role="monitoring",
            capabilities=("security", "zero-trust"),
            extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None
        self._thinking_lock = threading.Lock()
        self.bpftool_available = self._check_bpftool()
        self.cache: Dict[str, Tuple[float, Any]] = {}
        self.cache_ttl = 0.5  # seconds

        logger.info(f"MapReader initialized (bpftool={self.bpftool_available})")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        return self.event_bus

    def _thinking_coach_or_create(self) -> AgentThinkingCoach:
        coach = getattr(self, "thinking_coach", None)
        if coach is None:
            self.source_agent = getattr(
                self,
                "source_agent",
                EBPF_TELEMETRY_MODULE_SERVICE_NAME,
            )
            coach = AgentThinkingCoach(
                agent_id=self.source_agent,
                role="monitoring",
                capabilities=("security", "zero-trust"),
                extra_techniques=("mape_k", "causal_analysis", "reverse_planning"),
            )
            self.thinking_coach = coach
        return coach

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_telemetry_map_reader_operation",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Record only local eBPF telemetry map-reader evidence, command "
                "shapes, hashes, counts, and status; do not expose raw map names, "
                "map keys, map values, stdout, stderr, or BCC objects."
            ),
        }
        lock = getattr(self, "_thinking_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._thinking_lock = lock
        with lock:
            self._last_thinking_context = self._thinking_coach_or_create().prepare_task(
                safe_task
            )
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose telemetry map-reader thinking state without task secrets."""

        return {
            **self._thinking_coach_or_create().status(),
            "last_context": getattr(self, "_last_thinking_context", None),
        }

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        returncode: Optional[int] = None,
        parsed_summary: Optional[Dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        thinking = self._record_thinking_context(
            operation=operation,
            goal=f"{operation}:{stage}:{status}",
            constraints={
                "stage": stage,
                "status": status,
                "source_mode": source_mode,
                "read_only": True,
                "returncode_present": returncode is not None,
                "parsed_summary_keys": sorted((parsed_summary or {}).keys()),
                "extra_keys": sorted((extra or {}).keys()),
            },
        )
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.telemetry_module",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:ebpf:telemetry_module:{operation}",
            "service_name": self.source_agent,
            "layer": EBPF_TELEMETRY_MODULE_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": True,
            "observed_state": True,
            "safe_observation": True,
            "safe_actuator": False,
            "payloads_redacted": True,
            "parsed_summary": parsed_summary or {},
            "thinking": thinking,
            "claim_boundary": EBPF_TELEMETRY_MODULE_CLAIM_BOUNDARY,
        }
        if error is not None:
            payload["error"] = {
                "type": type(error).__name__,
                "message_hash": _hash_value(str(error)),
                "message_redacted": True,
            }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                self.source_agent,
                payload,
                priority=5,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish telemetry module observation")
            return None

    def _map_selector_metadata(self, map_name: str) -> Dict[str, Any]:
        return {
            "map_name_hash": _hash_value(map_name),
            "map_name_redacted": True,
        }

    def _result_selector_metadata(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "result_key_hashes": _bounded_hashes(list(data.keys())),
            "result_selectors_redacted": True,
        }

    def _result_selector_metadata_from_any(self, data: Any) -> Dict[str, Any]:
        if isinstance(data, dict):
            return self._result_selector_metadata(data)
        return {"result_selectors_redacted": True}

    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        op_start = time.monotonic()
        command_shape = ["bpftool", "--version"]
        try:
            result = subprocess.run(
                command_shape, capture_output=True, timeout=2
            )
            available = result.returncode == 0
            self._publish_observation(
                stage="telemetry_bpftool_probe_completed",
                operation="check_bpftool",
                status="success" if available else "failure",
                source_mode="subprocess",
                start=op_start,
                returncode=result.returncode,
                parsed_summary={"bpftool_available": available},
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                    "stdout_metadata": _output_metadata(
                        getattr(result, "stdout", None)
                    ),
                    "stderr_metadata": _output_metadata(
                        getattr(result, "stderr", None)
                    ),
                },
            )
            return available
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="telemetry_bpftool_probe_timeout",
                operation="check_bpftool",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=124,
                error=exc,
                parsed_summary={"bpftool_available": False},
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                },
            )
            return False
        except FileNotFoundError as exc:
            self._publish_observation(
                stage="telemetry_bpftool_probe_missing",
                operation="check_bpftool",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=127,
                error=exc,
                parsed_summary={"bpftool_available": False},
                extra={
                    "command_shape": command_shape,
                    "command_hash": _hash_value(" ".join(command_shape)),
                },
            )
            return False

    def read_map_via_bcc(self, bpf_program: Any, map_name: str) -> Dict[str, Any]:
        """
        Read eBPF map using BCC.

        Args:
            bpf_program: BCC BPF program instance
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        op_start = time.monotonic()
        if not BCC_AVAILABLE:
            self._publish_observation(
                stage="telemetry_bcc_map_read_unavailable",
                operation="read_map_via_bcc",
                status="failure",
                source_mode="bcc",
                start=op_start,
                returncode=1,
                error=RuntimeError("BCC not available"),
                parsed_summary={"bcc_available": False, "result_count": 0},
                extra=self._map_selector_metadata(map_name),
            )
            raise RuntimeError("BCC not available")

        try:
            table = bpf_program[map_name]
            result = {}

            for key, value in table.items():
                # Convert key to string
                if isinstance(key, (bytes, bytearray)):
                    key_str = key.decode("utf-8", errors="replace").rstrip("\x00")
                else:
                    key_str = str(key)

                # Convert value
                if hasattr(value, "__dict__"):
                    # Struct value
                    value_dict = {}
                    for field_name, field_value in value.__dict__.items():
                        if isinstance(field_value, (bytes, bytearray)):
                            field_value = field_value.decode(
                                "utf-8", errors="replace"
                            ).rstrip("\x00")
                        value_dict[field_name] = field_value
                    result[key_str] = value_dict
                else:
                    result[key_str] = value

            self._publish_observation(
                stage="telemetry_bcc_map_read_completed",
                operation="read_map_via_bcc",
                status="success",
                source_mode="bcc",
                start=op_start,
                returncode=0,
                parsed_summary={
                    "bcc_available": True,
                    "result_count": len(result),
                    "bpf_program_present": bpf_program is not None,
                },
                extra={
                    **self._map_selector_metadata(map_name),
                    **self._result_selector_metadata(result),
                },
            )
            return result

        except Exception as e:
            self._publish_observation(
                stage="telemetry_bcc_map_read_failed",
                operation="read_map_via_bcc",
                status="failure",
                source_mode="bcc",
                start=op_start,
                returncode=1,
                error=e,
                parsed_summary={
                    "bcc_available": True,
                    "result_count": 0,
                    "bpf_program_present": bpf_program is not None,
                },
                extra=self._map_selector_metadata(map_name),
            )
            logger.error("Error reading map via BCC: %s", type(e).__name__)
            raise

    def read_map_via_bpftool(self, map_name: str) -> Dict[str, Any]:
        """
        Read eBPF map using bpftool.

        Args:
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        op_start = time.monotonic()
        command_shape = ["bpftool", "map", "dump", "name", "<map_name>", "--json"]
        command_hash = _hash_value(" ".join(command_shape))
        try:
            result = subprocess.run(
                ["bpftool", "map", "dump", "name", map_name, "--json"],
                capture_output=True,
                text=True,
                timeout=self.config.read_timeout,
            )

        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage="telemetry_bpftool_map_read_timeout",
                operation="read_map_via_bpftool",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=124,
                error=exc,
                parsed_summary={"result_count": 0, "timeout": self.config.read_timeout},
                extra={
                    **self._map_selector_metadata(map_name),
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                },
            )
            raise RuntimeError("bpftool timeout reading map") from exc
        except Exception as e:
            self._publish_observation(
                stage="telemetry_bpftool_map_read_subprocess_failed",
                operation="read_map_via_bpftool",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=1,
                error=e,
                parsed_summary={"result_count": 0},
                extra={
                    **self._map_selector_metadata(map_name),
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                },
            )
            logger.error("Error executing bpftool map read: %s", type(e).__name__)
            raise RuntimeError("bpftool execution failed") from e

        stdout_metadata = _output_metadata(getattr(result, "stdout", None))
        stderr_metadata = _output_metadata(getattr(result, "stderr", None))
        if result.returncode != 0:
            self._publish_observation(
                stage="telemetry_bpftool_map_read_failed",
                operation="read_map_via_bpftool",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=result.returncode,
                parsed_summary={"result_count": 0},
                extra={
                    **self._map_selector_metadata(map_name),
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                    "stdout_metadata": stdout_metadata,
                    "stderr_metadata": stderr_metadata,
                },
            )
            raise RuntimeError("bpftool failed")

        try:
            data = json.loads(result.stdout)
        except Exception as exc:
            self._publish_observation(
                stage="telemetry_bpftool_map_parse_failed",
                operation="read_map_via_bpftool",
                status="failure",
                source_mode="subprocess",
                start=op_start,
                returncode=result.returncode,
                error=exc,
                parsed_summary={"result_count": 0},
                extra={
                    **self._map_selector_metadata(map_name),
                    "command_shape": command_shape,
                    "command_hash": command_hash,
                    "stdout_metadata": stdout_metadata,
                    "stderr_metadata": stderr_metadata,
                },
            )
            logger.error("Error parsing bpftool map output: %s", type(exc).__name__)
            raise

        # Parse map data
        parsed = {}
        raw_entries_count = 0
        if isinstance(data, dict) and "data" in data:
            raw_entries = data["data"] if isinstance(data["data"], list) else []
            raw_entries_count = len(raw_entries)
            for entry in raw_entries:
                key = entry.get("key")
                value = entry.get("value")

                # Convert key to string
                if isinstance(key, list):
                    key_str = "_".join(str(k) for k in key)
                else:
                    key_str = str(key)

                parsed[key_str] = value

        self._publish_observation(
            stage="telemetry_bpftool_map_read_completed",
            operation="read_map_via_bpftool",
            status="success",
            source_mode="subprocess",
            start=op_start,
            returncode=result.returncode,
            parsed_summary={
                "result_count": len(parsed),
                "raw_entries_count": raw_entries_count,
            },
            extra={
                **self._map_selector_metadata(map_name),
                **self._result_selector_metadata(parsed),
                "command_shape": command_shape,
                "command_hash": command_hash,
                "stdout_metadata": stdout_metadata,
                "stderr_metadata": stderr_metadata,
            },
        )
        return parsed

    def read_map(
        self, bpf_program: Optional[Any], map_name: str, use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Read eBPF map with automatic backend selection.

        Args:
            bpf_program: BCC BPF program instance (optional)
            map_name: Name of the map
            use_cache: Whether to use cached data

        Returns:
            Dictionary with map data
        """
        op_start = time.monotonic()
        bcc_error: Optional[Exception] = None
        bpftool_error: Optional[Exception] = None

        # Check cache
        if use_cache and map_name in self.cache:
            cached_time, cached_data = self.cache[map_name]
            if time.time() - cached_time < self.cache_ttl:
                self._publish_observation(
                    stage="telemetry_map_read_cache_hit",
                    operation="read_map",
                    status="success",
                    source_mode="cache",
                    start=op_start,
                    returncode=0,
                    parsed_summary={
                        "backend": "cache",
                        "result_count": len(cached_data)
                        if hasattr(cached_data, "__len__")
                        else 0,
                        "use_cache": use_cache,
                        "bpf_program_present": bpf_program is not None,
                    },
                    extra={
                        **self._map_selector_metadata(map_name),
                        **self._result_selector_metadata_from_any(cached_data),
                    },
                )
                return cached_data

        # Try BCC first
        if bpf_program and BCC_AVAILABLE:
            try:
                data = self.read_map_via_bcc(bpf_program, map_name)
                self.cache[map_name] = (time.time(), data)
                self._publish_observation(
                    stage="telemetry_map_read_completed",
                    operation="read_map",
                    status="success",
                    source_mode="bcc",
                    start=op_start,
                    returncode=0,
                    parsed_summary={
                        "backend": "bcc",
                        "result_count": len(data),
                        "use_cache": use_cache,
                        "bpf_program_present": True,
                    },
                    extra={
                        **self._map_selector_metadata(map_name),
                        **self._result_selector_metadata(data),
                    },
                )
                return data
            except Exception as e:
                bcc_error = e
                logger.warning(
                    "BCC map read failed, trying bpftool: %s", type(e).__name__
                )

        # Fallback to bpftool
        if self.bpftool_available:
            try:
                data = self.read_map_via_bpftool(map_name)
                self.cache[map_name] = (time.time(), data)
                self._publish_observation(
                    stage="telemetry_map_read_completed",
                    operation="read_map",
                    status="success",
                    source_mode="bpftool",
                    start=op_start,
                    returncode=0,
                    parsed_summary={
                        "backend": "bpftool",
                        "result_count": len(data),
                        "use_cache": use_cache,
                        "bpf_program_present": bpf_program is not None,
                        "bcc_failed_first": bcc_error is not None,
                    },
                    extra={
                        **self._map_selector_metadata(map_name),
                        **self._result_selector_metadata(data),
                        "bcc_error": {
                            "type": type(bcc_error).__name__,
                            "message_hash": _hash_value(str(bcc_error)),
                            "message_redacted": True,
                        }
                        if bcc_error is not None
                        else None,
                    },
                )
                return data
            except Exception as e:
                bpftool_error = e
                logger.error("bpftool map read failed: %s", type(e).__name__)
                self._publish_observation(
                    stage="telemetry_map_read_backend_failed",
                    operation="read_map",
                    status="failure",
                    source_mode="bpftool",
                    start=op_start,
                    returncode=1,
                    error=e,
                    parsed_summary={
                        "backend": "bpftool",
                        "result_count": 0,
                        "use_cache": use_cache,
                        "bpf_program_present": bpf_program is not None,
                        "bcc_failed_first": bcc_error is not None,
                    },
                    extra={
                        **self._map_selector_metadata(map_name),
                        "bcc_error": {
                            "type": type(bcc_error).__name__,
                            "message_hash": _hash_value(str(bcc_error)),
                            "message_redacted": True,
                        }
                        if bcc_error is not None
                        else None,
                    },
                )

        # Return empty dict if all methods fail
        logger.error("All methods failed to read map")
        self._publish_observation(
            stage="telemetry_map_read_empty",
            operation="read_map",
            status="empty",
            source_mode="none",
            start=op_start,
            returncode=1,
            parsed_summary={
                "backend": "none",
                "result_count": 0,
                "use_cache": use_cache,
                "bpf_program_present": bpf_program is not None,
                "bcc_available": BCC_AVAILABLE,
                "bpftool_available": self.bpftool_available,
            },
            extra={
                **self._map_selector_metadata(map_name),
                "bcc_error": {
                    "type": type(bcc_error).__name__,
                    "message_hash": _hash_value(str(bcc_error)),
                    "message_redacted": True,
                }
                if bcc_error is not None
                else None,
                "bpftool_error": {
                    "type": type(bpftool_error).__name__,
                    "message_hash": _hash_value(str(bpftool_error)),
                    "message_redacted": True,
                }
                if bpftool_error is not None
                else None,
            },
        )
        return {}

    def read_multiple_maps(
        self, bpf_program: Optional[Any], map_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Read multiple maps in parallel.

        Args:
            bpf_program: BCC BPF program instance (optional)
            map_names: List of map names

        Returns:
            Dictionary mapping map names to their data
        """
        op_start = time.monotonic()
        results = {}

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_map = {
                executor.submit(self.read_map, bpf_program, map_name): map_name
                for map_name in map_names
            }

            for future in as_completed(future_to_map):
                map_name = future_to_map[future]
                try:
                    results[map_name] = future.result()
                except Exception as e:
                    logger.error("Error reading map in batch: %s", type(e).__name__)
                    results[map_name] = {}

        self._publish_observation(
            stage="telemetry_multiple_maps_read_completed",
            operation="read_multiple_maps",
            status="success",
            source_mode="mixed",
            start=op_start,
            returncode=0,
            parsed_summary={
                "maps_requested": len(map_names),
                "maps_returned": len(results),
                "empty_results": sum(1 for data in results.values() if not data),
                "bpf_program_present": bpf_program is not None,
            },
            extra={
                "map_name_hashes": _bounded_hashes(map_names),
                "map_names_redacted": True,
            },
        )
        return results

    def clear_cache(self):
        """Clear the map cache."""
        self.cache.clear()


# ============================================================================
# Perf Buffer Reader
# ============================================================================


class PerfBufferReader:
    """
    High-throughput reader for eBPF perf buffer events.

    Features:
    - Non-blocking event processing
    - Event batching
    - Custom event handlers
    - Thread-safe queue
    """

    def __init__(self, config: TelemetryConfig, security: SecurityManager):
        self.config = config
        self.security = security
        self.running = False
        self.event_queue: deque = deque(maxlen=config.max_queue_size)
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "parse_errors": 0,
        }

        logger.info("PerfBufferReader initialized")

    def register_handler(
        self, event_type: str, handler: Callable[[TelemetryEvent], None]
    ):
        """
        Register event handler.

        Args:
            event_type: Type of event to handle
            handler: Callback function
        """
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")

    def start_reading(self, bpf_program: Any, map_name: str):
        """
        Start reading perf buffer events.

        Args:
            bpf_program: BCC BPF program instance
            map_name: Name of the perf buffer map
        """
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, cannot read perf buffer")
            return

        self.running = True

        def handle_event(cpu, data, size):
            """Handle perf buffer event."""
            try:
                # Parse event header
                if size < 16:
                    self.stats["parse_errors"] += 1
                    return

                # Parse event (simplified - real implementation would match C struct)
                event_type = struct.unpack("I", data[0:4])[0]
                timestamp_ns = struct.unpack("Q", data[4:12])[0]
                cpu_id = struct.unpack("I", data[12:16])[0]

                # Create telemetry event
                event = TelemetryEvent(
                    event_type=f"event_{event_type}",
                    timestamp_ns=timestamp_ns,
                    cpu_id=cpu_id,
                    data={"raw_size": size},
                )

                # Validate event
                is_valid, error = self.security.validate_event(event)
                if not is_valid:
                    logger.warning(f"Invalid event: {error}")
                    return

                # Add to queue
                if len(self.event_queue) >= self.event_queue.maxlen:
                    self.stats["events_dropped"] += 1

                self.event_queue.append(event)
                self.stats["events_received"] += 1

            except Exception as e:
                logger.error(f"Error handling perf event: {e}")
                self.stats["parse_errors"] += 1

        try:
            # Open perf buffer
            bpf_program[map_name].open_perf_buffer(handle_event)

            logger.info(f"Started reading perf buffer: {map_name}")

            # Poll loop
            while self.running:
                bpf_program.perf_buffer_poll(timeout=self.config.poll_timeout)

                # Process queued events
                self._process_events()

        except Exception as e:
            logger.error(f"Error reading perf buffer: {e}")
        finally:
            self.running = False

    def _process_events(self):
        """Process queued events."""
        while self.event_queue:
            event = self.event_queue.popleft()

            # Call registered handlers
            handlers = self.event_handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                    self.stats["events_processed"] += 1
                except Exception as e:
                    logger.error(f"Event handler error: {e}")

    def stop_reading(self):
        """Stop reading perf buffer events."""
        self.running = False
        logger.info("Stopped reading perf buffer")

    def get_stats(self) -> Dict[str, Any]:
        """Get reader statistics."""
        return self.stats.copy()


# ============================================================================
# Prometheus Exporter
# ============================================================================


class PrometheusExporter:
    """
    Export metrics to Prometheus format.

    Features:
    - Automatic metric type detection
    - Label support
    - Histogram buckets
    - HTTP endpoint
    """

    def __init__(self, config: TelemetryConfig, security: SecurityManager):
        self.config = config
        self.security = security
        self.metrics: Dict[str, Any] = {}
        self.metric_definitions: Dict[str, MetricDefinition] = {}
        self.registry = CollectorRegistry()
        self.server_started = False

        if PROMETHEUS_AVAILABLE:
            logger.info("PrometheusExporter initialized")
        else:
            logger.warning("Prometheus client not available")

    def start_server(self):
        """Start Prometheus HTTP server."""
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Cannot start Prometheus server - client not available")
            return

        if self.server_started:
            logger.warning("Prometheus server already started")
            return

        try:
            start_http_server(
                port=self.config.prometheus_port,
                addr=self.config.prometheus_host,
                registry=self.registry,
            )
            self.server_started = True
            logger.info(
                f"Prometheus server started on {self.config.prometheus_host}:{self.config.prometheus_port}"
            )
        except Exception as e:
            logger.error(f"Failed to start Prometheus server: {e}")

    def register_metric(self, definition: MetricDefinition):
        """
        Register a metric definition.

        Args:
            definition: MetricDefinition object
        """
        # Validate metric name
        is_valid, error = self.security.validate_metric_name(definition.name)
        if not is_valid:
            logger.error(f"Invalid metric name {definition.name}: {error}")
            return

        self.metric_definitions[definition.name] = definition

        if PROMETHEUS_AVAILABLE:
            try:
                if definition.type == MetricType.COUNTER:
                    metric = Counter(
                        definition.name,
                        definition.description or definition.help_text,
                        definition.labels,
                        registry=self.registry,
                    )
                elif definition.type == MetricType.GAUGE:
                    metric = Gauge(
                        definition.name,
                        definition.description or definition.help_text,
                        definition.labels,
                        registry=self.registry,
                    )
                elif definition.type == MetricType.HISTOGRAM:
                    metric = Histogram(
                        definition.name,
                        definition.description or definition.help_text,
                        definition.labels,
                        registry=self.registry,
                    )
                elif definition.type == MetricType.SUMMARY:
                    metric = Summary(
                        definition.name,
                        definition.description or definition.help_text,
                        definition.labels,
                        registry=self.registry,
                    )
                else:
                    logger.error(f"Unknown metric type: {definition.type}")
                    return

                self.metrics[definition.name] = metric
                logger.debug(f"Registered metric: {definition.name}")

            except Exception as e:
                logger.error(f"Failed to register metric {definition.name}: {e}")

    def set_metric(self, name: str, value: float, labels: Dict[str, str] = None):
        """
        Set metric value.

        Args:
            name: Metric name
            value: Metric value
            labels: Optional labels
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return

        # Validate value
        is_valid, error = self.security.validate_metric_value(value)
        if not is_valid:
            logger.warning(f"Invalid value for metric {name}: {error}")
            return

        try:
            metric = self.metrics[name]

            if labels:
                metric.labels(**labels).set(value)
            else:
                metric.set(value)

        except Exception as e:
            logger.error(f"Failed to set metric {name}: {e}")

    def increment_metric(
        self, name: str, amount: float = 1.0, labels: Dict[str, str] = None
    ):
        """
        Increment counter metric.

        Args:
            name: Metric name
            amount: Amount to increment
            labels: Optional labels
        """
        if name not in self.metrics:
            logger.warning(f"Metric {name} not registered")
            return

        try:
            metric = self.metrics[name]

            if labels:
                metric.labels(**labels).inc(amount)
            else:
                metric.inc(amount)

        except Exception as e:
            logger.error(f"Failed to increment metric {name}: {e}")

    def export_metrics(self, metrics_data: Dict[str, Any]):
        """
        Export multiple metrics.

        Args:
            metrics_data: Dictionary of metric_name -> value
        """
        for name, value in metrics_data.items():
            # Auto-register if not exists
            if name not in self.metrics:
                metric_type = MetricType.GAUGE
                if "total" in name or "count" in name:
                    metric_type = MetricType.COUNTER

                definition = MetricDefinition(
                    name=name,
                    type=metric_type,
                    description=f"Auto-registered metric: {name}",
                )
                self.register_metric(definition)

            # Set value
            self.set_metric(name, float(value))

    def get_metrics_text(self) -> str:
        """
        Get metrics in Prometheus text format.

        Returns:
            Metrics as text
        """
        if not PROMETHEUS_AVAILABLE:
            return "# Prometheus client not available\n"

        try:
            return generate_latest(self.registry).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to generate metrics: {e}")
            return "# Error generating metrics\n"


# ============================================================================
# Main Telemetry Collector
# ============================================================================


class EBPFTelemetryCollector:
    """
    Main telemetry collector for eBPF programs.

    This is the primary interface for collecting telemetry from eBPF programs.
    It coordinates map reading, perf buffer processing, and metrics export.

    Usage:
        collector = EBPFTelemetryCollector(config)
        collector.register_program(perf_monitor, "performance_monitor")
        collector.start()

        # Collect metrics
        metrics = collector.collect_all_metrics()

        # Export to Prometheus
        collector.export_to_prometheus(metrics)
    """

    def __init__(
        self,
        config: Optional[TelemetryConfig] = None,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """
        Initialize telemetry collector.

        Args:
            config: Optional configuration
        """
        self.config = config or TelemetryConfig()
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.security = SecurityManager(self.config)
        self.map_reader = MapReader(
            self.config,
            self.security,
            event_bus=event_bus,
            event_project_root=event_project_root,
        )
        self.perf_reader = PerfBufferReader(self.config, self.security)
        self.prometheus = PrometheusExporter(self.config, self.security)

        # Registered programs
        self.programs: Dict[str, Any] = {}
        self.program_maps: Dict[str, List[str]] = {}

        # Statistics
        self.stats = CollectionStats()

        # Threading
        self.collection_thread: Optional[threading.Thread] = None
        self.perf_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        logger.info("EBPFTelemetryCollector initialized")

    def register_program(
        self, bpf_program: Any, program_name: str, map_names: List[str] = None
    ):
        """
        Register an eBPF program for telemetry collection.

        Args:
            bpf_program: BCC BPF program instance
            program_name: Name of the program
            map_names: List of map names to monitor
        """
        self.programs[program_name] = bpf_program
        self.program_maps[program_name] = map_names or []

        logger.info(f"Registered eBPF program: {program_name}")

    def register_map(
        self, program_name: str, map_name: str, map_type: MapType = MapType.HASH
    ):
        """
        Register a specific map for monitoring.

        Args:
            program_name: Name of the program
            map_name: Name of the map
            map_type: Type of the map
        """
        if program_name not in self.program_maps:
            self.program_maps[program_name] = []

        if map_name not in self.program_maps[program_name]:
            self.program_maps[program_name].append(map_name)
            logger.debug(f"Registered map: {program_name}/{map_name}")

    def collect_from_map(self, program_name: str, map_name: str) -> Dict[str, Any]:
        """
        Collect metrics from a specific map.

        Args:
            program_name: Name of the program
            map_name: Name of the map

        Returns:
            Dictionary with map data
        """
        bpf_program = self.programs.get(program_name)
        if not bpf_program:
            logger.warning(f"Program {program_name} not found")
            return {}

        try:
            data = self.map_reader.read_map(bpf_program, map_name)
            self.stats.total_metrics_collected += len(data)
            return data
        except Exception as e:
            logger.error(f"Error collecting from map {map_name}: {e}")
            return {}

    def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all registered programs and maps.

        Returns:
            Dictionary with all collected metrics
        """
        start_time = time.time()
        all_metrics = {}

        self.stats.total_collections += 1

        try:
            # Collect from all programs
            for program_name, bpf_program in self.programs.items():
                program_metrics = {}

                # Get maps for this program
                map_names = self.program_maps.get(program_name, [])

                if not map_names and BCC_AVAILABLE:
                    # Auto-discover maps
                    try:
                        for key in dir(bpf_program):
                            if key.startswith("[") and key.endswith("]"):
                                map_name = key[2:-2]
                                map_names.append(map_name)
                    except Exception as e:
                        logger.debug(
                            f"Could not auto-discover maps for {program_name}: {e}"
                        )

                # Read all maps
                if map_names:
                    map_data = self.map_reader.read_multiple_maps(
                        bpf_program, map_names
                    )
                    for map_name, data in map_data.items():
                        # Flatten map data into metrics
                        for key, value in data.items():
                            metric_name = f"{program_name}_{map_name}_{key}"
                            program_metrics[metric_name] = value

                all_metrics[program_name] = program_metrics

            self.stats.successful_collections += 1
            self.stats.last_collection_time = time.time()

            # Update average collection time
            collection_time = time.time() - start_time
            self.stats.collection_times.append(collection_time)
            self.stats.average_collection_time = sum(self.stats.collection_times) / len(
                self.stats.collection_times
            )

            logger.debug(
                f"Collected {len(all_metrics)} program metrics in {collection_time*1000:.2f}ms"
            )

        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self.stats.failed_collections += 1

        return all_metrics

    def export_to_prometheus(self, metrics: Dict[str, Any]):
        """
        Export metrics to Prometheus.

        Args:
            metrics: Dictionary of metrics to export
        """
        # Flatten metrics
        flat_metrics = {}
        for program_name, program_metrics in metrics.items():
            for metric_name, value in program_metrics.items():
                flat_metrics[f"{program_name}_{metric_name}"] = value

        # Export
        self.prometheus.export_metrics(flat_metrics)

        logger.debug(f"Exported {len(flat_metrics)} metrics to Prometheus")

    def start_perf_reading(self, map_name: str = "events"):
        """
        Start reading perf buffer events.

        Args:
            map_name: Name of the perf buffer map
        """
        if not self.programs:
            logger.warning("No programs registered for perf reading")
            return

        # Use first registered program
        bpf_program = next(iter(self.programs.values()))

        self.perf_thread = threading.Thread(
            target=self.perf_reader.start_reading,
            args=(bpf_program, map_name),
            daemon=True,
        )
        self.perf_thread.start()

        logger.info("Started perf buffer reading thread")

    def start_collection_loop(self, interval: Optional[float] = None):
        """
        Start automatic metric collection loop.

        Args:
            interval: Collection interval in seconds
        """
        interval = interval or self.config.collection_interval

        def collection_loop():
            while not self.stop_event.is_set():
                try:
                    metrics = self.collect_all_metrics()
                    self.export_to_prometheus(metrics)
                except Exception as e:
                    logger.error(f"Error in collection loop: {e}")

                self.stop_event.wait(interval)

        self.collection_thread = threading.Thread(target=collection_loop, daemon=True)
        self.collection_thread.start()

        logger.info(f"Started collection loop (interval={interval}s)")

    def start(self):
        """Start the telemetry collector."""
        # Start Prometheus server
        self.prometheus.start_server()

        # Start collection loop
        self.start_collection_loop()

        logger.info("Telemetry collector started")

    def stop(self):
        """Stop the telemetry collector."""
        self.stop_event.set()

        # Stop perf reader
        self.perf_reader.stop_reading()

        # Wait for threads
        if self.collection_thread:
            self.collection_thread.join(timeout=5)
        if self.perf_thread:
            self.perf_thread.join(timeout=5)

        logger.info("Telemetry collector stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            "collection": asdict(self.stats),
            "security": self.security.get_stats(),
            "perf_reader": self.perf_reader.get_stats(),
            "programs": list(self.programs.keys()),
            "maps": self.program_maps,
        }

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# ============================================================================
# Convenience Functions
# ============================================================================


def create_collector(
    prometheus_port: int = 9090,
    collection_interval: float = 1.0,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
) -> EBPFTelemetryCollector:
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
    return EBPFTelemetryCollector(
        config,
        event_bus=event_bus,
        event_project_root=event_project_root,
    )


def quick_start(
    bpf_program: Any,
    program_name: str,
    prometheus_port: int = 9090,
    event_bus: Optional[EventBus] = None,
    event_project_root: str = ".",
) -> EBPFTelemetryCollector:
    """
    Quick start telemetry collection for a single eBPF program.

    Args:
        bpf_program: BCC BPF program instance
        program_name: Name of the program
        prometheus_port: Prometheus HTTP server port

    Returns:
        EBPFTelemetryCollector instance
    """
    collector = create_collector(
        prometheus_port,
        event_bus=event_bus,
        event_project_root=event_project_root,
    )
    collector.register_program(bpf_program, program_name)
    collector.start()
    return collector


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Example usage
    logger.info("eBPF Telemetry Module Example")

    # Create collector
    collector = create_collector(prometheus_port=9090)

    # Register a program (would be loaded from eBPF)
    # collector.register_program(bpf_program, "performance_monitor")

    # Start collector
    collector.start()

    try:
        # Collect metrics
        metrics = collector.collect_all_metrics()
        logger.info(f"Collected metrics: {len(metrics)} programs")

        # Get stats
        stats = collector.get_stats()
        logger.info(f"Stats: {stats}")

        # Keep running
        logger.info("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Stopping...")
        collector.stop()
