#!/usr/bin/env python3
"""Probe popular services via direct/http-proxy/socks and recommend VPN improvements."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import socket
import sqlite3
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


DEFAULT_PROXY = os.environ.get("VPN_AGENT_PROXY_URL", "http://127.0.0.1:10918")
DEFAULT_SOCKS = os.environ.get("VPN_AGENT_SOCKS_URL", "socks5://127.0.0.1:10918")
DEFAULT_TIMEOUT = float(os.environ.get("VPN_AGENT_TIMEOUT_SEC", "12"))
DEFAULT_REPORT_DIR = Path(
    os.environ.get("VPN_SERVICE_AGENT_REPORT_DIR", str(Path.home() / ".local/state/vpn-service-access-agent"))
)
DEFAULT_OUTPUT = os.environ.get("VPN_SERVICE_AGENT_OUTPUT", "")
DEFAULT_CONFIG_PATH = Path(
    os.environ.get(
        "VPN_LOCAL_SINGBOX_CONFIG",
        str(Path.home() / ".local/share/v2rayN/binConfigs/configPre.json"),
    )
)
DEFAULT_SUBSCRIPTION_CHECK_URL = os.environ.get("VPN_AGENT_SUBSCRIPTION_CHECK_URL", "").strip()
DEFAULT_GHOST_DB_PATH = Path(
    os.environ.get("VPN_AGENT_GHOST_DB_PATH", "/opt/ghost-access-bot/shared/x0tta6bl4.db")
)
DEFAULT_SUBSCRIPTION_BASE_URL = os.environ.get("VPN_AGENT_SUBSCRIPTION_BASE_URL", "").strip()
DEFAULT_ENV_FILE = Path(
    os.environ.get("VPN_AGENT_ENV_FILE", "/opt/ghost-access-bot/shared/.env")
)
DEFAULT_VPN_HOST = os.environ.get("VPN_AGENT_VPN_HOST", "127.0.0.1")
DEFAULT_VPN_PORT = int(os.environ.get("VPN_AGENT_VPN_PORT", "443"))
DEFAULT_XUI_DB_PATH = Path(os.environ.get("VPN_AGENT_XUI_DB_PATH", "/etc/x-ui/x-ui.db"))
DEFAULT_XUI_INBOUND_PORT = int(os.environ.get("VPN_AGENT_XUI_INBOUND_PORT", "443"))
DEFAULT_VPN_DELIVERY_CANARY = os.environ.get("VPN_AGENT_VPN_DELIVERY_CANARY", "").strip()
DEFAULT_SECONDARY_VPN_HOST = os.environ.get("VPN_AGENT_SECONDARY_VPN_HOST", DEFAULT_VPN_HOST)
DEFAULT_SECONDARY_VPN_PORT = int(os.environ.get("VPN_AGENT_SECONDARY_VPN_PORT", "2083"))
DEFAULT_SECONDARY_XUI_INBOUND_PORT = int(os.environ.get("VPN_AGENT_SECONDARY_XUI_INBOUND_PORT", str(DEFAULT_SECONDARY_VPN_PORT)))
DEFAULT_SECONDARY_VPN_DELIVERY_CANARY = os.environ.get("VPN_AGENT_SECONDARY_VPN_DELIVERY_CANARY", "").strip()
DEFAULT_FALLBACK_VPN_HOST = os.environ.get("VPN_AGENT_FALLBACK_VPN_HOST", "")
DEFAULT_FALLBACK_VPN_PORT = int(os.environ.get("VPN_AGENT_FALLBACK_VPN_PORT", "2443"))
DEFAULT_FALLBACK_VPN_DELIVERY_CANARY = os.environ.get("VPN_AGENT_FALLBACK_VPN_DELIVERY_CANARY", "").strip()
DEFAULT_TELEGRAM_MEDIA_TARGETS = os.environ.get(
    "VPN_AGENT_TELEGRAM_MEDIA_TARGETS",
    "149.154.167.222:443,149.154.166.111:443,91.105.192.100:443,91.108.56.161:443",
).strip()
DEFAULT_TELEGRAM_ACCESS_LOG = os.environ.get("VPN_AGENT_TELEGRAM_ACCESS_LOG", "/var/log/xray/access.log").strip()
DEFAULT_TELEGRAM_TARGET_LIMIT = int(os.environ.get("VPN_AGENT_TELEGRAM_TARGET_LIMIT", "4"))


SERVICE_CATALOG: list[dict[str, str]] = [
    {"service_id": "youtube", "category": "media", "url": "https://www.youtube.com"},
    {"service_id": "chatgpt", "category": "ai", "url": "https://api.openai.com/v1/models"},
    {"service_id": "claude", "category": "ai", "url": "https://api.anthropic.com/v1/messages"},
    {"service_id": "github", "category": "dev", "url": "https://github.com"},
    {"service_id": "copilot", "category": "ai-dev", "url": "https://api.githubcopilot.com"},
    {"service_id": "windsurf", "category": "ai-dev", "url": "https://server.self-serve.windsurf.com"},
    {"service_id": "codeium", "category": "ai-dev", "url": "https://inference.codeium.com"},
    {"service_id": "kilo", "category": "ai-dev", "url": "https://app.kilo.ai"},
    {"service_id": "telegram-web", "category": "messenger", "url": "https://web.telegram.org"},
    {"service_id": "x-twitter", "category": "social", "url": "https://x.com"},
]


@dataclass
class ProbeResult:
    mode: str
    http_code: int | None
    total_s: float | None
    connect_s: float | None
    tls_s: float | None
    start_s: float | None
    ok: bool
    command_error: str | None = None


@dataclass
class TcpProbeResult:
    host: str
    port: int
    ok: bool
    connect_s: float | None
    error: str | None = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe popular services and recommend VPN improvements.")
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--socks", default=DEFAULT_SOCKS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--only")
    parser.add_argument("--config-path", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--subscription-check-url", default=DEFAULT_SUBSCRIPTION_CHECK_URL)
    parser.add_argument("--ghost-db-path", type=Path, default=DEFAULT_GHOST_DB_PATH)
    parser.add_argument("--subscription-base-url", default=DEFAULT_SUBSCRIPTION_BASE_URL)
    parser.add_argument("--vpn-host", default=DEFAULT_VPN_HOST)
    parser.add_argument("--vpn-port", type=int, default=DEFAULT_VPN_PORT)
    parser.add_argument("--xui-db-path", type=Path, default=DEFAULT_XUI_DB_PATH)
    parser.add_argument("--xui-inbound-port", type=int, default=DEFAULT_XUI_INBOUND_PORT)
    parser.add_argument("--vpn-delivery-canary", default=DEFAULT_VPN_DELIVERY_CANARY)
    parser.add_argument("--secondary-vpn-host", default=DEFAULT_SECONDARY_VPN_HOST)
    parser.add_argument("--secondary-vpn-port", type=int, default=DEFAULT_SECONDARY_VPN_PORT)
    parser.add_argument("--secondary-xui-inbound-port", type=int, default=DEFAULT_SECONDARY_XUI_INBOUND_PORT)
    parser.add_argument("--secondary-vpn-delivery-canary", default=DEFAULT_SECONDARY_VPN_DELIVERY_CANARY)
    parser.add_argument("--fallback-vpn-host", default=DEFAULT_FALLBACK_VPN_HOST)
    parser.add_argument("--fallback-vpn-port", type=int, default=DEFAULT_FALLBACK_VPN_PORT)
    parser.add_argument("--fallback-vpn-delivery-canary", default=DEFAULT_FALLBACK_VPN_DELIVERY_CANARY)
    parser.add_argument("--telegram-media-targets", default=DEFAULT_TELEGRAM_MEDIA_TARGETS)
    parser.add_argument("--telegram-access-log", default=DEFAULT_TELEGRAM_ACCESS_LOG)
    parser.add_argument("--telegram-target-limit", type=int, default=DEFAULT_TELEGRAM_TARGET_LIMIT)
    return parser


def _curl_probe(url: str, timeout: float, mode: str, proxy: str | None = None, socks: str | None = None) -> ProbeResult:
    fmt = "code=%{http_code} connect=%{time_connect} tls=%{time_appconnect} start=%{time_starttransfer} total=%{time_total}"
    cmd = ["curl", "-4", "-s", "-o", "/dev/null", "-w", fmt, "--max-time", str(timeout)]
    if proxy:
        cmd.extend(["--proxy", proxy])
    if socks:
        cmd.extend(["--proxy", socks])
    cmd.append(url)
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if completed.returncode != 0:
        return ProbeResult(
            mode=mode,
            http_code=None,
            total_s=None,
            connect_s=None,
            tls_s=None,
            start_s=None,
            ok=False,
            command_error=(completed.stderr or completed.stdout).strip() or f"curl exited {completed.returncode}",
        )

    raw = (completed.stdout or "").strip()
    metrics: dict[str, str] = {}
    for part in raw.split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        metrics[key] = value
    code = int(metrics.get("code", "0"))
    return ProbeResult(
        mode=mode,
        http_code=code,
        total_s=float(metrics.get("total", "0") or 0),
        connect_s=float(metrics.get("connect", "0") or 0),
        tls_s=float(metrics.get("tls", "0") or 0),
        start_s=float(metrics.get("start", "0") or 0),
        ok=200 <= code < 500,
        command_error=None,
    )


def _load_quic_reject(config_path: Path) -> bool:
    if not config_path.exists():
        return False
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    rules = ((payload.get("route") or {}).get("rules")) or []
    for rule in rules:
        if rule.get("action") == "reject" and rule.get("network") == ["udp"] and rule.get("port") == [443]:
            return True
    return False


def _tcp_probe(host: str, port: int, timeout: float) -> TcpProbeResult:
    started = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return TcpProbeResult(host=host, port=port, ok=True, connect_s=round(time.time() - started, 4), error=None)
    except Exception as exc:
        return TcpProbeResult(host=host, port=port, ok=False, connect_s=None, error=str(exc))
    finally:
        try:
            sock.close()
        except Exception:
            pass


def _extract_recent_telegram_targets_from_access_log(path: str, limit: int) -> list[str]:
    log_path = Path(path)
    if not log_path.exists():
        return []
    prefixes = ("149.154.", "91.108.", "91.105.")
    found: list[str] = []
    seen: set[str] = set()
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        marker = "accepted tcp:"
        start = line.find(marker)
        if start < 0:
            continue
        endpoint = line[start + len(marker):].split(" ", 1)[0].strip()
        if ":" not in endpoint:
            continue
        host, _port = endpoint.rsplit(":", 1)
        if not host.startswith(prefixes):
            continue
        normalized = f"{host}:443"
        if normalized in seen:
            continue
        seen.add(normalized)
        found.append(normalized)
        if len(found) >= max(1, limit):
            break
    return found


def _resolve_telegram_media_targets(args: argparse.Namespace) -> list[str]:
    explicit = [
        item.strip()
        for item in str(getattr(args, "telegram_media_targets", "") or "").split(",")
        if item.strip()
    ]
    if explicit:
        return explicit
    derived = _extract_recent_telegram_targets_from_access_log(
        str(getattr(args, "telegram_access_log", "") or ""),
        int(getattr(args, "telegram_target_limit", 4) or 4),
    )
    return derived


def _build_telegram_media_summary(args: argparse.Namespace) -> dict[str, Any]:
    targets = _resolve_telegram_media_targets(args)
    if not targets:
        return {
            "configured": False,
            "status": "not-configured",
            "targets": {},
            "best_target": None,
            "best_latency_s": None,
            "worst_target": None,
            "worst_latency_s": None,
            "latency_spread_s": None,
            "healthy_target_count": 0,
            "total_target_count": 0,
        }

    target_payloads: dict[str, dict[str, Any]] = {}
    latencies: list[tuple[str, float]] = []
    for target in targets:
        if ":" not in target:
            host, port = target, 443
        else:
            host, raw_port = target.rsplit(":", 1)
            try:
                port = int(raw_port)
            except ValueError:
                port = 443
        probe = _tcp_probe(host, port, args.timeout)
        target_payloads[target] = asdict(probe)
        if probe.ok and probe.connect_s is not None:
            latencies.append((target, float(probe.connect_s)))

    if not latencies:
        status = "unhealthy"
        best_target = None
        best_latency = None
        worst_target = None
        worst_latency = None
        spread = None
    else:
        ordered = sorted(latencies, key=lambda item: item[1])
        best_target, best_latency = ordered[0]
        worst_target, worst_latency = ordered[-1]
        spread = round(float(worst_latency) - float(best_latency), 3)
        if float(worst_latency) >= 0.18 or spread >= 0.12:
            status = "degraded"
        elif float(worst_latency) >= 0.08 or spread >= 0.05:
            status = "advisory"
        else:
            status = "healthy"

    return {
        "configured": True,
        "status": status,
        "targets": target_payloads,
        "best_target": best_target,
        "best_latency_s": round(float(best_latency), 3) if best_latency is not None else None,
        "worst_target": worst_target,
        "worst_latency_s": round(float(worst_latency), 3) if worst_latency is not None else None,
        "latency_spread_s": spread,
        "healthy_target_count": len(latencies),
        "total_target_count": len(targets),
    }


def _load_xui_inbound_snapshot(db_path: Path, inbound_port: int) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "db_path": str(db_path),
        "inbound_port": inbound_port,
        "ok": False,
        "client_count": None,
        "inbound_id": None,
        "remark": None,
        "error": None,
    }
    if not db_path.exists():
        snapshot["error"] = "xui-db-missing"
        return snapshot
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT id, remark, settings FROM inbounds WHERE port=? ORDER BY id LIMIT 1",
                (inbound_port,),
            ).fetchone()
        if not row:
            snapshot["error"] = "inbound-not-found"
            return snapshot
        inbound_id, remark, settings_raw = row
        settings = json.loads(settings_raw or "{}")
        clients = settings.get("clients") or []
        snapshot.update(
            {
                "ok": True,
                "inbound_id": inbound_id,
                "remark": remark,
                "client_count": len(clients),
            }
        )
        return snapshot
    except Exception as exc:
        snapshot["error"] = str(exc)
        return snapshot


def _run_vpn_delivery_canary(command: str) -> dict[str, Any]:
    if not command.strip():
        return {"ok": None, "error": "not-configured"}
    completed = subprocess.run(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        raw = (completed.stdout or "").strip()
        if not raw:
            return {"ok": False, "error": "empty-stdout", "command_error": None}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"ok": False, "error": "invalid-json", "raw": raw}
        payload["command_error"] = None
        return payload
    try:
        payload = json.loads((completed.stdout or "").strip() or "{}")
    except json.JSONDecodeError:
        payload = {}
    payload["ok"] = False
    payload["command_error"] = (completed.stderr or completed.stdout).strip() or f"exit={completed.returncode}"
    return payload


def _derive_secondary_canary_command(command: str, secondary_port: int) -> str:
    if not command.strip():
        return ""
    if "--inbound-port" in command:
        return command
    return f"{command} --inbound-port {secondary_port}"


def _read_env_file_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        env_key, value = line.split("=", 1)
        if env_key.strip() == key:
            return value.strip().strip("'").strip('"')
    return ""


def _resolve_subscription_check_url(args: argparse.Namespace) -> str:
    raw = (args.subscription_check_url or "").strip()
    if raw and raw.lower() not in {"auto", "latest", "db"}:
        return raw

    base_url = (args.subscription_base_url or "").strip() or _read_env_file_value(
        DEFAULT_ENV_FILE, "SUBSCRIPTION_BASE_URL"
    )
    if not base_url:
        return raw

    db_path = args.ghost_db_path
    if not db_path.exists():
        return raw

    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT subscription_token
                FROM users
                WHERE subscription_token IS NOT NULL
                  AND COALESCE(TRIM(subscription_token), '') != ''
                ORDER BY subscription_updated_at DESC, user_id DESC
                LIMIT 1
                """
            ).fetchone()
    except Exception:
        return raw

    if not row or not row[0]:
        return raw

    token = str(row[0]).strip()
    if not token:
        return raw

    return f"{base_url.rstrip('/')}/sub/{token}?format=raw"


