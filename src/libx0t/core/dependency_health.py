"""
Dependency Health Checks for x0tta6bl4

Provides comprehensive health checks for all optional dependencies
with graceful degradation status reporting.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

PRODUCTION_MODE = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"


class DependencyStatus(Enum):
    """Status of a dependency"""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    REQUIRED = "required"  # Required in production, but missing


@dataclass
class DependencyInfo:
    """Information about a dependency"""

    name: str
    status: DependencyStatus
    version: Optional[str] = None
    reason: Optional[str] = None
    required_in_production: bool = False
    graceful_degradation: bool = False


class DependencyHealthChecker:
    """
    Comprehensive health checker for all dependencies.

    Checks availability of optional dependencies and reports
    graceful degradation status.
    """

    def __init__(self):
        self.dependencies: Dict[str, DependencyInfo] = {}
        self._check_all_dependencies()

    def _check_all_dependencies(self):
        """Check all dependencies and populate status"""
        # Post-Quantum Cryptography
        self._check_liboqs()

        # SPIFFE/SPIRE
        self._check_spiffe()

        # eBPF
        self._check_ebpf()

        # Machine Learning
        self._check_torch()
        self._check_hnsw()
        self._check_sentence_transformers()

        # OpenTelemetry
        self._check_opentelemetry()

        # Blockchain & Web3
        self._check_web3()
        self._check_ipfs()

        # Prometheus
        self._check_prometheus()

        # Federated Learning
        self._check_flwr()

    def _check_liboqs(self):
        """Check liboqs-python availability"""
        try:
            import oqs
            from oqs import KeyEncapsulation, Signature

            version = getattr(oqs, "__version__", "unknown")

            self.dependencies["liboqs"] = DependencyInfo(
                name="liboqs-python",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=True,
                graceful_degradation=False,
            )
        except (ImportError, RuntimeError) as e:
            status = (
                DependencyStatus.REQUIRED
                if PRODUCTION_MODE
                else DependencyStatus.UNAVAILABLE
            )

            self.dependencies["liboqs"] = DependencyInfo(
                name="liboqs-python",
                status=status,
                reason=str(e),
                required_in_production=True,
                graceful_degradation=True,
            )

            if PRODUCTION_MODE:
                logger.critical(
                    "🔴 PRODUCTION MODE: liboqs-python REQUIRED but not available!\n"
                    f"Error: {type(e).__name__}: {e}\n"
                    "Install: pip install liboqs-python"
                )
            else:
                logger.warning(f"⚠️ liboqs-python not available: {e}")

    def _check_spiffe(self):
        """Check SPIFFE/SPIRE availability"""
        try:
            import spiffe

            version = getattr(spiffe, "__version__", "unknown")

            self.dependencies["spiffe"] = DependencyInfo(
                name="py-spiffe",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["spiffe"] = DependencyInfo(
                name="py-spiffe",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.warning(f"⚠️ py-spiffe not available: {e}")

    def _check_ebpf(self):
        """Check eBPF kernel support"""
        try:
            # Check if eBPF is available via kernel
            import subprocess

            result = subprocess.run(
                ["bpftool", "version"], capture_output=True, text=True, timeout=2
            )

            if result.returncode == 0:
                self.dependencies["ebpf"] = DependencyInfo(
                    name="eBPF",
                    status=DependencyStatus.AVAILABLE,
                    version="kernel",
                    required_in_production=False,
                    graceful_degradation=True,
                )
            else:
                raise FileNotFoundError("bpftool not found")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            self.dependencies["ebpf"] = DependencyInfo(
                name="eBPF",
                status=DependencyStatus.UNAVAILABLE,
                reason="Kernel eBPF support or bpftool not available",
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"eBPF not available: {e}")

    def _check_torch(self):
        """Check PyTorch availability"""
        try:
            import torch

            version = torch.__version__

            self.dependencies["torch"] = DependencyInfo(
                name="torch",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["torch"] = DependencyInfo(
                name="torch",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"torch not available: {e}")

    def _check_hnsw(self):
        """Check HNSW availability"""
        try:
            import hnswlib

            version = getattr(hnswlib, "__version__", "unknown")

            self.dependencies["hnsw"] = DependencyInfo(
                name="hnswlib",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["hnsw"] = DependencyInfo(
                name="hnswlib",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"hnswlib not available: {e}")

    def _check_sentence_transformers(self):
        """Check sentence-transformers availability"""
        try:
            import sentence_transformers

            version = sentence_transformers.__version__

            self.dependencies["sentence_transformers"] = DependencyInfo(
                name="sentence-transformers",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["sentence_transformers"] = DependencyInfo(
                name="sentence-transformers",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"sentence-transformers not available: {e}")

    def _check_opentelemetry(self):
        """Check OpenTelemetry availability"""
        try:
            import opentelemetry
            from opentelemetry import trace

            version = getattr(opentelemetry, "__version__", "unknown")

            self.dependencies["opentelemetry"] = DependencyInfo(
                name="opentelemetry",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["opentelemetry"] = DependencyInfo(
                name="opentelemetry",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"opentelemetry not available: {e}")

    def _check_web3(self):
        """Check Web3 availability"""
        try:
            import web3

            version = web3.__version__

            self.dependencies["web3"] = DependencyInfo(
                name="web3",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["web3"] = DependencyInfo(
                name="web3",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"web3 not available: {e}")

    def _check_ipfs(self):
        """Check IPFS client availability"""
        try:
            import ipfshttpclient

            version = getattr(ipfshttpclient, "__version__", "unknown")

            self.dependencies["ipfs"] = DependencyInfo(
                name="ipfshttpclient",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["ipfs"] = DependencyInfo(
                name="ipfshttpclient",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"ipfshttpclient not available: {e}")

    def _check_prometheus(self):
        """Check Prometheus client availability"""
        try:
            import prometheus_client
            from prometheus_client import Counter

            version = getattr(prometheus_client, "__version__", "unknown")

            self.dependencies["prometheus"] = DependencyInfo(
                name="prometheus-client",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["prometheus"] = DependencyInfo(
                name="prometheus-client",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"prometheus-client not available: {e}")

    def _check_flwr(self):
        """Check Flower (Federated Learning) availability"""
        try:
            import flwr

            version = flwr.__version__

            self.dependencies["flwr"] = DependencyInfo(
                name="flwr",
                status=DependencyStatus.AVAILABLE,
                version=version,
                required_in_production=False,
                graceful_degradation=True,
            )
        except ImportError as e:
            self.dependencies["flwr"] = DependencyInfo(
                name="flwr",
                status=DependencyStatus.UNAVAILABLE,
                reason=str(e),
                required_in_production=False,
                graceful_degradation=True,
            )
            logger.debug(f"flwr not available: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of all dependencies.

        Returns:
            Dictionary with dependency status information
        """
        status = {
            "overall_status": "healthy",
            "production_mode": PRODUCTION_MODE,
            "dependencies": {},
        }

        critical_issues = []
        warnings = []

        for key, dep in self.dependencies.items():
            dep_status = {
                "name": dep.name,
                "status": dep.status.value,
                "version": dep.version,
                "required_in_production": dep.required_in_production,
                "graceful_degradation": dep.graceful_degradation,
            }

            if dep.reason:
                dep_status["reason"] = dep.reason

            status["dependencies"][key] = dep_status

            # Check for critical issues
            if dep.status == DependencyStatus.REQUIRED:
                critical_issues.append(
                    f"{dep.name} is required in production but unavailable"
                )
                status["overall_status"] = "unhealthy"
            elif (
                dep.status == DependencyStatus.UNAVAILABLE
                and dep.required_in_production
            ):
                warnings.append(
                    f"{dep.name} is unavailable (graceful degradation active)"
                )

        if critical_issues:
            status["critical_issues"] = critical_issues

        if warnings:
            status["warnings"] = warnings

        return status

    def is_healthy(self) -> bool:
        """
        Check if system is healthy (no critical missing dependencies).

        Returns:
            True if healthy, False if critical dependencies are missing
        """
        for dep in self.dependencies.values():
            if dep.status == DependencyStatus.REQUIRED:
                return False
        return True

    def get_degraded_features(self) -> list:
        """
        Get list of features that are degraded due to missing dependencies.

        Returns:
            List of feature names that are degraded
        """
        degraded = []
        for key, dep in self.dependencies.items():
            if dep.status == DependencyStatus.UNAVAILABLE and dep.graceful_degradation:
                degraded.append(key)
        return degraded


# Global instance
_health_checker: Optional[DependencyHealthChecker] = None


def get_dependency_health_checker() -> DependencyHealthChecker:
    """Get or create global dependency health checker instance"""
    global _health_checker
    if _health_checker is None:
        _health_checker = DependencyHealthChecker()
    return _health_checker


def check_dependencies_health() -> Dict[str, Any]:
    """Convenience function to check dependency health"""
    return get_dependency_health_checker().get_health_status()
