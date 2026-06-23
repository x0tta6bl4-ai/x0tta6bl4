#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


DEFAULT_TRANSPORT_USAGE_PATH = Path("nl-diagnostics/nl-transport-usage-latest.json")
DEFAULT_SUBSCRIPTION_PAYLOAD_PATH = Path("nl-diagnostics/nl-live-subscription-payload-latest.json")
DEFAULT_DB_PATH = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
DEFAULT_JSON_OUT = Path("nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.json")
DEFAULT_MARKDOWN_OUT = Path("nl-diagnostics/nl-legacy-client-migration-packet-2026-06-05.md")
EXPECTED_REALITY_PORTS = {443, 2083}
REPLY_RECORDER_PATH = "services/nl-server/ghost-access/record_legacy_client_migration_reply.py"

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
    "http_url": re.compile(r"\bhttps?://", re.IGNORECASE),
    "telegram_handle": re.compile(r"@[A-Za-z0-9_]{4,}"),
    "phone": re.compile(r"\+\d[\d .()_-]{8,}\d\b"),
}


class MigrationPacketError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MigrationPacketError(f"required JSON artifact missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MigrationPacketError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise MigrationPacketError(f"{path} must be a JSON object")
    return payload


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[1]) for row in rows}


def parse_expiry(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        numeric = float(text)
    except ValueError:
        numeric = None
    if numeric is not None:
        if numeric > 10_000_000_000:
            numeric = numeric / 1000
        return datetime.fromtimestamp(numeric, tz=UTC)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def read_db_summary(db_path: Path, *, now: datetime | None = None) -> dict[str, Any]:
    base = {
        "available": False,
        "path": str(db_path),
        "total_users": 0,
        "users_with_subscription_token": 0,
        "active_users": 0,
        "expired_users": 0,
        "missing_or_invalid_expiry_users": 0,
        "total_devices": 0,
        "users_with_devices": 0,
        "users_without_devices": 0,
        "raw_user_ids_printed": False,
        "raw_tokens_printed": False,
    }
    if not db_path.exists():
        return base
    current = now or datetime.now(UTC)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "users"):
            return {**base, "available": True}
        user_columns = table_columns(conn, "users")
        result = {**base, "available": True}
        result["total_users"] = int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        if "subscription_token" in user_columns:
            result["users_with_subscription_token"] = int(
                conn.execute(
                    "SELECT COUNT(*) FROM users "
                    "WHERE subscription_token IS NOT NULL AND TRIM(subscription_token) != ''"
                ).fetchone()[0]
            )
        if "expires_at" in user_columns:
            active = expired = missing = 0
            for row in conn.execute("SELECT expires_at FROM users"):
                parsed = parse_expiry(row["expires_at"])
                if parsed is None:
                    missing += 1
                elif parsed > current:
                    active += 1
                else:
                    expired += 1
            result["active_users"] = active
            result["expired_users"] = expired
            result["missing_or_invalid_expiry_users"] = missing
        if table_exists(conn, "devices"):
            device_columns = table_columns(conn, "devices")
            result["total_devices"] = int(conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0])
            if "user_id" in user_columns and "user_id" in device_columns:
                result["users_with_devices"] = int(
                    conn.execute(
                        "SELECT COUNT(DISTINCT u.user_id) "
                        "FROM users u JOIN devices d ON d.user_id = u.user_id"
                    ).fetchone()[0]
                )
                result["users_without_devices"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM users u "
                        "WHERE NOT EXISTS (SELECT 1 FROM devices d WHERE d.user_id = u.user_id)"
                    ).fetchone()[0]
                )
        return result


def subscription_is_safe(payload: dict[str, Any]) -> bool:
    ports = {
        int(port)
        for port in (payload.get("ports") or [])
        if isinstance(port, int) or str(port).isdigit()
    }
    transport_counts = payload.get("transport_counts") if isinstance(payload.get("transport_counts"), dict) else {}
    non_reality = [
        key for key, value in transport_counts.items() if str(key) != "reality" and int(value or 0) > 0
    ]
    return (
        payload.get("ok") is True
        and bool(ports)
        and ports.issubset(EXPECTED_REALITY_PORTS)
        and int(transport_counts.get("reality") or 0) > 0
        and not non_reality
        and not payload.get("failures")
    )


def legacy_attention(payload: dict[str, Any]) -> bool:
    findings = payload.get("findings") if isinstance(payload.get("findings"), list) else []
    return payload.get("decision") == "TRANSPORT_USAGE_ATTENTION" or bool(findings)