def _recommend_for_service(service: dict[str, str], direct: ProbeResult, proxy: ProbeResult, socks: ProbeResult, quic_reject: bool) -> list[str]:
    recs: list[str] = []
    service_id = service["service_id"]
    category = service["category"]

    if not direct.ok and (proxy.ok or socks.ok):
        recs.append(f"route:{service_id}: direct path is unhealthy; keep this service on VPN by default")

    if direct.http_code == 403 and socks.ok and socks.http_code != 403:
        recs.append(f"anonymity:{service_id}: direct path returns 403 while socks path works; force SOCKS5 for this client/app")

    if proxy.ok and direct.ok and proxy.total_s and direct.total_s and proxy.total_s - direct.total_s > 0.8:
        recs.append(f"speed:{service_id}: HTTP proxy adds >800ms; inspect proxy route, outbound port, and DNS strategy")

    if socks.ok and direct.ok and socks.total_s and direct.total_s and socks.total_s - direct.total_s > 0.8:
        recs.append(f"speed:{service_id}: SOCKS path adds >800ms; consider alternate outbound or split route tuning")

    if category == "media" and quic_reject:
        recs.append(f"stability:{service_id}: local QUIC is blocked (udp/443 reject); allow QUIC to reduce startup latency and buffering")

    if category in {"ai", "ai-dev"} and socks.ok:
        recs.append(f"anonymity:{service_id}: prefer SOCKS5 for editor/CLI traffic to keep provider access on VPN path")

    if category == "vpn-control":
        if not direct.ok:
            recs.append(f"stability:{service_id}: subscription endpoint is unhealthy on direct path")
        elif direct.total_s and direct.total_s > 1.2:
            recs.append(f"speed:{service_id}: subscription endpoint is slow on direct path; investigate nginx/bot latency")

    if not any([direct.ok, proxy.ok, socks.ok]):
        recs.append(f"stability:{service_id}: all probe modes failed; check DNS resolution, endpoint changes, or provider-side blocking")

    return recs


