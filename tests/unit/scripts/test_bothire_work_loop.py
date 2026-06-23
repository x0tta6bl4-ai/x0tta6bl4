from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from pathlib import Path

from scripts.ops import bothire_work_loop


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/bothire_work_loop.py"


def test_bothire_work_loop_offline_fulfills_mailbox_messages(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    hires = tmp_path / "hires.json"
    inboxes = tmp_path / "inboxes.json"
    output = tmp_path / "work.json"

    identity.write_text(json.dumps({"bot_id": "bot-1", "api_key": "bh_secret"}), encoding="utf-8")
    hires.write_text(json.dumps({"hires": [{"_id": "hire-1"}]}), encoding="utf-8")
    inboxes.write_text(
        json.dumps(
            {
                "hire-1": {
                    "messages": [
                        {
                            "message_id": "msg-1",
                            "payload": {
                                "service_name": "Demo API",
                                "endpoints": [
                                    {
                                        "method": "GET",
                                        "path": "/health",
                                        "summary": "Health endpoint",
                                    }
                                ],
                            },
                        },
                        {
                            "message_id": "msg-2",
                            "payload": {
                                "repo_url": "https://example.test/repo",
                                "files": [
                                    {"path": "pyproject.toml", "text": "[project]\nname='demo'\n"}
                                ],
                            },
                        },
                        {
                            "message_id": "msg-3",
                            "payload": {
                                "profile_text": (
                                    "Direct endpoint. Send public profile text only. "
                                    "Return JSON scorecard. Price 0.05 USDC."
                                )
                            },
                        },
                        {
                            "message_id": "msg-4",
                            "payload": {
                                "pay_to": "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
                                "amount": 20000,
                                "network": "eip155:8453",
                                "asset": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
                            },
                        },
                        {
                            "message_id": "msg-5",
                            "payload": {
                                "opportunity_title": "Paid x402 API listing",
                                "description": "Public-input paid API. Per request. USDC on Base.",
                                "payout_usdc": 0.02,
                                "required_upfront_usdc": 0,
                                "estimated_token_cost": 1500,
                                "estimated_minutes": 3,
                                "payout_type": "per_request",
                                "payment_rail": "x402 USDC on Base",
                                "deliverable_type": "JSON report",
                            },
                        },
                        {
                            "message_id": "msg-6",
                            "payload": {
                                "url": "http://127.0.0.1:8120/paid/repo-triage",
                                "expected_network": "eip155:8453",
                                "max_amount_micro_usdc": 100000,
                            },
                        },
                        {
                            "message_id": "msg-7",
                            "payload": {
                                "url": "http://127.0.0.1:8120/",
                                "max_links": 5,
                                "max_text_chars": 200,
                            },
                        },
                        {
                            "message_id": "msg-8",
                            "payload": {
                                "target": "http://127.0.0.1:8120/",
                                "fetch_http": True,
                                "check_tls": True,
                            },
                        },
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--identity",
            str(identity),
            "--offline-hires",
            str(hires),
            "--offline-inboxes",
            str(inboxes),
            "--output",
            str(output),
            "--once",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["active_hires_total"] == 1
    assert payload["deliveries_total"] == 8
    messages = payload["hires"][0]["messages"]
    assert messages[0]["fulfillment_status"] == "ready"
    assert messages[1]["fulfillment_status"] == "ready"
    assert messages[2]["fulfillment_status"] == "ready"
    assert messages[3]["fulfillment_status"] == "ready"
    assert messages[4]["fulfillment_status"] == "ready"
    assert messages[5]["fulfillment_status"] == "ready"
    assert messages[6]["fulfillment_status"] == "ready"
    assert messages[7]["fulfillment_status"] == "ready"
    assert payload["funds_received_claim_allowed"] is False


def test_bothire_http_json_returns_soft_status_for_urlerror(monkeypatch) -> None:
    def fail_open(*_args, **_kwargs):
        raise urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING]")

    monkeypatch.setattr(bothire_work_loop.urllib.request, "urlopen", fail_open)

    status, payload = bothire_work_loop._http_json("GET", "/api/demo", api_key="secret")

    assert status == 0
    assert payload["error"] == "external_tls_unreachable"
    assert "received funds" in payload["claim_boundary"]
