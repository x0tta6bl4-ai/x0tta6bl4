"""Metric models, validation, and sanitization for eBPF metrics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from src.services.service_event_identity import service_event_identity


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
        }

    def validate(self, name: str, value: Any) -> MetricValidationResult:
        """Validate a single metric."""
        if name not in self.validation_rules:
            return MetricValidationResult(
                name=name,
                value=value,
                status=MetricValidationStatus.INVALID,
                message=f"No validation rules for metric: {name}",
            )
        rules = self.validation_rules[name]
        if not isinstance(value, rules.get("type", type(value))):
            return MetricValidationResult(
                name=name,
                value=value,
                status=MetricValidationStatus.TYPE_MISMATCH,
                message=f"Type mismatch: expected {rules.get('type', 'any')}, got {type(value)}",
            )
        if value < rules.get("min", float("-inf")):
            return MetricValidationResult(
                name=name,
                value=value,
                status=MetricValidationStatus.OUT_OF_RANGE,
                message=f"Value {value} below minimum {rules['min']}",
            )
        if value > rules.get("max", float("inf")):
            return MetricValidationResult(
                name=name,
                value=value,
                status=MetricValidationStatus.OUT_OF_RANGE,
                message=f"Value {value} above maximum {rules['max']}",
            )
        return MetricValidationResult(
            name=name,
            value=value,
            status=MetricValidationStatus.VALID,
        )

    def sanitize(
        self, metrics: Dict[str, Any]
    ) -> tuple[Dict[str, Any], list[MetricValidationResult]]:
        """Sanitize all metrics, returning valid metrics and validation results."""
        valid_metrics = {}
        validation_results = []

        for name, value in metrics.items():
            result = self.validate(name, value)
            validation_results.append(result)
            if result.status == MetricValidationStatus.VALID:
                valid_metrics[name] = value

        return valid_metrics, validation_results


# Constants
EBPF_METRICS_EXPORTER_SERVICE_NAME = "ebpf-metrics-exporter"
EBPF_METRICS_EXPORTER_LAYER = "network_ebpf_metrics_observed_state"
EBPF_METRICS_EXPORTER_CLAIM_BOUNDARY = (
    "Local eBPF metrics exporter observation only. Events record bpftool map "
    "lookup/dump outcomes, return codes, duration, bounded output hashes, and "
    "redacted map selectors; they do not prove production traffic, packet "
    "forwarding, Prometheus delivery, or attached kernel program correctness."
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return ""


def _sha256_text(value: Any) -> str | None:
    value = _normalize_text(value)
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _hash_value(value: Any) -> str | None:
    if value is None:
        return None
    return _sha256_text(str(value))


def _bounded_output_metadata(
    stdout: str | None,
    stderr: str | None,
) -> Dict[str, Any]:
    safe_stdout = _normalize_text(stdout)
    safe_stderr = _normalize_text(stderr)
    return {
        "stdout_chars": len(safe_stdout),
        "stderr_chars": len(safe_stderr),
        "stdout_sha256": _sha256_text(safe_stdout),
        "stderr_sha256": _sha256_text(safe_stderr),
        "output_bounded": True,
        "output_redacted": True,
    }


def _identity_metadata() -> Dict[str, Any]:
    identity = service_event_identity(service_name=EBPF_METRICS_EXPORTER_SERVICE_NAME)
    return {"service_name": identity.get("service_name", ""), "node_id": identity.get("node_id", "")}