def _service_summary(service: dict[str, str], probes: dict[str, ProbeResult], recs: list[str]) -> dict[str, Any]:
    if service["service_id"] == "subscription-edge":
        for probe in probes.values():
            probe.ok = probe.http_code == 200

    best_mode = None
    healthy = [probe for probe in probes.values() if probe.ok and probe.total_s is not None]
    if healthy:
        best_mode = min(healthy, key=lambda item: item.total_s or 999).mode
    return {
        "service_id": service["service_id"],
        "category": service["category"],
        "url": service["url"],
        "best_mode": best_mode,
        "availability": {key: asdict(value) for key, value in probes.items()},
        "recommendations": recs,
    }


def _global_recommendations(
    services: list[dict[str, Any]],
    telegram_media: dict[str, Any] | None = None,
) -> list[str]:
    recs: list[str] = []
    if any("route:" in rec for service in services for rec in service["recommendations"]):
        recs.append("routing: maintain a curated domain allowlist for blocked/popular services and pin them to VPN")
    if any("anonymity:" in rec for service in services for rec in service["recommendations"]):
        recs.append("anonymity: prefer SOCKS5 for browsers, IDEs, and AI tools instead of mixed direct/proxy fallback")
    if any("speed:" in rec for service in services for rec in service["recommendations"]):
        recs.append("speed: compare direct/http/socks paths periodically and switch hot services to the fastest healthy mode")
    if any("stability:" in rec for service in services for rec in service["recommendations"]):
        recs.append("stability: surface config drifts like QUIC blocks, stale routes, and dead proxy ports as first-class alerts")
    telegram_status = str((telegram_media or {}).get("status") or "")
    if telegram_status == "advisory":
        recs.append("telegram-media: some Telegram media edges are slower than usual; compare entry-node and egress placement before changing app-side settings")
    elif telegram_status in {"degraded", "unhealthy"}:
        recs.append("telegram-media: Telegram media edges are materially slower from the current egress; prefer a closer egress/entry path before blaming the client app")
    return recs


