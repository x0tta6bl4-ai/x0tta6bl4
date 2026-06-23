from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentpact_register_webhook.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("agentpact_register_webhook_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_register_webhook_posts_events_and_redacts_secret(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    secret = tmp_path / "webhook.secret.json"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret-api-key"}), encoding="utf-8")
    calls = []

    def fake_http_json(method, path, *, api_key, payload=None, timeout_seconds=30.0):
        calls.append(
            {
                "method": method,
                "path": path,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if method == "GET":
            return 200, []
        return 201, {
            "id": "webhook-1",
            "agent_id": "agent-1",
            "url": "https://example.test/agentpact/webhook",
            "events": list(module.EVENTS),
            "secret": "must-not-leak",
            "active": True,
        }

    monkeypatch.setattr(module, "_http_json", fake_http_json)

    result = module.register_webhook(
        identity_path=identity,
        public_base_url="https://example.test",
        status_path=status,
        secret_path=secret,
    )

    assert result["status"] == "registered"
    assert result["webhook_id"] == "webhook-1"
    assert result["response"]["secret"] == "***"
    assert json.loads(secret.read_text(encoding="utf-8"))["secret"] == "must-not-leak"
    assert calls[0]["method"] == "GET"
    assert calls[1]["method"] == "POST"
    assert calls[1]["payload"]["events"] == list(module.EVENTS)
    assert calls[1]["api_key"] == "secret-api-key"


def test_register_webhook_reuses_existing_matching_webhook(tmp_path: Path, monkeypatch) -> None:
    module = _load_script_module()
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    secret = tmp_path / "webhook.secret.json"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret-api-key"}), encoding="utf-8")

    def fake_http_json(method, path, *, api_key, payload=None, timeout_seconds=30.0):
        assert method == "GET"
        assert path == "/api/webhooks"
        return 200, [
            {
                "id": "webhook-1",
                "agent_id": "agent-1",
                "url": "https://example.test/agentpact/webhook",
                "events": list(module.EVENTS),
                "secret": "must-not-leak",
                "active": True,
            }
        ]

    monkeypatch.setattr(module, "_http_json", fake_http_json)

    result = module.register_webhook(
        identity_path=identity,
        public_base_url="https://example.test",
        status_path=status,
        secret_path=secret,
    )

    assert result["status"] == "already_registered"
    assert result["webhook_id"] == "webhook-1"
    assert result["list_response"]["matching"]["secret"] == "***"
    assert not secret.exists()


def test_agentpact_register_webhook_cli_writes_skip_without_api_key(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    secret = tmp_path / "webhook.secret.json"
    identity.write_text(json.dumps({"agentId": "agent-1"}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--identity",
            str(identity),
            "--status",
            str(status),
            "--secret",
            str(secret),
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
