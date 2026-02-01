"""
Enhanced Health Check Endpoint

Provides detailed health status including:
- Application status
- Database connectivity
- Redis cache connectivity
- External service status
- Resource utilization
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any, Callable
from datetime import datetime

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health check status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    status: HealthStatus
    latency_ms: float
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "message": self.message,
            "details": self.details,
        }


@dataclass
class HealthCheckResponse:
    """Complete health check response."""
    status: HealthStatus
    version: str
    timestamp: str
    uptime_seconds: float
    checks: List[CheckResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "version": self.version,
            "timestamp": self.timestamp,
            "uptime_seconds": round(self.uptime_seconds, 2),
            "checks": [c.to_dict() for c in self.checks],
        }


class HealthChecker:
    """
    Health checker with configurable dependency checks.

    Usage:
        checker = HealthChecker(version="3.1.0")
        checker.add_check("database", check_database)
        checker.add_check("redis", check_redis)

        result = await checker.run_all_checks()
    """

    def __init__(self, version: str = "3.1.0"):
        self.version = version
        self.start_time = time.time()
        self._checks: Dict[str, Callable] = {}

    def add_check(self, name: str, check_fn: Callable):
        """Add a health check function."""
        self._checks[name] = check_fn

    async def run_check(self, name: str, check_fn: Callable) -> CheckResult:
        """Run a single health check with timing."""
        start = time.time()
        try:
            result = await check_fn()
            latency = (time.time() - start) * 1000

            if isinstance(result, CheckResult):
                result.latency_ms = latency
                return result

            # Simple boolean result
            return CheckResult(
                name=name,
                status=HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY,
                latency_ms=latency,
            )
        except Exception as e:
            latency = (time.time() - start) * 1000
            logger.warning(f"Health check '{name}' failed: {e}")
            return CheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                latency_ms=latency,
                message=str(e),
            )

    async def run_all_checks(self, timeout: float = 5.0) -> HealthCheckResponse:
        """Run all health checks with timeout."""
        tasks = [
            self.run_check(name, check_fn)
            for name, check_fn in self._checks.items()
        ]

        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            results = [
                CheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=timeout * 1000,
                    message="Check timed out",
                )
                for name in self._checks
            ]

        # Process results
        check_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                name = list(self._checks.keys())[i]
                check_results.append(CheckResult(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0,
                    message=str(result),
                ))
            else:
                check_results.append(result)

        # Determine overall status
        statuses = [r.status for r in check_results]
        if all(s == HealthStatus.HEALTHY for s in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            overall_status = HealthStatus.UNHEALTHY
        else:
            overall_status = HealthStatus.DEGRADED

        return HealthCheckResponse(
            status=overall_status,
            version=self.version,
            timestamp=datetime.utcnow().isoformat() + "Z",
            uptime_seconds=time.time() - self.start_time,
            checks=check_results,
        )


# Default health check functions

async def check_database() -> CheckResult:
    """Check database connectivity."""
    try:
        from src.database import SessionLocal

        start = time.time()
        db = SessionLocal()
        try:
            # Simple query to test connection
            db.execute("SELECT 1")
            latency = (time.time() - start) * 1000

            return CheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message="Connected",
                details={"type": "postgresql/sqlite"}
            )
        finally:
            db.close()
    except Exception as e:
        return CheckResult(
            name="database",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message=f"Connection failed: {e}",
        )


async def check_redis() -> CheckResult:
    """Check Redis connectivity."""
    try:
        from src.core.cache import cache

        start = time.time()
        await cache.set("health_check", "ok", ttl=10)
        result = await cache.get("health_check")
        latency = (time.time() - start) * 1000

        if result == "ok":
            return CheckResult(
                name="redis",
                status=HealthStatus.HEALTHY,
                latency_ms=latency,
                message="Connected",
            )
        else:
            return CheckResult(
                name="redis",
                status=HealthStatus.DEGRADED,
                latency_ms=latency,
                message="Cache read/write mismatch",
            )
    except Exception as e:
        return CheckResult(
            name="redis",
            status=HealthStatus.UNHEALTHY,
            latency_ms=0,
            message=f"Connection failed: {e}",
        )


async def check_vpn_server() -> CheckResult:
    """Check VPN server connectivity."""
    server = os.getenv("VPN_SERVER", "")
    port = int(os.getenv("VPN_PORT", "0")) or 0

    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port),
            timeout=2.0
        )
        writer.close()
        await writer.wait_closed()
        latency = (time.time() - start) * 1000

        return CheckResult(
            name="vpn_server",
            status=HealthStatus.HEALTHY,
            latency_ms=latency,
            message="Online",
            details={"server": server, "port": port}
        )
    except Exception as e:
        return CheckResult(
            name="vpn_server",
            status=HealthStatus.DEGRADED,
            latency_ms=0,
            message=f"Unreachable: {e}",
            details={"server": server, "port": port}
        )


async def check_memory() -> CheckResult:
    """Check memory usage."""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_percent = process.memory_percent()

        status = HealthStatus.HEALTHY
        if memory_percent > 90:
            status = HealthStatus.UNHEALTHY
        elif memory_percent > 80:
            status = HealthStatus.DEGRADED

        return CheckResult(
            name="memory",
            status=status,
            latency_ms=0,
            message=f"{memory_percent:.1f}% used",
            details={
                "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
                "percent": round(memory_percent, 2),
            }
        )
    except Exception as e:
        return CheckResult(
            name="memory",
            status=HealthStatus.HEALTHY,  # Non-critical
            latency_ms=0,
            message=f"Check unavailable: {e}",
        )


async def check_disk() -> CheckResult:
    """Check disk usage."""
    try:
        import psutil
        disk = psutil.disk_usage('/')

        status = HealthStatus.HEALTHY
        if disk.percent > 95:
            status = HealthStatus.UNHEALTHY
        elif disk.percent > 85:
            status = HealthStatus.DEGRADED

        return CheckResult(
            name="disk",
            status=status,
            latency_ms=0,
            message=f"{disk.percent:.1f}% used",
            details={
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2),
            }
        )
    except Exception as e:
        return CheckResult(
            name="disk",
            status=HealthStatus.HEALTHY,  # Non-critical
            latency_ms=0,
            message=f"Check unavailable: {e}",
        )


# Global health checker instance
health_checker = HealthChecker(version="3.1.0")

# Register default checks
health_checker.add_check("database", check_database)
health_checker.add_check("redis", check_redis)
health_checker.add_check("vpn_server", check_vpn_server)
health_checker.add_check("memory", check_memory)
health_checker.add_check("disk", check_disk)


async def get_health_status() -> HealthCheckResponse:
    """Get complete health status."""
    return await health_checker.run_all_checks()


async def get_liveness() -> Dict[str, Any]:
    """Simple liveness probe (is the app running?)."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


async def get_readiness() -> Dict[str, Any]:
    """Readiness probe (is the app ready to serve traffic?)."""
    result = await health_checker.run_all_checks(timeout=3.0)

    # Consider unhealthy dependencies as not ready
    critical_checks = ["database"]
    for check in result.checks:
        if check.name in critical_checks and check.status == HealthStatus.UNHEALTHY:
            return {
                "status": "not_ready",
                "reason": f"{check.name} is unhealthy: {check.message}",
            }

    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


__all__ = [
    "HealthChecker",
    "HealthStatus",
    "CheckResult",
    "HealthCheckResponse",
    "health_checker",
    "get_health_status",
    "get_liveness",
    "get_readiness",
]
