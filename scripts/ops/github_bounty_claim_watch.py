#!/usr/bin/env python3
"""Watch active GitHub bounty claim PRs for review or payout-relevant changes."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = Path(".tmp/non-bounty/github_bounty_claim_watch_status.json")
TARGET_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
CLAIM_BOUNDARY = (
    "This proves only GitHub issue/PR claim state visible through gh. It does not prove "
    "maintainer approval, merge, bounty award, settlement, payout eligibility, or received funds."
)
OUR_LOGIN = "x0tta6bl4-ai"
TARGETS: list[dict[str, Any]] = [
    {
        "repo": "xevrion-v2/agent-playground",
        "issue": 1035,
        "pr": 1036,
        "bounty_usd": 50,
        "priority": "primary_self_reported",
        "title": "Seeded starter bounty issues omit parent bounty reference",
    },
    {
        "repo": "xevrion-v2/agent-playground",
        "issue": 980,
        "pr": 1031,
        "bounty_usd": 50,
        "priority": "primary",
        "title": "Seed meta issue workflow recreates bounty program issue",
    },
    {
        "repo": "xevrion-v2/agent-playground",
        "issue": 957,
        "pr": 972,
        "bounty_usd": 50,
        "priority": "primary",
        "title": "Seed workflows fail when bounty labels are missing",
    },
    {
        "repo": "xevrion-v2/agent-playground",
        "issue": 937,
        "pr": 938,
        "bounty_usd": 50,
        "priority": "secondary_competed",
        "title": "SECURITY reward guidance conflicts with active bounty program",
    },
]


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _gh_json(args: list[str], *, timeout_seconds: float) -> tuple[bool, Any]:
    completed = subprocess.run(
        ["gh", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        return False, {
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-1000:],
            "stderr_tail": completed.stderr[-1000:],
        }
    try:
        return True, json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return False, {"error": exc.__class__.__name__, "stdout_tail": completed.stdout[-1000:]}


def _author_login(item: dict[str, Any]) -> str:
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    return str(author.get("login") or "")


def _comment_has(text: Any, *needles: str) -> bool:
    haystack = str(text or "").lower()
    return all(needle.lower() in haystack for needle in needles)


def _latest_created_at(comments: list[dict[str, Any]], *, own: bool | None = None) -> str | None:
    values = []
    for comment in comments:
        is_own = _author_login(comment) == OUR_LOGIN
        if own is not None and is_own != own:
            continue
        created_at = str(comment.get("createdAt") or "")
        if created_at:
            values.append(created_at)
    return max(values) if values else None


def _summarize_target(target: dict[str, Any], pr: dict[str, Any], issue: dict[str, Any]) -> dict[str, Any]:
    pr_body = str(pr.get("body") or "")
    pr_comments = [item for item in pr.get("comments", []) if isinstance(item, dict)]
    issue_comments = [item for item in issue.get("comments", []) if isinstance(item, dict)]
    labels = [str(item.get("name") or "") for item in pr.get("labels", []) if isinstance(item, dict)]
    reviews = [item for item in pr.get("reviews", []) if isinstance(item, dict)]
    checks = [item for item in pr.get("statusCheckRollup", []) if isinstance(item, dict)]

    claim_text = f"/claim #{target['issue']}"
    submitted_comment = next(
        (
            comment
            for comment in issue_comments
            if _author_login(comment) == OUR_LOGIN and _comment_has(comment.get("body"), f"pr #{target['pr']}", claim_text)
        ),
        None,
    )
    submitted_at = str(submitted_comment.get("createdAt") or "") if submitted_comment else None
    external_after_submit = []
    if submitted_at:
        external_after_submit = [
            comment
            for comment in issue_comments
            if _author_login(comment) != OUR_LOGIN and str(comment.get("createdAt") or "") > submitted_at
        ]

    review_states = [str(review.get("state") or "") for review in reviews]
    failing_checks = [
        str(check.get("name") or check.get("workflowName") or check.get("displayName") or "unknown")
        for check in checks
        if str(check.get("conclusion") or check.get("status") or "").upper() in {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED"}
    ]
    claim_ready = (
        str(pr.get("state") or "").upper() == "OPEN"
        and not bool(pr.get("isDraft"))
        and claim_text.lower() in pr_body.lower()
        and TARGET_WALLET.lower() in pr_body.lower()
        and bool(submitted_comment)
    )

    attention_flags: list[str] = []
    if "CHANGES_REQUESTED" in review_states:
        attention_flags.append("changes_requested")
    if failing_checks:
        attention_flags.append("failing_checks")
    if not submitted_comment:
        attention_flags.append("missing_issue_submission_comment")
    if claim_text.lower() not in pr_body.lower():
        attention_flags.append("missing_pr_claim")
    if TARGET_WALLET.lower() not in pr_body.lower():
        attention_flags.append("missing_pr_wallet")
    if external_after_submit:
        attention_flags.append("external_issue_activity_after_submission")

    if "changes_requested" in attention_flags or "failing_checks" in attention_flags:
        next_action = "respond_or_patch_pr"
    elif not claim_ready:
        next_action = "repair_claim_metadata"
    elif external_after_submit:
        next_action = "inspect_competing_activity"
    else:
        next_action = "wait_for_maintainer_merge_reward"

    return {
        "repo": target["repo"],
        "issue": target["issue"],
        "pr": target["pr"],
        "bounty_usd": target["bounty_usd"],
        "priority": target["priority"],
        "pr_url": pr.get("url"),
        "issue_url": issue.get("url"),
        "pr_state": pr.get("state"),
        "issue_state": issue.get("state"),
        "is_draft": bool(pr.get("isDraft")),
        "mergeable": pr.get("mergeable"),
        "merge_state_status": pr.get("mergeStateStatus"),
        "labels": labels,
        "bounty_claim_label_present": "🙋 Bounty claim" in labels,
        "claim_ready": claim_ready,
        "claim_present_in_pr": claim_text.lower() in pr_body.lower(),
        "wallet_present_in_pr": TARGET_WALLET.lower() in pr_body.lower(),
        "submitted_issue_comment_present": bool(submitted_comment),
        "submitted_issue_comment_url": submitted_comment.get("url") if submitted_comment else None,
        "latest_own_issue_comment_at": _latest_created_at(issue_comments, own=True),
        "latest_external_issue_comment_at": _latest_created_at(issue_comments, own=False),
        "external_issue_comments_after_submission": len(external_after_submit),
        "reviews_total": len(reviews),
        "review_states": review_states,
        "checks_total": len(checks),
        "failing_checks": failing_checks,
        "attention_flags": attention_flags,
        "next_action": next_action,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    targets = []
    fetch_failures = []
    for target in TARGETS:
        pr_ok, pr_payload = _gh_json(
            [
                "pr",
                "view",
                str(target["pr"]),
                "--repo",
                str(target["repo"]),
                "--json",
                "title,body,state,isDraft,mergeable,mergeStateStatus,labels,comments,reviews,statusCheckRollup,url,updatedAt",
            ],
            timeout_seconds=args.timeout_seconds,
        )
        issue_ok, issue_payload = _gh_json(
            [
                "issue",
                "view",
                str(target["issue"]),
                "--repo",
                str(target["repo"]),
                "--json",
                "title,body,state,comments,url,updatedAt",
            ],
            timeout_seconds=args.timeout_seconds,
        )
        if not pr_ok or not issue_ok:
            fetch_failures.append(
                {
                    "repo": target["repo"],
                    "issue": target["issue"],
                    "pr": target["pr"],
                    "pr_ok": pr_ok,
                    "issue_ok": issue_ok,
                    "pr_error": pr_payload if not pr_ok else None,
                    "issue_error": issue_payload if not issue_ok else None,
                }
            )
            continue
        targets.append(_summarize_target(target, pr_payload, issue_payload))

    attention_targets = [item for item in targets if item.get("attention_flags")]
    claim_ready_total = sum(1 for item in targets if item.get("claim_ready"))
    status = {
        "schema": "x0tta6bl4.github_bounty_claim_watch.v1",
        "checked_at_utc": _utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "wallet": TARGET_WALLET,
        "ok": not fetch_failures,
        "targets_total": len(TARGETS),
        "targets_checked": len(targets),
        "claim_ready_total": claim_ready_total,
        "attention_targets_total": len(attention_targets),
        "fetch_failures": fetch_failures,
        "targets": targets,
        "next_action": "respond_or_patch_bounty_pr" if attention_targets else "wait_for_maintainer_merge_reward",
        "funds_received_claim_allowed": False,
    }
    _write_json(args.output, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    return parser.parse_args()


def main() -> int:
    status = run(parse_args())
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
