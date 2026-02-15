"""
Grafana Dashboard Definitions

Provides pre-configured dashboards for monitoring the x0tta6bl4 system.
Includes dashboards for:
- System Performance & Health
- ML Pipeline Monitoring
- Network & Mesh Operations
- Security & Zero Trust
- Distributed Tracing
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class GrafanaPanel:
    """Grafana panel configuration"""

    title: str
    type: str
    targets: List[Dict[str, Any]]
    fieldConfig: Optional[Dict[str, Any]] = None
    options: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to Grafana panel dict"""
        panel = {
            "title": self.title,
            "type": self.type,
            "targets": self.targets,
        }
        if self.fieldConfig:
            panel["fieldConfig"] = self.fieldConfig
        if self.options:
            panel["options"] = self.options
        return panel


class GrafanaDashboardBuilder:
    """Builder for Grafana dashboards"""

    def __init__(self, title: str, uid: str, description: str = ""):
        """Initialize dashboard builder"""
        self.title = title
        self.uid = uid
        self.description = description
        self.panels: List[Dict[str, Any]] = []
        self.row_counter = 0
        self.panel_id_counter = 1

    def add_row(self, title: str) -> "GrafanaDashboardBuilder":
        """Add a collapsible row"""
        row = {
            "id": self.row_counter,
            "title": title,
            "type": "row",
            "collapsed": False,
        }
        self.panels.append(row)
        self.row_counter += 1
        return self

    def add_metric_gauge(
        self,
        title: str,
        metric: str,
        unit: str = "",
        min_val: float = 0,
        max_val: float = 100,
        thresholds: Optional[List[float]] = None,
    ) -> "GrafanaDashboardBuilder":
        """Add a gauge panel for metric"""
        panel = {
            "id": self.panel_id_counter,
            "title": title,
            "type": "gauge",
            "targets": [{"expr": metric, "refId": "A"}],
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "min": min_val,
                    "max": max_val,
                    "thresholds": {
                        "mode": "percentage",
                        "steps": thresholds
                        or [
                            {"color": "green", "value": None},
                            {"color": "yellow", "value": 70},
                            {"color": "red", "value": 90},
                        ],
                    },
                }
            },
        }
        self.panels.append(panel)
        self.panel_id_counter += 1
        return self

    def add_time_series(
        self,
        title: str,
        metrics: List[Dict[str, str]],
        legend: bool = True,
        yAxisLabel: str = "",
    ) -> "GrafanaDashboardBuilder":
        """Add a time series panel"""
        panel = {
            "id": self.panel_id_counter,
            "title": title,
            "type": "timeseries",
            "targets": metrics,
            "options": {
                "legend": {"showLegend": legend, "placement": "right"},
                "tooltip": {"mode": "multi"},
            },
            "fieldConfig": {
                "defaults": {
                    "custom": {
                        "hideFrom": {"tooltip": False, "viz": False, "legend": False}
                    }
                }
            },
        }
        self.panels.append(panel)
        self.panel_id_counter += 1
        return self

    def add_stat_panel(
        self, title: str, metric: str, unit: str = "", decimals: int = 2
    ) -> "GrafanaDashboardBuilder":
        """Add a stat panel"""
        panel = {
            "id": self.panel_id_counter,
            "title": title,
            "type": "stat",
            "targets": [{"expr": metric, "refId": "A"}],
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "decimals": decimals,
                    "custom": {
                        "hideFrom": {"tooltip": False, "viz": False, "legend": False}
                    },
                }
            },
        }
        self.panels.append(panel)
        self.panel_id_counter += 1
        return self

    def add_heatmap(
        self, title: str, metric: str, bucketOffset: int = 0, bucketSize: int = 10
    ) -> "GrafanaDashboardBuilder":
        """Add a heatmap panel"""
        panel = {
            "id": self.panel_id_counter,
            "title": title,
            "type": "heatmap",
            "targets": [{"expr": metric, "refId": "A", "format": "heatmap"}],
            "options": {"bucketOffset": bucketOffset, "bucketSize": bucketSize},
        }
        self.panels.append(panel)
        self.panel_id_counter += 1
        return self

    def build(self) -> Dict[str, Any]:
        """Build the dashboard"""
        dashboard = {
            "annotations": {"list": []},
            "editable": True,
            "gnetId": None,
            "graphTooltip": 0,
            "id": None,
            "links": [],
            "panels": self.panels,
            "refresh": "30s",
            "schemaVersion": 38,
            "style": "dark",
            "tags": ["x0tta6bl4"],
            "templating": {"list": []},
            "time": {"from": "now-6h", "to": "now"},
            "timepicker": {},
            "timezone": "browser",
            "title": self.title,
            "uid": self.uid,
            "version": 0,
            "description": self.description,
        }

        return dashboard


