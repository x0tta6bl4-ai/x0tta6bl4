#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Callable
from urllib import error, parse, request


DEFAULT_ENV_FILE = Path("/opt/ghost-access-bot/shared/.env")
DEFAULT_DB_PATH = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
DEFAULT_EXPECTED_PORTS = (443, 2083)
DEFAULT_LIMIT = 10
DEFAULT_TIMEOUT = 12.0
ANTI_DPI_PRIMARY_PORT = 443
ANTI_DPI_SECONDARY_PORTS = {2083}
SUPPORTED_REALITY_FINGERPRINTS = {
    "chrome",
    "firefox",
    "safari",
    "ios",
    "android",
    "edge",
    "360",
    "qq",
    "random",
    "randomized",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read-only check that live subscription payloads expose only current Reality profiles."
    )
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--subscription-base-url", default="")
    parser.add_argument("--expected-port", type=int, action="append", dest="expected_ports")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--expired-limit", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--include-expired", action="store_true")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def resolve_subscription_base_url(args: argparse.Namespace) -> str:
    if args.subscription_base_url.strip():
        return args.subscription_base_url.strip().rstrip("/")
    env = read_env_file(args.env_file)
    return (
        env.get("SUBSCRIPTION_BASE_URL")
        or env.get("WEB_SUBSCRIPTION_BASE_URL")
        or ""
    ).strip().rstrip("/")


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except sqlite3.Error:
        return set()
    return {str(row[1]) for row in rows}


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


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


def expiry_is_active(value: Any, now: datetime | None = None) -> bool:
    parsed = parse_expiry(value)
    if parsed is None:
        return False
    return parsed > (now or datetime.now(UTC))


def read_subscription_tokens(
    db_path: Path,
    limit: int,
    include_expired: bool = False,
    expired_only: bool = False,
) -> list[str]:
    max_tokens = int(limit)
    if max_tokens <= 0:
        return []
    if not db_path.exists():
        return []
    with sqlite3.connect(str(db_path)) as conn:
        if not table_exists(conn, "users"):
            return []
        user_columns = table_columns(conn, "users")
        if "subscription_token" not in user_columns:
            return []
        predicates = [
            "subscription_token IS NOT NULL",
            "TRIM(subscription_token) != ''",
        ]
        selected = ["subscription_token"]
        if "expires_at" in user_columns:
            selected.append("expires_at")
        if (
            "user_id" in user_columns
            and table_exists(conn, "devices")
            and "user_id" in table_columns(conn, "devices")
        ):
            predicates.append("EXISTS (SELECT 1 FROM devices d WHERE d.user_id = users.user_id)")
        order_parts = []
        if "subscription_updated_at" in user_columns:
            order_parts.append("COALESCE(subscription_updated_at, '') DESC")
        if "user_id" in user_columns:
            order_parts.append("user_id DESC")
        order_sql = f" ORDER BY {', '.join(order_parts)}" if order_parts else ""
        sql = (
            f"SELECT {', '.join(selected)} FROM users WHERE "
            + " AND ".join(predicates)
            + order_sql
        )
        rows = conn.execute(sql).fetchall()
    tokens: list[str] = []
    now = datetime.now(UTC)
    for row in rows:
        active = len(row) <= 1 or expiry_is_active(row[1], now)
        if expired_only and active:
            continue
        if not expired_only and not include_expired and not active:
            continue
        token = str(row[0]).strip()
        if token:
            tokens.append(token)
        if len(tokens) >= max_tokens:
            break
    return tokens


def read_expired_subscription_tokens(db_path: Path, limit: int) -> list[str]:
    return read_subscription_tokens(db_path, limit, include_expired=True, expired_only=True)


