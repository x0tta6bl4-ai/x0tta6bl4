#!/usr/bin/env python3
"""Tests for mesh node Prometheus metrics (issue #170).

Validates that deploy/docker-compose/mesh_node.py and quickstart/mesh_node.py
use the x0tta6bl4_mesh_ prefix and expose the required metrics.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

REQUIRED_METRICS = {
    "x0tta6bl4_mesh_pqc_handshakes_total": "counter",
    "x0tta6bl4_mesh_recovery_total": "counter",
    "x0tta6bl4_mesh_peers_connected": "gauge",
    "x0tta6bl4_mesh_uptime_seconds": "gauge",
    "x0tta6bl4_mesh_routing_table_size": "gauge",
    "x0tta6bl4_mesh_forwarded_messages_total": "counter",
    "x0tta6bl4_mesh_route_refresh_total": "gauge",
    "x0tta6bl4_mesh_health_score": "gauge",
}

MESH_NODE_FILES = [
    ROOT / "deploy" / "docker-compose" / "mesh_node.py",
    ROOT / "quickstart" / "mesh_node.py",
]


@pytest.mark.parametrize("mesh_file", MESH_NODE_FILES, ids=lambda p: p.name)
class TestMeshPrometheusMetrics:
    def test_all_required_metrics_defined(self, mesh_file: Path):
        """Each required metric name must appear in the source file."""
        source = mesh_file.read_text(encoding="utf-8")
        for metric_name in REQUIRED_METRICS:
            assert metric_name in source, (
                f"{mesh_file.name}: missing metric '{metric_name}'"
            )

    def test_no_old_unprefixed_metric_names(self, mesh_file: Path):
        """Old unprefixed metric names must not appear as Counter/Gauge definitions."""
        source = mesh_file.read_text(encoding="utf-8")
        old_names = [
            '"pqc_handshakes_total"',
            '"mapek_recovery_actions_total"',
            '"active_peers_count"',
            '"mesh_health_score"',
            '"mesh_routing_table_size"',
            '"mesh_forwarded_messages_total"',
            '"mesh_route_refresh_total"',
        ]
        for old in old_names:
            assert old not in source, (
                f"{mesh_file.name}: old unprefixed metric {old} still present"
            )

    def test_uptime_gauge_has_node_id_label(self, mesh_file: Path):
        """Uptime gauge must accept node_id label."""
        source = mesh_file.read_text(encoding="utf-8")
        assert 'x0tta6bl4_mesh_uptime_seconds' in source
        assert '"node_id"' in source

    def test_metrics_port_configurable(self, mesh_file: Path):
        """MESH_METRICS_PORT env var must be supported."""
        source = mesh_file.read_text(encoding="utf-8")
        assert "MESH_METRICS_PORT" in source

    def test_start_http_server_called(self, mesh_file: Path):
        """start_http_server must be called to expose /metrics."""
        source = mesh_file.read_text(encoding="utf-8")
        assert "start_http_server" in source