def _top_level_subscription_summary(services: list[dict[str, Any]]) -> dict[str, Any] | None:
    subscription_service = next((item for item in services if item.get("service_id") == "subscription-edge"), None)
    if not subscription_service:
        return {
            "configured": False,
            "url": None,
            "best_mode": None,
            "status": "not-configured",
            "http_status": None,
            "direct_ok": None,
            "http_proxy_ok": None,
            "socks5_ok": None,
            "direct_http_status": None,
            "http_proxy_http_status": None,
            "socks5_http_status": None,
            "recommendations": [],
        }

    availability = subscription_service.get("availability") or {}
    direct = availability.get("direct") or {}
    http_proxy = availability.get("http_proxy") or {}
    socks5 = availability.get("socks5") or {}
    best_mode = subscription_service.get("best_mode")
    mode_map = {
        "direct": direct,
        "http-proxy": http_proxy,
        "http_proxy": http_proxy,
        "socks5": socks5,
    }

    http_status = None
    preferred = mode_map.get(str(best_mode or ""))
    if isinstance(preferred, dict):
        http_status = preferred.get("http_code")
    if http_status is None:
        for probe in (direct, http_proxy, socks5):
            if isinstance(probe, dict) and probe.get("http_code") is not None:
                http_status = probe.get("http_code")
                break

    direct_ok = bool(direct.get("ok"))
    http_proxy_ok = bool(http_proxy.get("ok"))
    socks5_ok = bool(socks5.get("ok"))
    if direct_ok:
        status = "healthy"
    elif http_proxy_ok or socks5_ok:
        status = "degraded"
    else:
        status = "unhealthy"

    return {
        "configured": True,
        "url": subscription_service.get("url"),
        "best_mode": best_mode,
        "status": status,
        "http_status": http_status,
        "direct_ok": direct_ok,
        "http_proxy_ok": http_proxy_ok,
        "socks5_ok": socks5_ok,
        "direct_http_status": direct.get("http_code"),
        "http_proxy_http_status": http_proxy.get("http_code"),
        "socks5_http_status": socks5.get("http_code"),
        "recommendations": subscription_service.get("recommendations") or [],
    }


