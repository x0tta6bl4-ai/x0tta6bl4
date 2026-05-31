#!/usr/bin/env python3
"""Diagnose and repair Ghost Access subscription 404s.

The `/sub/{token}` handler returns HTTP 404 only when the token is absent from
both `users.subscription_token` and `offline_subscriptions.subscription_token`.
This tool is intentionally local-only: run it on the host with the bot SQLite
database so subscription tokens do not need to be copied into chat or tickets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


DEFAULT_DB_PATH = Path(
    os.getenv("GHOST_ACCESS_DB_PATH", "/opt/ghost-access-bot/shared/x0tta6bl4.db")
)
DEFAULT_BASE_URL_ENV_KEYS = ("SUBSCRIPTION_BASE_URL", "WEB_SUBSCRIPTION_BASE_URL")
OFFLINE_TOKEN_INDEX = "idx_offline_subscriptions_token"


class DiagnosticError(RuntimeError):
    """Expected operator-facing failure."""


@dataclass(frozen=True)
class MatchSelector:
    column: str
    value: str
    mode: str = "exact"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose Ghost Access HTTP 404 on subscription refresh and optionally "
            "repair an offline subscription token."
        )
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite DB path, default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--subscription-url",
        help="Full subscription URL from the VPN client, for example https://host/sub/TOKEN",
    )
    parser.add_argument("--token", help="Raw token from /sub/{token}; prefer local use only")
    parser.add_argument("--claim-code", help="Offline claim code, for example OFFLINE-ABC123")
    parser.add_argument("--vpn-uuid", help="Offline VPN UUID stored in offline_subscriptions")
    parser.add_argument("--xray-email", help="Offline Xray email stored in offline_subscriptions")
    parser.add_argument(
        "--label-like",
        help="Case-insensitive label fragment, for example the suffix visible in the VPN app",
    )
    parser.add_argument(
        "--base-url",
        help="Base URL used to print repaired subscription URLs; defaults to SUBSCRIPTION_BASE_URL",
    )
    parser.add_argument(
        "--repair-offline-token",
        action="store_true",
        help="Generate or return a working offline subscription URL for exactly one matched row",
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="With --repair-offline-token, replace an existing offline subscription token",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON. Plain text is used by default.",
    )
    return parser.parse_args(argv)


def extract_token(raw_token: str | None, subscription_url: str | None) -> str:
    if raw_token:
        return raw_token.strip()
    if not subscription_url:
        return ""

    parsed = urlparse(subscription_url.strip())
    if not parsed.scheme and not parsed.netloc:
        candidate = subscription_url.strip()
        if "/sub/" in candidate:
            return candidate.rsplit("/sub/", 1)[1].split("?", 1)[0].strip("/")
        return candidate.strip()

    path = parsed.path.strip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) >= 2 and parts[-2] == "sub":
        return parts[-1].strip()
    return ""


def token_summary(token: str) -> dict[str, Any]:
    if not token:
        return {"present": False}
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return {
        "present": True,
        "length": len(token),
        "prefix": token[:6],
        "sha256_12": digest[:12],
    }


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({quote_ident(table)})")}


def quote_ident(identifier: str) -> str:
    if not identifier.replace("_", "").isalnum():
        raise ValueError(f"unsafe SQL identifier: {identifier}")
    return f'"{identifier}"'


def select_row_by_token(
    conn: sqlite3.Connection,
    table: str,
    token: str,
    preferred_columns: list[str],
) -> dict[str, Any] | None:
    columns = table_columns(conn, table)
    if "subscription_token" not in columns:
        return None

    selected = [column for column in preferred_columns if column in columns]
    if "subscription_token" not in selected:
        selected.append("subscription_token")
    select_clause = ", ".join(quote_ident(column) for column in selected)
    row = conn.execute(
        f"""
        SELECT {select_clause}
        FROM {quote_ident(table)}
        WHERE subscription_token = ?
        LIMIT 1
        """,
        (token,),
    ).fetchone()
    return dict(row) if row else None


def normalize_claim_code(value: str) -> str:
    raw = value.strip().upper()
    if raw and not raw.startswith("OFFLINE-"):
        return f"OFFLINE-{raw}"
    return raw


def build_selectors(args: argparse.Namespace) -> list[MatchSelector]:
    selectors: list[MatchSelector] = []
    if args.claim_code:
        selectors.append(MatchSelector("claim_code", normalize_claim_code(args.claim_code)))
    if args.vpn_uuid:
        selectors.append(MatchSelector("vpn_uuid", args.vpn_uuid.strip()))
    if args.xray_email:
        selectors.append(MatchSelector("xray_email", args.xray_email.strip()))
    if args.label_like:
        selectors.append(MatchSelector("label", args.label_like.strip(), mode="like"))
    return [selector for selector in selectors if selector.value]


def find_offline_rows_by_selectors(
    conn: sqlite3.Connection,
    selectors: list[MatchSelector],
) -> list[dict[str, Any]]:
    if not selectors:
        return []

    columns = table_columns(conn, "offline_subscriptions")
    if not columns:
        return []

    allowed_columns = {
        "claim_code",
        "subscription_token",
        "vpn_uuid",
        "xray_email",
        "plan",
        "days",
        "expires_at",
        "label",
        "delivery_profile",
        "entry_node",
        "issued_at",
        "claimed_at",
        "claimed_by_tg_id",
    }
    selected = [column for column in allowed_columns if column in columns]
    if not selected:
        return []

    clauses: list[str] = []
    params: list[str] = []
    for selector in selectors:
        if selector.column not in columns:
            continue
        quoted = quote_ident(selector.column)
        if selector.mode == "like":
            clauses.append(f"LOWER({quoted}) LIKE LOWER(?)")
            params.append(f"%{selector.value}%")
        else:
            clauses.append(f"{quoted} = ?")
            params.append(selector.value)

    if not clauses:
        return []

    select_clause = ", ".join(quote_ident(column) for column in selected)
    where_clause = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT {select_clause}
        FROM offline_subscriptions
        WHERE {where_clause}
        ORDER BY expires_at DESC, claim_code ASC
        LIMIT 25
        """,
        tuple(params),
    ).fetchall()
    return [dict(row) for row in rows]


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
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def expiry_state(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"expires_at": None, "expired": None}
    expires_at = parse_datetime(row.get("expires_at"))
    if not expires_at:
        return {"expires_at": row.get("expires_at"), "expired": None}
    return {
        "expires_at": expires_at.isoformat(),
        "expired": datetime.now() > expires_at,
    }


