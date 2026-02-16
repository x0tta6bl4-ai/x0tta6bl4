"""
eBPF Metrics Exporter for Prometheus

Enhanced version with:
- Custom exception classes for detailed error classification
- Retry logic with exponential backoff for network operations
- Graceful degradation when Prometheus endpoint is unavailable
- Structured logging with error context
- Proper signal handling for graceful shutdown
- Metric validation and sanitization
- Error counting and performance tracking
- Health check integration

Supports:
- Per-CPU array counters
- Ring buffer events
- Histogram maps
"""

import json
import logging
import signal
import struct
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


# Enhanced error handling and validation components
class MetricValidationStatus(Enum):
    """Status of metric validation."""

    VALID = "valid"
    INVALID = "invalid"
    OUT_OF_RANGE = "out_of_range"
    TYPE_MISMATCH = "type_mismatch"


@dataclass
class MetricValidationResult:
    """Result of metric validation."""

    name: str
    value: Any
    status: MetricValidationStatus
    message: Optional[str] = None
    expected_type: Optional[type] = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None


@dataclass
class ErrorCount:
    """Count of errors by type."""

    total: int = 0
    map_read: int = 0
    bpftool: int = 0
    parsing: int = 0
    validation: int = 0
    export: int = 0
    timeout: int = 0


class MetricSanitizer:
    """Responsible for sanitizing and validating metrics before export."""

    def __init__(self, validation_rules: Optional[Dict[str, Any]] = None):
        """Initialize metric sanitizer with validation rules."""
        self.validation_rules = validation_rules or {
            "packet_counters": {"min": 0, "max": 10**12, "type": int},
            "latency_ms": {"min": 0, "max": 60000, "type": (int, float)},
            "bytes_transferred": {"min": 0, "max": 10**15, "type": int},
            "interface_count": {"min": 0, "max": 100, "type": int},
        }

    def validate(self, name: str, value: Any) -> MetricValidationResult:
        """Validate a single metric."""
        # Check for exact match
        rules = self.validation_rules.get(name, {})

        # If no specific rules for the exact name, try different matching strategies
        if not rules:
            # Try matching metric type from name patterns
            if "packet" in name or "counter" in name:
                rules = self.validation_rules.get("packet_counters", {})
            elif "latency" in name or "ms" in name:
                rules = self.validation_rules.get("latency_ms", {})
            elif "byte" in name or "transfer" in name:
                rules = self.validation_rules.get("bytes_transferred", {})
            elif "interface" in name or "count" in name:
                rules = self.validation_rules.get("interface_count", {})

        # Debug info
        print(f"Validating metric: {name} (value: {value})")
        print(f"Rules found: {rules}")

        # Check type
        expected_types = rules.get("type", (int, float))
        if not isinstance(value, expected_types):
            return MetricValidationResult(
                name=name,
                value=value,
                status=MetricValidationStatus.TYPE_MISMATCH,
                message=f"Expected type {expected_types}, got {type(value)}",
                expected_type=expected_types,
            )

        # Check range
        range_min = rules.get("min")
        range_max = rules.get("max")

        if range_min is not None and range_max is not None:
            if not (range_min <= value <= range_max):
                return MetricValidationResult(
                    name=name,
                    value=value,
                    status=MetricValidationStatus.OUT_OF_RANGE,
                    message=f"Value {value} outside valid range [{range_min}, {range_max}]",
                    range_min=range_min,
                    range_max=range_max,
                )

        return MetricValidationResult(
            name=name, value=value, status=MetricValidationStatus.VALID
        )

    def sanitize(
        self, metrics: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[MetricValidationResult]]:
        """
        Sanitize all metrics, returning valid metrics and validation results.

        Args:
            metrics: Dictionary of metrics to sanitize

        Returns:
            Tuple of valid metrics and validation results
        """
        valid_metrics = {}
        validation_results = []

        for name, value in metrics.items():
            result = self.validate(name, value)
            validation_results.append(result)

            if result.status == MetricValidationStatus.VALID:
                valid_metrics[name] = value
            else:
                logger.warning(f"Metric {name} invalid: {result.message}")

        return valid_metrics, validation_results


