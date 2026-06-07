#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


DEFAULT_PACKET_PATH = Path("/var/lib/ghost-access/legacy-migration/latest.json")
DEFAULT_MESSAGE_SEND_PATH = Path("/var/lib/ghost-access/legacy-migration/message-send.json")
DEFAULT_REPLIES_PATH = Path("/var/lib/ghost-access/legacy-migration/replies.json")
DEFAULT_DB_PATH = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
DEFAULT_JSON_OUT = Path("/var/lib/ghost-access/legacy-migration/progress.json")
DEFAULT_MARKDOWN_OUT = Path("/var/lib/ghost-access/legacy-migration/progress.md")
CONFIRM_TEXT = "COLLECT_CURRENT_LEGACY_PROGRESS"
TECHNICAL_SUBSCRIPTION_UA_PREFIXES = (
    "curl/",
    "python-urllib/",
    "python-requests/",
    "aiohttp/",
    "diag-probe/",
    "post-deploy-probe/",
    "ghost-access-canary/",
    "ghost-access-probe/",
    "x0tta-live-subscription-payload-check",
    "monitoring-agent/",
    "go-http-client/",
)
TECHNICAL_SUBSCRIPTION_IPS = {"127.0.0.1", "::1"}

FORBIDDEN_PATTERNS = {
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


class LegacyMigrationProgressError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> datetime | None:
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
    normalized = text.replace("Z", "+00:00")
    for candidate in (normalized, normalized.replace(" ", "T", 1)):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def load_json_with_source(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise LegacyMigrationProgressError(f"required JSON artifact missing: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LegacyMigrationProgressError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LegacyMigrationProgressError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegacyMigrationProgressError(f"{path} must be a JSON object")
    return payload, {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def load_optional_json(path: Path) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    if not path.exists():
        return None, None
    return load_json_with_source(path)


def validate_expected_sha256(actual_sha256: str, expected_sha256: str) -> None:
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise LegacyMigrationProgressError("--expect-packet-sha256 must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise LegacyMigrationProgressError(
            "migration packet sha256 mismatch: "
            f"expected={expected}, actual={actual_sha256.lower()}"
        )


def validate_write_args(args: argparse.Namespace) -> None:
    if args.write and args.confirm_current_progress != CONFIRM_TEXT:
        raise LegacyMigrationProgressError(
            f"--write requires --confirm-current-progress {CONFIRM_TEXT}"
        )


def validate_packet(packet: dict[str, Any]) -> None:
    if packet.get("decision") != "LEGACY_CLIENT_MIGRATION_PACKET_READY":
        raise LegacyMigrationProgressError("migration packet is not ready")
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), dict) else {}
    flags = [
        "raw_user_ids_printed",
        "raw_chat_ids_printed",
        "raw_tokens_printed",
        "raw_subscription_urls_printed",
        "raw_vpn_uris_printed",
        "raw_uuid_printed",
        "raw_ip_printed",
        "raw_telegram_handle_printed",
    ]
    if any(privacy.get(flag) is not False for flag in flags):
        raise LegacyMigrationProgressError("migration packet privacy flags are not clean")


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
    for name, pattern in FORBIDDEN_PATTERNS.items():
        match = pattern.search(value)
        if match:
            findings.append({"path": path, "kind": name, "sample": match.group(0)[:80]})
    return findings


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


def is_active_expiry(value: Any, *, now: datetime) -> bool:
    expiry = parse_time(value)
    return bool(expiry and expiry > now)


def sanitize_label(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9._ -]+", "_", text)[:40].strip(" ._-")
    return text or "unknown"


def is_technical_subscription_access(user_agent: Any, ip_address: Any = None, client_app: Any = None) -> bool:
    ua_lower = str(user_agent or "").strip().lower()
    app_lower = str(client_app or "").strip().lower()
    ip_text = str(ip_address or "").strip()
    if ip_text in TECHNICAL_SUBSCRIPTION_IPS:
        return True
    return any(ua_lower.startswith(prefix) or app_lower.startswith(prefix) for prefix in TECHNICAL_SUBSCRIPTION_UA_PREFIXES)


def read_active_user_ids(conn: sqlite3.Connection, *, now: datetime) -> set[int]:
    if not table_exists(conn, "users"):
        return set()
    cols = table_columns(conn, "users")
    if not {"user_id", "expires_at"}.issubset(cols):
        return set()
    predicates: list[str] = []
    if "subscription_token" in cols:
        predicates.extend(["subscription_token IS NOT NULL", "TRIM(subscription_token) != ''"])
    if table_exists(conn, "devices") and "user_id" in table_columns(conn, "devices"):
        predicates.append("EXISTS (SELECT 1 FROM devices d WHERE d.user_id = users.user_id)")
    where_sql = f" WHERE {' AND '.join(predicates)}" if predicates else ""
    rows = conn.execute(f"SELECT user_id, expires_at FROM users{where_sql}").fetchall()
    active: set[int] = set()
    for row in rows:
        if is_active_expiry(row["expires_at"], now=now):
            try:
                active.add(int(row["user_id"]))
            except (TypeError, ValueError):
                continue
    return active


def collect_db_progress(db_path: Path, *, sent_at: datetime, now: datetime) -> dict[str, Any]:
    if not db_path.exists():
        return {
            "db_available": False,
            "active_user_count": 0,
            "subscription_refresh": {},
            "device_activity": {},
            "request_events": {},
        }
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        active_user_ids = read_active_user_ids(conn, now=now)

        subscription_rows_since = []
        if table_exists(conn, "subscription_accesses"):
            cols = table_columns(conn, "subscription_accesses")
            if {"user_id", "last_seen_at"}.issubset(cols):
                selected_cols = ["user_id", "last_seen_at"]
                if "client_app" in cols:
                    selected_cols.append("client_app")
                if "user_agent" in cols:
                    selected_cols.append("user_agent")
                if "ip_address" in cols:
                    selected_cols.append("ip_address")
                rows = conn.execute(
                    f"SELECT {', '.join(selected_cols)} FROM subscription_accesses"
                ).fetchall()
                for row in rows:
                    try:
                        user_id = int(row["user_id"])
                    except (TypeError, ValueError):
                        continue
                    seen_at = parse_time(row["last_seen_at"])
                    if user_id not in active_user_ids or seen_at is None or seen_at < sent_at:
                        continue
                    raw_user_agent = row["user_agent"] if "user_agent" in row.keys() else ""
                    app = row["client_app"] if "client_app" in row.keys() else ""
                    raw_ip = row["ip_address"] if "ip_address" in row.keys() else ""
                    if is_technical_subscription_access(raw_user_agent, raw_ip, app):
                        continue
                    if not app:
                        app = str(raw_user_agent or "").split("/", 1)[0]
                    subscription_rows_since.append({"user_id": user_id, "client_app": sanitize_label(app)})

        device_rows_since = []
        if table_exists(conn, "devices"):
            cols = table_columns(conn, "devices")
            if {"user_id", "last_seen_at", "last_handshake_at"}.intersection(cols):
                selected_cols = [
                    col
                    for col in ["user_id", "last_seen_at", "last_handshake_at", "profile_kind", "status"]
                    if col in cols
                ]
                rows = conn.execute(f"SELECT {', '.join(selected_cols)} FROM devices").fetchall()
                for row in rows:
                    try:
                        user_id = int(row["user_id"])
                    except (TypeError, ValueError):
                        continue
                    if user_id not in active_user_ids:
                        continue
                    last_seen = parse_time(row["last_seen_at"]) if "last_seen_at" in row.keys() else None
                    last_handshake = (
                        parse_time(row["last_handshake_at"]) if "last_handshake_at" in row.keys() else None
                    )
                    observed_at = max(
                        [value for value in [last_seen, last_handshake] if value is not None],
                        default=None,
                    )
                    if observed_at is None or observed_at < sent_at:
                        continue
                    device_rows_since.append(
                        {
                            "user_id": user_id,
                            "profile_kind": sanitize_label(row["profile_kind"] if "profile_kind" in row.keys() else ""),
                            "status": sanitize_label(row["status"] if "status" in row.keys() else ""),
                        }
                    )

        request_actions = Counter()
        if table_exists(conn, "request_events"):
            cols = table_columns(conn, "request_events")
            if {"user_id", "action", "created_at"}.issubset(cols):
                rows = conn.execute("SELECT user_id, action, created_at FROM request_events").fetchall()
                for row in rows:
                    try:
                        user_id = int(row["user_id"])
                    except (TypeError, ValueError):
                        continue
                    seen_at = parse_time(row["created_at"])
                    if user_id in active_user_ids and seen_at is not None and seen_at >= sent_at:
                        request_actions[sanitize_label(row["action"])] += 1

    subscription_users = {int(row["user_id"]) for row in subscription_rows_since}
    device_users = {int(row["user_id"]) for row in device_rows_since}
    return {
        "db_available": True,
        "active_user_count": len(active_user_ids),
        "subscription_refresh": {
            "active_users_with_subscription_pull_since_message": len(subscription_users),
            "subscription_pull_rows_since_message": len(subscription_rows_since),
            "client_app_counts": dict(sorted(Counter(row["client_app"] for row in subscription_rows_since).items())),
            "raw_user_ids_stored": False,
            "raw_tokens_stored": False,
            "raw_subscription_urls_stored": False,
        },
        "device_activity": {
            "active_users_with_device_activity_since_message": len(device_users),
            "device_activity_rows_since_message": len(device_rows_since),
            "profile_kind_counts": dict(sorted(Counter(row["profile_kind"] for row in device_rows_since).items())),
            "device_status_counts": dict(sorted(Counter(row["status"] for row in device_rows_since).items())),
            "raw_user_ids_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
        },
        "request_events": {
            "action_counts": dict(sorted(request_actions.items())),
            "config_requests_since_message": int(request_actions.get("config", 0)),
            "raw_user_ids_stored": False,
        },
        "combined": {
            "active_users_with_any_progress_since_message": len(subscription_users | device_users),
            "active_users_with_subscription_and_device_progress_since_message": len(subscription_users & device_users),
        },
    }


def derive_sent_at(message_send: dict[str, Any] | None, sent_at_arg: str) -> datetime:
    if sent_at_arg:
        parsed = parse_time(sent_at_arg)
        if parsed:
            return parsed
        raise LegacyMigrationProgressError("--sent-at is not a valid datetime")
    if isinstance(message_send, dict):
        parsed = parse_time(message_send.get("generated_at"))
        if parsed:
            return parsed
    raise LegacyMigrationProgressError("message send timestamp is missing; provide --sent-at")


def build_summary(
    *,
    packet: dict[str, Any],
    packet_source: dict[str, Any],
    message_send: dict[str, Any] | None,
    message_send_source: dict[str, Any] | None,
    replies: dict[str, Any] | None,
    db_progress: dict[str, Any],
    sent_at: datetime,
) -> dict[str, Any]:
    target = packet.get("target_audience") if isinstance(packet.get("target_audience"), dict) else {}
    active_target = int(target.get("active_subscription_count") or db_progress.get("active_user_count") or 0)
    sent_count = int((message_send or {}).get("sent_count") or 0)
    done_count = int((replies or {}).get("done_updated_count") or 0)
    failure_count = int((replies or {}).get("failure_count") or 0)
    subscription_users = int(
        (db_progress.get("subscription_refresh") or {}).get("active_users_with_subscription_pull_since_message") or 0
    )
    device_users = int(
        (db_progress.get("device_activity") or {}).get("active_users_with_device_activity_since_message") or 0
    )
    any_progress_users = int(
        (db_progress.get("combined") or {}).get("active_users_with_any_progress_since_message") or 0
    )
    if sent_count <= 0:
        status = "message_send_missing"
        operator_action = "send_legacy_migration_message"
    elif active_target and done_count >= active_target:
        status = "all_reported_updated"
        operator_action = "refresh_transport_usage_evidence"
    elif active_target and device_users >= active_target:
        status = "all_active_device_activity_seen_after_message"
        operator_action = "refresh_transport_usage_evidence"
    elif subscription_users > 0 and device_users > 0:
        status = "migration_progress_seen"
        operator_action = "monitor_remaining_client_replies_and_legacy_transport"
    elif any_progress_users > 0:
        status = "migration_partial_signal_seen"
        operator_action = "continue_collecting_legacy_migration_replies"
    else:
        status = "message_sent_no_progress_seen"
        operator_action = "nudge_legacy_clients_to_refresh_reality_profile"
    return {
        "schema_version": 1,
        "source": "collect_legacy_migration_progress.py",
        "generated_at": utc_now(),
        "status": status,
        "operator_action": operator_action,
        "sent_at": sent_at.isoformat().replace("+00:00", "Z"),
        "packet": {
            "source": packet_source["path"],
            "sha256": packet_source["sha256"],
            "decision": packet.get("decision"),
            "target_active_subscription_count": active_target,
        },
        "message_send": {
            "available": bool(message_send),
            "source": (message_send_source or {}).get("path"),
            "sha256": (message_send_source or {}).get("sha256"),
            "decision": (message_send or {}).get("decision"),
            "sent_count": sent_count,
            "selected_user_count": int((message_send or {}).get("selected_user_count") or 0),
        },
        "replies": {
            "available": bool(replies),
            "status": (replies or {}).get("status"),
            "total_replies": int((replies or {}).get("total_replies") or 0),
            "done_updated_count": done_count,
            "failure_count": failure_count,
        },
        "db_progress": db_progress,
        "privacy": {
            "raw_user_ids_stored": False,
            "raw_chat_ids_stored": False,
            "raw_tokens_stored": False,
            "raw_subscription_urls_stored": False,
            "raw_vpn_uris_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_stored": False,
            "raw_telegram_handle_stored": False,
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    db = summary.get("db_progress") if isinstance(summary.get("db_progress"), dict) else {}
    sub = db.get("subscription_refresh") if isinstance(db.get("subscription_refresh"), dict) else {}
    dev = db.get("device_activity") if isinstance(db.get("device_activity"), dict) else {}
    combined = db.get("combined") if isinstance(db.get("combined"), dict) else {}
    lines = [
        "# NL Legacy Migration Progress",
        "",
        f"- Status: `{summary['status']}`",
        f"- Operator action: `{summary['operator_action']}`",
        f"- Sent at: `{summary['sent_at']}`",
        f"- Sent count: `{summary['message_send']['sent_count']}`",
        f"- Active target: `{summary['packet']['target_active_subscription_count']}`",
        f"- Users with subscription pull after message: `{sub.get('active_users_with_subscription_pull_since_message', 0)}`",
        f"- Users with device activity after message: `{dev.get('active_users_with_device_activity_since_message', 0)}`",
        f"- Users with any progress after message: `{combined.get('active_users_with_any_progress_since_message', 0)}`",
        f"- Replies done updated: `{summary['replies']['done_updated_count']}`",
        f"- Reply failures: `{summary['replies']['failure_count']}`",
    ]
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect privacy-safe legacy migration progress.")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--message-send", type=Path, default=DEFAULT_MESSAGE_SEND_PATH)
    parser.add_argument("--replies", type=Path, default=DEFAULT_REPLIES_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    parser.add_argument("--sent-at", default="")
    parser.add_argument("--expect-packet-sha256", default="")
    parser.add_argument("--confirm-current-progress", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validate_write_args(args)
    packet, packet_source = load_json_with_source(args.packet)
    validate_expected_sha256(packet_source["sha256"], args.expect_packet_sha256)
    validate_packet(packet)
    message_send, message_send_source = load_optional_json(args.message_send)
    replies, _replies_source = load_optional_json(args.replies)
    sent_at = derive_sent_at(message_send, args.sent_at)
    now = datetime.now(UTC)
    db_progress = collect_db_progress(args.db_path, sent_at=sent_at, now=now)
    summary = build_summary(
        packet=packet,
        packet_source=packet_source,
        message_send=message_send,
        message_send_source=message_send_source,
        replies=replies,
        db_progress=db_progress,
        sent_at=sent_at,
    )
    findings = secret_findings(summary)
    if findings:
        raise LegacyMigrationProgressError(
            "refusing to write unsafe migration progress summary: "
            + ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        )

    if args.write:
        write_text(args.json_out, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        write_text(args.markdown_out, render_markdown(summary))
    if args.json or not args.write:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except LegacyMigrationProgressError as exc:
        print(f"error: {exc}")
        raise SystemExit(2)