def public_record(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    public = dict(row)
    token = str(public.pop("subscription_token", "") or "")
    public["subscription_token"] = token_summary(token)
    return public


def base_url_from_args(args: argparse.Namespace) -> str:
    if args.base_url:
        return args.base_url.strip().rstrip("/")
    for key in DEFAULT_BASE_URL_ENV_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value.rstrip("/")
    return ""


def make_subscription_url(base_url: str, token: str) -> str | None:
    if not base_url or not token:
        return None
    return f"{base_url.rstrip('/')}/sub/{token}"


def ensure_offline_token_schema(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "offline_subscriptions"):
        raise DiagnosticError("offline_subscriptions table is missing")
    columns = table_columns(conn, "offline_subscriptions")
    if "subscription_token" not in columns:
        conn.execute("ALTER TABLE offline_subscriptions ADD COLUMN subscription_token TEXT")
    conn.execute(
        f"""
        CREATE UNIQUE INDEX IF NOT EXISTS {quote_ident(OFFLINE_TOKEN_INDEX)}
        ON offline_subscriptions(subscription_token)
        WHERE subscription_token IS NOT NULL
        """
    )


def generate_unique_token(conn: sqlite3.Connection) -> str:
    for _ in range(32):
        token = secrets.token_urlsafe(24)
        row = conn.execute(
            """
            SELECT 1
            FROM offline_subscriptions
            WHERE subscription_token = ?
            LIMIT 1
            """,
            (token,),
        ).fetchone()
        if row is None:
            return token
    raise DiagnosticError("failed to generate a unique subscription token")


def repair_offline_token(
    conn: sqlite3.Connection,
    args: argparse.Namespace,
    selectors: list[MatchSelector],
) -> dict[str, Any]:
    if not selectors:
        raise DiagnosticError(
            "--repair-offline-token requires one selector: --claim-code, --vpn-uuid, --xray-email, or --label-like"
        )

    ensure_offline_token_schema(conn)
    rows = find_offline_rows_by_selectors(conn, selectors)
    if not rows:
        raise DiagnosticError("no offline subscription matched the repair selector")
    if len(rows) > 1:
        return {
            "status": "ambiguous_offline_match",
            "matched_rows": [public_record(row) for row in rows],
            "expected_http_status": None,
            "action": "narrow the selector before repairing",
        }

    row = rows[0]
    previous_token = str(row.get("subscription_token") or "").strip()
    token = previous_token
    rotated = False
    if args.rotate or not token:
        token = generate_unique_token(conn)
        conn.execute(
            """
            UPDATE offline_subscriptions
            SET subscription_token = ?
            WHERE claim_code = ?
            """,
            (token, row["claim_code"]),
        )
        conn.commit()
        row["subscription_token"] = token
        rotated = True

    base_url = base_url_from_args(args)
    return {
        "status": "repaired_offline" if rotated else "existing_offline_token",
        "record_kind": "offline",
        "matched_row": public_record(row),
        "expected_http_status": 200,
        "rotated": rotated,
        "subscription_url": make_subscription_url(base_url, token),
        "base_url_configured": bool(base_url),
        "note": (
            "Re-import subscription_url in the VPN app."
            if base_url
            else "Set SUBSCRIPTION_BASE_URL or pass --base-url to print the full URL."
        ),
    }


def diagnose(args: argparse.Namespace) -> dict[str, Any]:
    token = extract_token(args.token, args.subscription_url)
    selectors = build_selectors(args)

    if not args.db_path.exists():
        return {
            "status": "db_not_found",
            "db_path": str(args.db_path),
            "token": token_summary(token),
            "expected_http_status": None,
        }

    readonly = not args.repair_offline_token
    uri = f"file:{args.db_path}?mode=ro" if readonly else str(args.db_path)
    with sqlite3.connect(uri, uri=readonly) as conn:
        conn.row_factory = sqlite3.Row
        if args.repair_offline_token:
            return repair_offline_token(conn, args, selectors)

        report: dict[str, Any] = {
            "status": "not_found",
            "db_path": str(args.db_path),
            "token": token_summary(token),
            "expected_http_status": 404 if token else None,
            "tables": {
                "users": sorted(table_columns(conn, "users")),
                "offline_subscriptions": sorted(table_columns(conn, "offline_subscriptions")),
            },
        }

        if token:
            user = select_row_by_token(
                conn,
                "users",
                token,
                ["user_id", "username", "plan", "expires_at", "subscription_updated_at", "vpn_uuid"],
            )
            if user:
                state = expiry_state(user)
                return {
                    **report,
                    "status": "found_user_expired" if state["expired"] else "found_user",
                    "record_kind": "user",
                    "matched_row": public_record(user),
                    "expiry": state,
                    "expected_http_status": 200,
                }

            offline = select_row_by_token(
                conn,
                "offline_subscriptions",
                token,
                [
                    "claim_code",
                    "vpn_uuid",
                    "xray_email",
                    "plan",
                    "days",
                    "expires_at",
                    "label",
                    "delivery_profile",
                    "entry_node",
                    "claimed_at",
                    "claimed_by_tg_id",
                ],
            )
            if offline:
                state = expiry_state(offline)
                return {
                    **report,
                    "status": "found_offline_expired" if state["expired"] else "found_offline",
                    "record_kind": "offline",
                    "matched_row": public_record(offline),
                    "expiry": state,
                    "expected_http_status": 200,
                }

        selector_rows = find_offline_rows_by_selectors(conn, selectors)
        if selector_rows:
            report["status"] = "offline_selector_match"
            report["matched_rows"] = [public_record(row) for row in selector_rows]
            report["expected_http_status"] = 404 if token else None
            report["action"] = (
                "Run again with --repair-offline-token and a precise selector to print or rotate the URL."
            )
        return report


def print_plain(report: dict[str, Any]) -> None:
    status = report.get("status")
    print(f"status: {status}")
    if report.get("db_path"):
        print(f"db_path: {report['db_path']}")
    if report.get("expected_http_status") is not None:
        print(f"expected_http_status: {report['expected_http_status']}")

    token = report.get("token")
    if isinstance(token, dict) and token.get("present"):
        print(
            "token: "
            f"prefix={token.get('prefix')}... len={token.get('length')} sha256_12={token.get('sha256_12')}"
        )

    matched = report.get("matched_row")
    if isinstance(matched, dict):
        claim_code = matched.get("claim_code") or matched.get("user_id")
        label = matched.get("label") or matched.get("username")
        expires_at = matched.get("expires_at")
        print(f"matched: {claim_code} label={label} expires_at={expires_at}")

    matched_rows = report.get("matched_rows")
    if isinstance(matched_rows, list):
        print(f"matched_rows: {len(matched_rows)}")
        for row in matched_rows[:10]:
            print(
                "  - "
                f"{row.get('claim_code')} label={row.get('label')} expires_at={row.get('expires_at')} "
                f"token={row.get('subscription_token')}"
            )

    if report.get("subscription_url"):
        print(f"subscription_url: {report['subscription_url']}")
    if report.get("note"):
        print(f"note: {report['note']}")
    if report.get("action"):
        print(f"action: {report['action']}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = diagnose(args)
    except DiagnosticError as exc:
        report = {"status": "error", "error": str(exc), "expected_http_status": None}
    except sqlite3.Error as exc:
        report = {"status": "sqlite_error", "error": str(exc), "expected_http_status": None}

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_plain(report)

    return 0 if report.get("status") not in {"error", "sqlite_error", "db_not_found"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