# Configure structured logging
logger = logging.getLogger(__name__)


# ==================== Custom Exception Classes ====================


class EBPFMetricsError(Exception):
    """Base exception for eBPF metrics errors"""

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "context": self.context,
            "timestamp": self.timestamp,
        }


class MapReadError(EBPFMetricsError):
    """Error reading eBPF map data"""

    pass


class BpftoolError(EBPFMetricsError):
    """Error executing bpftool command"""

    def __init__(
        self, message: str, command: List[str], stderr: str = "", returncode: int = -1
    ):
        super().__init__(
            message,
            {"command": " ".join(command), "stderr": stderr, "returncode": returncode},
        )
        self.command = command
        self.stderr = stderr
        self.returncode = returncode


class PrometheusExportError(EBPFMetricsError):
    """Error exporting metrics to Prometheus"""

    pass


class MetricRegistrationError(EBPFMetricsError):
    """Error registering a metric"""

    pass


class ParseError(EBPFMetricsError):
    """Error parsing eBPF map data"""

    pass


class TimeoutError(EBPFMetricsError):
    """Operation timed out"""

    pass


# ==================== Retry Logic ====================


@dataclass
class RetryConfig:
    """Configuration for retry logic"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True


def with_retry(
    config: Optional[RetryConfig] = None,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None,
):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        config: Retry configuration
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Callback function called on each retry
    """
    if config is None:
        config = RetryConfig()

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(
                            f"Max retries ({config.max_retries}) exceeded for {func.__name__}",
                            extra={
                                "function": func.__name__,
                                "attempt": attempt + 1,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base**attempt),
                        config.max_delay,
                    )

                    # Add jitter if enabled
                    if config.jitter:
                        import random

                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"Retry {attempt + 1}/{config.max_retries} for {func.__name__} "
                        f"after {delay:.2f}s due to: {e}",
                        extra={
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "delay": delay,
                            "error": str(e),
                        },
                    )

                    if on_retry:
                        on_retry(attempt, e, delay)

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


# ==================== Graceful Degradation ====================


class DegradationLevel(Enum):
    """Levels of graceful degradation"""

    FULL = "full"  # All features available
    DEGRADED = "degraded"  # Some features unavailable
    MINIMAL = "minimal"  # Only basic features
    OFFLINE = "offline"  # No external connections


@dataclass
class DegradationState:
    """Current degradation state"""

    level: DegradationLevel = DegradationLevel.FULL
    prometheus_available: bool = True
    bpftool_available: bool = True
    last_check: float = 0.0
    error_count: int = 0
    consecutive_failures: int = 0

    def update_prometheus_status(self, available: bool):
        """Update Prometheus availability status"""
        if available:
            self.consecutive_failures = 0
            if not self.prometheus_available:
                logger.info("Prometheus endpoint recovered")
        else:
            self.consecutive_failures += 1
            self.error_count += 1

        self.prometheus_available = available
        self._recalculate_level()

    def _recalculate_level(self):
        """Recalculate degradation level based on current state"""
        if self.prometheus_available and self.bpftool_available:
            self.level = DegradationLevel.FULL
        elif self.bpftool_available:
            self.level = DegradationLevel.DEGRADED
        elif self.prometheus_available:
            self.level = DegradationLevel.MINIMAL
        else:
            self.level = DegradationLevel.OFFLINE


# ==================== Signal Handling ====================


class GracefulShutdown:
    """Handler for graceful shutdown on signals"""

    def __init__(self):
        self.shutdown_requested = False
        self._callbacks: List[Callable] = []
        self._lock = threading.Lock()

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name}, initiating graceful shutdown...")

        with self._lock:
            self.shutdown_requested = True

            # Execute callbacks
            for callback in self._callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in shutdown callback: {e}")

    def register_callback(self, callback: Callable):
        """Register a callback to be called on shutdown"""
        with self._lock:
            self._callbacks.append(callback)

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self.shutdown_requested


