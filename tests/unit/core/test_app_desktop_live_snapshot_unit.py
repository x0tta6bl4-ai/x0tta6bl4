"""Unit tests for the desktop app live snapshot endpoint."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.coordination.events import EventBus, EventType
from src.core.app import app_desktop


def test_platform_live_snapshot_returns_redacted_eventbus_state(tmp_path, monkeypatch) -> None:
    bus = EventBus(str(tmp_path))
    bus.publish(
        EventType.SYSTEM_ALERT,
        "unit-test-agent",
        {
            "status": "ok",
            "operation": "unit_live_snapshot",
            "api_token": "secret-token-value",
            "install_command": "curl https://example.invalid/secret | sh",
            "result_summary": {
                "checks_total": 2,
                "private_key": "secret-private-key",
            },
        },
    )
    monkeypatch.setattr(app_desktop, "get_event_bus", lambda _project_root=".": bus)

    response = TestClient(app_desktop.app).get("/api/v1/platform/live-snapshot?limit=5")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "x0tta6bl4.platform.live_snapshot.v1"
    assert body["event_bus"]["available"] is True
    assert body["event_bus"]["events_returned"] >= 1
    assert body["event_bus"]["payloads_redacted"] is True
    event = body["event_bus"]["recent_events"][-1]
    assert event["source_agent"] == "unit-test-agent"
    assert event["surface"] == "system"
    assert event["data"]["status"] == "ok"
    assert event["data"]["operation"] == "unit_live_snapshot"
    assert "api_token" in event["data"]["redacted_sensitive_keys"]
    assert "install_command" in event["data"]["redacted_sensitive_keys"]
    assert event["data"]["result_summary"] == {"checks_total": 2}
    assert body["cross_plane_claim_gate"]["allowed"] is False

    serialized = json.dumps(body, sort_keys=True)
    assert "secret-token-value" not in serialized
    assert "secret-private-key" not in serialized
    assert "https://example.invalid/secret" not in serialized


def test_platform_live_snapshot_limit_is_bounded(tmp_path, monkeypatch) -> None:
    bus = EventBus(str(tmp_path))
    monkeypatch.setattr(app_desktop, "get_event_bus", lambda _project_root=".": bus)

    response = TestClient(app_desktop.app).get("/api/v1/platform/live-snapshot?limit=101")

    assert response.status_code == 422


def test_platform_live_snapshot_groups_events_by_surface(tmp_path, monkeypatch) -> None:
    bus = EventBus(str(tmp_path))
    bus.publish(
        EventType.MARKETPLACE_ESCROW_HELD,
        "maas-marketplace",
        {
            "operation": "marketplace_rent_node",
            "transition": "held",
            "status": "success",
        },
    )
    monkeypatch.setattr(app_desktop, "get_event_bus", lambda _project_root=".": bus)

    response = TestClient(app_desktop.app).get("/api/v1/platform/live-snapshot?limit=5")

    assert response.status_code == 200, response.text
    event_bus = response.json()["event_bus"]
    assert event_bus["surface_counts"]["marketplace"] == 1
    assert event_bus["recent_by_surface"]["marketplace"][0]["surface"] == "marketplace"
    assert event_bus["recent_by_surface"]["marketplace"][0]["data"]["transition"] == "held"


def test_product_ideas_api_exposes_ten_scaffolded_products() -> None:
    client = TestClient(app_desktop.app)

    response = client.get("/api/v1/product/ideas")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "x0tta6bl4.product_ideas.portfolio.v1"
    assert body["ideas_total"] == 10
    assert body["claim_gate"]["production_readiness_claim_allowed"] is False
    assert body["claim_gate"]["customer_traffic_claim_allowed"] is False
    assert body["first_offer"] == "Self-hosted secure mesh access with proof-based status."
    assert {idea["idea_id"] for idea in body["ideas"]} == {
        "agent_black_box",
        "sovereign_office",
        "crisis_internet_kit",
        "devops_truth_detector",
        "remote_infra_caretaker",
        "abandoned_places_mesh",
        "paranoid_self_hosted_mesh",
        "node_trust_passport",
        "autonomous_network_repair",
        "industrial_edge_commander",
    }


def test_product_idea_api_returns_single_card_and_404_for_unknown() -> None:
    client = TestClient(app_desktop.app)

    response = client.get("/api/v1/product/ideas/agent_black_box")
    missing = client.get("/api/v1/product/ideas/nope")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["idea_id"] == "agent_black_box"
    assert body["paid_offer"]
    assert body["claim_gate"]["production_readiness_claim_allowed"] is False
    assert missing.status_code == 404


def test_product_pilot_package_api_exposes_first_paid_offer() -> None:
    client = TestClient(app_desktop.app)

    response = client.get("/api/v1/product/pilot-package")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "x0tta6bl4.product_ideas.pilot_package.v1"
    assert body["offer_name"] == "Self-hosted secure mesh access pilot"
    assert body["target_idea_id"] == "paranoid_self_hosted_mesh"
    assert body["claim_gate"]["pilot_package_claim_allowed"] is True
    assert body["claim_gate"]["production_readiness_claim_allowed"] is False
    assert body["claim_gate"]["customer_traffic_claim_allowed"] is False


def test_product_payment_intake_api_exposes_target_wallet_without_funds_claim() -> None:
    client = TestClient(app_desktop.app)

    response = client.get("/api/v1/product/payment-intake")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema"] == "x0tta6bl4.wallet_payment_intake.v1"
    assert body["wallet"]["address"] == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    assert body["wallet"]["address_shape_valid"] is True
    assert body["payment_reference"] == "X0T-PILOT-6017E099"
    assert [item["amount_usd"] for item in body["pricing_ladder"]] == [500, 2500, 10000]
    assert body["claim_gate"]["payment_intake_claim_allowed"] is True
    assert body["claim_gate"]["funds_received_claim_allowed"] is False
    assert body["claim_gate"]["settlement_finality_claim_allowed"] is False
