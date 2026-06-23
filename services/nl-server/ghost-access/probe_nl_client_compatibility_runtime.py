#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Sequence


DEFAULT_JSON_OUT = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-probe-2026-06-02.json"
)
DEFAULT_MARKDOWN_OUT = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-runtime-probe-2026-06-02.md"
)

PROFILE_STATUS_UNIT = "x0tta6bl4-profile-status-api.service"
CLIENT_COMPAT_SERVICE = "ghost-access-client-compatibility-summary.service"
CLIENT_COMPAT_TIMER = "ghost-access-client-compatibility-summary.timer"
CLIENT_COMPAT_SUMMARY = "/var/lib/ghost-access/client-compatibility/latest.json"
CLIENT_COMPAT_MATRIX = "/var/lib/ghost-access/client-compatibility/matrix.json"
LOCAL_STATUS_BASE = "http://127.0.0.1:9472"
CURRENT_EVIDENCE_SESSION_ID = "nl-anti-block-2026-06-02"
CURRENT_EVIDENCE_SESSION_STARTED_AT = "2026-06-02T00:00:00Z"
CURRENT_EVIDENCE_REQUIRED_TRANSPORT = "reality"
CURRENT_EVIDENCE_REQUIRED_PORT = 443
THINKING_CONTRACT = {
    "role": "nl_client_compatibility_runtime_probe",
    "techniques": [
        "framing",
        "mape_k",
        "causal_analysis",
        "weighted_decision_matrix",
        "zero_trust_review",
    ],
    "safety_boundary": "read-only probe; do not store raw endpoints or client secrets",
}

FORBIDDEN_PATTERNS = {
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
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


class RuntimeProbeError(ValueError):
    pass


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


Runner = Callable[[Sequence[str]], CommandResult]


def default_runner(args: Sequence[str]) -> CommandResult:
    completed = subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=12,
    )
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ssh_command(host: str, remote_command: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        host,
        remote_command,
    ]


def run_ssh(host: str, remote_command: str, runner: Runner) -> CommandResult:
    return runner(ssh_command(host, remote_command))


def remote_stdout(host: str, remote_command: str, runner: Runner) -> str:
    result = run_ssh(host, remote_command, runner)
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def unit_active(host: str, unit: str, runner: Runner) -> str:
    status = remote_stdout(host, f"systemctl is-active {unit} 2>/dev/null || true", runner)
    return status or "unknown"


def unit_enabled(host: str, unit: str, runner: Runner) -> str:
    status = remote_stdout(host, f"systemctl is-enabled {unit} 2>/dev/null || true", runner)
    return status or "unknown"


def path_present(host: str, path: str, runner: Runner) -> bool:
    result = run_ssh(host, f"test -e {path}", runner)
    return result.returncode == 0


def http_code(host: str, path: str, runner: Runner) -> int:
    command = (
        f"curl -sS -o /dev/null -w '%{{http_code}}' "
        f"--max-time 3 {LOCAL_STATUS_BASE}{path} || true"
    )
    value = remote_stdout(host, command, runner)
    try:
        return int(value)
    except ValueError:
        return 0


def transport_usage_summary(host: str, runner: Runner) -> dict[str, Any]:
    command = f"curl -fsS --max-time 3 {LOCAL_STATUS_BASE}/transport-usage || true"
    output = remote_stdout(host, command, runner)
    if not output:
        return {"http_ok": False}
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {"http_ok": False, "json_ok": False}
    if not isinstance(payload, dict):
        return {"http_ok": False, "json_ok": False}
    usage = payload.get("transport_usage_60m") if isinstance(payload.get("transport_usage_60m"), dict) else {}
    return {
        "http_ok": True,
        "json_ok": True,
        "ok": payload.get("ok") is True,
        "ghost_xhttp_ready": payload.get("ghost_xhttp_ready") is True,
        "ghost_https_ws_ready": payload.get("ghost_https_ws_ready") is True,
        "privacy_ok": usage.get("privacy_ok") is True,
    }


