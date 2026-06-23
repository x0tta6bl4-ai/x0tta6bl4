#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Callable
from urllib import parse, request


DEFAULT_PACKET_PATH = Path("/var/lib/ghost-access/legacy-migration/latest.json")
DEFAULT_DB_PATH = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
CONFIRM_TEXT = "SEND_LEGACY_MIGRATION"
MAX_MESSAGE_BYTES = 4096

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


class LegacyMigrationSendError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def load_json_with_source(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    import hashlib

    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise LegacyMigrationSendError(f"required JSON artifact missing: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LegacyMigrationSendError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LegacyMigrationSendError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegacyMigrationSendError(f"{path} must be a JSON object")
    return payload, {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def validate_expected_sha256(actual_sha256: str, expected_sha256: str) -> None:
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise LegacyMigrationSendError("--expect-packet-sha256 must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise LegacyMigrationSendError(
            "migration packet sha256 mismatch: "
            f"expected={expected}, actual={actual_sha256.lower()}"
        )


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


def validate_packet(packet: dict[str, Any]) -> str:
    if packet.get("decision") != "LEGACY_CLIENT_MIGRATION_PACKET_READY":
        raise LegacyMigrationSendError("migration packet is not ready")
    send_policy = packet.get("send_policy") if isinstance(packet.get("send_policy"), dict) else {}
    if send_policy.get("automatic_broadcast_allowed") is True:
        raise LegacyMigrationSendError("migration packet unexpectedly allows automatic broadcast")
    privacy = packet.get("privacy") if isinstance(packet.get("privacy"), dict) else {}
    privacy_flags = [
        "raw_user_ids_printed",
        "raw_chat_ids_printed",
        "raw_tokens_printed",
        "raw_subscription_urls_printed",
        "raw_vpn_uris_printed",
        "raw_uuid_printed",
        "raw_ip_printed",
        "raw_telegram_handle_printed",
    ]
    if any(privacy.get(flag) is not False for flag in privacy_flags):
        raise LegacyMigrationSendError("migration packet privacy flags are not clean")
    migration = packet.get("migration_request") if isinstance(packet.get("migration_request"), dict) else {}
    message = str(migration.get("message_ru") or "").strip()
    if not message:
        raise LegacyMigrationSendError("migration packet message is missing")
    if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise LegacyMigrationSendError("migration message is too large for Telegram")
    findings = secret_findings(message)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise LegacyMigrationSendError(f"migration message is unsafe: {details}")
    return message


def read_active_user_ids(db_path: Path, *, now: datetime | None = None) -> list[int]:
    if not db_path.exists():
        return []
    current = now or datetime.now(UTC)
    uri = f"file:{db_path}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "users"):
            return []
        user_columns = table_columns(conn, "users")
        if "user_id" not in user_columns or "expires_at" not in user_columns:
            return []
        selected = ["user_id", "expires_at"]
        predicates = []
        if "subscription_token" in user_columns:
            predicates.extend(
                [
                    "subscription_token IS NOT NULL",
                    "TRIM(subscription_token) != ''",
                ]
            )
        if (
            table_exists(conn, "devices")
            and "user_id" in table_columns(conn, "devices")
        ):
            predicates.append("EXISTS (SELECT 1 FROM devices d WHERE d.user_id = users.user_id)")
        where_sql = f" WHERE {' AND '.join(predicates)}" if predicates else ""
        rows = conn.execute(
            f"SELECT {', '.join(selected)} FROM users{where_sql} ORDER BY user_id ASC"
        ).fetchall()
    user_ids: list[int] = []
    for row in rows:
        expiry = parse_expiry(row["expires_at"])
        if expiry and expiry > current:
            try:
                user_ids.append(int(row["user_id"]))
            except (TypeError, ValueError):
                continue
    return user_ids


def validate_apply_args(args: argparse.Namespace) -> None:
    if not args.apply:
        return
    if args.confirm != CONFIRM_TEXT:
        raise LegacyMigrationSendError(f"--confirm {CONFIRM_TEXT} is required with --apply")
    if not str(args.expect_packet_sha256 or "").strip():
        raise LegacyMigrationSendError("--expect-packet-sha256 is required with --apply")
    if int(args.limit or 0) <= 0:
        raise LegacyMigrationSendError("--limit must be positive with --apply")
    if not str(args.bot_token or "").strip():
        raise LegacyMigrationSendError("Telegram bot token is required with --apply")


def send_telegram_message(*, bot_token: str, user_id: int, text: str, timeout: float) -> str:
    data = parse.urlencode(
        {
            "chat_id": str(user_id),
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        lowered = str(exc).lower()
        if "blocked" in lowered or "deactivated" in lowered or "chat not found" in lowered:
            return "blocked"
        return "failed"
    return "sent" if payload.get("ok") is True else "failed"


def build_report(
    *,
    packet_source: dict[str, Any],
    apply: bool,
    candidate_count: int,
    selected_count: int,
    sent: int,
    failed: int,
    blocked: int,
    message_bytes: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "send_legacy_client_migration_message.py",
        "generated_at": utc_now(),
        "mode": "apply" if apply else "dry_run",
        "decision": "LEGACY_CLIENT_MIGRATION_MESSAGE_SENT" if apply else "LEGACY_CLIENT_MIGRATION_MESSAGE_DRY_RUN",
        "packet": {
            "source": packet_source["path"],
            "sha256": packet_source["sha256"],
            "size_bytes": packet_source["size_bytes"],
        },
        "candidate_active_user_count": candidate_count,
        "selected_user_count": selected_count,
        "sent_count": sent,
        "failed_count": failed,
        "blocked_count": blocked,
        "message_bytes": message_bytes,
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


def run(
    argv: list[str] | None = None,
    *,
    sender: Callable[[int, str], str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Dry-run or send legacy migration message to active users.")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expect-packet-sha256", default="")
    parser.add_argument("--bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validate_apply_args(args)
    packet, packet_source = load_json_with_source(args.packet)
    validate_expected_sha256(packet_source["sha256"], args.expect_packet_sha256)
    message = validate_packet(packet)
    user_ids = read_active_user_ids(args.db_path)
    limit = max(0, int(args.limit or 0))
    selected = user_ids[:limit] if limit else []

    sent = failed = blocked = 0
    if args.apply:
        if sender is None:
            sender = lambda uid, text: send_telegram_message(
                bot_token=args.bot_token,
                user_id=uid,
                text=text,
                timeout=float(args.timeout),
            )
        for uid in selected:
            outcome = sender(uid, message)
            if outcome == "sent":
                sent += 1
            elif outcome == "blocked":
                blocked += 1
            else:
                failed += 1
            time.sleep(max(0.0, float(args.sleep_seconds)))

    report = build_report(
        packet_source=packet_source,
        apply=bool(args.apply),
        candidate_count=len(user_ids),
        selected_count=len(selected),
        sent=sent,
        failed=failed,
        blocked=blocked,
        message_bytes=len(message.encode("utf-8")),
    )
    findings = secret_findings(report)
    if findings:
        raise LegacyMigrationSendError(
            "refusing to print unsafe send report: "
            + ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        )
    if args.json or True:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except LegacyMigrationSendError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
