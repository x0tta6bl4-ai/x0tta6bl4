"""
Advanced SLA Metrics and Custom Metrics Tracking

Production-grade SLA tracking with:
- Real-time SLA compliance monitoring
- Custom metric definitions
- SLA violation prediction
- Compliance reporting
- Multi-level alerts
"""

import hashlib
import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


def _safe_labels_summary(labels: Optional[Dict[str, str]]) -> Dict[str, Any]:
    values = labels or {}
    return {
        "label_count_bucket": _safe_count_bucket(len(values)),
        "label_key_hashes": sorted(_safe_hash(key) for key in values.keys()),
        "non_empty_values": sum(1 for value in values.values() if value),
    }


def _safe_stats_summary(stats: Dict[str, float]) -> Dict[str, Any]:
    return {
        "stat_key_hashes": sorted(_safe_hash(key) for key in stats.keys()),
        "count_bucket": _safe_count_bucket(int(stats.get("count", 0))),
        "mean_band": _safe_number_band(stats.get("mean")),
        "p95_band": _safe_number_band(stats.get("p95")),
        "p99_band": _safe_number_band(stats.get("p99")),
    }


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
        self.lock = threading.RLock()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="custom-metrics-registry",
            role="monitoring",
            capabilities=("ops", "quality"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "custom_metrics_registry_init",
                "goal": "Initialize custom metric registry without raw metric labels",
                "signals": {"metric_count_bucket": "0", "value_window_limit": 10000},
                "safety_boundary": (
                    "Keep metric names, descriptions, label values, and tenant data "
                    "out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_metric_names": True,
                    "redact_metric_descriptions": True,
                    "redact_label_values": True,
                    "preserve_metric_type_and_counts": True,
                },
                "safety_boundary": "Use hashes, counts, metric types, and value bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def register_metric(
        self, name: str, metric_type: MetricType, unit: str, description: str = ""
    ) -> CustomMetric:
        """Register a custom metric"""
        with self.lock:
            metric = CustomMetric(
                name=name, metric_type=metric_type, unit=unit, description=description
            )
            self.metrics[name] = metric
            self._record_thinking(
                "custom_metric_registered",
                "Register custom metric definition safely",
                {
                    "metric_hash": _safe_hash(name),
                    "metric_type": metric_type.value,
                    "unit_hash": _safe_hash(unit),
                    "has_description": bool(description),
                    "metric_count_bucket": _safe_count_bucket(len(self.metrics)),
                },
            )
            logger.info(f"Registered custom metric: {name} ({metric_type.value})")
            return metric

    def record_value(
        self, metric_name: str, value: float, labels: Dict[str, str] = None
    ) -> bool:
        """Record metric value"""
        with self.lock:
            if metric_name not in self.metrics:
                self._record_thinking(
                    "custom_metric_value_rejected",
                    "Reject value for unknown custom metric",
                    {
                        "metric_hash": _safe_hash(metric_name),
                        "registered": False,
                        "value_band": _safe_number_band(value),
                        "labels": _safe_labels_summary(labels),
                    },
                )
                return False

            metric_value = CustomMetricValue(
                metric_name=metric_name, value=value, labels=labels or {}
            )
            self.values[metric_name].append(metric_value)
            self._record_thinking(
                "custom_metric_value_recorded",
                "Record custom metric value safely",
                {
                    "metric_hash": _safe_hash(metric_name),
                    "registered": True,
                    "value_band": _safe_number_band(value),
                    "labels": _safe_labels_summary(labels),
                    "sample_count_bucket": _safe_count_bucket(
                        len(self.values[metric_name])
                    ),
                },
            )
            return True

    def get_metric_stats(
        self, metric_name: str, window_seconds: int = 300
    ) -> Dict[str, float]:
        """Get statistics for metric"""
        with self.lock:
            if metric_name not in self.values:
                self._record_thinking(
                    "custom_metric_stats",
                    "Report missing custom metric stats",
                    {
                        "metric_hash": _safe_hash(metric_name),
                        "window_seconds": window_seconds,
                        "sample_count_bucket": "0",
                    },
                )
                return {}

            values = list(self.values[metric_name])
            cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
            recent = [v.value for v in values if v.timestamp > cutoff]

            if not recent:
                self._record_thinking(
                    "custom_metric_stats",
                    "Report empty recent custom metric stats window",
                    {
                        "metric_hash": _safe_hash(metric_name),
                        "window_seconds": window_seconds,
                        "sample_count_bucket": "0",
                    },
                )
                return {}

            recent_arr = np.array(recent)

            stats = {
                "count": len(recent),
                "min": float(np.min(recent_arr)),
                "max": float(np.max(recent_arr)),
                "mean": float(np.mean(recent_arr)),
                "p50": float(np.percentile(recent_arr, 50)),
                "p95": float(np.percentile(recent_arr, 95)),
                "p99": float(np.percentile(recent_arr, 99)),
                "stddev": float(np.std(recent_arr)),
            }
            self._record_thinking(
                "custom_metric_stats",
                "Summarize custom metric stats safely",
                {
                    "metric_hash": _safe_hash(metric_name),
                    "window_seconds": window_seconds,
                    "stats": _safe_stats_summary(stats),
                },
            )
            return stats


