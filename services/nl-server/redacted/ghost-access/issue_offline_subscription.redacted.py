# REDACTED REVIEW COPY - NOT DEPLOYABLE
# source: /opt/ghost-access-bot/current/scripts/issue_offline_subscription.py
# raw content was read into memory only and not stored locally

#!/usr/bin/env python3
"""Issue a Ghost Access subscription for a user without Telegram.

Creates an offline_subscriptions row, registers an xray client with a
placeholder tg_id=0, and prints a ready-to-use subscription URL plus a claim code.

The user can start using the subscription immediately in any client. Later, if
they install Telegram and want to bind the subscription to their account, they
send the bot:

    /start OFFLINE-XXXXXX

Usage:
    python3 scripts/issue_offline_subscription.py --plan trial
    python3 scripts/issue_offline_subscription.py --plan basic_1m
    python3 scripts/issue_offline_subscription.py --plan basic_3m --days 90 --label "Friend"
    python3 scripts/issue_offline_subscription.py --plan trial --spb --label "SPB tester"
    python3 scripts/issue_offline_subscription.py --plan base
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

BOT_ROOT = Path(os.environ.get("GHOST_ACCESS_BOT_ROOT", "/opt/ghost-access-bot/current"))
_shared_db = Path("/opt/ghost-access-bot/shared/x0tta6bl4.db")
_local_db = BOT_ROOT / "x0tta6bl4.db"
DEFAULT_DB_PATH = (
    os.environ.get("GHOST_ACCESS_DB_PATH", "").strip()
    or (str(_shared_db) if _shared_db.exists() else "")
    or (str(_local_db) if _local_db.exists() else "")
    or str(_shared_db)
)
SHARED_DB = Path(DEFAULT_DB_PATH)

_DEFAULT_XRAY_MGR = BOT_ROOT / "scripts" / "xui_client_manager.py"
XRAY_CLIENT_MANAGER = os.environ.get("XRAY_CLIENT_MANAGER") or (
    str(_DEFAULT_XRAY_MGR)
    if _DEFAULT_XRAY_MGR.exists()
    else "/mnt/projects/scripts/xui_client_manager.py"
)

VPN_SERVER = os.environ.get("VPN_SERVER", "89.125.1.107")
PROFILE_VPN_SERVER = os.environ.get("PROFILE_VPN_SERVER", "195.58.48.193")
VPN_PORT = int(os.environ.get("VPN_PORT", "443"))
SECONDARY_VPN_PORT = int(os.environ.get("SECONDARY_VPN_PORT", "2083"))
ENABLE_SECONDARY = os.environ.get("ENABLE_SECONDARY_REALITY_FALLBACK", "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ENABLE_XHTTP = os.environ.get("ENABLE_XHTTP_FALLBACK", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EXPOSE_FALLBACK_TRANSPORTS = os.environ.get("EXPOSE_FALLBACK_TRANSPORTS", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
SPB_REALITY_SERVER_NAME = os.environ.get("SPB_REALITY_SERVER_NAME", "www.cloudflare.com").strip()
SPB_REALITY_FINGERPRINT = os.environ.get("SPB_REALITY_FINGERPRINT", "chrome").strip()
SPB_REALITY_PUBLIC_KEY = os.environ.get(
    "SPB_REALITY_PUBLIC_KEY",
    "AZmSghVAZbdZOWxxEw2cmOXRucFKDn6Bf45YrNZ6bx8",
).strip()
SPB_REALITY_SHORT_ID = os.environ.get("SPB_REALITY_SHORT_ID", "a1b2c3d4").strip()
DELIVERY_PROFILE_ANDROID_STEALTH_SPB = "android_stealth_spb"
ENTRY_NODE_SPB = "spb"
ENTRY_NODE_NL = "nl"

PLANS = {
    "trial": {"days": int(os.environ.get("TRIAL_DAYS", "7")), "amount": 0},
    "basic_1m": {"days": 30, "amount": 149},
    "basic_3m": {"days": 90, "amount": 399},
    "basic_6m": {"days": 180, "amount": 699},
    "basic_12m": {"days": 365, "amount": 1099},
}

PLAN_ALIASES = {
    "base": "basic_1m",
    "pro": "basic_3m",
    "plus": "basic_6m",
    "year": "basic_12m",
}

OFFLINE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS offline_subscriptions (
    claim_code        TEXT PRIMARY KEY,
    subscription_token TEXT UNIQUE,
    vpn_uuid          TEXT NOT NULL UNIQUE,
    xray_email        TEXT NOT NULL,
    plan              TEXT NOT NULL,
    days              INTEGER NOT NULL,
    expires_at        TIMESTAMP NOT NULL,
    label             TEXT,
    delivery_profile  TEXT,
    entry_node        TEXT,
    issued_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    claimed_at        TIMESTAMP,
    claimed_by_tg_id  INTEGER
)
"""

