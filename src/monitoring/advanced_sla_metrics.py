"""
Advanced SLA Metrics and Custom Metrics Tracking

Production-grade SLA tracking with:
- Real-time SLA compliance monitoring
- Custom metric definitions
- SLA violation prediction
- Compliance reporting
- Multi-level alerts
"""

import logging
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Custom metric types"""
    GAUGE = "gauge"
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class SLAStatus(Enum):
    """SLA status"""
    HEALTHY = "healthy"
    WARNING = "warning"
    VIOLATION = "violation"
    RECOVERED = "recovered"


@dataclass
class CustomMetric:
    """Custom metric definition"""
    name: str
    metric_type: MetricType
    unit: str
    description: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CustomMetricValue:
    """Custom metric value with timestamp"""
    metric_name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class SLAThreshold:
    """SLA threshold definition"""
    name: str
    metric_name: str
    threshold_value: float
    operator: str
    window_seconds: int = 300
    consecutive_violations: int = 1


@dataclass
class SLACompliancePoint:
    """Single SLA compliance measurement"""
    timestamp: datetime
    sla_name: str
    metric_value: float
    threshold: float
    is_compliant: bool
    operator: str


class CustomMetricsRegistry:
    """Registry for custom metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, CustomMetric] = {}
        self.values: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.lock = __import__('threading').Lock()
    
    def register_metric(self, name: str, metric_type: MetricType, 
                       unit: str, description: str = "") -> CustomMetric:
        """Register a custom metric"""
        with self.lock:
            metric = CustomMetric(
                name=name,
                metric_type=metric_type,
                unit=unit,
                description=description
            )
            self.metrics[name] = metric
            logger.info(f"Registered custom metric: {name} ({metric_type.value})")
            return metric
    
    def record_value(self, metric_name: str, value: float, 
                    labels: Dict[str, str] = None) -> bool:
        """Record metric value"""
        with self.lock:
            if metric_name not in self.metrics:
                return False
            
            metric_value = CustomMetricValue(
                metric_name=metric_name,
                value=value,
                labels=labels or {}
            )
            self.values[metric_name].append(metric_value)
            return True
    
    def get_metric_stats(self, metric_name: str, 
                        window_seconds: int = 300) -> Dict[str, float]:
        """Get statistics for metric"""
        with self.lock:
            if metric_name not in self.values:
                return {}
            
            values = list(self.values[metric_name])
            cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
            recent = [v.value for v in values if v.timestamp > cutoff]
            
            if not recent:
                return {}
            
            recent_arr = np.array(recent)
            
            return {
                "count": len(recent),
                "min": float(np.min(recent_arr)),
                "max": float(np.max(recent_arr)),
                "mean": float(np.mean(recent_arr)),
                "p50": float(np.percentile(recent_arr, 50)),
                "p95": float(np.percentile(recent_arr, 95)),
                "p99": float(np.percentile(recent_arr, 99)),
                "stddev": float(np.std(recent_arr))
            }