def evidence_session_contract_ok(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    return (
        value.get("id") == CURRENT_EVIDENCE_SESSION_ID
        and value.get("started_at") == CURRENT_EVIDENCE_SESSION_STARTED_AT
        and value.get("required_transport") == CURRENT_EVIDENCE_REQUIRED_TRANSPORT
        and value.get("required_port") == CURRENT_EVIDENCE_REQUIRED_PORT
        and set(value.get("required_for_network_types") or [])
        == {"mobile", "restricted-wifi", "work-wifi"}
        and isinstance(value.get("session_bound_requirements"), dict)
    )


def client_compatibility_summary(host: str, runner: Runner) -> dict[str, Any]:
    code = http_code(host, "/client-compatibility", runner)
    summary: dict[str, Any] = {"http_code": code, "http_ok": code == 200}
    if code != 200:
        return summary
    output = remote_stdout(host, f"curl -fsS --max-time 3 {LOCAL_STATUS_BASE}/client-compatibility || true", runner)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        summary["json_ok"] = False
        return summary
    if not isinstance(payload, dict):
        summary["json_ok"] = False
        return summary
    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    evidence_session = (
        payload.get("evidence_session")
        if isinstance(payload.get("evidence_session"), dict)
        else {}
    )
    summary.update(
        {
            "json_ok": True,
            "ok": payload.get("ok") is True,
            "complete": payload.get("complete") is True,
            "decision": payload.get("decision"),
            "evidence_session": {
                "id": evidence_session.get("id"),
                "started_at": evidence_session.get("started_at"),
                "required_transport": evidence_session.get("required_transport"),
                "required_port": evidence_session.get("required_port"),
                "required_for_network_types": [
                    str(item)
                    for item in evidence_session.get("required_for_network_types") or []
                ],
                "session_bound_current_passing_checks": evidence_session.get(
                    "session_bound_current_passing_checks"
                )
                if isinstance(
                    evidence_session.get("session_bound_current_passing_checks"), int
                )
                else 0,
                "session_bound_requirements_present": isinstance(
                    evidence_session.get("session_bound_requirements"), dict
                ),
            },
            "evidence_session_contract_ok": evidence_session_contract_ok(
                evidence_session
            ),
            "missing_requirements": [
                str(item) for item in payload.get("missing_requirements") or []
            ]
            if isinstance(payload.get("missing_requirements"), list)
            else [],
            "privacy_ok": privacy.get("output_privacy_ok") is True,
            "raw_real_client_rows_returned": privacy.get("raw_real_client_rows_returned") is True,
        }
    )
    return summary


def decide(report: dict[str, Any]) -> str:
    client = report.get("client_compatibility_endpoint") or {}
    units = report.get("systemd_wiring") or {}
    if (
        client.get("http_ok")
        and units.get("summary_present") is True
        and client.get("evidence_session_contract_ok") is True
    ):
        return "NL_CLIENT_COMPAT_RUNTIME_READY"
    if client.get("http_code") == 404:
        return "NL_CLIENT_COMPAT_RUNTIME_ENDPOINT_MISSING"
    return "NL_CLIENT_COMPAT_RUNTIME_INCOMPLETE"


def thinking_context(task_type: str, goal: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "contract": THINKING_CONTRACT,
        "applied": {
            "framing": {
                "problem": task_type,
                "goal": goal,
                "constraints": constraints or {},
                "safety_boundary": THINKING_CONTRACT["safety_boundary"],
            },
            "mape_k": ["monitor", "analyze", "plan", "execute-readonly", "knowledge"],
            "zero_trust_review": {
                "default": "do not mutate remote state",
                "least_privilege": "SSH read-only commands only",
            },
        },
    }


def privacy_findings(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    findings = []
    for name, pattern in FORBIDDEN_PATTERNS.items():
        if pattern.search(rendered):
            findings.append({"kind": name})
    return findings


def build_report(host: str, runner: Runner | None = None) -> dict[str, Any]:
    runner = runner or default_runner
    transport = transport_usage_summary(host, runner)
    client = client_compatibility_summary(host, runner)
    wiring = {
        "summary_present": path_present(host, CLIENT_COMPAT_SUMMARY, runner),
        "matrix_present": path_present(host, CLIENT_COMPAT_MATRIX, runner),
        "service_unit_present": path_present(
            host, f"/etc/systemd/system/{CLIENT_COMPAT_SERVICE}", runner
        ),
        "timer_unit_present": path_present(
            host, f"/etc/systemd/system/{CLIENT_COMPAT_TIMER}", runner
        ),
        "timer_enabled": unit_enabled(host, CLIENT_COMPAT_TIMER, runner),
        "timer_active": unit_active(host, CLIENT_COMPAT_TIMER, runner),
    }
    report = {
        "probe_id": "nl-anti-block-client-compatibility-runtime-probe-2026-06-02",
        "checked_at": utc_now(),
        "ssh_host_label": host,
        "profile_status_api_unit": {
            "unit": PROFILE_STATUS_UNIT,
            "active": unit_active(host, PROFILE_STATUS_UNIT, runner),
        },
        "transport_usage_endpoint": transport,
        "client_compatibility_endpoint": client,
        "systemd_wiring": wiring,
        "required_actions": [],
        "privacy": {
            "output_privacy_ok": True,
            "raw_ssh_config_stored": False,
            "raw_ip_stored": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_email_stored": False,
            "raw_phone_stored": False,
            "raw_telegram_handle_stored": False,
            "raw_client_rows_stored": False,
        },
        "thinking": thinking_context(
            "nl_client_compatibility_runtime_probe",
            "Determine whether the NL client compatibility runtime is ready without leaking secrets.",
            {
                "required_transport": CURRENT_EVIDENCE_REQUIRED_TRANSPORT,
                "required_port": CURRENT_EVIDENCE_REQUIRED_PORT,
            },
        ),
    }
    if client.get("http_code") == 404:
        report["required_actions"].append("deploy_profile_status_api_client_compatibility_endpoint")
    if client.get("http_ok") and client.get("evidence_session_contract_ok") is not True:
        report["required_actions"].append("publish_current_client_compatibility_contract")
    if not wiring["summary_present"] or not wiring["matrix_present"]:
        report["required_actions"].append("publish_client_compatibility_matrix_and_summary")
    if not wiring["service_unit_present"] or not wiring["timer_unit_present"]:
        report["required_actions"].append("install_client_compatibility_summary_timer")
    report["decision"] = decide(report)
    findings = privacy_findings(report)
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
    client = report.get("client_compatibility_endpoint") or {}
    transport = report.get("transport_usage_endpoint") or {}
    wiring = report.get("systemd_wiring") or {}
    lines = [
        "# NL Anti-Block Client Compatibility Runtime Probe - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{markdown_cell(report.get('decision'))}`",
        "",
        "Read-only probe. It does not copy files, restart services, reload systemd, or store raw SSH config, IP addresses, subscription URLs, VPN links, UUIDs, emails, handles, phone numbers, or client rows.",
        "",
        "## Endpoints",
        "",
        "| Endpoint | Result |",
        "| --- | --- |",
        f"| /transport-usage | ok={markdown_cell(transport.get('ok'))}; xhttp={markdown_cell(transport.get('ghost_xhttp_ready'))}; ws={markdown_cell(transport.get('ghost_https_ws_ready'))}; privacy={markdown_cell(transport.get('privacy_ok'))} |",
        f"| /client-compatibility | http={markdown_cell(client.get('http_code'))}; ok={markdown_cell(client.get('ok'))}; complete={markdown_cell(client.get('complete'))}; missing={markdown_cell(client.get('missing_requirements'))} |",
        f"| /client-compatibility contract | session_ok={markdown_cell(client.get('evidence_session_contract_ok'))}; transport={markdown_cell((client.get('evidence_session') or {}).get('required_transport'))}; port={markdown_cell((client.get('evidence_session') or {}).get('required_port'))} |",
        "",
        "## Wiring",
        "",
        "| Item | Status |",
        "| --- | --- |",
        f"| summary file | {markdown_cell(wiring.get('summary_present'))} |",
        f"| matrix file | {markdown_cell(wiring.get('matrix_present'))} |",
        f"| service unit | {markdown_cell(wiring.get('service_unit_present'))} |",
        f"| timer unit | {markdown_cell(wiring.get('timer_unit_present'))} |",
        f"| timer enabled | {markdown_cell(wiring.get('timer_enabled'))} |",
        f"| timer active | {markdown_cell(wiring.get('timer_active'))} |",
        "",
        "## Required Actions",
        "",
        f"`{markdown_cell(report.get('required_actions'))}`",
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Read-only probe for NL client compatibility runtime wiring."
    )
    p.add_argument("--ssh-host", default="nl")
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        report = build_report(args.ssh_host)
        if args.write:
            write_json(args.json_out, report)
            write_markdown(args.markdown_out, report)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ok=true decision={report['decision']}")
        return 0 if (report.get("privacy") or {}).get("output_privacy_ok") is True else 1
    except RuntimeProbeError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
