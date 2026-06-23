from __future__ import annotations

import base64
import json

from fastapi.testclient import TestClient

from src.sales.x402_paid_api import (
    DEFAULT_FACILITATOR_URL,
    DEFAULT_RECEIVER_WALLET,
    AgentWorldMessageRequest,
    AgentBazaarTaskRequest,
    ApiDocsRequest,
    DomainHealthRequest,
    IncomeRouteRequest,
    ListingAuditRequest,
    PaidApiSettings,
    PaymentRiskRequest,
    PreviewRouteRequest,
    RepoTriageRequest,
    UrlSnapshotRequest,
    X402ValidateRequest,
    build_agentworld_reply,
    build_agentbazaar_task_result,
    build_agent_card,
    build_machina_agent_manifest,
    build_machina_agent_manifests,
    build_api_docs_package,
    build_domain_health_report,
    build_discovery_payload,
    enrich_payment_required_payload,
    build_income_route_report,
    build_listing_audit_report,
    build_payment_risk_report,
    build_preview_route,
    build_repo_triage_report,
    build_url_snapshot_report,
    build_x402_validate_report,
    create_app,
    decode_payment_required_header,
)


def test_x402_paid_api_catalog_exposes_price_and_wallet() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False))
    client = TestClient(app)

    response = client.get("/x402/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pay_to"] == DEFAULT_RECEIVER_WALLET
    assert payload["routes"]["GET /paid/repo-triage"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["POST /paid/repo-triage"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["GET /paid/api-docs"]["accepts"]["price"] == "$0.03"
    assert payload["routes"]["POST /paid/api-docs"]["accepts"]["price"] == "$0.03"
    assert payload["routes"]["GET /paid/listing-audit"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["POST /paid/listing-audit"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["GET /paid/payment-risk"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["POST /paid/payment-risk"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["GET /paid/income-route"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["POST /paid/income-route"]["accepts"]["price"] == "$0.02"
    assert payload["routes"]["GET /paid/x402-validate"]["accepts"]["price"] == "$0.01"
    assert payload["routes"]["POST /paid/x402-validate"]["accepts"]["price"] == "$0.01"
    assert payload["routes"]["GET /paid/url-snapshot"]["accepts"]["price"] == "$0.01"
    assert payload["routes"]["POST /paid/url-snapshot"]["accepts"]["price"] == "$0.01"
    assert payload["routes"]["GET /paid/domain-health"]["accepts"]["price"] == "$0.001"
    assert payload["routes"]["POST /paid/domain-health"]["accepts"]["price"] == "$0.001"
    assert payload["paid_api_available"] is False


def test_workprotocol_deliverable_file_route_serves_only_artifact_dir(tmp_path, monkeypatch) -> None:
    artifact_dir = tmp_path / "deliverables"
    artifact_dir.mkdir()
    artifact = artifact_dir / "job" / "README.md"
    artifact.parent.mkdir()
    artifact.write_text("deliverable", encoding="utf-8")
    secret = tmp_path / "secret.txt"
    secret.write_text("secret", encoding="utf-8")
    monkeypatch.setattr("src.sales.x402_paid_api.WORKPROTOCOL_DELIVERABLE_DIR", artifact_dir)
    app = create_app(PaidApiSettings(x402_enabled=False))
    client = TestClient(app)

    ok = client.get("/workprotocol/deliverables/job/README.md")
    blocked = client.get("/workprotocol/deliverables/../secret.txt")

    assert ok.status_code == 200
    assert ok.text == "deliverable"
    assert blocked.status_code == 404


def test_paid_endpoint_fails_closed_when_x402_is_not_active() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, allow_unpaid_dev=False))
    client = TestClient(app)

    response = client.post(
        "/paid/repo-triage",
        json={"repo_url": "https://example.invalid/repo", "files": []},
    )

    assert response.status_code == 503
    assert "paid endpoint unavailable" in response.json()["detail"]["error"]


def test_api_docs_endpoint_fails_closed_when_x402_is_not_active() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, allow_unpaid_dev=False))
    client = TestClient(app)

    response = client.post(
        "/paid/api-docs",
        json={
            "service_name": "Demo API",
            "endpoints": [{"method": "GET", "path": "/health", "summary": "Health"}],
        },
    )

    assert response.status_code == 503
    assert "paid endpoint unavailable" in response.json()["detail"]["error"]


def test_agent402_endpoints_bypass_second_x402_paywall_for_forwarded_calls() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, allow_unpaid_dev=False))
    client = TestClient(app)

    catalog = client.get("/agent402/services")
    response = client.post(
        "/agent402/api-docs",
        json={
            "payload": {
                "service_name": "Demo API",
                "endpoints": [{"method": "GET", "path": "/health", "summary": "Health"}],
            }
        },
    )

    assert catalog.status_code == 200
    assert catalog.json()["services"][1]["endpoint"].endswith("/agent402/api-docs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["platform"] == "agent402"
    assert payload["tool"] == "api-docs"
    assert payload["package"]["service_name"] == "Demo API"


def test_repo_triage_report_detects_basic_project_signals() -> None:
    report = build_repo_triage_report(
        RepoTriageRequest(
            repo_url="https://example.invalid/repo",
            files=[
                {"path": "pyproject.toml", "text": "[project]\nname='demo'\n"},
                {"path": "tests/test_app.py", "text": "def test_ok(): assert True\n"},
                {"path": ".github/workflows/test.yml", "text": "name: test\n"},
            ],
            focus=["tests"],
        )
    )

    assert report["signals"]["has_python_project"] is True
    assert report["signals"]["has_tests"] is True
    assert report["signals"]["has_ci"] is True
    assert report["readiness_score"] == 100
    assert report["suggested_next_steps"][0] == "Prioritize requested focus: tests."


def test_build_api_docs_package_returns_markdown_examples() -> None:
    package = build_api_docs_package(
        ApiDocsRequest(
            service_name="Demo API",
            base_url="https://api.example.test",
            auth_guide="Use bearer tokens.",
            endpoints=[
                {
                    "method": "post",
                    "path": "/items",
                    "summary": "Create an item.",
                    "auth": "Bearer token",
                    "request_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "count": {"type": "integer"},
                        },
                    },
                    "response_schema": {
                        "type": "object",
                        "properties": {"id": {"type": "string"}},
                    },
                    "errors": ["400 invalid input"],
                }
            ],
        )
    )

    assert package["schema"] == "x0tta6bl4.paid_api_docs_package.v1"
    assert package["endpoints_total"] == 1
    assert "### POST `/items`" in package["markdown"]
    assert "curl -X POST" in package["markdown"]
    assert "requests.request('POST'" in package["markdown"]


