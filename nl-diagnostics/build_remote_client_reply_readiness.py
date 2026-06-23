#!/usr/bin/env python3
"""Build a local readiness packet for remote client evidence replies.

The report reads local artifacts only. It does not record tester replies, does
not update the client matrix, and does not contact NL/SPB.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_REQUEST_PACKET = DIAGNOSTICS_DIR / "nl-anti-block-remote-client-evidence-request-2026-06-02.json"
DEFAULT_GOAL_STATUS = DIAGNOSTICS_DIR / "vpn-production-candidate-goal-2026-06-02.json"
DEFAULT_REPLY_RECORDER = ROOT / "services" / "nl-server" / "ghost-access" / "record_remote_client_evidence_reply.py"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "nl-anti-block-remote-client-reply-readiness-2026-06-06.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "nl-anti-block-remote-client-reply-readiness-2026-06-06.md"

PASS = "pass"
MISSING = "missing"
BLOCKED_EXTERNAL = "blocked_external_reply"
MAX_REQUEST_AGE_HOURS = 24
REQUIRED_MISSING_REQUIREMENTS = {
    "android_happ_or_hiddify",
    "mobile_network",
    "restricted_or_work_wifi",
}
REQUIRED_SAFE_REPLY_OPTIONS = {
    "pass connected",
    "fail timeout",
    "fail import",
    "fail no-internet",
}
FORBIDDEN_TEXT_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
    "http_url": re.compile(r"\bhttps?://", re.IGNORECASE),
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def read_json_with_source(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError:
        return {}, {"path": str(path), "sha256": "", "size_bytes": 0}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        }
    return (
        payload if isinstance(payload, dict) else {},
        {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size_bytes": len(raw),
        },
    )


def read_json(path: Path) -> dict[str, Any]:
    payload, _source = read_json_with_source(path)
    return payload


def make_gate(gate_id: str, title: str, status: str, evidence: list[str], next_step: str) -> dict[str, Any]:
    return {
        "id": gate_id,
        "title": title,
        "status": status,
        "ok": status in {PASS, BLOCKED_EXTERNAL},
        "evidence": evidence,
        "next_step": next_step,
    }


def age_hours(generated_at: Any, *, now: datetime | None = None) -> float | None:
    parsed = parse_timestamp(generated_at)
    if parsed is None:
        return None
    current = (now or datetime.now(UTC)).astimezone(UTC)
    return (current - parsed).total_seconds() / 3600


def privacy_findings(payload: Any, *, path: str = "$") -> list[dict[str, str]]:
    if isinstance(payload, dict):
        findings: list[dict[str, str]] = []
        for key, value in payload.items():
            findings.extend(privacy_findings(value, path=f"{path}.{key}"))
        return findings
    if isinstance(payload, list):
        findings = []
        for index, value in enumerate(payload):
            findings.extend(privacy_findings(value, path=f"{path}[{index}]"))
        return findings
    if not isinstance(payload, str):
        return []
    findings = []
    for name, pattern in FORBIDDEN_TEXT_PATTERNS.items():
        if pattern.search(payload):
            findings.append({"path": path, "kind": name})
    return findings


def request_freshness_gate(packet: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    age = age_hours(packet.get("generated_at"), now=now)
    fresh = age is not None and 0 <= age <= MAX_REQUEST_AGE_HOURS
    return make_gate(
        "REQUEST-FRESHNESS-01",
        "Remote request packet is fresh enough for reply intake",
        PASS if fresh else MISSING,
        [
            f"generated_at={packet.get('generated_at') or 'missing'}",
            f"age_hours={'missing' if age is None else f'{age:.2f}'}",
            f"max_age_hours={MAX_REQUEST_AGE_HOURS}",
        ],
        "refresh nl-anti-block-remote-client-evidence-request before recording delayed replies",
    )


def request_contract_gate(packet: dict[str, Any]) -> dict[str, Any]:
    requests = [row for row in packet.get("requests") or [] if isinstance(row, dict)]
    missing = set(str(item) for item in packet.get("missing_requirements") or [])
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), dict) else {}
    ready = (
        packet.get("decision") == "REMOTE_CLIENT_EVIDENCE_REQUEST_READY"
        and REQUIRED_MISSING_REQUIREMENTS.issubset(missing)
        and packet.get("minimum_reports_required") == len(requests)
        and packet.get("request_count") == len(requests)
        and len(requests) == 2
        and privacy.get("output_privacy_ok") is True
        and not packet.get("privacy_findings")
    )
    return make_gate(
        "REQUEST-CONTRACT-01",
        "Request packet covers the remaining real-client evidence",
        PASS if ready else MISSING,
        [
            f"decision={packet.get('decision') or 'missing'}",
            f"missing_requirements={','.join(sorted(missing)) or 'missing'}",
            f"minimum_reports_required={packet.get('minimum_reports_required')}",
            f"request_count={packet.get('request_count')}",
            f"privacy_ok={str(privacy.get('output_privacy_ok') is True).lower()}",
        ],
        "regenerate the remote client evidence request from the current matrix",
    )


def command_has_hash_guard(command: str) -> bool:
    return "--expect-request-packet-sha256" in command and "sha256sum" in command


def command_uses_stdin(command: str) -> bool:
    return "record_remote_client_evidence_reply.py" in command and "--reply-stdin" in command and "--reply " not in command


def request_commands_gate(packet: dict[str, Any]) -> dict[str, Any]:
    requests = [row for row in packet.get("requests") or [] if isinstance(row, dict)]
    issues: list[str] = []
    for row in requests:
        request_id = str(row.get("request_id") or "missing")
        safe_options = set(str(value) for value in row.get("safe_reply_options") or [])
        record_pass = str(row.get("operator_reply_record_pass_command") or "")
        record_fail = str(row.get("operator_reply_record_fail_command") or "")
        validate_pass = str(row.get("operator_reply_validate_pass_command") or "")
        validate_fail = str(row.get("operator_reply_validate_fail_command") or "")
        direct_pass = str(row.get("operator_record_pass_command") or "")
        direct_fail = str(row.get("operator_record_fail_command") or "")
        if direct_pass or direct_fail:
            issues.append(f"{request_id}:direct_record_command_present")
        for name, command in {
            "record_pass": record_pass,
            "record_fail": record_fail,
        }.items():
            if not command_uses_stdin(command):
                issues.append(f"{request_id}:{name}:not_stdin")
            if not command_has_hash_guard(command):
                issues.append(f"{request_id}:{name}:missing_hash_guard")
            if "--write" not in command or "--record-matrix" not in command or "--refresh-artifacts" not in command:
                issues.append(f"{request_id}:{name}:missing_write_refresh_scope")
        for name, command in {
            "validate_pass": validate_pass,
            "validate_fail": validate_fail,
        }.items():
            if not command_uses_stdin(command):
                issues.append(f"{request_id}:{name}:not_stdin")
            if not command_has_hash_guard(command):
                issues.append(f"{request_id}:{name}:missing_hash_guard")
            if "--write" in command or "--record-matrix" in command:
                issues.append(f"{request_id}:{name}:validate_writes")
        if not REQUIRED_SAFE_REPLY_OPTIONS.issubset(safe_options):
            issues.append(f"{request_id}:missing_safe_reply_options")
    findings = privacy_findings(packet)
    ready = bool(requests) and not issues and not findings
    evidence = [
        f"request_ids={','.join(str(row.get('request_id') or 'missing') for row in requests) or 'missing'}",
        f"issues={','.join(issues) if issues else 'none'}",
        f"privacy_findings={','.join(item['kind'] for item in findings) if findings else 'none'}",
    ]
    return make_gate(
        "REQUEST-COMMANDS-01",
        "Reply commands are stdin-only, hash-bound, and validate without writing",
        PASS if ready else MISSING,
        evidence,
        "regenerate request commands with reply recorder, packet hash guard, and non-writing validate commands",
    )


def reply_recorder_gate(script_text: str, script_path: Path) -> dict[str, Any]:
    markers = {
        "script_present": bool(script_text),
        "write_requires_sha": "validate_write_requires_sha256" in script_text
        and "--expect-request-packet-sha256 is required with --write" in script_text,
        "write_rejects_inline_reply": "validate_write_reply_source" in script_text
        and "--write requires --reply-stdin or --reply-file" in script_text,
        "freshness_guard": "DEFAULT_MAX_REQUEST_AGE_HOURS = 24" in script_text
        and "validate_packet_freshness" in script_text,
        "short_reply_limit": "MAX_REPLY_BYTES = 64" in script_text,
        "secret_patterns": "FORBIDDEN_REPLY_PATTERNS" in script_text
        and "unsafe tester reply" in script_text,
        "refresh_requires_write_matrix": "--refresh-artifacts requires --write and --record-matrix" in script_text,
        "raw_reply_not_stored": '"raw_reply_stored": False' in script_text,
    }
    ready = all(markers.values())
    return make_gate(
        "REPLY-RECORDER-01",
        "Reply recorder blocks stale, unbound, inline, and secret-bearing writes",
        PASS if ready else MISSING,
        [
            f"script_path={script_path}",
            *[f"{key}={str(value).lower()}" for key, value in markers.items()],
        ],
        "fix record_remote_client_evidence_reply.py guards before accepting tester replies",
    )


def goal_gate(goal_status: dict[str, Any]) -> dict[str, Any]:
    antiblock = next(
        (
            row
            for row in goal_status.get("requirements") or []
            if isinstance(row, dict) and row.get("id") == "ANTIBLOCK-CLIENTS-01"
        ),
        {},
    )
    evidence = [str(item) for item in antiblock.get("evidence") or []]
    evidence_text = "\n".join(evidence)
    ready = (
        goal_status.get("decision") == "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE"
        and antiblock.get("status") == "blocked_external_evidence"
        and "remote_request_decision=REMOTE_CLIENT_EVIDENCE_REQUEST_READY" in evidence_text
        and "remote_request_count=2" in evidence_text
        and "remote_request_record_commands_use_stdin=true" in evidence_text
        and "remote_request_reply_commands_hash_guard_ok=true" in evidence_text
        and "remote_request_reply_dry_run_uses_packet_hash=true" in evidence_text
    )
    return make_gate(
        "GOAL-ANTIBLOCK-01",
        "Goal gate points ANTIBLOCK to external reply intake, not server work",
        PASS if ready else MISSING,
        [
            f"goal_decision={goal_status.get('decision') or 'missing'}",
            f"antiblock_status={antiblock.get('status') or 'missing'}",
            f"reply_hash_guard={str('remote_request_reply_commands_hash_guard_ok=true' in evidence_text).lower()}",
            f"reply_dry_run_hash={str('remote_request_reply_dry_run_uses_packet_hash=true' in evidence_text).lower()}",
        ],
        "rebuild vpn goal status after refreshing remote request artifacts",
    )


def external_reply_gate(packet: dict[str, Any]) -> dict[str, Any]:
    requests = [row for row in packet.get("requests") or [] if isinstance(row, dict)]
    request_ids = [str(row.get("request_id") or "missing") for row in requests]
    covers = sorted(
        {
            str(requirement)
            for row in requests
            for requirement in (row.get("covers_requirements") or [])
        }
    )
    return make_gate(
        "EXTERNAL-REPLIES-01",
        "Actual tester replies are still required",
        BLOCKED_EXTERNAL,
        [
            f"request_ids={','.join(request_ids) or 'missing'}",
            f"covers_requirements={','.join(covers) or 'missing'}",
            "accepted_replies=pass connected, fail timeout, fail import, fail no-internet",
            "raw_tester_text_stored=false",
        ],
        "send request messages to testers and record only their short reply through --reply-stdin",
    )


def build_payload(
    *,
    request_packet: dict[str, Any],
    request_source: dict[str, Any],
    goal_status: dict[str, Any],
    reply_recorder_text: str,
    reply_recorder_path: Path = DEFAULT_REPLY_RECORDER,
    now: datetime | None = None,
) -> dict[str, Any]:
    gates = [
        request_freshness_gate(request_packet, now=now),
        request_contract_gate(request_packet),
        request_commands_gate(request_packet),
        reply_recorder_gate(reply_recorder_text, reply_recorder_path),
        goal_gate(goal_status),
        external_reply_gate(request_packet),
    ]
    technical_ready = all(row["status"] == PASS for row in gates if row["id"] != "EXTERNAL-REPLIES-01")
    waiting_for_replies = gates[-1]["status"] == BLOCKED_EXTERNAL
    ready_for_safe_intake = technical_ready and waiting_for_replies
    requests = [row for row in request_packet.get("requests") or [] if isinstance(row, dict)]
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_remote_client_reply_readiness.py",
        "generated_at": utc_now(),
        "decision": (
            "REMOTE_CLIENT_REPLIES_READY_FOR_SAFE_INTAKE"
            if ready_for_safe_intake
            else "REMOTE_CLIENT_REPLIES_NOT_READY"
        ),
        "ready_for_safe_intake": ready_for_safe_intake,
        "server_write_allowed": False,
        "local_matrix_write_allowed_after_safe_reply": ready_for_safe_intake,
        "reply_recording_performed": False,
        "source_request_packet": request_source,
        "minimum_reports_required": request_packet.get("minimum_reports_required"),
        "request_count": request_packet.get("request_count"),
        "requests": [
            {
                "request_id": row.get("request_id"),
                "covers_requirements": row.get("covers_requirements") or [],
                "tester_message": row.get("tester_message"),
                "validate_pass_command": row.get("operator_reply_validate_pass_command"),
                "record_pass_command": row.get("operator_reply_record_pass_command"),
                "validate_fail_command": row.get("operator_reply_validate_fail_command"),
                "record_fail_command": row.get("operator_reply_record_fail_command"),
                "safe_reply_options": row.get("safe_reply_options") or [],
            }
            for row in requests
        ],
        "gates": gates,
        "privacy": {
            "output_privacy_ok": not privacy_findings(request_packet),
            "raw_reply_stored": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_reporter_identifier_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_phone_stored": False,
            "raw_screenshot_stored": False,
            "raw_logs_stored": False,
        },
        "no_nl_or_spb_writes_performed": True,
    }


def markdown_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, (list, tuple)):
        text = ", ".join(markdown_cell(item) for item in value)
    elif isinstance(value, dict):
        text = ", ".join(f"{key}={markdown_cell(nested)}" for key, nested in value.items())
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# NL Anti-Block Remote Client Reply Readiness",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"decision: `{payload['decision']}`",
        f"ready_for_safe_intake: `{str(payload['ready_for_safe_intake']).lower()}`",
        f"server_write_allowed: `{str(payload['server_write_allowed']).lower()}`",
        f"reply_recording_performed: `{str(payload['reply_recording_performed']).lower()}`",
        "",
        "## Gates",
        "",
        "| ID | Status | OK | Next Step |",
        "|---|---:|---:|---|",
    ]
    for gate in payload["gates"]:
        lines.append(
            f"| `{gate['id']}` | `{gate['status']}` | `{str(gate['ok']).lower()}` | {gate['next_step']} |"
        )
    lines.extend(["", "## Requests", ""])
    for request in payload["requests"]:
        lines.extend(
            [
                f"### {markdown_cell(request.get('request_id'))}",
                "",
                "Tester message:",
                "",
                "```text",
                str(request.get("tester_message") or ""),
                "```",
                "",
                "Validate pass without writing:",
                "",
                "```bash",
                str(request.get("validate_pass_command") or ""),
                "```",
                "",
                "Record pass after a safe reply:",
                "",
                "```bash",
                str(request.get("record_pass_command") or ""),
                "```",
                "",
            ]
        )
    lines.extend(["No NL or SPB writes were performed by this readiness report.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build remote client reply readiness packet")
    parser.add_argument("--request-packet", default=str(DEFAULT_REQUEST_PACKET))
    parser.add_argument("--goal-status", default=str(DEFAULT_GOAL_STATUS))
    parser.add_argument("--reply-recorder", default=str(DEFAULT_REPLY_RECORDER))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    request_packet, request_source = read_json_with_source(Path(args.request_packet))
    payload = build_payload(
        request_packet=request_packet,
        request_source=request_source,
        goal_status=read_json(Path(args.goal_status)),
        reply_recorder_text=read_text(Path(args.reply_recorder)),
        reply_recorder_path=Path(args.reply_recorder),
    )
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ready_for_safe_intake"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
