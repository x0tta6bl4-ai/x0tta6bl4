"""
Health checks for eBPF components.

This module provides health check functionality for all eBPF components
to ensure they are functioning correctly and provide meaningful diagnostics.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from src.network.ebpf.loader import EBPFLoader
from src.network.ebpf.metrics_exporter import EBPFMetricsExporter
from src.network.ebpf.cilium_integration import CiliumLikeIntegration
from src.network.ebpf.dynamic_fallback import DynamicFallbackController
from src.network.ebpf.mape_k_integration import EBPFMAPEKIntegration
from src.network.ebpf.ringbuf_reader import RingBufferReader


logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    status: HealthStatus
    component: str
    message: str
    timestamp: float
    duration_ms: float
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "component": self.component,
            "message": self.message,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "details": self.details
        }


class EBPFHealthChecker:
    """Health checker for eBPF components."""

    def __init__(self,
                 loader: EBPFLoader,
                 metrics: EBPFMetricsExporter,
                 cilium: CiliumLikeIntegration,
                 fallback: DynamicFallbackController,
                 mapek: EBPFMAPEKIntegration,
                 ring_buffer: RingBufferReader,
                 check_interval: float = 5.0):
        """Initialize health checker with all eBPF components."""
        self.loader = loader
        self.metrics = metrics
        self.cilium = cilium
        self.fallback = fallback
        self.mapek = mapek
        self.ring_buffer = ring_buffer
        self.check_interval = check_interval
        self._last_check_time: float = 0.0
        self._health_cache: Dict[str, HealthCheckResult] = {}
        self._lock = asyncio.Lock()

    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """
        Perform health check on all eBPF components.

        Returns:
            Dictionary mapping component name to HealthCheckResult.
        """
        async with self._lock:
            start_time = time.time()
            logger.debug("Starting health check for all eBPF components")

            results = await asyncio.gather(
                self.check_loader(),
                self.check_metrics(),
                self.check_cilium(),
                self.check_fallback(),
                self.check_mapek(),
                self.check_ring_buffer(),
                return_exceptions=True
            )

            components = ["loader", "metrics", "cilium", "fallback", "mapek", "ring_buffer"]
            health_results: Dict[str, HealthCheckResult] = {}

            for component, result in zip(components, results):
                if isinstance(result, Exception):
                    health_results[component] = HealthCheckResult(
                        status=HealthStatus.UNHEALTHY,
                        component=component,
                        message=f"Health check failed: {str(result)}",
                        timestamp=start_time,
                        duration_ms=(time.time() - start_time) * 1000,
                        details={"exception": str(result)}
                    )
                    logger.error(f"Health check failed for {component}: {result}")
                else:
                    health_results[component] = result

            # Update cache
            self._health_cache = health_results
            self._last_check_time = start_time

            logger.debug(f"Health check completed in {(time.time() - start_time)*1000:.2f}ms")
            return health_results

    async def check_loader(self) -> HealthCheckResult:
        """Check health of EBPFLoader."""
        start_time = time.time()

        try:
            loaded_programs = self.loader.list_loaded_programs()
            program_count = len(loaded_programs)

            if program_count == 0:
                status = HealthStatus.DEGRADED
                message = "No eBPF programs loaded"
            else:
                status = HealthStatus.HEALTHY
                message = f"Loaded {program_count} eBPF programs"

            details = {
                "program_count": program_count,
                "programs": [p["id"] for p in loaded_programs],
                "interfaces": list(self.loader.attached_interfaces.keys())
            }

            return HealthCheckResult(
                status=status,
                component="loader",
                message=message,
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details=details
            )

        except Exception as e:
            logger.error(f"Loader health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="loader",
                message=f"Health check failed: {str(e)}",
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details={"exception": str(e)}
            )

    async def check_metrics(self) -> HealthCheckResult:
        """Check health of EBPFMetricsExporter."""
        start_time = time.time()

        try:
            summary = self.metrics.get_metrics_summary()
            degradation = self.metrics.get_degradation_status()

            if not degradation.get("prometheus_available", False):
                status = HealthStatus.DEGRADED
                message = "Prometheus metrics not available"
            elif degradation.get("consecutive_failures", 0) > 3:
                status = HealthStatus.DEGRADED
                message = f"Metrics collection failing ({degradation['consecutive_failures']} consecutive failures)"
            else:
                status = HealthStatus.HEALTHY
                message = f"Metrics exporter healthy (degradation: {degradation['level']})"

            details = {
                "registered_maps": summary.get("registered_maps", 0),
                "prometheus_metrics": summary.get("prometheus_metrics", 0),
                "degradation_level": degradation.get("level"),
                "prometheus_available": degradation.get("prometheus_available"),
                "bpftool_available": degradation.get("bpftool_available"),
                "total_errors": degradation.get("total_errors", 0),
                "consecutive_failures": degradation.get("consecutive_failures", 0)
            }

            return HealthCheckResult(
                status=status,
                component="metrics",
                message=message,
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details=details
            )

        except Exception as e:
            logger.error(f"Metrics health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="metrics",
                message=f"Health check failed: {str(e)}",
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details={"exception": str(e)}
            )

    async def check_cilium(self) -> HealthCheckResult:
        """Check health of CiliumLikeIntegration."""
        start_time = time.time()

        try:
            # Check if flow metrics are available
            flow_metrics = self.cilium.get_flow_metrics()

            if not flow_metrics.get("flows"):
                status = HealthStatus.DEGRADED
                message = "No network flow metrics available"
            else:
                status = HealthStatus.HEALTHY
                message = f"Flow metrics available ({len(flow_metrics['flows'])} active flows)"

            details = {
                "flow_count": len(flow_metrics.get("flows", [])),
                "interfaces": flow_metrics.get("interfaces", [])
            }

            return HealthCheckResult(
                status=status,
                component="cilium",
                message=message,
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details=details
            )

        except Exception as e:
            logger.error(f"Cilium health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="cilium",
                message=f"Health check failed: {str(e)}",
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details={"exception": str(e)}
            )

    async def check_fallback(self) -> HealthCheckResult:
        """Check health of DynamicFallbackController."""
        start_time = time.time()

        try:
            status = self.fallback.get_status()

            if status.get("active_fallback", False):
                status_level = HealthStatus.DEGRADED
                message = "Dynamic fallback mechanism active"
            else:
                status_level = HealthStatus.HEALTHY
                message = "Dynamic fallback mechanism idle"

            details = {
                "active_fallback": status.get("active_fallback", False),
                "fallback_count": status.get("fallback_count", 0),
                "last_fallback_time": status.get("last_fallback_time"),
                "available_interfaces": status.get("available_interfaces", []),
                "unavailable_interfaces": status.get("unavailable_interfaces", [])
            }

            return HealthCheckResult(
                status=status_level,
                component="fallback",
                message=message,
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details=details
            )

        except Exception as e:
            logger.error(f"Fallback health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="fallback",
                message=f"Health check failed: {str(e)}",
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details={"exception": str(e)}
            )

    async def check_mapek(self) -> HealthCheckResult:
        """Check health of EBPFMAPEKIntegration."""
        start_time = time.time()

        try:
            # Check if MAPE-K integration is operational
            if hasattr(self.mapek, "is_operational"):
                operational = self.mapek.is_operational()
            else:
                # If no explicit method, assume operational
                operational = True

            if operational:
                status = HealthStatus.HEALTHY
                message = "MAPE-K integration operational"
            else:
                status = HealthStatus.DEGRADED
                message = "MAPE-K integration non-operational"

            details = {
                "operational": operational
            }

            return HealthCheckResult(
                status=status,
                component="mapek",
                message=message,
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details=details
            )

        except Exception as e:
            logger.error(f"MAPE-K health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="mapek",
                message=f"Health check failed: {str(e)}",
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details={"exception": str(e)}
            )

    async def check_ring_buffer(self) -> HealthCheckResult:
        """Check health of RingBufferReader."""
        start_time = time.time()

        try:
            # Check if ring buffer is active and running
            if hasattr(self.ring_buffer, "running"):
                is_running = self.ring_buffer.running
            else:
                # If no running attribute, check basic functionality
                is_running = True

            if is_running:
                status = HealthStatus.HEALTHY
                message = "Ring buffer reader active"
            else:
                status = HealthStatus.DEGRADED
                message = "Ring buffer reader inactive"

            details = {
                "running": is_running,
                "event_handlers": len(getattr(self.ring_buffer, "event_handlers", {}))
            }

            return HealthCheckResult(
                status=status,
                component="ring_buffer",
                message=message,
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details=details
            )

        except Exception as e:
            logger.error(f"Ring buffer health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component="ring_buffer",
                message=f"Health check failed: {str(e)}",
                timestamp=start_time,
                duration_ms=(time.time() - start_time) * 1000,
                details={"exception": str(e)}
            )

    async def check_and_report(self) -> Dict[str, Any]:
        """
        Check health and generate report for Prometheus.

        Returns:
            Dictionary with health metrics for Prometheus.
        """
        results = await self.check_all()

        # Convert results to Prometheus-compatible format
        health_metrics = {
            "ebpf_health_total": len(results),
            "ebpf_health_healthy": sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY),
            "ebpf_health_degraded": sum(1 for r in results.values() if r.status == HealthStatus.DEGRADED),
            "ebpf_health_unhealthy": sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY)
        }

        # Per-component health metrics
        for component, result in results.items():
            health_metrics[f"ebpf_health_{component}"] = {
                "status": result.status.value,
                "message": result.message,
                "details": result.details
            }

        return health_metrics

    def get_cache(self) -> Dict[str, HealthCheckResult]:
        """Get cached health check results."""
        return self._health_cache.copy()

    def get_last_check_time(self) -> float:
        """Get timestamp of last health check."""
        return self._last_check_time


# Add health check methods to existing components
def add_health_check_methods():
    """Monkey-patch health check methods into existing eBPF components."""

    # Add is_healthy method to EBPFLoader
    def loader_is_healthy(self):
        try:
            programs = self.list_loaded_programs()
            return len(programs) > 0
        except Exception:
            return False

    EBPFLoader.is_healthy = loader_is_healthy

    # Add health check method to EBPFMetricsExporter
    def metrics_is_healthy(self):
        try:
            degradation = self.get_degradation_status()
            return (degradation.get("prometheus_available", False) and
                    degradation.get("consecutive_failures", 0) <= 3)
        except Exception:
            return False

    EBPFMetricsExporter.is_healthy = metrics_is_healthy

    # Add health check method to CiliumLikeIntegration
    def cilium_is_healthy(self):
        try:
            flow_metrics = self.get_flow_metrics()
            return len(flow_metrics.get("flows", [])) > 0
        except Exception:
            return False

    CiliumLikeIntegration.is_healthy = cilium_is_healthy

    # Add health check method to DynamicFallbackController
    def fallback_is_healthy(self):
        try:
            status = self.get_status()
            return not status.get("active_fallback", False)
        except Exception:
            return False

    DynamicFallbackController.is_healthy = fallback_is_healthy

    # Add health check method to EBPFMAPEKIntegration
    def mapek_is_healthy(self):
        try:
            return hasattr(self, "is_operational") and self.is_operational()
        except Exception:
            return False

    EBPFMAPEKIntegration.is_healthy = mapek_is_healthy

    # Add health check method to RingBufferReader
    def ring_buffer_is_healthy(self):
        try:
            return hasattr(self, "running") and self.running
        except Exception:
            return False

    RingBufferReader.is_healthy = ring_buffer_is_healthy


# Apply monkey patches when module is imported
add_health_check_methods()