from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/x402_directory_watch.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("x402_directory_watch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_payload_contains_checks_nested_directory_payload() -> None:
    mod = _load_module()

    assert mod.payload_contains(
        {"services": [{"resourceUrl": "https://example.test/paid/domain-health"}]},
        "example.test",
        "domain-health",
    )


def test_summarize_watch_prefers_visible_directory_hits() -> None:
    mod = _load_module()

    summary = mod.summarize_watch(
        {
            "public": {"ready": True},
            "wallet": {
                "coin_balance": "0",
                "has_tokens": False,
                "has_token_transfers": False,
                "probe": {"ok": True},
            },
            "directory_visibility": {
                "archtools": False,
                "x402_direct": False,
                "gate402_direct": True,
                "agoragentic": True,
            },
        }
    )

    assert summary["public_ready"] is True
    assert summary["directory_hits_total"] == 2
    assert summary["wallet_zero"] is True
    assert summary["money_received"] is False
    assert summary["next_action"] == "watch_for_paid_calls_and_orders"


def test_summarize_watch_marks_money_received_when_wallet_is_not_zero() -> None:
    mod = _load_module()

    summary = mod.summarize_watch(
        {
            "public": {"ready": True},
            "wallet": {"coin_balance": "1", "has_tokens": False, "probe": {"ok": True}},
            "directory_visibility": {},
        }
    )

    assert summary["wallet_zero"] is False
    assert summary["money_received"] is True


def test_summarize_watch_does_not_claim_money_when_wallet_probe_failed() -> None:
    mod = _load_module()

    summary = mod.summarize_watch(
        {
            "public": {"ready": True},
            "wallet": {
                "coin_balance": None,
                "has_tokens": None,
                "has_token_transfers": None,
                "probe": {"ok": False, "http_status": 403},
            },
            "directory_visibility": {"gate402_direct": True},
        }
    )

    assert summary["wallet_probe_ok"] is False
    assert summary["wallet_zero"] is False
    assert summary["money_received"] is False