def _top_level_best_mode(services: list[dict[str, Any]]) -> str | None:
    subscription_service = next((item for item in services if item.get("service_id") == "subscription-edge"), None)
    if subscription_service and subscription_service.get("best_mode"):
        return str(subscription_service["best_mode"])

    for service in services:
        if service.get("best_mode"):
            return str(service["best_mode"])
    return None


def _top_level_overall_status(
    services: list[dict[str, Any]],
    vpn_delivery: dict[str, Any],
    subscription_summary: dict[str, Any] | None,
    transport_summary: dict[str, Any] | None,
    telegram_media: dict[str, Any] | None,
) -> str:
    primary_tcp_ok = bool(((vpn_delivery.get("tcp_probe") or {}).get("ok")))
    primary_xui_ok = bool(((vpn_delivery.get("xui_inbound") or {}).get("ok")))
    primary_canary_ok = bool(((vpn_delivery.get("reality_canary") or {}).get("ok")))
    transport_status = str((transport_summary or {}).get("status") or "").strip().lower()
    telegram_status = str((telegram_media or {}).get("status") or "").strip().lower()
    any_service_ok = any(
        any(bool((service.get("availability") or {}).get(mode, {}).get("ok")) for mode in ("direct", "http_proxy", "socks5"))
        for service in services
    )

    if (
        subscription_summary
        and subscription_summary.get("direct_ok")
        and primary_tcp_ok
        and primary_xui_ok
        and primary_canary_ok
        and transport_status == "healthy"
        and telegram_status in {"", "healthy", "unknown", "not-configured"}
    ):
        return "healthy"
    if telegram_status == "degraded":
        return "degraded"
    if (
        any_service_ok
        or primary_tcp_ok
        or primary_xui_ok
        or primary_canary_ok
        or transport_status in {"healthy", "advisory", "degraded"}
        or telegram_status == "advisory"
    ):
        return "degraded"
    return "unhealthy"


