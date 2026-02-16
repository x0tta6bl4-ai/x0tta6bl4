import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class AggregatedMetrics:
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    min_value: float = 0
    max_value: float = 0
    avg_value: float = 0

    def update_stats(self) -> None:
        if not self.points:
            return
        values = [p.value for p in self.points]
        self.min_value = min(values)
        self.max_value = max(values)
        self.avg_value = sum(values) / len(values)


class UnifiedMetricsCollector:
    def __init__(self, max_points_per_metric: int = 10000):
        self.metrics: Dict[str, AggregatedMetrics] = {}
        self.max_points = max_points_per_metric
        self.lock = __import__("threading").Lock()

    def record_metric(
        self, name: str, value: float, labels: Dict[str, str] = None
    ) -> None:
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = AggregatedMetrics(name)

            metric = self.metrics[name]
            point = MetricPoint(
                timestamp=datetime.utcnow(), value=value, labels=labels or {}
            )
            metric.points.append(point)

            if len(metric.points) > self.max_points:
                metric.points.pop(0)

            metric.update_stats()

    def get_metric(self, name: str) -> Dict[str, Any]:
        with self.lock:
            if name not in self.metrics:
                return {}

            metric = self.metrics[name]
            return {
                "name": metric.name,
                "min": metric.min_value,
                "max": metric.max_value,
                "avg": metric.avg_value,
                "count": len(metric.points),
                "latest": metric.points[-1].value if metric.points else 0,
            }

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            return {
                name: {
                    "min": m.min_value,
                    "max": m.max_value,
                    "avg": m.avg_value,
                    "count": len(m.points),
                }
                for name, m in self.metrics.items()
            }

    def export_prometheus_format(self) -> str:
        with self.lock:
            lines = []
            for name, metric in self.metrics.items():
                lines.append(f"# HELP {name} Custom metric")
                lines.append(f"# TYPE {name} gauge")
                if metric.points:
                    lines.append(f"{name} {metric.points[-1].value}")
            return "\n".join(lines)


class HealthCheckAggregator:
    def __init__(self):
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.lock = __import__("threading").Lock()

    def register_check(self, component: str, check_fn) -> None:
        with self.lock:
            self.checks[component] = {
                "fn": check_fn,
                "last_result": None,
                "last_check": None,
            }

    def run_checks(self) -> Dict[str, Any]:
        results = {}
        with self.lock:
            for component, check_data in self.checks.items():
                try:
                    result = check_data["fn"]()
                    check_data["last_result"] = result
                    check_data["last_check"] = datetime.utcnow()
                    results[component] = {"status": "ok", "data": result}
                except Exception as e:
                    results[component] = {"status": "error", "error": str(e)}

        return results

    def get_overall_health(self) -> Dict[str, Any]:
        checks = self.run_checks()

        healthy = sum(1 for c in checks.values() if c["status"] == "ok")
        total = len(checks)
        health_score = (healthy / total * 100) if total > 0 else 0

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "score": health_score,
            "healthy_components": healthy,
            "total_components": total,
            "status": "HEALTHY" if health_score >= 90 else "WARNING",
            "checks": checks,
        }


_collector = None
_health = None


def get_metrics_collector() -> UnifiedMetricsCollector:
    global _collector
    if _collector is None:
        _collector = UnifiedMetricsCollector()
    return _collector


def get_health_aggregator() -> HealthCheckAggregator:
    global _health
    if _health is None:
        _health = HealthCheckAggregator()
    return _health


__all__ = [
    "MetricPoint",
    "AggregatedMetrics",
    "UnifiedMetricsCollector",
    "HealthCheckAggregator",
    "get_metrics_collector",
    "get_health_aggregator",
]
