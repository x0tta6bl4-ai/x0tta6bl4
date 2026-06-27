"""Unit tests for MaaS analytics EventBus evidence."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_analytics as analytics_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


def test_analytics_summary_publishes_redacted_observed_state(
    monkeypatch,
    tmp_path,
):
    email = "analytics-summary-secret@example.test"
    user_id = "analytics-summary-user-secret"
    mesh_id = "analytics-summary-mesh-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="operator", plan="pro")
    calls = []

    class _Analytics:
        def __init__(self, db, redis_client):
            calls.append(("init", db, redis_client))

        def get_mesh_summary(self, mesh_id_arg, owner_id_arg):
            calls.append((mesh_id_arg, owner_id_arg))
            return {
                "mesh_id": mesh_id_arg,
                "cost_maas_total": 12.34,
                "cost_aws_estimate": 45.0,
                "savings_pct": 72.6,
                "pqc_status": True,
                "nodes_total": 3,
                "nodes_online": 2,
                "health_score": 0.667,
            }

    monkeypatch.setattr(analytics_mod, "MaaSAnalyticsService", _Analytics)

    result = asyncio.run(
        analytics_mod.get_mesh_analytics(
            mesh_id,
            request,
            current_user=user,
            db=SimpleNamespace(name="analytics-summary-db-secret"),
        )
    )

    assert result.mesh_id == mesh_id
    assert calls[-1] == (mesh_id, user_id)
    payloads = _payloads(bus, "maas-analytics-summary-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_analytics_summary_read"
    assert payload["service_name"] == "maas-analytics-summary-read"
    assert payload["layer"] == "api_analytics_summary_observed_state"
    assert payload["actor_user_id_hash"] == analytics_mod._redacted_sha256_prefix(user_id)
    assert payload["actor_email_hash"] == analytics_mod._redacted_sha256_prefix(
        email.lower()
    )
    assert payload["mesh_id_hash"] == analytics_mod._redacted_sha256_prefix(mesh_id)
    assert payload["nodes_total"] == 3
    assert payload["nodes_online"] == 2
    assert payload["health_score"] == 0.667
    assert payload["read_only"] is True
    assert payload["observed_state"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        user_id,
        mesh_id,
        "analytics-summary-db-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_analytics_timeseries_publishes_success_and_denied_evidence(
    monkeypatch,
    tmp_path,
):
    email = "analytics-timeseries-secret@example.test"
    user_id = "analytics-timeseries-user-secret"
    mesh_id = "analytics-timeseries-mesh-secret"
    missing_mesh_id = "analytics-timeseries-missing-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="operator", plan="pro")

    class _Analytics:
        def __init__(self, db, redis_client):
            pass

        def get_mesh_timeseries(self, mesh_id_arg, owner_id_arg, time_range):
            if mesh_id_arg == missing_mesh_id:
                return None
            return {
                "mesh_id": mesh_id_arg,
                "range": time_range,
                "nodes_total": 4,
                "data": [
                    {"timestamp": "2026-05-30T12:00:00", "health": 100.0},
                    {"timestamp": "2026-05-30T13:00:00", "health": 75.0},
                ],
            }

    monkeypatch.setattr(analytics_mod, "MaaSAnalyticsService", _Analytics)

    result = asyncio.run(
        analytics_mod.get_mesh_timeseries(
            mesh_id,
            request,
            time_range="7d",
            current_user=user,
            db=SimpleNamespace(name="analytics-timeseries-db-secret"),
        )
    )

    assert result["mesh_id"] == mesh_id
    payloads = _payloads(bus, "maas-analytics-timeseries-read")
    assert len(payloads) == 1
    success_payload = payloads[0]
    assert success_payload["operation"] == "maas_analytics_timeseries_read"
    assert success_payload["service_name"] == "maas-analytics-timeseries-read"
    assert success_payload["layer"] == "api_analytics_timeseries_observed_state"
    assert success_payload["status"] == "success"
    assert success_payload["time_range"] == "7d"
    assert success_payload["points_count"] == 2
    assert success_payload["nodes_total"] == 4

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            analytics_mod.get_mesh_timeseries(
                missing_mesh_id,
                request,
                current_user=user,
                db=SimpleNamespace(name="analytics-timeseries-db-secret"),
            )
        )
    assert exc.value.status_code == 404
    payloads = _payloads(bus, "maas-analytics-timeseries-read")
    assert len(payloads) == 2
    denied_payload = payloads[1]
    assert denied_payload["status"] == "denied"
    assert denied_payload["http_status_code"] == 404
    assert denied_payload["reason"] == "mesh_not_found"

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, user_id, mesh_id, missing_mesh_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_analytics_roi_publishes_redacted_economy_evidence(
    monkeypatch,
    tmp_path,
):
    email = "analytics-roi-secret@example.test"
    user_id = "analytics-roi-user-secret"
    mesh_id = "analytics-roi-mesh-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="operator", plan="pro")

    class _Analytics:
        def __init__(self, db, redis_client):
            pass

        def get_marketplace_roi(self, mesh_id_arg, owner_id_arg):
            return {
                "mesh_id": mesh_id_arg,
                "listings": {
                    "total": 5,
                    "available": 2,
                    "rented": 2,
                    "in_escrow": 1,
                },
                "revenue": {
                    "hourly_cents": 350,
                    "hourly_usd": 3.5,
                    "monthly_estimate_usd": 2520.0,
                },
            }

    monkeypatch.setattr(analytics_mod, "MaaSAnalyticsService", _Analytics)

    result = asyncio.run(
        analytics_mod.get_marketplace_roi(
            mesh_id,
            request,
            current_user=user,
            db=SimpleNamespace(name="analytics-roi-db-secret"),
        )
    )

    assert result["mesh_id"] == mesh_id
    payloads = _payloads(bus, "maas-analytics-roi-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_analytics_roi_read"
    assert payload["service_name"] == "maas-analytics-roi-read"
    assert payload["layer"] == "api_analytics_roi_observed_state"
    assert payload["mesh_id_hash"] == analytics_mod._redacted_sha256_prefix(mesh_id)
    assert payload["listings_total"] == 5
    assert payload["listings_available"] == 2
    assert payload["listings_rented"] == 2
    assert payload["listings_in_escrow"] == 1
    assert payload["hourly_revenue_cents"] == 350
    assert payload["monthly_estimate_usd"] == 2520.0
    assert payload["economy_projection"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, user_id, mesh_id, "analytics-roi-db-secret"):
        assert raw_value not in serialized
        assert raw_value not in raw_log