def _build_transport_path_summary(
    *,
    path_id: str,
    role: str,
    host: str,
    port: int,
    tcp_probe: dict[str, Any],
    xui_inbound: dict[str, Any] | None,
    reality_canary: dict[str, Any] | None,
    require_xui: bool,
) -> dict[str, Any]:
    tcp_ok = bool((tcp_probe or {}).get("ok"))
    xui_present = bool(xui_inbound)
    xui_ok = True
    if require_xui:
        xui_ok = bool((xui_inbound or {}).get("ok"))
        client_count = (xui_inbound or {}).get("client_count")
        if client_count is not None and int(client_count or 0) <= 0:
            xui_ok = False
    canary_ok = bool((reality_canary or {}).get("ok"))
    latency_s = None
    if canary_ok and (reality_canary or {}).get("total_s") is not None:
        latency_s = float((reality_canary or {}).get("total_s") or 0.0)

    if tcp_ok and canary_ok and xui_ok:
        status = "healthy"
    elif tcp_ok or canary_ok or (xui_present and xui_ok):
        status = "degraded"
    else:
        status = "unhealthy"

    errors: list[str] = []
    if not tcp_ok:
        errors.append(str((tcp_probe or {}).get("error") or "tcp-failed"))
    if require_xui and xui_present and not xui_ok:
        errors.append(str((xui_inbound or {}).get("error") or "xui-failed"))
    if reality_canary and not canary_ok:
        errors.append(str((reality_canary or {}).get("error") or (reality_canary or {}).get("command_error") or "canary-failed"))

    return {
        "path_id": path_id,
        "role": role,
        "endpoint": f"{host}:{port}",
        "host": host,
        "port": port,
        "status": status,
        "latency_s": latency_s,
        "tcp_ok": tcp_ok,
        "xui_required": require_xui,
        "xui_ok": xui_ok if require_xui else None,
        "canary_ok": canary_ok,
        "errors": errors,
    }


