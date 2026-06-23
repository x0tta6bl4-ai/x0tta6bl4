from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_paid_task_watch_loop.py"


def test_run_paid_task_watch_loop_finds_clean_fixture_target(tmp_path: Path) -> None:
    fixture_json = tmp_path / "github-search.json"
    current_json = tmp_path / "current.json"
    history_jsonl = tmp_path / "history.jsonl"
    alerts_md = tmp_path / "alerts.md"
    fixture_json.write_text(
        json.dumps(
            {
                "total_count": 1,
                "items": [
                    {
                        "repository_url": "https://api.github.com/repos/example/project",
                        "html_url": "https://github.com/example/project/issues/1",
                        "comments_url": "https://api.github.com/repos/example/project/issues/1/comments",
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
            "--cycles",
            "1",
            "--interval-seconds",
            "0",
            "--fixture-json",
            str(fixture_json),
            "--enrich-comments",
            "0",
            "--write-current-json",
            str(current_json),
            "--write-history-jsonl",
            str(history_jsonl),
            "--write-alerts-md",
            str(alerts_md),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    stdout = json.loads(result.stdout)
    current = json.loads(current_json.read_text(encoding="utf-8"))
    history = history_jsonl.read_text(encoding="utf-8").strip().splitlines()
    alerts = alerts_md.read_text(encoding="utf-8")
    assert stdout["action"] == "start_work"
    assert current["selected_first_task"]["title"] == "Fix README typo"
    assert len(history) == 1
    assert "x0tta6bl4 Paid Task Watch" in alerts
    assert "Clean Target" in alerts
