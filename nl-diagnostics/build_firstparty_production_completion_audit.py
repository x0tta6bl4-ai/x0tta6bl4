#!/usr/bin/env python3
"""Build first-party VPN production completion audit evidence.

This audit is intentionally local-only. It reads a guarded production runbook
and optional post-apply JSON outputs, then decides whether the production VPN
completion claim is proven. It never SSHes, never starts services, and never
executes the runbook commands.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
APPROVAL_PHRASE = "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT"
SERVER_SERVICE = "x0tta-firstparty-vpn.service"
CLIENT_SERVICE = "x0tta-firstparty-vpn-client.service"
REQUIRED_RUNBOOK_COMMAND_IDS = {
    "server_health_post_apply",
    "client_health_post_apply",
    "client_doctor_post_apply",
    "build_completion_audit_after_post_apply",
    "rollback_client_policy_and_service_after_approval",
    "rollback_server_service_after_approval",
}
REQUIRED_RUNBOOK_CHECKS = {
    "post_apply_validation_commands_present",
    "post_apply_evidence_paths_present",
    "post_apply_validation_commands_capture_json",
    "completion_audit_command_present",
    "rollback_commands_present",
    "mutating_commands_have_approval_guard",
    "mutating_x0vpn_commands_have_allow_os_mutation",
    "no_legacy_service_targets_in_commands",
    "runbook_does_not_execute_commands",
    "no_nl_or_spb_writes_performed",
    "os_mutation_not_performed",
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_file_sha256(path: Path | None) -> str:
    if path is None:
        return "missing"
    try:
        return file_sha256(path)
    except OSError:
        return "missing"


def latest_summary(pattern: str, diagnostics_dir: Path = DIAGNOSTICS_DIR) -> Path | None:
    candidates = sorted(diagnostics_dir.glob(pattern))
    return candidates[-1] if candidates else None


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


def command_ids(runbook: dict[str, Any]) -> set[str]:
    rows = runbook.get("commands") if isinstance(runbook.get("commands"), list) else []
    return {str(row.get("id") or "") for row in rows if isinstance(row, dict)}


def command_for(runbook: dict[str, Any], command_id: str) -> str:
    rows = runbook.get("commands") if isinstance(runbook.get("commands"), list) else []
    for row in rows:
        if isinstance(row, dict) and row.get("id") == command_id:
            return str(row.get("command") or "")
    return ""


def path_from_runbook(runbook: dict[str, Any], key: str) -> Path | None:
    paths = (
        runbook.get("post_apply_evidence_paths")
        if isinstance(runbook.get("post_apply_evidence_paths"), dict)
        else {}
    )
    value = paths.get(key)
    return Path(str(value)) if value else None


def required_checks_ok(payload: dict[str, Any]) -> bool:
    checks = payload.get("checks")
    if not isinstance(checks, list):
        return payload.get("ok") is True
    required = [row for row in checks if isinstance(row, dict) and row.get("required", True)]
    return bool(required) and all(row.get("ok") is True for row in required)


def failed_required_checks(payload: dict[str, Any]) -> list[str]:
    checks = payload.get("checks")
    if isinstance(checks, list):
        return [
            str(row.get("name") or "unknown")
            for row in checks
            if isinstance(row, dict)
            and row.get("required", True)
            and row.get("ok") is not True
        ]
    values = payload.get("failed_required_checks")
    return [str(value) for value in values] if isinstance(values, list) else []


def endpoint_matches_runbook(
    *,
    runbook: dict[str, Any],
    server_health: dict[str, Any],
    client_health: dict[str, Any],
    client_doctor: dict[str, Any],
) -> bool:
    endpoint = runbook.get("endpoint") if isinstance(runbook.get("endpoint"), dict) else {}
    expected_host = str(endpoint.get("host") or "")
    expected_port = endpoint.get("port")
    expected_transport = str(endpoint.get("transport") or "")
    server_port_ok = server_health.get("port") == expected_port
    server_transport_ok = str(server_health.get("transport") or "") == expected_transport
    client_port_ok = client_health.get("port") == expected_port or client_doctor.get("port") == expected_port
    client_host_ok = (
        str(client_health.get("host") or "") == expected_host
        or str(client_doctor.get("host") or "") == expected_host
    )
    return (
        bool(expected_host)
        and isinstance(expected_port, int)
        and expected_port > 0
        and bool(expected_transport)
        and server_port_ok
        and server_transport_ok
        and client_port_ok
        and client_host_ok
    )


def service_names_match(
    *,
    runbook: dict[str, Any],
    server_health: dict[str, Any],
    client_health: dict[str, Any],
    client_doctor: dict[str, Any],
) -> bool:
    services = runbook.get("service_names") if isinstance(runbook.get("service_names"), dict) else {}
    server_service = str(services.get("server") or "")
    client_service = str(services.get("client") or "")
    return (
        server_service == SERVER_SERVICE
        and client_service == CLIENT_SERVICE
        and str(server_health.get("service_name") or "") == SERVER_SERVICE
        and (
            str(client_health.get("service_name") or "") == CLIENT_SERVICE
            or str(client_doctor.get("service_name") or "") == CLIENT_SERVICE
        )
    )


def build_payload(
    *,
    runbook_summary_path: Path,
    server_health_path: Path | None = None,
    client_health_path: Path | None = None,
    client_doctor_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    runbook = read_json(runbook_summary_path)
    server_health_path = server_health_path or path_from_runbook(
        runbook,
        "server_health_local_path",
    )
    client_health_path = client_health_path or path_from_runbook(
        runbook,
        "client_health_local_path",
    )
    client_doctor_path = client_doctor_path or path_from_runbook(
        runbook,
        "client_doctor_local_path",
    )
    server_health = read_json(server_health_path)
    client_health = read_json(client_health_path)
    client_doctor = read_json(client_doctor_path)
    runbook_checks = (
        runbook.get("checks") if isinstance(runbook.get("checks"), dict) else {}
    )
    ids = command_ids(runbook)

    runbook_required_checks_ok = all(
        runbook_checks.get(name) is True for name in REQUIRED_RUNBOOK_CHECKS
    )
    runbook_required_commands_present = REQUIRED_RUNBOOK_COMMAND_IDS.issubset(ids)
    runbook_guarded = (
        runbook.get("ok") is True
        and runbook.get("approval_phrase_required") == APPROVAL_PHRASE
        and runbook.get("approval_present") is False
        and runbook.get("production_mutation_allowed") is False
        and runbook.get("manual_approval_still_required") is True
    )
    server_health_present = bool(server_health)
    client_health_present = bool(client_health)
    client_doctor_present = bool(client_doctor)
    server_health_ok = (
        server_health.get("ok") is True
        and server_health.get("mode") == "server-health"
        and required_checks_ok(server_health)
    )
    client_health_ok = (
        client_health.get("ok") is True
        and client_health.get("mode") == "client-health"
        and required_checks_ok(client_health)
    )
    client_doctor_ok = (
        client_doctor.get("ok") is True
        and client_doctor.get("mode") == "client-doctor"
        and client_doctor.get("require_installed_health") is True
        and not failed_required_checks(client_doctor)
    )
    endpoint_ok = endpoint_matches_runbook(
        runbook=runbook,
        server_health=server_health,
        client_health=client_health,
        client_doctor=client_doctor,
    )
    services_ok = service_names_match(
        runbook=runbook,
        server_health=server_health,
        client_health=client_health,
        client_doctor=client_doctor,
    )
    health_no_mutation = all(
        payload.get("os_mutation_performed") is False
        for payload in (server_health, client_health, client_doctor)
        if payload
    )
    completion_evidence_present = (
        server_health_present and client_health_present and client_doctor_present
    )
    checks = {
        "runbook_summary_ok": runbook.get("ok") is True,
        "runbook_approval_guarded": runbook_guarded,
        "runbook_required_checks_ok": runbook_required_checks_ok,
        "runbook_required_commands_present": runbook_required_commands_present,
        "runbook_no_legacy_commands": not runbook.get("legacy_command_findings"),
        "completion_evidence_present": completion_evidence_present,
        "server_health_evidence_present": server_health_present,
        "server_health_ok": server_health_ok,
        "client_health_evidence_present": client_health_present,
        "client_health_ok": client_health_ok,
        "client_doctor_evidence_present": client_doctor_present,
        "client_doctor_ok": client_doctor_ok,
        "client_doctor_requires_installed_health": (
            client_doctor.get("require_installed_health") is True
        ),
        "endpoint_matches_runbook": endpoint_ok,
        "service_names_match": services_ok,
        "post_apply_evidence_no_os_mutation": health_no_mutation,
        "audit_does_not_execute_commands": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    ok = not failed_checks
    completion_decision = (
        "FIRSTPARTY_VPN_PRODUCTION_COMPLETE"
        if ok
        else "FIRSTPARTY_VPN_PRODUCTION_NOT_PROVEN"
    )
    return {
        "mode": "firstparty-production-completion-audit-summary",
        "generated_at": generated_at,
        "ok": ok,
        "completion_decision": completion_decision,
        "goal_completion_claim_allowed": ok,
        "approval_phrase_required": APPROVAL_PHRASE,
        "production_apply_still_required": not ok,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "evidence_paths": {
            "runbook_summary_path": str(runbook_summary_path),
            "server_health_path": str(server_health_path or "missing"),
            "client_health_path": str(client_health_path or "missing"),
            "client_doctor_path": str(client_doctor_path or "missing"),
        },
        "evidence_hashes": {
            "runbook_summary_sha256": safe_file_sha256(runbook_summary_path),
            "server_health_sha256": safe_file_sha256(server_health_path),
            "client_health_sha256": safe_file_sha256(client_health_path),
            "client_doctor_sha256": safe_file_sha256(client_doctor_path),
        },
        "required_operator_evidence_commands": {
            "server_health_post_apply": command_for(runbook, "server_health_post_apply"),
            "client_health_post_apply": command_for(runbook, "client_health_post_apply"),
            "client_doctor_post_apply": command_for(runbook, "client_doctor_post_apply"),
            "build_completion_audit_after_post_apply": command_for(
                runbook,
                "build_completion_audit_after_post_apply",
            ),
        },
        "rollback_commands": {
            "client": command_for(runbook, "rollback_client_policy_and_service_after_approval"),
            "server": command_for(runbook, "rollback_server_service_after_approval"),
        },
        "server_failed_required_checks": failed_required_checks(server_health),
        "client_failed_required_checks": failed_required_checks(client_health),
        "client_doctor_failed_required_checks": failed_required_checks(client_doctor),
        "failed_checks": failed_checks,
        "checks": checks,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Production Completion Audit",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"completion_decision: `{payload['completion_decision']}`",
        f"goal_completion_claim_allowed: `{str(payload['goal_completion_claim_allowed']).lower()}`",
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
    lines.extend(["", "## Required Evidence Commands", ""])
    commands = (
        payload.get("required_operator_evidence_commands")
        if isinstance(payload.get("required_operator_evidence_commands"), dict)
        else {}
    )
    for name in sorted(commands):
        lines.extend(["```bash", str(commands[name]), "```", ""])
    lines.append("This audit did not execute any command and did not write to NL/SPB.")
    return "\n".join(lines) + "\n"


def write_packet(payload: dict[str, Any], *, diagnostics_dir: Path) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-completion-audit-{stamp}"
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
        description="Build first-party VPN production completion audit evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--runbook-summary")
    parser.add_argument("--server-health")
    parser.add_argument("--client-health")
    parser.add_argument("--client-doctor")
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
    payload = build_payload(
        runbook_summary_path=runbook_summary,
        server_health_path=Path(args.server_health) if args.server_health else None,
        client_health_path=Path(args.client_health) if args.client_health else None,
        client_doctor_path=Path(args.client_doctor) if args.client_doctor else None,
    )
    if args.write:
        out_dir = write_packet(payload, diagnostics_dir=diagnostics_dir)
        payload = read_json(out_dir / "summary.json")
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
