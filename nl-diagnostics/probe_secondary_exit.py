#!/usr/bin/env python3
"""Probe a future secondary VPN exit node from local evidence only.

The probe does not connect to NL or SPB and does not mutate local or remote
VPN runtime state. It accepts only public endpoint metadata, not VPN URIs,
UUIDs, private keys, bot tokens, or profile secrets.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import subprocess
import time
from typing import Any, Callable


SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.I),
    re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
)
PLACEHOLDER_TOKENS = ("REPLACE_", "TBD", "TODO", "example.invalid", "<")
DEFAULT_CONFIG = "nl-diagnostics/manual-failover-secondary.example.json"


def read_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("config must be a JSON object")
    validate_no_secrets(payload)
    return payload


def validate_no_secrets(value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError("config appears to contain a VPN secret or private credential")


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return any(token in text for token in PLACEHOLDER_TOKENS)


def normalized_ports(raw_ports: Any) -> list[int]:
    ports: list[int] = []
    if not isinstance(raw_ports, list):
        return ports
    for raw in raw_ports:
        try:
            port = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 < port < 65536 and port not in ports:
            ports.append(port)
    return ports


def tcp_probe(host: str, port: int, timeout: float) -> dict[str, Any]:
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        return {
            "host": host,
            "port": port,
            "ok": False,
            "latency_ms": None,
            "error": str(exc)[-200:],
        }
    return {
        "host": host,
        "port": port,
        "ok": True,
        "latency_ms": round((time.monotonic() - started) * 1000, 3),
        "error": "",
    }


def build_exit_ip_curl_command(url: str, socks_host: str, socks_port: int, timeout: float) -> list[str]:
    return [
        "curl",
        "-fsS",
        "--connect-timeout",
        str(min(timeout, 5.0)),
        "--max-time",
        str(timeout),
        "--proxy",
        f"socks5h://{socks_host}:{socks_port}",
        url,
    ]


def probe_client_exit_ip(
    client_probe: dict[str, Any],
    *,
    timeout: float,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    if not bool(client_probe.get("enabled", False)):
        return {
            "enabled": False,
            "ok": None,
            "reason": "client probe disabled; enable only after manual emergency profile activation on a test client",
        }

    socks_host = str(client_probe.get("socks_host") or "127.0.0.1").strip()
    socks_port = int(client_probe.get("socks_port") or 0)
    expected_exit_ip = str(client_probe.get("expected_exit_ip") or "").strip()
    url = str(client_probe.get("exit_ip_url") or "https://api.ipify.org").strip()
    if not socks_host or not 0 < socks_port < 65536:
        return {"enabled": True, "ok": False, "reason": "invalid socks_host/socks_port"}
    if is_placeholder(expected_exit_ip):
        return {"enabled": True, "ok": False, "reason": "expected_exit_ip is not configured"}
    if not url.startswith(("http://", "https://")):
        return {"enabled": True, "ok": False, "reason": "exit_ip_url must be http/https"}

    cmd = build_exit_ip_curl_command(url, socks_host, socks_port, timeout)
    completed = runner(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    observed = completed.stdout.strip().splitlines()[-1].strip() if completed.stdout.strip() else ""
    ok = completed.returncode == 0 and observed == expected_exit_ip
    return {
        "enabled": True,
        "ok": ok,
        "exit_code": completed.returncode,
        "expected_exit_ip": expected_exit_ip,
        "observed_exit_ip": observed or None,
        "stderr_tail": completed.stderr[-300:],
        "command_shape": "curl --proxy <redacted-socks> EXIT_IP_URL",
    }


def assess(candidate_configured: bool, tcp_results: list[dict[str, Any]], client_exit: dict[str, Any]) -> str:
    if not candidate_configured:
        return "planning_template"
    if tcp_results and not all(bool(row.get("ok")) for row in tcp_results):
        return "endpoint_degraded"
    if client_exit.get("enabled") is True:
        return "healthy" if client_exit.get("ok") is True else "client_exit_mismatch"
    if tcp_results and all(bool(row.get("ok")) for row in tcp_results):
        return "endpoint_reachable_profile_unverified"
    return "insufficient_data"


def build_payload(
    config: dict[str, Any],
    *,
    timeout: float = 3.0,
    connector: Callable[[str, int, float], dict[str, Any]] = tcp_probe,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    candidate = config.get("candidate") if isinstance(config.get("candidate"), dict) else {}
    client_probe = config.get("client_probe") if isinstance(config.get("client_probe"), dict) else {}
    host = str(candidate.get("host") or "").strip()
    ports = normalized_ports(candidate.get("tcp_ports"))
    candidate_configured = not is_placeholder(host) and bool(ports)

    tcp_results: list[dict[str, Any]] = []
    if candidate_configured:
        for port in ports:
            tcp_results.append(connector(host, port, timeout))

    client_exit = probe_client_exit_ip(client_probe, timeout=timeout, runner=runner)
    status = assess(candidate_configured, tcp_results, client_exit)
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/probe_secondary_exit.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "candidate": {
            "label": candidate.get("label", "secondary-placeholder"),
            "provider": candidate.get("provider", "TBD"),
            "region": candidate.get("region", "TBD"),
            "host": host if candidate_configured else "UNCONFIGURED",
            "tcp_ports": ports,
        },
        "candidate_configured": candidate_configured,
        "tcp_results": tcp_results,
        "client_exit_probe": client_exit,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe a future secondary VPN exit node")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--json-out")
    args = parser.parse_args()

    try:
        payload = build_payload(read_config(Path(args.config)), timeout=args.timeout)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        payload = {
            "schema_version": 1,
            "source": "nl-diagnostics/probe_secondary_exit.py",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "config_error",
            "error": str(exc),
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        }
        if args.json_out:
            Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 2

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["status"] in {"planning_template", "healthy", "endpoint_reachable_profile_unverified"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
