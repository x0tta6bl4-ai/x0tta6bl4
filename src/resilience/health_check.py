"""
Health Check Implementation
===========================

Health check endpoints with graceful degradation support.
Implements health monitoring patterns for distributed systems.
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""
    check_interval_seconds: float = 30.0
    timeout_seconds: float = 5.0
    failure_threshold: int = 3
    success_threshold: int = 2
    parallel_checks: bool = True
    
    # Degradation thresholds
    degraded_latency_ms: float = 1000.0
    unhealthy_latency_ms: float = 5000.0
    
    # Callbacks
    on_status_change: Optional[Callable[[str, HealthStatus, HealthStatus], None]] = None
    on_degraded: Optional[Callable[[str, HealthCheckResult], None]] = None
    on_unhealthy: Optional[Callable[[str, HealthCheckResult], None]] = None


class HealthCheck(ABC):
    """Abstract base class for health checks."""
    
    def __init__(self, name: str, config: Optional[HealthCheckConfig] = None):
        self.name = name
        self.config = config or HealthCheckConfig()
        self._status = HealthStatus.UNKNOWN
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_result: Optional[HealthCheckResult] = None
    
    @property
    def status(self) -> HealthStatus:
        return self._status
    
    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """Perform the health check."""
        pass
    
    def _update_status(self, result: HealthCheckResult) -> None:
        """Update status based on result."""
        old_status = self._status
        
        if result.status == HealthStatus.HEALTHY:
            self._consecutive_failures = 0
            self._consecutive_successes += 1
            
            if self._consecutive_successes >= self.config.success_threshold:
                self._status = HealthStatus.HEALTHY
        
        elif result.status == HealthStatus.DEGRADED:
            self._consecutive_failures = 0
            self._status = HealthStatus.DEGRADED
            
            if self.config.on_degraded:
                self.config.on_degraded(self.name, result)
        
        else:  # UNHEALTHY
            self._consecutive_successes = 0
            self._consecutive_failures += 1
            
            if self._consecutive_failures >= self.config.failure_threshold:
                self._status = HealthStatus.UNHEALTHY
                
                if self.config.on_unhealthy:
                    self.config.on_unhealthy(self.name, result)
        
        # Notify status change
        if old_status != self._status and self.config.on_status_change:
            self.config.on_status_change(self.name, old_status, self._status)
        
        self._last_result = result


class HTTPHealthCheck(HealthCheck):
    """HTTP-based health check."""
    
    def __init__(
        self,
        name: str,
        url: str,
        expected_status: int = 200,
        expected_content: Optional[str] = None,
        config: Optional[HealthCheckConfig] = None,
    ):
        super().__init__(name, config)
        self.url = url
        self.expected_status = expected_status
        self.expected_content = expected_content
    
    async def check(self) -> HealthCheckResult:
        """Perform HTTP health check."""
        import aiohttp
        
        start_time = time.time()
        
        try:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(self.url) as response:
                    latency_ms = (time.time() - start_time) * 1000
                    
                    if response.status != self.expected_status:
                        result = HealthCheckResult(
                            name=self.name,
                            status=HealthStatus.UNHEALTHY,
                            message=f"Expected status {self.expected_status}, got {response.status}",
                            latency_ms=latency_ms,
                        )
                    elif self.expected_content:
                        content = await response.text()
                        if self.expected_content not in content:
                            result = HealthCheckResult(
                                name=self.name,
                                status=HealthStatus.UNHEALTHY,
                                message="Expected content not found",
                                latency_ms=latency_ms,
                            )
                        else:
                            result = HealthCheckResult(
                                name=self.name,
                                status=self._get_status_by_latency(latency_ms),
                                message="OK",
                                latency_ms=latency_ms,
                            )
                    else:
                        result = HealthCheckResult(
                            name=self.name,
                            status=self._get_status_by_latency(latency_ms),
                            message="OK",
                            latency_ms=latency_ms,
                        )
        
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Timeout",
                latency_ms=self.config.timeout_seconds * 1000,
            )
        
        except Exception as e:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
        
        self._update_status(result)
        return result
    
    def _get_status_by_latency(self, latency_ms: float) -> HealthStatus:
        """Determine status based on latency."""
        if latency_ms >= self.config.unhealthy_latency_ms:
            return HealthStatus.UNHEALTHY
        elif latency_ms >= self.config.degraded_latency_ms:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


class TCPHealthCheck(HealthCheck):
    """TCP-based health check."""
    
    def __init__(
        self,
        name: str,
        host: str,
        port: int,
        config: Optional[HealthCheckConfig] = None,
    ):
        super().__init__(name, config)
        self.host = host
        self.port = port
    
    async def check(self) -> HealthCheckResult:
        """Perform TCP health check."""
        start_time = time.time()
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.config.timeout_seconds,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            writer.close()
            await writer.wait_closed()
            
            result = HealthCheckResult(
                name=self.name,
                status=self._get_status_by_latency(latency_ms),
                message="Connection successful",
                latency_ms=latency_ms,
            )
        
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="Connection timeout",
            )
        
        except Exception as e:
            result = HealthCheckResult(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )
        
        self._update_status(result)
        return result
    
    def _get_status_by_latency(self, latency_ms: float) -> HealthStatus:
        """Determine status based on latency."""
        if latency_ms >= self.config.unhealthy_latency_ms:
            return HealthStatus.DEGRADED
        elif latency_ms >= self.config.degraded_latency_ms:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY


class HealthCheckEndpoint:
    """
    Aggregates multiple health checks and provides a unified endpoint.
    
    Features:
    - Multiple health check support
    - Parallel execution
    - Overall health aggregation
    - Graceful degradation tracking
    """
    
    def __init__(self, config: Optional[HealthCheckConfig] = None):
        self.config = config or HealthCheckConfig()
        self._checks: Dict[str, HealthCheck] = {}
        self._degraded_features: Set[str] = set()
        self._lock = threading.Lock()
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register_check(self, check: HealthCheck) -> None:
        """Register a health check."""
        self._checks[check.name] = check
    
    def unregister_check(self, name: str) -> None:
        """Unregister a health check."""
        self._checks.pop(name, None)
    
    async def run_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks."""
        if self.config.parallel_checks:
            tasks = {
                name: check.check()
                for name, check in self._checks.items()
            }
            results = {}
            for name, task in tasks.items():
                try:
                    results[name] = await task
                except Exception as e:
                    results[name] = HealthCheckResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=str(e),
                    )
        else:
            results = {}
            for name, check in self._checks.items():
                try:
                    results[name] = await check.check()
                except Exception as e:
                    results[name] = HealthCheckResult(
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=str(e),
                    )
        
        return results
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall health status."""
        if not self._checks:
            return HealthStatus.UNKNOWN
        
        statuses = [check.status for check in self._checks.values()]
        
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN
    
    async def start_periodic_checks(self) -> None:
        """Start periodic health checks."""
        self._running = True
        
        while self._running:
            try:
                await self.run_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            await asyncio.sleep(self.config.check_interval_seconds)
    
    def stop_periodic_checks(self) -> None:
        """Stop periodic health checks."""
        self._running = False
        if self._task:
            self._task.cancel()
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health report."""
        results = {
            name: check._last_result.to_dict() if check._last_result else None
            for name, check in self._checks.items()
        }
        
        return {
            "overall_status": self.get_overall_status().value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": results,
            "degraded_features": list(self._degraded_features),
        }


