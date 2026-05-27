#!/usr/bin/env python3
"""Create a safe secondary exit probe config from public endpoint metadata.

The generated file is for local health probing only. It must not contain VPN
profile URIs, UUIDs, private keys, bot tokens, or any NL/SPB mutation command.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


NL_IP = "89.125.1.107"
DEFAULT_EXIT_IP_URL = "https://api.ipify.org"
SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(?:vless|vmess|trojan|ss)://", re.I),
    re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),
)


def sanitize_label(value: str) -> str:
    label = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    if not label:
        raise ValueError("label is required")
    return label


def parse_ports(raw_ports: list[str]) -> list[int]:
    ports: list[int] = []
    for raw in raw_ports:
        for part in str(raw).replace(";", ",").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                port = int(part)
            except ValueError as exc:
                raise ValueError(f"invalid tcp port: {part}") from exc
            if not 0 < port < 65536:
                raise ValueError(f"tcp port out of range: {port}")
            if port not in ports:
                ports.append(port)
    if not ports:
        raise ValueError("at least one tcp port is required")
    return ports


def validate_no_secrets(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ValueError("generated config contains a forbidden secret-like value")


def validate_not_nl_or_spb(*, label: str, provider: str, region: str, host: str) -> None:
    combined = " ".join((label, provider, region, host)).lower()
    if "spb" in combined:
        raise ValueError("SPB is disabled and must not be used as secondary fallback")
    if host.strip() == NL_IP:
        raise ValueError("secondary host must not be the current NL exit IP")


def build_config(
    *,
    label: str,
    provider: str,
    region: str,
    host: str,
    tcp_ports: list[int],
    expected_exit_ip: str | None,
    enable_client_probe: bool,
    socks_host: str,
    socks_port: int,
    exit_ip_url: str,
) -> dict[str, Any]:
    label = sanitize_label(label)
    provider = provider.strip()
    region = region.strip()
    host = host.strip()
    expected_exit_ip = (expected_exit_ip or "").strip()
    socks_host = socks_host.strip()
    exit_ip_url = exit_ip_url.strip()

    if not provider or not region or not host:
        raise ValueError("provider, region, and host are required")
    if not 0 < socks_port < 65536:
        raise ValueError("socks port out of range")
    if not exit_ip_url.startswith(("http://", "https://")):
        raise ValueError("exit IP URL must be http/https")
    if enable_client_probe and not expected_exit_ip:
        raise ValueError("expected exit IP is required when client probe is enabled")

    validate_not_nl_or_spb(label=label, provider=provider, region=region, host=host)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Safe local secondary exit health probe config. No profile secrets are stored here.",
        "candidate": {
            "label": label,
            "provider": provider,
            "region": region,
            "host": host,
            "tcp_ports": tcp_ports,
        },
        "client_probe": {
            "enabled": enable_client_probe,
            "socks_host": socks_host,
            "socks_port": socks_port,
            "expected_exit_ip": expected_exit_ip or "REPLACE_WITH_SECONDARY_EXIT_IP",
            "exit_ip_url": exit_ip_url,
        },
        "policy": {
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
            "nl_write_allowed": False,
            "store_raw_vpn_uri": False,
        },
    }
    validate_no_secrets(payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a safe secondary exit probe config")
    parser.add_argument("--label", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--tcp-port", action="append", required=True)
    parser.add_argument("--expected-exit-ip")
    parser.add_argument("--enable-client-probe", action="store_true")
    parser.add_argument("--socks-host", default="127.0.0.1")
    parser.add_argument("--socks-port", type=int, default=10918)
    parser.add_argument("--exit-ip-url", default=DEFAULT_EXIT_IP_URL)
    parser.add_argument("--out")
    args = parser.parse_args()

    try:
        payload = build_config(
            label=args.label,
            provider=args.provider,
            region=args.region,
            host=args.host,
            tcp_ports=parse_ports(args.tcp_port),
            expected_exit_ip=args.expected_exit_ip,
            enable_client_probe=args.enable_client_probe,
            socks_host=args.socks_host,
            socks_port=args.socks_port,
            exit_ip_url=args.exit_ip_url,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, ensure_ascii=False))
        return 2

    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
