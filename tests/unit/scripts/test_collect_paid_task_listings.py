from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/collect_paid_task_listings.py"


def test_collect_paid_task_listings_cli_writes_fixture_collection(tmp_path: Path) -> None:
    fixture = tmp_path / "github-search.json"
    output = tmp_path / "paid-task-listings.json"
    fixture.write_text(
        json.dumps(
            {
                "total_count": 624,
                "items": [
                    {
                        "repository_url": "https://api.github.com/repos/tine1117/oss-hunter-livefire",
                        "html_url": "https://github.com/tine1117/oss-hunter-livefire/issues/1",
                        "number": 1,
                        "title": "parse_duration drops the days (d) unit",
                        "state": "open",
                        "comments": 7,
                        "labels": [
                            {"name": "\U0001f48e Bounty"},
                            {"name": "$50"},
                        ],
                        "body": "Fix parse_duration days support and add tests.\n\n/bounty $50\n",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--fixture-json",
            str(fixture),
            "--write-json",
            str(output),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    stdout = json.loads(result.stdout)
    collection = json.loads(output.read_text(encoding="utf-8"))
    assert stdout["status"] == "collection_ready"
    assert stdout["public_network_used"] is False
    assert stdout["funds_received_claim_allowed"] is False
    assert collection["tasks"][0]["source_id"] == "algora"
    assert collection["tasks"][0]["payout_usd"] == 50
