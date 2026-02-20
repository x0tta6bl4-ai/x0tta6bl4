"""
Security manager for eBPF telemetry module.

Handles input validation, data sanitization, and security checks
for telemetry data.
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from .models import EventSeverity, TelemetryConfig, TelemetryEvent

logger = logging.getLogger(__name__)


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


__all__ = ["SecurityManager"]
