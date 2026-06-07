from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentpact_wallet_targeted_offers.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agentpact_wallet_targeted_offers", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_targeted_offers_posts_missing_offers(monkeypatch, tmp_path: Path) -> None:
    mod = _load_module()
    identity = tmp_path / "identity.secret.json"
    status_path = tmp_path / "status.json"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret"}), encoding="utf-8")
    posts: list[dict[str, Any]] = []

    def fake_http_json(method: str, path: str, **kwargs):
        if method == "GET" and path == "/api/offers":
            if not posts:
                return 200, [{"id": "old-1", "agent_id": "agent-1", "status": "active", "title": "Old offer"}]
            return 200, [
                {"id": "old-1", "agent_id": "agent-1", "status": "active", "title": "Old offer"},
                *[
                    {
                        "id": f"new-{index}",
                        "agent_id": "agent-1",
                        "status": "active",
                        "title": payload["title"],
                    }
                    for index, payload in enumerate(posts, start=1)
                ],
            ]
        if method == "POST" and path == "/api/offers":
            payload = kwargs["payload"]
            posts.append(payload)
            return 201, {"id": f"new-{len(posts)}", "status": "active", "title": payload["title"]}
        if method == "GET" and path.startswith("/api/matches/recommendations"):
            return 200, [{"id": "match-1", "offer_id": "new-1"}]
        raise AssertionError((method, path))

    monkeypatch.setattr(mod, "_http_json", fake_http_json)

    status = mod.run(
        argparse.Namespace(
            identity=identity,
            status=status_path,
            timeout_seconds=1.0,
        )
    )

    assert status["ok"] is True
    assert status["posted_total"] == len(mod.TARGET_OFFERS)
    assert status["failed_total"] == 0
    assert status["active_offers_before"] == 1
    assert status["active_offers_after"] == 1 + len(mod.TARGET_OFFERS)
    assert status["matches_total"] == 1
    assert json.loads(status_path.read_text(encoding="utf-8"))["funds_received_claim_allowed"] is False


def test_targeted_offers_skips_existing_offer(monkeypatch, tmp_path: Path) -> None:
    mod = _load_module()
    identity = tmp_path / "identity.secret.json"
    status_path = tmp_path / "status.json"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret"}), encoding="utf-8")
    first_title = mod.TARGET_OFFERS[0]["title"]
    posts: list[dict[str, Any]] = []

    def fake_http_json(method: str, path: str, **kwargs):
        if method == "GET" and path == "/api/offers":
            return 200, [{"id": "existing-1", "agent_id": "agent-1", "status": "active", "title": first_title}]
        if method == "POST" and path == "/api/offers":
            payload = kwargs["payload"]
            posts.append(payload)
            return 201, {"id": f"new-{len(posts)}", "status": "active", "title": payload["title"]}
        if method == "GET" and path.startswith("/api/matches/recommendations"):
            return 200, []
        raise AssertionError((method, path))

    monkeypatch.setattr(mod, "_http_json", fake_http_json)

    status = mod.run(argparse.Namespace(identity=identity, status=status_path, timeout_seconds=1.0))

    assert status["known_total"] == len(mod.TARGET_OFFERS)
    assert status["posted_total"] == len(mod.TARGET_OFFERS) - 1
    assert status["results"][0]["status"] == "already_active"
