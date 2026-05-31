#!/usr/bin/env python3
"""Read-only Ghost Access user subscription diagnostic.

The tool checks one Ghost Access user across:

- Ghost Access SQLite user/device rows
- x-ui SQLite inbound client rows
- optional public subscription HTTP response
- optional Xray runtime user lookup via HandlerService helper
- optional Xray access log route summary

It never prints full subscription tokens or VPN profile URIs.
"""

from __future__ import annotations

import argparse
import base64
from collections import Counter, deque
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from typing import Any
from urllib import error, request


DEFAULT_GHOST_DB = Path(
    os.getenv("GHOST_ACCESS_DB_PATH", "/opt/ghost-access-bot/shared/x0tta6bl4.db")
)
DEFAULT_XUI_DB = Path(os.getenv("XUI_DB_PATH", "/etc/x-ui/x-ui.db"))
DEFAULT_ACCESS_LOG = Path(os.getenv("XRAY_ACCESS_LOG_PATH", "/var/log/xray/access.log"))
DEFAULT_RUNTIME_MANAGER = Path(
    os.getenv(
        "XRAY_RUNTIME_USER_MANAGER",
        "/opt/ghost-access-bot/current/scripts/xray_runtime_user_manager.py",
    )
)
DEFAULT_PORTS = (443, 2083)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose one Ghost Access user's subscription without printing secrets."
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--username")
    selector.add_argument("--user-id", type=int)
    parser.add_argument("--ghost-db-path", type=Path, default=DEFAULT_GHOST_DB)
    parser.add_argument("--xui-db-path", type=Path, default=DEFAULT_XUI_DB)
    parser.add_argument("--access-log", type=Path, default=DEFAULT_ACCESS_LOG)
    parser.add_argument("--access-log-tail-lines", type=int, default=5000)
    parser.add_argument("--port", action="append", help="Expected x-ui inbound port. Defaults to 443,2083.")
    parser.add_argument("--subscription-base-url", default=env_subscription_base_url())
    parser.add_argument("--check-subscription-http", action="store_true")
    parser.add_argument("--check-runtime", action="store_true")
    parser.add_argument("--runtime-manager", type=Path, default=DEFAULT_RUNTIME_MANAGER)
    parser.add_argument("--runtime-server", default="127.0.0.1:62789")
    parser.add_argument("--runtime-timeout", type=float, default=3.0)
    parser.add_argument("--stale-hours", type=float, default=24.0)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def env_subscription_base_url() -> str:
    for key in ("SUBSCRIPTION_BASE_URL", "WEB_SUBSCRIPTION_BASE_URL"):
        value = os.getenv(key, "").strip()
        if value:
            return value.rstrip("/")
    env_file = Path(os.getenv("GHOST_ACCESS_ENV_FILE", "/opt/ghost-access-bot/shared/.env"))
    if not env_file.exists():
        return ""
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() in {"SUBSCRIPTION_BASE_URL", "WEB_SUBSCRIPTION_BASE_URL"}:
            return value.strip().strip("'").strip('"').rstrip("/")
    return ""


def parse_ports(values: list[str] | None) -> list[int]:
    if not values:
        return list(DEFAULT_PORTS)
    ports: list[int] = []
    for value in values:
        for raw in str(value).split(","):
            raw = raw.strip()
            if not raw:
                continue
            port = int(raw)
            if not 0 < port < 65536:
                raise argparse.ArgumentTypeError(f"port out of range: {port}")
            if port not in ports:
                ports.append(port)
    return ports


def token_summary(token: str | None) -> dict[str, Any]:
    value = str(token or "")
    if not value:
        return {"present": False, "length": 0}
    return {
        "present": True,
        "length": len(value),
        "prefix": value[:6],
        "sha256_12": hashlib.sha256(value.encode("utf-8")).hexdigest()[:12],
    }


def uuid_summary(value: str | None) -> dict[str, Any]:
    raw = str(value or "")
    if not raw:
        return {"present": False}
    return {
        "present": True,
        "prefix": raw[:8],
        "sha256_12": hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12],
    }


