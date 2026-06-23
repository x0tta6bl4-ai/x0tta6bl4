"""eBPF Metrics Exporter — exception hierarchy."""

from __future__ import annotations

from typing import Any, Dict, Optional


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


