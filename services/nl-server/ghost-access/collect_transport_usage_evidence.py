#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT = Path("/var/lib/ghost-access/transport-usage/latest.json")
DEFAULT_HASH_KEY = Path("/var/lib/ghost-access/transport-usage/hash.key")
DEFAULT_WINDOW_MINUTES = (15, 60, 360)
DEFAULT_XRAY_LOGS = {
    "ghost_xhttp": [
        Path("/var/log/ghost-access/ghost-https-xhttp-access.log"),
    ],
    "ghost_https_ws": [
        Path("/var/log/ghost-access/ghost-https-ws-access.log"),
        Path("/var/log/ghost-access/nl-https-ws-access.log"),
    ],
}
DEFAULT_NGINX_LOG = Path("/var/log/nginx/access.log")

XRAY_RE = re.compile(
    r"^(?P<ts>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?) "
    r"from (?P<src>\S+) accepted (?P<network>tcp|udp):(?P<target>.+?):(?P<port>\d+) "
    r"\[(?P<tag>[^\]]+) >> [^\]]+\](?: email: (?P<email>.*))?$"
)
NGINX_RE = re.compile(
    r"^(?P<src>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "
    r'"(?P<method>\S+) (?P<path>\S+) [^"]+" (?P<status>\d{3}) (?P<size>\d+)'
    r'(?: "[^"]*" "(?P<user_agent>[^"]*)")?'
)


@dataclass(frozen=True)
class XrayEvent:
    ts: datetime
    transport: str
    client_hash: str | None
    network: str
    dest_port: str


@dataclass(frozen=True)
class NginxEvent:
    ts: datetime
    path: str
    status: str
    source_hash: str | None = None
    method: str = "unknown"
    user_agent_family: str = "unknown"


def parse_xray_ts(raw: str) -> datetime | None:
    for fmt in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def parse_nginx_ts(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw, "%d/%b/%Y:%H:%M:%S %z").astimezone(UTC)
    except ValueError:
        return None


def read_tail(path: Path, tail_lines: int) -> list[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-tail_lines:]


def ensure_hash_key(path: Path, *, create: bool) -> bytes | None:
    if path.exists():
        try:
            return path.read_bytes().strip()
        except OSError:
            return None
    if not create:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_bytes(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, key.hex().encode("ascii") + b"\n")
    finally:
        os.close(fd)
    return key.hex().encode("ascii")


