#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any


DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_MATRIX_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md"
)
DEFAULT_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-intake-2026-06-02.json"
)
DEFAULT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-intake-2026-06-02.md"
)
RECORDER_PATH = Path(__file__).with_name("record_client_compatibility.py")
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"

ALLOWED_EVIDENCE_SOURCES = {
    "remote_user_report",
    "operator_screen_share",
    "support_call_summary",
    "adb_probe_summary",
}
ALLOWED_REPORTER_LABELS = {
    "operator",
    "friend",
    "remote-city-user",
    "workplace-user",
    "unknown",
}

EXTRA_FORBIDDEN_PATTERNS = {
    "http_url": re.compile(r"\bhttps?://", re.IGNORECASE),
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


class RemoteEvidenceError(ValueError):
    pass


def load_recorder() -> Any:
    spec = importlib.util.spec_from_file_location("record_client_compatibility", RECORDER_PATH)
    if spec is None or spec.loader is None:
        raise RemoteEvidenceError(f"cannot load recorder module: {RECORDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_enum(value: str, *, allowed: set[str], field: str) -> str:
    text = (value or "").strip().lower().replace("_", "-")
    text = text.replace("screen-share", "screen_share")
    if field == "evidence_source":
        text = text.replace("-", "_")
    if text not in allowed:
        raise RemoteEvidenceError(f"unsupported {field}: {value!r}")
    return text


def normalize_safe_text(value: str, *, default: str) -> str:
    text = " ".join((value or "").strip().split())
    return text or default


def extra_secret_findings(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            findings.extend(extra_secret_findings(nested, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(extra_secret_findings(nested, path=f"{path}[{index}]"))
        return findings
    if not isinstance(value, str):
        return findings
    for name, pattern in EXTRA_FORBIDDEN_PATTERNS.items():
        if pattern.search(value):
            findings.append({"path": path, "kind": name})
    return findings


def validate_safe_payload(payload: dict[str, Any], recorder: Any) -> list[dict[str, str]]:
    findings = recorder.check_no_secret_text(payload)
    findings.extend(extra_secret_findings(payload))
    return findings


def load_matrix(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RemoteEvidenceError(f"matrix not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RemoteEvidenceError(f"matrix is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise RemoteEvidenceError("matrix must be a JSON object")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_safe_command_template() -> str:
    return (
        "python3 services/nl-server/ghost-access/record_remote_client_evidence.py "
        "--write --record-matrix "
        "--evidence-source remote_user_report "
        "--reporter-label remote-city-user "
        '--client "Happ" '
        "--client-version unknown "
        "--network-type mobile "
        "--transport reality "
        "--port 443 "
        "--result <pass|fail> "
        '--symptom "<short result, no secrets>" '
        f"--evidence-session-id {CURRENT_EVIDENCE_SESSION_ID} "
        "--json"
    )


def validate_remote_candidate_contract(row: dict[str, Any], recorder: Any) -> None:
    try:
        network_type = recorder.normalize_network_type(str(row.get("network_type") or "unknown"))
    except Exception as exc:
        if exc.__class__.__name__ == "CompatibilityError":
            raise RemoteEvidenceError(str(exc)) from exc
        raise
    session_bound_networks = set(getattr(recorder, "SESSION_BOUND_NETWORK_TYPES", set()))
    if network_type not in session_bound_networks:
        return

    expected_session_id = getattr(recorder, "CURRENT_EVIDENCE_SESSION_ID", "")
    expected_started_at = getattr(recorder, "CURRENT_EVIDENCE_SESSION_STARTED_AT", "")
    expected_transport = getattr(recorder, "CURRENT_EVIDENCE_REQUIRED_TRANSPORT", "")
    expected_port = getattr(recorder, "CURRENT_EVIDENCE_REQUIRED_PORT", None)

    if row.get("evidence_session_id") != expected_session_id:
        raise RemoteEvidenceError(
            f"session-bound remote evidence must use evidence_session_id={expected_session_id}"
        )
    if not recorder.checked_at_in_current_session(str(row.get("checked_at") or "")):
        raise RemoteEvidenceError(
            f"session-bound remote evidence must be checked at or after {expected_started_at}"
        )
    if row.get("transport") != expected_transport:
        raise RemoteEvidenceError(
            f"session-bound remote evidence must use transport={expected_transport}"
        )
    if row.get("port") != expected_port:
        raise RemoteEvidenceError(f"session-bound remote evidence must use port={expected_port}")


def build_candidate(
    *,
    recorder: Any,
    checked_at: str,
    evidence_source: str,
    reporter_label: str,
    client: str,
    client_version: str,
    network_type: str,
    transport: str,
    port: int | None,
    result: str,
    symptom: str,
    evidence_session_id: str = CURRENT_EVIDENCE_SESSION_ID,
) -> dict[str, Any]:
    source = normalize_enum(
        evidence_source, allowed=ALLOWED_EVIDENCE_SOURCES, field="evidence_source"
    )
    reporter = normalize_enum(
        reporter_label, allowed=ALLOWED_REPORTER_LABELS, field="reporter_label"
    )
    try:
        row = recorder.build_check_row(
            checked_at=checked_at,
            client=client,
            client_version=client_version,
            network_type=network_type,
            transport=transport,
            port=port,
            result=result,
            symptom=symptom,
            evidence_session_id=evidence_session_id,
        )
    except Exception as exc:
        if exc.__class__.__name__ == "CompatibilityError":
            raise RemoteEvidenceError(str(exc)) from exc
        raise
    validate_remote_candidate_contract(row, recorder)
    row.update(
        {
            "evidence_source": source,
            "reporter_label": reporter,
            "evidence_strength": (
                "remote_runtime_report"
                if source in {"remote_user_report", "operator_screen_share", "support_call_summary"}
                else "local_tool_summary"
            ),
            "raw_reporter_identifier_stored": False,
            "raw_network_identifier_stored": False,
            "remote_evidence_intake_version": 1,
            "symptom": normalize_safe_text(str(row.get("symptom") or ""), default="none"),
        }
    )
    findings = validate_safe_payload(row, recorder)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise RemoteEvidenceError(f"unsafe remote client evidence: {details}")
    return row


def candidate_args_present(args: argparse.Namespace) -> bool:
    fields = (
        args.checked_at,
        args.evidence_source,
        args.reporter_label,
        args.client,
        args.network_type,
        args.transport,
        args.result,
        args.symptom,
    )
    return any(str(value or "").strip() for value in fields) or args.port is not None


def safe_candidate_view(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
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
    }


def build_report(
    *,
    recorder: Any,
    matrix: dict[str, Any],
    candidate: dict[str, Any] | None,
    matrix_after: dict[str, Any] | None,
    record_matrix: bool,
    wrote_matrix: bool,
    generated_at: str | None = None,
) -> dict[str, Any]:
    active_matrix = matrix_after if matrix_after is not None else matrix
    summary = recorder.build_summary(active_matrix)
    if candidate is None:
        decision = "REMOTE_CLIENT_EVIDENCE_INTAKE_READY"
    elif record_matrix and wrote_matrix:
        decision = "REMOTE_CLIENT_EVIDENCE_RECORDED"
    elif record_matrix:
        decision = "REMOTE_CLIENT_EVIDENCE_DRY_RUN"
    else:
        decision = "REMOTE_CLIENT_EVIDENCE_VALIDATED"
    report = {
        "intake_id": "nl-anti-block-remote-client-evidence-intake-2026-06-02",
        "generated_at": generated_at or utc_now(),
        "decision": decision,
        "source_matrix": str(DEFAULT_MATRIX_PATH),
        "matrix_updated": bool(wrote_matrix),
        "candidate": safe_candidate_view(candidate),
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
        "safe_remote_record_command_template": build_safe_command_template(),
        "privacy": {
            "output_privacy_ok": True,
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
        },
    }
    findings = validate_safe_payload(report, recorder)
    if findings:
        report["privacy"]["output_privacy_ok"] = False
        report["privacy_findings"] = findings
    return report


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
    candidate = report.get("candidate") if isinstance(report.get("candidate"), dict) else {}
    summary = report.get("matrix_summary") if isinstance(report.get("matrix_summary"), dict) else {}
    completion = summary.get("completion") if isinstance(summary.get("completion"), dict) else {}
    lines = [
        "# NL Anti-Block Remote Client Evidence Intake - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(report.get('decision'))}`",
        "",
        "This file stores only privacy-safe remote client evidence metadata. Do not store VPN links, subscription URLs, UUIDs, raw IPs, emails, Telegram handles, phone numbers, QR codes, or screenshots.",
        "",
        "## Matrix Summary",
        "",
        "| Complete | Missing Requirements | Real Checks | Passing Checks |",
        "| --- | --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(summary.get("complete")),
                markdown_cell(summary.get("missing_requirements")),
                markdown_cell(summary.get("real_client_checks")),
                markdown_cell(summary.get("passing_real_client_checks")),
            ]
        )
        + " |",
        "",
        "| Requirement | Proven |",
        "| --- | --- |",
        f"| desktop_v2rayn | {markdown_cell(completion.get('desktop_v2rayn'))} |",
        f"| android_happ_or_hiddify | {markdown_cell(completion.get('android_happ_or_hiddify'))} |",
        f"| mobile_network | {markdown_cell(completion.get('mobile_network'))} |",
        f"| restricted_or_work_wifi | {markdown_cell(completion.get('restricted_or_work_wifi'))} |",
        "",
        "## Latest Candidate",
        "",
        "| Source | Reporter Label | Client | Network | Transport | Port | Status | Symptom |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if candidate:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(candidate.get("evidence_source")),
                    markdown_cell(candidate.get("reporter_label")),
                    markdown_cell(candidate.get("client")),
                    markdown_cell(candidate.get("network_type")),
                    markdown_cell(candidate.get("transport")),
                    markdown_cell(candidate.get("port")),
                    markdown_cell(candidate.get("status")),
                    markdown_cell(candidate.get("symptom")),
                ]
            )
            + " |"
        )
    else:
        lines.append("| none |  |  |  |  |  |  |  |")
    lines.extend(
        [
            "",
            "## Safe Remote Record Command",
            "",
            "```bash",
            str(report.get("safe_remote_record_command_template") or ""),
            "```",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, report: dict[str, Any], recorder: Any) -> None:
    findings = validate_safe_payload(report, recorder)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise RemoteEvidenceError(f"refusing to render unsafe remote evidence report: {details}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Record privacy-safe remote NL client evidence.")
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--matrix-markdown", type=Path, default=DEFAULT_MATRIX_MARKDOWN_PATH)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_PATH)
    p.add_argument("--write", action="store_true", help="write report and requested matrix updates")
    p.add_argument("--record-matrix", action="store_true", help="add this result to the matrix")
    p.add_argument("--json", action="store_true", help="print JSON report")
    p.add_argument("--checked-at", default="")
    p.add_argument("--evidence-source", default="")
    p.add_argument("--reporter-label", default="")
    p.add_argument("--client", default="")
    p.add_argument("--client-version", default="unknown")
    p.add_argument("--network-type", default="")
    p.add_argument("--transport", default="")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--result", default="")
    p.add_argument("--symptom", default="")
    p.add_argument("--evidence-session-id", default=CURRENT_EVIDENCE_SESSION_ID)
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    recorder = load_recorder()
    try:
        matrix = load_matrix(args.matrix)
        candidate = None
        if candidate_args_present(args) or args.record_matrix:
            candidate = build_candidate(
                recorder=recorder,
                checked_at=args.checked_at,
                evidence_source=args.evidence_source,
                reporter_label=args.reporter_label,
                client=args.client,
                client_version=args.client_version,
                network_type=args.network_type,
                transport=args.transport,
                port=args.port,
                result=args.result,
                symptom=args.symptom,
                evidence_session_id=args.evidence_session_id,
            )
        matrix_after = None
        wrote_matrix = False
        if args.record_matrix:
            if candidate is None:
                raise RemoteEvidenceError("--record-matrix requires a client evidence candidate")
            matrix_after = recorder.add_or_update_check(matrix, candidate)
            if args.write:
                recorder.write_matrix(args.matrix, matrix_after)
                recorder.write_markdown(args.matrix_markdown, matrix_after)
                wrote_matrix = True
        report = build_report(
            recorder=recorder,
            matrix=matrix,
            candidate=candidate,
            matrix_after=matrix_after,
            record_matrix=args.record_matrix,
            wrote_matrix=wrote_matrix,
        )
        findings = validate_safe_payload(report, recorder)
        if findings:
            details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
            raise RemoteEvidenceError(f"unsafe remote evidence report: {details}")
        if args.write:
            write_json(args.json_out, report)
            write_markdown(args.markdown_out, report, recorder)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"ok=true decision={report['decision']} "
                f"matrix_updated={str(report['matrix_updated']).lower()}"
            )
        return 0
    except RemoteEvidenceError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
