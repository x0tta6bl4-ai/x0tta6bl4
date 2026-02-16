"""Unit tests for causal analysis API handlers."""

from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.core import causal_api


@dataclass
class _Dashboard:
    incident_id: str
    score: float


@pytest.mark.asyncio
async def test_get_causal_analysis_returns_404_for_unknown_incident():
    causal_api._causal_engine = SimpleNamespace(incidents={})
    causal_api._visualizer = SimpleNamespace()

    with pytest.raises(HTTPException) as exc:
        await causal_api.get_causal_analysis("missing")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_causal_analysis_success():
    causal_api._causal_engine = SimpleNamespace(incidents={"inc-1": object()})
    causal_api._visualizer = SimpleNamespace(
        generate_dashboard_data=lambda incident_id: _Dashboard(
            incident_id=incident_id, score=0.9
        )
    )

    payload = await causal_api.get_causal_analysis("inc-1")

    assert payload["incident_id"] == "inc-1"
    assert payload["score"] == 0.9


@pytest.mark.asyncio
async def test_create_demo_incident_returns_incident_and_dashboard():
    causal_api._causal_engine = SimpleNamespace(incidents={"demo-1": object()})
    causal_api._visualizer = SimpleNamespace(
        generate_demo_incident=lambda: "demo-1",
        generate_dashboard_data=lambda incident_id: _Dashboard(
            incident_id=incident_id, score=1.0
        ),
    )

    payload = await causal_api.create_demo_incident()

    assert payload["incident_id"] == "demo-1"
    assert payload["dashboard_data"]["score"] == 1.0


@pytest.mark.asyncio
async def test_list_incidents_aggregates_metadata():
    incident = SimpleNamespace(
        timestamp=datetime(2026, 1, 1),
        node_id="n1",
        service_id="svc",
        anomaly_type="latency",
        severity=SimpleNamespace(value="high"),
    )
    causal_api._causal_engine = SimpleNamespace(incidents={"inc-1": incident})
    causal_api._visualizer = SimpleNamespace()

    payload = await causal_api.list_incidents()

    assert payload["total"] == 1
    assert payload["incidents"][0]["event_id"] == "inc-1"
    assert payload["incidents"][0]["severity"] == "high"
