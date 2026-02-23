"""
Batman-adv Health Monitor
=========================

Comprehensive health monitoring for Batman-adv mesh nodes.
Provides health checks, anomaly detection, and integration with MAPE-K loop.

Features:
- Node health scoring
- Link quality monitoring
- Connectivity verification
- Automatic failover detection
- Prometheus metrics export
"""

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels for Batman nodes."""
    
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class HealthCheckType(Enum):
    """Types of health checks."""
    
    CONNECTIVITY = "connectivity"
    LINK_QUALITY = "link_quality"
    ORIGINATOR_TABLE = "originator_table"
    GATEWAY = "gateway"
    INTERFACE = "interface"
    ROUTING = "routing"


@dataclass
class HealthCheckResult:
    """Result of a single health check."""
    
    check_type: HealthCheckType
    status: HealthStatus
    score: float  # 0.0 - 1.0
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0


@dataclass
class NodeHealthReport:
    """Complete health report for a Batman node."""
    
    node_id: str
    overall_status: HealthStatus
    overall_score: float
    checks: List[HealthCheckResult] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "node_id": self.node_id,
            "overall_status": self.overall_status.value,
            "overall_score": self.overall_score,
            "checks": [
                {
                    "type": c.check_type.value,
                    "status": c.status.value,
                    "score": c.score,
                    "message": c.message,
                    "details": c.details,
                    "timestamp": c.timestamp.isoformat(),
                    "duration_ms": c.duration_ms,
                }
                for c in self.checks
            ],
            "recommendations": self.recommendations,
            "timestamp": self.timestamp.isoformat(),
        }


class BatmanHealthMonitor:
    """
    Comprehensive health monitor for Batman-adv mesh nodes.
    
    Performs periodic health checks and provides:
    - Node health scoring
    - Link quality assessment
    - Connectivity verification
    - Integration with MAPE-K for autonomous healing
    
    Example:
        >>> monitor = BatmanHealthMonitor(node_id="node-001")
        >>> report = await monitor.run_health_checks()
        >>> print(f"Node health: {report.overall_status.value}")
    """
    
    # Health thresholds
    HEALTHY_THRESHOLD = 0.8
    DEGRADED_THRESHOLD = 0.5
    
    # Check timeouts
    CHECK_TIMEOUT_SECONDS = 5.0
    
    def __init__(
        self,
        node_id: str,
        interface: str = "bat0",
        check_interval: float = 30.0,
        enable_prometheus: bool = True,
        alert_callback: Optional[Callable[[NodeHealthReport], None]] = None,
    ):
        """
        Initialize Batman health monitor.
        
        Args:
            node_id: Unique identifier for this node
            interface: Batman-adv interface name
            check_interval: Interval between health checks in seconds
            enable_prometheus: Enable Prometheus metrics export
            alert_callback: Callback for health alerts
        """
        self.node_id = node_id
        self.interface = interface
        self.check_interval = check_interval
        self.enable_prometheus = enable_prometheus
        self.alert_callback = alert_callback
        
        self._running = False
        self._last_report: Optional[NodeHealthReport] = None
        self._health_history: List[NodeHealthReport] = []
        self._max_history_size = 100
        
        # Health check functions
        self._health_checks: Dict[HealthCheckType, Callable] = {
            HealthCheckType.CONNECTIVITY: self._check_connectivity,
            HealthCheckType.LINK_QUALITY: self._check_link_quality,
            HealthCheckType.ORIGINATOR_TABLE: self._check_originator_table,
            HealthCheckType.GATEWAY: self._check_gateway,
            HealthCheckType.INTERFACE: self._check_interface,
            HealthCheckType.ROUTING: self._check_routing,
        }
        
        # Custom health checks
        self._custom_checks: Dict[str, Callable] = {}
        
        # Prometheus metrics
        if self.enable_prometheus:
            self._init_prometheus_metrics()
        
        logger.info(f"BatmanHealthMonitor initialized for {node_id} on {interface}")
    
    def _init_prometheus_metrics(self):
        """Initialize Prometheus metrics."""
        try:
            from prometheus_client import Counter, Gauge, Histogram
            
            self._metrics = {
                "health_score": Gauge(
                    "batman_node_health_score",
                    "Overall health score of Batman node",
                    ["node_id"],
                    registry=None,
                ),
                "health_status": Gauge(
                    "batman_node_health_status",
                    "Health status (1=healthy, 0.5=degraded, 0=unhealthy)",
                    ["node_id"],
                    registry=None,
                ),
                "check_duration": Histogram(
                    "batman_health_check_duration_seconds",
                    "Duration of health checks",
                    ["node_id", "check_type"],
                    registry=None,
                ),
                "checks_total": Counter(
                    "batman_health_checks_total",
                    "Total number of health checks performed",
                    ["node_id", "status"],
                    registry=None,
                ),
                "originators_count": Gauge(
                    "batman_originators_count",
                    "Number of originators in Batman mesh",
                    ["node_id"],
                    registry=None,
                ),
                "links_count": Gauge(
                    "batman_links_count",
                    "Number of active links",
                    ["node_id"],
                    registry=None,
                ),
            }
        except ImportError:
            logger.warning("Prometheus client not available, metrics disabled")
            self.enable_prometheus = False
            self._metrics = {}
    
    def register_custom_check(self, name: str, check_fn: Callable) -> None:
        """
        Register a custom health check.
        
        Args:
            name: Unique name for the check
            check_fn: Async function that returns HealthCheckResult
        """
        self._custom_checks[name] = check_fn
        logger.info(f"Registered custom health check: {name}")
    
    async def run_health_checks(self) -> NodeHealthReport:
        """
        Run all health checks and generate a report.
        
        Returns:
            NodeHealthReport with all check results
        """
        start_time = time.time()
        checks: List[HealthCheckResult] = []
        
        # Run standard health checks
        for check_type, check_fn in self._health_checks.items():
            try:
                check_start = time.time()
                result = await asyncio.wait_for(
                    check_fn(),
                    timeout=self.CHECK_TIMEOUT_SECONDS
                )
                result.duration_ms = (time.time() - check_start) * 1000
                checks.append(result)
                
                # Record Prometheus metrics
                if self.enable_prometheus and "check_duration" in self._metrics:
                    self._metrics["check_duration"].labels(
                        node_id=self.node_id,
                        check_type=check_type.value
                    ).observe(result.duration_ms / 1000)
                    
            except asyncio.TimeoutError:
                checks.append(HealthCheckResult(
                    check_type=check_type,
                    status=HealthStatus.UNKNOWN,
                    score=0.0,
                    message=f"Health check timed out after {self.CHECK_TIMEOUT_SECONDS}s",
                    duration_ms=self.CHECK_TIMEOUT_SECONDS * 1000,
                ))
            except Exception as e:
                logger.error(f"Health check {check_type.value} failed: {e}")
                checks.append(HealthCheckResult(
                    check_type=check_type,
                    status=HealthStatus.UNKNOWN,
                    score=0.0,
                    message=f"Health check error: {str(e)}",
                ))
        
        # Run custom health checks
        for name, check_fn in self._custom_checks.items():
            try:
                result = await asyncio.wait_for(
                    check_fn(),
                    timeout=self.CHECK_TIMEOUT_SECONDS
                )
                checks.append(result)
            except Exception as e:
                logger.error(f"Custom health check {name} failed: {e}")
        
        # Calculate overall score and status
        overall_score = self._calculate_overall_score(checks)
        overall_status = self._determine_status(overall_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(checks)
        
        # Create report
        report = NodeHealthReport(
            node_id=self.node_id,
            overall_status=overall_status,
            overall_score=overall_score,
            checks=checks,
            recommendations=recommendations,
        )
        
        # Store report
        self._last_report = report
        self._health_history.append(report)
        if len(self._health_history) > self._max_history_size:
            self._health_history.pop(0)
        
        # Update Prometheus metrics
        if self.enable_prometheus:
            self._update_prometheus_metrics(report)
        
        # Trigger alert callback if unhealthy
        if overall_status == HealthStatus.UNHEALTHY and self.alert_callback:
            try:
                self.alert_callback(report)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
        
        duration = time.time() - start_time
        logger.info(
            f"Health check completed: {overall_status.value} "
            f"(score: {overall_score:.2f}, duration: {duration:.2f}s)"
        )
        
        return report
    
    def _calculate_overall_score(self, checks: List[HealthCheckResult]) -> float:
        """Calculate overall health score from all checks."""
        if not checks:
            return 0.0
        
        # Weight different check types
        weights = {
            HealthCheckType.CONNECTIVITY: 2.0,
            HealthCheckType.LINK_QUALITY: 1.5,
            HealthCheckType.ORIGINATOR_TABLE: 1.0,
            HealthCheckType.GATEWAY: 1.0,
            HealthCheckType.INTERFACE: 1.5,
            HealthCheckType.ROUTING: 1.0,
        }
        
        total_weight = 0.0
        weighted_score = 0.0
        
        for check in checks:
            weight = weights.get(check.check_type, 1.0)
            weighted_score += check.score * weight
            total_weight += weight
        
        return weighted_score / total_weight if total_weight > 0 else 0.0
    
    def _determine_status(self, score: float) -> HealthStatus:
        """Determine health status from score."""
        if score >= self.HEALTHY_THRESHOLD:
            return HealthStatus.HEALTHY
        elif score >= self.DEGRADED_THRESHOLD:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNHEALTHY
    
    def _generate_recommendations(self, checks: List[HealthCheckResult]) -> List[str]:
        """Generate recommendations based on health check results."""
        recommendations = []
        
        for check in checks:
            if check.status == HealthStatus.UNHEALTHY:
                if check.check_type == HealthCheckType.CONNECTIVITY:
                    recommendations.append(
                        "Check network connectivity and interface status"
                    )
                elif check.check_type == HealthCheckType.LINK_QUALITY:
                    recommendations.append(
                        "Investigate link quality issues - consider node repositioning"
                    )
                elif check.check_type == HealthCheckType.ORIGINATOR_TABLE:
                    recommendations.append(
                        "Verify Batman-adv daemon is running correctly"
                    )
                elif check.check_type == HealthCheckType.GATEWAY:
                    recommendations.append(
                        "Check gateway connectivity or select alternative gateway"
                    )
                elif check.check_type == HealthCheckType.INTERFACE:
                    recommendations.append(
                        "Verify Batman-adv interface configuration"
                    )
                elif check.check_type == HealthCheckType.ROUTING:
                    recommendations.append(
                        "Check routing table and originator entries"
                    )
        
        return list(set(recommendations))  # Remove duplicates
    
    async def _check_connectivity(self) -> HealthCheckResult:
        """Check basic connectivity through Batman mesh."""
        try:
            # Try to ping known originators
            originators = await self._get_originators()
            
            if not originators:
                return HealthCheckResult(
                    check_type=HealthCheckType.CONNECTIVITY,
                    status=HealthStatus.UNHEALTHY,
                    score=0.0,
                    message="No originators found in mesh",
                    details={"originators_count": 0},
                )
            
            # Check if we can reach at least one originator
            reachable = 0
            for orig in originators[:3]:  # Check first 3
                if await self._ping_originator(orig):
                    reachable += 1
            
            score = reachable / min(len(originators), 3)
            status = self._determine_status(score)
            
            return HealthCheckResult(
                check_type=HealthCheckType.CONNECTIVITY,
                status=status,
                score=score,
                message=f"Reachable {reachable}/{min(len(originators), 3)} originators",
                details={
                    "originators_count": len(originators),
                    "reachable_count": reachable,
                },
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.CONNECTIVITY,
                status=HealthStatus.UNKNOWN,
                score=0.0,
                message=f"Connectivity check failed: {str(e)}",
            )
    
    async def _check_link_quality(self) -> HealthCheckResult:
        """Check link quality to neighbors."""
        try:
            # Get link quality from batctl
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "originators"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return HealthCheckResult(
                    check_type=HealthCheckType.LINK_QUALITY,
                    status=HealthStatus.UNKNOWN,
                    score=0.0,
                    message="Failed to get originator information",
                )
            
            # Parse link quality from output
            lines = result.stdout.strip().split("\n")
            qualities = []
            
            for line in lines[2:]:  # Skip header
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        # Extract TQ (Transmission Quality) value
                        tq_str = parts[3].replace("(", "").replace(")", "")
                        tq = int(tq_str)
                        qualities.append(tq / 255.0)  # Normalize to 0-1
                    except (ValueError, IndexError):
                        continue
            
            if not qualities:
                return HealthCheckResult(
                    check_type=HealthCheckType.LINK_QUALITY,
                    status=HealthStatus.DEGRADED,
                    score=0.5,
                    message="No link quality data available",
                )
            
            avg_quality = sum(qualities) / len(qualities)
            status = self._determine_status(avg_quality)
            
            return HealthCheckResult(
                check_type=HealthCheckType.LINK_QUALITY,
                status=status,
                score=avg_quality,
                message=f"Average link quality: {avg_quality:.2%}",
                details={
                    "avg_quality": avg_quality,
                    "min_quality": min(qualities),
                    "max_quality": max(qualities),
                    "links_count": len(qualities),
                },
            )
        except FileNotFoundError:
            return HealthCheckResult(
                check_type=HealthCheckType.LINK_QUALITY,
                status=HealthStatus.UNKNOWN,
                score=0.5,
                message="batctl not available",
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.LINK_QUALITY,
                status=HealthStatus.UNKNOWN,
                score=0.0,
                message=f"Link quality check failed: {str(e)}",
            )
    
    async def _check_originator_table(self) -> HealthCheckResult:
        """Check originator table health."""
        try:
            originators = await self._get_originators()
            
            if not originators:
                return HealthCheckResult(
                    check_type=HealthCheckType.ORIGINATOR_TABLE,
                    status=HealthStatus.UNHEALTHY,
                    score=0.0,
                    message="Originator table is empty",
                    details={"originators_count": 0},
                )
            
            # Score based on number of originators
            # More originators = better mesh connectivity
            score = min(1.0, len(originators) / 10.0)  # 10+ originators = full score
            status = self._determine_status(score)
            
            return HealthCheckResult(
                check_type=HealthCheckType.ORIGINATOR_TABLE,
                status=status,
                score=score,
                message=f"Found {len(originators)} originators",
                details={"originators_count": len(originators)},
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.ORIGINATOR_TABLE,
                status=HealthStatus.UNKNOWN,
                score=0.0,
                message=f"Originator table check failed: {str(e)}",
            )
    
    async def _check_gateway(self) -> HealthCheckResult:
        """Check gateway connectivity."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "gateways"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return HealthCheckResult(
                    check_type=HealthCheckType.GATEWAY,
                    status=HealthStatus.UNKNOWN,
                    score=0.5,
                    message="Failed to get gateway information",
                )
            
            output = result.stdout.strip()
            
            if not output or "No gateways" in output:
                return HealthCheckResult(
                    check_type=HealthCheckType.GATEWAY,
                    status=HealthStatus.DEGRADED,
                    score=0.5,
                    message="No gateways available",
                    details={"gateways_count": 0},
                )
            
            # Count gateways
            gateway_count = len([l for l in output.split("\n") if l.strip()])
            
            return HealthCheckResult(
                check_type=HealthCheckType.GATEWAY,
                status=HealthStatus.HEALTHY,
                score=1.0,
                message=f"Found {gateway_count} gateway(s)",
                details={"gateways_count": gateway_count},
            )
        except FileNotFoundError:
            return HealthCheckResult(
                check_type=HealthCheckType.GATEWAY,
                status=HealthStatus.UNKNOWN,
                score=0.5,
                message="batctl not available",
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.GATEWAY,
                status=HealthStatus.UNKNOWN,
                score=0.0,
                message=f"Gateway check failed: {str(e)}",
            )
    
    async def _check_interface(self) -> HealthCheckResult:
        """Check Batman-adv interface status."""
        try:
            result = subprocess.run(
                ["ip", "link", "show", self.interface],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return HealthCheckResult(
                    check_type=HealthCheckType.INTERFACE,
                    status=HealthStatus.UNHEALTHY,
                    score=0.0,
                    message=f"Interface {self.interface} not found",
                )
            
            output = result.stdout.lower()
            
            if "up" in output and "unknown" not in output:
                return HealthCheckResult(
                    check_type=HealthCheckType.INTERFACE,
                    status=HealthStatus.HEALTHY,
                    score=1.0,
                    message=f"Interface {self.interface} is UP",
                    details={"interface": self.interface, "state": "up"},
                )
            else:
                return HealthCheckResult(
                    check_type=HealthCheckType.INTERFACE,
                    status=HealthStatus.DEGRADED,
                    score=0.5,
                    message=f"Interface {self.interface} state unknown",
                    details={"interface": self.interface, "state": "unknown"},
                )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.INTERFACE,
                status=HealthStatus.UNKNOWN,
                score=0.0,
                message=f"Interface check failed: {str(e)}",
            )
    
    async def _check_routing(self) -> HealthCheckResult:
        """Check routing table health."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "translocal"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return HealthCheckResult(
                    check_type=HealthCheckType.ROUTING,
                    status=HealthStatus.UNKNOWN,
                    score=0.5,
                    message="Failed to get routing information",
                )
            
            lines = result.stdout.strip().split("\n")
            entries = len([l for l in lines if l.strip()])
            
            if entries < 2:  # Only header
                return HealthCheckResult(
                    check_type=HealthCheckType.ROUTING,
                    status=HealthStatus.DEGRADED,
                    score=0.5,
                    message="Routing table is empty",
                    details={"routing_entries": 0},
                )
            
            score = min(1.0, (entries - 1) / 5.0)  # 5+ entries = full score
            status = self._determine_status(score)
            
            return HealthCheckResult(
                check_type=HealthCheckType.ROUTING,
                status=status,
                score=score,
                message=f"Routing table has {entries - 1} entries",
                details={"routing_entries": entries - 1},
            )
        except FileNotFoundError:
            return HealthCheckResult(
                check_type=HealthCheckType.ROUTING,
                status=HealthStatus.UNKNOWN,
                score=0.5,
                message="batctl not available",
            )
        except Exception as e:
            return HealthCheckResult(
                check_type=HealthCheckType.ROUTING,
                status=HealthStatus.UNKNOWN,
                score=0.0,
                message=f"Routing check failed: {str(e)}",
            )
    
    async def _get_originators(self) -> List[str]:
        """Get list of originator MAC addresses."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "originators"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return []
            
            originators = []
            for line in result.stdout.strip().split("\n")[2:]:  # Skip header
                parts = line.split()
                if parts:
                    originators.append(parts[0])  # MAC address
            
            return originators
        except Exception:
            return []
    
    async def _ping_originator(self, mac: str, count: int = 1) -> bool:
        """Ping an originator through Batman mesh."""
        try:
            result = subprocess.run(
                ["batctl", "meshif", self.interface, "ping", "-c", str(count), mac],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _update_prometheus_metrics(self, report: NodeHealthReport) -> None:
        """Update Prometheus metrics with health report."""
        if not self.enable_prometheus or not self._metrics:
            return
        
        try:
            # Update health score
            self._metrics["health_score"].labels(
                node_id=self.node_id
            ).set(report.overall_score)
            
            # Update health status
            status_value = {
                HealthStatus.HEALTHY: 1.0,
                HealthStatus.DEGRADED: 0.5,
                HealthStatus.UNHEALTHY: 0.0,
                HealthStatus.UNKNOWN: 0.25,
            }.get(report.overall_status, 0.0)
            
            self._metrics["health_status"].labels(
                node_id=self.node_id
            ).set(status_value)
            
            # Update check counter
            self._metrics["checks_total"].labels(
                node_id=self.node_id,
                status=report.overall_status.value,
            ).inc()
            
            # Update originators and links count
            for check in report.checks:
                if check.check_type == HealthCheckType.ORIGINATOR_TABLE:
                    count = check.details.get("originators_count", 0)
                    self._metrics["originators_count"].labels(
                        node_id=self.node_id
                    ).set(count)
                elif check.check_type == HealthCheckType.LINK_QUALITY:
                    count = check.details.get("links_count", 0)
                    self._metrics["links_count"].labels(
                        node_id=self.node_id
                    ).set(count)
        except Exception as e:
            logger.error(f"Failed to update Prometheus metrics: {e}")
    
    async def start_monitoring(self) -> None:
        """Start continuous health monitoring loop."""
        self._running = True
        logger.info(f"Starting health monitoring for {self.node_id}")
        
        while self._running:
            try:
                await self.run_health_checks()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.check_interval)
        
        logger.info(f"Health monitoring stopped for {self.node_id}")
    
    def stop_monitoring(self) -> None:
        """Stop health monitoring loop."""
        self._running = False
    
    def get_last_report(self) -> Optional[NodeHealthReport]:
        """Get the last health report."""
        return self._last_report
    
    def get_health_history(self, limit: int = 10) -> List[NodeHealthReport]:
        """Get health history."""
        return self._health_history[-limit:]
    
    def get_health_trend(self, window: int = 10) -> Dict[str, Any]:
        """
        Analyze health trend over recent reports.
        
        Returns:
            Dict with trend analysis
        """
        if len(self._health_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent = self._health_history[-window:]
        scores = [r.overall_score for r in recent]
        
        if len(scores) < 2:
            return {"trend": "insufficient_data"}
        
        # Calculate trend
        first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
        second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
        
        if second_half > first_half + 0.1:
            trend = "improving"
        elif second_half < first_half - 0.1:
            trend = "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "avg_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "samples": len(scores),
        }


def create_health_monitor_for_mapek(
    node_id: str,
    interface: str = "bat0",
    alert_callback: Optional[Callable[[NodeHealthReport], None]] = None,
) -> BatmanHealthMonitor:
    """
    Create a BatmanHealthMonitor configured for MAPE-K integration.
    
    Args:
        node_id: Node identifier
        interface: Batman-adv interface
        alert_callback: Callback for health alerts to MAPE-K
    
    Returns:
        Configured BatmanHealthMonitor instance
    """
    return BatmanHealthMonitor(
        node_id=node_id,
        interface=interface,
        check_interval=30.0,
        enable_prometheus=True,
        alert_callback=alert_callback,
    )
