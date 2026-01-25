"""
SLA Monitoring

Provides SLA definitions, tracking, reporting, and alerting.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class SLAMetric(Enum):
    """SLA metrics"""
    UPTIME = "uptime"  # Percentage uptime
    LATENCY = "latency"  # Response time (p95, p99)
    THROUGHPUT = "throughput"  # Requests per second
    ERROR_RATE = "error_rate"  # Error percentage
    MTTR = "mttr"  # Mean time to recover
    AVAILABILITY = "availability"  # Service availability


@dataclass
class SLATarget:
    """SLA target definition"""
    metric: SLAMetric
    threshold: float
    operator: str = ">="  # >=, <=, ==
    window_minutes: int = 60  # Time window for evaluation


@dataclass
class SLADefinition:
    """SLA definition"""
    sla_id: str
    name: str
    description: str = ""
    targets: List[SLATarget] = field(default_factory=list)
    tenant_id: Optional[str] = None
    service_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    enabled: bool = True


@dataclass
class SLAViolation:
    """SLA violation record"""
    violation_id: str
    sla_id: str
    metric: SLAMetric
    threshold: float
    actual_value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_seconds: float = 0.0
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class SLAMonitor:
    """
    Monitors SLA compliance and generates violations.
    
    Provides:
    - SLA definitions
    - Real-time monitoring
    - Violation tracking
    - Reporting
    - Alerting
    """
    
    def __init__(self):
        self.slas: Dict[str, SLADefinition] = {}
        self.violations: Dict[str, List[SLAViolation]] = {}  # sla_id -> violations
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {}  # metric -> history
        
        logger.info("SLAMonitor initialized")
    
    def create_sla(
        self,
        name: str,
        targets: List[SLATarget],
        description: str = "",
        tenant_id: Optional[str] = None,
        service_id: Optional[str] = None
    ) -> SLADefinition:
        """
        Create an SLA definition.
        
        Args:
            name: SLA name
            targets: List of SLA targets
            description: SLA description
            tenant_id: Optional tenant ID
            service_id: Optional service ID
        
        Returns:
            Created SLADefinition
        """
        sla_id = f"sla-{name.lower().replace(' ', '-')}"
        sla = SLADefinition(
            sla_id=sla_id,
            name=name,
            description=description,
            targets=targets,
            tenant_id=tenant_id,
            service_id=service_id
        )
        
        self.slas[sla_id] = sla
        self.violations[sla_id] = []
        
        logger.info(f"Created SLA {sla_id} ({name}) with {len(targets)} targets")
        return sla
    
    def get_sla(self, sla_id: str) -> Optional[SLADefinition]:
        """Get SLA by ID"""
        return self.slas.get(sla_id)
    
    def record_metric(
        self,
        metric: SLAMetric,
        value: float,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a metric value.
        
        Args:
            metric: Metric type
            value: Metric value
            timestamp: Optional timestamp (default: now)
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        
        metric_key = metric.value
        if metric_key not in self.metrics_history:
            self.metrics_history[metric_key] = []
        
        self.metrics_history[metric_key].append({
            "value": value,
            "timestamp": timestamp,
            "timestamp_epoch": timestamp.timestamp()
        })
        
        # Keep only last 24 hours of history
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.metrics_history[metric_key] = [
            m for m in self.metrics_history[metric_key]
            if m["timestamp"] > cutoff
        ]
        
        # Check SLAs
        self._check_slas(metric, value, timestamp)
    
    def _check_slas(self, metric: SLAMetric, value: float, timestamp: datetime):
        """Check all SLAs for this metric"""
        for sla_id, sla in self.slas.items():
            if not sla.enabled:
                continue
            
            for target in sla.targets:
                if target.metric != metric:
                    continue
                
                # Evaluate target
                violation = self._evaluate_target(sla_id, target, value, timestamp)
                if violation:
                    if sla_id not in self.violations:
                        self.violations[sla_id] = []
                    self.violations[sla_id].append(violation)
                    logger.warning(
                        f"SLA violation: {sla_id} - {metric.value} = {value} "
                        f"(threshold: {target.threshold})"
                    )
    
    def _evaluate_target(
        self,
        sla_id: str,
        target: SLATarget,
        value: float,
        timestamp: datetime
    ) -> Optional[SLAViolation]:
        """
        Evaluate if target is violated.
        
        Args:
            sla_id: SLA ID
            target: SLA target
            value: Current value
            timestamp: Timestamp
        
        Returns:
            SLAViolation if violated, None otherwise
        """
        violated = False
        
        if target.operator == ">=":
            violated = value < target.threshold
        elif target.operator == "<=":
            violated = value > target.threshold
        elif target.operator == "==":
            violated = abs(value - target.threshold) > 0.01  # Small tolerance
        
        if violated:
            violation_id = f"violation-{sla_id}-{timestamp.timestamp()}"
            return SLAViolation(
                violation_id=violation_id,
                sla_id=sla_id,
                metric=target.metric,
                threshold=target.threshold,
                actual_value=value,
                timestamp=timestamp
            )
        
        return None
    
    def get_sla_compliance(
        self,
        sla_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get SLA compliance report.
        
        Args:
            sla_id: SLA ID
            start_time: Optional start time
            end_time: Optional end time
        
        Returns:
            Compliance report
        """
        sla = self.slas.get(sla_id)
        if not sla:
            return {"error": "SLA not found"}
        
        if start_time is None:
            start_time = datetime.utcnow() - timedelta(hours=24)
        if end_time is None:
            end_time = datetime.utcnow()
        
        # Get violations in period
        violations = [
            v for v in self.violations.get(sla_id, [])
            if start_time <= v.timestamp <= end_time
        ]
        
        # Calculate compliance
        period_seconds = (end_time - start_time).total_seconds()
        violation_seconds = sum(v.duration_seconds for v in violations)
        compliance_percentage = max(0, 100 * (1 - violation_seconds / period_seconds))
        
        return {
            "sla_id": sla_id,
            "sla_name": sla.name,
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "compliance_percentage": compliance_percentage,
            "violations_count": len(violations),
            "violations": [
                {
                    "metric": v.metric.value,
                    "threshold": v.threshold,
                    "actual": v.actual_value,
                    "timestamp": v.timestamp.isoformat(),
                    "resolved": v.resolved
                }
                for v in violations
            ]
        }
    
    def resolve_violation(self, violation_id: str) -> bool:
        """
        Mark violation as resolved.
        
        Args:
            violation_id: Violation ID
        
        Returns:
            True if resolved successfully
        """
        for sla_id, violations in self.violations.items():
            for violation in violations:
                if violation.violation_id == violation_id:
                    violation.resolved = True
                    violation.resolved_at = datetime.utcnow()
                    logger.info(f"Resolved SLA violation {violation_id}")
                    return True
        
        return False
    
    def get_active_violations(self, sla_id: Optional[str] = None) -> List[SLAViolation]:
        """
        Get active (unresolved) violations.
        
        Args:
            sla_id: Optional SLA ID filter
        
        Returns:
            List of active violations
        """
        active = []
        
        for vid, violations in self.violations.items():
            if sla_id and vid != sla_id:
                continue
            
            for violation in violations:
                if not violation.resolved:
                    active.append(violation)
        
        return active

