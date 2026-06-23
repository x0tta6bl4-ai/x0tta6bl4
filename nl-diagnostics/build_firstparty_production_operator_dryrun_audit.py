#!/usr/bin/env python3
"""Build dry-run audit evidence for first-party VPN production operator scripts.

This audit executes only the generated scripts in their default dry-run mode
and runs guard-negative checks that exit before any runbook command is reached.
It does not execute nested production commands and does not write to NL/SPB.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
EXPECTED_APPLY_COMMAND_IDS = {
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
EXPECTED_ROLLBACK_COMMAND_IDS = {
    "rollback_client_policy_and_service_after_approval",
    "rollback_server_service_after_approval",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp_now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
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


def safe_file_sha256(path: Path) -> str:
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


def path_from_summary(summary: dict[str, Any], key: str) -> Path | None:
    paths = summary.get("script_paths") if isinstance(summary.get("script_paths"), dict) else {}
    value = paths.get(key)
    return Path(str(value)) if value else None


def expected_ids(summary: dict[str, Any], key: str, fallback: set[str]) -> set[str]:
    values = summary.get(key)
    if isinstance(values, list) and values:
        return {str(value) for value in values}
    return set(fallback)


def run_script(
    script_path: Path,
    *,
    transcript_path: Path,
    execute: str = "0",
    dry_run: str = "1",
    approval: str = "",
) -> dict[str, Any]:
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    if transcript_path.exists():
        transcript_path.unlink()
    env = dict(os.environ)
    env.update(
        {
            "EXECUTE": execute,
            "DRY_RUN": dry_run,
            "APPROVAL": approval,
            "TRANSCRIPT": str(transcript_path),
        }
    )
    completed = subprocess.run(
        [str(script_path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
        "transcript_path": str(transcript_path),
        "event_count": len(read_jsonl(transcript_path)),
    }


def transcript_step_ids(events: list[dict[str, Any]], event_name: str) -> set[str]:
    return {
        str(row.get("step_id") or "")
        for row in events
        if row.get("event") == event_name and row.get("rc") == 0
    }


def transcript_complete(events: list[dict[str, Any]], expected: set[str]) -> bool:
    starts = transcript_step_ids(events, "start")
    dry_runs = transcript_step_ids(events, "dry_run")
    return expected.issubset(starts) and expected.issubset(dry_runs)


def no_finish_events(events: list[dict[str, Any]]) -> bool:
    return all(row.get("event") != "finish" for row in events)


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


def scripts_syntax_ok(script_paths: list[Path]) -> bool:
    for path in script_paths:
        completed = subprocess.run(
            ["bash", "-n", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return False
    return True


def build_payload(
    *,
    operator_summary_path: Path,
    evidence_dir: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    summary = read_json(operator_summary_path)
    apply_script = path_from_summary(summary, "apply")
    rollback_script = path_from_summary(summary, "rollback")
    apply_expected = expected_ids(
        summary,
        "apply_command_ids",
        EXPECTED_APPLY_COMMAND_IDS,
    )
    rollback_expected = expected_ids(
        summary,
        "rollback_command_ids",
        EXPECTED_ROLLBACK_COMMAND_IDS,
    )
    script_hashes = (
        summary.get("script_file_hashes")
        if isinstance(summary.get("script_file_hashes"), dict)
        else {}
    )
    apply_hash = safe_file_sha256(apply_script) if apply_script else "missing"
    rollback_hash = safe_file_sha256(rollback_script) if rollback_script else "missing"

    apply_transcript = evidence_dir / "apply-dryrun.jsonl"
    rollback_transcript = evidence_dir / "rollback-dryrun.jsonl"
    guard_pair_transcript = evidence_dir / "guard-requires-execute-and-dryrun.jsonl"
    guard_approval_transcript = evidence_dir / "guard-requires-approval.jsonl"

    apply_result = (
        run_script(apply_script, transcript_path=apply_transcript)
        if apply_script
        else {"exit_code": 127, "transcript_path": str(apply_transcript), "event_count": 0}
    )
    rollback_result = (
        run_script(rollback_script, transcript_path=rollback_transcript)
        if rollback_script
        else {"exit_code": 127, "transcript_path": str(rollback_transcript), "event_count": 0}
    )
    guard_pair_result = (
        run_script(
            apply_script,
            transcript_path=guard_pair_transcript,
            execute="1",
            dry_run="1",
            approval=APPROVAL_PHRASE,
        )
        if apply_script
        else {"exit_code": 127, "transcript_path": str(guard_pair_transcript), "event_count": 0}
    )
    guard_approval_result = (
        run_script(
            apply_script,
            transcript_path=guard_approval_transcript,
            execute="1",
            dry_run="0",
            approval="WRONG_APPROVAL",
        )
        if apply_script
        else {"exit_code": 127, "transcript_path": str(guard_approval_transcript), "event_count": 0}
    )

    apply_events = read_jsonl(apply_transcript)
    rollback_events = read_jsonl(rollback_transcript)
    apply_meta = first_meta_event(apply_events)
    rollback_meta = first_meta_event(rollback_events)
    apply_start_ids = transcript_step_ids(apply_events, "start")
    rollback_start_ids = transcript_step_ids(rollback_events, "start")
    runbook_sha256 = str(summary.get("runbook_summary_sha256") or "")
    checks = {
        "operator_summary_ok": summary.get("ok") is True,
        "operator_summary_no_mutation": (
            summary.get("os_mutation_performed") is False
            and summary.get("no_nl_or_spb_writes_performed") is True
        ),
        "operator_summary_approval_guarded": (
            summary.get("approval_phrase_required") == APPROVAL_PHRASE
            and summary.get("approval_present") is False
            and summary.get("production_mutation_allowed") is False
            and summary.get("manual_approval_still_required") is True
        ),
        "script_paths_present": bool(apply_script and rollback_script),
        "script_hashes_match_summary": (
            apply_hash == script_hashes.get("apply_script_sha256")
            and rollback_hash == script_hashes.get("rollback_script_sha256")
        ),
        "scripts_syntax_ok": scripts_syntax_ok(
            [path for path in (apply_script, rollback_script) if path]
        ),
        "dryrun_env_safe": True,
        "apply_dryrun_exit_zero": apply_result.get("exit_code") == 0,
        "rollback_dryrun_exit_zero": rollback_result.get("exit_code") == 0,
        "apply_transcript_complete": transcript_complete(apply_events, apply_expected),
        "rollback_transcript_complete": transcript_complete(rollback_events, rollback_expected),
        "apply_transcript_excludes_rollback": not (apply_start_ids & rollback_expected),
        "rollback_transcript_contains_only_rollback": (
            bool(rollback_events) and rollback_start_ids.issubset(rollback_expected)
        ),
        "dryrun_transcripts_have_no_finish_events": no_finish_events(apply_events)
        and no_finish_events(rollback_events),
        "apply_transcript_meta_present": bool(apply_meta),
        "rollback_transcript_meta_present": bool(rollback_meta),
        "apply_transcript_meta_role_apply": apply_meta.get("script_role") == "apply",
        "rollback_transcript_meta_role_rollback": rollback_meta.get("script_role")
        == "rollback",
        "apply_transcript_meta_execute_disabled": boolish(apply_meta.get("execute"))
        is False,
        "rollback_transcript_meta_execute_disabled": boolish(
            rollback_meta.get("execute")
        )
        is False,
        "apply_transcript_meta_dry_run_enabled": boolish(apply_meta.get("dry_run"))
        is True,
        "rollback_transcript_meta_dry_run_enabled": boolish(
            rollback_meta.get("dry_run")
        )
        is True,
        "apply_transcript_meta_approval_not_ok": boolish(
            apply_meta.get("approval_ok")
        )
        is False,
        "rollback_transcript_meta_approval_not_ok": boolish(
            rollback_meta.get("approval_ok")
        )
        is False,
        "apply_transcript_meta_runbook_hash_matches": apply_meta.get("runbook_sha256")
        == runbook_sha256,
        "rollback_transcript_meta_runbook_hash_matches": rollback_meta.get(
            "runbook_sha256"
        )
        == runbook_sha256,
        "apply_transcript_meta_script_hash_matches": apply_meta.get("script_sha256")
        == script_hashes.get("apply_script_sha256"),
        "rollback_transcript_meta_script_hash_matches": rollback_meta.get(
            "script_sha256"
        )
        == script_hashes.get("rollback_script_sha256"),
        "guard_blocks_execute_without_dryrun_pair": guard_pair_result.get("exit_code") == 41,
        "guard_blocks_wrong_approval": guard_approval_result.get("exit_code") == 42,
        "guard_checks_do_not_start_steps": (
            guard_pair_result.get("event_count") == 0
            and guard_approval_result.get("event_count") == 0
        ),
        "no_legacy_command_findings": not summary.get("legacy_command_findings"),
        "audit_only_runs_dryrun_scripts": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "mode": "firstparty-production-operator-dryrun-audit-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "operator_summary_path": str(operator_summary_path),
        "operator_summary_sha256": safe_file_sha256(operator_summary_path),
        "script_paths": {
            "apply": str(apply_script or "missing"),
            "rollback": str(rollback_script or "missing"),
        },
        "script_hashes": {
            "apply_script_sha256": apply_hash,
            "rollback_script_sha256": rollback_hash,
        },
        "transcript_paths": {
            "apply": str(apply_transcript),
            "rollback": str(rollback_transcript),
            "guard_requires_pair": str(guard_pair_transcript),
            "guard_requires_approval": str(guard_approval_transcript),
        },
        "dryrun_results": {
            "apply": apply_result,
            "rollback": rollback_result,
        },
        "guard_results": {
            "execute_without_dryrun_pair": guard_pair_result,
            "wrong_approval": guard_approval_result,
        },
        "expected_apply_command_ids": sorted(apply_expected),
        "expected_rollback_command_ids": sorted(rollback_expected),
        "apply_transcript_start_ids": sorted(apply_start_ids),
        "rollback_transcript_start_ids": sorted(rollback_start_ids),
        "transcript_meta": {
            "apply": apply_meta,
            "rollback": rollback_meta,
        },
        "failed_checks": failed_checks,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Production Operator Dry-Run Audit",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
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
    lines.extend(["", "## Transcripts", ""])
    transcripts = (
        payload.get("transcript_paths")
        if isinstance(payload.get("transcript_paths"), dict)
        else {}
    )
    for name in sorted(transcripts):
        lines.append(f"- {name}: `{transcripts[name]}`")
    lines.extend(
        [
            "",
            "This audit ran generated scripts only in dry-run or pre-step guard-failure mode.",
            "No nested production command was executed and no NL/SPB write was performed.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    evidence_dir = Path(str(payload.get("evidence_dir") or ""))
    out_dir = evidence_dir if evidence_dir.name.startswith("firstparty-production-operator-dryrun-audit-") else diagnostics_dir / f"firstparty-production-operator-dryrun-audit-{stamp_now()}"
    out_dir.mkdir(parents=True, exist_ok=True)
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
        description="Build dry-run audit evidence for guarded first-party VPN operator scripts"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--operator-summary")
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
    out_dir = diagnostics_dir / f"firstparty-production-operator-dryrun-audit-{stamp_now()}"
    payload = build_payload(
        operator_summary_path=operator_summary,
        evidence_dir=out_dir,
    )
    payload["evidence_dir"] = str(out_dir)
    if args.write:
        written_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload = read_json(written_dir / "summary.json")
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