def summarize_legacy_windows(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    for window_name in ("15m", "60m"):
        health = (windows.get(window_name) or {}).get("legacy_transport_health") if isinstance(windows.get(window_name), dict) else {}
        transports = health.get("transports") if isinstance(health, dict) and isinstance(health.get("transports"), dict) else {}
        result[window_name] = {
            "status": str((health or {}).get("status") or "unknown"),
            "ok": (health or {}).get("ok") is True,
            "findings": [
                str(item)
                for item in ((health or {}).get("findings") or [])
                if isinstance(item, str)
            ],
            "transports": {
                str(name): {
                    "status": str(row.get("status") or "unknown"),
                    "proxy_requests": int(row.get("proxy_requests") or 0),
                    "proxy_4xx": int(row.get("proxy_4xx") or 0),
                    "proxy_5xx": int(row.get("proxy_5xx") or 0),
                    "dataplane_events": int(row.get("dataplane_events") or 0),
                    "unique_client_count": int(row.get("unique_client_count") or 0),
                    "findings": [
                        str(item)
                        for item in (row.get("findings") or [])
                        if isinstance(item, str)
                    ],
                }
                for name, row in transports.items()
                if isinstance(row, dict)
            },
        }
    return result


def migration_message_ru() -> str:
    return (
        "Если VPN сейчас не подключается, обновите профиль. "
        "Откройте этого бота, нажмите Подключить и импортируйте свежий профиль Reality. "
        "В клиенте удалите старые профили Ghost Access с xhttp, ws или портом 8443, "
        "чтобы телефон не выбирал их вместо нового профиля. "
        "После проверки ответьте только одним вариантом: done updated, fail import, "
        "fail timeout или fail no-internet. "
        "Не присылайте ссылки, QR-коды, UUID, IP-адреса, скриншоты, логи, телефон или username."
    )


def build_reply_record_command(reply: str) -> str:
    return (
        f"printf '%s\\n' \"{reply}\" | "
        f"python3 {REPLY_RECORDER_PATH} "
        "--write "
        '--expect-packet-sha256 "$(sha256sum '
        f"{DEFAULT_JSON_OUT} "
        '| awk \'{print $1}\')" '
        "--reporter-label legacy-client-1 "
        "--reply-stdin "
        "--json"
    )


def build_reply_validate_command(reply: str) -> str:
    return (
        f"printf '%s\\n' \"{reply}\" | "
        f"python3 {REPLY_RECORDER_PATH} "
        '--expect-packet-sha256 "$(sha256sum '
        f"{DEFAULT_JSON_OUT} "
        '| awk \'{print $1}\')" '
        "--reporter-label legacy-client-1 "
        "--reply-stdin "
        "--json"
    )


def build_packet(
    *,
    transport_usage: dict[str, Any],
    subscription_payload: dict[str, Any],
    db_summary: dict[str, Any],
    generated_at: str | None = None,
) -> dict[str, Any]:
    sub_safe = subscription_is_safe(subscription_payload)
    legacy_needs_attention = legacy_attention(transport_usage)
    if not sub_safe:
        decision = "LEGACY_CLIENT_MIGRATION_BLOCKED_SUBSCRIPTION_UNSAFE"
        action = "fix_subscription_payload_before_migration"
    elif legacy_needs_attention:
        decision = "LEGACY_CLIENT_MIGRATION_PACKET_READY"
        action = "ask_legacy_clients_to_refresh_reality_profile"
    else:
        decision = "LEGACY_CLIENT_MIGRATION_NOT_NEEDED"
        action = "observe"

    active_count = int(db_summary.get("active_users") or 0)
    if active_count <= 0:
        active_count = int(subscription_payload.get("checked_subscription_count") or 0)

    return {
        "schema_version": 1,
        "source": "build_legacy_client_migration_packet.py",
        "generated_at": generated_at or utc_now(),
        "decision": decision,
        "operator_action": action,
        "send_policy": {
            "automatic_broadcast_allowed": False,
            "manual_operator_review_required": True,
            "reason": "message targets are Telegram users; this packet prepares migration safely but does not send anything",
        },
        "target_audience": {
            "active_subscription_count": active_count,
            "expired_users_excluded": int(db_summary.get("expired_users") or 0),
            "users_with_devices": int(db_summary.get("users_with_devices") or 0),
            "raw_user_ids_printed": False,
            "raw_chat_ids_printed": False,
        },
        "current_safe_profile": {
            "transport": "reality",
            "ports": [
                int(port)
                for port in (subscription_payload.get("ports") or [])
                if isinstance(port, int) or str(port).isdigit()
            ],
            "active_subscription_payload_safe": sub_safe,
            "checked_subscription_count": int(subscription_payload.get("checked_subscription_count") or 0),
            "transport_counts": subscription_payload.get("transport_counts") or {},
            "failures": subscription_payload.get("failures") or [],
        },
        "legacy_problem": {
            "attention": legacy_needs_attention,
            "decision": str(transport_usage.get("decision") or "unknown"),
            "operator_action": str(transport_usage.get("operator_action") or "unknown"),
            "findings": [
                str(item)
                for item in (transport_usage.get("findings") or [])
                if isinstance(item, str)
            ],
            "windows": summarize_legacy_windows(transport_usage),
        },
        "migration_request": {
            "message_ru": migration_message_ru(),
            "safe_reply_options": [
                "done updated",
                "fail import",
                "fail timeout",
                "fail no-internet",
            ],
            "success_reply": "done updated",
            "failure_replies": ["fail import", "fail timeout", "fail no-internet"],
            "operator_reply_record_commands": {
                reply: build_reply_record_command(reply)
                for reply in ["done updated", "fail import", "fail timeout", "fail no-internet"]
            },
            "operator_reply_validate_commands": {
                reply: build_reply_validate_command(reply)
                for reply in ["done updated", "fail import", "fail timeout", "fail no-internet"]
            },
            "do_not_request": [
                "profile links",
                "subscription links",
                "QR codes",
                "UUIDs",
                "IP addresses",
                "screenshots",
                "logs",
                "phone numbers",
                "usernames",
            ],
        },
        "operator_checks_after_migration": [
            "run ghost-access-transport-usage-evidence.service and verify legacy 15m/60m findings decrease",
            "run scripts/vpn_status.sh --json and verify subscription_payload stays safe",
            "record only short replies; do not store raw links, screenshots, logs, IPs, usernames, or phone numbers",
        ],
        "db_summary": db_summary,
        "privacy": {
            "raw_user_ids_printed": False,
            "raw_chat_ids_printed": False,
            "raw_tokens_printed": False,
            "raw_subscription_urls_printed": False,
            "raw_vpn_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_ip_printed": False,
            "raw_telegram_handle_printed": False,
        },
    }


def secret_findings(value: Any, *, path: str = "$") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            findings.extend(secret_findings(nested, path=f"{path}.{key}"))
        return findings
    if isinstance(value, list):
        for index, nested in enumerate(value):
            findings.extend(secret_findings(nested, path=f"{path}[{index}]"))
        return findings
    if not isinstance(value, str):
        return findings
    for name, pattern in FORBIDDEN_OUTPUT_PATTERNS.items():
        match = pattern.search(value)
        if match:
            findings.append({"path": path, "kind": name, "sample": match.group(0)[:80]})
    return findings


def validate_output(packet: dict[str, Any]) -> list[dict[str, str]]:
    return secret_findings(packet)


def render_markdown(packet: dict[str, Any]) -> str:
    audience = packet["target_audience"]
    safe = packet["current_safe_profile"]
    legacy = packet["legacy_problem"]
    migration = packet["migration_request"]
    lines = [
        "# NL Legacy Client Migration Packet",
        "",
        f"- Decision: `{packet['decision']}`",
        f"- Operator action: `{packet['operator_action']}`",
        f"- Active subscriptions: `{audience['active_subscription_count']}`",
        f"- Expired users excluded: `{audience['expired_users_excluded']}`",
        f"- Safe profile: `{safe['transport']}` ports `{safe['ports']}`",
        f"- Subscription payload safe: `{safe['active_subscription_payload_safe']}`",
        f"- Legacy attention: `{legacy['attention']}`",
        "",
        "## Findings",
        "",
    ]
    for finding in legacy["findings"] or ["none"]:
        lines.append(f"- `{finding}`")
    lines.extend(
        [
            "",
            "## User Message",
            "",
            migration["message_ru"],
            "",
            "## Safe Replies",
            "",
        ]
    )
    for reply in migration["safe_reply_options"]:
        lines.append(f"- `{reply}`")
    lines.extend(
        [
            "",
            "## Reply Recording",
            "",
            "Validate a short reply before writing:",
            "",
            f"```bash\n{migration['operator_reply_validate_commands']['done updated']}\n```",
            "",
            "Record a short reply only after operator review:",
            "",
            f"```bash\n{migration['operator_reply_record_commands']['done updated']}\n```",
            "",
            "Change `legacy-client-1` to a non-private local label such as `legacy-client-2`.",
        ]
    )
    lines.extend(
        [
            "",
            "## Send Policy",
            "",
            "- Automatic broadcast allowed: `false`",
            "- Manual operator review required: `true`",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build privacy-safe NL legacy client migration packet.")
    parser.add_argument("--transport-usage", type=Path, default=DEFAULT_TRANSPORT_USAGE_PATH)
    parser.add_argument("--subscription-payload", type=Path, default=DEFAULT_SUBSCRIPTION_PAYLOAD_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    transport_usage = load_json(args.transport_usage)
    subscription_payload = load_json(args.subscription_payload)
    packet = build_packet(
        transport_usage=transport_usage,
        subscription_payload=subscription_payload,
        db_summary=read_db_summary(args.db_path),
    )
    findings = validate_output(packet)
    if findings:
        packet["decision"] = "LEGACY_CLIENT_MIGRATION_PACKET_BLOCKED_PRIVACY"
        packet["operator_action"] = "remove_sensitive_output_before_migration"
        packet["privacy_findings"] = findings
    if args.write:
        write_text(args.json_out, json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        write_text(args.markdown_out, render_markdown(packet))
    if args.json or not args.write:
        print(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not findings else 2


if __name__ == "__main__":
    raise SystemExit(run())
