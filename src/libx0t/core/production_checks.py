"""
Production Dependency Checks for x0tta6bl4

Ensures all critical dependencies are available before starting in production mode.
No graceful degradation for production-critical components.
"""

import os
import sys
from typing import List, Tuple

PRODUCTION_MODE = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"


class ProductionDependencyError(Exception):
    """Raised when critical production dependencies are missing."""

    pass


def check_production_dependencies() -> None:
    """
    Check all critical dependencies for production mode.

    Raises ProductionDependencyError if any critical dependency is missing.
    """
    if not PRODUCTION_MODE:
        return

    errors = []

    # PQC - Critical for security
    try:
        from libx0t.security.post_quantum_liboqs import LIBOQS_AVAILABLE

        if not LIBOQS_AVAILABLE:
            errors.append(
                "liboqs-python not available - REQUIRED for post-quantum cryptography"
            )
    except ImportError:
        errors.append("Post-quantum cryptography module not available")

    # ML Components - Critical for anomaly detection
    try:
        import torch

        if not torch.cuda.is_available():
            errors.append("CUDA not available - required for production ML inference")
    except Exception:
        errors.append("PyTorch not available")

    try:
        from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector
    except ImportError:
        errors.append("GraphSAGE anomaly detector not available")

    # eBPF Components - Critical for network monitoring
    try:
        import bcc
    except ImportError:
        errors.append("BCC not available - required for eBPF")

    # Database - Critical for persistence
    try:
        import redis
    except ImportError:
        errors.append("Redis not available")

    # Monitoring - Critical for observability
    try:
        import prometheus_client
    except ImportError:
        errors.append("Prometheus client not available")

    try:
        from opentelemetry import trace
    except ImportError:
        errors.append("OpenTelemetry not available")

    if errors:
        error_msg = "PRODUCTION DEPENDENCY CHECK FAILED:\n" + "\n".join(
            f"- {e}" for e in errors
        )
        print(error_msg, file=sys.stderr)
        raise ProductionDependencyError(error_msg)


def get_dependency_status() -> List[Tuple[str, bool, str]]:
    """
    Get status of all dependencies.

    Returns:
        List of (dependency_name, is_available, status_message) tuples
    """
    status = []

    # PQC
    try:
        from libx0t.security.post_quantum_liboqs import LIBOQS_AVAILABLE

        status.append(
            (
                "PQC (liboqs)",
                LIBOQS_AVAILABLE,
                "Available" if LIBOQS_AVAILABLE else "Missing",
            )
        )
    except ImportError:
        status.append(("PQC (liboqs)", False, "Module not found"))

    # PyTorch
    try:
        import torch

        cuda_available = torch.cuda.is_available()
        status.append(("PyTorch", True, f"Available (CUDA: {cuda_available})"))
    except Exception:
        status.append(("PyTorch", False, "Not available"))

    # GraphSAGE
    try:
        from src.ml.graphsage_anomaly_detector import GraphSAGEAnomalyDetector

        status.append(("GraphSAGE", True, "Available"))
    except ImportError:
        status.append(("GraphSAGE", False, "Not available"))

    # eBPF
    try:
        import bcc

        status.append(("eBPF (BCC)", True, "Available"))
    except ImportError:
        status.append(("eBPF (BCC)", False, "Not available"))

    # Redis
    try:
        import redis

        status.append(("Redis", True, "Available"))
    except ImportError:
        status.append(("Redis", False, "Not available"))

    # Prometheus
    try:
        import prometheus_client

        status.append(("Prometheus", True, "Available"))
    except ImportError:
        status.append(("Prometheus", False, "Not available"))

    # OpenTelemetry
    try:
        from opentelemetry import trace

        status.append(("OpenTelemetry", True, "Available"))
    except ImportError:
        status.append(("OpenTelemetry", False, "Not available"))

    return status
