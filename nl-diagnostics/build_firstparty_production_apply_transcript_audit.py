#!/usr/bin/env python3
"""Build first-party VPN production apply transcript audit evidence.

This audit is local-only. It verifies an already-collected operator apply
transcript from the generated guarded apply script. It never runs the apply
script and never writes to NL/SPB.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
FALLBACK_APPLY_COMMAND_IDS = {
    "verify_authorization_summary_hash",
    "verify_apply_packet_hash",
    "verify_handoff_summary_hash",
    "verify_handoff_archive_hash_and_mode",
    "verify_handoff_manifest_hash_and_mode",
    "verify_nl_port_still_free_readonly",
    "copy_handoff_to_nl_after_approval",
    "install_server_service_after_approval",
    "server_health_post_apply",
    "apply_client_config_after_approval",
    "client_health_post_apply",
    "client_doctor_post_apply",
    "build_completion_audit_after_post_apply",
}
FALLBACK_ROLLBACK_COMMAND_IDS = {
    "rollback_client_policy_and_service_after_approval",
    "rollback_server_service_after_approval",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def latest_summary(pattern: str, diagnostics_dir: Path = DIAGNOSTICS_DIR) -> Path | None:
    candidates = sorted(diagnostics_dir.glob(pattern))
    return candidates[-1] if candidates else None


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file_sha256(path: Path | None) -> str:
    if path is None:
        return "missing"
    try:
        return file_sha256(path)
    except OSError:
        return "missing"


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "missing"
    return str(value)


def compact(values: list[str], *, limit: int = 8) -> str:
    if not values:
        return "none"
    head = values[:limit]
    if len(values) > limit:
        head.append(f"...+{len(values) - limit}")
    return ", ".join(head)


def path_from_operator_summary(summary: dict[str, Any], key: str) -> Path | None:
    paths = summary.get("script_paths") if isinstance(summary.get("script_paths"), dict) else {}
    value = paths.get(key)
    return Path(str(value)) if value else None


def hash_from_operator_summary(summary: dict[str, Any], key: str) -> str:
    hashes = (
        summary.get("script_file_hashes")
        if isinstance(summary.get("script_file_hashes"), dict)
        else {}
    )
    value = hashes.get(key)
    return str(value) if isinstance(value, str) else ""


def expected_ids(summary: dict[str, Any], key: str, fallback: set[str]) -> set[str]:
    values = summary.get(key)
    if isinstance(values, list) and values:
        return {str(value) for value in values}
    return set(fallback)


def latest_apply_transcript_from_summary(summary: dict[str, Any]) -> Path | None:
    transcript_dir = summary.get("transcript_dir")
    if not transcript_dir:
        return None
    candidates = sorted(Path(str(transcript_dir)).glob("apply-execution-*.jsonl"))
    return candidates[-1] if candidates else None


def script_syntax_ok(path: Path | None) -> bool:
    if path is None or not path.exists():
        return False
    completed = subprocess.run(
        ["bash", "-n", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def transcript_ids(events: list[dict[str, Any]], event_name: str) -> set[str]:
    return {
        str(row.get("step_id") or "")
        for row in events
        if row.get("event") == event_name
    }


def finish_ids_rc0(events: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("step_id") or "")
        for row in events
        if row.get("event") == "finish" and row.get("rc") == 0
    }


def failed_finish_rows(events: list[dict[str, Any]]) -> list[str]:
    return [
        f"{row.get('step_id')}:rc={row.get('rc')}"
        for row in events
        if row.get("event") == "finish" and row.get("rc") != 0
    ]


def first_meta_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    for row in events:
        if row.get("event") == "meta":
            return row
    return {}


def boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes"}:
            return True
        if normalized in {"0", "false", "no"}:
            return False
    return None


def build_payload(
    *,
    operator_summary_path: Path,
    apply_transcript_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    summary = read_json(operator_summary_path)
    apply_script = path_from_operator_summary(summary, "apply")
    rollback_script = path_from_operator_summary(summary, "rollback")
    apply_transcript_path = apply_transcript_path or latest_apply_transcript_from_summary(summary)
    events = read_jsonl(apply_transcript_path)
    apply_expected = expected_ids(summary, "apply_command_ids", FALLBACK_APPLY_COMMAND_IDS)
    rollback_expected = expected_ids(summary, "rollback_command_ids", FALLBACK_ROLLBACK_COMMAND_IDS)
    starts = transcript_ids(events, "start")
    finishes = finish_ids_rc0(events)
    dry_runs = transcript_ids(events, "dry_run")
    apply_meta = first_meta_event(events)
    runbook_sha256 = str(summary.get("runbook_summary_sha256") or "")
    all_step_ids = {
        str(row.get("step_id") or "")
        for row in events
        if isinstance(row.get("step_id"), str)
    }
    rollback_ids_in_transcript = sorted(all_step_ids & rollback_expected)
    failed_finishes = failed_finish_rows(events)
    apply_script_hash = safe_file_sha256(apply_script)
    rollback_script_hash = safe_file_sha256(rollback_script)

    checks = {
        "operator_summary_ok": summary.get("ok") is True,
        "operator_summary_approval_guarded": (
            summary.get("approval_phrase_required") == APPROVAL_PHRASE
            and summary.get("approval_present") is False
            and summary.get("production_mutation_allowed") is False
            and summary.get("manual_approval_still_required") is True
        ),
        "operator_summary_no_mutation": (
            summary.get("os_mutation_performed") is False
            and summary.get("no_nl_or_spb_writes_performed") is True
        ),
        "apply_script_path_present": apply_script is not None and apply_script.exists(),
        "rollback_script_path_present": rollback_script is not None and rollback_script.exists(),
        "apply_script_hash_matches_summary": apply_script_hash
        == hash_from_operator_summary(summary, "apply_script_sha256"),
        "rollback_script_hash_matches_summary": rollback_script_hash
        == hash_from_operator_summary(summary, "rollback_script_sha256"),
        "apply_script_syntax_ok": script_syntax_ok(apply_script),
        "rollback_script_syntax_ok": script_syntax_ok(rollback_script),
        "apply_transcript_present": bool(apply_transcript_path and apply_transcript_path.exists()),
        "apply_transcript_nonempty": bool(events),
        "apply_transcript_all_expected_starts_present": apply_expected.issubset(starts),
        "apply_transcript_all_expected_finishes_rc0": apply_expected.issubset(finishes),
        "apply_transcript_no_dry_run_events": not dry_runs,
        "apply_transcript_excludes_rollback_steps": not rollback_ids_in_transcript,
        "apply_transcript_no_failed_finishes": not failed_finishes,
        "apply_transcript_has_only_expected_apply_steps": all_step_ids.issubset(apply_expected),
        "apply_transcript_meta_present": bool(apply_meta),
        "apply_transcript_meta_role_apply": apply_meta.get("script_role") == "apply",
        "apply_transcript_meta_execute_enabled": boolish(apply_meta.get("execute"))
        is True,
        "apply_transcript_meta_dry_run_disabled": boolish(apply_meta.get("dry_run"))
        is False,
        "apply_transcript_meta_approval_ok": boolish(apply_meta.get("approval_ok"))
        is True,
        "apply_transcript_meta_runbook_hash_matches": apply_meta.get("runbook_sha256")
        == runbook_sha256,
        "apply_transcript_meta_script_hash_matches": apply_meta.get("script_sha256")
        == hash_from_operator_summary(summary, "apply_script_sha256"),
        "audit_does_not_execute_commands": True,
        "os_mutation_not_performed_by_audit": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    ok = not failed_checks
    return {
        "mode": "firstparty-production-apply-transcript-audit-summary",
        "generated_at": generated_at,
        "ok": ok,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "apply_execution_proven": ok,
        "operator_summary_path": str(operator_summary_path),
        "operator_summary_sha256": safe_file_sha256(operator_summary_path),
        "apply_transcript_path": str(apply_transcript_path or "missing"),
        "apply_transcript_sha256": safe_file_sha256(apply_transcript_path),
        "script_paths": {
            "apply": str(apply_script or "missing"),
            "rollback": str(rollback_script or "missing"),
        },
        "script_hashes": {
            "apply_script_sha256": apply_script_hash,
            "rollback_script_sha256": rollback_script_hash,
        },
        "expected_apply_command_ids": sorted(apply_expected),
        "expected_rollback_command_ids": sorted(rollback_expected),
        "transcript_start_ids": sorted(starts),
        "transcript_finish_rc0_ids": sorted(finishes),
        "transcript_dry_run_ids": sorted(dry_runs),
        "rollback_ids_in_transcript": rollback_ids_in_transcript,
        "failed_finish_rows": failed_finishes,
        "transcript_meta": apply_meta,
        "failed_checks": failed_checks,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Production Apply Transcript Audit",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"apply_execution_proven: `{str(payload['apply_execution_proven']).lower()}`",
        f"approval_phrase_required: `{payload['approval_phrase_required']}`",
        "",
        "## Checks",
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    for name in sorted(checks):
        lines.append(f"| `{name}` | `{bool_text(checks[name])}` |")
    lines.extend(["", "## Failed Checks", ""])
    failed = payload.get("failed_checks") if isinstance(payload.get("failed_checks"), list) else []
    if failed:
        lines.extend(f"- {value}" for value in failed)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            f"apply_transcript: `{payload.get('apply_transcript_path', 'missing')}`",
            "",
            "This audit did not execute the apply script and did not write to NL/SPB.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-apply-transcript-audit-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = dict(payload)
    payload["evidence_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build first-party VPN production apply transcript audit evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--operator-summary")
    parser.add_argument("--apply-transcript")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    operator_summary = (
        Path(args.operator_summary)
        if args.operator_summary
        else latest_summary("firstparty-production-operator-script-*/summary.json", diagnostics_dir)
    )
    if operator_summary is None:
        raise SystemExit("first-party production operator script summary is missing")
    payload = build_payload(
        operator_summary_path=operator_summary,
        apply_transcript_path=Path(args.apply_transcript) if args.apply_transcript else None,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload = read_json(out_dir / "summary.json")
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
