#!/usr/bin/env python3
"""Probe public NL transport ports from the local machine.

This is an outside-in TCP reachability probe. It does not SSH to NL/SPB and
does not mutate local or remote VPN runtime state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import time
from typing import Any, Callable


DEFAULT_HOST = "89.125.1.107"
DEFAULT_PORTS = (443, 2083, 39829)
DEFAULT_JSON_OUT = "nl-diagnostics/nl-transport-probe-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = "nl-diagnostics/nl-transport-probe-2026-05-28.md"


def parse_ports(values: list[str] | None) -> list[int]:
    if not values:
        return list(DEFAULT_PORTS)
    ports: list[int] = []
    for value in values:
        for raw in str(value).split(","):
            raw = raw.strip()
            if not raw:
                continue
            try:
                port = int(raw)
            except ValueError as exc:
                raise argparse.ArgumentTypeError(f"invalid port: {raw}") from exc
            if not 0 < port < 65536:
                raise argparse.ArgumentTypeError(f"port out of range: {port}")
            if port not in ports:
                ports.append(port)
    if not ports:
        raise argparse.ArgumentTypeError("at least one port is required")
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


def assess(results: list[dict[str, Any]]) -> str:
    if not results:
        return "insufficient_data"
    ok_count = sum(1 for row in results if row.get("ok") is True)
    if ok_count == len(results):
        return "healthy"
    if ok_count > 0:
        return "degraded"
    return "critical"


def build_payload(
    *,
    host: str = DEFAULT_HOST,
    ports: list[int] | None = None,
    timeout: float = 2.0,
    connector: Callable[[str, int, float], dict[str, Any]] = tcp_probe,
) -> dict[str, Any]:
    selected_ports = ports or list(DEFAULT_PORTS)
    results = [connector(host, port, timeout) for port in selected_ports]
    status = assess(results)
    ok_count = sum(1 for row in results if row.get("ok") is True)
    return {
        "schema_version": 1,
        "source": "nl-diagnostics/probe_nl_transport_ports.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": host,
        "ports": selected_ports,
        "status": status,
        "ok_count": ok_count,
        "port_count": len(results),
        "results": results,
        "failure_domain_hint": "none" if status == "healthy" else "nl_or_provider_or_path",
        "recommended_action": "observe" if status == "healthy" else "collect fresh read-only snapshot and compare NL listeners",
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# NL Transport Probe",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"host: `{payload['host']}`",
        "",
        "## Summary",
        "",
        "```text",
        f"status={payload.get('status')}",
        f"ok_count={payload.get('ok_count')}/{payload.get('port_count')}",
        f"failure_domain_hint={payload.get('failure_domain_hint')}",
        f"recommended_action={payload.get('recommended_action')}",
        "nl_mutation_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Ports",
        "",
        "| Port | OK | Latency ms | Error |",
        "|---|---|---:|---|",
    ]
    for row in payload["results"]:
        error = str(row.get("error") or "").replace("|", "/")
        lines.append(
            f"| `{row.get('port')}` | `{str(row.get('ok')).lower()}` | "
            f"`{row.get('latency_ms')}` | {error} |"
        )
    lines.extend(["", "No NL or SPB writes were performed by this transport probe."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe public NL transport TCP ports")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", action="append", help="Port or comma-separated ports. Defaults to 443,2083,39829.")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--json-out", default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", default=DEFAULT_MARKDOWN_OUT)
    args = parser.parse_args()

    payload = build_payload(host=args.host, ports=parse_ports(args.port), timeout=args.timeout)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