def create_system_health_dashboard() -> Dict[str, Any]:
    """Create System Health & Performance dashboard"""
    builder = GrafanaDashboardBuilder(
        title="x0tta6bl4 System Health",
        uid="system_health",
        description="Overall system health, CPU, memory, and network metrics",
    )

    builder.add_row("System Resources")
    builder.add_metric_gauge(
        "CPU Usage",
        "100 - (avg(rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)",
        unit="percent",
    )
    builder.add_metric_gauge(
        "Memory Usage",
        "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
        unit="percent",
    )
    builder.add_metric_gauge(
        "Disk Usage",
        "(1 - (node_filesystem_avail_bytes / node_filesystem_size_bytes)) * 100",
        unit="percent",
    )

    builder.add_row("Network Metrics")
    builder.add_time_series(
        "Network I/O",
        [
            {
                "expr": "rate(node_network_receive_bytes_total[5m])",
                "legendFormat": "RX",
                "refId": "A",
            },
            {
                "expr": "rate(node_network_transmit_bytes_total[5m])",
                "legendFormat": "TX",
                "refId": "B",
            },
        ],
    )

    builder.add_row("Application Health")
    builder.add_stat_panel(
        "Active Connections", "sum(x0tta6bl4_mesh_active_connections)", decimals=0
    )
    builder.add_stat_panel(
        "Error Rate", "rate(x0tta6bl4_errors_total[5m])", unit="short"
    )

    return builder.build()


def create_ml_pipeline_dashboard() -> Dict[str, Any]:
    """Create ML Pipeline Monitoring dashboard"""
    builder = GrafanaDashboardBuilder(
        title="x0tta6bl4 ML Pipeline",
        uid="ml_pipeline",
        description="Machine Learning model performance and training metrics",
    )

    builder.add_row("GraphSAGE Anomaly Detection")
    builder.add_time_series(
        "Inference Latency",
        [
            {
                "expr": "x0tta6bl4_graphsage_inference_latency_ms",
                "legendFormat": "Latency",
                "refId": "A",
            }
        ],
    )
    builder.add_metric_gauge(
        "Model Accuracy",
        "x0tta6bl4_graphsage_accuracy{type='current'}",
        min_val=0,
        max_val=1,
    )
    builder.add_stat_panel(
        "Anomalies Detected",
        "increase(x0tta6bl4_graphsage_anomalies_detected_total[1h])",
        decimals=0,
    )

    builder.add_row("RAG Pipeline")
    builder.add_time_series(
        "Retrieval Latency",
        [
            {
                "expr": "x0tta6bl4_rag_retrieval_latency_ms",
                "legendFormat": "Latency",
                "refId": "A",
            }
        ],
    )
    builder.add_stat_panel(
        "Documents Indexed", "x0tta6bl4_rag_documents_indexed", decimals=0
    )

    builder.add_row("LoRA Fine-tuning")
    builder.add_time_series(
        "Training Loss",
        [
            {
                "expr": "x0tta6bl4_lora_training_loss",
                "legendFormat": "Loss",
                "refId": "A",
            }
        ],
    )
    builder.add_stat_panel(
        "Trainable Parameters", "x0tta6bl4_lora_trainable_parameters", decimals=0
    )

    return builder.build()


def create_network_mesh_dashboard() -> Dict[str, Any]:
    """Create Network & Mesh Operations dashboard"""
    builder = GrafanaDashboardBuilder(
        title="x0tta6bl4 Network & Mesh",
        uid="network_mesh",
        description="Mesh network topology, routing, and connectivity metrics",
    )

    builder.add_row("Mesh Topology")
    builder.add_stat_panel(
        "Active Nodes", "count(x0tta6bl4_mesh_nodes_active)", decimals=0
    )
    builder.add_stat_panel(
        "Active Connections", "sum(x0tta6bl4_mesh_active_connections)", decimals=0
    )
    builder.add_metric_gauge(
        "Mesh Health", "x0tta6bl4_mesh_health_percent", unit="percent"
    )

    builder.add_row("Routing Performance")
    builder.add_time_series(
        "Message Latency Distribution",
        [
            {
                "expr": "histogram_quantile(0.50, x0tta6bl4_mesh_message_latency_ms)",
                "legendFormat": "p50",
                "refId": "A",
            },
            {
                "expr": "histogram_quantile(0.95, x0tta6bl4_mesh_message_latency_ms)",
                "legendFormat": "p95",
                "refId": "B",
            },
            {
                "expr": "histogram_quantile(0.99, x0tta6bl4_mesh_message_latency_ms)",
                "legendFormat": "p99",
                "refId": "C",
            },
        ],
    )

    builder.add_row("eBPF Network Programs")
    builder.add_stat_panel(
        "eBPF Programs Loaded", "count(x0tta6bl4_ebpf_programs_loaded)", decimals=0
    )
    builder.add_time_series(
        "eBPF Program Execution Time",
        [
            {
                "expr": "rate(x0tta6bl4_ebpf_execution_time_microseconds[5m])",
                "legendFormat": "Execution Rate",
                "refId": "A",
            }
        ],
    )

    return builder.build()


