from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.api.maas_analytics as analytics_mod


def test_analytics_readiness_ready_when_db_service_and_redis_are_available(monkeypatch):
    monkeypatch.setattr(analytics_mod, "_redis_client", object())
    db = MagicMock(spec=["query"])

    payload = analytics_mod._analytics_readiness_status(db)

    assert payload["status"] == "ready"
    assert payload["route_registered"] is True
    assert payload["lifecycle_binding"] == "route_import_only"
    assert payload["startup_hook_completed"] is None
    assert payload["analytics_runtime_ready"] is True
    assert payload["analytics_db_ready"] is True
    assert payload["analytics_service_ready"] is True
    assert payload["realtime_telemetry_ready"] is True
    assert payload["degraded_dependencies"] == []


def test_analytics_readiness_degraded_when_backing_state_is_missing(monkeypatch):
    monkeypatch.setattr(analytics_mod, "_redis_client", None)
    monkeypatch.setattr(analytics_mod, "MaaSAnalyticsService", None)

    payload = analytics_mod._analytics_readiness_status(SimpleNamespace())

    assert payload["status"] == "degraded"
    assert payload["analytics_runtime_ready"] is False
    assert payload["analytics_db_ready"] is False
    assert payload["analytics_service_ready"] is False
    assert payload["realtime_telemetry_ready"] is False
    assert payload["degraded_dependencies"] == [
        "database",
        "analytics_service",
        "redis_telemetry",
    ]
    assert "real-time Redis telemetry" in payload["claim_boundary"]


def test_analytics_readiness_endpoint_marks_degraded_dependencies(monkeypatch):
    monkeypatch.setattr(analytics_mod, "_redis_client", None)
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(
        analytics_mod.analytics_readiness(request=request, db=SimpleNamespace())
    )

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"database", "redis_telemetry"}
