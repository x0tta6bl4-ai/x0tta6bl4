from __future__ import annotations

import json
import urllib.error

from scripts.ops.opentask_agent_cli import (
    _load_opentask_bid_targets,
    _load_selected_opentask_targets,
    _request_json,
    _redact_status,
    bid_approach_for_task,
    bid_payload_for_task,
    capability_claims_for_task,
    missing_payout_method_payloads,
    portfolio_payloads,
)
from scripts.ops import opentask_agent_cli


def test_opentask_bid_payload_is_scoped_and_discounted() -> None:
    payload = bid_payload_for_task(
        {
            "title": "Build a simple Python script",
            "payout_usd_estimate": 100,
        }
    )

    assert payload["priceText"] == "80 USDC"
    assert payload["etaDays"] == 1
    assert "Verification:" in payload["approach"]
    assert "Portfolio evidence:" in payload["approach"]
    assert "Out of scope:" in payload["approach"]


def test_opentask_bid_approach_specializes_csv_to_json_task() -> None:
    approach = bid_approach_for_task(
        {
            "title": "Build a simple Python script to parse CSV files and generate JSON output",
            "tags": ["python", "csv", "json"],
        }
    )

    assert "CSV-to-JSON" in approach
    assert "pytest" in approach
    assert "Out of scope:" in approach


def test_opentask_bid_approach_specializes_openapi_task() -> None:
    approach = bid_approach_for_task({"title": "Create OpenAPI docs", "tags": ["openapi"]})

    assert "OpenAPI" in approach
    assert "endpoint examples" in approach
    assert "Verification:" in approach


def test_opentask_bid_approach_specializes_api_integration_task() -> None:
    approach = bid_approach_for_task({"title": "FastAPI Backend Development - REST API", "tags": ["fastapi"]})

    assert "API integration" in approach
    assert "curl smoke checks" in approach
    assert "Out of scope:" in approach


def test_opentask_bid_approach_specializes_qa_report_task() -> None:
    approach = bid_approach_for_task({"title": "Small API or Content QA Report - $5 USDC", "tags": ["qa"]})

    assert "QA report" in approach
    assert "issue severity" in approach
    assert "Verification:" in approach


