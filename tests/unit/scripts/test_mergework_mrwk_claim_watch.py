from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/mergework_mrwk_claim_watch.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("mergework_mrwk_claim_watch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summarize_marks_earned_mrwk_and_required_claim() -> None:
    mod = _load_module()

    summary = mod._summarize(
        status_payload={
            "current_transfer_paths": ["github:* balance claims into a linked wallet"],
            "unsupported_public_paths": ["BTC", "USDC", "fiat", "bridge", "exchange", "off-ramp"],
        },
        account_payload={
            "exists": True,
            "balance_mrwk": "525",
            "transfer_status": "Claim GitHub balances from /me after linking a registered mrwk1 wallet.",
            "accepted_work": {
                "accepted_awards": 7,
                "accepted_mrwk": "525",
                "latest_submission_url": "https://github.com/ramimbo/mergework/pull/958",
                "latest_proof_public_url": "https://mrwk.online/proofs/example",
            },
            "pending_summary": {"pending_mrwk": "0"},
        },
        accepted_payload={"accepted_work": [{"amount_mrwk": "75", "submission_url": "https://example.test/pr"}]},
        auth_payload={"authenticated": False, "github_login": None},
        fetch_failures=[],
    )

    assert summary["earned_signal"] is True
    assert summary["claim_required"] is True
    assert summary["github_claim_supported"] is True
    assert summary["base_wallet_supported_by_mergework"] is False
    assert summary["funds_received_claim_allowed"] is False
    assert summary["next_action"] == "open_mrwk_me_sign_in_link_wallet_claim"


def test_summarize_keeps_zero_balance_as_no_earned_signal() -> None:
    mod = _load_module()

    summary = mod._summarize(
        status_payload={},
        account_payload={"exists": False, "balance_mrwk": "0", "accepted_work": {"accepted_awards": 0, "accepted_mrwk": "0"}},
        accepted_payload={"accepted_work": []},
        auth_payload={"authenticated": False},
        fetch_failures=[],
    )

    assert summary["earned_signal"] is False
    assert summary["claim_required"] is False
    assert summary["earned_mrwk_claim_allowed"] is False
    assert summary["next_action"] == "find_new_mergework_bounty_or_paid_task"
