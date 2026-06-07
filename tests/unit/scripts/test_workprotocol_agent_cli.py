from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/workprotocol_agent_cli.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("workprotocol_agent_cli", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workprotocol_agent_payload_uses_target_wallet_and_fixed_scope() -> None:
    mod = _load_module()
    wallet = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"

    payload = mod.build_agent_payload("x0tta6bl4-worker", wallet)

    assert payload["name"] == "x0tta6bl4-worker"
    assert payload["walletAddress"] == wallet
    assert payload["capabilities"]["maxJobValue"] == 150
    assert "bounty work" in payload["description"]
    assert payload["pricing"]["acceptedCurrencies"] == ["USDC"]


def test_workprotocol_redact_masks_api_key() -> None:
    mod = _load_module()

    redacted = mod.redact({"agent": {"apiKey": "wp_agent_secret", "id": "agent-1"}})

    assert redacted["agent"]["apiKey"] == "[redacted]"
    assert redacted["agent"]["id"] == "agent-1"


def test_workprotocol_extract_claim_id_from_common_shapes() -> None:
    mod = _load_module()

    assert mod.extract_claim_id({"claim": {"id": "claim-1"}}) == "claim-1"
    assert mod.extract_claim_id({"claimId": "claim-2"}) == "claim-2"
    assert mod.extract_claim_id({"data": {"id": "claim-3"}}) == "claim-3"
    assert mod.extract_claim_id({}) == ""


def test_workprotocol_claim_gate_blocks_high_effort() -> None:
    mod = _load_module()

    ok, reasons = mod._claimable(
        {
            "source_id": "workprotocol",
            "decision": "manual_review",
            "score": 55,
            "estimated_token_cost": 120000,
            "risk_flags": ["high_effort"],
        },
        min_score=62,
        max_estimated_tokens=60000,
    )

    assert ok is False
    assert "decision:manual_review" in reasons
    assert "risk:high_effort" in reasons


def test_workprotocol_cli_can_write_empty_status_without_network(tmp_path: Path) -> None:
    status = tmp_path / "workprotocol_status.json"
    secret = tmp_path / "missing.secret.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--status-file",
            str(status),
            "--secret-file",
            str(secret),
            "--status-only",
            "--dry-run",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["has_api_key"] is False
    assert payload["has_agent_id"] is False
    assert "claim_boundary" in payload
