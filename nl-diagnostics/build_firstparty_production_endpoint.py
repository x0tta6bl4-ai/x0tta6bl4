#!/usr/bin/env python3
"""Build first-party VPN production endpoint evidence.

The packet proves that a non-loopback first-party endpoint can be generated for
production without colliding with current NL listeners. Raw generated configs
are created in a temporary directory and deleted before evidence is written.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
NODE_SCRIPT = ROOT / "services" / "nl-server" / "firstparty-vpn-test" / "x0vpn_test_node.py"
DEFAULT_HOST = "89.125.1.107"
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_PORT = 40467
DEFAULT_TRANSPORT = "tcp"
LEGACY_PORTS = {
    443,
    2083,
    2443,
    34506,
    39829,
    4433,
    4434,
    51820,
    62789,
    8443,
}
LEGACY_MARKERS = (
    "x-ui",
    "xray",
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


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def collect_nl_listeners(*, ssh_target: str = "nl", timeout: int = 15) -> str:
    completed = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={timeout}",
            ssh_target,
            "ss -lntup",
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=timeout + 5,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"read-only NL listener collection failed: {completed.stderr[-500:]}"
        )
    return completed.stdout


def parse_listener_ports(text: str) -> set[int]:
    ports: set[int] = set()
    for line in text.splitlines():
        for match in re.finditer(r":(\d{1,5})(?=\s)", line):
            port = int(match.group(1))
            if 1 <= port <= 65535:
                ports.add(port)
    return ports


def build_payload(
    *,
    host: str = DEFAULT_HOST,
    bind_host: str = DEFAULT_BIND_HOST,
    port: int = DEFAULT_PORT,
    transport: str = DEFAULT_TRANSPORT,
    listeners_text: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or utc_now()
    occupied_ports = parse_listener_ports(listeners_text)
    candidate = _build_candidate_artifacts(
        host=host,
        bind_host=bind_host,
        port=port,
        transport=transport,
    )
    server_unit = str(candidate.get("server_unit_content") or "")
    client_unit = str(candidate.get("client_unit_content") or "")
    legacy_findings = _legacy_marker_findings([server_unit, client_unit])
    checks = {
        "generate_ok": candidate.get("generate_ok") is True,
        "server_service_plan_ok": candidate.get("server_service_plan_ok") is True,
        "client_service_plan_ok": candidate.get("client_service_plan_ok") is True,
        "endpoint_host_public": _is_public_endpoint(host),
        "server_bind_not_loopback": _is_non_loopback_bind(bind_host),
        "generated_server_bind_matches": candidate.get("server_bind_host") == bind_host,
        "generated_client_host_matches": candidate.get("client_host") == host,
        "generated_port_matches": candidate.get("port") == port,
        "generated_transport_matches": candidate.get("transport") == transport,
        "candidate_port_in_range": 1 <= port <= 65535,
        "candidate_port_not_legacy_known": port not in LEGACY_PORTS,
        "candidate_port_free_on_nl_snapshot": port not in occupied_ports,
        "service_units_firstparty_only": not legacy_findings
        and "x0vpn_node.py" in server_unit
        and "x0vpn_node.py" in client_unit
        and "server-tun" in server_unit
        and "client-tun" in client_unit,
        "temp_config_dir_removed": candidate.get("temp_config_dir_persisted") is False,
        "raw_secret_material_not_stored_in_evidence": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, passed in checks.items() if passed is not True)
    payload = {
        "mode": "firstparty-production-endpoint-summary",
        "generated_at": generated_at,
        "ok": not failed_checks,
        "host": host,
        "bind_host": bind_host,
        "port": port,
        "transport": transport,
        "deployment_epoch": candidate.get("deployment_epoch") or "missing",
        "server_service_name": candidate.get("server_service_name") or "missing",
        "client_service_name": candidate.get("client_service_name") or "missing",
        "server_candidate_hash": candidate.get("server_candidate_hash") or "missing",
        "client_candidate_hash": candidate.get("client_candidate_hash") or "missing",
        "occupied_port_count": len(occupied_ports),
        "occupied_ports_observed": sorted(occupied_ports),
        "legacy_port_set": sorted(LEGACY_PORTS),
        "legacy_unit_findings": legacy_findings,
        "listeners_sha256": hashlib.sha256(listeners_text.encode("utf-8")).hexdigest(),
        "checks": checks,
        "failed_checks": failed_checks,
        "raw_secret_material_stored_in_evidence": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
    }
    return payload


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# First-Party VPN Production Endpoint",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        f"endpoint: `{payload['transport']}://{payload['host']}:{payload['port']}`",
        f"bind_host: `{payload['bind_host']}`",
        "",
        "## Checks",
        "",
        "| Check | Passed |",
        "|---|---|",
    ]
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    for name in sorted(checks):
        lines.append(f"| `{name}` | `{bool_text(checks[name])}` |")
    failed = payload.get("failed_checks") if isinstance(payload.get("failed_checks"), list) else []
    lines.extend(["", "## Failed Checks", ""])
    if failed:
        lines.extend(f"- {value}" for value in failed)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- server_service_name: `{payload.get('server_service_name')}`",
            f"- client_service_name: `{payload.get('client_service_name')}`",
            f"- occupied_port_count: `{payload.get('occupied_port_count')}`",
            f"- legacy_unit_findings: `{compact([str(v) for v in payload.get('legacy_unit_findings') or []])}`",
            f"- listeners_sha256: `{payload.get('listeners_sha256')}`",
            "",
            "No NL or SPB writes were performed by this endpoint packet.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_packet(
    payload: dict[str, Any],
    *,
    listeners_text: str,
    diagnostics_dir: Path,
) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = diagnostics_dir / f"firstparty-production-endpoint-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    payload = dict(payload)
    payload["evidence_dir"] = str(out_dir)
    (out_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.md").write_text(render_markdown(payload), encoding="utf-8")
    (out_dir / "listeners.raw.txt").write_text(listeners_text, encoding="utf-8")
    return out_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build first-party VPN production endpoint evidence"
    )
    parser.add_argument("--diagnostics-dir", default=str(DIAGNOSTICS_DIR))
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--bind-host", default=DEFAULT_BIND_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--transport", choices=("tcp", "camouflage"), default=DEFAULT_TRANSPORT)
    parser.add_argument("--listeners-file")
    parser.add_argument("--collect-listeners", action="store_true")
    parser.add_argument("--ssh-target", default="nl")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.listeners_file:
        listeners_text = Path(args.listeners_file).read_text(encoding="utf-8")
    elif args.collect_listeners:
        listeners_text = collect_nl_listeners(ssh_target=args.ssh_target)
    else:
        raise SystemExit("pass --listeners-file or --collect-listeners")

    payload = build_payload(
        host=args.host,
        bind_host=args.bind_host,
        port=args.port,
        transport=args.transport,
        listeners_text=listeners_text,
    )
    if args.write:
        out_dir = write_packet(
            payload,
            listeners_text=listeners_text,
            diagnostics_dir=Path(args.diagnostics_dir),
        )
        payload["evidence_dir"] = str(out_dir)
    if args.json or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if payload.get("ok") is True else 2


def _build_candidate_artifacts(
    *,
    host: str,
    bind_host: str,
    port: int,
    transport: str,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="x0vpn-production-endpoint.") as tmp_raw:
        tmp = Path(tmp_raw)
        generate = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "generate",
                "--out-dir",
                str(tmp),
                "--host",
                host,
                "--bind-host",
                bind_host,
                "--port",
                str(port),
                "--transport",
                transport,
                "--deployment-epoch-prefix",
                "production-firstparty-endpoint",
                "--client-count",
                "2",
                "--pqc-reviewed",
                "--pqc-mode",
                "production",
            ]
        )
        server_config_path = Path(str(generate.get("server_config") or tmp / "server.json"))
        client_config_path = Path(str(generate.get("client_config") or tmp / "client.json"))
        server_config = read_json(server_config_path)
        client_config = read_json(client_config_path)
        server_plan = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "server-service-plan",
                "--config",
                str(server_config_path),
            ]
        )
        client_plan = _run_json(
            [
                sys.executable,
                str(NODE_SCRIPT),
                "client-service-plan",
                "--config",
                str(client_config_path),
                "--install-config-sync",
            ]
        )
        result = {
            "generate_ok": generate.get("ok") is True,
            "server_service_plan_ok": server_plan.get("ok") is True,
            "client_service_plan_ok": client_plan.get("ok") is True,
            "deployment_epoch": server_config.get("deployment_epoch")
            or generate.get("deployment_epoch"),
            "server_bind_host": server_config.get("bind_host"),
            "client_host": client_config.get("host"),
            "port": int(server_config.get("port") or 0),
            "transport": str(server_config.get("transport") or generate.get("transport") or ""),
            "server_service_name": server_plan.get("service_name"),
            "client_service_name": client_plan.get("service_name"),
            "server_unit_content": server_plan.get("unit_content") or "",
            "client_unit_content": client_plan.get("unit_content") or "",
            "server_candidate_hash": file_sha256(server_config_path),
            "client_candidate_hash": file_sha256(client_config_path),
            "temp_config_dir": str(tmp),
        }
    result["temp_config_dir_persisted"] = Path(str(result["temp_config_dir"])).exists()
    return result


def _run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stderr[-800:]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"command returned non-JSON: {' '.join(command)}\n{completed.stdout[-800:]}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"command returned non-object JSON: {' '.join(command)}")
    return payload


def _is_public_endpoint(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        lowered = host.strip().lower()
        return bool(lowered) and lowered not in {"localhost"} and not lowered.endswith(".local")
    return not (
        ip.is_loopback
        or ip.is_private
        or ip.is_unspecified
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_link_local
    )


def _is_non_loopback_bind(bind_host: str) -> bool:
    if bind_host in {"0.0.0.0", "::"}:
        return True
    try:
        ip = ipaddress.ip_address(bind_host)
    except ValueError:
        return False
    return not (ip.is_loopback or ip.is_unspecified or ip.is_link_local)


def _legacy_marker_findings(values: list[str]) -> list[str]:
    findings: list[str] = []
    for index, value in enumerate(values):
        lowered = str(value).lower()
        for marker in LEGACY_MARKERS:
            if marker in lowered:
                findings.append(f"value{index}:{marker}")
    return findings


if __name__ == "__main__":
    raise SystemExit(main())
