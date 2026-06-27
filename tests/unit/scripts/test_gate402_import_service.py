from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_defunct


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/gate402_import_service.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gate402_import_service", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_or_create_identity_creates_signing_wallet(tmp_path: Path) -> None:
    mod = _load_module()
    identity_file = tmp_path / "gate402_identity.secret.json"

    identity = mod.load_or_create_identity(identity_file)

    assert identity_file.exists()
    assert identity["address"].startswith("0x")
    assert identity["private_key"].startswith("0x")
    assert identity_file.stat().st_mode & 0o777 == 0o600


def test_sign_text_returns_recoverable_evm_signature() -> None:
    mod = _load_module()
    account = Account.create()
    message = "agenthub-auth:test"

    signature = mod.sign_text(account.key.hex(), message)
    recovered = Account.recover_message(encode_defunct(text=message), signature=signature)

    assert signature.startswith("0x")
    assert recovered.lower() == account.address.lower()


def test_build_import_payload_uses_import_proof_shape() -> None:
    mod = _load_module()

    payload = mod.build_import_payload(
        manifest_url="https://example.test/.well-known/x402.json",
        name="x0tta6bl4 paid x402 tools",
        owner_wallet="0x1234567890123456789012345678901234567890",
        challenge_id="challenge-1",
        signature="0xsig",
    )

    assert payload["importUrl"] == "https://example.test/.well-known/x402.json"
    assert payload["url"] == "https://example.test/.well-known/x402.json"
    assert payload["walletAddress"] == "0x1234567890123456789012345678901234567890"
    assert payload["chain"] == "Base"
    assert payload["pricePerCall"] == 0
    assert payload["importProof"] == {"challengeId": "challenge-1", "signature": "0xsig"}


def test_redact_removes_tokens_signatures_and_private_keys() -> None:
    mod = _load_module()

    redacted = mod.redact(
        {
            "token": "abc",
            "private_key": "0xsecret",
            "nested": [{"signature": "0xsig", "message": "sign this", "safe": "ok"}],
        }
    )

    assert redacted["token"] == "<redacted>"
    assert redacted["private_key"] == "<redacted>"
    assert redacted["nested"][0]["signature"] == "<redacted>"
    assert redacted["nested"][0]["message"] == "<redacted>"
    assert redacted["nested"][0]["safe"] == "ok"


def test_summarize_status_detects_visible_import() -> None:
    mod = _load_module()
    discover = mod.HttpResult(
        ok=True,
        http_status=200,
        payload={
            "results": [
                {
                    "name": "x0tta6bl4 paid x402 tools",
                    "url": "https://example.test/.well-known/x402.json",
                }
            ]
        },
    )

    summary = mod.summarize_status(
        {"import": {"submit": {"ok": True}}},
        discover,
        None,
        "x0tta6bl4 paid x402 tools",
        "https://example.test/.well-known/x402.json",
    )

    assert summary["submitted"] is True
    assert summary["known_registered"] is True
    assert summary["discover_visible"] is True
    assert summary["next_action"] == "keep_catalog_watch_running"


def test_summarize_status_accepts_direct_service_visibility_before_search_indexing() -> None:
    mod = _load_module()
    discover = mod.HttpResult(ok=True, http_status=200, payload={"results": []})
    direct = mod.HttpResult(ok=True, http_status=200, payload={"id": "service-1", "status": "active"})

    summary = mod.summarize_status(
        {"import": {"skipped": True, "reason": "existing_service_id", "service_id": "service-1"}},
        discover,
        direct,
        "x0tta6bl4 paid x402 tools",
        "https://example.test/.well-known/x402.json",
    )

    assert summary["submitted"] is False
    assert summary["known_registered"] is True
    assert summary["service_id"] == "service-1"
    assert summary["direct_service_visible"] is True
    assert summary["next_action"] == "service_active_wait_for_gate402_search_indexing"