class SLAComplianceMonitor:
    """Monitors SLA compliance with advanced tracking"""
    
    def __init__(self, metrics_registry: CustomMetricsRegistry):
        self.metrics_registry = metrics_registry
        self.thresholds: Dict[str, SLAThreshold] = {}
        self.compliance_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
        self.violations: Dict[str, List[Tuple[datetime, datetime]]] = defaultdict(list)
        self.lock = __import__('threading').Lock()
    
    def define_sla(self, name: str, metric_name: str, threshold: float,
                  operator: str, window_seconds: int = 300,
                  consecutive_violations: int = 1) -> SLAThreshold:
        """Define SLA threshold"""
        with self.lock:
            sla = SLAThreshold(
                name=name,
                metric_name=metric_name,
                threshold_value=threshold,
                operator=operator,
                window_seconds=window_seconds,
                consecutive_violations=consecutive_violations
            )
            self.thresholds[name] = sla
            logger.info(f"Defined SLA: {name} ({metric_name} {operator} {threshold})")
            return sla
    
    def check_compliance(self, sla_name: str) -> Optional[SLACompliancePoint]:
        """Check SLA compliance"""
        with self.lock:
            sla = self.thresholds.get(sla_name)
            if not sla:
                return None
            
            metric_stats = self.metrics_registry.get_metric_stats(
                sla.metric_name, sla.window_seconds
            )
            
            if not metric_stats:
                return None
            
            metric_value = metric_stats.get("mean", 0)
            is_compliant = self._evaluate_threshold(
                metric_value, sla.threshold_value, sla.operator
            )
            
            point = SLACompliancePoint(
                timestamp=datetime.utcnow(),
                sla_name=sla_name,
                metric_value=metric_value,
                threshold=sla.threshold_value,
                is_compliant=is_compliant,
                operator=sla.operator
            )
            
            self.compliance_history[sla_name].append(point)
            
            if not is_compliant:
                self._record_violation(sla_name)
            
            return point
    
    def _evaluate_threshold(self, value: float, threshold: float, 
                           operator: str) -> bool:
        """Evaluate threshold"""
        if operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == "==":
            return abs(value - threshold) < 0.01
        return False
    
    def _record_violation(self, sla_name: str) -> None:
        """Record SLA violation"""
        if sla_name not in self.violations:
            self.violations[sla_name] = []
        
        now = datetime.utcnow()
        if not self.violations[sla_name] or self.violations[sla_name][-1][1]:
            self.violations[sla_name].append((now, None))
    
    def resolve_violation(self, sla_name: str) -> None:
        """Resolve SLA violation"""
        if sla_name in self.violations and self.violations[sla_name]:
            if not self.violations[sla_name][-1][1]:
                start, _ = self.violations[sla_name][-1]
                self.violations[sla_name][-1] = (start, datetime.utcnow())
    
    def get_sla_compliance_report(self, sla_name: str, 
                                 hours: int = 24) -> Dict[str, Any]:
        """Get SLA compliance report"""
        with self.lock:
            history = list(self.compliance_history.get(sla_name, []))
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            recent = [p for p in history if p.timestamp > cutoff]
            
            if not recent:
                return {}
            
            compliant_count = sum(1 for p in recent if p.is_compliant)
            compliance_percentage = (compliant_count / len(recent)) * 100
            
            violations = self.violations.get(sla_name, [])
            recent_violations = []
            total_violation_seconds = 0
            
            for start, end in violations:
                if start > cutoff:
                    if end:
                        duration = (end - start).total_seconds()
                    else:
                        duration = (datetime.utcnow() - start).total_seconds()
                    
                    total_violation_seconds += duration
                    recent_violations.append({
                        "start": start.isoformat(),
                        "end": end.isoformat() if end else None,
                        "duration_seconds": duration
                    })
            
            return {
                "sla_name": sla_name,
                "period_hours": hours,
                "compliance_percentage": compliance_percentage,
                "total_samples": len(recent),
                "compliant_samples": compliant_count,
                "violations": recent_violations,
                "total_violation_seconds": total_violation_seconds,
                "status": "healthy" if compliance_percentage >= 99.9 else "warning" if compliance_percentage >= 99 else "violation"
            }


class AdvancedSLAManager:
    """Advanced SLA management system"""
    
    def __init__(self):
        self.metrics_registry = CustomMetricsRegistry()
        self.compliance_monitor = SLAComplianceMonitor(self.metrics_registry)
        self.predictions: Dict[str, Dict[str, Any]] = {}
    
    def register_metric(self, name: str, metric_type: MetricType,
                       unit: str = "", description: str = "") -> CustomMetric:
        """Register custom metric"""
        return self.metrics_registry.register_metric(name, metric_type, unit, description)
    
    def record_metric(self, metric_name: str, value: float,
                     labels: Dict[str, str] = None) -> bool:
        """Record metric value"""
        return self.metrics_registry.record_value(metric_name, value, labels)
    
    def define_sla(self, name: str, metric_name: str, threshold: float,
                  operator: str, window_seconds: int = 300) -> SLAThreshold:
        """Define SLA"""
        return self.compliance_monitor.define_sla(
            name, metric_name, threshold, operator, window_seconds
        )
    
    def check_all_slas(self) -> Dict[str, Dict[str, Any]]:
        """Check all SLAs"""
        results = {}
        with self.compliance_monitor.lock:
            for sla_name in self.compliance_monitor.thresholds.keys():
                point = self.compliance_monitor.check_compliance(sla_name)
                if point:
                    results[sla_name] = {
                        "compliant": point.is_compliant,
                        "value": point.metric_value,
                        "threshold": point.threshold,
                        "timestamp": point.timestamp.isoformat()
                    }
        return results
    
    def get_overall_compliance(self) -> Dict[str, Any]:
        """Get overall compliance across all SLAs"""
        sla_reports = []
        
        with self.compliance_monitor.lock:
            for sla_name in self.compliance_monitor.thresholds.keys():
                report = self.compliance_monitor.get_sla_compliance_report(sla_name)
                if report:
                    sla_reports.append(report)
        
        if not sla_reports:
            return {}
        
        avg_compliance = np.mean([r.get("compliance_percentage", 0) for r in sla_reports])
        
        return {
            "overall_compliance_percentage": float(avg_compliance),
            "total_slas": len(sla_reports),
            "sla_reports": sla_reports,
            "status": "healthy" if avg_compliance >= 99.9 else "warning" if avg_compliance >= 99 else "violation",
            "timestamp": datetime.utcnow().isoformat()
        }


_manager = None

def get_advanced_sla_manager() -> AdvancedSLAManager:
    """Get or create singleton manager"""
    global _manager
    if _manager is None:
        _manager = AdvancedSLAManager()
    return _manager


__all__ = [
    "MetricType",
    "SLAStatus",
    "CustomMetric",
    "CustomMetricValue",
    "SLAThreshold",
    "SLACompliancePoint",
    "CustomMetricsRegistry",
    "SLAComplianceMonitor",
    "AdvancedSLAManager",
    "get_advanced_sla_manager",
]
