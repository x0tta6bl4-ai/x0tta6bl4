#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_MATRIX_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md"
)
DEFAULT_REQUEST_PACKET_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json"
)
DEFAULT_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-reply-2026-06-02.json"
)
DEFAULT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-reply-2026-06-02.md"
)
REFRESH_ARTIFACTS_PATH = "services/nl-server/ghost-access/refresh_client_evidence_artifacts.py"
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"
CURRENT_EVIDENCE_SESSION_STARTED_AT = "2026-06-02T00:00:00Z"
CURRENT_EVIDENCE_REQUIRED_TRANSPORT = "reality"
CURRENT_EVIDENCE_REQUIRED_PORT = 443
DEFAULT_MAX_REQUEST_AGE_HOURS = 24
MAX_REPLY_BYTES = 64

ALLOWED_REPLY_SYMPTOMS = {
    "connected",
    "timeout",
    "import",
    "no-internet",
}
PASS_SYMPTOMS = {"connected"}
FAIL_SYMPTOMS = {"timeout", "import", "no-internet"}

FORBIDDEN_REPLY_PATTERNS = {
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


class RemoteReplyError(ValueError):
    pass


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


def validate_packet_freshness(
    packet: dict[str, Any],
    *,
    max_age_hours: int,
    now: datetime | None = None,
) -> None:
    generated_at = parse_timestamp(packet.get("generated_at"))
    if generated_at is None:
        raise RemoteReplyError("request packet generated_at is missing or invalid")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    age_hours = (current - generated_at).total_seconds() / 3600
    if age_hours < 0:
        raise RemoteReplyError("request packet generated_at is in the future")
    if age_hours > max_age_hours:
        raise RemoteReplyError(
            f"request packet is stale: age_hours={age_hours:.2f}, max_age_hours={max_age_hours}"
        )


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RemoteReplyError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    payload, _source = load_json_with_source(path)
    return payload


def load_json_with_source(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise RemoteReplyError(f"required JSON artifact missing: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise RemoteReplyError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RemoteReplyError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RemoteReplyError(f"{path} must be a JSON object")
    source = {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }
    return payload, source


def validate_expected_sha256(actual_sha256: str, expected_sha256: str) -> None:
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RemoteReplyError("--expect-request-packet-sha256 must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise RemoteReplyError(
            "request packet sha256 mismatch: "
            f"expected={expected}, actual={actual_sha256.lower()}"
        )


def validate_write_requires_sha256(args: argparse.Namespace) -> None:
    if args.write and not str(args.expect_request_packet_sha256 or "").strip():
        raise RemoteReplyError(
            "--expect-request-packet-sha256 is required with --write"
        )


def validate_write_reply_source(args: argparse.Namespace) -> None:
    if args.write and args.reply:
        raise RemoteReplyError(
            "--write requires --reply-stdin or --reply-file; do not persist replies from --reply"
        )


def secret_findings(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            findings.extend(secret_findings(nested, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(secret_findings(nested, path=f"{path}[{index}]"))
        return findings
    if not isinstance(value, str):
        return findings
    for name, pattern in FORBIDDEN_REPLY_PATTERNS.items():
        match = pattern.search(value)
        if match:
            findings.append({"path": path, "kind": name, "sample": match.group(0)[:80]})
    return findings


def parse_reply(reply: str) -> dict[str, str]:
    if len((reply or "").encode("utf-8")) > MAX_REPLY_BYTES:
        raise RemoteReplyError(
            f"reply is too long: max_bytes={MAX_REPLY_BYTES}"
        )
    findings = secret_findings(reply)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise RemoteReplyError(f"unsafe tester reply: {details}")
    tokens = " ".join((reply or "").strip().lower().replace("_", "-").split()).split(" ")
    if len(tokens) != 2:
        raise RemoteReplyError(
            "reply must be exactly one of: pass connected, fail timeout, fail import, fail no-internet"
        )
    result, symptom = tokens
    if result not in {"pass", "fail"}:
        raise RemoteReplyError("reply result must be pass or fail")
    if symptom not in ALLOWED_REPLY_SYMPTOMS:
        raise RemoteReplyError(f"unsupported reply symptom: {symptom!r}")
    if result == "pass" and symptom not in PASS_SYMPTOMS:
        raise RemoteReplyError("pass replies may only use symptom connected")
    if result == "fail" and symptom not in FAIL_SYMPTOMS:
        raise RemoteReplyError("fail replies must use timeout, import, or no-internet")
    return {"result": result, "symptom": symptom}


def read_reply_from_args(args: argparse.Namespace) -> str:
    sources = [
        bool(args.reply),
        args.reply_file is not None,
        bool(args.reply_stdin),
    ]
    if sum(1 for value in sources if value) != 1:
        raise RemoteReplyError("provide exactly one reply source: --reply, --reply-file, or --reply-stdin")
    if args.reply_file is not None:
        try:
            return args.reply_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise RemoteReplyError(f"cannot read reply file: {args.reply_file}") from exc
    if args.reply_stdin:
        return sys.stdin.read()
    return str(args.reply)


def find_request(packet: dict[str, Any], request_id: str) -> dict[str, Any]:
    for request in packet.get("requests") or []:
        if isinstance(request, dict) and request.get("request_id") == request_id:
            return request
    raise RemoteReplyError(f"request_id not found in request packet: {request_id!r}")


def validate_request_contract(request: dict[str, Any]) -> None:
    if request.get("evidence_session_id") != CURRENT_EVIDENCE_SESSION_ID:
        raise RemoteReplyError(
            f"request evidence_session_id must be {CURRENT_EVIDENCE_SESSION_ID}"
        )
    if request.get("evidence_session_started_at") != CURRENT_EVIDENCE_SESSION_STARTED_AT:
        raise RemoteReplyError(
            f"request evidence_session_started_at must be {CURRENT_EVIDENCE_SESSION_STARTED_AT}"
        )
    if request.get("transport") != CURRENT_EVIDENCE_REQUIRED_TRANSPORT:
        raise RemoteReplyError(
            f"request transport must be {CURRENT_EVIDENCE_REQUIRED_TRANSPORT}"
        )
    if request.get("port") != CURRENT_EVIDENCE_REQUIRED_PORT:
        raise RemoteReplyError(f"request port must be {CURRENT_EVIDENCE_REQUIRED_PORT}")


def reporter_label_for(network_type: str) -> str:
    return "workplace-user" if network_type == "work-wifi" else "remote-city-user"


def evidence_source_for(network_type: str) -> str:
    return "support_call_summary" if network_type == "work-wifi" else "remote_user_report"


def safe_request_view(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request.get("request_id"),
        "covers_requirements": request.get("covers_requirements") or [],
        "client": request.get("client"),
        "network_type": request.get("network_type"),
        "transport": request.get("transport"),
        "port": request.get("port"),
        "evidence_session_id": request.get("evidence_session_id"),
        "evidence_session_started_at": request.get("evidence_session_started_at"),
        "minimum_result_to_close_requirements": request.get(
            "minimum_result_to_close_requirements"
        ),
    }


def build_candidate_from_reply(
    *,
    remote_module: Any,
    recorder: Any,
    request: dict[str, Any],
    parsed_reply: dict[str, str],
    checked_at: str,
) -> dict[str, Any]:
    network_type = str(request.get("network_type") or "")
    port_value = request.get("port")
    port = port_value if isinstance(port_value, int) else None
    client = str(request.get("client") or "any")
    if client == "any":
        client = "Happ"
    evidence_session_id = str(request.get("evidence_session_id") or CURRENT_EVIDENCE_SESSION_ID)
    return remote_module.build_candidate(
        recorder=recorder,
        checked_at=checked_at,
        evidence_source=evidence_source_for(network_type),
        reporter_label=reporter_label_for(network_type),
        client=client,
        client_version="unknown",
        network_type=network_type,
        transport=str(request.get("transport") or ""),
        port=port,
        result=parsed_reply["result"],
        symptom=parsed_reply["symptom"],
        evidence_session_id=evidence_session_id,
    )


def build_report(
    *,
    recorder: Any,
    matrix: dict[str, Any],
    request: dict[str, Any],
    parsed_reply: dict[str, str],
    candidate: dict[str, Any],
    matrix_after: dict[str, Any] | None,
    record_matrix: bool,
    wrote_matrix: bool,
    refresh_requested: bool,
    refresh_report: dict[str, Any] | None,
    checked_at: str,
    request_packet_source: dict[str, Any],
) -> dict[str, Any]:
    active_matrix = matrix_after if matrix_after is not None else matrix
    summary = recorder.build_summary(active_matrix)
    if record_matrix and wrote_matrix:
        decision = "REMOTE_CLIENT_EVIDENCE_REPLY_RECORDED"
    elif record_matrix:
        decision = "REMOTE_CLIENT_EVIDENCE_REPLY_DRY_RUN"
    else:
        decision = "REMOTE_CLIENT_EVIDENCE_REPLY_VALIDATED"
    refresh_ran = refresh_report is not None
    refresh_required = bool(wrote_matrix and not refresh_ran)
    report = {
        "reply_id": "nl-anti-block-remote-client-evidence-reply-2026-06-02",
        "generated_at": utc_now(),
        "checked_at": checked_at,
        "decision": decision,
        "source_request_packet": request_packet_source.get("path"),
        "source_request_packet_sha256": request_packet_source.get("sha256"),
        "source_request_packet_size_bytes": request_packet_source.get("size_bytes"),
        "source_matrix": str(DEFAULT_MATRIX_PATH),
        "request": safe_request_view(request),
        "normalized_reply": parsed_reply,
        "candidate": {
            "checked_at": candidate.get("checked_at"),
            "evidence_source": candidate.get("evidence_source"),
            "reporter_label": candidate.get("reporter_label"),
            "client": candidate.get("client"),
            "client_version": candidate.get("client_version"),
            "network_type": candidate.get("network_type"),
            "transport": candidate.get("transport"),
            "port": candidate.get("port"),
            "status": candidate.get("status"),
            "symptom": candidate.get("symptom"),
            "evidence_session_id": candidate.get("evidence_session_id"),
            "evidence_strength": candidate.get("evidence_strength"),
            "raw_secret_material_stored": candidate.get("raw_secret_material_stored"),
            "raw_reporter_identifier_stored": candidate.get("raw_reporter_identifier_stored"),
            "raw_network_identifier_stored": candidate.get("raw_network_identifier_stored"),
        },
        "recording": {
            "attempted": bool(record_matrix),
            "recorded": bool(wrote_matrix),
            "reason": (
                "record_matrix_not_requested"
                if not record_matrix
                else "written"
                if wrote_matrix
                else "dry_run_no_write"
            ),
        },
        "matrix_summary": {
            "decision": summary.get("decision"),
            "completion": summary.get("completion"),
            "missing_requirements": summary.get("missing_requirements"),
            "complete": summary.get("complete"),
            "real_client_checks": summary.get("real_client_checks"),
            "passing_real_client_checks": summary.get("passing_real_client_checks"),
        },
        "artifact_refresh": {
            "requested": bool(refresh_requested),
            "ran": refresh_ran,
            "decision": refresh_report.get("decision") if refresh_ran else None,
            "production_audit_decision": (
                refresh_report.get("production_audit_decision") if refresh_ran else None
            ),
            "production_audit_remaining_count": (
                refresh_report.get("production_audit_remaining_count") if refresh_ran else None
            ),
            "goal_status_decision": (
                refresh_report.get("goal_status_decision") if refresh_ran else None
            ),
            "goal_complete": (
                refresh_report.get("goal_complete") if refresh_ran else None
            ),
            "goal_requirements_passed": (
                refresh_report.get("goal_requirements_passed") if refresh_ran else None
            ),
            "goal_requirements_total": (
                refresh_report.get("goal_requirements_total") if refresh_ran else None
            ),
            "missing_requirements": (
                refresh_report.get("missing_requirements") if refresh_ran else None
            ),
            "privacy_ok": (
                (refresh_report.get("privacy") or {}).get("output_privacy_ok")
                if refresh_ran
                else None
            ),
        },
        "next_steps": {
            "refresh_artifacts_required": refresh_required,
            "refresh_artifacts_command": (
                f"python3 {REFRESH_ARTIFACTS_PATH} --write --json" if refresh_required else None
            ),
            "reason": (
                "matrix_was_updated_refresh_before_production_audit"
                if refresh_required
                else "artifact_refresh_completed"
                if refresh_ran
                else "no_matrix_write_no_refresh_required"
            ),
        },
        "privacy": {
            "output_privacy_ok": True,
            "raw_reply_stored": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_reporter_identifier_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_phone_stored": False,
            "raw_url_stored": False,
            "raw_screenshot_stored": False,
            "raw_logs_stored": False,
        },
    }
    findings = validate_report(report, recorder)
    if findings:
        report["privacy"]["output_privacy_ok"] = False
        report["privacy_findings"] = findings
    return report


def validate_report(report: dict[str, Any], recorder: Any) -> list[dict[str, str]]:
    findings = recorder.check_no_secret_text(report)
    findings.extend(secret_findings(report))
    return findings


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


def render_markdown(report: dict[str, Any]) -> str:
    request = report.get("request") if isinstance(report.get("request"), dict) else {}
    reply = report.get("normalized_reply") if isinstance(report.get("normalized_reply"), dict) else {}
    candidate = report.get("candidate") if isinstance(report.get("candidate"), dict) else {}
    summary = report.get("matrix_summary") if isinstance(report.get("matrix_summary"), dict) else {}
    refresh = report.get("artifact_refresh") if isinstance(report.get("artifact_refresh"), dict) else {}
    next_steps = report.get("next_steps") if isinstance(report.get("next_steps"), dict) else {}
    lines = [
        "# NL Anti-Block Remote Client Evidence Reply - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(report.get('decision'))}`",
        "",
        "This report stores only normalized tester reply metadata. Raw tester text, VPN links, subscription URLs, QR codes, UUIDs, raw IPs, emails, handles, phone numbers, screenshots, and logs are not stored.",
        "",
        "## Request And Reply",
        "",
        "| Request | Covers | Client | Network | Transport | Port | Result | Symptom | Evidence Session |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(request.get("request_id")),
                markdown_cell(request.get("covers_requirements")),
                markdown_cell(candidate.get("client")),
                markdown_cell(candidate.get("network_type")),
                markdown_cell(candidate.get("transport")),
                markdown_cell(candidate.get("port")),
                markdown_cell(reply.get("result")),
                markdown_cell(reply.get("symptom")),
                markdown_cell(candidate.get("evidence_session_id")),
            ]
        )
        + " |",
        "",
        "## Recording",
        "",
        "```json",
        json.dumps(report.get("recording") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Matrix Summary",
        "",
        "```json",
        json.dumps(summary, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Artifact Refresh",
        "",
        "```json",
        json.dumps(refresh, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Next Steps",
        "",
        "```json",
        json.dumps(next_steps, indent=2, ensure_ascii=False),
        "```",
    ]
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_markdown(path: Path, report: dict[str, Any], recorder: Any) -> None:
    findings = validate_report(report, recorder)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise RemoteReplyError(f"refusing to render unsafe remote reply report: {details}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Record a privacy-safe short tester reply for a remote client evidence request."
    )
    p.add_argument("--request-packet", type=Path, default=DEFAULT_REQUEST_PACKET_PATH)
    p.add_argument(
        "--expect-request-packet-sha256",
        default="",
        help="Fail before recording if the request packet SHA-256 does not match this digest.",
    )
    p.add_argument("--request-id", required=True)
    p.add_argument(
        "--max-request-age-hours",
        type=int,
        default=DEFAULT_MAX_REQUEST_AGE_HOURS,
        help="Fail before recording if the request packet generated_at is older than this many hours.",
    )
    p.add_argument("--reply", default="")
    p.add_argument(
        "--reply-file",
        type=Path,
        help="Read the short tester reply from a local file instead of a shell argument.",
    )
    p.add_argument(
        "--reply-stdin",
        action="store_true",
        help="Read the short tester reply from stdin instead of a shell argument.",
    )
    p.add_argument(
        "--checked-at",
        default="",
        help="Optional ISO UTC time; omitted value records current UTC.",
    )
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--matrix-markdown", type=Path, default=DEFAULT_MATRIX_MARKDOWN_PATH)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_PATH)
    p.add_argument("--write", action="store_true")
    p.add_argument("--record-matrix", action="store_true")
    p.add_argument(
        "--refresh-artifacts",
        action="store_true",
        help="After writing matrix evidence, refresh the derived request/audit artifacts locally.",
    )
    p.add_argument("--json", action="store_true")
    return p


def refresh_artifacts(args: argparse.Namespace) -> dict[str, Any]:
    refresh_module = load_module(
        "refresh_client_evidence_artifacts",
        SCRIPT_DIR / "refresh_client_evidence_artifacts.py",
    )
    refresh_args = refresh_module.parser().parse_args(
        [
            "--matrix",
            str(args.matrix),
            "--matrix-markdown",
            str(args.matrix_markdown),
            "--write",
        ]
    )
    try:
        report = refresh_module.refresh(refresh_args)
    except Exception as exc:
        if exc.__class__.__name__ == "RefreshError":
            raise RemoteReplyError(f"artifact refresh failed: {exc}") from exc
        raise
    if (report.get("privacy") or {}).get("output_privacy_ok") is not True:
        raise RemoteReplyError("artifact refresh failed privacy validation")
    return report


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    remote = load_module("record_remote_client_evidence", SCRIPT_DIR / "record_remote_client_evidence.py")
    recorder = remote.load_recorder()
    try:
        packet, request_packet_source = load_json_with_source(args.request_packet)
        validate_expected_sha256(
            str(request_packet_source.get("sha256") or ""),
            args.expect_request_packet_sha256,
        )
        validate_packet_freshness(packet, max_age_hours=args.max_request_age_hours)
        request = find_request(packet, args.request_id)
        validate_request_contract(request)
        parsed = parse_reply(read_reply_from_args(args))
        checked_at = args.checked_at or utc_now()
        validate_write_requires_sha256(args)
        validate_write_reply_source(args)
        matrix = remote.load_matrix(args.matrix)
        candidate = build_candidate_from_reply(
            remote_module=remote,
            recorder=recorder,
            request=request,
            parsed_reply=parsed,
            checked_at=checked_at,
        )
        matrix_after = None
        wrote_matrix = False
        refresh_report = None
        if args.record_matrix:
            matrix_after = recorder.add_or_update_check(matrix, candidate)
            if args.write:
                recorder.write_matrix(args.matrix, matrix_after)
                recorder.write_markdown(args.matrix_markdown, matrix_after)
                wrote_matrix = True
        if args.refresh_artifacts:
            if not wrote_matrix:
                raise RemoteReplyError(
                    "--refresh-artifacts requires --write and --record-matrix"
                )
            refresh_report = refresh_artifacts(args)
        report = build_report(
            recorder=recorder,
            matrix=matrix,
            request=request,
            parsed_reply=parsed,
            candidate=candidate,
            matrix_after=matrix_after,
            record_matrix=args.record_matrix,
            wrote_matrix=wrote_matrix,
            refresh_requested=args.refresh_artifacts,
            refresh_report=refresh_report,
            checked_at=checked_at,
            request_packet_source=request_packet_source,
        )
        findings = validate_report(report, recorder)
        if findings:
            details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
            raise RemoteReplyError(f"unsafe remote reply report: {details}")
        if args.write:
            write_json(args.json_out, report)
            write_markdown(args.markdown_out, report, recorder)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"ok=true decision={report['decision']} "
                f"matrix_updated={str(report['recording']['recorded']).lower()}"
            )
        return 0
    except RemoteReplyError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
