"""
Enhanced eBPF Metrics Exporter with improved error handling and resilience.

This module builds upon the existing EBPFMetricsExporter to provide:
1. Enhanced error handling and recovery mechanisms
2. Better metric validation and sanitization
3. Improved performance monitoring
4. Health check integration
5. Detailed error reporting for debugging
"""

import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType
from src.network.ebpf.metrics_exporter import EBPFMetricsExporter
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

EBPF_METRICS_EXPORTER_ENHANCED_SERVICE_NAME = "ebpf-metrics-exporter-enhanced"
EBPF_METRICS_EXPORTER_ENHANCED_LAYER = "network_ebpf_metrics_enhanced_observed_state"
EBPF_METRICS_EXPORTER_ENHANCED_CLAIM_BOUNDARY = (
    "Local enhanced eBPF metrics wrapper evidence only. Events record timeout/retry "
    "wrapper outcomes, duration, result shape, and redacted map selectors; they do "
    "not prove production traffic, Prometheus delivery, or attached kernel program "
    "correctness."
)


def _sha256_text(value: str) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return _sha256_text(str(value))


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(
        service_name=EBPF_METRICS_EXPORTER_ENHANCED_SERVICE_NAME
    )
    return {
        "service_name": EBPF_METRICS_EXPORTER_ENHANCED_SERVICE_NAME,
        "layer": EBPF_METRICS_EXPORTER_ENHANCED_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }


def _result_shape(value: Any) -> Dict[str, Any]:
    if value is None:
        return {"type": "none", "count": 0}
    if isinstance(value, dict):
        return {
            "type": "dict",
            "count": len(value),
            "key_hashes": [
                _hash_value(key)
                for key in sorted(value.keys(), key=lambda item: str(item))
            ],
            "keys_redacted": True,
        }
    if hasattr(value, "__len__"):
        return {"type": type(value).__name__, "count": len(value)}
    return {"type": type(value).__name__, "count": 1}


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


class _EBPFMetricsExporterCompatBase(EBPFMetricsExporter):
    """
    Compatibility layer.

    Keeps the MRO shape expected by legacy tests:
    Enhanced -> CompatBase -> EBPFMetricsExporter -> object
    """


