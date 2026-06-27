from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentpact_subscribe_alerts.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("agentpact_subscribe_alerts_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_subscribe_alerts_posts_need_filters_and_redacts_response(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret-api-key"}), encoding="utf-8")
    calls = []

    def fake_http_json(method, path, *, payload, api_key, timeout_seconds=30.0):
        calls.append(
            {
                "method": method,
                "path": path,
                "payload": payload,
                "api_key": api_key,
                "timeout_seconds": timeout_seconds,
            }
        )
        return 201, {"id": "sub-1", "apiKey": "must-not-leak"}

    monkeypatch.setattr(module, "_http_json", fake_http_json)

    result = module.subscribe_alerts(
        identity_path=identity,
        public_base_url="https://example.test",
        status_path=status,
    )

    assert result["status"] == "subscribed"
    assert result["webhook_url"] == "https://example.test/agentpact/webhook"
    assert len(calls) == 3
    assert {call["payload"]["kind"] for call in calls} == {"needs"}
    assert {call["payload"]["webhookUrl"] for call in calls} == {"https://example.test/agentpact/webhook"}
    assert all(call["api_key"] == "secret-api-key" for call in calls)
    assert result["subscriptions"][0]["response"]["apiKey"] == "***"


def test_agentpact_subscribe_alerts_cli_writes_skip_without_api_key(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    identity.write_text(json.dumps({"agentId": "agent-1"}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--identity",
            str(identity),
            "--status",
            str(status),
            "--public-base-url",
            "https://example.test",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["status"] == "skipped"
    assert payload["reason"] == "missing_api_key"
    assert payload["webhook_url"] == "https://example.test/agentpact/webhook"
    assert payload["funds_received_claim_allowed"] is False


def test_subscribe_alerts_preserves_previous_success_without_reposting(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret-api-key"}), encoding="utf-8")
    status.write_text(
        json.dumps(
            {
                "agentId": "agent-1",
                "webhook_url": "https://example.test/agentpact/webhook",
                "subscriptions": [
                    {
                        "name": "python_data_microtasks",
                        "status": "subscribed",
                        "http_status": 201,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def fail_http_json(*_args, **_kwargs):
        raise AssertionError("should not repost existing successful subscriptions")

    monkeypatch.setattr(module, "_http_json", fail_http_json)

    result = module.subscribe_alerts(
        identity_path=identity,
        public_base_url="https://example.test",
        status_path=status,
    )

    assert result["status"] == "already_subscribed"
    assert result["subscriptions"] == [
        {
            "name": "python_data_microtasks",
            "status": "subscribed",
            "http_status": 201,
        }
    ]