def create_security_dashboard() -> Dict[str, Any]:
    """Create Security & Zero Trust dashboard"""
    builder = GrafanaDashboardBuilder(
        title="x0tta6bl4 Security & Zero Trust",
        uid="security_zerotrust",
        description="Security metrics, SPIFFE/SPIRE, mTLS, and policy enforcement",
    )

    builder.add_row("SPIFFE/SPIRE Identity")
    builder.add_stat_panel(
        "Active SVIDs", "count(x0tta6bl4_spiffe_svid_active)", decimals=0
    )
    builder.add_time_series(
        "SVID Renewal Rate",
        [
            {
                "expr": "rate(x0tta6bl4_spiffe_svid_renewals_total[5m])",
                "legendFormat": "Renewals",
                "refId": "A",
            }
        ],
    )

    builder.add_row("mTLS & TLS 1.3")
    builder.add_stat_panel(
        "mTLS Connections", "sum(x0tta6bl4_mtls_connections_active)", decimals=0
    )
    builder.add_metric_gauge(
        "TLS Handshake Success Rate",
        "rate(x0tta6bl4_tls_handshake_success_total[5m]) / rate(x0tta6bl4_tls_handshake_total[5m]) * 100",
        unit="percent",
    )

    builder.add_row("Zero Trust Enforcement")
    builder.add_stat_panel(
        "Policy Decisions",
        "increase(x0tta6bl4_zerotrust_decisions_total[1h])",
        decimals=0,
    )
    builder.add_time_series(
        "Denied Requests",
        [
            {
                "expr": "rate(x0tta6bl4_zerotrust_denied_total[5m])",
                "legendFormat": "Denied Rate",
                "refId": "A",
            }
        ],
    )

    return builder.build()


def create_tracing_dashboard() -> Dict[str, Any]:
    """Create Distributed Tracing dashboard"""
    builder = GrafanaDashboardBuilder(
        title="x0tta6bl4 Distributed Tracing",
        uid="distributed_tracing",
        description="OpenTelemetry traces, span latency, and service dependencies",
    )

    builder.add_row("Span Metrics")
    builder.add_stat_panel(
        "Total Spans", "increase(x0tta6bl4_spans_total[1h])", decimals=0
    )
    builder.add_metric_gauge(
        "Span Success Rate",
        "rate(x0tta6bl4_spans_success_total[5m]) / rate(x0tta6bl4_spans_total[5m]) * 100",
        unit="percent",
    )

    builder.add_row("Latency Analysis")
    builder.add_heatmap("Span Latency Heatmap", "x0tta6bl4_span_duration_ms")

    builder.add_row("MAPE-K Loop Tracing")
    builder.add_time_series(
        "MAPE-K Phase Durations",
        [
            {
                "expr": "x0tta6bl4_mapek_monitor_duration_ms",
                "legendFormat": "Monitor",
                "refId": "A",
            },
            {
                "expr": "x0tta6bl4_mapek_analyze_duration_ms",
                "legendFormat": "Analyze",
                "refId": "B",
            },
            {
                "expr": "x0tta6bl4_mapek_plan_duration_ms",
                "legendFormat": "Plan",
                "refId": "C",
            },
            {
                "expr": "x0tta6bl4_mapek_execute_duration_ms",
                "legendFormat": "Execute",
                "refId": "D",
            },
        ],
    )

    return builder.build()


def export_dashboards_to_json(output_dir: Path) -> bool:
    """
    Export all dashboards to JSON files.

    Args:
        output_dir: Directory to export dashboards to

    Returns:
        True if successful
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)

        dashboards = {
            "system_health.json": create_system_health_dashboard(),
            "ml_pipeline.json": create_ml_pipeline_dashboard(),
            "network_mesh.json": create_network_mesh_dashboard(),
            "security_zerotrust.json": create_security_dashboard(),
            "distributed_tracing.json": create_tracing_dashboard(),
        }

        for filename, dashboard_config in dashboards.items():
            filepath = output_dir / filename
            with open(filepath, "w") as f:
                json.dump({"dashboard": dashboard_config}, f, indent=2)
            print(f"✅ Exported dashboard: {filename}")

        return True

    except Exception as e:
        print(f"❌ Failed to export dashboards: {e}")
        return False


def create_grafana_provisioning_config(
    datasource_url: str = "http://prometheus:9090",
) -> Dict[str, Any]:
    """
    Create Grafana provisioning configuration.

    Args:
        datasource_url: Prometheus datasource URL

    Returns:
        Provisioning config dict
    """
    config = {
        "apiVersion": 1,
        "providers": [
            {
                "name": "x0tta6bl4",
                "orgId": 1,
                "folder": "x0tta6bl4",
                "type": "file",
                "disableDeletion": False,
                "editable": True,
                "options": {"path": "/etc/grafana/provisioning/dashboards"},
            }
        ],
    }

    return config
