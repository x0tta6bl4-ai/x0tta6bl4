from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/score_paid_task_listings.py"


def test_score_paid_task_listings_cli_writes_artifacts(tmp_path: Path) -> None:
    input_path = tmp_path / "tasks.json"
    output_json = tmp_path / "selection.json"
    output_md = tmp_path / "selection.md"
    input_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "source_id": "ghbounty",
                        "title": "Fix Python test failure in CLI command",
                        "description": "Patch a Python bug, add a unit test, and submit a GitHub pull request.",
                        "labels": ["python", "bug", "test", "github"],
                        "payout_amount": 250,
                        "payout_asset": "USDC",
                        "deadline_utc": "2026-06-10T00:00:00Z",
                        "url": "https://www.ghbounty.com/example/fix-python-test",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--input",
            str(input_path),
            "--write-json",
            str(output_json),
            "--write-md",
            str(output_md),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    stdout = json.loads(result.stdout)
    selection = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_md.read_text(encoding="utf-8")
    assert stdout["status"] == "selection_ready"
    assert stdout["funds_received_claim_allowed"] is False
    assert selection["selected_first_task"]["source_id"] == "ghbounty"
    assert "x0tta6bl4 Paid Task Selection" in markdown
    assert "Funds received claim allowed: False" in markdown
