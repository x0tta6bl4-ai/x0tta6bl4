from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/payanagent_job_watcher.py"


def test_payanagent_job_watcher_bids_safe_jobs_and_delivers_assigned(tmp_path: Path) -> None:
    identity = tmp_path / "identity.secret.json"
    state = tmp_path / "state.json"
    status = tmp_path / "status.json"
    open_jobs = tmp_path / "open_jobs.json"
    all_jobs = tmp_path / "all_jobs.json"

    identity.write_text(
        json.dumps({"agent_id": "agent-1", "api_key": "pk_test"}),
        encoding="utf-8",
    )
    open_jobs.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "_id": "job-safe",
                        "title": "Write API docs",
                        "description": "Need endpoint documentation in Markdown.",
                        "budgetMaxCents": 25,
                    },
                    {
                        "_id": "job-blocked",
                        "title": "CAPTCHA bypass",
                        "description": "Need account automation.",
                        "budgetMaxCents": 25,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    all_jobs.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "_id": "job-accepted",
                        "title": "Repo triage",
                        "description": "Review public code snippets.",
                        "providerAgentId": "agent-1",
                        "status": "accepted",
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
            "--identity",
            str(identity),
            "--state",
            str(state),
            "--status",
            str(status),
            "--offline-open-jobs",
            str(open_jobs),
            "--offline-all-jobs",
            str(all_jobs),
            "--once",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["open_jobs_total"] == 2
    assert payload["bids"][0]["status"] == "bid_submitted"
    assert payload["bids"][1]["status"] == "skipped"
    assert payload["deliveries"][0]["status"] == "delivered"
    assert payload["funds_received_claim_allowed"] is False
