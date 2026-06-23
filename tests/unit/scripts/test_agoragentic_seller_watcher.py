from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agoragentic_seller_watcher.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agoragentic_seller_watcher", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_summary_marks_verified_public_listing() -> None:
    mod = _load_module()
    listing_id = "47d9779a-6e29-4eb5-9f21-2a0ec8e8658e"
    checks = {
        "/api/seller/health": {
            "response": {
                "listings": [
                    {
                        "id": listing_id,
                        "name": "x0tta6bl4 Domain Health Lite",
                        "status": "active",
                        "review_status": "approved",
                        "verification_status": "verified",
                        "price_per_unit_usdc": 0.1,
                        "total_invocations": 2,
                        "success_count": 2,
                        "failure_count": 0,
                        "public_browse_visibility": {"visible": True, "reason": "browse_visible"},
                    }
                ]
            }
        },
        "/api/agents/me": {
            "response": {"wallet": {"balance": 0.2, "withdrawable": 0.2, "total_earned": 0.2}}
        },
        "/api/agents/me/tasks": {"response": {"tasks": [{"id": "task-1"}]}},
        "/api/webhooks": {"response": {"webhooks": [{"id": "whk-1"}]}},
        "public_search": {"response": {"items": [{"id": listing_id, "name": "x0tta6bl4"}]}},
    }

    summary = mod.build_summary(checks, listing_id=listing_id)

    assert summary["public_visible"] is True
    assert summary["verification_status"] == "verified"
    assert summary["total_invocations"] == 2
    assert summary["wallet_total_earned_usdc"] == 0.2
    assert summary["next_action"] == "wait_for_buyer_invocation"


def test_collect_status_uses_short_request_timeout(monkeypatch) -> None:
    mod = _load_module()
    calls = []

    def fake_fetch_json(url, *, api_key=None, timeout_seconds=20.0):
        calls.append((url, api_key, timeout_seconds))
        return {"http_status": 200, "ok": True, "response": {}}

    monkeypatch.setattr(mod, "_fetch_json", fake_fetch_json)

    status = mod.collect_status(
        api_key="amk_test",
        listing_id="listing-1",
        base_url="https://example.test",
        request_timeout_seconds=2.5,
    )

    assert status["summary"]["listing_id"] == "listing-1"
    assert calls
    assert all(call[1] == "amk_test" for call in calls if "/api/capabilities?query=" not in call[0])
    assert all(call[2] == 2.5 for call in calls)
