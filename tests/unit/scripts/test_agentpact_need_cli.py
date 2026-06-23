from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import importlib.util


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentpact_need_cli.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("agentpact_need_cli_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agentpact_need_cli_offline_writes_selection(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    needs = tmp_path / "needs.json"
    output = tmp_path / "selection.json"
    identity.write_text(json.dumps({"agentId": "seller-agent", "apiKey": "secret"}), encoding="utf-8")
    status.write_text(
        json.dumps({"offer": {"response": {"id": "offer-id"}}}),
        encoding="utf-8",
    )
    needs.write_text(
        json.dumps(
            [
                {
                    "id": "need-id",
                    "agent_id": "buyer-agent",
                    "title": "Python / Data Task Execution",
                    "description_md": "Python coding, data analysis, automation, or API integration task.",
                    "category": "development",
                    "tags": ["python", "data", "automation", "coding"],
                    "budget_min": "5",
                    "budget_max": "5",
                    "currency": "USDC",
                    "acceptance_criteria": "[\"Working code or structured report delivered\"]",
                    "status": "open",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(needs),
            "--identity",
            str(identity),
            "--status",
            str(status),
            "--output",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    stdout = json.loads(result.stdout)
    assert payload["selected_need"]["need_id"] == "need-id"
    assert payload["proposal_payload"]["sellerAgentId"] == "seller-agent"
    assert stdout["submit"]["status"] == "submit_not_requested"


def test_submit_proposal_uses_agentpact_propose_endpoint(monkeypatch) -> None:
    module = _load_script_module()
    calls = []

    def fake_http_json(method, path, *, payload=None, api_key=None, timeout_seconds=30.0):
        calls.append(
            {
                "method": method,
                "path": path,
                "payload": payload,
                "api_key": api_key,
                "timeout_seconds": timeout_seconds,
            }
        )
        return 201, {"id": "deal-id"}

    monkeypatch.setattr(module, "_http_json", fake_http_json)

    result = module._submit_proposal({"apiKey": "secret"}, {"needId": "need-id"})

    assert result["status"] == "submitted"
    assert calls == [
            {
                "method": "POST",
                "path": "/api/deals/propose",
                "payload": {"needId": "need-id"},
                "api_key": "secret",
                "timeout_seconds": 30.0,
        }
    ]


def test_submit_proposal_classifies_buyer_authorization_block(monkeypatch) -> None:
    module = _load_script_module()

    def fake_http_json(method, path, *, payload=None, api_key=None, timeout_seconds=30.0):
        return 403, {"error": "Not authorized to act as this agent"}

    monkeypatch.setattr(module, "_http_json", fake_http_json)

    result = module._submit_proposal({"apiKey": "secret"}, {"needId": "need-id"})

    assert result["status"] == "submit_blocked_buyer_agent_authorization_required"
    assert result["http_status"] == 403
    assert result["next_action"] == "wait_for_buyer_proposal_or_buyer_authorized_deal_creation"
