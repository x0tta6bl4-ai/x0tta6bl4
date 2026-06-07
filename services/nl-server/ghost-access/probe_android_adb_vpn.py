#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Sequence


DEFAULT_JSON_PATH = Path("nl-diagnostics/nl-anti-block-android-adb-probe-2026-06-02.json")
DEFAULT_MARKDOWN_PATH = Path("nl-diagnostics/nl-anti-block-android-adb-probe-2026-06-02.md")
DEFAULT_MATRIX_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.json"
)
DEFAULT_MATRIX_MARKDOWN_PATH = Path(
    "nl-diagnostics/nl-anti-block-client-compatibility-matrix-2026-06-02.md"
)
DEFAULT_RECORDER_PATH = Path("services/nl-server/ghost-access/record_client_compatibility.py")
DEFAULT_TARGET_URL = "https://www.gstatic.com/generate_204"

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
}


class AndroidProbeError(ValueError):
    pass


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def default_runner(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=25,
    )


def parse_adb_devices(stdout: str) -> dict[str, Any]:
    state_counts: dict[str, int] = {}
    connected = 0
    for line in stdout.splitlines():
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
        "connected_device_count": connected,
        "device_state_counts": state_counts,
        "raw_serials_stored": False,
    }


def list_adb_devices(runner: Runner = default_runner) -> dict[str, Any]:
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
    parsed = parse_adb_devices(result.stdout or "")
    parsed["adb_available"] = result.returncode == 0
    return parsed


def run_android_shell(command: str, runner: Runner = default_runner) -> subprocess.CompletedProcess[str]:
    return runner(["adb", "shell", "sh", "-c", command])


def parse_http_probe(stdout: str, returncode: int) -> dict[str, Any]:
    text = " ".join(stdout.strip().split())
    code_match = re.search(r"\bcode=(\d{3})\b", text)
    tool_match = re.search(r"\btool=([A-Za-z0-9_.-]+)\b", text)
    http_code = int(code_match.group(1)) if code_match else 0
    tool = tool_match.group(1) if tool_match else "unknown"
    ok = returncode == 0 and 200 <= http_code < 500
    return {
        "ok": ok,
        "http_code": http_code,
        "tool": tool,
        "raw_response_stored": False,
    }


def probe_vpn_runtime(runner: Runner = default_runner) -> dict[str, Any]:
    command = "dumpsys connectivity 2>/dev/null | grep -E 'TRANSPORT_VPN|VPN' | head -n 20"
    result = run_android_shell(command, runner)
    text = result.stdout or ""
    return {
        "checked": result.returncode in {0, 1},
        "vpn_transport_seen": "VPN" in text.upper() or "TRANSPORT_VPN" in text.upper(),
        "raw_connectivity_dump_stored": False,
    }