_CLAIM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_claim_code() -> str:
    suffix = "".join(secrets.choice(_CLAIM_ALPHABET) for _ in range(6))
    return f"OFFLINE-{suffix}"


def generate_subscription_token() -> str:
    return secrets.token_urlsafe(24)


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(OFFLINE_TABLE_DDL)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(offline_subscriptions)").fetchall()}
    if "subscription_token" not in columns:
        conn.execute("ALTER TABLE offline_subscriptions ADD COLUMN subscription_token TEXT")
    if "delivery_profile" not in columns:
        conn.execute("ALTER TABLE offline_subscriptions ADD COLUMN delivery_profile TEXT")
    if "entry_node" not in columns:
        conn.execute("ALTER TABLE offline_subscriptions ADD COLUMN entry_node TEXT")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_offline_subscriptions_token
        ON offline_subscriptions(subscription_token)
        WHERE subscription_token IS NOT NULL
        """
    )
    conn.commit()


def run_xray(*args: str) -> str:
    result = subprocess.run(
        ["python3", XRAY_CLIENT_MANAGER, *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def show_profile(port: int) -> dict:
    if PROFILE_VPN_SERVER != VPN_SERVER and port == VPN_PORT:
        return {
            "flow": "xtls-rprx-vision",
            "type": "tcp",
            "server_name": SPB_REALITY_SERVER_NAME,
            "fingerprint": SPB_REALITY_FINGERPRINT,
            "public_key": SPB_REALITY_PUBLIC_KEY,
            "short_id": SPB_REALITY_SHORT_ID,
        }
    return json.loads(run_xray("show-profile", "--port", str(port)))


def build_vless_link(uuid_: str, port: int, profile: dict, label: str) -> str:
    fragment = quote(label, safe="")
    return (
        f"<REDACTED_VPN_URI>"
        "?security=reality"
        "&encryption=none"
        f"&flow={profile['flow']}"
        f"&type={profile['type']}"
        f"&sni={profile['server_name']}"
        f"&fp={profile['fingerprint']}"
        f"&pbk={profile['public_key']}"
        f"&sid={profile['short_id']}"
        f"#{fragment}"
    )


def build_xhttp_link(uuid_: str, profile: dict, label: str) -> str:
    fragment = quote(label, safe="")
    path = profile.get("path", "/xhttp")
    return (
        f"<REDACTED_VPN_URI>"
        "?security=tls"
        "&encryption=none"
        f"&type={profile['type']}"
        f"&path={path}"
        "&allowInsecure=1"
        f"#{fragment}"
    )


def subscription_base_url() -> str:
    configured = (os.environ.get("SUBSCRIPTION_BASE_URL") or "").strip()
    if configured:
        return configured
    sub_port = int(os.environ.get("SUBSCRIPTION_HTTP_PORT", "8880"))
    return f"http://{VPN_SERVER}:{sub_port}"


def web_access_base_url() -> str:
    configured = (os.environ.get("WEB_ACCESS_BASE_URL") or "").strip()
    if configured:
        return configured.rstrip("/")
    return subscription_base_url()


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument(
        "--plan",
        default="basic_1m",
        choices=sorted(set(PLANS) | set(PLAN_ALIASES)),
    )
    ap.add_argument(
        "--days",
        type=int,
        default=None,
        help="override plan days (default = plan's own duration)",
    )
    ap.add_argument(
        "--label",
        default=None,
        help="human note saved in DB and used as VLESS fragment suffix",
    )
    ap.add_argument(
        "--delivery-profile",
        default=os.environ.get("OFFLINE_DELIVERY_PROFILE", "").strip(),
        help="optional bot delivery profile stored with the offline subscription",
    )
    ap.add_argument(
        "--entry-node",
        choices=("", ENTRY_NODE_NL, ENTRY_NODE_SPB),
        default=os.environ.get("OFFLINE_ENTRY_NODE", "").strip(),
        help="optional entry node stored with the offline subscription",
    )
    ap.add_argument(
        "--spb",
        action="store_true",
        help="mark this offline subscription as an SPB profile for bot /sub rendering",
    )
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    plan_key = PLAN_ALIASES.get(args.plan, args.plan)

    if not SHARED_DB.exists():
        print(f"ERROR: bot DB not found at {SHARED_DB}", file=sys.stderr)
        return 2
    if not Path(XRAY_CLIENT_MANAGER).exists():
        print(f"ERROR: xray client manager not found at {XRAY_CLIENT_MANAGER}", file=sys.stderr)
        return 2

    days = args.days or PLANS[plan_key]["days"]
    claim_code = generate_claim_code()
    subscription_token = generate_subscription_token()
    vpn_uuid = str(uuid.uuid4())
    email = f"offline-{claim_code.lower()}@x0tta6bl4"
    expires_at = datetime.now() + timedelta(days=days)
    label_suffix = claim_code.split("-", 1)[1]
    fragment_label = args.label or f"x0tta6bl4-Offline-{label_suffix}"
    delivery_profile = (args.delivery_profile or "").strip() or None
    entry_node = (args.entry_node or "").strip() or None
    if args.spb:
        delivery_profile = DELIVERY_PROFILE_ANDROID_STEALTH_SPB
        entry_node = ENTRY_NODE_SPB

    conn = sqlite3.connect(str(SHARED_DB))
    conn.row_factory = sqlite3.Row
    try:
        ensure_table(conn)
        conn.execute(
            "INSERT INTO offline_subscriptions "
            "(claim_code, subscription_token, vpn_uuid, xray_email, plan, days, expires_at, "
            "label, delivery_profile, entry_node) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                claim_code,
                subscription_token,
                vpn_uuid,
                email,
                plan_key,
                days,
                expires_at.isoformat(),
                args.label,
                delivery_profile,
                entry_node,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    run_xray(
        "ensure-client",
        "--port",
        str(VPN_PORT),
        "--uuid",
        vpn_uuid,
        "--email",
        email,
        "--flow",
        "xtls-rprx-vision",
        "--tg-id",
        "0",
    )
    if EXPOSE_FALLBACK_TRANSPORTS and ENABLE_SECONDARY:
        run_xray(
            "ensure-client",
            "--port",
            str(SECONDARY_VPN_PORT),
            "--uuid",
            vpn_uuid,
            "--email",
            email,
            "--flow",
            "xtls-rprx-vision",
            "--tg-id",
            "0",
        )

    main_link = build_vless_link(vpn_uuid, VPN_PORT, show_profile(VPN_PORT), fragment_label)
    subscription_url = f"{subscription_base_url()}/sub/{subscription_token}"
    access_url = f"{web_access_base_url()}/access/{subscription_token}"
    alt_link = ""
    if EXPOSE_FALLBACK_TRANSPORTS and ENABLE_SECONDARY:
        alt_link = build_vless_link(
            vpn_uuid,
            SECONDARY_VPN_PORT,
            show_profile(SECONDARY_VPN_PORT),
            f"{fragment_label}-Alt",
        )
    xhttp_link = ""
    if EXPOSE_FALLBACK_TRANSPORTS and ENABLE_XHTTP:
        xhttp_link = build_xhttp_link(
            vpn_uuid,
            show_profile(8443),
            f"{fragment_label}-XHTTP",
        )

    print("=" * 56)
    print("  OFFLINE SUBSCRIPTION ISSUED")
    print("=" * 56)
    print(f"Claim code   : {claim_code}")
    print(f"Plan         : {plan_key} ({days} days)")
    print(f"Expires at   : {expires_at.strftime('%Y-%m-%d %H:%M')}")
    if args.label:
        print(f"Label        : {args.label}")
    print(f"Access page  : {access_url}")
    print(f"Subscription : {subscription_url}")
    print(f"Xray email   : {email}")
    print(f"UUID         : {vpn_uuid}")
    print()
    print(f"MAIN DIRECT (port {VPN_PORT}):")
    print(main_link)
    if alt_link:
        print()
        print(f"OPERATOR RESERVE (port {SECONDARY_VPN_PORT}):")
        print(alt_link)
    if xhttp_link:
        print()
        print("OPERATOR XHTTP (port 8443):")
        print(xhttp_link)
    print()
    print("Передай клиенту Access page или Subscription URL. Резервы держи только для операторской диагностики.")
    print("Если клиент позже захочет привязать Telegram, попроси написать боту:")
    print(f"    /start {claim_code}")
    print("=" * 56)
    return 0


if __name__ == "__main__":
    sys.exit(main())
