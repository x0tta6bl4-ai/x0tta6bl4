#!/usr/bin/env python3
"""Build guarded operator scripts for first-party VPN production apply.

The generated scripts are local artifacts. This builder never executes the
runbook commands. The apply script defaults to dry-run and excludes rollback;
the rollback script is separate and has the same explicit execution guard.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
LEGACY_MARKERS = (
    "x-ui",
    "xray",
    "ghost-access",
    "vless",
    "vmess",
    "trojan",
    "shadowsocks",
    "wireguard",
    "openvpn",
    "hiddify",
    "happ",
    "warp",
)
APPLY_EXCLUDED_PHASES = {"rollback"}
REQUIRED_APPLY_COMMAND_IDS = {
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
REQUIRED_ROLLBACK_COMMAND_IDS = {
    "rollback_client_policy_and_service_after_approval",
    "rollback_server_service_after_approval",
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


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


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mode_executable_not_group_world_writable(mode: str) -> bool:
    try:
        value = int(mode, 8)
    except ValueError:
        return False
    return bool(value & 0o100) and not bool(value & 0o022)


def q(value: object) -> str:
    return shlex.quote(str(value))


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


def command_rows(runbook: dict[str, Any]) -> list[dict[str, Any]]:
    rows = runbook.get("commands")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def command_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("id") or "") for row in rows}


def legacy_marker_findings(rows: list[dict[str, Any]]) -> list[str]:
    findings: list[str] = []
    for row in rows:
        text = str(row.get("command") or "").lower()
        row_id = str(row.get("id") or "unknown")
        for marker in LEGACY_MARKERS:
            if marker in text:
                findings.append(f"{row_id}:{marker}")
    return findings


def bash_syntax_ok(text: str) -> bool:
    completed = subprocess.run(
        ["bash", "-n", "-c", text],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def commands_syntax_ok(rows: list[dict[str, Any]]) -> bool:
    return all(bash_syntax_ok(str(row.get("command") or "")) for row in rows)


def mutating_commands_guarded(rows: list[dict[str, Any]]) -> bool:
    mutating = [row for row in rows if row.get("mutation") is True]
    return bool(mutating) and all(
        row.get("approval_required") is True
        and APPROVAL_PHRASE in str(row.get("command") or "")
        and 'test "$APPROVAL"' in str(row.get("command") or "")
        for row in mutating
    )


def render_shell_script(
    *,
    title: str,
    script_role: str,
    transcript_prefix: str,
    runbook_summary_path: Path,
    runbook_sha256: str,
    transcript_dir: Path,
    rows: list[dict[str, Any]],
) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f"# {title}",
        "# Generated locally. Default mode is dry-run; no production command runs",
        "# unless EXECUTE=1, DRY_RUN=0, and APPROVAL has the exact approval phrase.",
        f"RUNBOOK_SUMMARY={q(runbook_summary_path)}",
        f"RUNBOOK_SHA256={q(runbook_sha256)}",
        f"APPROVAL_PHRASE={q(APPROVAL_PHRASE)}",
        'DRY_RUN="${DRY_RUN:-1}"',
        'EXECUTE="${EXECUTE:-0}"',
        'APPROVAL="${APPROVAL:-}"',
        f"SCRIPT_ROLE={q(script_role)}",
        f"TRANSCRIPT_DIR={q(transcript_dir)}",
        'mkdir -p "$TRANSCRIPT_DIR"',
        f'TRANSCRIPT="${{TRANSCRIPT:-$TRANSCRIPT_DIR/{transcript_prefix}-$(date -u +%Y%m%dT%H%M%SZ).jsonl}}"',
        "",
        'current_sha="$(sha256sum "$RUNBOOK_SUMMARY" | awk \'{print $1}\')"',
        'if [[ "$current_sha" != "$RUNBOOK_SHA256" ]]; then',
        '  echo "runbook hash mismatch: $current_sha != $RUNBOOK_SHA256" >&2',
        "  exit 40",
        "fi",
        "",
        'if [[ "$EXECUTE" == "1" || "$DRY_RUN" == "0" ]]; then',
        '  if [[ "$EXECUTE" != "1" || "$DRY_RUN" != "0" ]]; then',
        '    echo "execution requires both EXECUTE=1 and DRY_RUN=0" >&2',
        "    exit 41",
        "  fi",
        '  if [[ "$APPROVAL" != "$APPROVAL_PHRASE" ]]; then',
        '    echo "execution requires APPROVAL=$APPROVAL_PHRASE" >&2',
        "    exit 42",
        "  fi",
        "else",
        '  echo "dry-run only: set EXECUTE=1 DRY_RUN=0 and APPROVAL=$APPROVAL_PHRASE to run"',
        "fi",
        "",
        'SCRIPT_SHA256="$(sha256sum "$0" | awk \'{print $1}\')"',
        'APPROVAL_OK="false"',
        'if [[ "$APPROVAL" == "$APPROVAL_PHRASE" ]]; then APPROVAL_OK="true"; fi',
        'EXECUTE_OK="false"',
        'if [[ "$EXECUTE" == "1" ]]; then EXECUTE_OK="true"; fi',
        'DRY_RUN_OK="false"',
        'if [[ "$DRY_RUN" == "1" ]]; then DRY_RUN_OK="true"; fi',
        'printf \'{"ts":"%s","event":"meta","script_role":"%s","execute":%s,"dry_run":%s,"approval_ok":%s,"runbook_sha256":"%s","script_sha256":"%s"}\\n\' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SCRIPT_ROLE" "$EXECUTE_OK" "$DRY_RUN_OK" "$APPROVAL_OK" "$RUNBOOK_SHA256" "$SCRIPT_SHA256" >> "$TRANSCRIPT"',
        "",
        "log_event() {",
        '  local event="$1"',
        '  local step_id="$2"',
        '  local rc="${3:-0}"',
        '  printf \'{"ts":"%s","event":"%s","step_id":"%s","rc":%s}\\n\' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$event" "$step_id" "$rc" >> "$TRANSCRIPT"',
        "}",
        "",
        "run_step() {",
        '  local step_id="$1"',
        '  local mutation="$2"',
        '  local command="$3"',
        '  echo "==> $step_id"',
        '  log_event "start" "$step_id" 0',
        '  if [[ "$EXECUTE" != "1" || "$DRY_RUN" != "0" ]]; then',
        '    printf \'[dry-run] %s\\n\' "$command"',
        '    log_event "dry_run" "$step_id" 0',
        "    return 0",
        "  fi",
        '  if [[ "$mutation" == "true" && "$APPROVAL" != "$APPROVAL_PHRASE" ]]; then',
        '    echo "mutating step blocked without approval: $step_id" >&2',
        "    exit 43",
        "  fi",
        "  set +e",
        '  export APPROVAL',
        '  bash -o pipefail -c "$command"',
        "  local rc=$?",
        "  set -e",
        '  log_event "finish" "$step_id" "$rc"',
        '  if [[ "$rc" -ne 0 ]]; then',
        '    echo "step failed: $step_id rc=$rc" >&2',
        '    exit "$rc"',
        "  fi",
        "}",
        "",
    ]
    for row in rows:
        row_id = str(row.get("id") or "unknown")
        mutation = "true" if row.get("mutation") is True else "false"
        command = str(row.get("command") or "")
        lines.append(f"run_step {q(row_id)} {q(mutation)} {q(command)}")
    lines.append("")
    lines.append('echo "transcript: $TRANSCRIPT"')
    return "\n".join(lines) + "\n"


def build_payload(
    *,
    runbook_summary_path: Path,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    runbook = read_json(runbook_summary_path)
    rows = command_rows(runbook)
    ids = command_ids(rows)
    apply_rows = [
        row
        for row in rows
        if str(row.get("phase") or "") not in APPLY_EXCLUDED_PHASES
    ]
    rollback_rows = [
        row for row in rows if str(row.get("phase") or "") == "rollback"
    ]
    runbook_sha = safe_file_sha256(runbook_summary_path)
    transcript_dir = (
        DIAGNOSTICS_DIR
        / "firstparty-production-operator-transcripts"
        / generated_at.replace("-", "").replace(":", "").replace("Z", "Z")
    )
    apply_script_text = render_shell_script(
        title="First-party VPN production apply",
        script_role="apply",
        transcript_prefix="apply-execution",
        runbook_summary_path=runbook_summary_path,
        runbook_sha256=runbook_sha,
        transcript_dir=transcript_dir,
        rows=apply_rows,
    )
    rollback_script_text = render_shell_script(
        title="First-party VPN production rollback",
        script_role="rollback",
        transcript_prefix="rollback-execution",
        runbook_summary_path=runbook_summary_path,
        runbook_sha256=runbook_sha,
        transcript_dir=transcript_dir,
        rows=rollback_rows,
    )
    runbook_checks = (
        runbook.get("checks") if isinstance(runbook.get("checks"), dict) else {}
    )
    legacy_findings = list(runbook.get("legacy_command_findings") or [])
    legacy_findings.extend(legacy_marker_findings(rows))
    apply_ids = command_ids(apply_rows)
    rollback_ids = command_ids(rollback_rows)
    checks = {
        "runbook_summary_ok": runbook.get("ok") is True,
        "runbook_hash_present": len(runbook_sha) == 64 and runbook_sha != "missing",
        "runbook_approval_guarded": (
            runbook.get("approval_phrase_required") == APPROVAL_PHRASE
            and runbook.get("approval_present") is False
            and runbook.get("production_mutation_allowed") is False
            and runbook.get("manual_approval_still_required") is True
        ),
        "runbook_no_mutation": (
            runbook.get("os_mutation_performed") is False
            and runbook.get("no_nl_or_spb_writes_performed") is True
            and runbook_checks.get("runbook_does_not_execute_commands") is True
        ),
        "required_apply_commands_present": REQUIRED_APPLY_COMMAND_IDS.issubset(apply_ids),
        "required_rollback_commands_present": REQUIRED_ROLLBACK_COMMAND_IDS.issubset(rollback_ids),
        "apply_script_excludes_rollback": not (REQUIRED_ROLLBACK_COMMAND_IDS & apply_ids),
        "rollback_script_contains_only_rollback": (
            bool(rollback_rows)
            and rollback_ids.issubset(REQUIRED_ROLLBACK_COMMAND_IDS)
            and len(rollback_rows) == len(rollback_ids)
        ),
        "mutating_commands_guarded": mutating_commands_guarded(rows),
        "commands_syntax_ok": commands_syntax_ok(rows),
        "apply_script_syntax_ok": bash_syntax_ok(apply_script_text),
        "rollback_script_syntax_ok": bash_syntax_ok(rollback_script_text),
        "scripts_default_dry_run": (
            'DRY_RUN="${DRY_RUN:-1}"' in apply_script_text
            and 'EXECUTE="${EXECUTE:-0}"' in apply_script_text
            and 'DRY_RUN="${DRY_RUN:-1}"' in rollback_script_text
            and 'EXECUTE="${EXECUTE:-0}"' in rollback_script_text
        ),
        "scripts_require_approval_to_execute": (
            APPROVAL_PHRASE in apply_script_text
            and APPROVAL_PHRASE in rollback_script_text
            and "execution requires APPROVAL=" in apply_script_text
            and "execution requires APPROVAL=" in rollback_script_text
        ),
        "scripts_hash_bound_to_runbook": (
            runbook_sha in apply_script_text and runbook_sha in rollback_script_text
        ),
        "scripts_log_self_hash_meta": (
            '"event":"meta"' in apply_script_text
            and '"event":"meta"' in rollback_script_text
            and "SCRIPT_SHA256=" in apply_script_text
            and "SCRIPT_SHA256=" in rollback_script_text
            and "script_sha256" in apply_script_text
            and "script_sha256" in rollback_script_text
            and "runbook_sha256" in apply_script_text
            and "runbook_sha256" in rollback_script_text
            and "SCRIPT_ROLE=apply" in apply_script_text
            and "SCRIPT_ROLE=rollback" in rollback_script_text
        ),
        "no_legacy_commands": not legacy_findings,
        "operator_builder_does_not_execute_commands": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    return {
        "mode": "firstparty-production-operator-script-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "approval_phrase_required": APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "runbook_summary_path": str(runbook_summary_path),
        "runbook_summary_sha256": runbook_sha,
        "apply_command_ids": [str(row.get("id") or "") for row in apply_rows],
        "rollback_command_ids": [str(row.get("id") or "") for row in rollback_rows],
        "apply_command_count": len(apply_rows),
        "rollback_command_count": len(rollback_rows),
        "mutating_command_count": sum(1 for row in rows if row.get("mutation") is True),
        "transcript_dir": str(transcript_dir),
        "script_hashes": {
            "apply_script_sha256": text_sha256(apply_script_text),
            "rollback_script_sha256": text_sha256(rollback_script_text),
        },
        "script_paths": {
            "apply": "not_written",
            "rollback": "not_written",
        },
        "legacy_command_findings": sorted(set(str(value) for value in legacy_findings)),
        "failed_checks": failed_checks,
        "checks": checks,
        "apply_script_text": apply_script_text,
        "rollback_script_text": rollback_script_text,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Production Operator Scripts",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"approval_phrase_required: `{payload['approval_phrase_required']}`",
        f"runbook_summary_sha256: `{payload['runbook_summary_sha256']}`",
        "",
        "## Scripts",
        "",
    ]
    paths = payload.get("script_paths") if isinstance(payload.get("script_paths"), dict) else {}
    for name in sorted(paths):
        lines.append(f"- {name}: `{paths[name]}`")
    lines.extend(["", "## Checks", "", "| Check | Passed |", "|---|---|"])
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
            "The generated scripts default to dry-run. They require EXECUTE=1, DRY_RUN=0, and the explicit approval phrase before any command is executed.",
            "This builder did not execute any command and did not write to NL/SPB.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-operator-script-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    apply_script = out_dir / "apply-firstparty-production.sh"
    rollback_script = out_dir / "rollback-firstparty-production.sh"
    apply_script.write_text(str(payload["apply_script_text"]), encoding="utf-8")
    rollback_script.write_text(str(payload["rollback_script_text"]), encoding="utf-8")
    apply_script.chmod(0o700)
    rollback_script.chmod(0o700)

    payload = {
        key: value
        for key, value in payload.items()
        if key not in {"apply_script_text", "rollback_script_text"}
    }
    payload["evidence_dir"] = str(out_dir)
    payload["script_paths"] = {
        "apply": str(apply_script),
        "rollback": str(rollback_script),
    }
    payload["script_file_modes"] = {
        "apply": f"{apply_script.stat().st_mode & 0o777:04o}",
        "rollback": f"{rollback_script.stat().st_mode & 0o777:04o}",
    }
    payload["script_file_hashes"] = {
        "apply_script_sha256": file_sha256(apply_script),
        "rollback_script_sha256": file_sha256(rollback_script),
    }
    payload["checks"] = dict(payload.get("checks") or {})
    payload["checks"]["script_files_written_executable_not_group_world_writable"] = (
        mode_executable_not_group_world_writable(payload["script_file_modes"]["apply"])
        and mode_executable_not_group_world_writable(payload["script_file_modes"]["rollback"])
    )
    payload["checks"]["script_file_hashes_match_preview"] = (
        payload["script_file_hashes"] == payload["script_hashes"]
    )
    payload["failed_checks"] = sorted(
        name for name, passed in payload["checks"].items() if passed is not True
    )
    payload["ok"] = not payload["failed_checks"]
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build guarded first-party VPN production operator scripts"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--runbook-summary")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    diagnostics_dir = Path(args.diagnostics_dir)
    runbook_summary = (
        Path(args.runbook_summary)
        if args.runbook_summary
        else latest_summary("firstparty-production-apply-runbook-*/summary.json", diagnostics_dir)
    )
    if runbook_summary is None:
        raise SystemExit("first-party production apply runbook summary is missing")
    payload = build_payload(runbook_summary_path=runbook_summary)
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload = read_json(out_dir / "summary.json")
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