def test_opentask_target_loader_deduplicates_ids_not_titles(tmp_path) -> None:
    path = tmp_path / "ranking.json"
    path.write_text(
        json.dumps(
            {
                "selected_first": [
                    {
                        "source_id": "opentask",
                        "decision": "account_gate_first",
                        "external_id": "task_1",
                        "title": "Same task",
                    },
                    {
                        "source_id": "opentask",
                        "decision": "account_gate_first",
                        "external_id": "task_2",
                        "title": "Same task",
                    },
                    {
                        "source_id": "opentask",
                        "decision": "account_gate_first",
                        "external_id": "task_2",
                        "title": "Same task duplicate id",
                    },
                    {
                        "source_id": "moltjobs",
                        "decision": "account_gate_first",
                        "external_id": "job_1",
                        "title": "Different market",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    targets = _load_selected_opentask_targets(path, limit=3)

    assert len(targets) == 2
    assert targets[0]["external_id"] == "task_1"
    assert targets[1]["external_id"] == "task_2"


def test_opentask_bid_target_loader_can_include_safe_manual_review(tmp_path) -> None:
    path = tmp_path / "ranking.json"
    path.write_text(
        json.dumps(
            {
                "ranked": [
                    {
                        "source_id": "opentask",
                        "decision": "account_gate_first",
                        "external_id": "task_1",
                        "title": "JSON parser",
                        "risk_flags": ["needs_headless_registration_and_bearer_token"],
                    },
                    {
                        "source_id": "opentask",
                        "decision": "manual_review",
                        "external_id": "task_2",
                        "title": "FastAPI Backend Development",
                        "risk_flags": ["needs_headless_registration_and_bearer_token"],
                    },
                    {
                        "source_id": "opentask",
                        "decision": "manual_review",
                        "external_id": "task_3",
                        "title": "Python anti-detection scraping",
                        "risk_flags": ["needs_headless_registration_and_bearer_token"],
                    },
                    {
                        "source_id": "opentask",
                        "decision": "manual_review",
                        "external_id": "task_4",
                        "title": "API Integration broad",
                        "risk_flags": ["broad_service_listing"],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    conservative = _load_opentask_bid_targets(path, limit=10, include_manual_review=False)
    expanded = _load_opentask_bid_targets(path, limit=10, include_manual_review=True)

    assert [item["external_id"] for item in conservative] == ["task_1"]
    assert [item["external_id"] for item in expanded] == ["task_1", "task_2"]


def test_opentask_status_redacts_secret_values() -> None:
    redacted = _redact_status(
        {
            "secret": {
                "handle": "x0t_worker",
                "password": "clear-password",
                "token": "ot_live_1234567890",
                "signing_key_hex": "abcdef",
            }
        }
    )

    assert redacted["secret"]["password"] == "***"
    assert redacted["secret"]["token"].startswith("ot_l")
    assert "1234567890" not in redacted["secret"]["token"]
    assert redacted["secret"]["signing_key_hex"] == "***"


def test_opentask_request_json_returns_soft_status_for_urlerror(monkeypatch) -> None:
    def fail_open(*_args, **_kwargs):
        raise urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING]")

    monkeypatch.setattr(opentask_agent_cli.urllib.request, "urlopen", fail_open)

    status, payload = _request_json("GET", "/api/agent/me", token="secret")

    assert status == 0
    assert payload["error"] == "external_tls_unreachable"
    assert "received funds" in payload["claim_boundary"]


def test_missing_payout_method_payloads_avoid_duplicates() -> None:
    evm_only = {
        "methods": [
            {
                "symbol": "USDC",
                "network": "EVM",
                "address": "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
            }
        ]
    }
    base_missing = missing_payout_method_payloads(evm_only)

    assert [item["network"] for item in base_missing] == ["BASE"]

    both = {
        "methods": [
            {
                "symbol": "USDC",
                "network": "EVM",
                "address": "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
            },
            {
                "symbol": "USDC",
                "network": "BASE",
                "address": "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
            },
        ]
    }

    assert missing_payout_method_payloads(both) == []


def test_opentask_portfolio_payloads_attach_capability_ids() -> None:
    payloads = portfolio_payloads(
        "https://public.example",
        {
            "capabilities": [
                {"id": "cap_python", "name": "Python data parser microtask"},
                {"id": "cap_docs", "name": "OpenAPI and API docs repair"},
            ]
        },
    )

    assert len(payloads) == 3
    assert payloads[0]["capabilityId"] == "cap_python"
    assert payloads[0]["url"] == "https://public.example/agentbazaar/task"
    assert payloads[1]["capabilityId"] == "cap_python"
    assert payloads[1]["url"] == (
        "https://public.example/workprotocol/deliverables/"
        "f82a9ca9-github-actions-log-parser/delivery.json"
    )
    assert payloads[2]["capabilityId"] == "cap_docs"
    assert payloads[2]["url"] == "https://public.example/.well-known/x402-discovery"


def test_opentask_capability_claims_match_task_type() -> None:
    caps = {
        "capabilities": [
            {"id": "cap_python", "name": "Python data parser microtask"},
            {"id": "cap_docs", "name": "OpenAPI and API docs repair"},
            {"id": "cap_api", "name": "Small FastAPI and API integration task"},
            {"id": "cap_qa", "name": "Small API and content QA report"},
        ]
    }

    python_claims = capability_claims_for_task({"title": "Write Python JSON to CSV parser"}, caps)
    docs_claims = capability_claims_for_task({"title": "Create OpenAPI docs"}, caps)
    api_claims = capability_claims_for_task({"title": "FastAPI backend webhook integration"}, caps)
    qa_claims = capability_claims_for_task({"title": "Small API or Content QA Report"}, caps)

    assert python_claims[0]["capabilityId"] == "cap_python"
    assert docs_claims[0]["capabilityId"] == "cap_docs"
    assert api_claims[0]["capabilityId"] == "cap_api"
    assert qa_claims[0]["capabilityId"] == "cap_qa"
