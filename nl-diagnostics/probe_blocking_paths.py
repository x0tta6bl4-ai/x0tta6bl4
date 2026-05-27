#!/usr/bin/env python3
"""Probe app/service reachability across direct, HTTP proxy, and SOCKS paths.

This script is local-only. It does not connect to NL over SSH and does not
mutate local or remote VPN state.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
from typing import Any


DEFAULT_TARGETS = (
    "connectivity=https://www.gstatic.com/generate_204",
    "telegram_web=https://web.telegram.org/",
    "telegram_api=https://api.telegram.org/",
    "russia_search=https://ya.ru/",
)
DEFAULT_SOCKS_PORTS = (10918, 10808, 10809, 10924, 40467, 1080, 7890, 7891)
OK_HTTP_CODES = {200, 204, 301, 302, 303, 307, 308, 401, 403, 404}
REJECT_HTTP_CODES = {403, 451}


@dataclass(frozen=True)
class Target:
    label: str
    kind: str
    url: str | None = None
    host: str | None = None
    port: int | None = None
    group: str = "default"


def parse_target(raw: str) -> Target:
    if "=" not in raw:
        raise argparse.ArgumentTypeError("target must be label=https://example or label=tcp://host:port")
    label, value = raw.split("=", 1)
    label = re.sub(r"[^a-zA-Z0-9_.-]+", "_", label.strip()).strip("_")
    value = value.strip()
    if not label:
        raise argparse.ArgumentTypeError("target label is empty")
    if value.startswith(("http://", "https://")):
        return Target(label=label, kind="http", url=value)
    if value.startswith("tcp://"):
        endpoint = value.removeprefix("tcp://")
        if ":" not in endpoint:
            raise argparse.ArgumentTypeError("tcp target must be tcp://host:port")
        host, raw_port = endpoint.rsplit(":", 1)
        try:
            port = int(raw_port)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("tcp target port must be an integer") from exc
        if not host or not 0 < port < 65536:
            raise argparse.ArgumentTypeError("tcp target must include a valid host and port")
        return Target(label=label, kind="tcp", host=host, port=port)
    raise argparse.ArgumentTypeError("target must start with http://, https://, or tcp://")


def load_targets_file(path: str) -> list[Target]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_targets = payload.get("targets") if isinstance(payload, dict) else payload
    if not isinstance(raw_targets, list):
        raise ValueError("targets file must contain a list or an object with a targets list")
    targets: list[Target] = []
    for item in raw_targets:
        if not isinstance(item, dict):
            raise ValueError("each target must be an object")
        label = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(item.get("label", "")).strip()).strip("_")
        kind = str(item.get("kind", "http")).strip().lower()
        group = re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(item.get("group", "default")).strip()).strip("_") or "default"
        if not label:
            raise ValueError("target label is required")
        if kind == "http":
            url = str(item.get("url", "")).strip()
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"http target {label} must include http/https URL")
            targets.append(Target(label=label, kind=kind, url=url, group=group))
        elif kind == "tcp":
            host = str(item.get("host", "")).strip()
            port = int(item.get("port", 0) or 0)
            if not host or not 0 < port < 65536:
                raise ValueError(f"tcp target {label} must include host and valid port")
            targets.append(Target(label=label, kind=kind, host=host, port=port, group=group))
        else:
            raise ValueError(f"unsupported target kind for {label}: {kind}")
    return targets


def detect_socks_port(host: str, ports: list[int], timeout: float) -> int | None:
    for port in ports:
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.send(b"\x05\x01\x00")
                if sock.recv(2) == b"\x05\x00":
                    return port
        except OSError:
            continue
    return None


def parse_curl_writeout(stdout: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for part in stdout.strip().split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key in {"code", "exitcode"}:
            try:
                values[key] = int(value)
            except ValueError:
                values[key] = None
        else:
            try:
                values[key] = float(value)
            except ValueError:
                values[key] = None
    return values


def build_curl_command(
    url: str,
    *,
    mode: str,
    timeout: float,
    socks_proxy: str | None,
    http_proxy: str | None,
) -> list[str]:
    cmd = [
        "curl",
        "-L",
        "-sS",
        "-o",
        "/dev/null",
        "--connect-timeout",
        str(min(timeout, 5.0)),
        "--max-time",
        str(timeout),
        "-w",
        "code=%{http_code} namelookup=%{time_namelookup} connect=%{time_connect} "
        "tls=%{time_appconnect} starttransfer=%{time_starttransfer} total=%{time_total}",
    ]
    if mode == "socks":
        if not socks_proxy:
            raise ValueError("socks mode requires socks_proxy")
        cmd.extend(["--proxy", socks_proxy])
    elif mode == "http_proxy":
        if not http_proxy:
            raise ValueError("http_proxy mode requires http_proxy")
        cmd.extend(["--proxy", http_proxy])
    elif mode != "direct":
        raise ValueError(f"unknown probe mode: {mode}")
    cmd.append(url)
    return cmd


def probe_url(
    target: Target,
    *,
    mode: str,
    timeout: float,
    attempts: int,
    socks_proxy: str | None,
    http_proxy: str | None,
    runner=subprocess.run,
) -> dict[str, Any]:
    try:
        if target.url is None:
            raise ValueError("http target requires url")
        cmd = build_curl_command(
            target.url,
            mode=mode,
            timeout=timeout,
            socks_proxy=socks_proxy,
            http_proxy=http_proxy,
        )
    except ValueError as exc:
        return {
            "label": target.label,
            "kind": target.kind,
            "url": target.url,
            "group": target.group,
            "mode": mode,
            "ok": False,
            "skipped": True,
            "reason": str(exc),
        }

    attempt_rows: list[dict[str, Any]] = []
    for attempt in range(1, max(1, attempts) + 1):
        completed = runner(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        metrics = parse_curl_writeout(completed.stdout)
        http_code = metrics.get("code")
        ok = completed.returncode == 0 and isinstance(http_code, int) and http_code in OK_HTTP_CODES
        row = {
            "attempt": attempt,
            "ok": ok,
            "exit_code": completed.returncode,
            "http_code": http_code,
            "metrics": {k: v for k, v in metrics.items() if k != "code"},
            "stderr_tail": completed.stderr[-300:],
        }
        attempt_rows.append(row)
        if ok:
            break

    selected = next((row for row in attempt_rows if row["ok"]), attempt_rows[-1])
    return {
        "label": target.label,
        "kind": target.kind,
        "group": target.group,
        "url": target.url,
        "mode": mode,
        "ok": selected["ok"],
        "exit_code": selected["exit_code"],
        "http_code": selected["http_code"],
        "metrics": selected["metrics"],
        "attempt_count": len(attempt_rows),
        "attempts": attempt_rows,
        "stderr_tail": selected["stderr_tail"],
        "command_shape": "curl --proxy <redacted> URL" if mode != "direct" else "curl URL",
    }


def socks5_connect(proxy_host: str, proxy_port: int, target_host: str, target_port: int, timeout: float) -> None:
    with socket.create_connection((proxy_host, proxy_port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(b"\x05\x01\x00")
        if sock.recv(2) != b"\x05\x00":
            raise OSError("SOCKS5 no-auth handshake failed")

        try:
            packed = socket.inet_pton(socket.AF_INET, target_host)
            request = b"\x05\x01\x00\x01" + packed
        except OSError:
            encoded = target_host.encode("idna")
            if len(encoded) > 255:
                raise OSError("SOCKS5 target hostname is too long")
            request = b"\x05\x01\x00\x03" + bytes([len(encoded)]) + encoded
        request += target_port.to_bytes(2, "big")
        sock.sendall(request)

        header = sock.recv(4)
        if len(header) != 4 or header[1] != 0:
            code = header[1] if len(header) >= 2 else "short"
            raise OSError(f"SOCKS5 connect failed: {code}")
        atyp = header[3]
        if atyp == 1:
            sock.recv(4)
        elif atyp == 3:
            length = sock.recv(1)[0]
            sock.recv(length)
        elif atyp == 4:
            sock.recv(16)
        sock.recv(2)


def probe_tcp(
    target: Target,
    *,
    mode: str,
    timeout: float,
    attempts: int,
    socks_host: str,
    socks_port: int | None,
) -> dict[str, Any]:
    if target.host is None or target.port is None:
        return {
            "label": target.label,
            "kind": target.kind,
            "group": target.group,
            "mode": mode,
            "ok": False,
            "skipped": True,
            "reason": "tcp target requires host and port",
        }

    if mode == "http_proxy":
        return {
            "label": target.label,
            "kind": target.kind,
            "group": target.group,
            "host": target.host,
            "port": target.port,
            "mode": mode,
            "ok": False,
            "skipped": True,
            "reason": "tcp over HTTP proxy is not implemented",
        }

    attempt_rows: list[dict[str, Any]] = []
    for attempt in range(1, max(1, attempts) + 1):
        started = datetime.now(timezone.utc)
        try:
            if mode == "direct":
                with socket.create_connection((target.host, target.port), timeout=timeout):
                    pass
            elif mode == "socks":
                if socks_port is None:
                    raise OSError("socks mode requires detected socks port")
                socks5_connect(socks_host, socks_port, target.host, target.port, timeout)
            else:
                raise OSError(f"unknown probe mode: {mode}")
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            attempt_rows.append({"attempt": attempt, "ok": True, "metrics": {"connect": elapsed, "total": elapsed}})
            break
        except OSError as exc:
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            attempt_rows.append(
                {
                    "attempt": attempt,
                    "ok": False,
                    "metrics": {"connect": elapsed, "total": elapsed},
                    "error": str(exc)[-300:],
                }
            )

    selected = next((row for row in attempt_rows if row["ok"]), attempt_rows[-1])
    return {
        "label": target.label,
        "kind": target.kind,
        "group": target.group,
        "host": target.host,
        "port": target.port,
        "mode": mode,
        "ok": selected["ok"],
        "metrics": selected["metrics"],
        "attempt_count": len(attempt_rows),
        "attempts": attempt_rows,
        "error": selected.get("error"),
        "command_shape": "tcp connect via SOCKS" if mode == "socks" else "tcp connect",
    }


def classify_target(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_mode = {str(row.get("mode")): row for row in rows}
    direct = by_mode.get("direct", {})
    socks = by_mode.get("socks", {})
    http_proxy = by_mode.get("http_proxy", {})

    direct_ok = bool(direct.get("ok"))
    socks_ok = bool(socks.get("ok"))
    http_proxy_ok = bool(http_proxy.get("ok"))
    socks_code = socks.get("http_code")
    http_proxy_code = http_proxy.get("http_code")

    if direct_ok and socks_ok:
        assessment = "ok"
    elif direct_ok and (socks_code in REJECT_HTTP_CODES or http_proxy_code in REJECT_HTTP_CODES):
        assessment = "exit_ip_or_vpn_rejected"
    elif direct_ok and not socks_ok:
        assessment = "vpn_path_degraded"
    elif not direct_ok and (socks_ok or http_proxy_ok):
        assessment = "possible_local_isp_block"
    elif not direct_ok and not socks_ok and not http_proxy_ok:
        assessment = "target_or_global_unreachable"
    else:
        assessment = "mixed"

    return {
        "label": str(rows[0].get("label", "unknown")) if rows else "unknown",
        "kind": str(rows[0].get("kind", "unknown")) if rows else "unknown",
        "group": str(rows[0].get("group", "default")) if rows else "default",
        "assessment": assessment,
        "direct_ok": direct_ok,
        "socks_ok": socks_ok,
        "http_proxy_ok": http_proxy_ok,
        "direct_http_code": direct.get("http_code"),
        "socks_http_code": socks.get("http_code"),
        "http_proxy_http_code": http_proxy.get("http_code"),
    }


def summarize(target_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    assessments = [str(item.get("assessment")) for item in target_summaries]
    if not target_summaries:
        overall = "no_targets"
    elif any(item.get("assessment") == "exit_ip_or_vpn_rejected" for item in target_summaries):
        overall = "exit_ip_or_vpn_rejected"
    elif any(item.get("assessment") == "possible_local_isp_block" for item in target_summaries):
        overall = "possible_local_isp_block"
    elif any(item.get("assessment") == "vpn_path_degraded" for item in target_summaries):
        overall = "vpn_path_degraded"
    elif any(item.get("assessment") == "target_or_global_unreachable" for item in target_summaries):
        overall = "app_specific_degradation"
    elif all(item.get("assessment") == "ok" for item in target_summaries):
        overall = "no_probe_evidence"
    else:
        overall = "mixed"

    return {
        "assessment": overall,
        "target_count": len(target_summaries),
        "target_assessments": dict(sorted((label, assessments.count(label)) for label in set(assessments))),
        "group_assessments": summarize_groups(target_summaries),
    }


def summarize_groups(target_summaries: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    groups: dict[str, dict[str, int]] = {}
    for item in target_summaries:
        group = str(item.get("group") or "default")
        assessment = str(item.get("assessment") or "unknown")
        groups.setdefault(group, {})
        groups[group][assessment] = groups[group].get(assessment, 0) + 1
    return dict(sorted((group, dict(sorted(values.items()))) for group, values in groups.items()))


def parse_ports(value: str) -> list[int]:
    ports: list[int] = []
    for raw in value.replace(";", ",").split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            port = int(raw)
        except ValueError:
            continue
        if 0 < port < 65536 and port not in ports:
            ports.append(port)
    return ports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe app blocking paths locally")
    parser.add_argument("--target", action="append", type=parse_target, help="label=https://example; repeatable")
    parser.add_argument("--targets-file", default=os.environ.get("VPN_BLOCKING_TARGETS_FILE", ""))
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("VPN_BLOCKING_PROBE_TIMEOUT", "6")))
    parser.add_argument("--attempts", type=int, default=int(os.environ.get("VPN_BLOCKING_PROBE_ATTEMPTS", "2")))
    parser.add_argument("--socks-host", default=os.environ.get("VPN_SOCKS_HOST", "127.0.0.1"))
    parser.add_argument("--socks-port", type=int, default=int(os.environ["VPN_SOCKS_PORT"]) if os.environ.get("VPN_SOCKS_PORT") else None)
    parser.add_argument("--socks-port-candidates", default=os.environ.get("VPN_SOCKS_PORT_CANDIDATES", ",".join(str(p) for p in DEFAULT_SOCKS_PORTS)))
    parser.add_argument("--http-proxy", default=os.environ.get("VPN_HTTP_PROXY_URL") or os.environ.get("VPN_AGENT_PROXY_URL") or "")
    args = parser.parse_args(argv)

    if args.target:
        targets = args.target
        targets_source = "argv"
    elif args.targets_file:
        targets = load_targets_file(args.targets_file)
        targets_source = args.targets_file
    else:
        targets = [parse_target(raw) for raw in DEFAULT_TARGETS]
        targets_source = "defaults"
    socks_port = args.socks_port
    if socks_port is None:
        socks_port = detect_socks_port(args.socks_host, parse_ports(args.socks_port_candidates), timeout=1.0)

    socks_proxy = f"socks5h://{args.socks_host}:{socks_port}" if socks_port else None
    http_proxy = args.http_proxy.strip() or None
    modes = ["direct"]
    if http_proxy:
        modes.append("http_proxy")
    modes.append("socks")

    probes: list[dict[str, Any]] = []
    by_target: dict[str, list[dict[str, Any]]] = {}
    for target in targets:
        rows: list[dict[str, Any]] = []
        for mode in modes:
            if target.kind == "http":
                row = probe_url(
                    target,
                    mode=mode,
                    timeout=args.timeout,
                    attempts=args.attempts,
                    socks_proxy=socks_proxy,
                    http_proxy=http_proxy,
                )
            elif target.kind == "tcp":
                row = probe_tcp(
                    target,
                    mode=mode,
                    timeout=args.timeout,
                    attempts=args.attempts,
                    socks_host=args.socks_host,
                    socks_port=socks_port,
                )
            else:
                row = {
                    "label": target.label,
                    "kind": target.kind,
                    "group": target.group,
                    "mode": mode,
                    "ok": False,
                    "skipped": True,
                    "reason": f"unsupported target kind: {target.kind}",
                }
            probes.append(row)
            rows.append(row)
        by_target[target.label] = rows

    target_summaries = [classify_target(rows) for rows in by_target.values()]
    payload = {
        "schema_version": 1,
        "source": "nl-diagnostics/probe_blocking_paths.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "socks_proxy_detected": bool(socks_proxy),
        "socks_host": args.socks_host,
        "socks_port": socks_port,
        "http_proxy_configured": bool(http_proxy),
        "modes": modes,
        "targets_source": targets_source,
        "summary": summarize(target_summaries),
        "targets": target_summaries,
        "probes": probes,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