def probe_dataplane(
    *,
    target_url: str = DEFAULT_TARGET_URL,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    command = (
        "if command -v curl >/dev/null 2>&1; then "
        f"curl -4 -L -s -o /dev/null -w 'code=%{{http_code}} tool=curl' --max-time 15 {target_url}; "
        "elif command -v toybox >/dev/null 2>&1; then "
        f"toybox wget -q -T 15 -O /dev/null {target_url} >/dev/null 2>&1 "
        "&& echo 'code=204 tool=toybox-wget' || echo 'code=000 tool=toybox-wget'; "
        "elif command -v wget >/dev/null 2>&1; then "
        f"wget -q -T 15 -O /dev/null {target_url} >/dev/null 2>&1 "
        "&& echo 'code=204 tool=wget' || echo 'code=000 tool=wget'; "
        "else echo 'code=000 tool=missing'; fi"
    )
    result = run_android_shell(command, runner)
    parsed = parse_http_probe(result.stdout or "", result.returncode)
    parsed["target_url_class"] = "https_generate_204"
    return parsed


def build_report(
    *,
    runner: Runner = default_runner,
    target_url: str = DEFAULT_TARGET_URL,
    checked_at: str | None = None,
) -> dict[str, Any]:
    adb = list_adb_devices(runner)
    if not adb.get("adb_available"):
        decision = "ANDROID_ADB_UNAVAILABLE"
        ok = False
        vpn_runtime = {
            "checked": False,
            "vpn_transport_seen": False,
            "raw_connectivity_dump_stored": False,
        }
        dataplane = {
            "ok": False,
            "http_code": 0,
            "tool": "not_run",
            "target_url_class": "https_generate_204",
            "raw_response_stored": False,
        }
    elif adb.get("connected_device_count") == 0:
        decision = "ANDROID_DEVICE_NOT_CONNECTED"
        ok = False
        vpn_runtime = {
            "checked": False,
            "vpn_transport_seen": False,
            "raw_connectivity_dump_stored": False,
        }
        dataplane = {
            "ok": False,
            "http_code": 0,
            "tool": "not_run",
            "target_url_class": "https_generate_204",
            "raw_response_stored": False,
        }
    elif adb.get("connected_device_count") != 1:
        decision = "ANDROID_MULTIPLE_DEVICES_CONNECTED"
        ok = False
        vpn_runtime = {
            "checked": False,
            "vpn_transport_seen": False,
            "raw_connectivity_dump_stored": False,
        }
        dataplane = {
            "ok": False,
            "http_code": 0,
            "tool": "not_run",
            "target_url_class": "https_generate_204",
            "raw_response_stored": False,
        }
    else:
        vpn_runtime = probe_vpn_runtime(runner)
        dataplane = probe_dataplane(target_url=target_url, runner=runner)
        ok = bool(dataplane.get("ok")) and bool(vpn_runtime.get("vpn_transport_seen"))
        if ok:
            decision = "ANDROID_ADB_VPN_DATAPLANE_PASS"
        elif dataplane.get("ok"):
            decision = "ANDROID_ADB_DATAPLANE_PASS_VPN_NOT_OBSERVED"
        else:
            decision = "ANDROID_ADB_VPN_DATAPLANE_FAIL"

    report = {
        "checked_at": checked_at or utc_now(),
        "decision": decision,
        "ok": ok,
        "adb": adb,
        "vpn_runtime": vpn_runtime,
        "dataplane": dataplane,
        "privacy": {
            "output_privacy_ok": True,
            "raw_adb_serial_stored": False,
            "raw_connectivity_dump_stored": False,
            "raw_response_stored": False,
            "raw_subscription_url_stored": False,
            "raw_vpn_uri_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
        },
    }
    findings = validate_output(report)
    if findings:
        report["privacy"]["output_privacy_ok"] = False
        report["privacy_findings"] = findings
    return report


def validate_output(payload: dict[str, Any]) -> list[dict[str, str]]:
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    findings = []
    for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items():
        if pattern.search(rendered):
            findings.append({"kind": name})
    return findings


def load_recorder(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("record_client_compatibility", path)
    if spec is None or spec.loader is None:
        raise AndroidProbeError(f"cannot load recorder: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def record_probe_to_matrix(
    report: dict[str, Any],
    *,
    recorder_path: Path,
    matrix_path: Path,
    markdown_path: Path | None,
    client: str,
    client_version: str,
    network_type: str,
    transport: str,
    port: int,
    record_fail: bool,
) -> dict[str, Any]:
    probe_passed = bool(report.get("ok")) and report.get("decision") == "ANDROID_ADB_VPN_DATAPLANE_PASS"
    result = "pass" if probe_passed else "fail"
    if result == "fail" and not record_fail:
        return {
            "attempted": False,
            "recorded": False,
            "reason": "probe_not_passed_record_fail_not_enabled",
            "would_result": result,
            "matrix_path": str(matrix_path),
        }

    recorder = load_recorder(recorder_path)
    dataplane = report.get("dataplane") or {}
    vpn_runtime = report.get("vpn_runtime") or {}
    symptom = (
        f"android adb vpn probe {report.get('decision')} "
        f"http {dataplane.get('http_code', 0)} "
        f"vpn_seen {str(bool(vpn_runtime.get('vpn_transport_seen'))).lower()}"
    )
    row = recorder.build_check_row(
        checked_at=str(report.get("checked_at") or utc_now()),
        client=client,
        client_version=client_version,
        network_type=network_type,
        transport=transport,
        port=port,
        result=result,
        symptom=symptom,
    )
    matrix = recorder.load_matrix(matrix_path)
    matrix = recorder.add_or_update_check(matrix, row)
    recorder.write_matrix(matrix_path, matrix)
    if markdown_path is not None:
        recorder.write_markdown(markdown_path, matrix)
    return {
        "attempted": True,
        "recorded": True,
        "result": result,
        "client": row["client"],
        "network_type": row["network_type"],
        "transport": row["transport"],
        "port": row["port"],
        "matrix_path": str(matrix_path),
        "markdown_path": str(markdown_path) if markdown_path is not None else None,
    }


def markdown_cell(value: Any) -> str:
    if value is None:
        text = ""
    elif isinstance(value, bool):
        text = "true" if value else "false"
    elif isinstance(value, dict):
        text = ", ".join(f"{key}={markdown_cell(nested)}" for key, nested in value.items())
    elif isinstance(value, (list, tuple)):
        text = ", ".join(markdown_cell(item) for item in value)
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ").strip()


def render_markdown(report: dict[str, Any]) -> str:
    adb = report.get("adb") or {}
    vpn_runtime = report.get("vpn_runtime") or {}
    dataplane = report.get("dataplane") or {}
    matrix_recording = report.get("matrix_recording") or {}
    return (
        "# NL Anti-Block Android ADB VPN Probe - 2026-06-02\n\n"
        "## Decision\n\n"
        f"`{markdown_cell(report.get('decision'))}`\n\n"
        "This probe stores only aggregate ADB/device/runtime/dataplane status. It does not store ADB serials, VPN links, UUIDs, raw IPs, emails, subscription tokens, QR codes, screenshots, or connectivity dumps.\n\n"
        "## ADB\n\n"
        "| ADB Available | Connected Devices | State Counts | Raw Serials Stored |\n"
        "| --- | --- | --- | --- |\n"
        f"| {markdown_cell(adb.get('adb_available'))} | {markdown_cell(adb.get('connected_device_count'))} | {markdown_cell(adb.get('device_state_counts'))} | {markdown_cell(adb.get('raw_serials_stored'))} |\n\n"
        "## Runtime\n\n"
        "| VPN Transport Seen | Connectivity Dump Stored |\n"
        "| --- | --- |\n"
        f"| {markdown_cell(vpn_runtime.get('vpn_transport_seen'))} | {markdown_cell(vpn_runtime.get('raw_connectivity_dump_stored'))} |\n\n"
        "## Dataplane\n\n"
        "| OK | HTTP Code | Tool | Target URL Class | Raw Response Stored |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| {markdown_cell(dataplane.get('ok'))} | {markdown_cell(dataplane.get('http_code'))} | {markdown_cell(dataplane.get('tool'))} | {markdown_cell(dataplane.get('target_url_class'))} | {markdown_cell(dataplane.get('raw_response_stored'))} |\n\n"
        "## Matrix Recording\n\n"
        "| Attempted | Recorded | Reason | Result | Matrix Path |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| {markdown_cell(matrix_recording.get('attempted'))} | {markdown_cell(matrix_recording.get('recorded'))} | {markdown_cell(matrix_recording.get('reason'))} | {markdown_cell(matrix_recording.get('result'))} | {markdown_cell(matrix_recording.get('matrix_path'))} |\n"
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(payload), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Probe Android active VPN dataplane through ADB without storing secrets.")
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_PATH)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_PATH)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--record-matrix", action="store_true", help="record probe result into the client compatibility matrix")
    p.add_argument("--record-fail", action="store_true", help="allow recording fail rows when the probe does not pass")
    p.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    p.add_argument("--matrix-markdown", type=Path, default=DEFAULT_MATRIX_MARKDOWN_PATH)
    p.add_argument("--recorder", type=Path, default=DEFAULT_RECORDER_PATH)
    p.add_argument("--client", default="Happ")
    p.add_argument("--client-version", default="unknown")
    p.add_argument("--network-type", default="mobile")
    p.add_argument("--transport", default="reality")
    p.add_argument("--port", type=int, default=443)
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    report = build_report(runner=default_runner)
    findings = validate_output(report)
    if findings:
        report["privacy"]["output_privacy_ok"] = False
        report["privacy_findings"] = findings
    report["matrix_recording"] = {
        "attempted": False,
        "recorded": False,
        "reason": "record_matrix_not_requested",
    }
    if args.record_matrix:
        try:
            report["matrix_recording"] = record_probe_to_matrix(
                report,
                recorder_path=args.recorder,
                matrix_path=args.matrix,
                markdown_path=args.matrix_markdown,
                client=args.client,
                client_version=args.client_version,
                network_type=args.network_type,
                transport=args.transport,
                port=args.port,
                record_fail=args.record_fail,
            )
        except Exception as exc:
            report["matrix_recording"] = {
                "attempted": True,
                "recorded": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
    if args.write:
        write_json(args.json_out, report)
        write_markdown(args.markdown_out, report)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"ok={str(report['ok']).lower()} decision={report['decision']}")
    if report["privacy"].get("output_privacy_ok") is not True:
        return 2
    if args.record_matrix and report["matrix_recording"].get("attempted") is True and not report["matrix_recording"].get("recorded"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
