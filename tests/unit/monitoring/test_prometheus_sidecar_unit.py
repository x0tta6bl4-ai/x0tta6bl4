#!/usr/bin/env python3
"""Tests for Prometheus Docker Compose sidecar configuration (issue #170)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
COMPOSE_DIR = ROOT / "deploy" / "docker-compose"


class TestPrometheusSidecar:
    def test_override_file_exists(self):
        assert (COMPOSE_DIR / "docker-compose.override.yml").exists()

    def test_prometheus_yml_exists(self):
        assert (COMPOSE_DIR / "prometheus.yml").exists()

    def test_override_has_prometheus_service(self):
        override = yaml.safe_load(
            (COMPOSE_DIR / "docker-compose.override.yml").read_text()
        )
        assert "services" in override
        assert "prometheus" in override["services"]

    def test_override_prometheus_image(self):
        override = yaml.safe_load(
            (COMPOSE_DIR / "docker-compose.override.yml").read_text()
        )
        prom = override["services"]["prometheus"]
        assert "prom/prometheus" in prom["image"]

    def test_override_prometheus_volumes_prometheus_yml(self):
        override = yaml.safe_load(
            (COMPOSE_DIR / "docker-compose.override.yml").read_text()
        )
        volumes = override["services"]["prometheus"]["volumes"]
        assert any("prometheus.yml" in v for v in volumes)

    def test_override_prometheus_port_9090(self):
        override = yaml.safe_load(
            (COMPOSE_DIR / "docker-compose.override.yml").read_text()
        )
        ports = override["services"]["prometheus"]["ports"]
        assert any("9090" in p for p in ports)

    def test_prometheus_yml_scrape_config(self):
        prom = yaml.safe_load(
            (COMPOSE_DIR / "prometheus.yml").read_text()
        )
        assert "scrape_configs" in prom
        jobs = prom["scrape_configs"]
        assert len(jobs) >= 1
        assert jobs[0]["job_name"] == "x0tta6bl4-mesh"

    def test_prometheus_yml_targets_mesh_nodes(self):
        prom = yaml.safe_load(
            (COMPOSE_DIR / "prometheus.yml").read_text()
        )
        targets = prom["scrape_configs"][0]["static_configs"][0]["targets"]
        assert "mesh-node:9090" in targets
        assert "mesh-node-2:9090" in targets