class GracefulDegradation:
    """
    Graceful degradation manager.
    
    Manages feature availability based on system health.
    """
    
    def __init__(self):
        self._features: Dict[str, Callable[[], bool]] = {}
        self._fallbacks: Dict[str, Callable] = {}
        self._degraded_features: Set[str] = set()
        self._lock = threading.Lock()
    
    def register_feature(
        self,
        name: str,
        health_check: Callable[[], bool],
        fallback: Optional[Callable] = None,
    ) -> None:
        """Register a feature with health check and optional fallback."""
        with self._lock:
            self._features[name] = health_check
            if fallback:
                self._fallbacks[name] = fallback
    
    def is_available(self, feature: str) -> bool:
        """Check if a feature is available."""
        with self._lock:
            if feature not in self._features:
                return False
            
            check = self._features[feature]
            try:
                available = check()
                if not available:
                    self._degraded_features.add(feature)
                else:
                    self._degraded_features.discard(feature)
                return available
            except Exception:
                self._degraded_features.add(feature)
                return False
    
    def execute(
        self,
        feature: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with graceful degradation."""
        if self.is_available(feature):
            return func(*args, **kwargs)
        
        # Feature unavailable - use fallback
        if feature in self._fallbacks:
            logger.warning(f"Feature '{feature}' unavailable, using fallback")
            return self._fallbacks[feature](*args, **kwargs)
        
        raise RuntimeError(f"Feature '{feature}' is unavailable")
    
    def get_degraded_features(self) -> List[str]:
        """Get list of degraded features."""
        with self._lock:
            return list(self._degraded_features)
    
    def clear_degraded(self, feature: str) -> None:
        """Clear degraded status for a feature."""
        with self._lock:
            self._degraded_features.discard(feature)


__all__ = [
    "HealthStatus",
    "HealthCheckResult",
    "HealthCheckConfig",
    "HealthCheck",
    "HTTPHealthCheck",
    "TCPHealthCheck",
    "HealthCheckEndpoint",
    "GracefulDegradation",
]
