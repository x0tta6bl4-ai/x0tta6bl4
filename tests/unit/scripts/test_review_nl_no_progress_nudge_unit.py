import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "review_nl_no_progress_nudge.sh"


def test_review_nl_no_progress_nudge_shell_syntax() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_review_nl_no_progress_nudge_is_review_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    forbidden_patterns = [
        r"--apply",
        r"SEND_LEGACY_NO_PROGRESS_NUDGE",
        r"SEND_LEGACY_MIGRATION",
        r"send_legacy_no_progress_nudge\.py",
        r"send_legacy_client_migration_message\.py",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+x-ui",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+nginx",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None

    assert "refresh_nl_vpn_readonly_evidence.sh" in text
    assert "nl-no-progress-nudge-review-latest.json" in text
    assert "REVIEW_JSON_OUT" in text
    assert "REFRESH_CMD" in text
    assert "VPN_STATUS_CMD" in text
    assert "SSH_CMD" in text
    assert "review_and_send_no_progress_nudge" in text
    assert "earliest_mutation_seconds_until" in text
    assert "hash_collection_status" in text
    assert "ready_blockers" in text
    assert "blocked_actions" in text
    assert "cooldown_active" in text
    assert "reason" in text
    assert "user_message_allowed_after_review" in text
    assert "expected_hashes" in text


def test_review_nl_no_progress_nudge_binds_all_required_hash_names() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for field in [
        "packet",
        "dry_run",
        "subscription_payload",
        "transport_usage",
        "replies",
    ]:
        assert field in text

    for remote_path in [
        "/var/lib/ghost-access/legacy-migration/latest.json",
        "/var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json",
        "/var/lib/ghost-access/subscription-payload/latest.json",
        "/var/lib/ghost-access/transport-usage/latest.json",
        "/var/lib/ghost-access/legacy-migration/replies.json",
    ]:
        assert remote_path in text


def test_review_nl_no_progress_nudge_audits_hash_collection_failure(tmp_path: Path) -> None:
    refresh_cmd = tmp_path / "fake_refresh.sh"
    status_cmd = tmp_path / "fake_status.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    review_out = tmp_path / "review.json"

    refresh_cmd.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    status_cmd.write_text(
        """#!/usr/bin/env bash
cat <<'JSON'
{
  "overall_status": "advisory",
  "user_connectivity": {
    "status": "partial_user_progress",
    "blockers": ["some_active_users_without_progress_signal"]
  },
  "transport_usage": {
    "status": "attention",
    "summary": {"restart_relevant": false}
  },
  "next_safe_action": {
    "action": "review_and_send_no_progress_nudge",
    "reason": "some active users still have no progress signal",
    "user_message_allowed_after_review": true,
    "no_progress_candidate_count": 1,
    "earliest_mutation_at": "2026-06-06T02:28:51Z",
    "earliest_mutation_seconds_until": 0,
    "cooldown_active": false,
    "automatic_restart_allowed": false,
    "immediate_readonly_actions": [],
    "deferred_readonly_actions": [],
    "blocked_actions": ["restart_x-ui"]
  }
}
JSON
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "hash fetch failed" >&2
exit 9
""",
        encoding="utf-8",
    )
    refresh_cmd.chmod(0o755)
    status_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REFRESH_CMD"] = str(refresh_cmd)
    env["VPN_STATUS_CMD"] = str(status_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["REVIEW_JSON_OUT"] = str(review_out)
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    saved = json.loads(review_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["ready"] is False
    assert payload["reason"] == "remote hash collection failed before no-progress nudge review"
    assert payload["hash_collection_status"] == "failed"
    assert payload["hash_collection_exit_code"] == 9
    assert "hash_collection_failed" in payload["ready_blockers"]
    assert "hash_collection_error" not in payload
    assert payload["hash_collection_error_size_bytes"] == len("hash fetch failed")
    assert payload["hash_collection_error_sha256"] == hashlib.sha256(
        b"hash fetch failed"
    ).hexdigest()
    assert payload["expected_hashes"] == {}


def test_review_nl_no_progress_nudge_reports_cooldown_ready_blockers(tmp_path: Path) -> None:
    refresh_cmd = tmp_path / "fake_refresh.sh"
    status_cmd = tmp_path / "fake_status.sh"
    review_out = tmp_path / "review.json"

    refresh_cmd.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    status_cmd.write_text(
        """#!/usr/bin/env bash
cat <<'JSON'
{
  "overall_status": "advisory",
  "user_connectivity": {
    "status": "partial_user_progress",
    "blockers": ["some_active_users_without_progress_signal"]
  },
  "transport_usage": {
    "status": "attention",
    "summary": {"restart_relevant": false}
  },
  "next_safe_action": {
    "action": "wait_for_nudge_cooldown_and_collect_readonly_evidence",
    "reason": "no-progress nudge cooldown is active",
    "user_message_allowed_after_review": false,
    "no_progress_candidate_count": 4,
    "earliest_mutation_at": "2026-06-06T02:28:51Z",
    "earliest_mutation_seconds_until": 3600,
    "cooldown_active": true,
    "automatic_restart_allowed": false,
    "immediate_readonly_actions": [],
    "deferred_readonly_actions": [
      "refresh_transport_usage_evidence_before_user_nudge"
    ],
    "blocked_actions": [
      "restart_x-ui",
      "send_duplicate_no_progress_nudge_before_cooldown"
    ]
  }
}
JSON
""",
        encoding="utf-8",
    )
    refresh_cmd.chmod(0o755)
    status_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REFRESH_CMD"] = str(refresh_cmd)
    env["VPN_STATUS_CMD"] = str(status_cmd)
    env["REVIEW_JSON_OUT"] = str(review_out)
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ready"] is False
    assert payload["hash_collection_status"] == "not_required"
    assert payload["expected_hashes"] == {}
    assert payload["ready_blockers"] == [
        "action_not_review_and_send_no_progress_nudge",
        "user_message_not_allowed_after_review",
        "cooldown_active",
    ]
