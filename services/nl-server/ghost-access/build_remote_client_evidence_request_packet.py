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


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_ANDROID_ADB_PROBE_PATH = Path(
    "nl-diagnostics/nl-anti-block-android-adb-probe-2026-06-02.json"
)
DEFAULT_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json"
)
DEFAULT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.md"
)
REMOTE_RECORDER_PATH = "services/nl-server/ghost-access/record_remote_client_evidence.py"
REMOTE_REPLY_RECORDER_PATH = "services/nl-server/ghost-access/record_remote_client_evidence_reply.py"
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"
CURRENT_EVIDENCE_SESSION_STARTED_AT = "2026-06-02T00:00:00Z"
DIRECT_RECORD_COMMANDS_POLICY = (
    "Direct record_remote_client_evidence.py --write commands are disabled in this "
    "remote request packet; record tester replies only through "
    "operator_reply_record_* commands so every persisted reply is bound to the "
    "current request packet SHA-256."
)

FORBIDDEN_OUTPUT_PATTERNS = {
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


class RequestPacketError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RequestPacketError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RequestPacketError(f"{path} is not valid JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else None


def load_matrix(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    if payload is None:
        raise RequestPacketError(f"matrix not found or not an object: {path}")
    return payload


def request_key(task: dict[str, Any]) -> tuple[str, str, str, int | None]:
    return (
        str(task.get("client") or "any"),
        str(task.get("network_type") or "unknown"),
        str(task.get("transport") or "reality"),
        task.get("port") if isinstance(task.get("port"), int) else None,
    )


def reporter_label_for(network_type: str) -> str:
    return "workplace-user" if network_type == "work-wifi" else "remote-city-user"


def evidence_source_for(network_type: str) -> str:
    return "support_call_summary" if network_type == "work-wifi" else "remote_user_report"


def build_record_command(
    *,
    client: str,
    network_type: str,
    transport: str,
    port: int | None,
    result: str,
    symptom: str,
) -> str:
    return (
        f"python3 {REMOTE_RECORDER_PATH} "
        "--write --record-matrix "
        f"--evidence-source {evidence_source_for(network_type)} "
        f"--reporter-label {reporter_label_for(network_type)} "
        f'--client "{client}" '
        "--client-version unknown "
        f"--network-type {network_type} "
        f"--transport {transport} "
        f"--port {port if port is not None else ''} "
        f"--result {result} "
        f'--symptom "{symptom}" '
        f"--evidence-session-id {CURRENT_EVIDENCE_SESSION_ID} "
        "--json"
    )


def build_reply_record_command(*, request_id: str, reply: str) -> str:
    return (
        f"printf '%s\\n' \"{reply}\" | "
        f"python3 {REMOTE_REPLY_RECORDER_PATH} "
        "--write --record-matrix "
        "--refresh-artifacts "
        '--expect-request-packet-sha256 "$(sha256sum '
        f"{DEFAULT_JSON_PATH} "
        '| awk \'{print $1}\')" '
        f"--request-id {request_id} "
        "--reply-stdin "
        "--json"
    )


def build_reply_validate_command(*, request_id: str, reply: str) -> str:
    return (
        f"printf '%s\\n' \"{reply}\" | "
        f"python3 {REMOTE_REPLY_RECORDER_PATH} "
        '--expect-request-packet-sha256 "$(sha256sum '
        f"{DEFAULT_JSON_PATH} "
        '| awk \'{print $1}\')" '
        f"--request-id {request_id} "
        "--reply-stdin "
        "--json"
    )


def tester_message(
    *,
    request_id: str,
    client: str,
    network_type: str,
    transport: str,
    port: int | None,
) -> str:
    network_text = (
        "mobile data, not Wi-Fi"
        if network_type == "mobile"
        else "the restricted or work Wi-Fi"
        if network_type == "work-wifi"
        else network_type
    )
    app_text = "Happ or Hiddify" if client.lower() in {"happ", "hiddify", "any"} else client
    profile_text = (
        "active Ghost Access Reality profile"
        if transport.lower() == "reality"
        else f"Ghost Access {transport.upper()} profile"
    )
    return (
        f"Test {request_id}: use {app_text} on {network_text}. "
        f"Select the {profile_text} on port {port}. "
        "Open any normal encrypted website or app through the VPN. "
        "Reply only with: pass connected, fail timeout, fail import, or fail no-internet. "
        "Do not send profile links, subscription links, QR codes, UUIDs, IP addresses, "
        "usernames, phone numbers, handles, screenshots, or logs."
    )


def build_requests(plan: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, int | None], dict[str, Any]] = {}
    for task in plan.get("required_tasks") or []:
        if not isinstance(task, dict):
            continue
        key = request_key(task)
        row = grouped.setdefault(
            key,
            {
                "client": key[0],
                "network_type": key[1],
                "transport": key[2],
                "port": key[3],
                "covers_requirements": [],
            },
        )
        requirement = str(task.get("requirement") or "")
        if requirement and requirement not in row["covers_requirements"]:
            row["covers_requirements"].append(requirement)

    requests: list[dict[str, Any]] = []
    for index, row in enumerate(grouped.values(), start=1):
        request_id = f"remote-client-evidence-{index}"
        client = str(row["client"])
        network_type = str(row["network_type"])
        transport = str(row["transport"])
        port = row["port"] if isinstance(row["port"], int) else None
        requests.append(
            {
                "request_id": request_id,
                "covers_requirements": list(row["covers_requirements"]),
                "client": client,
                "network_type": network_type,
                "transport": transport,
                "port": port,
                "evidence_session_id": CURRENT_EVIDENCE_SESSION_ID,
                "evidence_session_started_at": CURRENT_EVIDENCE_SESSION_STARTED_AT,
                "minimum_result_to_close_requirements": "pass",
                "tester_message": tester_message(
                    request_id=request_id,
                    client=client,
                    network_type=network_type,
                    transport=transport,
                    port=port,
                ),
                "operator_record_command_policy": DIRECT_RECORD_COMMANDS_POLICY,
                "operator_record_pass_command": "",
                "operator_reply_record_pass_command": build_reply_record_command(
                    request_id=request_id,
                    reply="pass connected",
                ),
                "operator_reply_validate_pass_command": build_reply_validate_command(
                    request_id=request_id,
                    reply="pass connected",
                ),
                "operator_record_fail_command": "",
                "operator_reply_record_fail_command": build_reply_record_command(
                    request_id=request_id,
                    reply="fail timeout",
                ),
                "operator_reply_validate_fail_command": build_reply_validate_command(
                    request_id=request_id,
                    reply="fail timeout",
                ),
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            }
        )
    return requests


def build_packet(
    matrix: dict[str, Any],
    *,
    android_adb_probe: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    plan_builder = load_module("build_client_evidence_plan", SCRIPT_DIR / "build_client_evidence_plan.py")
    plan = plan_builder.build_plan(
        matrix,
        android_adb_probe=android_adb_probe,
        generated_at=generated_at or utc_now(),
    )
    requests = build_requests(plan)
    missing = [str(item) for item in plan.get("missing_requirements") or []]
    packet = {
        "packet_id": "nl-anti-block-remote-client-evidence-request-2026-06-02",
        "generated_at": generated_at or utc_now(),
        "decision": (
            "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED"
            if not missing
            else "REMOTE_CLIENT_EVIDENCE_REQUEST_READY"
        ),
        "source_matrix": str(DEFAULT_MATRIX_PATH),
        "matrix_decision": matrix.get("decision"),
        "evidence_session_id": CURRENT_EVIDENCE_SESSION_ID,
        "evidence_session_started_at": CURRENT_EVIDENCE_SESSION_STARTED_AT,
        "missing_requirements": missing,
        "minimum_reports_required": len(requests),
        "request_count": len(requests),
        "checked_at_policy": (
            "generated commands omit --checked-at so the recorder stores current UTC; "
            "append --checked-at <ISO8601_Z> only when recording a delayed report"
        ),
        "request_freshness_policy": (
            "record_remote_client_evidence_reply.py rejects request packets older than 24 hours; "
            "refresh this packet before recording delayed replies"
        ),
        "request_packet_hash_binding_policy": (
            "record_remote_client_evidence_reply.py supports --expect-request-packet-sha256; "
            "before recording a reply, bind it to the exact request artifact hash from "
            "scripts/vpn_status.sh --json client_evidence.remote_request_packet.source_sha256 "
            "or from sha256sum of this request packet"
        ),
        "direct_record_commands_policy": DIRECT_RECORD_COMMANDS_POLICY,
        "requests": requests,
        "android_adb_probe_decision": (
            android_adb_probe.get("decision") if isinstance(android_adb_probe, dict) else None
        ),
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
            "raw_logs_stored": False,
        },
    }
    findings = validate_output(packet)
    if findings:
        packet["privacy"]["output_privacy_ok"] = False
        packet["privacy_findings"] = findings
    return packet


def validate_output(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return [
        {"kind": name}
        for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items()
        if pattern.search(rendered)
    ]


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


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# NL Anti-Block Remote Client Evidence Request - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(packet.get('decision'))}`",
        "",
        "This packet contains safe request text and operator commands for collecting the remaining real-client evidence. It must not contain VPN links, subscription URLs, QR codes, UUIDs, raw IPs, emails, handles, phone numbers, screenshots, logs, or personal identifiers.",
        "",
        "## Summary",
        "",
        "| Missing Requirements | Minimum Reports Required | Request Count |",
        "| --- | --- | --- |",
        "| "
        + " | ".join(
            [
                markdown_cell(packet.get("missing_requirements")),
                markdown_cell(packet.get("minimum_reports_required")),
                markdown_cell(packet.get("request_count")),
            ]
        )
        + " |",
        "",
        "Freshness policy:",
        "",
        "```text",
        str(packet.get("request_freshness_policy") or ""),
        "```",
        "",
        "Request packet hash binding policy:",
        "",
        "```text",
        str(packet.get("request_packet_hash_binding_policy") or ""),
        "```",
        "",
        "## Requests",
        "",
    ]
    for request in packet.get("requests") or []:
        if not isinstance(request, dict):
            continue
        lines.extend(
            [
                f"### {markdown_cell(request.get('request_id'))}",
                "",
                "| Covers | Client | Network | Transport | Port | Evidence Session | Session Started At |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| "
                + " | ".join(
                    [
                        markdown_cell(request.get("covers_requirements")),
                        markdown_cell(request.get("client")),
                        markdown_cell(request.get("network_type")),
                        markdown_cell(request.get("transport")),
                        markdown_cell(request.get("port")),
                        markdown_cell(request.get("evidence_session_id")),
                        markdown_cell(request.get("evidence_session_started_at")),
                    ]
                )
                + " |",
                "",
                "Tester message:",
                "",
                "```text",
                str(request.get("tester_message") or ""),
                "```",
                "",
                "Direct record command policy:",
                "",
                "```text",
                str(request.get("operator_record_command_policy") or ""),
                "```",
                "",
                "Record pass from short reply:",
                "",
                "```bash",
                str(request.get("operator_reply_record_pass_command") or ""),
                "```",
                "",
                "Validate pass reply without writing:",
                "",
                "```bash",
                str(request.get("operator_reply_validate_pass_command") or ""),
                "```",
                "",
                "Record fail from short reply:",
                "",
                "```bash",
                str(request.get("operator_reply_record_fail_command") or ""),
                "```",
                "",
                "Validate fail reply without writing:",
                "",
                "```bash",
                str(request.get("operator_reply_validate_fail_command") or ""),
                "```",
                "",
                "Allowed short replies:",
                "",
                "```text",
                markdown_cell(request.get("safe_reply_options")),
                "```",
                "",
            ]
        )
    if not packet.get("requests"):
        lines.append("No remote client evidence requests are needed.")
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build a privacy-safe request packet for missing NL client evidence."
    )
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--android-adb-probe", type=Path, default=DEFAULT_ANDROID_ADB_PROBE_PATH)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_PATH)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        matrix = load_matrix(args.matrix)
        packet = build_packet(
            matrix,
            android_adb_probe=load_json(args.android_adb_probe),
        )
        findings = validate_output(packet)
        if findings:
            raise RequestPacketError(
                "unsafe request packet output: "
                + ", ".join(item["kind"] for item in findings)
            )
        if args.write:
            write_json(args.json_out, packet)
            write_markdown(args.markdown_out, packet)
        if args.json:
            print(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"ok=true decision={packet['decision']} "
                f"requests={packet['request_count']}"
            )
        return 0
    except RequestPacketError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