def open_sqlite_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def is_expired(value: Any, *, now: datetime | None = None) -> bool | None:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    return parsed < (now or datetime.now(UTC))


def load_user(conn: sqlite3.Connection, username: str | None, user_id: int | None) -> dict[str, Any] | None:
    if username:
        row = conn.execute(
            """
            SELECT user_id, username, plan, expires_at, vpn_uuid, subscription_token,
                   subscription_updated_at, delivery_profile, entry_node, client_family,
                   transport_preference
            FROM users
            WHERE username = ?
            LIMIT 1
            """,
            (username,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT user_id, username, plan, expires_at, vpn_uuid, subscription_token,
                   subscription_updated_at, delivery_profile, entry_node, client_family,
                   transport_preference
            FROM users
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def load_devices(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT device_id, user_id, device_name, device_type, vpn_uuid, xray_email,
               status, profile_kind, first_seen_at, last_seen_at, last_ip,
               last_handshake_at, created_at, revoked_at
        FROM devices
        WHERE user_id = ?
        ORDER BY device_id
        """,
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def load_xui_inbounds(conn: sqlite3.Connection, ports: list[int]) -> list[dict[str, Any]]:
    placeholders = ",".join("?" for _ in ports)
    rows = conn.execute(
        f"""
        SELECT id, port, tag, remark, enable, settings
        FROM inbounds
        WHERE port IN ({placeholders})
        ORDER BY port
        """,
        tuple(ports),
    ).fetchall()
    inbounds: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        try:
            item["clients"] = json.loads(item.get("settings") or "{}").get("clients") or []
            item["settings_error"] = ""
        except Exception as exc:
            item["clients"] = []
            item["settings_error"] = f"{type(exc).__name__}: {exc}"
        item.pop("settings", None)
        inbounds.append(item)
    return inbounds


def load_traffic_rows(conn: sqlite3.Connection, email: str) -> list[dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT inbound_id, enable, email, up, down, all_time, expiry_time,
                   total, reset, last_online
            FROM client_traffics
            WHERE email = ?
            ORDER BY inbound_id
            """,
            (email,),
        ).fetchall()
    except sqlite3.Error:
        return []
    return [dict(row) for row in rows]


def summarize_device(
    device: dict[str, Any],
    inbounds: list[dict[str, Any]],
    traffic_rows: list[dict[str, Any]],
    expected_ports: list[int],
    *,
    now: datetime,
    stale_after: timedelta,
) -> dict[str, Any]:
    email = str(device.get("xray_email") or "")
    uuid = str(device.get("vpn_uuid") or "")
    checks: list[dict[str, Any]] = []
    missing_ports: list[int] = []
    disabled_ports: list[int] = []

    inbounds_by_port = {int(item.get("port")): item for item in inbounds}
    for port in expected_ports:
        inbound = inbounds_by_port.get(port)
        if not inbound:
            checks.append({"port": port, "status": "inbound_missing"})
            missing_ports.append(port)
            continue
        matches = [
            client
            for client in inbound.get("clients", [])
            if client.get("id") == uuid or client.get("email") == email
        ]
        if not matches:
            checks.append(
                {
                    "port": port,
                    "status": "client_missing",
                    "inbound_id": inbound.get("id"),
                    "tag": inbound.get("tag"),
                }
            )
            missing_ports.append(port)
            continue
        client = matches[0]
        enabled = bool(client.get("enable", True)) and bool(inbound.get("enable", 1))
        if not enabled:
            disabled_ports.append(port)
        checks.append(
            {
                "port": port,
                "status": "ok" if enabled else "disabled",
                "inbound_id": inbound.get("id"),
                "tag": inbound.get("tag"),
                "uuid_match": client.get("id") == uuid,
                "email_match": client.get("email") == email,
                "flow": client.get("flow"),
                "client_enable": client.get("enable", True),
            }
        )

    last_seen = parse_datetime(device.get("last_handshake_at") or device.get("last_seen_at"))
    stale = None if last_seen is None else last_seen < now - stale_after
    return {
        "device_id": device.get("device_id"),
        "device_name": device.get("device_name"),
        "device_type": device.get("device_type"),
        "status": device.get("status"),
        "profile_kind": device.get("profile_kind"),
        "xray_email": email,
        "vpn_uuid": uuid_summary(uuid),
        "last_seen_at": device.get("last_seen_at"),
        "last_handshake_at": device.get("last_handshake_at"),
        "last_seen_stale": stale,
        "xui_checks": checks,
        "missing_ports": missing_ports,
        "disabled_ports": disabled_ports,
        "traffic_rows": sanitize_traffic_rows(traffic_rows),
    }


def sanitize_traffic_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for row in rows:
        sanitized.append(
            {
                "inbound_id": row.get("inbound_id"),
                "enable": row.get("enable"),
                "up": row.get("up"),
                "down": row.get("down"),
                "all_time": row.get("all_time"),
                "last_online": row.get("last_online"),
            }
        )
    return sanitized


def decode_subscription_body(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        padding = "=" * ((4 - len(text) % 4) % 4)
        decoded = base64.b64decode(text + padding, validate=False).decode("utf-8", errors="replace")
    except Exception:
        return text
    if "vless://" in decoded or "vmess://" in decoded or "trojan://" in decoded:
        return decoded
    return text


def check_subscription_http(base_url: str, token: str, devices: list[dict[str, Any]]) -> dict[str, Any]:
    if not base_url:
        return {"checked": False, "reason": "base_url_missing"}
    if not token:
        return {"checked": False, "reason": "token_missing"}
    url = f"{base_url.rstrip('/')}/sub/{token}"
    req = request.Request(url, headers={"User-Agent": "x0tta6bl4-user-subscription-diagnostic/1.0"})
    try:
        with request.urlopen(req, timeout=10) as response:
            raw = response.read(200000)
            headers = {key.lower(): value for key, value in response.headers.items()}
            decoded = decode_subscription_body(raw)
            lines = [line for line in decoded.splitlines() if line.strip()]
            uuid_presence = [
                {
                    "device_id": device.get("device_id"),
                    "uuid_present": str(device.get("vpn_uuid") or "") in decoded,
                }
                for device in devices
            ]
            return {
                "checked": True,
                "http_status": response.status,
                "content_type": headers.get("content-type"),
                "subscription_userinfo_present": "subscription-userinfo" in headers,
                "profile_update_interval": headers.get("profile-update-interval"),
                "line_count": len(lines),
                "vless_line_count": sum(1 for line in lines if line.startswith("vless://")),
                "uuid_presence": uuid_presence,
                "contains_error_text": contains_error_text(decoded),
            }
    except error.HTTPError as exc:
        return {"checked": True, "http_status": exc.code, "error": str(exc)[:200]}
    except Exception as exc:
        return {"checked": True, "http_status": None, "error": f"{type(exc).__name__}: {exc}"[:200]}


def contains_error_text(text: str) -> bool:
    lowered = text.lower()
    return "not found" in lowered or "error" in lowered or "не найд" in lowered


def run_runtime_checks(
    runtime_manager: Path,
    runtime_server: str,
    runtime_timeout: float,
    devices: list[dict[str, Any]],
    inbounds: list[dict[str, Any]],
    expected_ports: list[int],
) -> list[dict[str, Any]]:
    if not runtime_manager.exists():
        return [{"status": "not_checked", "reason": "runtime_manager_missing"}]

    inbounds_by_port = {int(item.get("port")): item for item in inbounds}
    results: list[dict[str, Any]] = []
    for device in devices:
        email = str(device.get("xray_email") or "")
        uuid = str(device.get("vpn_uuid") or "")
        for port in expected_ports:
            inbound = inbounds_by_port.get(port)
            if not inbound or not inbound.get("tag"):
                results.append(
                    {
                        "device_id": device.get("device_id"),
                        "port": port,
                        "status": "skipped",
                        "reason": "inbound_tag_missing",
                    }
                )
                continue
            command = [
                sys.executable,
                str(runtime_manager),
                "--server",
                runtime_server,
                "--timeout",
                str(runtime_timeout),
                "get-user",
                "--tag",
                str(inbound["tag"]),
                "--email",
                email,
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=max(5.0, runtime_timeout + 2.0),
                )
            except Exception as exc:
                results.append(
                    {
                        "device_id": device.get("device_id"),
                        "port": port,
                        "status": "error",
                        "error": f"{type(exc).__name__}: {exc}"[:200],
                    }
                )
                continue
            if completed.returncode != 0:
                results.append(
                    {
                        "device_id": device.get("device_id"),
                        "port": port,
                        "status": "error",
                        "error": (completed.stderr or completed.stdout).strip()[:200],
                    }
                )
                continue
            try:
                users = json.loads(completed.stdout or "[]")
            except json.JSONDecodeError as exc:
                results.append(
                    {
                        "device_id": device.get("device_id"),
                        "port": port,
                        "status": "error",
                        "error": f"invalid runtime json: {exc}"[:200],
                    }
                )
                continue
            matched = any(item.get("email") == email and item.get("uuid") == uuid for item in users)
            results.append(
                {
                    "device_id": device.get("device_id"),
                    "port": port,
                    "status": "ok" if matched else "runtime_user_missing",
                    "user_count": len(users),
                }
            )
    return results


def read_tail_lines(path: Path, tail_lines: int) -> list[str]:
    limit = max(1, int(tail_lines))
    window: deque[str] = deque(maxlen=limit)
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            window.append(line.rstrip("\n"))
    return list(window)


def parse_access_log(path: Path, email_prefix: str, tail_lines: int) -> dict[str, Any]:
    if not path.exists():
        return {"checked": False, "reason": "access_log_missing"}
    try:
        lines = read_tail_lines(path, tail_lines)
    except OSError as exc:
        return {"checked": False, "reason": f"read_failed: {exc}"[:200]}

    matching = [line for line in lines if email_prefix in line]
    emails: Counter[str] = Counter()
    inbounds: Counter[str] = Counter()
    routes: Counter[str] = Counter()
    blocked_targets: Counter[str] = Counter()
    latest_redacted: list[str] = []
    for line in matching:
        email_match = re.search(r"email: ([^ ]+)", line)
        if email_match:
            emails[email_match.group(1)] += 1
        route_match = re.search(r"\[([^ ]+) -> ([^\]]+)\]", line)
        inbound = route_match.group(1) if route_match else ""
        route = route_match.group(2) if route_match else ""
        if inbound:
            inbounds[inbound] += 1
        if route:
            routes[route] += 1
        target_match = re.search(r"accepted (?:tcp|udp):([^ ]+)", line)
        if target_match and route == "blocked":
            blocked_targets[target_match.group(1).rsplit(":", 1)[0]] += 1
        latest_redacted.append(redact_log_line(line))

    return {
        "checked": True,
        "sample_line_count": len(matching),
        "emails": dict(emails),
        "inbounds": dict(inbounds),
        "routes": dict(routes),
        "blocked_total": int(routes.get("blocked", 0)),
        "blocked_targets": [
            {"target": target, "count": count}
            for target, count in blocked_targets.most_common(20)
        ],
        "latest_redacted": latest_redacted[-12:],
    }


def redact_log_line(line: str) -> str:
    return re.sub(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", "REDACTED_IP", line)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    ports = parse_ports(args.port)
    now = datetime.now(UTC)
    report: dict[str, Any] = {
        "schema_version": 1,
        "source": "services/nl-server/ghost-access/diagnose_user_subscription.py",
        "generated_at": now.isoformat(),
        "selector": {"username": args.username, "user_id": args.user_id},
        "expected_ports": ports,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
    }

    if not args.ghost_db_path.exists():
        return {
            **report,
            "status": "blocked",
            "summary": {"ghost_db_found": False},
            "recommendations": ["run this on the host with the Ghost Access SQLite database"],
        }

    with open_sqlite_readonly(args.ghost_db_path) as ghost_conn:
        user = load_user(ghost_conn, args.username, args.user_id)
        if not user:
            return {
                **report,
                "status": "not_found",
                "summary": {"user_found": False},
                "recommendations": ["check the username/user_id selector"],
            }
        devices = load_devices(ghost_conn, int(user["user_id"]))

    user_public = public_user(user)
    active_devices = [device for device in devices if str(device.get("status") or "").lower() == "active"]
    stale_after = timedelta(hours=max(0.1, float(args.stale_hours)))

    inbounds: list[dict[str, Any]] = []
    device_reports: list[dict[str, Any]] = []
    xui_found = args.xui_db_path.exists()
    if xui_found:
        with open_sqlite_readonly(args.xui_db_path) as xui_conn:
            inbounds = load_xui_inbounds(xui_conn, ports)
            for device in devices:
                rows = load_traffic_rows(xui_conn, str(device.get("xray_email") or ""))
                device_reports.append(
                    summarize_device(
                        device,
                        inbounds,
                        rows,
                        ports,
                        now=now,
                        stale_after=stale_after,
                    )
                )
    else:
        for device in devices:
            device_reports.append(
                {
                    "device_id": device.get("device_id"),
                    "device_name": device.get("device_name"),
                    "status": device.get("status"),
                    "xray_email": device.get("xray_email"),
                    "vpn_uuid": uuid_summary(str(device.get("vpn_uuid") or "")),
                    "xui_checks": [],
                    "missing_ports": ports,
                    "disabled_ports": [],
                    "traffic_rows": [],
                }
            )

    subscription = (
        check_subscription_http(args.subscription_base_url, str(user.get("subscription_token") or ""), devices)
        if args.check_subscription_http
        else {"checked": False, "reason": "not_requested"}
    )
    runtime = (
        run_runtime_checks(
            args.runtime_manager,
            args.runtime_server,
            args.runtime_timeout,
            devices,
            inbounds,
            ports,
        )
        if args.check_runtime
        else [{"status": "not_checked", "reason": "not_requested"}]
    )
    access = parse_access_log(
        args.access_log,
        str(user.get("username") or user.get("user_id") or ""),
        int(args.access_log_tail_lines),
    )

    summary = summarize_report(user_public, device_reports, subscription, runtime, access, xui_found)
    recommendations = build_recommendations(summary)
    return {
        **report,
        "status": summary["status"],
        "summary": summary,
        "user": user_public,
        "devices": device_reports,
        "subscription": subscription,
        "runtime": runtime,
        "access_log": access,
        "recommendations": recommendations,
    }


def public_user(user: dict[str, Any]) -> dict[str, Any]:
    token = str(user.get("subscription_token") or "")
    result = {
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "plan": user.get("plan"),
        "expires_at": user.get("expires_at"),
        "expired": is_expired(user.get("expires_at")),
        "vpn_uuid": uuid_summary(str(user.get("vpn_uuid") or "")),
        "subscription_token": token_summary(token),
        "subscription_updated_at": user.get("subscription_updated_at"),
        "delivery_profile": user.get("delivery_profile"),
        "entry_node": user.get("entry_node"),
        "client_family": user.get("client_family"),
        "transport_preference": user.get("transport_preference"),
    }
    return result


def summarize_report(
    user: dict[str, Any],
    devices: list[dict[str, Any]],
    subscription: dict[str, Any],
    runtime: list[dict[str, Any]],
    access: dict[str, Any],
    xui_found: bool,
) -> dict[str, Any]:
    active_devices = [device for device in devices if str(device.get("status") or "").lower() == "active"]
    missing_ports = sum(len(device.get("missing_ports") or []) for device in active_devices)
    disabled_ports = sum(len(device.get("disabled_ports") or []) for device in active_devices)
    stale_devices = sum(1 for device in active_devices if device.get("last_seen_stale") is True)
    never_seen_devices = sum(1 for device in active_devices if device.get("last_seen_stale") is None)
    runtime_missing = sum(1 for item in runtime if item.get("status") == "runtime_user_missing")
    subscription_http_status = subscription.get("http_status") if subscription.get("checked") else None
    subscription_uuid_missing = 0
    if isinstance(subscription.get("uuid_presence"), list):
        subscription_uuid_missing = sum(
            1 for item in subscription["uuid_presence"] if item.get("uuid_present") is False
        )

    hard_failures = []
    warnings = []
    if user.get("expired") is True:
        hard_failures.append("user_plan_expired")
    if not user.get("subscription_token", {}).get("present"):
        hard_failures.append("subscription_token_missing")
    if subscription_http_status is not None and int(subscription_http_status) >= 400:
        hard_failures.append("subscription_http_failed")
    if not xui_found:
        hard_failures.append("xui_db_missing")
    if missing_ports:
        hard_failures.append("active_device_missing_xui_port")
    if disabled_ports:
        hard_failures.append("active_device_disabled_in_xui")
    if runtime_missing:
        hard_failures.append("runtime_user_missing")
    if subscription_uuid_missing:
        hard_failures.append("subscription_missing_device_uuid")

    if stale_devices:
        warnings.append("active_device_stale")
    if never_seen_devices:
        warnings.append("active_device_never_seen")
    if access.get("blocked_total", 0):
        warnings.append("blocked_routes_observed")

    status = "healthy"
    if warnings:
        status = "attention"
    if hard_failures:
        status = "broken"

    return {
        "status": status,
        "hard_failures": hard_failures,
        "warnings": warnings,
        "user_found": True,
        "plan_expired": user.get("expired"),
        "subscription_token_present": user.get("subscription_token", {}).get("present", False),
        "subscription_http_status": subscription_http_status,
        "subscription_uuid_missing": subscription_uuid_missing,
        "device_count": len(devices),
        "active_device_count": len(active_devices),
        "active_device_missing_xui_port_count": missing_ports,
        "active_device_disabled_xui_port_count": disabled_ports,
        "active_device_stale_count": stale_devices,
        "active_device_never_seen_count": never_seen_devices,
        "runtime_user_missing_count": runtime_missing,
        "blocked_route_count": access.get("blocked_total") if access.get("checked") else None,
        "xui_db_found": xui_found,
    }


def build_recommendations(summary: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    failures = set(summary.get("hard_failures") or [])
    warnings = set(summary.get("warnings") or [])
    if "subscription_token_missing" in failures:
        recommendations.append("repair or rotate the user's subscription token through the Ghost Access support path")
    if "subscription_http_failed" in failures:
        recommendations.append("check /sub/{token} routing before changing x-ui clients")
    if "active_device_missing_xui_port" in failures or "active_device_disabled_in_xui" in failures:
        recommendations.append("sync the affected active device clients into the expected x-ui inbounds")
    if "runtime_user_missing" in failures:
        recommendations.append("add the missing runtime user or restart x-ui only after backup and explicit write approval")
    if "active_device_never_seen" in warnings:
        recommendations.append("ask the user to re-import the subscription on devices that have never connected")
    if "active_device_stale" in warnings:
        recommendations.append("ask the user to open the VPN client on stale devices and retry the current subscription")
    if "blocked_routes_observed" in warnings:
        recommendations.append("if the complaint is one app/site only, inspect routing rules for blocked targets instead of rotating subscriptions")
    if not recommendations:
        recommendations.append("subscription path looks healthy; collect the exact app/device symptom if the user still sees instability")
    return recommendations


def print_plain(report: dict[str, Any]) -> None:
    print(f"status: {report.get('status')}")
    summary = report.get("summary") or {}
    print(f"user_found: {summary.get('user_found')}")
    print(f"subscription_token_present: {summary.get('subscription_token_present')}")
    if summary.get("subscription_http_status") is not None:
        print(f"subscription_http_status: {summary.get('subscription_http_status')}")
    print(f"active_devices: {summary.get('active_device_count')}/{summary.get('device_count')}")
    print(f"missing_xui_ports: {summary.get('active_device_missing_xui_port_count')}")
    print(f"disabled_xui_ports: {summary.get('active_device_disabled_xui_port_count')}")
    print(f"runtime_missing: {summary.get('runtime_user_missing_count')}")
    print(f"blocked_routes: {summary.get('blocked_route_count')}")
    for item in report.get("recommendations") or []:
        print(f"recommendation: {item}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_report(args)
    except sqlite3.Error as exc:
        report = {
            "schema_version": 1,
            "source": "services/nl-server/ghost-access/diagnose_user_subscription.py",
            "status": "blocked",
            "error": f"sqlite_error: {exc}",
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_plain(report)
    return 0 if report.get("status") not in {"blocked", "not_found"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