def _build_transport_summary(
    args: argparse.Namespace,
    vpn_delivery: dict[str, Any],
    telegram_media: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paths: dict[str, dict[str, Any]] = {
        "main": _build_transport_path_summary(
            path_id="main",
            role="primary",
            host=args.vpn_host,
            port=args.vpn_port,
            tcp_probe=vpn_delivery.get("tcp_probe") or {},
            xui_inbound=vpn_delivery.get("xui_inbound") or {},
            reality_canary=vpn_delivery.get("reality_canary") or {},
            require_xui=True,
        ),
        "secondary": _build_transport_path_summary(
            path_id="secondary",
            role="reserve",
            host=args.secondary_vpn_host,
            port=args.secondary_vpn_port,
            tcp_probe=vpn_delivery.get("secondary_tcp_probe") or {},
            xui_inbound=vpn_delivery.get("secondary_xui_inbound") or {},
            reality_canary=vpn_delivery.get("secondary_reality_canary") or {},
            require_xui=True,
        ),
    }

    if args.fallback_vpn_host.strip():
        fallback_tcp = _tcp_probe(args.fallback_vpn_host, args.fallback_vpn_port, args.timeout)
        fallback_canary = _run_vpn_delivery_canary(args.fallback_vpn_delivery_canary)
        fallback_path = _build_transport_path_summary(
            path_id="fallback_nl",
            role="emergency-fallback",
            host=args.fallback_vpn_host,
            port=args.fallback_vpn_port,
            tcp_probe=asdict(fallback_tcp),
            xui_inbound=None,
            reality_canary=fallback_canary,
            require_xui=False,
        )
        paths["fallback_nl"] = fallback_path
        vpn_delivery["fallback_tcp_probe"] = asdict(fallback_tcp)
        vpn_delivery["fallback_reality_canary"] = fallback_canary

    healthy = [item for item in paths.values() if item.get("status") == "healthy" and item.get("latency_s") is not None]
    best_path = min(healthy, key=lambda item: float(item.get("latency_s") or 999.0))["path_id"] if healthy else None

    main_path = paths["main"]
    secondary_path = paths["secondary"]
    latency_delta = None
    if main_path.get("latency_s") is not None and secondary_path.get("latency_s") is not None:
        latency_delta = round(float(main_path["latency_s"]) - float(secondary_path["latency_s"]), 3)

    if main_path.get("status") == "healthy" and best_path in {None, "main"}:
        status = "healthy"
    elif best_path is not None or any(item.get("status") in {"healthy", "degraded"} for item in paths.values()):
        status = "advisory" if best_path and best_path != "main" else "degraded"
    else:
        status = "unhealthy"

    return {
        "status": status,
        "best_path": best_path,
        "main_vs_secondary_delta_s": latency_delta,
        "telegram_media_status": str((telegram_media or {}).get("status") or "unknown"),
        "telegram_media_best_target": (telegram_media or {}).get("best_target"),
        "telegram_media_best_latency_s": (telegram_media or {}).get("best_latency_s"),
        "telegram_media_worst_target": (telegram_media or {}).get("worst_target"),
        "telegram_media_worst_latency_s": (telegram_media or {}).get("worst_latency_s"),
        "telegram_media_latency_spread_s": (telegram_media or {}).get("latency_spread_s"),
        "paths": paths,
    }


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    subscription_check_url = _resolve_subscription_check_url(args)
    selected = list(SERVICE_CATALOG)
    if subscription_check_url:
        selected.append(
            {
                "service_id": "subscription-edge",
                "category": "vpn-control",
                "url": subscription_check_url,
            }
        )
    if args.only:
        wanted = {item.strip() for item in args.only.split(",") if item.strip()}
        selected = [item for item in SERVICE_CATALOG if item["service_id"] in wanted]
        if subscription_check_url and "subscription-edge" in wanted:
            selected.append(
                {
                    "service_id": "subscription-edge",
                    "category": "vpn-control",
                    "url": subscription_check_url,
                }
            )

    quic_reject = _load_quic_reject(args.config_path)
    vpn_tcp_probe = _tcp_probe(args.vpn_host, args.vpn_port, args.timeout)
    xui_inbound = _load_xui_inbound_snapshot(args.xui_db_path, args.xui_inbound_port)
    reality_canary = _run_vpn_delivery_canary(args.vpn_delivery_canary)
    secondary_tcp_probe = _tcp_probe(args.secondary_vpn_host, args.secondary_vpn_port, args.timeout)
    secondary_xui_inbound = _load_xui_inbound_snapshot(args.xui_db_path, args.secondary_xui_inbound_port)
    secondary_canary_cmd = args.secondary_vpn_delivery_canary.strip() or _derive_secondary_canary_command(
        args.vpn_delivery_canary,
        args.secondary_vpn_port,
    )
    secondary_reality_canary = _run_vpn_delivery_canary(secondary_canary_cmd)
    telegram_media = _build_telegram_media_summary(args)
    services: list[dict[str, Any]] = []
    started = time.time()
    for service in selected:
        direct = _curl_probe(service["url"], args.timeout, mode="direct")
        proxy = _curl_probe(service["url"], args.timeout, mode="http-proxy", proxy=args.proxy)
        socks = _curl_probe(service["url"], args.timeout, mode="socks5", socks=args.socks)
        recs = _recommend_for_service(service, direct, proxy, socks, quic_reject)
        services.append(_service_summary(service, {"direct": direct, "http_proxy": proxy, "socks5": socks}, recs))

    global_recommendations = _global_recommendations(services, telegram_media)
    vpn_delivery = {
        "tcp_probe": asdict(vpn_tcp_probe),
        "xui_inbound": xui_inbound,
        "reality_canary": reality_canary,
        "secondary_tcp_probe": asdict(secondary_tcp_probe),
        "secondary_xui_inbound": secondary_xui_inbound,
        "secondary_reality_canary": secondary_reality_canary,
        "telegram_media": telegram_media,
    }
    transport_summary = _build_transport_summary(args, vpn_delivery, telegram_media)
    subscription_summary = _top_level_subscription_summary(services)
    overall_status = _top_level_overall_status(
        services,
        vpn_delivery,
        subscription_summary,
        transport_summary,
        telegram_media,
    )
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_status": overall_status,
        "status": overall_status,
        "best_mode": _top_level_best_mode(services),
        "subscription": subscription_summary,
        "subscription_check": dict(subscription_summary or {}),
        "transport_summary": transport_summary,
        "telegram_media": telegram_media,
        "recommendations": global_recommendations,
        "proxy": args.proxy,
        "socks": args.socks,
        "subscription_check_url": subscription_check_url or None,
        "quic_reject_present": quic_reject,
        "vpn_delivery": vpn_delivery,
        "services": services,
        "global_recommendations": global_recommendations,
        "probe_duration_s": round(time.time() - started, 3),
    }
    return payload


def _write_payload(path: str | None, report_dir: Path, payload: dict[str, Any]) -> None:
    if path:
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return

    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    report_path = report_dir / f"vpn-service-access-{timestamp}.json"
    latest_path = report_dir / "latest.json"
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    payload = _build_payload(args)
    _write_payload(args.output, args.report_dir, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
