#!/usr/bin/env python3
"""
eBPF Performance Monitoring, Alerting and Dashboards

This module provides comprehensive performance monitoring for eBPF programs
in the x0tta6bl4 mesh network, including:

- Real-time performance metrics collection
- Automated alerting for performance issues
- Grafana dashboard configurations
- Performance profiling and optimization tools

Integrates with Prometheus for metrics export and alerting.
"""

import asyncio
import hashlib
import json
import logging
import os
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.agent_thinking import AgentThinkingCoach

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CollectorRegistry = None  # type: ignore[assignment]
    Counter = Gauge = Histogram = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


class AlertSeverity(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class MetricType(Enum):
    """Types of performance metrics"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class PerformanceMetric:
    """Performance metric definition"""

    name: str
    type: MetricType
    description: str
    labels: List[str] = field(default_factory=list)
    unit: str = ""


@dataclass
class AlertRule:
    """Alert rule definition"""

    name: str
    condition: str  # PromQL expression
    duration: str = "5m"
    severity: AlertSeverity = AlertSeverity.WARNING
    description: str = ""
    summary: str = ""


@dataclass
class PerformanceThreshold:
    """Performance threshold for alerting"""

    metric: str
    warning_threshold: float
    critical_threshold: float
    description: str


@dataclass
class EBPFMetricSnapshot:
    """Point-in-time local metrics used by the performance monitor."""

    packets_processed: int = 0
    latency_microseconds: float = 0.0
    cpu_usage_percent: float = 0.0
    memory_usage_bytes: float = 0.0

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "EBPFMetricSnapshot":
        return cls(
            packets_processed=max(0, int(payload.get("packets_processed", 0))),
            latency_microseconds=max(
                0.0,
                float(payload.get("latency_microseconds", 0.0)),
            ),
            cpu_usage_percent=max(0.0, float(payload.get("cpu_usage_percent", 0.0))),
            memory_usage_bytes=max(0.0, float(payload.get("memory_usage_bytes", 0.0))),
        )


class EBPFSystemMetricSource:
    """Reads local runtime counters without fabricating eBPF-only values."""

    def __init__(
        self,
        proc_net_dev: Path = Path("/proc/net/dev"),
        bpffs_root: Path = Path("/sys/fs/bpf"),
    ):
        self.proc_net_dev = proc_net_dev
        self.bpffs_root = bpffs_root

    def snapshot(self) -> EBPFMetricSnapshot:
        return EBPFMetricSnapshot(
            packets_processed=self._read_packets_processed(),
            latency_microseconds=0.0,
            cpu_usage_percent=0.0,
            memory_usage_bytes=self._read_bpffs_size_bytes(),
        )

    def _read_packets_processed(self) -> int:
        try:
            lines = self.proc_net_dev.read_text(encoding="utf-8").splitlines()[2:]
        except OSError:
            return 0

        total = 0
        for line in lines:
            if ":" not in line:
                continue
            _iface, counters = line.split(":", 1)
            fields = counters.split()
            if len(fields) < 10:
                continue
            try:
                rx_packets = int(fields[1])
                tx_packets = int(fields[9])
            except ValueError:
                continue
            total += max(0, rx_packets) + max(0, tx_packets)
        return total

    def _read_bpffs_size_bytes(self) -> float:
        if not self.bpffs_root.exists():
            return 0.0

        total = 0
        for root, _dirs, files in os.walk(self.bpffs_root):
            for filename in files:
                path = Path(root) / filename
                try:
                    total += max(0, path.stat().st_size)
                except OSError:
                    continue
        return float(total)


class EBPFPerformanceMonitor:
    """
    Comprehensive performance monitoring for eBPF programs.

    Collects metrics, monitors thresholds, and generates alerts.
    Integrates with Prometheus and provides dashboard configurations.
    """

    def __init__(self, prometheus_port: int = 9090, metric_source: Any = None):
        self.prometheus_port = prometheus_port
        self.metric_source = metric_source or EBPFSystemMetricSource()
        self.metrics: Dict[str, Any] = {}
        self._registry = CollectorRegistry() if PROMETHEUS_AVAILABLE else None
        self.alert_rules: List[AlertRule] = []
        self.thresholds: List[PerformanceThreshold] = []
        self.performance_history: Dict[str, List[float]] = {}
        self.monitoring_active = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.thinking_coach = AgentThinkingCoach(
            agent_id="ebpf-performance-monitor",
            role="monitoring",
            capabilities=("security", "zero-trust"),
            extra_techniques=("mape_k", "causal_analysis", "chaos_driven_design"),
        )
        self._last_thinking_context: Optional[Dict[str, Any]] = None

        # Initialize standard metrics
        self._init_standard_metrics()

        # Initialize standard alert rules
        self._init_standard_alerts()

        # Initialize thresholds
        self._init_standard_thresholds()

    def _record_thinking_context(
        self,
        *,
        operation: str,
        goal: str,
        constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        safe_task = {
            "task_type": "ebpf_performance_monitoring",
            "goal": goal,
            "constraints": {
                "operation": operation,
                "redacted": True,
                **constraints,
            },
            "safety_boundary": (
                "Monitor local eBPF performance with bounded metadata; do not "
                "expose raw alert messages, sensitive labels, paths, or operator "
                "annotations in thinking context."
            ),
        }
        self._last_thinking_context = self.thinking_coach.prepare_task(safe_task)
        return self._last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        """Expose performance-monitor thinking state without task secrets."""

        return {
            **self.thinking_coach.status(),
            "last_context": self._last_thinking_context,
        }

    def _init_standard_metrics(self):
        """Initialize standard eBPF performance metrics"""
        standard_metrics = [
            PerformanceMetric(
                name="ebpf_packets_processed_total",
                type=MetricType.COUNTER,
                description="Total packets processed by eBPF programs",
                labels=["program", "interface"],
            ),
            PerformanceMetric(
                name="ebpf_packets_dropped_total",
                type=MetricType.COUNTER,
                description="Total packets dropped by eBPF programs",
                labels=["program", "interface", "reason"],
            ),
            PerformanceMetric(
                name="ebpf_processing_latency_microseconds",
                type=MetricType.HISTOGRAM,
                description="eBPF packet processing latency",
                labels=["program", "interface"],
                unit="microseconds",
            ),
            PerformanceMetric(
                name="ebpf_cpu_usage_percent",
                type=MetricType.GAUGE,
                description="CPU usage percentage by eBPF programs",
                labels=["program", "interface"],
            ),
            PerformanceMetric(
                name="ebpf_memory_usage_bytes",
                type=MetricType.GAUGE,
                description="Memory usage by eBPF maps and programs",
                labels=["program", "map_type"],
            ),
            PerformanceMetric(
                name="ebpf_flows_active",
                type=MetricType.GAUGE,
                description="Number of active network flows",
                labels=["interface"],
            ),
            PerformanceMetric(
                name="ebpf_errors_total",
                type=MetricType.COUNTER,
                description="Total eBPF program errors",
                labels=["program", "error_type"],
            ),
            PerformanceMetric(
                name="ebpf_program_load_time_seconds",
                type=MetricType.HISTOGRAM,
                description="Time taken to load eBPF programs",
                labels=["program"],
            ),
        ]

        for metric in standard_metrics:
            self._register_metric(metric)

    def _register_metric(self, metric: PerformanceMetric):
        """Register a metric with Prometheus"""
        if not PROMETHEUS_AVAILABLE:
            logger.warning(f"Prometheus not available, skipping metric: {metric.name}")
            return

        if metric.type == MetricType.COUNTER:
            self.metrics[metric.name] = Counter(
                metric.name, metric.description, metric.labels, registry=self._registry
            )
        elif metric.type == MetricType.GAUGE:
            self.metrics[metric.name] = Gauge(
                metric.name, metric.description, metric.labels, registry=self._registry
            )
        elif metric.type == MetricType.HISTOGRAM:
            self.metrics[metric.name] = Histogram(
                metric.name, metric.description, metric.labels, registry=self._registry
            )

    def _init_standard_alerts(self):
        """Initialize standard alert rules"""
        self.alert_rules = [
            AlertRule(
                name="EBPFHighLatency",
                condition="histogram_quantile(0.95, rate(ebpf_processing_latency_microseconds_bucket[5m])) > 100000",
                duration="5m",
                severity=AlertSeverity.WARNING,
                description="eBPF packet processing latency is above 100µs (95th percentile)",
                summary="High eBPF processing latency detected",
            ),
            AlertRule(
                name="EBPFPacketDrops",
                condition="rate(ebpf_packets_dropped_total[5m]) / rate(ebpf_packets_processed_total[5m]) > 0.05",
                duration="2m",
                severity=AlertSeverity.CRITICAL,
                description="Packet drop rate exceeds 5%",
                summary="High packet drop rate in eBPF programs",
            ),
            AlertRule(
                name="EBPFHighCPUUsage",
                condition="ebpf_cpu_usage_percent > 80",
                duration="5m",
                severity=AlertSeverity.WARNING,
                description="eBPF CPU usage above 80%",
                summary="High CPU usage by eBPF programs",
            ),
            AlertRule(
                name="EBPFMemoryPressure",
                condition="ebpf_memory_usage_bytes > 100000000",  # 100MB
                duration="10m",
                severity=AlertSeverity.WARNING,
                description="eBPF memory usage above 100MB",
                summary="High memory usage by eBPF programs",
            ),
            AlertRule(
                name="EBPFProgramErrors",
                condition="increase(ebpf_errors_total[10m]) > 10",
                duration="5m",
                severity=AlertSeverity.ERROR,
                description="More than 10 eBPF errors in 10 minutes",
                summary="High error rate in eBPF programs",
            ),
        ]

    def _init_standard_thresholds(self):
        """Initialize standard performance thresholds"""
        self.thresholds = [
            PerformanceThreshold(
                metric="ebpf_processing_latency_microseconds",
                warning_threshold=50000,  # 50µs
                critical_threshold=100000,  # 100µs
                description="Packet processing latency",
            ),
            PerformanceThreshold(
                metric="ebpf_cpu_usage_percent",
                warning_threshold=70.0,
                critical_threshold=90.0,
                description="CPU usage percentage",
            ),
            PerformanceThreshold(
                metric="ebpf_memory_usage_bytes",
                warning_threshold=50000000,  # 50MB
                critical_threshold=100000000,  # 100MB
                description="Memory usage",
            ),
        ]

    async def start_monitoring(self):
        """Start performance monitoring"""
        if self.monitoring_active:
            return

        self._record_thinking_context(
            operation="start_monitoring",
            goal="start local eBPF performance monitoring loop",
            constraints={
                "prometheus_port_hash": _hash_value(self.prometheus_port),
                "metrics_registered": len(self.metrics),
                "threshold_count": len(self.thresholds),
            },
        )
        self.monitoring_active = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())

        logger.info("eBPF performance monitoring started")

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        if not self.monitoring_active:
            return

        self._record_thinking_context(
            operation="stop_monitoring",
            goal="stop local eBPF performance monitoring loop",
            constraints={
                "metrics_registered": len(self.metrics),
                "history_keys": sorted(self.performance_history.keys()),
            },
        )
        self.monitoring_active = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("eBPF performance monitoring stopped")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                await self._collect_metrics()
                await self._check_thresholds()
                await asyncio.sleep(10)  # Collect every 10 seconds
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)

    async def _collect_metrics(self):
        """Collect current performance metrics"""
        self._record_thinking_context(
            operation="collect_metrics",
            goal="collect bounded local eBPF performance metrics",
            constraints={
                "metrics_registered": len(self.metrics),
                "metric_source_type": type(self.metric_source).__name__,
            },
        )
        snapshot = self._read_metric_snapshot()

        if "ebpf_packets_processed_total" in self.metrics:
            self.metrics["ebpf_packets_processed_total"].labels(
                program="xdp_monitor", interface="eth0"
            ).inc(snapshot.packets_processed)

        if "ebpf_processing_latency_microseconds" in self.metrics:
            self.metrics["ebpf_processing_latency_microseconds"].labels(
                program="xdp_monitor", interface="eth0"
            ).observe(snapshot.latency_microseconds)

        # Store in history for trend analysis
        self._update_history("latency", snapshot.latency_microseconds)
        self._update_history("packets", snapshot.packets_processed)

    def _read_metric_snapshot(self) -> EBPFMetricSnapshot:
        try:
            snapshot = self.metric_source.snapshot()
        except Exception as exc:
            logger.warning("Failed to read eBPF performance snapshot: %s", exc)
            return EBPFMetricSnapshot()
        if isinstance(snapshot, EBPFMetricSnapshot):
            return snapshot
        if isinstance(snapshot, dict):
            try:
                return EBPFMetricSnapshot.from_mapping(snapshot)
            except (TypeError, ValueError) as exc:
                logger.warning("Invalid eBPF performance snapshot: %s", exc)
        return EBPFMetricSnapshot()

    def _update_history(self, metric_name: str, value: float):
        """Update performance history for trend analysis"""
        if metric_name not in self.performance_history:
            self.performance_history[metric_name] = []

        self.performance_history[metric_name].append(value)

        # Keep only last 100 values
        if len(self.performance_history[metric_name]) > 100:
            self.performance_history[metric_name].pop(0)

    async def _check_thresholds(self):
        """Check performance thresholds and generate alerts"""
        self._record_thinking_context(
            operation="check_thresholds",
            goal="evaluate eBPF performance thresholds",
            constraints={
                "threshold_count": len(self.thresholds),
                "threshold_metrics": sorted(
                    {threshold.metric for threshold in self.thresholds}
                ),
            },
        )
        for threshold in self.thresholds:
            current_value = self._get_current_metric_value(threshold.metric)

            if current_value > threshold.critical_threshold:
                await self._generate_alert(
                    f"CRITICAL: {threshold.description}",
                    f"Value {current_value} exceeds critical threshold {threshold.critical_threshold}",
                    AlertSeverity.CRITICAL,
                )
            elif current_value > threshold.warning_threshold:
                await self._generate_alert(
                    f"WARNING: {threshold.description}",
                    f"Value {current_value} exceeds warning threshold {threshold.warning_threshold}",
                    AlertSeverity.WARNING,
                )

    async def _generate_alert(self, title: str, message: str, severity: AlertSeverity):
        """Generate an alert"""
        self._record_thinking_context(
            operation="generate_alert",
            goal="generate bounded eBPF performance alert",
            constraints={
                "severity": severity.value,
                "title_hash": _hash_value(title),
                "message_hash": _hash_value(message),
                "alert_text_redacted": True,
            },
        )
        alert = {
            "title": title,
            "message": message,
            "severity": severity.value,
            "timestamp": time.time(),
            "source": "ebpf_performance_monitor",
        }

        logger.warning(f"Alert generated: {alert}")

        # Here you would send to alert manager, email, etc.
        # For now, just log it

    def _get_current_metric_value(self, metric_name: str) -> float:
        """Get current value of a metric from the configured source."""
        snapshot = self._read_metric_snapshot()
        if metric_name == "ebpf_processing_latency_microseconds":
            return snapshot.latency_microseconds
        elif metric_name == "ebpf_cpu_usage_percent":
            return snapshot.cpu_usage_percent
        elif metric_name == "ebpf_memory_usage_bytes":
            return snapshot.memory_usage_bytes
        elif metric_name == "ebpf_packets_processed_total":
            return float(snapshot.packets_processed)

        return 0.0

    def get_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        self._record_thinking_context(
            operation="get_performance_report",
            goal="build local eBPF performance report",
            constraints={
                "read_only": True,
                "metrics_registered": len(self.metrics),
                "alert_rule_count": len(self.alert_rules),
                "history_keys": sorted(self.performance_history.keys()),
            },
        )
        report = {
            "timestamp": time.time(),
            "metrics": {},
            "alerts": len(
                [r for r in self.alert_rules if self._check_alert_condition(r)]
            ),
            "trends": {},
        }

        # Current metrics
        for metric_name in self.metrics.keys():
            current_value = self._get_current_metric_value(metric_name)
            report["metrics"][metric_name] = current_value

        # Performance trends
        for metric_name, values in self.performance_history.items():
            if len(values) >= 10:
                report["trends"][metric_name] = {
                    "current": values[-1],
                    "average": statistics.mean(values),
                    "min": min(values),
                    "max": max(values),
                    "trend": (
                        "increasing"
                        if values[-1] > statistics.mean(values)
                        else "decreasing"
                    ),
                }

        return report

    def _check_alert_condition(self, rule: AlertRule) -> bool:
        """Check if an alert condition is met (simplified)"""
        # This would evaluate PromQL expressions
        # For now, return False
        return False

    def export_grafana_dashboard(self) -> Dict[str, Any]:
        """Export Grafana dashboard configuration"""
        return {
            "dashboard": {
                "title": "x0tta6bl4 eBPF Performance Monitoring",
                "tags": ["ebpf", "performance", "x0tta6bl4"],
                "timezone": "browser",
                "refresh": "30s",
                "panels": [
                    {
                        "title": "Packet Processing Rate",
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                        "targets": [
                            {
                                "expr": "rate(ebpf_packets_processed_total[5m])",
                                "legendFormat": "{{program}} on {{interface}}",
                            }
                        ],
                    },
                    {
                        "title": "Processing Latency (95th percentile)",
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
                        "targets": [
                            {
                                "expr": "histogram_quantile(0.95, rate(ebpf_processing_latency_microseconds_bucket[5m]))",
                                "legendFormat": "{{program}} latency",
                            }
                        ],
                    },
                    {
                        "title": "Packet Drop Rate",
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
                        "targets": [
                            {
                                "expr": "rate(ebpf_packets_dropped_total[5m]) / rate(ebpf_packets_processed_total[5m])",
                                "legendFormat": "{{program}} drop rate",
                            }
                        ],
                    },
                    {
                        "title": "CPU Usage",
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8},
                        "targets": [
                            {
                                "expr": "ebpf_cpu_usage_percent",
                                "legendFormat": "{{program}} CPU usage",
                            }
                        ],
                    },
                    {
                        "title": "Memory Usage",
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 16},
                        "targets": [
                            {
                                "expr": "ebpf_memory_usage_bytes",
                                "legendFormat": "{{program}} memory",
                            }
                        ],
                    },
                    {
                        "title": "Active Flows",
                        "type": "singlestat",
                        "gridPos": {"h": 8, "w": 6, "x": 12, "y": 16},
                        "targets": [
                            {
                                "expr": "ebpf_flows_active",
                                "legendFormat": "Active flows",
                            }
                        ],
                    },
                    {
                        "title": "Error Rate",
                        "type": "graph",
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 24},
                        "targets": [
                            {
                                "expr": "rate(ebpf_errors_total[5m])",
                                "legendFormat": "{{program}} {{error_type}}",
                            }
                        ],
                    },
                ],
            }
        }

    def export_prometheus_alerts(self) -> Dict[str, Any]:
        """Export Prometheus alert rules"""
        return {
            "groups": [
                {
                    "name": "ebpf_performance_alerts",
                    "rules": [
                        {
                            "alert": rule.name,
                            "expr": rule.condition,
                            "for": rule.duration,
                            "labels": {"severity": rule.severity.value},
                            "annotations": {
                                "summary": rule.summary,
                                "description": rule.description,
                            },
                        }
                        for rule in self.alert_rules
                    ],
                }
            ]
        }


# Convenience functions
async def start_performance_monitoring(port: int = 9090) -> EBPFPerformanceMonitor:
    """Start eBPF performance monitoring"""
    monitor = EBPFPerformanceMonitor(port)
    await monitor.start_monitoring()
    return monitor


def generate_performance_report(monitor: EBPFPerformanceMonitor) -> str:
    """Generate human-readable performance report"""
    report = monitor.get_performance_report()

    output = []
    output.append("eBPF Performance Report")
    output.append("=" * 50)
    output.append(f"Generated: {time.ctime(report['timestamp'])}")
    output.append("")

    output.append("Current Metrics:")
    for metric, value in report["metrics"].items():
        output.append(f"  {metric}: {value}")

    output.append("")
    output.append("Performance Trends:")
    for metric, trend in report["trends"].items():
        output.append(f"  {metric}:")
        output.append(f"    Current: {trend['current']:.2f}")
        output.append(f"    Average: {trend['average']:.2f}")
        output.append(f"    Range: {trend['min']:.2f} - {trend['max']:.2f}")
        output.append(f"    Trend: {trend['trend']}")

    output.append("")
    output.append(f"Active Alerts: {report['alerts']}")

    return "\n".join(output)


if __name__ == "__main__":
    # Example usage
    async def main():
        monitor = await start_performance_monitoring()

        # Run for a bit
        await asyncio.sleep(30)

        # Generate report
        report = generate_performance_report(monitor)
        print(report)

        # Export dashboard
        dashboard = monitor.export_grafana_dashboard()
        with open("ebpf_dashboard.json", "w") as f:
            json.dump(dashboard, f, indent=2)

        # Export alerts
        alerts = monitor.export_prometheus_alerts()
        with open("ebpf_alerts.yml", "w") as f:
            json.dump(alerts, f, indent=2)

        await monitor.stop_monitoring()

    asyncio.run(main())
