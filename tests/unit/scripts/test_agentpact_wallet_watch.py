from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentpact_wallet_watch.py"


def test_agentpact_wallet_watch_offline_writes_summary(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    profile = tmp_path / "profile.json"
    offers = tmp_path / "offers.json"
    matches = tmp_path / "matches.json"
    deals = tmp_path / "deals.json"
    output = tmp_path / "watch.json"
    wallet = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    identity.write_text(json.dumps({"agentId": "agent-1", "apiKey": "secret"}), encoding="utf-8")
    profile.write_text(json.dumps({"owner_wallet_address": wallet}), encoding="utf-8")
    offers.write_text(json.dumps([{"id": "offer-1", "agent_id": "agent-1", "status": "active"}]), encoding="utf-8")
    matches.write_text(json.dumps([{"id": "match-1", "offer_id": "offer-1", "need_id": "need-1"}]), encoding="utf-8")
    deals.write_text(json.dumps([]), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--identity",
            str(identity),
            "--wallet",
            wallet,
            "--output",
            str(output),
            "--offline-profile",
            str(profile),
            "--offline-offers",
            str(offers),
            "--offline-matches",
            str(matches),
            "--offline-deals",
            str(deals),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["wallet_ready"] is True
    assert payload["matches_total"] == 1
    assert json.loads(result.stdout)["next_action"] == "wait_for_buyer_accept_or_platform_auto_deal"
