"""
Security manager for eBPF telemetry module.

Handles input validation, data sanitization, and security checks
for telemetry data.
"""

import logging
import hashlib
import os
from typing import Any, Dict, List, Optional, Tuple

from src.core.thinking.agent_thinking import AgentThinkingCoach

from .models import EventSeverity, TelemetryConfig, TelemetryEvent

logger = logging.getLogger(__name__)


def _safe_hash(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


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
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ebpf-telemetry-security-manager",
            role="security",
            capabilities=("zero-trust", "telemetry"),
        )
        self.last_thinking_context: Dict[str, Any] = {}

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

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "type": task_type,
            "goal": goal,
            "validation_error_count": len(self.validation_errors),
            "sanitized_count": self.sanitized_count,
            "validation_enabled": self.config.enable_validation,
            "sanitization_enabled": self.config.enable_sanitization,
            "constraints": {
                "redact_metric_names": True,
                "redact_paths": True,
                "redact_event_payloads": True,
                "telemetry_validation_is_not_dataplane_delivery_proof": True,
            },
            "safety_boundary": (
                "Telemetry security validation records local input checks only; "
                "it does not prove kernel eBPF program load or packet delivery."
            ),
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose telemetry security thinking state without raw inputs."""
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def validate_metric_name(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate metric name for security.

        Args:
            name: Metric name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            self._record_thinking(
                "ebpf_telemetry_metric_name_validation",
                "reject empty metric name",
                {"status": "invalid", "reason": "empty"},
            )
            return False, "Metric name cannot be empty"

        if len(name) > 200:
            self._record_thinking(
                "ebpf_telemetry_metric_name_validation",
                "reject overlong metric name",
                {
                    "status": "invalid",
                    "reason": "too_long",
                    "metric_name_hash": _safe_hash(name),
                    "metric_name_length": len(name),
                },
            )
            return False, f"Metric name too long: {len(name)} > 200"

        # Check for valid characters
        for char in name:
            if char not in self.allowed_metric_chars:
                self._record_thinking(
                    "ebpf_telemetry_metric_name_validation",
                    "reject metric name with invalid character",
                    {
                        "status": "invalid",
                        "reason": "invalid_character",
                        "metric_name_hash": _safe_hash(name),
                    },
                )
                return False, f"Invalid character in metric name: {char}"

        # Check for reserved prefixes
        if name.startswith("__"):
            self._record_thinking(
                "ebpf_telemetry_metric_name_validation",
                "reject reserved metric name prefix",
                {
                    "status": "invalid",
                    "reason": "reserved_prefix",
                    "metric_name_hash": _safe_hash(name),
                },
            )
            return False, "Metric name cannot start with '__'"

        self._record_thinking(
            "ebpf_telemetry_metric_name_validation",
            "accept metric name after local validation",
            {"status": "valid", "metric_name_hash": _safe_hash(name)},
        )
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
            self._record_thinking(
                "ebpf_telemetry_metric_value_validation",
                "reject missing metric value",
                {"status": "invalid", "reason": "none"},
            )
            return False, "Metric value cannot be None"

        # Check type
        if not isinstance(value, (int, float)):
            self._record_thinking(
                "ebpf_telemetry_metric_value_validation",
                "reject metric value with invalid type",
                {"status": "invalid", "reason": "invalid_type"},
            )
            return False, f"Invalid metric type: {type(value)}"

        # Check for NaN/Inf
        if isinstance(value, float):
            if value != value:  # NaN check
                self._record_thinking(
                    "ebpf_telemetry_metric_value_validation",
                    "reject NaN metric value",
                    {"status": "invalid", "reason": "nan"},
                )
                return False, "Metric value cannot be NaN"
            if abs(value) == float("inf"):
                self._record_thinking(
                    "ebpf_telemetry_metric_value_validation",
                    "reject infinite metric value",
                    {"status": "invalid", "reason": "infinite"},
                )
                return False, "Metric value cannot be infinite"

        # Check range
        if abs(value) > self.config.max_metric_value:
            self._record_thinking(
                "ebpf_telemetry_metric_value_validation",
                "reject metric value exceeding configured maximum",
                {"status": "invalid", "reason": "too_large"},
            )
            return (
                False,
                f"Metric value exceeds maximum: {value} > {self.config.max_metric_value}",
            )

        self._record_thinking(
            "ebpf_telemetry_metric_value_validation",
            "accept metric value after local validation",
            {"status": "valid"},
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
        self._record_thinking(
            "ebpf_telemetry_string_sanitization",
            "sanitize telemetry string without storing raw content",
            {"sanitized_count": self.sanitized_count, "input_hash": _safe_hash(s)},
        )
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
        self._record_thinking(
            "ebpf_telemetry_path_sanitization",
            "sanitize telemetry path without storing raw path",
            {"path_hash": _safe_hash(path), "path_redacted": True},
        )

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
            self._record_thinking(
                "ebpf_telemetry_event_validation",
                "reject telemetry event with invalid event type",
                {"status": "invalid", "reason": "event_type"},
            )
            return False, "Invalid event type"

        # Validate timestamp
        if event.timestamp_ns <= 0:
            self._record_thinking(
                "ebpf_telemetry_event_validation",
                "reject telemetry event with invalid timestamp",
                {"status": "invalid", "reason": "timestamp"},
            )
            return False, "Invalid timestamp"

        # Validate CPU ID
        if event.cpu_id < 0 or event.cpu_id > 255:
            self._record_thinking(
                "ebpf_telemetry_event_validation",
                "reject telemetry event with invalid CPU ID",
                {"status": "invalid", "reason": "cpu_id"},
            )
            return False, f"Invalid CPU ID: {event.cpu_id}"

        # Validate PID
        if event.pid < 0 or event.pid > 4194304:  # Max PID on Linux
            self._record_thinking(
                "ebpf_telemetry_event_validation",
                "reject telemetry event with invalid PID",
                {"status": "invalid", "reason": "pid"},
            )
            return False, f"Invalid PID: {event.pid}"

        # Validate severity
        if not isinstance(event.severity, EventSeverity):
            self._record_thinking(
                "ebpf_telemetry_event_validation",
                "reject telemetry event with invalid severity",
                {"status": "invalid", "reason": "severity"},
            )
            return False, "Invalid severity"

        self._record_thinking(
            "ebpf_telemetry_event_validation",
            "accept telemetry event after local validation",
            {
                "status": "valid",
                "event_type_hash": _safe_hash(event.event_type),
                "severity": event.severity.name,
            },
        )
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


__all__ = ["SecurityManager"]
