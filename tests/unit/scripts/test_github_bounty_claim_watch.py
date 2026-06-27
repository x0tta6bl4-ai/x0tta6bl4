from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/github_bounty_claim_watch.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("github_bounty_claim_watch", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summarize_target_marks_ready_claim_with_submission_comment() -> None:
    mod = _load_module()
    target = {
        "repo": "owner/repo",
        "issue": 957,
        "pr": 972,
        "bounty_usd": 50,
        "priority": "primary",
    }
    pr = {
        "body": f"Closes #957\n/claim #957\nPayment: {mod.TARGET_WALLET}",
        "state": "OPEN",
        "isDraft": False,
        "labels": [{"name": "🙋 Bounty claim"}],
        "comments": [],
        "reviews": [],
        "statusCheckRollup": [],
        "url": "https://example.test/pr/972",
    }
    issue = {
        "state": "OPEN",
        "url": "https://example.test/issues/957",
        "comments": [
            {
                "author": {"login": mod.OUR_LOGIN},
                "body": "Submitted PR #972 for this bounty.\n\n/claim #957",
                "createdAt": "2026-06-07T02:42:15Z",
                "url": "https://example.test/comment",
            }
        ],
    }

    summary = mod._summarize_target(target, pr, issue)

    assert summary["claim_ready"] is True
    assert summary["submitted_issue_comment_present"] is True
    assert summary["attention_flags"] == []
    assert summary["next_action"] == "wait_for_maintainer_merge_reward"


def test_summarize_target_requires_wallet_and_submission_comment() -> None:
    mod = _load_module()
    target = {
        "repo": "owner/repo",
        "issue": 937,
        "pr": 938,
        "bounty_usd": 50,
        "priority": "secondary",
    }
    pr = {
        "body": "/claim #937",
        "state": "OPEN",
        "isDraft": False,
        "labels": [],
        "comments": [],
        "reviews": [],
        "statusCheckRollup": [],
    }
    issue = {"state": "OPEN", "comments": []}

    summary = mod._summarize_target(target, pr, issue)

    assert summary["claim_ready"] is False
    assert "missing_pr_wallet" in summary["attention_flags"]
    assert "missing_issue_submission_comment" in summary["attention_flags"]
    assert summary["next_action"] == "repair_claim_metadata"
