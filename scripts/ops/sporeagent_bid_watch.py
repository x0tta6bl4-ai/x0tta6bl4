#!/usr/bin/env python3
"""Verify whether SporeAgent bid artifacts are still visible in the live API."""

from __future__ import annotations

import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_OUTPUT = ARTIFACT_DIR / "sporeagent_live_bid_check.json"
SPORE_AGENT_ID = "03fcb363-abc1-4284-ad00-f05fb5e43cdc"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_submit_artifacts() -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for path in sorted(ARTIFACT_DIR.glob("sporeagent_bid_*_response.txt")):
        text = path.read_text(encoding="utf-8", errors="replace")
        bid_id = re.search(r'"bid_id"\s*:\s*"([^"]+)"', text)
        task_id = re.search(r'"task_id"\s*:\s*"([^"]+)"', text)
        status = re.search(r'"status"\s*:\s*"([^"]+)"', text)
        artifacts.append(
            {
                "artifact": str(path),
                "bid_id": bid_id.group(1) if bid_id else "",
                "task_id": task_id.group(1) if task_id else "",
                "submit_status": status.group(1) if status else "",
            }
        )
    return artifacts


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{url}?_={int(time.time())}",
        headers={
            "cache-control": "no-cache",
            "pragma": "no-cache",
            "user-agent": "x0tta6bl4-sporeagent-bid-watch",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    return payload if isinstance(payload, dict) else {}


def build_sporeagent_live_bid_check() -> dict[str, Any]:
    artifacts = _extract_submit_artifacts()
    task_checks: list[dict[str, Any]] = []
    visible_bid_ids: set[str] = set()
    visible_agent_ids: set[str] = set()

    for artifact in artifacts:
        task_id = artifact.get("task_id")
        if not task_id:
            continue
        task = _get_json(f"https://sporeagent.com/api/tasks/{task_id}")
        bids = task.get("bids", []) if isinstance(task.get("bids"), list) else []
        task_visible_bid_ids = [str(bid.get("id", "")) for bid in bids]
        task_visible_agent_ids = [str(bid.get("agent_id", "")) for bid in bids]
        visible_bid_ids.update(item for item in task_visible_bid_ids if item)
        visible_agent_ids.update(item for item in task_visible_agent_ids if item)
        task_checks.append(
            {
                "task_id": task_id,
                "task_title": task.get("title"),
                "task_status": task.get("status"),
                "assigned_agent_id": task.get("assigned_agent_id"),
                "submitted_bid_id": artifact.get("bid_id"),
                "submitted_status": artifact.get("submit_status"),
                "submitted_bid_visible_live": artifact.get("bid_id") in task_visible_bid_ids,
                "our_agent_has_any_live_bid_on_task": SPORE_AGENT_ID in task_visible_agent_ids,
                "live_bid_count": len(bids),
            }
        )

    submitted_bid_ids = {item.get("bid_id", "") for item in artifacts if item.get("bid_id")}
    visible_submitted = submitted_bid_ids.intersection(visible_bid_ids)
    decision = (
        "SPORE_BIDS_VISIBLE_LIVE"
        if submitted_bid_ids and len(visible_submitted) == len(submitted_bid_ids)
        else "SPORE_SUBMIT_ARTIFACTS_NOT_VISIBLE_LIVE"
    )
    return {
        "schema": "x0tta6bl4.sporeagent_live_bid_check.v1",
        "checked_at_utc": _utc_now(),
        "agent_id": SPORE_AGENT_ID,
        "submitted_bids_total": len(submitted_bid_ids),
        "submitted_bids_visible_live": len(visible_submitted),
        "current_agent_visible_in_live_bids": SPORE_AGENT_ID in visible_agent_ids,
        "decision": decision,
        "task_checks": task_checks,
        "claim_boundary": (
            "This check verifies current public SporeAgent API visibility only. "
            "It does not prove payout, acceptance, or durable persistence."
        ),
    }


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_sporeagent_live_bid_check()
    DEFAULT_OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