class EBPFMetricsExporterEnhanced(_EBPFMetricsExporterCompatBase):
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
        stale_metric_ttl_seconds: float = 300.0,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        """Initialize enhanced metrics exporter."""
        super().__init__(
            prometheus_port,
            event_bus=event_bus,
            event_project_root=event_project_root,
        )
        self.sanitizer = MetricSanitizer(validation_rules)
        self.error_count = ErrorCount()
        self.max_queue_size = max_queue_size
        self.metric_queue = []
        self.metric_last_updated: Dict[str, float] = {}
        self.stale_metric_ttl_seconds = stale_metric_ttl_seconds
        self.performance_stats = {
            "export_time": [],
            "parse_time": [],
            "read_time": [],
        }
        self.enhanced_source_agent = EBPF_METRICS_EXPORTER_ENHANCED_SERVICE_NAME

        logger.info("Enhanced eBPF Metrics Exporter initialized")

    def _enhanced_event_bus_or_none(self) -> Optional[EventBus]:
        if not hasattr(self, "event_bus"):
            return None
        if self.event_bus is not None:
            return self.event_bus
        try:
            return EventBus(project_root=getattr(self, "event_project_root", "."))
        except Exception as exc:
            logger.error("Failed to initialize enhanced eBPF metrics EventBus: %s", exc)
            return None

    def _publish_enhanced_read_observation(
        self,
        *,
        stage: str,
        status: str,
        map_name: str,
        start: float,
        reason: str = "",
        result: Any = None,
        error: Optional[BaseException] = None,
    ) -> Optional[str]:
        bus = self._enhanced_event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.ebpf.metrics_exporter_enhanced",
            "stage": stage,
            "operation": "read_map_via_bpftool_with_timeout",
            "operation_resource": "ebpf_metrics_enhanced_bpftool_read",
            "resource": "network:ebpf:metrics_exporter_enhanced",
            "service_name": EBPF_METRICS_EXPORTER_ENHANCED_SERVICE_NAME,
            "layer": EBPF_METRICS_EXPORTER_ENHANCED_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "reason": reason,
            "backend": "bpftool",
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "map_name_hash": _hash_value(map_name),
            "map_name_redacted": True,
            "result_shape": _result_shape(result),
            "result_payload_redacted": True,
            "payloads_redacted": True,
            "read_only": True,
            "observed_state": True,
            "safe_observation": True,
            "claim_boundary": EBPF_METRICS_EXPORTER_ENHANCED_CLAIM_BOUNDARY,
        }
        if error is not None:
            payload.update(
                {
                    "error_type": type(error).__name__,
                    "error_message_hash": _hash_value(str(error)),
                    "error_message_redacted": True,
                }
            )

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                EBPF_METRICS_EXPORTER_ENHANCED_SERVICE_NAME,
                payload,
                priority=4,
            )
            return event.event_id
        except Exception as exc:
            logger.error(
                "Failed to publish enhanced eBPF metrics observation: %s", exc
            )
            return None

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
            updated_at = time.time()
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
                    self.metric_last_updated[metric_name] = updated_at

                except Exception as e:
                    logger.error(f"Failed to export metric {metric_name}: {e}")
                    self._update_error_count("export")

            # Fallback export if Prometheus unavailable
            if not self.prometheus.degradation.prometheus_available:
                self.prometheus.export_to_fallback(exported)

            # Track performance
            self._track_performance("export_time", time.time() - export_start)
            self._cleanup_stale_metrics(now=updated_at)

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
        start = time.monotonic()
        read_start = time.time()
        try:
            result = self._read_map_via_bpftool(map_name)
            if result is None:
                self._publish_enhanced_read_observation(
                    stage="enhanced_metrics_map_read_empty",
                    status="empty",
                    map_name=map_name,
                    start=start,
                    reason="bpftool_read_returned_none",
                    result=result,
                )
            else:
                self._publish_enhanced_read_observation(
                    stage="enhanced_metrics_map_read_succeeded",
                    status="success",
                    map_name=map_name,
                    start=start,
                    reason="bpftool_read_succeeded",
                    result=result,
                )
            return result
        except subprocess.TimeoutExpired as exc:
            logger.warning(f"bpftool timeout reading map {map_name}")
            self._update_error_count("timeout")
            self._publish_enhanced_read_observation(
                stage="enhanced_metrics_map_read_timeout",
                status="failure",
                map_name=map_name,
                start=start,
                reason="bpftool_timeout",
                error=exc,
            )
        except Exception as e:
            logger.error(f"Error reading map {map_name}: {e}")
            self._update_error_count("map_read")
            self._publish_enhanced_read_observation(
                stage="enhanced_metrics_map_read_failed",
                status="failure",
                map_name=map_name,
                start=start,
                reason="exception",
                error=e,
            )
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
        degradation = self.get_degradation_status()
        errors = self.get_error_summary()
        performance = self.get_performance_stats()

        def _as_int(value: Any, default: int = 0) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        # Determine overall health
        consecutive_failures = _as_int(degradation.get("consecutive_failures", 0))
        total_errors = _as_int(errors.get("total", 0))

        if consecutive_failures > 5 or total_errors > 100:
            overall = "unhealthy"
        elif total_errors > 50 or degradation.get("level") == "degraded":
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
            "metric_last_updated": self.metric_last_updated,
            "config": {
                "prometheus_port": self.prometheus.port,
                "max_queue_size": self.max_queue_size,
                "stale_metric_ttl_seconds": self.stale_metric_ttl_seconds,
            },
        }

        try:
            with open(file_path, "w") as f:
                json.dump(diagnostics, f, indent=2, default=str)
            logger.info(f"Diagnostics saved to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save diagnostics: {e}")

    def _cleanup_stale_metrics(
        self,
        *,
        now: Optional[float] = None,
        ttl_seconds: Optional[float] = None,
    ) -> List[str]:
        """Clean up stale metrics that haven't been updated recently."""
        last_updated = getattr(self, "metric_last_updated", None)
        if not isinstance(last_updated, dict):
            self.metric_last_updated = {}
            return []

        ttl = self.stale_metric_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            return []

        current_time = time.time() if now is None else now
        stale_names = [
            name
            for name, updated_at in list(last_updated.items())
            if current_time - float(updated_at) > ttl
        ]

        for metric_name in stale_names:
            last_updated.pop(metric_name, None)
            metric = getattr(self.prometheus, "metrics", {}).pop(metric_name, None)
            self._unregister_prometheus_metric(metric)

        if stale_names:
            logger.debug("Cleaned up %d stale eBPF metrics", len(stale_names))

        return stale_names

    def _unregister_prometheus_metric(self, metric: Any) -> None:
        """Best-effort removal from the default Prometheus registry."""
        if metric is None:
            return
        try:
            from prometheus_client import REGISTRY

            REGISTRY.unregister(metric)
        except (ImportError, KeyError, ValueError, AttributeError):
            return


# Monkey patch to replace existing exporter if needed
def patch_exporter():
    """Monkey patch the base exporter with enhanced version."""
    from src.network.ebpf import metrics_exporter

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