# ==================== Structured Logging ====================


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


class PrometheusExporter:
    """Handles Prometheus metric export with graceful degradation"""

    def __init__(self, port: int = 9090):
        self.port = port
        self.metrics: Dict[str, Any] = {}
        self._server_started = False
        self._fallback_file = Path("/tmp/ebpf_metrics_fallback.json")  # nosec B108
        self.degradation = DegradationState()
        self.slog = StructuredLogger(__name__)

        if not PROMETHEUS_AVAILABLE:
            self.slog.warning(
                "prometheus_client not available, using fallback mode",
                degradation_level=DegradationLevel.DEGRADED.value,
            )
            self.degradation.prometheus_available = False
            self.degradation._recalculate_level()

    @with_retry(
        config=RetryConfig(max_retries=3, base_delay=2.0),
        exceptions=(OSError, Exception),
    )
    def start_server(self) -> bool:
        """Start Prometheus HTTP server with retry logic"""
        if not PROMETHEUS_AVAILABLE:
            return False

        if self._server_started:
            return True

        try:
            start_http_server(self.port)
            self._server_started = True
            self.degradation.update_prometheus_status(True)
            self.slog.info(f"Prometheus metrics server started", port=self.port)
            return True
        except OSError as e:
            self.degradation.update_prometheus_status(False)
            self.slog.error(
                f"Failed to start Prometheus server", error=e, port=self.port
            )
            raise PrometheusExportError(
                f"Failed to start Prometheus server on port {self.port}",
                {"port": self.port, "error": str(e)},
            )

    def create_gauge(
        self, name: str, description: str, labels: List[str] = None
    ) -> Optional[Any]:
        """Create a Prometheus Gauge metric"""
        if not PROMETHEUS_AVAILABLE:
            return None

        try:
            if name in self.metrics:
                return self.metrics[name]

            metric = Gauge(name, description, labels or [])
            self.metrics[name] = metric
            return metric
        except Exception as e:
            self.slog.error(f"Failed to create gauge metric", error=e, metric_name=name)
            raise MetricRegistrationError(
                f"Failed to create gauge '{name}'",
                {"metric_name": name, "error": str(e)},
            )

    def create_counter(
        self, name: str, description: str, labels: List[str] = None
    ) -> Optional[Any]:
        """Create a Prometheus Counter metric"""
        if not PROMETHEUS_AVAILABLE:
            return None

        try:
            if name in self.metrics:
                return self.metrics[name]

            metric = Counter(name, description, labels or [])
            self.metrics[name] = metric
            return metric
        except Exception as e:
            self.slog.error(
                f"Failed to create counter metric", error=e, metric_name=name
            )
            raise MetricRegistrationError(
                f"Failed to create counter '{name}'",
                {"metric_name": name, "error": str(e)},
            )

    def create_histogram(
        self,
        name: str,
        description: str,
        labels: List[str] = None,
        buckets: tuple = None,
    ) -> Optional[Any]:
        """Create a Prometheus Histogram metric"""
        if not PROMETHEUS_AVAILABLE:
            return None

        try:
            if name in self.metrics:
                return self.metrics[name]

            kwargs = {"labelnames": labels or []}
            if buckets:
                kwargs["buckets"] = buckets

            metric = Histogram(name, description, **kwargs)
            self.metrics[name] = metric
            return metric
        except Exception as e:
            self.slog.error(
                f"Failed to create histogram metric", error=e, metric_name=name
            )
            raise MetricRegistrationError(
                f"Failed to create histogram '{name}'",
                {"metric_name": name, "error": str(e)},
            )

    def export_to_fallback(self, metrics: Dict[str, Any]):
        """Export metrics to fallback file when Prometheus unavailable"""
        try:
            data = {
                "timestamp": time.time(),
                "metrics": metrics,
                "degradation_level": self.degradation.level.value,
            }

            with open(self._fallback_file, "w") as f:
                json.dump(data, f, indent=2)

            self.slog.debug(
                "Metrics exported to fallback file", file=str(self._fallback_file)
            )
        except Exception as e:
            self.slog.error(
                "Failed to export to fallback file",
                error=e,
                file=str(self._fallback_file),
            )