def test_build_listing_audit_report_scores_agent_listing() -> None:
    report = build_listing_audit_report(
        ListingAuditRequest(
            listing_url="https://example.test/agent",
            profile_text=(
                "Direct endpoint delivery. Send public payload snippets only, no secrets. "
                "Return JSON scorecard immediately. Price: 0.05 USDC. Example output included."
            ),
            target_buyer="AI agents buying small developer tools",
            price_usdc=0.05,
        )
    )

    assert report["schema"] == "x0tta6bl4.bothire_listing_audit_report.v1"
    assert report["score"] >= 90
    assert report["signals"]["has_clear_price"] is True
    assert "0.05 USDC" in report["improved_cta"]


def test_build_payment_risk_report_scores_valid_small_payment() -> None:
    report = build_payment_risk_report(
        PaymentRiskRequest(
            resource_url="https://example.test/paid/tool",
            pay_to=DEFAULT_RECEIVER_WALLET,
            amount=20_000,
            network="eip155:8453",
            asset="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            service_name="Small paid tool",
        )
    )

    assert report["schema"] == "x0tta6bl4.paid_payment_risk_report.v1"
    assert report["verdict"] == "low_risk"
    assert report["signals"]["pay_to_shape_ok"] is True


def test_build_income_route_report_takes_recurring_public_paid_api() -> None:
    report = build_income_route_report(
        IncomeRouteRequest(
            opportunity_title="Paid x402 API listing",
            description="Public-input paid API. Per request. USDC on Base. JSON report output.",
            payout_usdc=0.02,
            required_upfront_usdc=0,
            estimated_token_cost=1500,
            estimated_minutes=3,
            payout_type="per_request",
            payment_rail="x402 USDC on Base",
            deliverable_type="JSON report",
            tags=["x402", "paid-api", "automation"],
        )
    )

    assert report["schema"] == "x0tta6bl4.paid_income_route_report.v1"
    assert report["verdict"] == "take_first"
    assert report["signals"]["recurring_income_fit"] is True
    assert report["token_to_money_ratio_usdc_per_1k_tokens"] > 0


