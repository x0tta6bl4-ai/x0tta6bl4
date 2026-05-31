import httpx
import pytest
import pytest_asyncio

from src.coordination.events import EventBus, EventType
from src.core.app import app
from src.mesh.metric_evidence_policy import (
    MESH_METRIC_POLICY_KEY,
    build_mesh_metric_evidence_policy,
)


class DummyMonkey:
    pass


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as tc:
        yield tc


@pytest.mark.asyncio
async def test_mesh_endpoints(monkeypatch, client):
    import src.network.yggdrasil_client as yc

    monkeypatch.setattr(
        yc,
        "get_yggdrasil_status",
        lambda: {
            "status": "online",
            "node": {"public_key": "PK", "ipv6_address": "200::1"},
        },
    )
    monkeypatch.setattr(
        yc,
        "get_yggdrasil_peers",
        lambda: {"status": "ok", "peers": [{"remote": "10.0.0.1"}], "count": 1},
    )
    monkeypatch.setattr(
        yc, "get_yggdrasil_routes", lambda: {"status": "ok", "routing_table_size": 5}
    )

    r1 = await client.get("/mesh/status")
    assert r1.status_code == 200
    payload = r1.json()
    assert payload["status"] == "online"
    assert "node" in payload
    assert payload["mesh_api_claim_gate"]["local_yggdrasil_observed_state_claim_allowed"] is True
    assert payload["mesh_api_claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert payload["mesh_api_claim_gate"]["customer_traffic_claim_allowed"] is False
    assert payload["mesh_api_claim_gate"]["external_dpi_bypass_claim_allowed"] is False
    assert payload["mesh_api_claim_gate"]["production_readiness_claim_allowed"] is False
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert payload["cross_plane_claim_gate"]["requested_claim_ids"] == [
        "dataplane_delivery",
        "traffic_delivery",
        "customer_traffic",
        "dpi_bypass",
        "production_readiness",
    ]

    r2 = await client.get("/mesh/peers")
    assert r2.status_code == 200
    peers_payload = r2.json()
    assert peers_payload["count"] == 1
    assert peers_payload["mesh_api_claim_gate"]["traffic_delivery_claim_allowed"] is False

    r3 = await client.get("/mesh/routes")
    assert r3.status_code == 200
    routes_payload = r3.json()
    assert routes_payload["routing_table_size"] == 5
    assert routes_payload["mesh_api_claim_gate"]["production_slo_claim_allowed"] is False


@pytest.mark.asyncio
async def test_mesh_status_endpoint_returns_yggdrasil_evidence(
    monkeypatch,
    tmp_path,
    client,
):
    import src.core.app as app_module
    import src.network.yggdrasil_client as yc

    class FakeCompleted:
        stdout = "Public key: TESTKEY\nIPv6 address: 200:dead:beef::1\n"
        stderr = ""
        returncode = 0

    bus = EventBus(project_root=str(tmp_path))
    monkeypatch.setattr(app_module, "_mesh_event_bus_from_request", lambda _request: bus)
    monkeypatch.setattr(yc, "_find_yggdrasilctl", lambda: "/usr/local/bin/yggdrasilctl")
    monkeypatch.setattr(yc.subprocess, "run", lambda *_args, **_kwargs: FakeCompleted())

    response = await client.get("/mesh/status")
    payload = response.json()
    events = bus.get_event_history(
        EventType.PIPELINE_STAGE_END,
        source_agent="yggdrasil-client",
        limit=10,
    )
    event_payload = events[-1].data
    event_text = str(event_payload)

    assert response.status_code == 200
    assert payload["status"] == "online"
    assert payload["evidence"]["event_ids"] == [events[-1].event_id]
    assert payload["evidence"]["redacted"] is True
    assert payload["control_policy_evidence"]["status"] == "missing"
    assert payload["control_policy_evidence"]["redacted"] is True
    assert payload["mesh_api_claim_gate"]["surface"] == "mesh_api.status"
    assert payload["mesh_api_claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert payload["cross_plane_claim_gate"]["surface"] == "mesh_api.status"
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert event_payload["observed_state"] is True
    assert event_payload["output"]["output_redacted"] is True
    assert "TESTKEY" not in event_text
    assert "200:dead:beef" not in event_text


@pytest.mark.asyncio
async def test_mesh_endpoint_returns_redacted_control_policy_evidence(
    monkeypatch,
    tmp_path,
    client,
):
    import src.core.app as app_module
    import src.network.yggdrasil_client as yc

    bus = EventBus(project_root=str(tmp_path))
    policy = build_mesh_metric_evidence_policy(
        {
            "mesh_metric_source_available": 1.0,
            "mesh_metric_dataplane_samples": 0.0,
            "mesh_metric_estimated_samples": 1.0,
            "mesh_metric_fallback_samples": 0.0,
        }
    )
    policy_event = bus.publish(
        EventType.PIPELINE_STAGE_END,
        "core-mapek-loop",
        {
            "operation": "enforce_mesh_optimization",
            "directives": {
                MESH_METRIC_POLICY_KEY: policy,
                "peer": "tcp://10.0.0.1:9000",
            },
        },
    )

    monkeypatch.setattr(app_module, "_mesh_event_bus_from_request", lambda _request: bus)
    monkeypatch.setattr(
        yc,
        "get_yggdrasil_peers",
        lambda **_kwargs: {"status": "ok", "peers": [], "count": 0},
    )

    response = await client.get("/mesh/peers")
    payload = response.json()
    control_evidence = payload["control_policy_evidence"]

    assert response.status_code == 200
    assert payload["mesh_api_claim_gate"]["surface"] == "mesh_api.peers"
    assert payload["mesh_api_claim_gate"]["control_policy_observation_claim_allowed"] is True
    assert payload["mesh_api_claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert control_evidence["status"] == "available"
    assert control_evidence["source_agents"] == ["core-mapek-loop"]
    assert control_evidence["event_ids"] == [policy_event.event_id]
    assert (
        control_evidence[MESH_METRIC_POLICY_KEY]["decision_basis"]
        == "estimate_or_fallback_based"
    )
    assert control_evidence[MESH_METRIC_POLICY_KEY]["redacted"] is True
    assert "10.0.0.1" not in str(control_evidence)


def test_status_api_response_keeps_local_health_out_of_production_claims():
    import src.core.app as app_module

    payload = app_module._status_api_response(
        {"status": "healthy", "version": "test", "mesh": {"connected_peers": 1}}
    )

    assert payload["status"] == "healthy"
    assert payload["status_api_claim_gate"]["local_system_health_observation_claim_allowed"] is True
    assert payload["status_api_claim_gate"]["local_mesh_health_observation_claim_allowed"] is True
    assert payload["status_api_claim_gate"]["production_readiness_claim_allowed"] is False
    assert payload["status_api_claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert payload["status_api_claim_gate"]["external_dpi_bypass_claim_allowed"] is False
    assert payload["status_api_claim_gate"]["settlement_finality_claim_allowed"] is False
    assert payload["cross_plane_claim_gate"]["surface"] == "status_api"
    assert payload["cross_plane_claim_gate"]["allowed"] is False


@pytest.mark.asyncio
async def test_health_endpoint_again(client):
    r = await client.get("/health")
    assert r.status_code == 200
    payload = r.json()
    assert payload["status"] == "ok"
    assert payload["health_api_claim_gate"]["local_liveness_observation_claim_allowed"] is True
    assert payload["health_api_claim_gate"]["production_readiness_claim_allowed"] is False
    assert payload["health_api_claim_gate"]["dataplane_delivery_claim_allowed"] is False
    assert payload["health_api_claim_gate"]["external_dpi_bypass_claim_allowed"] is False
    assert payload["health_api_claim_gate"]["settlement_finality_claim_allowed"] is False
    assert payload["cross_plane_claim_gate"]["surface"] == "health_api.health"
    assert payload["cross_plane_claim_gate"]["allowed"] is False


@pytest.mark.asyncio
async def test_metrics_endpoint_has_local_only_claim_boundary_headers(client):
    r = await client.get("/metrics")

    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert (
        r.headers["x-x0tta6bl4-claim-gate-schema"]
        == "x0tta6bl4.metrics_api_claim_boundary_headers.v1"
    )
    assert (
        r.headers["x-x0tta6bl4-local-metrics-observation-claim-allowed"] == "true"
    )
    assert r.headers["x-x0tta6bl4-production-readiness-claim-allowed"] == "false"
    assert r.headers["x-x0tta6bl4-production-slo-claim-allowed"] == "false"
    assert r.headers["x-x0tta6bl4-dataplane-delivery-claim-allowed"] == "false"
    assert r.headers["x-x0tta6bl4-traffic-delivery-claim-allowed"] == "false"
    assert r.headers["x-x0tta6bl4-customer-traffic-claim-allowed"] == "false"
    assert r.headers["x-x0tta6bl4-external-dpi-bypass-claim-allowed"] == "false"
    assert r.headers["x-x0tta6bl4-settlement-finality-claim-allowed"] == "false"
