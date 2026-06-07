import hashlib
import json
import os
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "send_nl_no_progress_nudge_guarded.sh"


def test_send_nl_no_progress_nudge_guarded_shell_syntax() -> None:
    proc = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_send_nl_no_progress_nudge_guarded_requires_review_and_confirmation() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "review_nl_no_progress_nudge.sh" in text
    assert "REVIEW_CMD" in text
    assert "SSH_CMD" in text
    assert "blocked_by_review_guard" in text
    assert "ready_blockers" in text
    assert "ready_blocker_count" in text
    assert "review_invariant_blockers" in text
    assert "review_invariant_blocker_count" in text
    assert "hash_collection_not_success" in text
    assert "hash_collection_exit_code_nonzero" in text
    assert "review_failed" in text
    assert "review_output_invalid" in text
    assert "review_output_sha256" in text
    assert "review_output_size_bytes" in text
    assert "confirmation_required" in text
    assert "send_failed" in text
    assert "send_output_invalid" in text
    assert "CONFIRM_NL_NO_PROGRESS_NUDGE" in text
    assert "SEND_NL_NO_PROGRESS_NUDGE" in text
    assert "LOCAL_ATTEMPT_OUT" in text
    assert "nl-no-progress-nudge-guarded-send-latest.json" in text
    assert "write_attempt_result" in text
    assert "--apply" in text
    assert "--confirm SEND_LEGACY_NO_PROGRESS_NUDGE" in text
    assert "--limit ${limit}" in text


def test_send_nl_no_progress_nudge_guarded_binds_all_runtime_hashes() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    required_flags = [
        "--expect-packet-sha256",
        "--expect-dry-run-sha256",
        "--expect-subscription-payload-sha256",
        "--expect-transport-usage-sha256",
        "--expect-replies-sha256",
    ]
    for flag in required_flags:
        assert flag in text

    assert "^[0-9a-f]{64}$" in text
    assert ".expected_hashes.packet" in text
    assert ".expected_hashes.dry_run" in text
    assert ".expected_hashes.subscription_payload" in text
    assert ".expected_hashes.transport_usage" in text
    assert ".expected_hashes.replies" in text


def test_send_nl_no_progress_nudge_guarded_does_not_restart_vpn_runtime() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    forbidden_patterns = [
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+x-ui",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+nginx",
        r"systemctl\s+(restart|reload|try-restart|reload-or-restart)\s+telegram-bot-simple",
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, text) is None