# ==================== Main Exporter Class ====================


class EBPFMetricsExporter:
    """
    Enhanced eBPF Metrics Exporter with robust error handling.

    Features:
    - Custom exception classes for detailed error classification
    - Retry logic with exponential backoff
    - Graceful degradation when Prometheus unavailable
    - Structured logging with context
    - Proper signal handling
    - Metric validation and sanitization
    - Error counting and performance tracking
    - Health check integration

    Example:
        >>> exporter = EBPFMetricsExporter()
        >>> exporter.register_map("packet_counters", "xdp_counter")
        >>> exporter.export_metrics()
    """

    def __init__(self, prometheus_port: int = 9090):
        self.registered_maps: Dict[str, Dict] = {}
        self.prometheus = PrometheusExporter(prometheus_port)
        self.shutdown = GracefulShutdown()
        self.slog = StructuredLogger(__name__)
        self.retry_config = RetryConfig()

        # Metric validation and sanitization
        self.sanitizer = MetricSanitizer()

        # Error tracking
        self.error_count = ErrorCount()

        # Performance tracking
        self.performance_stats = {"export_time": [], "parse_time": [], "read_time": []}

        # Register shutdown callback
        self.shutdown.register_callback(self._on_shutdown)

        # Set logging context
        self.slog.set_context(component="EBPFMetricsExporter")

        self.slog.info("EBPFMetricsExporter initialized")

    def _on_shutdown(self):
        """Cleanup on shutdown"""
        self.slog.info("Performing cleanup on shutdown...")
        # Export final metrics to fallback
        try:
            metrics = self._collect_all_metrics()
            self.prometheus.export_to_fallback(metrics)
        except Exception as e:
            self.slog.error("Failed to export final metrics", error=e)

    def register_map(
        self, map_name: str, program_name: str, map_type: str = "per_cpu_array"
    ):
        """
        Register an eBPF map for metric export.

        Args:
            map_name: Name of the eBPF map
            program_name: Name of the eBPF program (for labeling)
            map_type: Type of map (per_cpu_array, ringbuf, histogram)

        Raises:
            MetricRegistrationError: If registration fails
        """
        try:
            self.registered_maps[map_name] = {
                "program": program_name,
                "type": map_type,
            }

            # Create Prometheus metrics
            if map_type == "per_cpu_array":
                for label in ["tcp", "udp", "icmp", "other"]:
                    metric_name = f"ebpf_{program_name}_{label}_packets"
                    self.prometheus.create_gauge(
                        metric_name,
                        f"Number of {label.upper()} packets counted by {program_name}",
                        ["cpu", "interface"],
                    )
            elif map_type == "histogram":
                metric_name = f"ebpf_{program_name}_latency"
                self.prometheus.create_histogram(
                    metric_name,
                    f"Latency histogram from {program_name}",
                    ["operation"],
                    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
                )

            self.slog.info(
                f"Registered map '{map_name}' for program '{program_name}'",
                map_name=map_name,
                program_name=program_name,
                map_type=map_type,
            )

        except Exception as e:
            self.slog.error(f"Failed to register map", error=e, map_name=map_name)
            raise MetricRegistrationError(
                f"Failed to register map '{map_name}'",
                {"map_name": map_name, "error": str(e)},
            )

    @with_retry(
        config=RetryConfig(max_retries=2, base_delay=1.0),
        exceptions=(BpftoolError, subprocess.TimeoutExpired),
    )
    def _read_map_via_bpftool(self, map_name: str) -> Optional[Dict]:
        """
        Read eBPF map data using bpftool with retry logic.

        Args:
            map_name: Name of the map to read

        Returns:
            Dict with map data or None if failed

        Raises:
            BpftoolError: If bpftool command fails
            TimeoutError: If command times out
        """
        if self.shutdown.is_shutdown_requested():
            return None

        try:
            # Find map ID by name
            cmd = ["bpftool", "map", "show", "name", map_name, "-j"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                self.slog.debug(
                    f"Map '{map_name}' not found",
                    map_name=map_name,
                    stderr=result.stderr,
                )
                return None

            # Parse JSON output
            try:
                map_info = json.loads(result.stdout)
                if not map_info:
                    return None

                map_id = (
                    map_info[0].get("id")
                    if isinstance(map_info, list)
                    else map_info.get("id")
                )

            except json.JSONDecodeError as e:
                raise ParseError(
                    f"Failed to parse bpftool output for map '{map_name}'",
                    {"map_name": map_name, "output": result.stdout[:200]},
                )

            if not map_id:
                return None

            # Dump map contents
            cmd = ["bpftool", "map", "dump", "id", str(map_id), "-j"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

            if result.returncode != 0:
                raise BpftoolError(
                    f"Failed to dump map '{map_name}'",
                    cmd,
                    result.stderr,
                    result.returncode,
                )

            return {"raw_output": result.stdout, "map_id": map_id}

        except FileNotFoundError:
            self.prometheus.degradation.bpftool_available = False
            self.prometheus.degradation._recalculate_level()
            self.slog.warning(
                "bpftool not found",
                degradation_level=self.prometheus.degradation.level.value,
            )
            return None

        except subprocess.TimeoutExpired as e:
            raise TimeoutError(
                f"bpftool command timed out for map '{map_name}'",
                {"map_name": map_name, "timeout": 5},
            )

    def _parse_per_cpu_array(
        self, raw_output: str, map_id: Optional[str] = None
    ) -> List[int]:
        """
        Parse per-CPU array output from bpftool.

        Args:
            raw_output: Raw JSON output from bpftool
            map_id: Map ID for additional queries

        Returns:
            List of aggregated values [tcp_total, udp_total, icmp_total, other_total]

        Raises:
            ParseError: If parsing fails
        """
        try:
            if not raw_output:
                return [0, 0, 0, 0]

            data = json.loads(raw_output)

            # Aggregate per-CPU values
            totals = [0, 0, 0, 0]  # tcp, udp, icmp, other

            # Handle both list and dict formats
            entries = data if isinstance(data, list) else [data]

            for entry in entries:
                key = entry.get("key", 0)
                values = entry.get("value", [])

                # Per-CPU array: sum across all CPUs
                if isinstance(values, list):
                    total = sum(v for v in values if isinstance(v, (int, float)))
                else:
                    total = values if isinstance(values, (int, float)) else 0

                if 0 <= key < 4:
                    totals[key] = total

            return totals

        except json.JSONDecodeError as e:
            raise ParseError(
                "Failed to parse per-CPU array JSON",
                {"error": str(e), "output_preview": raw_output[:200]},
            )
        except Exception as e:
            self.slog.error("Unexpected error parsing per-CPU array", error=e)
            return [0, 0, 0, 0]

    def _collect_all_metrics(self) -> Dict[str, float]:
        """Collect all metrics from registered maps"""
        metrics = {}

        for map_name, map_info in self.registered_maps.items():
            try:
                map_data = self._read_map_via_bpftool(map_name)
                if not map_data:
                    continue

                program_name = map_info["program"]
                map_type = map_info["type"]

                if map_type == "per_cpu_array":
                    values = self._parse_per_cpu_array(map_data.get("raw_output", ""))
                    labels = ["tcp", "udp", "icmp", "other"]

                    for i, (label, value) in enumerate(zip(labels, values)):
                        metric_name = f"ebpf_{program_name}_{label}_packets"
                        metrics[metric_name] = value

            except EBPFMetricsError as e:
                self.slog.error(
                    f"Error collecting metrics for map '{map_name}'",
                    error=e,
                    map_name=map_name,
                )
            except Exception as e:
                self.slog.error(
                    f"Unexpected error collecting metrics", error=e, map_name=map_name
                )

        return metrics

    def _collect_all_metrics_with_validation(
        self,
    ) -> Tuple[Dict[str, Any], List[MetricValidationResult]]:
        """Collect and validate metrics."""
        start_time = time.time()

        try:
            map_metrics = self._collect_all_metrics()
            self._track_performance("read_time", time.time() - start_time)
            valid_metrics, validation_results = self._validate_and_sanitize(map_metrics)
            return valid_metrics, validation_results
        except Exception as e:
            self.slog.error(f"Error collecting metrics: {e}", error=e)
            self._update_error_count("map_read")
            return {}, []

    def _validate_and_sanitize(
        self, metrics: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[MetricValidationResult]]:
        """Validate and sanitize metrics."""
        valid_metrics, validation_results = self.sanitizer.sanitize(metrics)

        # Count validation errors
        invalid_count = sum(
            1 for r in validation_results if r.status != MetricValidationStatus.VALID
        )
        if invalid_count > 0:
            self._update_error_count("validation")

        return valid_metrics, validation_results

    def _track_performance(self, metric: str, duration: float):
        """Track performance metrics."""
        if metric not in self.performance_stats:
            self.performance_stats[metric] = []
        self.performance_stats[metric].append(duration)
        # Keep only last 100 samples
        if len(self.performance_stats[metric]) > 100:
            self.performance_stats[metric].pop(0)

    def _update_error_count(self, error_type: str):
        """Update error counts."""
        if hasattr(self.error_count, error_type):
            setattr(
                self.error_count, error_type, getattr(self.error_count, error_type) + 1
            )
        self.error_count.total += 1

    def export_metrics(
        self, custom_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Export all registered maps to Prometheus with validation.

        Args:
            custom_metrics: Optional custom metrics dict to export

        Returns:
            Dict of metric_name -> value
        """
        export_start = time.time()

        try:
            # Validate custom metrics
            if custom_metrics:
                valid_custom, _ = self.sanitizer.sanitize(custom_metrics)
            else:
                valid_custom = {}

            # Collect and validate map metrics
            map_metrics, validation_results = (
                self._collect_all_metrics_with_validation()
            )

            # Combine all valid metrics
            all_metrics = {**valid_custom, **map_metrics}

            # Export to Prometheus
            exported = {}
            for metric_name, value in all_metrics.items():
                try:
                    if metric_name not in self.prometheus.metrics:
                        if "total" in metric_name or "count" in metric_name:
                            self.prometheus.create_counter(
                                metric_name, f"Custom metric: {metric_name}", []
                            )
                        else:
                            self.prometheus.create_gauge(
                                metric_name, f"Custom metric: {metric_name}", []
                            )

                    metric = self.prometheus.metrics.get(metric_name)
                    if metric and hasattr(metric, "set"):
                        metric.set(value)

                    exported[metric_name] = value

                except Exception as e:
                    self.slog.error(
                        f"Failed to export metric", error=e, metric_name=metric_name
                    )
                    self._update_error_count("export")

            # Fallback export if Prometheus unavailable
            if not self.prometheus.degradation.prometheus_available:
                self.prometheus.export_to_fallback(exported)

            # Track performance
            self._track_performance("export_time", time.time() - export_start)

            # Log validation results
            for result in validation_results:
                if result.status != MetricValidationStatus.VALID:
                    self.slog.debug(
                        f"Metric validation failed: {result.name} = {result.value} - {result.message}"
                    )

            self.slog.debug(
                f"Exported {len(exported)} metrics in {self.performance_stats['export_time'][-1]*1000:.2f}ms",
                metric_count=len(exported),
            )

            return exported

        except Exception as e:
            self.slog.error(f"Error in export_metrics: {e}", error=e)
            self._update_error_count("export")
            return {}

    def get_error_summary(self) -> Dict[str, int]:
        """Get error count summary."""
        return {
            "total": self.error_count.total,
            "map_read": self.error_count.map_read,
            "bpftool": self.error_count.bpftool,
            "parsing": self.error_count.parsing,
            "validation": self.error_count.validation,
            "export": self.error_count.export,
            "timeout": self.error_count.timeout,
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        stats = {}
        for metric, times in self.performance_stats.items():
            if times:
                stats[metric] = {
                    "count": len(times),
                    "average_ms": sum(times) / len(times) * 1000,
                    "min_ms": min(times) * 1000,
                    "max_ms": max(times) * 1000,
                    "latest_ms": times[-1] * 1000,
                }
        return stats

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get detailed health status for monitoring.

        Returns:
            Dict with health information
        """
        degradation = self.get_degradation_status()
        errors = self.get_error_summary()
        performance = self.get_performance_stats()

        # Determine overall health
        if degradation.get("consecutive_failures", 0) > 5 or errors["total"] > 100:
            overall = "unhealthy"
        elif errors["total"] > 50 or degradation.get("level") == "degraded":
            overall = "degraded"
        else:
            overall = "healthy"

        return {
            "overall": overall,
            "degradation": degradation,
            "errors": errors,
            "performance": performance,
        }

    def reset_error_counts(self):
        """Reset all error counters."""
        self.error_count = ErrorCount()
        self.slog.info("Error counts reset")

    def dump_diagnostics(
        self, file_path: str = "/tmp/ebpf_metrics_diagnostics.json"  # nosec B108
    ):
        """
        Dump diagnostics information to file for debugging.

        Args:
            file_path: Path to save diagnostics file
        """
        diagnostics = {
            "timestamp": time.time(),
            "version": "2.0",
            "health": self.get_health_status(),
            "registered_maps": list(self.registered_maps.keys()),
            "prometheus_metrics": list(self.prometheus.metrics.keys()),
            "performance": self.performance_stats,
            "config": {"prometheus_port": self.prometheus.port},
        }

        try:
            with open(file_path, "w") as f:
                json.dump(diagnostics, f, indent=2, default=str)
            self.slog.info(f"Diagnostics saved to {file_path}")
        except Exception as e:
            self.slog.error(f"Failed to save diagnostics: {e}", error=e)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all exported metrics."""
        return {
            "registered_maps": len(self.registered_maps),
            "prometheus_metrics": len(self.prometheus.metrics),
            "maps": list(self.registered_maps.keys()),
            "degradation_level": self.prometheus.degradation.level.value,
            "prometheus_available": self.prometheus.degradation.prometheus_available,
            "bpftool_available": self.prometheus.degradation.bpftool_available,
            "error_count": self.prometheus.degradation.error_count,
        }

    def get_degradation_status(self) -> Dict[str, Any]:
        """Get current degradation status"""
        return {
            "level": (
                self.prometheus.degradation.level
                if isinstance(self.prometheus.degradation.level, str)
                else self.prometheus.degradation.level.value
            ),
            "prometheus_available": self.prometheus.degradation.prometheus_available,
            "bpftool_available": self.prometheus.degradation.bpftool_available,
            "consecutive_failures": self.prometheus.degradation.consecutive_failures,
            "total_errors": self.prometheus.degradation.error_count,
        }


# ==================== Example Usage ====================

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra)s",
        handlers=[logging.StreamHandler()],
    )

    exporter = EBPFMetricsExporter()
    exporter.register_map("packet_counters", "xdp_counter", "per_cpu_array")

    # Export metrics
    metrics = exporter.export_metrics()
    print("Exported metrics:", metrics)

    # Get summary
    summary = exporter.get_metrics_summary()
    print("Summary:", json.dumps(summary, indent=2))
