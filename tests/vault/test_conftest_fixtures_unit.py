"""Direct fixture-body tests for tests/vault/conftest.py coverage."""

from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def _vault_conftest_ns():
    path = Path(__file__).with_name("conftest.py")
    return runpy.run_path(str(path))


def test_event_loop_fixture_body_executes_and_closes():
    ns = _vault_conftest_ns()
    event_loop = getattr(ns["event_loop"], "__wrapped__", ns["event_loop"])
    gen = event_loop()
    loop = next(gen)
    assert loop is not None
    assert loop.is_closed() is False
    with pytest.raises(StopIteration):
        next(gen)
    assert loop.is_closed() is True


def test_vault_fixture_factories_cover_return_lines():
    ns = _vault_conftest_ns()

    health_monitor = getattr(
        ns["health_monitor"], "__wrapped__", ns["health_monitor"]
    )
    metrics_reporter = getattr(
        ns["metrics_reporter"], "__wrapped__", ns["metrics_reporter"]
    )
    sample_database_credentials = getattr(
        ns["sample_database_credentials"],
        "__wrapped__",
        ns["sample_database_credentials"],
    )
    mock_secret_response = getattr(
        ns["mock_secret_response"], "__wrapped__", ns["mock_secret_response"]
    )
    vault_integration_config = getattr(
        ns["vault_integration_config"],
        "__wrapped__",
        ns["vault_integration_config"],
    )

    fake_client = MagicMock()
    assert health_monitor(fake_client) is not None
    assert metrics_reporter(fake_client) is not None

    sample = sample_database_credentials()
    response = mock_secret_response(sample)
    assert response["data"]["data"]["username"] == sample["username"]

    cfg = vault_integration_config()
    assert cfg.client.vault_addr == "https://vault-test:8200"
    assert cfg.monitor.enabled is True


def test_reset_prometheus_registry_handles_unregister_errors_and_importerror(
    monkeypatch,
):
    ns = _vault_conftest_ns()
    reset_prometheus_registry = getattr(
        ns["reset_prometheus_registry"],
        "__wrapped__",
        ns["reset_prometheus_registry"],
    )

    class _BadRegistry:
        def __init__(self):
            self._collector_to_names = {object(): {"x"}}

        def unregister(self, _collector):
            raise RuntimeError("boom")

    prom_mod = types.ModuleType("prometheus_client")
    prom_mod.REGISTRY = _BadRegistry()
    monkeypatch.setitem(sys.modules, "prometheus_client", prom_mod)
    gen = reset_prometheus_registry()
    next(gen)
    gen.close()

    monkeypatch.setitem(sys.modules, "prometheus_client", None)
    gen_import_error = reset_prometheus_registry()
    next(gen_import_error)
    gen_import_error.close()