def test_build_x402_validate_report_rejects_localhost_target() -> None:
    report = build_x402_validate_report(
        X402ValidateRequest(url="http://127.0.0.1:8120/paid/repo-triage")
    )

    assert report["schema"] == "x0tta6bl4.paid_x402_validate_report.v1"
    assert report["verdict"] == "reject"
    assert report["signals"]["public_url"] is False


def test_build_url_snapshot_report_rejects_localhost_target() -> None:
    report = build_url_snapshot_report(
        UrlSnapshotRequest(url="http://127.0.0.1:8120/")
    )

    assert report["schema"] == "x0tta6bl4.paid_url_snapshot_report.v1"
    assert report["verdict"] == "reject"
    assert report["signals"]["public_url"] is False


def test_build_domain_health_report_rejects_localhost_target() -> None:
    report = build_domain_health_report(
        DomainHealthRequest(target="http://127.0.0.1:8120/")
    )

    assert report["schema"] == "x0tta6bl4.paid_domain_health_report.v1"
    assert report["verdict"] == "reject"
    assert report["signals"]["public_dns"] is False


def test_agentworld_reply_routes_to_paid_endpoint() -> None:
    reply = build_agentworld_reply(
        AgentWorldMessageRequest(message="Need API docs for an endpoint."),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert reply["schema"] == "x0tta6bl4.agentworld_reply.v1"
    assert reply["intent"] == "api_docs"
    assert reply["paid_endpoints"]["api_docs"] == "https://example.test/paid/api-docs"
    assert reply["payment"]["wallet"] == DEFAULT_RECEIVER_WALLET


def test_agent_card_advertises_wallet_and_paid_skills() -> None:
    card = build_agent_card("https://example.test", PaidApiSettings(x402_enabled=False))

    assert card["schema"] == "x0tta6bl4.agent_card.v1"
    assert card["wallet"] == DEFAULT_RECEIVER_WALLET
    assert len(card["skills"]) == 8
    assert card["endpoints"]["x402_discovery"] == "https://example.test/.well-known/x402-discovery"
    assert card["endpoints"]["x402_json"] == "https://example.test/.well-known/x402.json"
    assert card["endpoints"]["agentbazaar_task"] == "https://example.test/agentbazaar/task"
    assert card["endpoints"]["clustly_webhook"] == "https://example.test/clustly/webhook"
    assert card["endpoints"]["agoragentic_webhook"] == "https://example.test/agoragentic/webhook"
    assert card["endpoints"]["agentpact_webhook"] == "https://example.test/agentpact/webhook"
    assert card["endpoints"]["free_preview"] == "https://example.test/preview/route"


def test_build_machina_agent_manifest_advertises_domain_health_payment() -> None:
    manifest = build_machina_agent_manifest("https://example.test", PaidApiSettings(x402_enabled=False))

    assert manifest["name"] == "x0tta6bl4 Domain Health Lite"
    assert manifest["endpoint"] == "https://example.test/paid/domain-health"
    assert manifest["pricing"]["amount"] == 0.001
    assert manifest["pricing"]["currency"] == "USDC"
    assert manifest["payment"]["receive_address"] == DEFAULT_RECEIVER_WALLET
    assert "POST /paid/domain-health" in manifest["routes"]


def test_build_machina_agent_manifests_covers_all_paid_services() -> None:
    manifests = build_machina_agent_manifests("https://example.test", PaidApiSettings(x402_enabled=False))

    assert len(manifests) == 8
    assert {manifest["payment"]["receive_address"] for manifest in manifests} == {DEFAULT_RECEIVER_WALLET}
    assert {manifest["pricing"]["currency"] for manifest in manifests} == {"USDC"}
    assert "https://example.test/paid/api-docs" in {manifest["endpoint"] for manifest in manifests}


def test_discovery_payload_exposes_base_network_aliases_for_directories() -> None:
    payload = build_discovery_payload("https://example.test", PaidApiSettings(x402_enabled=False))

    assert payload["chain"] == "Base"
    assert payload["chain_id"] == 8453
    assert "base-mainnet" in payload["network_aliases"]
    assert "eip155:8453" in payload["network_aliases"]
    assert payload["asset_symbol"] == "USDC"
    assert payload["pay_to"] == DEFAULT_RECEIVER_WALLET
    first_service = payload["services"][0]
    assert first_service["asset_symbol"] == "USDC"
    assert first_service["price_micro_usdc"] == 20_000
    assert "base-mainnet" in first_service["network_aliases"]


def test_decode_payment_required_header_returns_json_payload() -> None:
    raw = {"x402Version": 2, "accepts": [{"payTo": DEFAULT_RECEIVER_WALLET}]}
    encoded = base64.urlsafe_b64encode(json.dumps(raw).encode()).decode().rstrip("=")

    assert decode_payment_required_header(encoded) == raw


def test_preview_route_maps_request_to_paid_tool() -> None:
    route = build_preview_route(
        PreviewRouteRequest(message="Need repo tests and CI triage", public_url="https://example.test/repo"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert route["schema"] == "x0tta6bl4.free_preview_route.v1"
    assert route["intent"] == "repo_triage"
    assert route["paid_endpoint"] == "https://example.test/paid/repo-triage"
    assert route["wallet"] == DEFAULT_RECEIVER_WALLET


def test_preview_route_maps_payment_request_to_risk_tool() -> None:
    route = build_preview_route(
        PreviewRouteRequest(message="Check x402 payment risk before wallet spend", public_url="https://example.test/pay"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert route["intent"] == "payment_risk"
    assert route["paid_endpoint"] == "https://example.test/paid/payment-risk"


def test_preview_route_maps_income_request_to_income_route_tool() -> None:
    route = build_preview_route(
        PreviewRouteRequest(message="Score this income opportunity for agent earning"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert route["intent"] == "income_route"
    assert route["paid_endpoint"] == "https://example.test/paid/income-route"


def test_preview_route_maps_x402_validation_request_to_validator_tool() -> None:
    route = build_preview_route(
        PreviewRouteRequest(message="validate x402 endpoint before payment", public_url="https://example.test/paid"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert route["intent"] == "x402_validate"
    assert route["paid_endpoint"] == "https://example.test/paid/x402-validate"


def test_preview_route_maps_url_snapshot_request_to_snapshot_tool() -> None:
    route = build_preview_route(
        PreviewRouteRequest(message="Need url snapshot with page title and links", public_url="https://example.test"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert route["intent"] == "url_snapshot"
    assert route["paid_endpoint"] == "https://example.test/paid/url-snapshot"


def test_preview_route_maps_domain_health_request_to_domain_tool() -> None:
    route = build_preview_route(
        PreviewRouteRequest(message="Need DNS TLS domain health", public_url="https://example.test"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert route["intent"] == "domain_health"
    assert route["paid_endpoint"] == "https://example.test/paid/domain-health"


def test_discovery_payload_lists_paid_services_and_receiver() -> None:
    payload = build_discovery_payload(
        "https://example.test",
        PaidApiSettings(x402_enabled=False),
    )

    assert payload["name"] == "x0tta6bl4 paid x402 tools"
    assert payload["network"] == "base"
    assert payload["currency"] == "USDC"
    assert payload["resources"][0]["url"] == payload["services"][0]["url"]
    assert payload["resources"][0]["x402"]["payTo"] == DEFAULT_RECEIVER_WALLET
    assert payload["instructions"]
    assert payload["total_services"] == 8
    assert {item["id"] for item in payload["services"]} == {
        "x0tta6bl4-repo-triage",
        "x0tta6bl4-api-docs",
        "x0tta6bl4-listing-audit",
        "x0tta6bl4-payment-risk",
        "x0tta6bl4-income-route",
        "x0tta6bl4-x402-validator",
        "x0tta6bl4-url-snapshot",
        "x0tta6bl4-domain-health",
    }
    for item in payload["items"]:
        accept = item["accepts"][0]
        assert accept["payTo"] == DEFAULT_RECEIVER_WALLET
        assert accept["network"] == "eip155:8453"
        assert accept["maxAmountRequired"]
        assert accept["resource"].startswith("/paid/")
        assert accept["mimeType"] == "application/json"
        assert accept["facilitator"] == DEFAULT_FACILITATOR_URL
    assert payload["generated_at"].endswith("Z")
    assert payload["updated_at"].endswith("Z")
    for service in payload["services"]:
        assert service["endpoint"] == service["url"]
        assert service["method"] == "POST"
        assert service["resource"].startswith("/paid/")
        assert service["mimeType"] == "application/json"
        assert isinstance(service["price_atomic"], int)
        assert service["price_usdc"]
        assert service["accepts"][0]["maxAmountRequired"]
        assert service["accepts"][0]["facilitator"] == DEFAULT_FACILITATOR_URL
        endpoint = service["endpoints"][0]
        assert endpoint["method"] == "POST"
        assert endpoint["pricing"]["currency"] == "USDC"
        assert endpoint["pricing"]["network"] == "eip155:8453"


def test_payment_required_payload_is_enriched_for_ontario_metadata() -> None:
    payload = {
        "x402Version": 2,
        "resource": {
            "url": "/paid/api-docs",
            "description": "API docs generator",
            "mimeType": "application/json",
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                "amount": "30000",
                "payTo": DEFAULT_RECEIVER_WALLET,
            }
        ],
    }

    enriched = enrich_payment_required_payload(payload, settings=PaidApiSettings(x402_enabled=False))
    accept = enriched["accepts"][0]

    assert accept["maxAmountRequired"] == "30000"
    assert accept["resource"] == "/paid/api-docs"
    assert accept["description"] == "API docs generator"
    assert accept["mimeType"] == "application/json"
    assert accept["facilitator"] == DEFAULT_FACILITATOR_URL
    assert enriched["facilitator"] == DEFAULT_FACILITATOR_URL


def test_metadata_endpoints_are_public() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, allow_unpaid_dev=False))
    client = TestClient(app)

    homepage = client.get("/")
    robots = client.get("/robots.txt")
    sitemap = client.get("/sitemap.xml")
    discovery = client.get("/.well-known/x402-discovery")
    x402_json = client.get("/.well-known/x402.json")
    x402_well_known = client.get("/.well-known/x402")
    x402_manifest = client.get("/.well-known/x402/manifest.json")
    well_known_openapi = client.get("/.well-known/openapi.json")
    agent_card = client.get("/.well-known/agent.json")
    agent_card_alias = client.get("/.well-known/agent-card.json")
    agent_descriptions = client.get("/.well-known/agent-descriptions")
    agent_pulse = client.get("/.well-known/agent-pulse")
    mcp_server = client.get("/.well-known/mcp/server.json")
    jwks = client.get("/.well-known/jwks.json")
    oracle_net = client.get("/.well-known/oracle-net.json")
    machina_manifest = client.get("/.well-known/machina-agent.json")
    machina_api_docs_manifest = client.get("/.well-known/machina/x0tta6bl4-api-docs.json")
    manifest = client.get("/mcp-manifest")
    llms = client.get("/llms.txt")
    preview_catalog = client.get("/preview/catalog")

    assert homepage.status_code == 200
    assert "application/ld+json" in homepage.text
    assert "x402 manifest" in homepage.text
    assert "/.well-known/openapi.json" in homepage.text
    assert "/.well-known/agent-card.json" in homepage.text
    assert "/.well-known/agent-descriptions" in homepage.text
    assert "/.well-known/agent-pulse" in homepage.text
    assert "/.well-known/mcp/server.json" in homepage.text
    assert "/.well-known/machina-agent.json" in homepage.text
    assert "/.well-known/oracle-net.json" in homepage.text
    assert "/mcp-manifest" in homepage.text
    assert "/agent402/services" in homepage.text
    assert robots.status_code == 200
    assert "Allow: /" in robots.text
    assert sitemap.status_code == 200
    assert "/.well-known/x402.json" in sitemap.text
    assert "/.well-known/openapi.json" in sitemap.text
    assert "/.well-known/agent-card.json" in sitemap.text
    assert "/.well-known/agent-descriptions" in sitemap.text
    assert "/.well-known/agent-pulse" in sitemap.text
    assert "/.well-known/mcp/server.json" in sitemap.text
    assert "/.well-known/jwks.json" in sitemap.text
    assert "/.well-known/machina-agent.json" in sitemap.text
    assert "/.well-known/oracle-net.json" in sitemap.text
    assert "/.well-known/machina/x0tta6bl4-api-docs.json" in sitemap.text
    assert "/mcp-manifest" in sitemap.text
    assert "/llms.txt" in sitemap.text
    assert "/agent402/services" in sitemap.text
    assert discovery.status_code == 200
    assert discovery.json()["total_services"] == 8
    assert x402_json.status_code == 200
    assert x402_json.json()["total_services"] == 8
    assert x402_well_known.status_code == 200
    assert x402_well_known.json()["resources"]
    assert x402_manifest.status_code == 200
    assert x402_manifest.json()["name"] == "x0tta6bl4 paid x402 tools"
    assert well_known_openapi.status_code == 200
    assert well_known_openapi.json()["openapi"].startswith("3.")
    assert "/paid/api-docs" in well_known_openapi.json()["paths"]
    assert agent_card.status_code == 200
    assert agent_card.json()["wallet"] == DEFAULT_RECEIVER_WALLET
    assert agent_card.json()["endpoints"]["mcp_server_json"].endswith(
        "/.well-known/mcp/server.json"
    )
    assert agent_card_alias.status_code == 200
    assert agent_card_alias.json()["wallet"] == DEFAULT_RECEIVER_WALLET
    assert agent_descriptions.status_code == 200
    assert agent_descriptions.json()["payTo"] == DEFAULT_RECEIVER_WALLET
    assert len(agent_descriptions.json()["offers"]) == 8
    assert agent_pulse.status_code == 200
    assert agent_pulse.json()["payment"]["payTo"] == DEFAULT_RECEIVER_WALLET
    assert agent_pulse.json()["service_count"] == 8
    assert mcp_server.status_code == 200
    assert len(mcp_server.json()["tools"]) == 8
    assert jwks.status_code == 200
    assert jwks.json()["keys"] == []
    assert oracle_net.status_code == 200
    assert oracle_net.json()["payTo"] == DEFAULT_RECEIVER_WALLET
    assert oracle_net.json()["mcp_server"].endswith("/.well-known/mcp/server.json")
    assert machina_manifest.status_code == 200
    assert machina_manifest.json()["payment"]["receive_address"] == DEFAULT_RECEIVER_WALLET
    assert machina_api_docs_manifest.status_code == 200
    assert machina_api_docs_manifest.json()["endpoint"].endswith("/paid/api-docs")
    assert manifest.status_code == 200
    assert len(manifest.json()["tools"]) == 8
    assert llms.status_code == 200
    assert DEFAULT_RECEIVER_WALLET in llms.text
    assert preview_catalog.status_code == 200
    assert preview_catalog.json()["endpoint"].endswith("/preview/route")


def test_paid_endpoint_head_checks_are_public_and_non_executing() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, allow_unpaid_dev=False))
    client = TestClient(app)

    response = client.head("/paid/api-docs")

    assert response.status_code == 204
    assert response.text == ""
    assert response.headers["X-Paid-API"] == "x402"
    assert response.headers["X-Paid-API-Service"] == "x0tta6bl4-api-docs"
    assert response.headers["X-Paid-API-Price-USDC"] == "0.03"
    assert response.headers["X-Paid-API-Pay-To"] == DEFAULT_RECEIVER_WALLET

    unknown = client.head("/paid/not-a-service")

    assert unknown.status_code == 404


def test_bothire_direct_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/api-docs",
        json={
            "service_name": "Demo API",
            "endpoints": [{"method": "GET", "path": "/health"}],
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_listing_audit_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/listing-audit",
        json={"profile_text": "Agent service card without paid access token."},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_payment_risk_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/payment-risk",
        json={"pay_to": DEFAULT_RECEIVER_WALLET, "amount": 20_000},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_income_route_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/income-route",
        json={"opportunity_title": "Paid API", "description": "Public paid API opportunity."},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_x402_validate_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/x402-validate",
        json={"url": "https://example.test/paid/tool"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_url_snapshot_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/url-snapshot",
        json={"url": "https://example.test/"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_domain_health_endpoint_rejects_missing_access_token() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=True))
    client = TestClient(app)

    response = client.post(
        "/bothire/domain-health",
        json={"target": "https://example.test/"},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["claim_gate"]["funds_received_claim_allowed"] is False


def test_bothire_direct_endpoint_generates_docs_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/api-docs",
        json={
            "service_name": "Demo API",
            "endpoints": [{"method": "GET", "path": "/health"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_api_docs_delivery.v1"
    assert payload["package"]["endpoints_total"] == 1
    assert payload["access"]["valid"] is True


def test_bothire_listing_audit_endpoint_generates_report_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/listing-audit",
        json={
            "access_token": "hire_tok_test",
            "payload": {
                "profile_text": (
                    "Send public profile text. I return a JSON report. "
                    "Direct delivery, 0.05 USDC, no secrets."
                ),
                "price_usdc": 0.05,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_listing_audit_delivery.v1"
    assert payload["report"]["signals"]["has_clear_price"] is True


def test_bothire_payment_risk_endpoint_generates_report_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/payment-risk",
        json={
            "access_token": "hire_tok_test",
            "payload": {
                "resource_url": "https://example.test/paid/tool",
                "pay_to": DEFAULT_RECEIVER_WALLET,
                "amount": 20_000,
                "network": "eip155:8453",
                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_payment_risk_delivery.v1"
    assert payload["report"]["verdict"] == "low_risk"


def test_bothire_income_route_endpoint_generates_report_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/income-route",
        json={
            "access_token": "hire_tok_test",
            "payload": {
                "opportunity_title": "Paid x402 API listing",
                "description": "Public-input paid API. Per request. USDC on Base. JSON report output.",
                "payout_usdc": 0.02,
                "required_upfront_usdc": 0,
                "estimated_token_cost": 1500,
                "estimated_minutes": 3,
                "payout_type": "per_request",
                "payment_rail": "x402 USDC on Base",
                "deliverable_type": "JSON report",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_income_route_delivery.v1"
    assert payload["report"]["verdict"] == "take_first"


def test_bothire_x402_validate_endpoint_generates_report_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/x402-validate",
        json={
            "access_token": "hire_tok_test",
            "payload": {"url": "http://127.0.0.1:8120/paid/repo-triage"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_x402_validate_delivery.v1"
    assert payload["report"]["verdict"] == "reject"


def test_bothire_url_snapshot_endpoint_generates_report_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/url-snapshot",
        json={
            "access_token": "hire_tok_test",
            "payload": {"url": "http://127.0.0.1:8120/", "max_links": 5},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_url_snapshot_delivery.v1"
    assert payload["report"]["schema"] == "x0tta6bl4.paid_url_snapshot_report.v1"
    assert payload["report"]["verdict"] == "reject"


def test_bothire_domain_health_endpoint_generates_report_when_access_verified_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/domain-health",
        json={
            "access_token": "hire_tok_test",
            "payload": {"target": "http://127.0.0.1:8120/", "fetch_http": True},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_domain_health_delivery.v1"
    assert payload["report"]["schema"] == "x0tta6bl4.paid_domain_health_report.v1"
    assert payload["report"]["verdict"] == "reject"


def test_bothire_direct_endpoint_accepts_payload_envelope_in_dev() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/bothire/repo-triage",
        json={
            "access_token": "hire_tok_test",
            "payload": {
                "repo_url": "https://example.test/repo",
                "files": [{"path": "pyproject.toml", "text": "[project]\nname='demo'\n"}],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "x0tta6bl4.bothire_repo_triage_delivery.v1"
    assert payload["report"]["files_seen"] == 1


def test_bothire_health_lists_direct_endpoints() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.get("/bothire/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["claim_gate"]["funds_received_claim_allowed"] is False
    assert {item["name"] for item in payload["tools"]} == {
        "api-docs",
        "repo-triage",
        "listing-audit",
        "payment-risk",
        "income-route",
        "x402-validate",
        "url-snapshot",
        "domain-health",
    }


def test_agentworld_message_endpoint_is_lightweight_catalog_router() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/agentworld/message",
        json={"message": "Can you triage a repo?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["intent"] == "repo_triage"
    assert payload["paid_endpoints"]["repo_triage"].endswith("/paid/repo-triage")
    assert payload["claim_boundary"]


def test_agentbazaar_task_endpoint_returns_result_body() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/agentbazaar/task",
        json={"task": "Run domain health for http://127.0.0.1:8120/", "buyer": "buyer-1", "jobId": 7},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "result" in payload
    assert payload["structured"]["schema"] == "x0tta6bl4.agentbazaar_task_result.v1"
    assert payload["structured"]["tool"] == "domain-health"
    assert payload["structured"]["report"]["verdict"] == "reject"


def test_agentbazaar_task_endpoint_advertises_public_probe_methods() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    info = client.get("/agentbazaar/task")
    head = client.head("/agentbazaar/task")

    assert info.status_code == 200
    assert info.json()["method"] == "POST"
    assert info.json()["endpoint"].endswith("/agentbazaar/task")
    assert info.json()["input_schema"]["title"] == "AgentBazaarTaskRequest"
    assert head.status_code == 204
    assert head.text == ""
    assert head.headers["X-Agent-Endpoint"] == "agentbazaar-task"


def test_agentbazaar_task_builder_rejects_secret_like_task() -> None:
    result = build_agentbazaar_task_result(
        AgentBazaarTaskRequest(task="Use this private_key=abc123"),
        base_url="https://example.test",
        settings=PaidApiSettings(x402_enabled=False),
    )

    assert result["structured"]["verdict"] == "reject"
    assert result["structured"]["reason"] == "unsafe_or_secret_like_task"


def test_payanagent_webhook_accepts_and_records_event() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/payanagent/webhook",
        json={"event": "request.created", "request_id": "req-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["source"] == "payanagent"
    assert payload["claim_boundary"]


def test_clustly_webhook_accepts_and_records_event() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/clustly/webhook",
        json={"event": "task.created", "data": {"id": "task-1"}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["source"] == "clustly"
    assert payload["claim_boundary"]


def test_agoragentic_webhook_accepts_and_records_event() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/agoragentic/webhook",
        json={"event": "listing.approved", "listing_id": "listing-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["source"] == "agoragentic"
    assert payload["claim_boundary"]


def test_agentpact_webhook_accepts_and_records_event() -> None:
    app = create_app(PaidApiSettings(x402_enabled=False, bothire_verify_access=False))
    client = TestClient(app)

    response = client.post(
        "/agentpact/webhook",
        json={"event": "match.created", "need_id": "need-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["source"] == "agentpact"
    assert payload["claim_boundary"]