def decode_subscription_body(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace").strip()
    if "://" in text:
        return text
    try:
        padded = text + "=" * (-len(text) % 4)
        return base64.b64decode(padded, validate=False).decode("utf-8", errors="replace")
    except Exception:
        return text


def contains_error_text(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("not found", "404", "error", "forbidden"))


def _port_from_line(line: str) -> int | None:
    try:
        parsed = parse.urlsplit(line.strip())
        if parsed.port is not None:
            return int(parsed.port)
    except ValueError:
        pass
    authority = (line.split("@", 1)[1] if "@" in line else "").split("?", 1)[0].split("#", 1)[0]
    match = re.search(r":(\d+)$", authority)
    return int(match.group(1)) if match else None


def _first_query_value(query: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        values = query.get(key.lower()) or []
        if values:
            return str(values[0]).strip()
    return ""


def _query_values(query: dict[str, list[str]], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(str(item).strip() for item in (query.get(key.lower()) or []))
    return values


def _short_id_format_ok(value: str) -> bool:
    if value == "":
        return True
    return bool(re.fullmatch(r"[0-9a-fA-F]{2,16}", value)) and len(value) % 2 == 0


def _fingerprint_is_supported(value: str) -> bool:
    text = value.strip()
    lowered = text.lower()
    return lowered in SUPPORTED_REALITY_FINGERPRINTS or text.startswith("Hello")


def classify_profile(line: str) -> dict[str, Any] | None:
    text = line.strip()
    lowered = text.lower()
    if lowered.startswith("vless://"):
        parsed = parse.urlsplit(text)
        query = {
            str(key).lower(): values
            for key, values in parse.parse_qs(parsed.query, keep_blank_values=True).items()
        }
        network = (query.get("type") or query.get("net") or [""])[0].lower()
        security = (query.get("security") or [""])[0].lower()
        if network in {"xhttp", "ws"}:
            transport = network
        elif security == "reality":
            transport = "reality"
        else:
            transport = "other_vless"
        short_id_keys = {"sid", "shortid"}
        short_ids = _query_values(query, "sid", "shortid")
        fingerprint = _first_query_value(query, "fp", "fingerprint")
        return {
            "scheme": "vless",
            "transport": transport,
            "security": security,
            "network": network,
            "port": _port_from_line(text),
            "has_reality_public_key": bool(
                _first_query_value(query, "pbk", "publickey", "password")
            ),
            "has_reality_short_id": any(key in query for key in short_id_keys),
            "has_non_empty_reality_short_id": any(short_ids),
            "reality_short_ids": short_ids,
            "has_valid_reality_short_id": all(_short_id_format_ok(value) for value in short_ids),
            "reality_fingerprint": fingerprint,
            "has_tls_fingerprint": bool(fingerprint),
            "has_supported_tls_fingerprint": bool(fingerprint)
            and _fingerprint_is_supported(fingerprint),
            "uses_unsafe_tls_fingerprint": fingerprint.lower() == "unsafe",
            "has_server_name": bool(
                _first_query_value(query, "sni", "servername", "server_name", "host")
            ),
            "uses_xtls_vision": _first_query_value(query, "flow").lower() == "xtls-rprx-vision",
        }
    for scheme in ("vmess", "trojan", "ss"):
        if lowered.startswith(f"{scheme}://"):
            return {"scheme": scheme, "transport": scheme, "security": "", "port": None}
    return None


def summarize_anti_dpi_quality(
    *,
    profiles: list[dict[str, Any]],
    ports: list[int],
    unexpected_ports: list[int],
    disallowed_count: int,
) -> dict[str, Any]:
    reality_profiles = [profile for profile in profiles if profile.get("transport") == "reality"]
    reality_ports = sorted(
        {
            int(profile["port"])
            for profile in reality_profiles
            if isinstance(profile.get("port"), int)
        }
    )
    primary_ready = ANTI_DPI_PRIMARY_PORT in reality_ports
    secondary_ready = any(port in ANTI_DPI_SECONDARY_PORTS for port in reality_ports)
    missing_public_key = sum(
        1 for profile in reality_profiles if profile.get("has_reality_public_key") is not True
    )
    missing_fingerprint = sum(
        1 for profile in reality_profiles if profile.get("has_tls_fingerprint") is not True
    )
    unsupported_fingerprint = sum(
        1
        for profile in reality_profiles
        if profile.get("has_tls_fingerprint") is True
        and profile.get("has_supported_tls_fingerprint") is not True
    )
    unsafe_fingerprint = sum(
        1 for profile in reality_profiles if profile.get("uses_unsafe_tls_fingerprint") is True
    )
    missing_server_name = sum(
        1 for profile in reality_profiles if profile.get("has_server_name") is not True
    )
    missing_short_id = sum(
        1 for profile in reality_profiles if profile.get("has_reality_short_id") is not True
    )
    empty_short_id = sum(
        1
        for profile in reality_profiles
        if profile.get("has_reality_short_id") is True
        and profile.get("has_non_empty_reality_short_id") is not True
    )
    invalid_short_id = sum(
        1 for profile in reality_profiles if profile.get("has_valid_reality_short_id") is not True
    )
    non_vision = sum(
        1 for profile in reality_profiles if profile.get("uses_xtls_vision") is not True
    )

    blockers: list[str] = []
    warnings: list[str] = []
    if not profiles:
        blockers.append("anti_dpi_subscription_missing_profiles")
    if not reality_profiles:
        blockers.append("anti_dpi_reality_profile_missing")
    if disallowed_count:
        blockers.append("anti_dpi_legacy_transports_in_subscription")
    if unexpected_ports:
        blockers.append("anti_dpi_unexpected_ports_in_subscription")
    if reality_profiles and not primary_ready:
        blockers.append("anti_dpi_primary_reality_443_missing")
    if missing_public_key:
        blockers.append("anti_dpi_reality_public_key_missing")
    if missing_fingerprint:
        blockers.append("anti_dpi_tls_fingerprint_missing")
    if unsafe_fingerprint:
        blockers.append("anti_dpi_tls_fingerprint_unsafe")
    if invalid_short_id:
        blockers.append("anti_dpi_short_id_invalid_format")
    if reality_profiles and not secondary_ready:
        warnings.append("anti_dpi_secondary_reality_port_missing")
    if len(reality_ports) < 2 and reality_profiles:
        warnings.append("anti_dpi_single_reality_port")
    if unsupported_fingerprint and not unsafe_fingerprint:
        warnings.append("anti_dpi_tls_fingerprint_unrecognized")
    if missing_server_name:
        warnings.append("anti_dpi_server_name_missing")
    if missing_short_id:
        warnings.append("anti_dpi_short_id_missing")
    if empty_short_id:
        warnings.append("anti_dpi_short_id_empty")
    if non_vision:
        warnings.append("anti_dpi_xtls_vision_not_declared")

    if blockers:
        status = "unsafe"
    elif warnings:
        status = "ready_with_warnings"
    else:
        status = "ready"

    ordered_ports = []
    for port in (ANTI_DPI_PRIMARY_PORT, *sorted(ANTI_DPI_SECONDARY_PORTS)):
        if port in reality_ports and port not in ordered_ports:
            ordered_ports.append(port)
    for port in reality_ports:
        if port not in ordered_ports:
            ordered_ports.append(port)

    return {
        "status": status,
        "ready": status in {"ready", "ready_with_warnings"},
        "primary_reality_443_ready": primary_ready,
        "secondary_reality_port_ready": secondary_ready,
        "reality_only": bool(profiles) and disallowed_count == 0,
        "legacy_transports_absent": disallowed_count == 0,
        "profile_count": len(profiles),
        "reality_profile_count": len(reality_profiles),
        "reality_ports": reality_ports,
        "recommended_port_order": ordered_ports,
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "missing_public_key_count": missing_public_key,
        "missing_tls_fingerprint_count": missing_fingerprint,
        "unsupported_tls_fingerprint_count": unsupported_fingerprint,
        "unsafe_tls_fingerprint_count": unsafe_fingerprint,
        "missing_server_name_count": missing_server_name,
        "missing_short_id_count": missing_short_id,
        "empty_short_id_count": empty_short_id,
        "invalid_short_id_count": invalid_short_id,
        "non_vision_reality_count": non_vision,
        "raw_tokens_or_uris_printed": False,
        "raw_uuid_printed": False,
        "raw_host_printed": False,
    }


def summarize_payload(raw: bytes, expected_ports: set[int]) -> dict[str, Any]:
    text = decode_subscription_body(raw)
    lines = [line for line in text.splitlines() if line.strip()]
    profiles = [profile for profile in (classify_profile(line) for line in lines) if profile]
    transport_counts = Counter(str(profile["transport"]) for profile in profiles)
    ports = sorted(
        {
            int(profile["port"])
            for profile in profiles
            if isinstance(profile.get("port"), int)
        }
    )
    unexpected_ports = [port for port in ports if port not in expected_ports]
    disallowed_count = sum(1 for profile in profiles if profile.get("transport") != "reality")
    reality_count = int(transport_counts.get("reality", 0))
    failures: list[str] = []
    if contains_error_text(text):
        failures.append("subscription_contains_error_text")
    if not profiles:
        failures.append("subscription_missing_profile")
    if disallowed_count:
        failures.append("subscription_disallowed_transport")
    if unexpected_ports:
        failures.append("subscription_unexpected_port")
    if profiles and not reality_count:
        failures.append("subscription_missing_reality_profile")
    anti_dpi = summarize_anti_dpi_quality(
        profiles=profiles,
        ports=ports,
        unexpected_ports=unexpected_ports,
        disallowed_count=disallowed_count,
    )
    failures.extend(anti_dpi["blockers"])
    return {
        "ok": not failures,
        "failures": sorted(set(failures)),
        "line_count": len(lines),
        "profile_count": len(profiles),
        "transport_counts": dict(transport_counts),
        "ports": ports,
        "expected_ports": sorted(expected_ports),
        "unexpected_ports": unexpected_ports,
        "disallowed_profile_count": disallowed_count,
        "reality_profile_count": reality_count,
        "all_profiles_reality": bool(profiles) and not disallowed_count,
        "anti_dpi": anti_dpi,
        "raw_tokens_or_uris_printed": False,
        "raw_uuid_printed": False,
        "raw_host_printed": False,
    }


def fetch_subscription(base_url: str, token: str, timeout: float) -> tuple[int, bytes]:
    url = f"{base_url.rstrip('/')}/sub/{token}"
    req = request.Request(url, headers={"User-Agent": "x0tta-live-subscription-payload-check/1.0"})
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return int(response.status), response.read(512_000)
    except error.HTTPError as exc:
        return int(exc.code), exc.read(128_000)


def check_expired_subscriptions(
    *,
    db_path: Path,
    base_url: str,
    limit: int,
    timeout: float,
    fetcher: Callable[[str, str, float], tuple[int, bytes]],
) -> dict[str, Any]:
    tokens = read_expired_subscription_tokens(db_path, limit)
    status_counts: Counter[str] = Counter()
    max_profile_count = 0
    ports_seen: set[int] = set()
    failures: list[str] = []
    checks: list[dict[str, Any]] = []

    if not tokens:
        return {
            "ok": True,
            "status": "skipped_no_expired_tokens",
            "failures": [],
            "checked_subscription_count": 0,
            "candidate_subscription_count": 0,
            "status_counts": {},
            "max_profile_count": 0,
            "ports_seen": [],
            "raw_tokens_or_uris_printed": False,
        }
    if not base_url:
        return {
            "ok": False,
            "status": "base_url_missing",
            "failures": ["expired_subscription_base_url_missing"],
            "checked_subscription_count": 0,
            "candidate_subscription_count": len(tokens),
            "status_counts": {},
            "max_profile_count": 0,
            "ports_seen": [],
            "raw_tokens_or_uris_printed": False,
        }

    for index, token in enumerate(tokens, start=1):
        item: dict[str, Any] = {"subscription_index": index}
        try:
            status, raw = fetcher(base_url, token, float(timeout))
        except Exception as exc:
            item["ok"] = False
            item["error_type"] = type(exc).__name__
            item["failures"] = ["expired_subscription_fetch_error"]
            checks.append(item)
            failures.append("expired_subscription_fetch_error")
            continue
        text = decode_subscription_body(raw)
        profiles = [profile for profile in (classify_profile(line) for line in text.splitlines()) if profile]
        ports = sorted(
            {
                int(profile["port"])
                for profile in profiles
                if isinstance(profile.get("port"), int)
            }
        )
        status_counts[str(status)] += 1
        max_profile_count = max(max_profile_count, len(profiles))
        ports_seen.update(ports)
        item.update(
            {
                "http_status": status,
                "profile_count": len(profiles),
                "ports": ports,
                "ok": status >= 400 and not profiles,
                "failures": [],
            }
        )
        if status < 400:
            item["failures"].append("expired_subscription_http_not_error")
            failures.append("expired_subscription_http_not_error")
        if profiles:
            item["failures"].append("expired_subscription_returned_vpn_profile")
            failures.append("expired_subscription_returned_vpn_profile")
        checks.append(item)

    unique_failures = sorted(set(failures))
    return {
        "ok": not unique_failures,
        "status": "safe" if not unique_failures else "unsafe",
        "failures": unique_failures,
        "checked_subscription_count": len(checks),
        "candidate_subscription_count": len(tokens),
        "status_counts": dict(status_counts),
        "max_profile_count": max_profile_count,
        "ports_seen": sorted(ports_seen),
        "checks": checks,
        "raw_tokens_or_uris_printed": False,
    }


def run_check(
    args: argparse.Namespace,
    fetcher: Callable[[str, str, float], tuple[int, bytes]] = fetch_subscription,
) -> dict[str, Any]:
    expected_ports = set(args.expected_ports or DEFAULT_EXPECTED_PORTS)
    base_url = resolve_subscription_base_url(args)
    tokens = read_subscription_tokens(
        args.db_path,
        args.limit,
        include_expired=bool(args.include_expired),
    )
    checks: list[dict[str, Any]] = []
    aggregate_counts: Counter[str] = Counter()
    aggregate_ports: set[int] = set()
    failures: list[str] = []
    anti_dpi_status_counts: Counter[str] = Counter()
    anti_dpi_warning_counts: Counter[str] = Counter()
    anti_dpi_blocker_counts: Counter[str] = Counter()
    anti_dpi_primary_ready_count = 0
    anti_dpi_secondary_ready_count = 0
    anti_dpi_ready_count = 0

    if not base_url:
        failures.append("subscription_base_url_missing")
    if not tokens:
        failures.append("subscription_token_missing")

    if base_url and tokens:
        for index, token in enumerate(tokens, start=1):
            item: dict[str, Any] = {"subscription_index": index}
            try:
                status, raw = fetcher(base_url, token, float(args.timeout))
                item["http_status"] = status
            except Exception as exc:
                item["ok"] = False
                item["failures"] = ["subscription_fetch_error"]
                item["error_type"] = type(exc).__name__
                checks.append(item)
                failures.append("subscription_fetch_error")
                continue
            if status >= 400:
                item["ok"] = False
                item["failures"] = ["subscription_http_failed"]
                checks.append(item)
                failures.append("subscription_http_failed")
                continue
            summary = summarize_payload(raw, expected_ports)
            aggregate_counts.update(summary["transport_counts"])
            aggregate_ports.update(summary["ports"])
            anti_dpi = summary.get("anti_dpi") if isinstance(summary.get("anti_dpi"), dict) else {}
            anti_dpi_status_counts[str(anti_dpi.get("status") or "unknown")] += 1
            anti_dpi_warning_counts.update(
                str(item) for item in (anti_dpi.get("warnings") or []) if isinstance(item, str)
            )
            anti_dpi_blocker_counts.update(
                str(item) for item in (anti_dpi.get("blockers") or []) if isinstance(item, str)
            )
            if anti_dpi.get("ready") is True:
                anti_dpi_ready_count += 1
            if anti_dpi.get("primary_reality_443_ready") is True:
                anti_dpi_primary_ready_count += 1
            if anti_dpi.get("secondary_reality_port_ready") is True:
                anti_dpi_secondary_ready_count += 1
            item.update(summary)
            checks.append(item)
            failures.extend(summary["failures"])

    expired_error_check = check_expired_subscriptions(
        db_path=args.db_path,
        base_url=base_url,
        limit=max(0, int(args.expired_limit)),
        timeout=float(args.timeout),
        fetcher=fetcher,
    )
    if not expired_error_check["ok"]:
        failures.extend(
            f"expired:{failure}"
            for failure in expired_error_check.get("failures", [])
            if isinstance(failure, str)
        )

    unique_failures = sorted(set(failures))
    checked_count = len(checks)
    anti_dpi_blockers = sorted(anti_dpi_blocker_counts)
    if checked_count and anti_dpi_ready_count < checked_count:
        anti_dpi_blockers.append("anti_dpi_not_ready_for_all_checked_subscriptions")
    anti_dpi_blockers = sorted(set(anti_dpi_blockers))
    anti_dpi_status = "missing"
    if checked_count:
        if anti_dpi_blockers:
            anti_dpi_status = "unsafe"
        elif anti_dpi_warning_counts:
            anti_dpi_status = "ready_with_warnings"
        else:
            anti_dpi_status = "ready"
    anti_dpi_warnings = sorted(anti_dpi_warning_counts)
    anti_dpi_legacy_transports_absent = not any(
        key != "reality" and int(value) > 0 for key, value in aggregate_counts.items()
    )
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "ok": not unique_failures,
        "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE" if not unique_failures else "LIVE_SUBSCRIPTION_PAYLOAD_UNSAFE",
        "failures": unique_failures,
        "checked_subscription_count": len(checks),
        "candidate_subscription_count": len(tokens),
        "include_expired": bool(args.include_expired),
        "expected_ports": sorted(expected_ports),
        "transport_counts": dict(aggregate_counts),
        "ports": sorted(aggregate_ports),
        "anti_dpi": {
            "status": anti_dpi_status,
            "ready": anti_dpi_status in {"ready", "ready_with_warnings"},
            "reality_only": bool(checked_count) and anti_dpi_legacy_transports_absent,
            "legacy_transports_absent": anti_dpi_legacy_transports_absent,
            "checked_subscription_count": checked_count,
            "ready_subscription_count": anti_dpi_ready_count,
            "primary_reality_443_ready_count": anti_dpi_primary_ready_count,
            "secondary_reality_port_ready_count": anti_dpi_secondary_ready_count,
            "all_checked_have_primary_reality_443": bool(checked_count)
            and anti_dpi_primary_ready_count == checked_count,
            "all_checked_have_secondary_reality_port": bool(checked_count)
            and anti_dpi_secondary_ready_count == checked_count,
            "status_counts": dict(anti_dpi_status_counts),
            "warning_counts": dict(anti_dpi_warning_counts),
            "blocker_counts": dict(anti_dpi_blocker_counts),
            "blockers": anti_dpi_blockers,
            "warnings": anti_dpi_warnings,
            "recommended_port_order": [
                port for port in (ANTI_DPI_PRIMARY_PORT, *sorted(ANTI_DPI_SECONDARY_PORTS)) if port in aggregate_ports
            ],
            "raw_tokens_or_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_host_printed": False,
        },
        "checks": checks,
        "expired_error_check": expired_error_check,
        "privacy": {
            "raw_tokens_printed": False,
            "raw_profile_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_host_printed": False,
        },
    }


def print_human(report: dict[str, Any]) -> None:
    print(f"decision: {report['decision']}")
    print(f"ok: {report['ok']}")
    print(f"checked_subscription_count: {report['checked_subscription_count']}")
    print(f"transport_counts: {json.dumps(report['transport_counts'], sort_keys=True)}")
    print(f"ports: {report['ports']}")
    anti_dpi = report.get("anti_dpi") or {}
    print(
        "anti_dpi: "
        f"status={anti_dpi.get('status')} "
        f"ready={anti_dpi.get('ready')} "
        f"primary443={anti_dpi.get('primary_reality_443_ready_count')}/"
        f"{anti_dpi.get('checked_subscription_count')} "
        f"secondary={anti_dpi.get('secondary_reality_port_ready_count')}/"
        f"{anti_dpi.get('checked_subscription_count')}"
    )
    expired = report.get("expired_error_check") or {}
    print(
        "expired_error_check: "
        f"ok={expired.get('ok')} checked={expired.get('checked_subscription_count')} "
        f"max_profile_count={expired.get('max_profile_count')} ports_seen={expired.get('ports_seen')}"
    )
    if report["failures"]:
        print(f"failures: {', '.join(report['failures'])}")


def main() -> int:
    args = parse_args()
    report = run_check(args)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        tmp = args.json_out.with_suffix(args.json_out.suffix + ".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(args.json_out)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print_human(report)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
