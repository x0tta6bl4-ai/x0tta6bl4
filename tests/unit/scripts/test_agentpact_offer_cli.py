from __future__ import annotations

import json
import stat
import subprocess
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentpact_offer_cli.py"


def test_agentpact_offer_cli_offline_preview_writes_redacted_status(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    status = tmp_path / "status.json"
    offer = tmp_path / "offer.json"
    offer.write_text(
        json.dumps(
            {
                "offer": {
                    "title": "Structured data extraction and repo triage agent",
                    "descriptionMd": "I return structured reports and reject unsafe tasks.",
                    "category": "data",
                    "tags": ["json", "reports"],
                    "basePrice": 5,
                    "slaDays": 1,
                }
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--offline",
            "--identity",
            str(identity),
            "--offer",
            str(offer),
            "--write-status",
            str(status),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    stdout = json.loads(result.stdout)
    status_payload = json.loads(status.read_text(encoding="utf-8"))
    mode = stat.S_IMODE(identity.stat().st_mode)
    assert mode == 0o600
    uuid.UUID(status_payload["agentId"])
    assert stdout["register"]["status"] == "offline_preview"
    assert stdout["offer"]["status"] == "offer_preview"
    assert stdout["apiKey_present"] is False
    assert status_payload["funds_received_claim_allowed"] is False
