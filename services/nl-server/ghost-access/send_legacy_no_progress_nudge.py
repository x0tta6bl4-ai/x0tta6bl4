#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
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
DEFAULT_MESSAGE_SEND_PATH = Path("/var/lib/ghost-access/legacy-migration/message-send.json")
DEFAULT_REPLIES_PATH = Path("/var/lib/ghost-access/legacy-migration/replies.json")
DEFAULT_DB_PATH = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
DEFAULT_JSON_OUT = Path("/var/lib/ghost-access/legacy-migration/no-progress-nudge.json")
DEFAULT_DRY_RUN_REPORT_PATH = Path("/var/lib/ghost-access/legacy-migration/no-progress-nudge-dry-run.json")
DEFAULT_SUBSCRIPTION_PAYLOAD_STATUS_PATH = Path("/var/lib/ghost-access/subscription-payload/latest.json")
DEFAULT_TRANSPORT_USAGE_STATUS_PATH = Path("/var/lib/ghost-access/transport-usage/latest.json")
CONFIRM_TEXT = "SEND_LEGACY_NO_PROGRESS_NUDGE"
MAX_MESSAGE_BYTES = 4096
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


class LegacyNoProgressNudgeError(ValueError):
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
        raise LegacyNoProgressNudgeError(f"required JSON artifact missing: {path}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise LegacyNoProgressNudgeError(f"{path} is not valid UTF-8 JSON: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise LegacyNoProgressNudgeError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise LegacyNoProgressNudgeError(f"{path} must be a JSON object")
    return payload, {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json_with_source(path)[0]


def validate_expected_sha256(actual_sha256: str, expected_sha256: str) -> None:
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise LegacyNoProgressNudgeError("--expect-packet-sha256 must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise LegacyNoProgressNudgeError(
            "migration packet sha256 mismatch: "
            f"expected={expected}, actual={actual_sha256.lower()}"
        )


def validate_expected_file_sha256(*, actual_sha256: str, expected_sha256: str, flag_name: str) -> None:
    expected = (expected_sha256 or "").strip().lower()
    if not expected:
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise LegacyNoProgressNudgeError(f"{flag_name} must be a 64-character hex digest")
    if actual_sha256.lower() != expected:
        raise LegacyNoProgressNudgeError(
            f"{flag_name} mismatch: expected={expected}, actual={actual_sha256.lower()}"
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


def validate_packet(packet: dict[str, Any]) -> None:
    if packet.get("decision") != "LEGACY_CLIENT_MIGRATION_PACKET_READY":
        raise LegacyNoProgressNudgeError("migration packet is not ready")
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
        raise LegacyNoProgressNudgeError("migration packet privacy flags are not clean")


def validate_apply_args(args: argparse.Namespace) -> None:
    if not args.apply:
        return
    if args.confirm != CONFIRM_TEXT:
        raise LegacyNoProgressNudgeError(f"--confirm {CONFIRM_TEXT} is required with --apply")
    if not str(args.expect_packet_sha256 or "").strip():
        raise LegacyNoProgressNudgeError("--expect-packet-sha256 is required with --apply")
    if not str(args.expect_dry_run_sha256 or "").strip():
        raise LegacyNoProgressNudgeError("--expect-dry-run-sha256 is required with --apply")
    if not str(args.expect_subscription_payload_sha256 or "").strip():
        raise LegacyNoProgressNudgeError("--expect-subscription-payload-sha256 is required with --apply")
    if not str(args.expect_transport_usage_sha256 or "").strip():
        raise LegacyNoProgressNudgeError("--expect-transport-usage-sha256 is required with --apply")
    if not str(args.expect_replies_sha256 or "").strip():
        raise LegacyNoProgressNudgeError("--expect-replies-sha256 is required with --apply")
    if int(args.limit or 0) <= 0:
        raise LegacyNoProgressNudgeError("--limit must be positive with --apply")
    if not str(args.bot_token or "").strip():
        raise LegacyNoProgressNudgeError("Telegram bot token is required with --apply")


def validate_subscription_payload_status(
    *,
    report: dict[str, Any],
    report_source: dict[str, Any],
    expected_sha256: str,
    now: datetime,
    max_age_minutes: int,
) -> None:
    validate_expected_file_sha256(
        actual_sha256=report_source["sha256"],
        expected_sha256=expected_sha256,
        flag_name="--expect-subscription-payload-sha256",
    )
    if report.get("decision") != "LIVE_SUBSCRIPTION_PAYLOAD_SAFE" or report.get("ok") is not True:
        raise LegacyNoProgressNudgeError("subscription payload status is not safe")
    generated_at = parse_time(report.get("generated_at"))
    if generated_at is None:
        raise LegacyNoProgressNudgeError("subscription payload generated_at is missing or invalid")
    if now - generated_at > timedelta(minutes=max(0, int(max_age_minutes))):
        raise LegacyNoProgressNudgeError(
            f"subscription payload status is stale: max_age_minutes={max_age_minutes}"
        )
    anti_dpi = report.get("anti_dpi") if isinstance(report.get("anti_dpi"), dict) else {}
    checked_count = int(report.get("checked_subscription_count") or 0)
    ready_count = int(anti_dpi.get("ready_subscription_count") or 0)
    if checked_count <= 0:
        raise LegacyNoProgressNudgeError("subscription payload has no checked active subscriptions")
    if anti_dpi.get("status") != "ready" or anti_dpi.get("ready") is not True:
        raise LegacyNoProgressNudgeError("subscription payload anti-DPI status is not ready")
    if anti_dpi.get("reality_only") is not True:
        raise LegacyNoProgressNudgeError("subscription payload is not Reality-only")
    if anti_dpi.get("legacy_transports_absent") is not True:
        raise LegacyNoProgressNudgeError("subscription payload still contains legacy transports")
    if anti_dpi.get("all_checked_have_primary_reality_443") is not True:
        raise LegacyNoProgressNudgeError("subscription payload is missing primary Reality 443")
    if anti_dpi.get("all_checked_have_secondary_reality_port") is not True:
        raise LegacyNoProgressNudgeError("subscription payload is missing secondary Reality port")
    if ready_count != checked_count:
        raise LegacyNoProgressNudgeError(
            f"subscription payload anti-DPI ready count mismatch: ready={ready_count}, checked={checked_count}"
        )
    privacy = report.get("privacy") if isinstance(report.get("privacy"), dict) else {}
    if (
        privacy.get("raw_tokens_printed") is not False
        or privacy.get("raw_profile_uris_printed") is not False
        or privacy.get("raw_uuid_printed") is not False
        or privacy.get("raw_host_printed") is not False
    ):
        raise LegacyNoProgressNudgeError("subscription payload privacy flags are not clean")
    if (
        anti_dpi.get("raw_tokens_or_uris_printed") is not False
        or anti_dpi.get("raw_uuid_printed") is not False
        or anti_dpi.get("raw_host_printed") is not False
    ):
        raise LegacyNoProgressNudgeError("subscription payload anti-DPI privacy flags are not clean")


def validate_transport_usage_status(
    *,
    report: dict[str, Any],
    report_source: dict[str, Any],
    expected_sha256: str,
    now: datetime,
    max_age_minutes: int,
) -> None:
    validate_expected_file_sha256(
        actual_sha256=report_source["sha256"],
        expected_sha256=expected_sha256,
        flag_name="--expect-transport-usage-sha256",
    )
    if report.get("decision") not in {"TRANSPORT_USAGE_OK", "TRANSPORT_USAGE_ATTENTION"}:
        raise LegacyNoProgressNudgeError("transport usage status decision is not recognized")
    generated_at = parse_time(report.get("generated_at"))
    if generated_at is None:
        raise LegacyNoProgressNudgeError("transport usage generated_at is missing or invalid")
    if now - generated_at > timedelta(minutes=max(0, int(max_age_minutes))):
        raise LegacyNoProgressNudgeError(
            f"transport usage status is stale: max_age_minutes={max_age_minutes}"
        )
    privacy = report.get("privacy") if isinstance(report.get("privacy"), dict) else {}
    if (
        privacy.get("raw_identifiers_stored") is not False
        or privacy.get("raw_ip_stored") is not False
        or privacy.get("raw_email_stored") is not False
        or privacy.get("raw_target_host_stored") is not False
        or privacy.get("raw_nginx_source_ip_stored") is True
        or privacy.get("raw_user_agent_stored") is True
    ):
        raise LegacyNoProgressNudgeError("transport usage privacy flags are not clean")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    restart_relevant = report.get("restart_relevant") is True or summary.get("restart_relevant") is True
    if restart_relevant:
        raise LegacyNoProgressNudgeError("transport usage has restart-relevant legacy findings")


def validate_replies_status(
    *,
    report: dict[str, Any],
    report_source: dict[str, Any],
    expected_sha256: str,
    packet_sha256: str,
    now: datetime,
    max_age_minutes: int,
) -> None:
    validate_expected_file_sha256(
        actual_sha256=report_source["sha256"],
        expected_sha256=expected_sha256,
        flag_name="--expect-replies-sha256",
    )
    if report.get("status") not in {
        "no_client_replies",
        "partial_client_replies",
        "all_reported_updated_by_count",
    }:
        raise LegacyNoProgressNudgeError("replies status is not recognized")
    generated_at = parse_time(report.get("generated_at"))
    if generated_at is None:
        raise LegacyNoProgressNudgeError("replies generated_at is missing or invalid")
    if now - generated_at > timedelta(minutes=max(0, int(max_age_minutes))):
        raise LegacyNoProgressNudgeError(
            f"replies status is stale: max_age_minutes={max_age_minutes}"
        )
    packet = report.get("packet") if isinstance(report.get("packet"), dict) else {}
    if str(packet.get("sha256") or "").lower() != packet_sha256.lower():
        raise LegacyNoProgressNudgeError("replies packet sha256 does not match current packet")
    privacy = report.get("privacy") if isinstance(report.get("privacy"), dict) else {}
    privacy_flags = [
        "raw_user_ids_stored",
        "raw_chat_ids_stored",
        "raw_tokens_stored",
        "raw_subscription_urls_stored",
        "raw_vpn_uris_stored",
        "raw_uuid_stored",
        "raw_ip_stored",
        "raw_telegram_handle_stored",
    ]
    if any(privacy.get(flag) is not False for flag in privacy_flags):
        raise LegacyNoProgressNudgeError("replies privacy flags are not clean")
    events = report.get("events")
    if events is not None and not isinstance(events, list):
        raise LegacyNoProgressNudgeError("replies events must be a list")


def validate_dry_run_report(
    *,
    report: dict[str, Any],
    report_source: dict[str, Any],
    expected_sha256: str,
    packet_sha256: str,
    selector_counts: dict[str, int],
    now: datetime,
    max_age_minutes: int,
) -> None:
    validate_expected_file_sha256(
        actual_sha256=report_source["sha256"],
        expected_sha256=expected_sha256,
        flag_name="--expect-dry-run-sha256",
    )
    if report.get("decision") != "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN":
        raise LegacyNoProgressNudgeError("dry-run report is not a no-progress nudge dry-run")
    if report.get("mode") != "dry_run":
        raise LegacyNoProgressNudgeError("dry-run report mode must be dry_run")
    generated_at = parse_time(report.get("generated_at"))
    if generated_at is None:
        raise LegacyNoProgressNudgeError("dry-run report generated_at is missing or invalid")
    if now - generated_at > timedelta(minutes=max(0, int(max_age_minutes))):
        raise LegacyNoProgressNudgeError(
            f"dry-run report is stale: max_age_minutes={max_age_minutes}"
        )
    packet = report.get("packet") if isinstance(report.get("packet"), dict) else {}
    if str(packet.get("sha256") or "").lower() != packet_sha256.lower():
        raise LegacyNoProgressNudgeError("dry-run report packet sha256 does not match current packet")
    privacy = report.get("privacy") if isinstance(report.get("privacy"), dict) else {}
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
        raise LegacyNoProgressNudgeError("dry-run report privacy flags are not clean")
    zero_fields = ["selected_user_count", "sent_count", "failed_count", "blocked_count"]
    for field in zero_fields:
        if int(report.get(field) or 0) != 0:
            raise LegacyNoProgressNudgeError(f"dry-run report {field} must be zero")
    count_fields = [
        "active_user_count",
        "progress_user_count",
        "reply_user_count",
        "no_progress_candidate_count",
    ]
    for field in count_fields:
        expected = int(selector_counts.get(field, 0))
        actual = int(report.get(field) or 0)
        if actual != expected:
            raise LegacyNoProgressNudgeError(
                f"dry-run report {field} mismatch: expected={expected}, actual={actual}"
            )


def nudge_message() -> str:
    message = (
        "Если VPN всё ещё не подключается, обновите профиль ещё раз: откройте этого бота, "
        "нажмите Подключить и импортируйте свежий Reality-профиль. "
        "В клиенте удалите старые Ghost Access профили с xhttp, ws или портом 8443. "
        "После проверки ответьте только одним вариантом: done updated, fail import, "
        "fail timeout или fail no-internet. "
        "Не присылайте ссылки, QR-коды, UUID, IP-адреса, скриншоты или логи."
    )
    if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise LegacyNoProgressNudgeError("nudge message is too large for Telegram")
    findings = secret_findings(message)
    if findings:
        details = ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        raise LegacyNoProgressNudgeError(f"nudge message is unsafe: {details}")
    return message


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


def is_technical_subscription_access(user_agent: Any, ip_address: Any = None, client_app: Any = None) -> bool:
    ua_lower = str(user_agent or "").strip().lower()
    app_lower = str(client_app or "").strip().lower()
    ip_text = str(ip_address or "").strip()
    if ip_text in TECHNICAL_SUBSCRIPTION_IPS:
        return True
    return any(ua_lower.startswith(prefix) or app_lower.startswith(prefix) for prefix in TECHNICAL_SUBSCRIPTION_UA_PREFIXES)


def reporter_label(*, packet_sha256: str, user_id: int) -> str:
    digest = hashlib.sha256(f"{packet_sha256}:{user_id}".encode("utf-8")).hexdigest()[:16]
    return f"legacy-client-{digest}"


def replied_reporter_labels(replies: dict[str, Any] | None) -> set[str]:
    labels: set[str] = set()
    if not isinstance(replies, dict):
        return labels
    events = replies.get("events")
    if not isinstance(events, list):
        return labels
    for event in events:
        if isinstance(event, dict) and isinstance(event.get("reporter_label"), str):
            labels.add(event["reporter_label"])
    return labels


def sent_at_from_message(message_send: dict[str, Any], sent_at_arg: str) -> datetime:
    parsed = parse_time(sent_at_arg) if sent_at_arg else parse_time(message_send.get("generated_at"))
    if parsed is None:
        raise LegacyNoProgressNudgeError("message send timestamp is missing; provide --sent-at")
    return parsed


def read_active_user_ids(conn: sqlite3.Connection, *, now: datetime) -> list[int]:
    if not table_exists(conn, "users"):
        return []
    columns = table_columns(conn, "users")
    if not {"user_id", "expires_at"}.issubset(columns):
        return []
    predicates: list[str] = []
    if "subscription_token" in columns:
        predicates.extend(["subscription_token IS NOT NULL", "TRIM(subscription_token) != ''"])
    if table_exists(conn, "devices") and "user_id" in table_columns(conn, "devices"):
        predicates.append("EXISTS (SELECT 1 FROM devices d WHERE d.user_id = users.user_id)")
    where_sql = f" WHERE {' AND '.join(predicates)}" if predicates else ""
    rows = conn.execute(f"SELECT user_id, expires_at FROM users{where_sql} ORDER BY user_id ASC").fetchall()
    user_ids: list[int] = []
    for row in rows:
        if is_active_expiry(row["expires_at"], now=now):
            try:
                user_ids.append(int(row["user_id"]))
            except (TypeError, ValueError):
                continue
    return user_ids


def read_progress_user_ids(conn: sqlite3.Connection, *, sent_at: datetime) -> set[int]:
    user_ids: set[int] = set()
    if table_exists(conn, "devices"):
        columns = table_columns(conn, "devices")
        selected = [col for col in ["user_id", "last_seen_at", "last_handshake_at"] if col in columns]
        if "user_id" in selected and len(selected) > 1:
            rows = conn.execute(f"SELECT {', '.join(selected)} FROM devices").fetchall()
            for row in rows:
                observed = [
                    parse_time(row[key])
                    for key in ("last_seen_at", "last_handshake_at")
                    if key in row.keys()
                ]
                if any(value is not None and value >= sent_at for value in observed):
                    try:
                        user_ids.add(int(row["user_id"]))
                    except (TypeError, ValueError):
                        continue
    if table_exists(conn, "subscription_accesses"):
        columns = table_columns(conn, "subscription_accesses")
        if {"user_id", "last_seen_at"}.issubset(columns):
            selected = ["user_id", "last_seen_at"]
            for col in ["user_agent", "client_app", "ip_address"]:
                if col in columns:
                    selected.append(col)
            rows = conn.execute(f"SELECT {', '.join(selected)} FROM subscription_accesses").fetchall()
            for row in rows:
                seen_at = parse_time(row["last_seen_at"])
                if seen_at is None or seen_at < sent_at:
                    continue
                user_agent = row["user_agent"] if "user_agent" in row.keys() else ""
                client_app = row["client_app"] if "client_app" in row.keys() else ""
                ip_address = row["ip_address"] if "ip_address" in row.keys() else ""
                if is_technical_subscription_access(user_agent, ip_address, client_app):
                    continue
                try:
                    user_ids.add(int(row["user_id"]))
                except (TypeError, ValueError):
                    continue
    return user_ids


def select_no_progress_user_ids(
    db_path: Path,
    *,
    sent_at: datetime,
    packet_sha256: str,
    replies: dict[str, Any] | None,
    now: datetime,
) -> tuple[list[int], dict[str, int]]:
    if not db_path.exists():
        return [], {
            "db_available": 0,
            "active_user_count": 0,
            "progress_user_count": 0,
            "reply_user_count": 0,
            "no_progress_candidate_count": 0,
        }
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        active = read_active_user_ids(conn, now=now)
        progress = read_progress_user_ids(conn, sent_at=sent_at)
    reply_labels = replied_reporter_labels(replies)
    reply_user_ids = {
        user_id
        for user_id in active
        if reporter_label(packet_sha256=packet_sha256, user_id=user_id) in reply_labels
    }
    active_set = set(active)
    no_progress = sorted(active_set - progress - reply_user_ids)
    return no_progress, {
        "db_available": 1,
        "active_user_count": len(active),
        "progress_user_count": len(active_set & progress),
        "reply_user_count": len(reply_user_ids),
        "no_progress_candidate_count": len(no_progress),
    }


def validate_min_age(*, sent_at: datetime, now: datetime, min_age_minutes: int) -> None:
    if now - sent_at < timedelta(minutes=max(0, int(min_age_minutes))):
        raise LegacyNoProgressNudgeError(
            f"migration message is too recent for a no-progress nudge: min_age_minutes={min_age_minutes}"
        )


def validate_cooldown(*, report_paths: list[Path], now: datetime, cooldown_hours: float) -> None:
    if cooldown_hours <= 0:
        return
    seen: set[str] = set()
    for report_path in report_paths:
        key = str(report_path)
        if key in seen or not report_path.exists():
            continue
        seen.add(key)
        payload = load_optional_json(report_path)
        if not isinstance(payload, dict):
            continue
        if payload.get("decision") != "LEGACY_NO_PROGRESS_NUDGE_SENT":
            continue
        generated_at = parse_time(payload.get("generated_at"))
        if generated_at and now - generated_at < timedelta(hours=float(cooldown_hours)):
            raise LegacyNoProgressNudgeError(
                "no-progress nudge cooldown is active: "
                f"cooldown_hours={cooldown_hours}, last_apply_report={report_path}"
            )


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
    sent_at: datetime,
    selector_counts: dict[str, int],
    selected_count: int,
    sent: int,
    failed: int,
    blocked: int,
    message_bytes: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "send_legacy_no_progress_nudge.py",
        "generated_at": utc_now(),
        "mode": "apply" if apply else "dry_run",
        "decision": "LEGACY_NO_PROGRESS_NUDGE_SENT" if apply else "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
        "sent_at": sent_at.isoformat().replace("+00:00", "Z"),
        "packet": {
            "source": packet_source["path"],
            "sha256": packet_source["sha256"],
            "size_bytes": packet_source["size_bytes"],
        },
        **selector_counts,
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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def run(
    argv: list[str] | None = None,
    *,
    sender: Callable[[int, str], str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Dry-run or send a nudge to legacy users with no progress.")
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET_PATH)
    parser.add_argument("--message-send", type=Path, default=DEFAULT_MESSAGE_SEND_PATH)
    parser.add_argument("--replies", type=Path, default=DEFAULT_REPLIES_PATH)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--dry-run-report", type=Path, default=DEFAULT_DRY_RUN_REPORT_PATH)
    parser.add_argument("--subscription-payload-status", type=Path, default=DEFAULT_SUBSCRIPTION_PAYLOAD_STATUS_PATH)
    parser.add_argument("--transport-usage-status", type=Path, default=DEFAULT_TRANSPORT_USAGE_STATUS_PATH)
    parser.add_argument("--sent-at", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--min-age-minutes", type=int, default=30)
    parser.add_argument("--cooldown-hours", type=float, default=12.0)
    parser.add_argument("--dry-run-max-age-minutes", type=int, default=30)
    parser.add_argument("--subscription-payload-max-age-minutes", type=int, default=30)
    parser.add_argument("--transport-usage-max-age-minutes", type=int, default=15)
    parser.add_argument("--replies-max-age-minutes", type=int, default=30)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the aggregate report to --json-out. Dry-run mode stays non-sending.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--expect-packet-sha256", default="")
    parser.add_argument("--expect-dry-run-sha256", default="")
    parser.add_argument("--expect-subscription-payload-sha256", default="")
    parser.add_argument("--expect-transport-usage-sha256", default="")
    parser.add_argument("--expect-replies-sha256", default="")
    parser.add_argument("--bot-token", default=os.getenv("TELEGRAM_BOT_TOKEN", "").strip())
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.05)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    validate_apply_args(args)
    packet, packet_source = load_json_with_source(args.packet)
    validate_expected_sha256(packet_source["sha256"], args.expect_packet_sha256)
    validate_packet(packet)
    message_send, _message_source = load_json_with_source(args.message_send)
    sent_at = sent_at_from_message(message_send, args.sent_at)
    now = datetime.now(UTC)
    if args.apply:
        replies, replies_source = load_json_with_source(args.replies)
        validate_replies_status(
            report=replies,
            report_source=replies_source,
            expected_sha256=args.expect_replies_sha256,
            packet_sha256=packet_source["sha256"],
            now=now,
            max_age_minutes=int(args.replies_max_age_minutes),
        )
    else:
        replies = load_optional_json(args.replies)
    validate_min_age(sent_at=sent_at, now=now, min_age_minutes=int(args.min_age_minutes))
    if args.apply:
        validate_cooldown(
            report_paths=[DEFAULT_JSON_OUT, args.json_out],
            now=now,
            cooldown_hours=float(args.cooldown_hours),
        )

    user_ids, selector_counts = select_no_progress_user_ids(
        args.db_path,
        sent_at=sent_at,
        packet_sha256=packet_source["sha256"],
        replies=replies,
        now=now,
    )
    if args.apply:
        subscription_status, subscription_status_source = load_json_with_source(args.subscription_payload_status)
        validate_subscription_payload_status(
            report=subscription_status,
            report_source=subscription_status_source,
            expected_sha256=args.expect_subscription_payload_sha256,
            now=now,
            max_age_minutes=int(args.subscription_payload_max_age_minutes),
        )
        transport_status, transport_status_source = load_json_with_source(args.transport_usage_status)
        validate_transport_usage_status(
            report=transport_status,
            report_source=transport_status_source,
            expected_sha256=args.expect_transport_usage_sha256,
            now=now,
            max_age_minutes=int(args.transport_usage_max_age_minutes),
        )
        dry_run_report, dry_run_source = load_json_with_source(args.dry_run_report)
        validate_dry_run_report(
            report=dry_run_report,
            report_source=dry_run_source,
            expected_sha256=args.expect_dry_run_sha256,
            packet_sha256=packet_source["sha256"],
            selector_counts=selector_counts,
            now=now,
            max_age_minutes=int(args.dry_run_max_age_minutes),
        )
    limit = max(0, int(args.limit or 0))
    selected = user_ids[:limit] if args.apply else []
    message = nudge_message()
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
        sent_at=sent_at,
        selector_counts=selector_counts,
        selected_count=len(selected),
        sent=sent,
        failed=failed,
        blocked=blocked,
        message_bytes=len(message.encode("utf-8")),
    )
    findings = secret_findings(report)
    if findings:
        raise LegacyNoProgressNudgeError(
            "refusing to print unsafe nudge report: "
            + ", ".join(f"{item['path']}:{item['kind']}" for item in findings[:5])
        )
    if args.apply or args.write:
        write_text(args.json_out, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    if args.json or True:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except LegacyNoProgressNudgeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