def test_send_nl_no_progress_nudge_guarded_blocks_when_review_not_ready(tmp_path: Path) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    attempt_out = tmp_path / "attempt.json"
    review_cmd.write_text(
        """#!/usr/bin/env bash
cat <<'JSON'
{
  "ready": false,
  "ready_blockers": [],
  "reason": "test review not ready",
  "action": "review_and_send_no_progress_nudge",
  "cooldown_active": false,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": true,
  "transport_restart_relevant": false,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 4,
  "expected_hashes": {}
}
JSON
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
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
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "blocked_by_review_guard"
    assert payload["reason"] == "test review not ready"
    assert payload["review_invariant_blocker_count"] == 0
    assert payload["review_invariant_blockers"] == []


def test_send_nl_no_progress_nudge_guarded_audits_review_failure(tmp_path: Path) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    review_output = "review failed"
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
echo "{review_output}"
exit 6
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "ssh must not be called" >&2
exit 99
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 6
    payload = json.loads(proc.stdout)
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "review_failed"
    assert payload["review_exit_code"] == 6
    assert "review_output" not in payload
    assert payload["review_output_size_bytes"] == len(review_output)
    assert payload["review_output_sha256"] == hashlib.sha256(
        review_output.encode()
    ).hexdigest()


def test_send_nl_no_progress_nudge_guarded_audits_invalid_review_json(tmp_path: Path) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    review_output = "not json"
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
echo "{review_output}"
exit 0
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "ssh must not be called" >&2
exit 99
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 5
    payload = json.loads(proc.stdout)
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "review_output_invalid"
    assert payload["review_exit_code"] == 0
    assert "review_output" not in payload
    assert payload["review_output_size_bytes"] == len(review_output)
    assert payload["review_output_sha256"] == hashlib.sha256(
        review_output.encode()
    ).hexdigest()


def test_send_nl_no_progress_nudge_guarded_blocks_when_review_has_ready_blockers(
    tmp_path: Path,
) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    fake_sha = "d" * 64
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
cat <<'JSON'
{{
  "ready": true,
  "ready_blockers": ["cooldown_active"],
  "reason": "ready flag inconsistent in test",
  "action": "review_and_send_no_progress_nudge",
  "cooldown_active": false,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": true,
  "transport_restart_relevant": false,
  "hash_collection_status": "success",
  "hash_collection_exit_code": 0,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 1,
  "expected_hashes": {{
    "packet": "{fake_sha}",
    "dry_run": "{fake_sha}",
    "subscription_payload": "{fake_sha}",
    "transport_usage": "{fake_sha}",
    "replies": "{fake_sha}"
  }}
}}
JSON
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "ssh must not be called" >&2
exit 99
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    env["CONFIRM_NL_NO_PROGRESS_NUDGE"] = "SEND_NL_NO_PROGRESS_NUDGE"
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
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "blocked_by_review_guard"
    assert payload["reason"] == "review guard reported ready blockers"
    assert payload["ready_blocker_count"] == 1
    assert payload["review"]["ready_blockers"] == ["cooldown_active"]


def test_send_nl_no_progress_nudge_guarded_blocks_inconsistent_ready_review(
    tmp_path: Path,
) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    fake_sha = "e" * 64
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
cat <<'JSON'
{{
  "ready": true,
  "ready_blockers": [],
  "reason": "inconsistent ready review in test",
  "action": "wait_for_nudge_cooldown_and_collect_readonly_evidence",
  "cooldown_active": true,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": false,
  "transport_restart_relevant": false,
  "hash_collection_status": "success",
  "hash_collection_exit_code": 0,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 1,
  "expected_hashes": {{
    "packet": "{fake_sha}",
    "dry_run": "{fake_sha}",
    "subscription_payload": "{fake_sha}",
    "transport_usage": "{fake_sha}",
    "replies": "{fake_sha}"
  }}
}}
JSON
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "ssh must not be called" >&2
exit 99
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    env["CONFIRM_NL_NO_PROGRESS_NUDGE"] = "SEND_NL_NO_PROGRESS_NUDGE"
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
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "blocked_by_review_guard"
    assert payload["reason"] == "review guard send invariants failed"
    assert payload["ready_blocker_count"] == 0
    assert payload["review_invariant_blockers"] == [
        "action_not_review_and_send_no_progress_nudge",
        "user_message_not_allowed_after_review",
        "cooldown_active",
    ]
    assert payload["review_invariant_blocker_count"] == 3


def test_send_nl_no_progress_nudge_guarded_blocks_incomplete_hash_collection(
    tmp_path: Path,
) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    fake_sha = "f" * 64
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
cat <<'JSON'
{{
  "ready": true,
  "ready_blockers": [],
  "reason": "ready but hash collection incomplete in test",
  "action": "review_and_send_no_progress_nudge",
  "cooldown_active": false,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": true,
  "transport_restart_relevant": false,
  "hash_collection_status": "not_required",
  "hash_collection_exit_code": 0,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 1,
  "expected_hashes": {{
    "packet": "{fake_sha}",
    "dry_run": "{fake_sha}",
    "subscription_payload": "{fake_sha}",
    "transport_usage": "{fake_sha}",
    "replies": "{fake_sha}"
  }}
}}
JSON
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "ssh must not be called" >&2
exit 99
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    env["CONFIRM_NL_NO_PROGRESS_NUDGE"] = "SEND_NL_NO_PROGRESS_NUDGE"
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
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "blocked_by_review_guard"
    assert payload["reason"] == "review guard send invariants failed"
    assert payload["review_invariant_blockers"] == ["hash_collection_not_success"]
    assert payload["review_invariant_blocker_count"] == 1


def test_send_nl_no_progress_nudge_guarded_requires_confirmation_before_send(tmp_path: Path) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    attempt_out = tmp_path / "attempt.json"
    fake_sha = "a" * 64
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
cat <<'JSON'
{{
  "ready": true,
  "reason": "ready in test",
  "action": "review_and_send_no_progress_nudge",
  "cooldown_active": false,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": true,
  "transport_restart_relevant": false,
  "hash_collection_status": "success",
  "hash_collection_exit_code": 0,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 1,
  "expected_hashes": {{
    "packet": "{fake_sha}",
    "dry_run": "{fake_sha}",
    "subscription_payload": "{fake_sha}",
    "transport_usage": "{fake_sha}",
    "replies": "{fake_sha}"
  }}
}}
JSON
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    env.pop("CONFIRM_NL_NO_PROGRESS_NUDGE", None)
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "confirmation_required"


def test_send_nl_no_progress_nudge_guarded_audits_remote_send_failure(tmp_path: Path) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    fake_sha = "b" * 64
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
cat <<'JSON'
{{
  "ready": true,
  "reason": "ready in test",
  "action": "review_and_send_no_progress_nudge",
  "cooldown_active": false,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": true,
  "transport_restart_relevant": false,
  "hash_collection_status": "success",
  "hash_collection_exit_code": 0,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 1,
  "expected_hashes": {{
    "packet": "{fake_sha}",
    "dry_run": "{fake_sha}",
    "subscription_payload": "{fake_sha}",
    "transport_usage": "{fake_sha}",
    "replies": "{fake_sha}"
  }}
}}
JSON
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
exit 7
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    env["CONFIRM_NL_NO_PROGRESS_NUDGE"] = "SEND_NL_NO_PROGRESS_NUDGE"
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 7
    payload = json.loads(proc.stdout)
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "send_failed"
    assert payload["send_exit_code"] == 7


def test_send_nl_no_progress_nudge_guarded_audits_invalid_sender_json(tmp_path: Path) -> None:
    review_cmd = tmp_path / "fake_review.sh"
    ssh_cmd = tmp_path / "fake_ssh.sh"
    attempt_out = tmp_path / "attempt.json"
    fake_sha = "c" * 64
    review_cmd.write_text(
        f"""#!/usr/bin/env bash
cat <<'JSON'
{{
  "ready": true,
  "reason": "ready in test",
  "action": "review_and_send_no_progress_nudge",
  "cooldown_active": false,
  "automatic_restart_allowed": false,
  "user_message_allowed_after_review": true,
  "transport_restart_relevant": false,
  "hash_collection_status": "success",
  "hash_collection_exit_code": 0,
  "immediate_readonly_actions": [],
  "no_progress_candidate_count": 1,
  "expected_hashes": {{
    "packet": "{fake_sha}",
    "dry_run": "{fake_sha}",
    "subscription_payload": "{fake_sha}",
    "transport_usage": "{fake_sha}",
    "replies": "{fake_sha}"
  }}
}}
JSON
""",
        encoding="utf-8",
    )
    ssh_cmd.write_text(
        """#!/usr/bin/env bash
echo "not json"
exit 0
""",
        encoding="utf-8",
    )
    review_cmd.chmod(0o755)
    ssh_cmd.chmod(0o755)

    env = os.environ.copy()
    env["REVIEW_CMD"] = str(review_cmd)
    env["SSH_CMD"] = str(ssh_cmd)
    env["LOCAL_ATTEMPT_OUT"] = str(attempt_out)
    env["CONFIRM_NL_NO_PROGRESS_NUDGE"] = "SEND_NL_NO_PROGRESS_NUDGE"
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    assert proc.returncode == 4
    payload = json.loads(proc.stdout)
    saved = json.loads(attempt_out.read_text(encoding="utf-8"))
    assert payload == saved
    assert payload["applied"] is False
    assert payload["status"] == "send_output_invalid"
    assert "send_output" not in payload
    assert payload["send_output_size_bytes"] == len("not json")
    assert payload["send_output_sha256"] == hashlib.sha256(b"not json").hexdigest()