class SLAComplianceMonitor:
    """Monitors SLA compliance with advanced tracking"""

    def __init__(self, metrics_registry: CustomMetricsRegistry):
        self.metrics_registry = metrics_registry
        self.thresholds: Dict[str, SLAThreshold] = {}
        self.compliance_history: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self.violations: Dict[str, List[Tuple[datetime, datetime]]] = defaultdict(list)
        self.lock = threading.RLock()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="sla-compliance-monitor",
            role="monitoring",
            capabilities=("ops", "quality", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "sla_compliance_monitor_init",
                "goal": "Initialize SLA compliance checks without raw metric names",
                "signals": {
                    "threshold_count_bucket": "0",
                    "history_window_limit": 10000,
                },
                "safety_boundary": (
                    "Keep SLA names, metric names, descriptions, labels, and tenant "
                    "values out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_sla_names": True,
                    "redact_metric_names": True,
                    "redact_metric_values": False,
                    "preserve_compliance_decision": True,
                },
                "safety_boundary": (
                    "Use hashes, operators, counts, value bands, and compliance flags."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def define_sla(
        self,
        name: str,
        metric_name: str,
        threshold: float,
        operator: str,
        window_seconds: int = 300,
        consecutive_violations: int = 1,
    ) -> SLAThreshold:
        """Define SLA threshold"""
        with self.lock:
            sla = SLAThreshold(
                name=name,
                metric_name=metric_name,
                threshold_value=threshold,
                operator=operator,
                window_seconds=window_seconds,
                consecutive_violations=consecutive_violations,
            )
            self.thresholds[name] = sla
            self._record_thinking(
                "sla_threshold_defined",
                "Define SLA threshold safely",
                {
                    "sla_hash": _safe_hash(name),
                    "metric_hash": _safe_hash(metric_name),
                    "threshold_band": _safe_number_band(threshold),
                    "operator": operator,
                    "window_seconds": window_seconds,
                    "consecutive_violations": consecutive_violations,
                    "threshold_count_bucket": _safe_count_bucket(
                        len(self.thresholds)
                    ),
                },
            )
            logger.info(f"Defined SLA: {name} ({metric_name} {operator} {threshold})")
            return sla

    def check_compliance(self, sla_name: str) -> Optional[SLACompliancePoint]:
        """Check SLA compliance"""
        with self.lock:
            sla = self.thresholds.get(sla_name)
            if not sla:
                self._record_thinking(
                    "sla_compliance_check",
                    "Skip unknown SLA compliance check",
                    {"sla_hash": _safe_hash(sla_name), "known": False},
                )
                return None

            metric_stats = self.metrics_registry.get_metric_stats(
                sla.metric_name, sla.window_seconds
            )

            if not metric_stats:
                self._record_thinking(
                    "sla_compliance_check",
                    "Skip SLA compliance check without metric stats",
                    {
                        "sla_hash": _safe_hash(sla_name),
                        "metric_hash": _safe_hash(sla.metric_name),
                        "known": True,
                        "has_metric_stats": False,
                    },
                )
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
                operator=sla.operator,
            )

            self.compliance_history[sla_name].append(point)

            if not is_compliant:
                self._record_violation(sla_name)

            self._record_thinking(
                "sla_compliance_check",
                "Evaluate SLA compliance from metric stats",
                {
                    "sla_hash": _safe_hash(sla_name),
                    "metric_hash": _safe_hash(sla.metric_name),
                    "operator": sla.operator,
                    "metric_value_band": _safe_number_band(metric_value),
                    "threshold_band": _safe_number_band(sla.threshold_value),
                    "is_compliant": is_compliant,
                    "history_count_bucket": _safe_count_bucket(
                        len(self.compliance_history[sla_name])
                    ),
                },
            )
            return point

    def _evaluate_threshold(
        self, value: float, threshold: float, operator: str
    ) -> bool:
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
        self._record_thinking(
            "sla_violation_recorded",
            "Record active SLA violation window",
            {
                "sla_hash": _safe_hash(sla_name),
                "violation_count_bucket": _safe_count_bucket(
                    len(self.violations[sla_name])
                ),
            },
        )

    def resolve_violation(self, sla_name: str) -> None:
        """Resolve SLA violation"""
        if sla_name in self.violations and self.violations[sla_name]:
            if not self.violations[sla_name][-1][1]:
                start, _ = self.violations[sla_name][-1]
                self.violations[sla_name][-1] = (start, datetime.utcnow())
                self._record_thinking(
                    "sla_violation_resolved",
                    "Resolve active SLA violation window",
                    {
                        "sla_hash": _safe_hash(sla_name),
                        "violation_count_bucket": _safe_count_bucket(
                            len(self.violations[sla_name])
                        ),
                    },
                )

    def get_sla_compliance_report(
        self, sla_name: str, hours: int = 24
    ) -> Dict[str, Any]:
        """Get SLA compliance report"""
        with self.lock:
            history = list(self.compliance_history.get(sla_name, []))
            cutoff = datetime.utcnow() - timedelta(hours=hours)

            recent = [p for p in history if p.timestamp > cutoff]

            if not recent:
                self._record_thinking(
                    "sla_compliance_report",
                    "Report empty SLA compliance history",
                    {
                        "sla_hash": _safe_hash(sla_name),
                        "period_hours": hours,
                        "sample_count_bucket": "0",
                    },
                )
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
                    recent_violations.append(
                        {
                            "start": start.isoformat(),
                            "end": end.isoformat() if end else None,
                            "duration_seconds": duration,
                        }
                    )

            report = {
                "sla_name": sla_name,
                "period_hours": hours,
                "compliance_percentage": compliance_percentage,
                "total_samples": len(recent),
                "compliant_samples": compliant_count,
                "violations": recent_violations,
                "total_violation_seconds": total_violation_seconds,
                "status": (
                    "healthy"
                    if compliance_percentage >= 99.9
                    else "warning" if compliance_percentage >= 99 else "violation"
                ),
            }
            self._record_thinking(
                "sla_compliance_report",
                "Summarize SLA compliance report safely",
                {
                    "sla_hash": _safe_hash(sla_name),
                    "period_hours": hours,
                    "sample_count_bucket": _safe_count_bucket(len(recent)),
                    "compliance_band": _safe_number_band(compliance_percentage),
                    "violation_count_bucket": _safe_count_bucket(
                        len(recent_violations)
                    ),
                    "status": report["status"],
                },
            )
            return report


class AdvancedSLAManager:
    """Advanced SLA management system"""

    def __init__(self):
        self.metrics_registry = CustomMetricsRegistry()
        self.compliance_monitor = SLAComplianceMonitor(self.metrics_registry)
        self.predictions: Dict[str, Dict[str, Any]] = {}
        self.thinking_coach = AgentThinkingCoach(
            agent_id="advanced-sla-manager",
            role="monitoring",
            capabilities=("ops", "quality", "healing"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "advanced_sla_manager_init",
                "goal": "Initialize SLA manager with safe compliance context",
                "signals": {
                    "metric_count_bucket": "0",
                    "sla_count_bucket": "0",
                    "prediction_count_bucket": "0",
                },
                "safety_boundary": (
                    "Keep SLA names, metric names, descriptions, labels, tenant "
                    "values, and prediction details out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_metric_names": True,
                    "redact_sla_names": True,
                    "redact_labels": True,
                    "preserve_compliance_summary": True,
                },
                "safety_boundary": "Use hashes, counts, bands, and status values only.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "registry": self.metrics_registry.get_thinking_status(),
            "compliance_monitor": self.compliance_monitor.get_thinking_status(),
        }

    def register_metric(
        self, name: str, metric_type: MetricType, unit: str = "", description: str = ""
    ) -> CustomMetric:
        """Register custom metric"""
        metric = self.metrics_registry.register_metric(
            name, metric_type, unit, description
        )
        self._record_thinking(
            "advanced_sla_metric_registered",
            "Register metric through SLA manager",
            {
                "metric_hash": _safe_hash(name),
                "metric_type": metric_type.value,
                "metric_count_bucket": _safe_count_bucket(
                    len(self.metrics_registry.metrics)
                ),
            },
        )
        return metric

    def record_metric(
        self, metric_name: str, value: float, labels: Dict[str, str] = None
    ) -> bool:
        """Record metric value"""
        recorded = self.metrics_registry.record_value(metric_name, value, labels)
        self._record_thinking(
            "advanced_sla_metric_recorded",
            "Record metric value through SLA manager",
            {
                "metric_hash": _safe_hash(metric_name),
                "recorded": recorded,
                "value_band": _safe_number_band(value),
                "labels": _safe_labels_summary(labels),
            },
        )
        return recorded

    def define_sla(
        self,
        name: str,
        metric_name: str,
        threshold: float,
        operator: str,
        window_seconds: int = 300,
    ) -> SLAThreshold:
        """Define SLA"""
        sla = self.compliance_monitor.define_sla(
            name, metric_name, threshold, operator, window_seconds
        )
        self._record_thinking(
            "advanced_sla_defined",
            "Define SLA through manager",
            {
                "sla_hash": _safe_hash(name),
                "metric_hash": _safe_hash(metric_name),
                "threshold_band": _safe_number_band(threshold),
                "operator": operator,
                "sla_count_bucket": _safe_count_bucket(
                    len(self.compliance_monitor.thresholds)
                ),
            },
        )
        return sla

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
                        "timestamp": point.timestamp.isoformat(),
                    }
        self._record_thinking(
            "advanced_sla_check_all",
            "Check all SLA compliance points",
            {
                "sla_count_bucket": _safe_count_bucket(
                    len(self.compliance_monitor.thresholds)
                ),
                "result_count_bucket": _safe_count_bucket(len(results)),
                "compliant_count_bucket": _safe_count_bucket(
                    sum(1 for result in results.values() if result["compliant"])
                ),
            },
        )
        return results

    def get_overall_compliance(self) -> Dict[str, Any]:
        """Get overall compliance across all SLAs"""
        sla_reports = []

        with self.compliance_monitor.lock:
            for sla_name in self.compliance_monitor.thresholds.keys():
                self.compliance_monitor.check_compliance(sla_name)
                report = self.compliance_monitor.get_sla_compliance_report(sla_name)
                if report:
                    sla_reports.append(report)

        if not sla_reports:
            self._record_thinking(
                "advanced_sla_overall_compliance",
                "Report empty overall SLA compliance",
                {
                    "sla_count_bucket": _safe_count_bucket(
                        len(self.compliance_monitor.thresholds)
                    ),
                    "report_count_bucket": "0",
                },
            )
            return {}

        avg_compliance = np.mean(
            [r.get("compliance_percentage", 0) for r in sla_reports]
        )

        report = {
            "overall_compliance_percentage": float(avg_compliance),
            "total_slas": len(sla_reports),
            "sla_reports": sla_reports,
            "status": (
                "healthy"
                if avg_compliance >= 99.9
                else "warning" if avg_compliance >= 99 else "violation"
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._record_thinking(
            "advanced_sla_overall_compliance",
            "Summarize overall SLA compliance",
            {
                "report_count_bucket": _safe_count_bucket(len(sla_reports)),
                "overall_compliance_band": _safe_number_band(float(avg_compliance)),
                "status": report["status"],
            },
        )
        return report

    def get_compliance_report(self) -> Dict[str, Any]:
        """Backward-compatible compliance report shape."""
        report = self.get_overall_compliance()
        if not report:
            return report

        metrics_recorded = sum(
            len(values) for values in self.metrics_registry.values.values()
        )
        # Older tests expect `slas` and `metrics_recorded` keys.
        report.setdefault("slas", report.get("sla_reports", []))
        report.setdefault("metrics_recorded", metrics_recorded)
        self._record_thinking(
            "advanced_sla_compliance_report",
            "Build backward-compatible SLA compliance report",
            {
                "has_report": True,
                "metrics_recorded_bucket": _safe_count_bucket(metrics_recorded),
                "sla_report_count_bucket": _safe_count_bucket(
                    len(report.get("sla_reports", []))
                ),
            },
        )
        return report


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
