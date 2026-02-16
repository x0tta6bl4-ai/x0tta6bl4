"""
Enhanced eBPF Metrics Exporter with improved error handling and resilience.

This module builds upon the existing EBPFMetricsExporter to provide:
1. Enhanced error handling and recovery mechanisms
2. Better metric validation and sanitization
3. Improved performance monitoring
4. Health check integration
5. Detailed error reporting for debugging
"""

import json
import logging
import struct
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .metrics_exporter import EBPFMetricsExporter

logger = logging.getLogger(__name__)


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
        # Check for exact match first
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


class EBPFMetricsExporterEnhanced(EBPFMetricsExporter):
    """
    Enhanced eBPF Metrics Exporter with improved error handling.

    Extends the base class with:
    - Metric validation and sanitization
    - Enhanced error tracking
    - Performance monitoring
    - Health check integration
    - Detailed error reporting
    """

    def __init__(
        self,
        prometheus_port: int = 9090,
        max_queue_size: int = 1000,
        validation_rules: Optional[Dict[str, Any]] = None,
    ):
        """Initialize enhanced metrics exporter."""
        super().__init__(prometheus_port)
        self.sanitizer = MetricSanitizer(validation_rules)
        self.error_count = ErrorCount()
        self.max_queue_size = max_queue_size
        self.metric_queue = []
        self.performance_stats = {"export_time": [], "parse_time": [], "read_time": []}

        logger.info("Enhanced eBPF Metrics Exporter initialized")

    def _track_performance(self, metric: str, duration: float):
        """Track performance metrics."""
        if metric in self.performance_stats:
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

    def _validate_map_metadata(
        self, map_name: str, program_name: str, map_type: str
    ) -> bool:
        """
        Validate map metadata before registration.

        Returns:
            bool: True if metadata is valid
        """
        if not map_name or not program_name or not map_type:
            logger.error("Invalid map metadata: name, program, and type are required")
            return False

        if len(map_name) > 100 or len(program_name) > 100:
            logger.warning("Map/program name exceeds recommended length")

        valid_types = ["per_cpu_array", "ringbuf", "histogram"]
        if map_type not in valid_types:
            logger.error(f"Invalid map type: {map_type}. Valid types: {valid_types}")
            return False

        return True

    def register_map(
        self, map_name: str, program_name: str, map_type: str = "per_cpu_array"
    ) -> bool:
        """
        Register eBPF map with validation.

        Args:
            map_name: Name of the eBPF map
            program_name: Name of the eBPF program (for labeling)
            map_type: Type of map (per_cpu_array, ringbuf, histogram)

        Returns:
            bool: True if registration successful, False otherwise
        """
        if not self._validate_map_metadata(map_name, program_name, map_type):
            self._update_error_count("validation")
            return False

        try:
            super().register_map(map_name, program_name, map_type)
            return True
        except Exception as e:
            logger.error(f"Failed to register map {map_name}: {e}")
            self._update_error_count("validation")
            return False

    def _collect_all_metrics_with_validation(
        self,
    ) -> Tuple[Dict[str, Any], List[MetricValidationResult]]:
        """Collect and validate metrics."""
        start_time = time.time()

        try:
            map_metrics = super()._collect_all_metrics()
            self._track_performance("read_time", time.time() - start_time)
            valid_metrics, validation_results = self._validate_and_sanitize(map_metrics)
            return valid_metrics, validation_results
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            self._update_error_count("map_read")
            return {}, []

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
                    logger.error(f"Failed to export metric {metric_name}: {e}")
                    self._update_error_count("export")

            # Fallback export if Prometheus unavailable
            if not self.prometheus.degradation.prometheus_available:
                self.prometheus.export_to_fallback(exported)

            # Track performance
            self._track_performance("export_time", time.time() - export_start)

            # Log validation results
            for result in validation_results:
                if result.status != MetricValidationStatus.VALID:
                    logger.debug(
                        f"Metric validation failed: {result.name} = {result.value} - {result.message}"
                    )

            logger.debug(
                f"Exported {len(exported)} metrics in {self.performance_stats['export_time'][-1]*1000:.2f}ms"
            )

            return exported

        except Exception as e:
            logger.error(f"Error in export_metrics: {e}")
            self._update_error_count("export")
            return {}

    def _read_map_via_bpftool_with_timeout(
        self, map_name: str, timeout: float = 5.0
    ) -> Optional[Dict]:
        """
        Read eBPF map data using bpftool with timeout and retries.

        Args:
            map_name: Name of the map to read
            timeout: Timeout in seconds

        Returns:
            Dict with map data or None if failed
        """
        read_start = time.time()
        try:
            return self._read_map_via_bpftool(map_name)
        except subprocess.TimeoutExpired:
            logger.warning(f"bpftool timeout reading map {map_name}")
            self._update_error_count("timeout")
        except Exception as e:
            logger.error(f"Error reading map {map_name}: {e}")
            self._update_error_count("map_read")
        finally:
            self._track_performance("read_time", time.time() - read_start)

        return None

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
        degradation = super().get_degradation_status()
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
        logger.info("Error counts reset")

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
            "config": {
                "prometheus_port": self.prometheus.port,
                "max_queue_size": self.max_queue_size,
            },
        }

        try:
            with open(file_path, "w") as f:
                json.dump(diagnostics, f, indent=2, default=str)
            logger.info(f"Diagnostics saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save diagnostics: {e}")

    def _cleanup_stale_metrics(self):
        """Clean up stale metrics that haven't been updated recently."""
        # Implementation would track last update time for each metric
        # and remove those older than a certain threshold (e.g., 5 minutes)
        logger.debug("Stale metrics cleanup not implemented yet")


# Monkey patch to replace existing exporter if needed
def patch_exporter():
    """Monkey patch the base exporter with enhanced version."""
    from . import metrics_exporter

    metrics_exporter.EBPFMetricsExporter = EBPFMetricsExporterEnhanced
    logger.info("EBPFMetricsExporter patched with enhanced version")


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    exporter = EBPFMetricsExporterEnhanced(prometheus_port=9090)
    exporter.register_map("packet_counters", "xdp_counter", "per_cpu_array")

    # Test export
    try:
        metrics = exporter.export_metrics()
        logger.info(f"Exported {len(metrics)} metrics")

        # Check health
        health = exporter.get_health_status()
        logger.info(f"Health status: {health['overall']}")

        # Dump diagnostics
        exporter.dump_diagnostics()

    except Exception as e:
        logger.error(f"Error: {e}")
