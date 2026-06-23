from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_paid_task_hunter.py"


def test_run_paid_task_hunter_cli_works_offline_with_fixture(tmp_path: Path) -> None:
    fixture_json = tmp_path / "github-search.json"
    listings_json = tmp_path / "listings.json"
    selection_json = tmp_path / "selection.json"
    report_md = tmp_path / "report.md"
    fixture_json.write_text(
        json.dumps(
            {
                "total_count": 1,
                "items": [
                    {
                        "repository_url": "https://api.github.com/repos/example/project",
                        "html_url": "https://github.com/example/project/issues/1",
                        "number": 1,
                        "title": "Fix README typo",
                        "state": "open",
                        "comments": 0,
                        "created_at": "2026-06-04T00:00:00Z",
                        "updated_at": "2026-06-04T00:00:00Z",
                        "labels": [{"name": "\U0001f48e Bounty"}, {"name": "$50"}],
                        "body": "Review the README for a minor spelling issue and submit a small cleanup PR.\n\n/bounty $50",
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
            str(fixture_json),
            "--write-listings-json",
            str(listings_json),
            "--write-selection-json",
            str(selection_json),
            "--write-report-md",
            str(report_md),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    stdout = json.loads(result.stdout)
    selection = json.loads(selection_json.read_text(encoding="utf-8"))
    report = report_md.read_text(encoding="utf-8")
    assert stdout["status"] == "selection_ready"
    assert stdout["selected_first_task"]["title"] == "Fix README typo"
    assert selection["selection_mode"] == "token_roi"
    assert "x0tta6bl4 Paid Task Hunter" in report
    assert "Funds received claim allowed: False" in report