def pseudonym(raw: str | None, key: bytes | None) -> str | None:
    if not raw or not key:
        return None
    return hmac.new(key, raw.strip().encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def user_agent_family(raw: str | None) -> str:
    lowered = (raw or "").strip().lower()
    if not lowered:
        return "empty"
    families = (
        ("xray", "xray"),
        ("v2ray", "v2ray"),
        ("sing-box", "sing-box"),
        ("singbox", "sing-box"),
        ("hiddify", "hiddify"),
        ("happ", "happ"),
        ("nekobox", "nekobox"),
        ("clash", "clash"),
        ("curl", "curl"),
        ("python", "python"),
        ("go-http-client", "go-http-client"),
        ("mozilla", "browser"),
    )
    for needle, family in families:
        if needle in lowered:
            return family
    return "other"


def parse_xray_line(line: str, *, transport: str, hash_key: bytes | None) -> XrayEvent | None:
    match = XRAY_RE.match(line.strip())
    if not match:
        return None
    ts = parse_xray_ts(match.group("ts"))
    if ts is None:
        return None
    email = (match.group("email") or "").strip()
    source = (match.group("src") or "").strip()
    client_identity = email or source
    return XrayEvent(
        ts=ts,
        transport=transport,
        client_hash=pseudonym(client_identity, hash_key),
        network=match.group("network"),
        dest_port=match.group("port"),
    )


def parse_nginx_line(line: str, *, hash_key: bytes | None = None) -> NginxEvent | None:
    match = NGINX_RE.match(line.strip())
    if not match:
        return None
    path = match.group("path").split("?", 1)[0]
    if path not in {"/ghost-xhttp", "/ghost-ws"}:
        return None
    ts = parse_nginx_ts(match.group("ts"))
    if ts is None:
        return None
    return NginxEvent(
        ts=ts,
        path=path,
        status=match.group("status"),
        source_hash=pseudonym((match.group("src") or "").strip(), hash_key),
        method=(match.group("method") or "unknown").upper(),
        user_agent_family=user_agent_family(match.group("user_agent")),
    )


def collect_xray_events(
    logs_by_transport: dict[str, list[Path]],
    *,
    hash_key: bytes | None,
    tail_lines: int,
) -> list[XrayEvent]:
    events: list[XrayEvent] = []
    for transport, paths in logs_by_transport.items():
        for path in paths:
            for line in read_tail(path, tail_lines):
                event = parse_xray_line(line, transport=transport, hash_key=hash_key)
                if event:
                    events.append(event)
    return events


def collect_nginx_events(path: Path, *, hash_key: bytes | None, tail_lines: int) -> list[NginxEvent]:
    return [
        event
        for line in read_tail(path, tail_lines)
        for event in [parse_nginx_line(line, hash_key=hash_key)]
        if event
    ]


def summarize_xray(events: list[XrayEvent], *, since: datetime) -> dict[str, Any]:
    recent = [event for event in events if event.ts >= since]
    by_transport: dict[str, dict[str, Any]] = {}
    for transport in sorted({event.transport for event in events} | set(DEFAULT_XRAY_LOGS)):
        subset = [event for event in recent if event.transport == transport]
        client_hashes = sorted({event.client_hash for event in subset if event.client_hash})
        by_transport[transport] = {
            "dataplane_events": len(subset),
            "unique_client_count": len(client_hashes),
            "client_hashes_sample": client_hashes[:10],
            "network_counts": dict(sorted(Counter(event.network for event in subset).items())),
            "dest_port_counts": dict(sorted(Counter(event.dest_port for event in subset).items())),
            "last_seen_at": max((event.ts for event in subset), default=None).isoformat().replace("+00:00", "Z")
            if subset
            else None,
        }
    return by_transport


def summarize_nginx(events: list[NginxEvent], *, since: datetime) -> dict[str, Any]:
    recent = [event for event in events if event.ts >= since]
    by_path: dict[str, dict[str, Any]] = {}
    for path in ("/ghost-xhttp", "/ghost-ws"):
        subset = [event for event in recent if event.path == path]
        source_hashes = sorted({event.source_hash for event in subset if event.source_hash})
        by_path[path] = {
            "requests": len(subset),
            "status_counts": dict(sorted(Counter(event.status for event in subset).items())),
            "method_counts": dict(sorted(Counter(event.method for event in subset).items())),
            "user_agent_family_counts": dict(
                sorted(Counter(event.user_agent_family for event in subset).items())
            ),
            "unique_proxy_source_count": len(source_hashes),
            "proxy_source_hashes_sample": source_hashes[:10],
            "last_seen_at": max((event.ts for event in subset), default=None).isoformat().replace("+00:00", "Z")
            if subset
            else None,
        }
    return by_path


def _status_family_count(status_counts: dict[str, Any], family_prefix: str) -> int:
    total = 0
    for status, count in status_counts.items():
        if str(status).startswith(family_prefix):
            try:
                total += int(count)
            except (TypeError, ValueError):
                continue
    return total


def _transport_attention_scope(
    *,
    transport_findings: list[str],
    proxy_requests: int,
    proxy_5xx: int,
    unique_proxy_source_count: int,
) -> str:
    if not transport_findings:
        return "none"
    if proxy_5xx > 0:
        return "legacy_proxy_server_error"
    if proxy_requests > 0 and unique_proxy_source_count <= 1:
        return "single_proxy_source"
    return "multiple_proxy_sources"


def _legacy_attention_summary(details: dict[str, dict[str, Any]], findings: list[str]) -> dict[str, Any]:
    all_proxy_source_hashes = sorted(
        {
            str(source_hash)
            for item in details.values()
            for source_hash in (item.get("proxy_source_hashes_sample") or [])
            if isinstance(source_hash, str) and source_hash
        }
    )
    aggregate_unique_proxy_source_count = len(all_proxy_source_hashes)
    proxy_requests = sum(int(item.get("proxy_requests") or 0) for item in details.values())
    dataplane_events = sum(int(item.get("dataplane_events") or 0) for item in details.values())
    max_unique_proxy_source_count = max(
        (int(item.get("unique_proxy_source_count") or 0) for item in details.values()),
        default=0,
    )
    if not findings:
        return {
            "severity": "none",
            "attention_scope": "none",
            "restart_relevant": False,
            "operator_action": "observe",
            "proxy_requests": proxy_requests,
            "dataplane_events": dataplane_events,
            "max_unique_proxy_source_count": max_unique_proxy_source_count,
            "aggregate_unique_proxy_source_count": aggregate_unique_proxy_source_count,
            "attention_unique_proxy_source_count": 0,
        }

    attention_transports = [
        item for item in details.values() if item.get("findings")
    ]
    has_5xx = any(int(item.get("proxy_5xx") or 0) > 0 for item in attention_transports)
    attention_proxy_source_hashes = sorted(
        {
            str(source_hash)
            for item in attention_transports
            for source_hash in (item.get("proxy_source_hashes_sample") or [])
            if isinstance(source_hash, str) and source_hash
        }
    )
    attention_unique_proxy_source_count = len(attention_proxy_source_hashes)
    all_single_source = all(
        int(item.get("unique_proxy_source_count") or 0) <= 1
        for item in attention_transports
        if int(item.get("proxy_requests") or 0) > 0
    ) and attention_unique_proxy_source_count <= 1

    if has_5xx:
        return {
            "severity": "legacy_proxy_server_error",
            "attention_scope": "legacy_proxy_server_error",
            "restart_relevant": True,
            "operator_action": "inspect_legacy_proxy_upstream_before_restart",
            "proxy_requests": proxy_requests,
            "dataplane_events": dataplane_events,
            "max_unique_proxy_source_count": max_unique_proxy_source_count,
            "aggregate_unique_proxy_source_count": aggregate_unique_proxy_source_count,
            "attention_unique_proxy_source_count": attention_unique_proxy_source_count,
        }
    if dataplane_events > 0:
        return {
            "severity": "legacy_dataplane_active_with_attention",
            "attention_scope": "mixed_legacy_dataplane_and_attention",
            "restart_relevant": False,
            "operator_action": "monitor_active_legacy_source_and_migrate_to_reality",
            "proxy_requests": proxy_requests,
            "dataplane_events": dataplane_events,
            "max_unique_proxy_source_count": max_unique_proxy_source_count,
            "aggregate_unique_proxy_source_count": aggregate_unique_proxy_source_count,
            "attention_unique_proxy_source_count": attention_unique_proxy_source_count,
        }
    if all_single_source and aggregate_unique_proxy_source_count <= 1:
        return {
            "severity": "single_source_stale_legacy",
            "attention_scope": "single_proxy_source",
            "restart_relevant": False,
            "operator_action": "monitor_single_stale_legacy_source_after_migration",
            "proxy_requests": proxy_requests,
            "dataplane_events": dataplane_events,
            "max_unique_proxy_source_count": max_unique_proxy_source_count,
            "aggregate_unique_proxy_source_count": aggregate_unique_proxy_source_count,
            "attention_unique_proxy_source_count": attention_unique_proxy_source_count,
        }
    return {
        "severity": "multi_source_legacy_attention",
        "attention_scope": "multiple_proxy_sources",
        "restart_relevant": False,
        "operator_action": "migrate_remaining_legacy_clients_to_reality",
        "proxy_requests": proxy_requests,
        "dataplane_events": dataplane_events,
        "max_unique_proxy_source_count": max_unique_proxy_source_count,
        "aggregate_unique_proxy_source_count": aggregate_unique_proxy_source_count,
        "attention_unique_proxy_source_count": attention_unique_proxy_source_count,
    }


def summarize_legacy_transport_health(
    *,
    xray_summary: dict[str, dict[str, Any]],
    nginx_summary: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    transports = {
        "ghost_xhttp": "/ghost-xhttp",
        "ghost_https_ws": "/ghost-ws",
    }
    details: dict[str, Any] = {}
    findings: list[str] = []
    for transport, path in transports.items():
        xray = xray_summary.get(transport) or {}
        nginx = nginx_summary.get(path) or {}
        status_counts = nginx.get("status_counts") if isinstance(nginx.get("status_counts"), dict) else {}
        proxy_requests = int(nginx.get("requests") or 0)
        dataplane_events = int(xray.get("dataplane_events") or 0)
        proxy_4xx = _status_family_count(status_counts, "4")
        proxy_5xx = _status_family_count(status_counts, "5")
        unique_proxy_source_count = int(nginx.get("unique_proxy_source_count") or 0)
        transport_findings: list[str] = []
        if proxy_requests > 0 and dataplane_events <= 0:
            transport_findings.append("legacy_proxy_requests_without_dataplane")
        if proxy_4xx > 0:
            transport_findings.append("legacy_proxy_4xx_seen")
        if proxy_5xx > 0:
            transport_findings.append("legacy_proxy_5xx_seen")
        if dataplane_events > 0:
            transport_status = "legacy_dataplane_seen"
        elif transport_findings:
            transport_status = "legacy_attention"
        else:
            transport_status = "no_legacy_traffic"
        findings.extend(f"{transport}:{item}" for item in transport_findings)
        details[transport] = {
            "path": path,
            "status": transport_status,
            "attention_scope": _transport_attention_scope(
                transport_findings=transport_findings,
                proxy_requests=proxy_requests,
                proxy_5xx=proxy_5xx,
                unique_proxy_source_count=unique_proxy_source_count,
            ),
            "restart_relevant": proxy_5xx > 0,
            "proxy_requests": proxy_requests,
            "proxy_4xx": proxy_4xx,
            "proxy_5xx": proxy_5xx,
            "unique_proxy_source_count": unique_proxy_source_count,
            "proxy_source_hashes_sample": nginx.get("proxy_source_hashes_sample")
            if isinstance(nginx.get("proxy_source_hashes_sample"), list)
            else [],
            "proxy_method_counts": nginx.get("method_counts") if isinstance(nginx.get("method_counts"), dict) else {},
            "proxy_user_agent_family_counts": nginx.get("user_agent_family_counts")
            if isinstance(nginx.get("user_agent_family_counts"), dict)
            else {},
            "dataplane_events": dataplane_events,
            "unique_client_count": int(xray.get("unique_client_count") or 0),
            "last_proxy_seen_at": nginx.get("last_seen_at"),
            "last_dataplane_seen_at": xray.get("last_seen_at"),
            "findings": transport_findings,
        }
    unique_findings = sorted(set(findings))
    attention_summary = _legacy_attention_summary(details, unique_findings)
    status = "attention" if unique_findings else "ok"
    return {
        "status": status,
        "ok": not unique_findings,
        "severity": attention_summary["severity"],
        "attention_scope": attention_summary["attention_scope"],
        "restart_relevant": attention_summary["restart_relevant"],
        "proxy_requests": attention_summary["proxy_requests"],
        "dataplane_events": attention_summary["dataplane_events"],
        "max_unique_proxy_source_count": attention_summary["max_unique_proxy_source_count"],
        "aggregate_unique_proxy_source_count": attention_summary["aggregate_unique_proxy_source_count"],
        "attention_unique_proxy_source_count": attention_summary["attention_unique_proxy_source_count"],
        "operator_action": attention_summary["operator_action"],
        "findings": unique_findings,
        "transports": details,
    }


def build_report(
    *,
    xray_events: list[XrayEvent],
    nginx_events: list[NginxEvent],
    windows: list[int],
    now: datetime | None = None,
    hash_key_present: bool,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    window_reports: dict[str, Any] = {}
    all_findings: list[str] = []
    for minutes in windows:
        since = now - timedelta(minutes=minutes)
        xray_summary = summarize_xray(xray_events, since=since)
        nginx_summary = summarize_nginx(nginx_events, since=since)
        legacy_health = summarize_legacy_transport_health(
            xray_summary=xray_summary,
            nginx_summary=nginx_summary,
        )
        all_findings.extend(f"{minutes}m:{item}" for item in legacy_health["findings"])
        window_reports[f"{minutes}m"] = {
            "since": since.isoformat().replace("+00:00", "Z"),
            "xray": xray_summary,
            "nginx": nginx_summary,
            "legacy_transport_health": legacy_health,
        }
    unique_findings = sorted(set(all_findings))
    primary_window_minutes = min(windows)
    primary_window_name = f"{primary_window_minutes}m"
    primary_health = (
        window_reports.get(primary_window_name, {}).get("legacy_transport_health")
        if isinstance(window_reports.get(primary_window_name), dict)
        else None
    )
    if not isinstance(primary_health, dict):
        primary_health = {
            "status": "unknown",
            "severity": "unknown",
            "attention_scope": "unknown",
            "restart_relevant": False,
            "proxy_requests": 0,
            "dataplane_events": 0,
            "max_unique_proxy_source_count": 0,
            "aggregate_unique_proxy_source_count": 0,
            "attention_unique_proxy_source_count": 0,
            "operator_action": "operator_review",
        }
    summary = {
        "recent_window_minutes": primary_window_minutes,
        "status": str(primary_health.get("status") or "unknown"),
        "severity": str(primary_health.get("severity") or "unknown"),
        "attention_scope": str(primary_health.get("attention_scope") or "unknown"),
        "restart_relevant": primary_health.get("restart_relevant") is True,
        "proxy_requests": int(primary_health.get("proxy_requests") or 0),
        "dataplane_events": int(primary_health.get("dataplane_events") or 0),
        "max_unique_proxy_source_count": int(primary_health.get("max_unique_proxy_source_count") or 0),
        "aggregate_unique_proxy_source_count": int(primary_health.get("aggregate_unique_proxy_source_count") or 0),
        "attention_unique_proxy_source_count": int(primary_health.get("attention_unique_proxy_source_count") or 0),
        "operator_action": str(primary_health.get("operator_action") or "operator_review"),
    }
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "source": "ghost-access-transport-usage-evidence",
        "ok": not unique_findings,
        "decision": "TRANSPORT_USAGE_OK" if not unique_findings else "TRANSPORT_USAGE_ATTENTION",
        "findings": unique_findings,
        "operator_action": summary["operator_action"],
        "summary": summary,
        "privacy": {
            "raw_identifiers_stored": False,
            "client_hashes_hmac_keyed": hash_key_present,
            "raw_ip_stored": False,
            "raw_nginx_source_ip_stored": False,
            "raw_email_stored": False,
            "raw_target_host_stored": False,
            "raw_user_agent_stored": False,
        },
        "windows": window_reports,
    }


def parse_windows(raw: str | None) -> list[int]:
    if not raw:
        return list(DEFAULT_WINDOW_MINUTES)
    values: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            value = int(chunk)
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return sorted(set(values)) or list(DEFAULT_WINDOW_MINUTES)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect privacy-safe Ghost Access transport usage evidence.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hash-key", type=Path, default=DEFAULT_HASH_KEY)
    parser.add_argument("--create-hash-key", action="store_true")
    parser.add_argument("--tail-lines", type=int, default=5000)
    parser.add_argument("--windows", default=",".join(str(item) for item in DEFAULT_WINDOW_MINUTES))
    parser.add_argument("--nginx-log", type=Path, default=DEFAULT_NGINX_LOG)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    hash_key = ensure_hash_key(args.hash_key, create=args.create_hash_key)
    xray_events = collect_xray_events(
        DEFAULT_XRAY_LOGS,
        hash_key=hash_key,
        tail_lines=max(1, args.tail_lines),
    )
    nginx_events = collect_nginx_events(
        args.nginx_log,
        hash_key=hash_key,
        tail_lines=max(1, args.tail_lines),
    )
    report = build_report(
        xray_events=xray_events,
        nginx_events=nginx_events,
        windows=parse_windows(args.windows),
        hash_key_present=hash_key is not None,
    )

    if args.write:
        write_json(args.output, report)
    if args.json or not args.write:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
