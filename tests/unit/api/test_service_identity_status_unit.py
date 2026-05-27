from __future__ import annotations

from fastapi.testclient import TestClient

from src.core.app import app
from src.coordination.events import EventBus, EventType
from src.api import service_identity_status as identity_api


def test_service_identity_status_endpoint_is_registered_and_redacted(monkeypatch):
    monkeypatch.setenv("X0TTA6BL4_SERVICE_SPIFFE_ID", "spiffe://secret/service")
    monkeypatch.setenv("X0TTA6BL4_SERVICE_DID", "did:mesh:secret")
    monkeypatch.setenv(
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "0xffffffffffffffffffffffffffffffffffffffff",
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/service-identity/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["redacted"] is True
    assert payload["services_total"] >= 20
    assert "spiffe://secret" not in response.text
    assert "did:mesh:secret" not in response.text
    assert "0xffff" not in response.text


def test_service_event_trace_filter_endpoint_maps_registered_layer():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/api/v1/service-identity/event-trace-filter",
        params={"layer": "swarm_consensus_to_control_plane"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["redacted"] is True
    assert payload["source_agents"] == ["swarm-pbft"]


def test_service_event_traces_endpoint_filters_and_redacts(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    bus.publish(
        EventType.PIPELINE_STAGE_START,
        "swarm-pbft",
        {
            "stage": "consensus",
            "spiffe_id": "spiffe://secret/workload",
            "identity": {
                "did": "did:mesh:secret",
                "wallet_address": "0xffffffffffffffffffffffffffffffffffffffff",
            },
        },
        target_agents={"agent-b"},
    )
    bus.publish(EventType.SYSTEM_ALERT, "pqc-rotator", {"stage": "noise"})
    monkeypatch.setattr(identity_api, "EventBus", lambda project_root=".": bus)

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/api/v1/service-identity/event-traces",
        params={"service_name": "swarm-pbft", "limit": 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["events_total"] == 1
    assert payload["events"][0]["source_agent"] == "swarm-pbft"
    assert payload["events"][0]["data"]["spiffe_id"] == "[redacted]"
    assert "spiffe://secret" not in response.text
    assert "did:mesh:secret" not in response.text
    assert "0xffff" not in response.text
