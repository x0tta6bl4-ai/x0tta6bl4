#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Sequence


DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_JSON_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-evidence-plan-2026-06-02.json"
)
DEFAULT_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-evidence-plan-2026-06-02.md"
)
DEFAULT_ANDROID_ADB_PROBE_PATH = Path(
    "nl-diagnostics/nl-anti-block-android-adb-probe-2026-06-02.json"
)
DEFAULT_RECORDER_PATH = "services/nl-server/ghost-access/record_client_compatibility.py"
DEFAULT_REMOTE_RECORDER_PATH = (
    "services/nl-server/ghost-access/record_remote_client_evidence.py"
)

FORBIDDEN_OUTPUT_PATTERNS = {
    "vpn_uri": re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.IGNORECASE),
    "subscription_path": re.compile(r"/sub/[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]{8,}"),
    "uuid": re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "ipv4": re.compile(
        r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
    ),
}


class EvidencePlanError(ValueError):
    pass


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_matrix(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EvidencePlanError(f"matrix not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvidencePlanError(f"matrix is not valid JSON: {exc}") from exc


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidencePlanError(f"{path} is not valid JSON: {exc}") from exc
    return payload if isinstance(payload, dict) else None


def default_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=8,
    )


def inspect_adb(runner: Runner = default_runner) -> dict[str, Any]:
    try:
        result = runner(["adb", "devices", "-l"])
    except FileNotFoundError:
        return {
            "adb_available": False,
            "connected_device_count": 0,
            "device_state_counts": {},
            "raw_serials_stored": False,
        }
    except Exception as exc:
        return {
            "adb_available": True,
            "connected_device_count": 0,
            "device_state_counts": {},
            "error_type": type(exc).__name__,
            "raw_serials_stored": False,
        }

    state_counts: dict[str, int] = {}
    connected = 0
    for line in (result.stdout or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("List of devices"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            continue
        state = parts[1]
        state_counts[state] = state_counts.get(state, 0) + 1
        if state == "device":
            connected += 1

    return {
        "adb_available": result.returncode == 0,
        "connected_device_count": connected,
        "device_state_counts": state_counts,
        "raw_serials_stored": False,
    }


def completion_rule(matrix: dict[str, Any]) -> dict[str, Any]:
    rule = matrix.get("completion_rule")
    return rule if isinstance(rule, dict) else {}


def missing_requirements(matrix: dict[str, Any]) -> list[str]:
    values = completion_rule(matrix).get("missing_requirements")
    return [str(value) for value in values] if isinstance(values, list) else []


def next_required_checks(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    values = completion_rule(matrix).get("next_required_checks")
    return [row for row in values if isinstance(row, dict)] if isinstance(values, list) else []


def planned_task(
    row: dict[str, Any],
    *,
    recorder_path: str,
    remote_recorder_path: str,
) -> dict[str, Any]:
    requirement = str(row.get("requirement") or "")
    client = str(row.get("client") or "any")
    network_type = str(row.get("network_type") or "unknown")
    transport = str(row.get("transport") or "reality")
    port = row.get("port")
    port_text = str(port) if port is not None else ""
    command = (
        f"python3 {recorder_path} "
        "--matrix nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json "
        "--markdown nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md "
        "--add-check "
        f"--client \"{client}\" "
        "--client-version unknown "
        f"--network-type {network_type} "
        f"--transport {transport} "
        f"--port {port_text} "
        "--result <pass|fail> "
        "--symptom \"<short result, no secrets>\" "
        "--json"
    )
    adb_record_command = (
        "python3 services/nl-server/ghost-access/probe_android_adb_vpn.py "
        "--write --json --record-matrix "
        f"--client \"{client}\" "
        "--client-version unknown "
        f"--network-type {network_type} "
        f"--transport {transport} "
        f"--port {port_text}"
    )
    remote_record_command = (
        f"python3 {remote_recorder_path} "
        "--write --record-matrix "
        "--evidence-source remote_user_report "
        "--reporter-label remote-city-user "
        f"--client \"{client}\" "
        "--client-version unknown "
        f"--network-type {network_type} "
        f"--transport {transport} "
        f"--port {port_text} "
        "--result <pass|fail> "
        "--symptom \"<short result, no secrets>\" "
        "--json"
    )
    return {
        "requirement": requirement,
        "client": client,
        "network_type": network_type,
        "transport": transport,
        "port": port,
        "pass_criteria": [
            "client imports the existing Ghost Access subscription",
            "selected active Reality profile connects without editing secrets",
            "HTTPS generate_204 or normal HTTPS browsing works through the VPN",
            "no VPN link, UUID, subscription token, raw IP, email, username, QR code, or screenshot is stored",
        ],
        "fail_criteria": [
            "client cannot import the active Reality profile",
            "selected active Reality profile connects but normal HTTPS does not work",
            "client reports timeout, TLS error, handshake failure, or HTTP 404 for subscription",
        ],
        "safe_recorder_command_template": command,
        "android_adb_probe_record_command_template": adb_record_command,
        "remote_client_evidence_record_command_template": remote_record_command,
        "checked_at_policy": (
            "generated commands omit --checked-at so the recorder stores current UTC; "
            "append --checked-at <ISO8601_Z> only when recording a delayed report"
        ),
    }


def build_plan(
    matrix: dict[str, Any],
    *,
    adb: dict[str, Any] | None = None,
    android_adb_probe: dict[str, Any] | None = None,
    generated_at: str | None = None,
    recorder_path: str = DEFAULT_RECORDER_PATH,
    remote_recorder_path: str = DEFAULT_REMOTE_RECORDER_PATH,
) -> dict[str, Any]:
    missing = missing_requirements(matrix)
    next_checks = next_required_checks(matrix)
    tasks = [
        planned_task(
            row,
            recorder_path=recorder_path,
            remote_recorder_path=remote_recorder_path,
        )
        for row in next_checks
    ]
    if "mobile_network" in missing and not any(
        row.get("requirement") == "mobile_network" for row in tasks
    ):
        tasks.append(
            planned_task(
                {
                    "requirement": "mobile_network",
                    "client": "Happ",
                    "network_type": "mobile",
                    "transport": "reality",
                    "port": 443,
                },
                recorder_path=recorder_path,
                remote_recorder_path=remote_recorder_path,
            )
        )

    decision = (
        "CLIENT_EVIDENCE_COMPLETE"
        if not missing
        else "CLIENT_EVIDENCE_REQUIRED"
    )
    payload = {
        "plan_id": "nl-anti-block-client-evidence-plan-2026-06-02",
        "generated_at": generated_at or utc_now(),
        "source_matrix": "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json",
        "decision": decision,
        "matrix_decision": matrix.get("decision"),
        "completion_evidence": completion_rule(matrix).get("evidence") or {},
        "missing_requirements": missing,
        "required_tasks": tasks,
        "adb_context": adb or inspect_adb(),
        "android_adb_probe": android_adb_probe,
        "privacy": {
            "output_privacy_ok": True,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_adb_serial_stored": False,
        },
    }
    findings = validate_output(payload)
    if findings:
        payload["privacy"]["output_privacy_ok"] = False
        payload["privacy_findings"] = findings
    return payload


def validate_output(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    findings = []
    for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items():
        if pattern.search(rendered):
            findings.append({"kind": name})
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


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# NL Anti-Block Client Evidence Plan - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(plan.get('decision'))}`",
        "",
        "This file contains only safe evidence instructions. Do not store VPN links, UUIDs, raw IPs, emails, usernames, subscription tokens, QR codes, or screenshots that reveal secrets.",
        "",
        "## Current Status",
        "",
        f"`missing_requirements={markdown_cell(plan.get('missing_requirements'))}`",
        "",
        "| Requirement | Proven |",
        "| --- | --- |",
    ]
    evidence = plan.get("completion_evidence") or {}
    if isinstance(evidence, dict):
        for key, value in evidence.items():
            lines.append(f"| {markdown_cell(key)} | {markdown_cell(value)} |")
    lines.extend(
        [
            "",
            "## ADB Context",
            "",
            "| ADB Available | Connected Devices | State Counts | Raw Serials Stored |",
            "| --- | --- | --- | --- |",
        ]
    )
    adb = plan.get("adb_context") or {}
    lines.append(
        "| "
        + " | ".join(
            [
                markdown_cell(adb.get("adb_available")),
                markdown_cell(adb.get("connected_device_count")),
                markdown_cell(adb.get("device_state_counts")),
                markdown_cell(adb.get("raw_serials_stored")),
            ]
        )
        + " |"
    )
    android_probe = plan.get("android_adb_probe")
    if isinstance(android_probe, dict):
        dataplane = android_probe.get("dataplane") or {}
        runtime = android_probe.get("vpn_runtime") or {}
        lines.extend(
            [
                "",
                "## Latest Android ADB Probe",
                "",
                "| Decision | OK | VPN Seen | Dataplane OK | HTTP Code | Tool |",
                "| --- | --- | --- | --- | --- | --- |",
                "| "
                + " | ".join(
                    [
                        markdown_cell(android_probe.get("decision")),
                        markdown_cell(android_probe.get("ok")),
                        markdown_cell(runtime.get("vpn_transport_seen")),
                        markdown_cell(dataplane.get("ok")),
                        markdown_cell(dataplane.get("http_code")),
                        markdown_cell(dataplane.get("tool")),
                    ]
                )
                + " |",
            ]
        )
    lines.extend(
        [
            "",
            "## Required Tasks",
            "",
            "| Requirement | Client | Network | Transport | Port |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for task in plan.get("required_tasks") or []:
        if not isinstance(task, dict):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(task.get("requirement")),
                    markdown_cell(task.get("client")),
                    markdown_cell(task.get("network_type")),
                    markdown_cell(task.get("transport")),
                    markdown_cell(task.get("port")),
                ]
            )
            + " |"
        )
    if not plan.get("required_tasks"):
        lines.append("| none |  |  |  |  |")

    lines.extend(["", "## Safe Recorder Commands", ""])
    for index, task in enumerate(plan.get("required_tasks") or [], start=1):
        if not isinstance(task, dict):
            continue
        lines.extend(
            [
                f"Task {index}: `{markdown_cell(task.get('requirement'))}`",
                "",
                "```bash",
                str(task.get("safe_recorder_command_template") or ""),
                "```",
                "",
                "Remote client evidence command:",
                "",
                "```bash",
                str(task.get("remote_client_evidence_record_command_template") or ""),
                "```",
                "",
                "Android ADB auto-record command:",
                "",
                "```bash",
                str(task.get("android_adb_probe_record_command_template") or ""),
                "```",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build a privacy-safe NL client evidence plan.")
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_PATH)
    p.add_argument("--android-adb-probe", type=Path, default=DEFAULT_ANDROID_ADB_PROBE_PATH)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        matrix = load_matrix(args.matrix)
        plan = build_plan(matrix, android_adb_probe=load_optional_json(args.android_adb_probe))
        findings = validate_output(plan)
        if findings:
            raise EvidencePlanError("unsafe evidence plan output: " + ", ".join(item["kind"] for item in findings))
        if args.write:
            write_json(args.json_out, plan)
            write_markdown(args.markdown_out, plan)
        if args.json:
            print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(
                f"ok=true decision={plan['decision']} "
                f"missing={len(plan['missing_requirements'])} tasks={len(plan['required_tasks'])}"
            )
        return 0
    except EvidencePlanError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
