#!/usr/bin/env python3
"""Tests for Docker Compose mesh node healthchecks (issue #168)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_PATH = ROOT / "deploy" / "docker-compose" / "compose.yaml"

MESH_SERVICES = ["mesh-node", "mesh-node-2", "node-nl-bridge"]

HEALTHCHECK_FIELDS = {
    "test": list,
    "interval": str,
    "timeout": str,
    "retries": int,
    "start_period": str,
}


class TestMeshNodeHealthchecks:
    @classmethod
    def load_compose(cls) -> dict:
        return yaml.safe_load(COMPOSE_PATH.read_text())

    def test_compose_file_exists(self):
        assert COMPOSE_PATH.exists()

    def test_all_mesh_services_have_healthcheck(self):
        compose = self.load_compose()
        services = compose.get("services", {})
        for name in MESH_SERVICES:
            assert name in services, f"Service {name} not found"
            assert "healthcheck" in services[name], (
                f"Service {name} missing healthcheck"
            )

    def test_healthcheck_uses_python_not_curl(self):
        """python:3.12-slim has no curl — healthcheck must use python3."""
        compose = self.load_compose()
        for name in MESH_SERVICES:
            hc = compose["services"][name]["healthcheck"]
            test_cmd = hc["test"]
            assert "python3" in test_cmd, (
                f"{name}: healthcheck must use python3, got {test_cmd}"
            )
            assert "curl" not in str(test_cmd), (
                f"{name}: healthcheck must not use curl (not in slim image)"
            )

    def test_healthcheck_hits_correct_port(self):
        """Each node's healthcheck must hit its own PORT."""
        compose = self.load_compose()
        expected_ports = {
            "mesh-node": "9100",
            "mesh-node-2": "9103",
            "node-nl-bridge": "9102",
        }
        for name in MESH_SERVICES:
            hc = compose["services"][name]["healthcheck"]
            test_str = str(hc["test"])
            port = expected_ports[name]
            assert port in test_str, (
                f"{name}: healthcheck should hit port {port}, got {test_str}"
            )

    def test_healthcheck_intervals_arereasonable(self):
        compose = self.load_compose()
        for name in MESH_SERVICES:
            hc = compose["services"][name]["healthcheck"]
            assert hc["retries"] >= 3, f"{name}: retries should be >= 3"
            assert "start_period" in hc, f"{name}: missing start_period"

    def test_mesh_node_2_depends_on_healthy_mesh_node(self):
        """mesh-node-2 should wait for mesh-node to be healthy, not just started."""
        compose = self.load_compose()
        deps = compose["services"]["mesh-node-2"].get("depends_on", {})
        for dep_name, dep_config in deps.items():
            if dep_name == "mesh-node":
                assert dep_config.get("condition") == "service_healthy", (
                    f"mesh-node-2 depends_on mesh-node should be service_healthy, "
                    f"got {dep_config.get('condition')}"
                )

    def test_node_nl_bridge_depends_on_healthy_mesh_node(self):
        """node-nl-bridge should wait for mesh-node to be healthy."""
        compose = self.load_compose()
        deps = compose["services"]["node-nl-bridge"].get("depends_on", {})
        for dep_name, dep_config in deps.items():
            if dep_name == "mesh-node":
                assert dep_config.get("condition") == "service_healthy", (
                    f"node-nl-bridge depends_on mesh-node should be service_healthy"
                )
