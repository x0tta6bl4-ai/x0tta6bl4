#!/usr/bin/env python3
"""
Manage VLESS clients via x-ui SQLite database directly.

Replaces xray_vless_client_manager.py which edited config.json
(x-ui overwrites config.json on xray restart, losing changes).

Usage:
  python3 xui_client_manager.py ensure-client --uuid UUID --email EMAIL [--inbound-id 2]
  python3 xui_client_manager.py remove-client --uuid UUID [--email EMAIL] [--inbound-id 2]
  python3 xui_client_manager.py show-profile [--inbound-id 2]
  python3 xui_client_manager.py list-clients [--inbound-id 2]
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sqlite3
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, Optional, Callable


# ============================================================================
# TYPE DEFINITIONS
# ============================================================================

class VLESSClient(TypedDict, total=False):
    """VLESS client record structure."""
    id: str  # UUID
    email: str
    flow: str  # e.g., "xtls-rprx-vision"
    level: int
    tgId: int
    limitIp: int
    totalGB: int
    expiryTime: int
    enable: bool


class RealitySettings(TypedDict, total=False):
    """Reality protocol settings."""
    dest: str
    xver: int
    serverNames: list[str]
    privateKey: str
    minClient: str
    maxClient: str
    maxTimediff: int
    shortIds: list[str]


class InboundRecord(TypedDict, total=False):
    """x-ui inbound record structure."""
    id: int
    port: int
    protocol: str
    settings: str  # JSON string
    stream_settings: str  # JSON string
    tag: str
    sniffing: str
    remark: str


@dataclass(frozen=True)
class PortConfig:
    """Configuration for a specific port."""
    port: int
    preferred_sni: list[str]
    preferred_short_ids: list[str]
    fallback_order: int = 0


# ============================================================================
# CONSTANTS
# ============================================================================

DEFAULT_DB = Path("/etc/x-ui/x-ui.db")
DEFAULT_INBOUND_ID = 2  # VLESS-VK-443

PORT_PREFERRED_SERVER_NAMES = {
    443: lambda: [
        os.environ.get("REALITY_SNI", "eh.vk.com"),
        "eh.vk.com",
        "login.vk.com",
        "api.vk.com",
        "vk.com",
    ],
    2083: lambda: [
        os.environ.get("SECONDARY_REALITY_SNI", ""),
        "docs.docker.com",
        "hub.docker.com",
        "www.docker.com",
        "docs.oracle.com",
        "www.oracle.com",
    ],
    39829: lambda: [
        os.environ.get("LEGACY_REALITY_SNI", "google.com"),
        "google.com",
        "www.google.com",
        "dl.google.com",
    ],
}

PORT_PREFERRED_SHORT_IDS = {
    443: lambda: [os.environ.get("REALITY_SHORT_ID", "b2c4"), "b2c4"],
    2083: lambda: [os.environ.get("SECONDARY_REALITY_SHORT_ID", "")],
    39829: lambda: [os.environ.get("LEGACY_REALITY_SHORT_ID", "18e154a0558d9263")],
}


def get_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def resolve_inbound_id(
    conn: sqlite3.Connection,
    inbound_id: int | None = None,
    port: int | None = None,
) -> int:
    if inbound_id is not None:
        return inbound_id
    if port is None:
        return DEFAULT_INBOUND_ID
    row = conn.execute(
        "SELECT id FROM inbounds WHERE port = ? ORDER BY id ASC LIMIT 1",
        (port,),
    ).fetchone()
    if not row:
        raise RuntimeError(f"Inbound with port {port} not found")
    return int(row["id"])


def get_inbound(conn: sqlite3.Connection, inbound_id: int) -> dict:
    row = conn.execute("SELECT * FROM inbounds WHERE id = ?", (inbound_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Inbound {inbound_id} not found")
    return dict(row)


def get_clients(conn: sqlite3.Connection, inbound_id: int) -> list[dict]:
    inbound = get_inbound(conn, inbound_id)
    settings = json.loads(inbound["settings"])
    return settings.get("clients", [])


def save_clients(conn: sqlite3.Connection, inbound_id: int, clients: list[dict]) -> None:
    inbound = get_inbound(conn, inbound_id)
    settings = json.loads(inbound["settings"])
    settings["clients"] = clients
    conn.execute(
        "UPDATE inbounds SET settings = ? WHERE id = ?",
        (json.dumps(settings, ensure_ascii=False), inbound_id),
    )
    conn.commit()


def ensure_client_traffic_row(
    conn: sqlite3.Connection,
    inbound_id: int,
    email: str,
    enable: bool = True,
) -> None:
    row = conn.execute(
        "SELECT id FROM client_traffics WHERE email = ? LIMIT 1",
        (email,),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE client_traffics SET inbound_id = ?, enable = ? WHERE id = ?",
            (inbound_id, 1 if enable else 0, row["id"]),
        )
    else:
        conn.execute(
            """
            INSERT OR IGNORE INTO client_traffics (
                inbound_id, enable, email, up, down, all_time, expiry_time, total, reset, last_online
            ) VALUES (?, ?, ?, 0, 0, 0, 0, 0, 0, 0)
            """,
            (inbound_id, 1 if enable else 0, email),
        )
        conn.execute(
            "UPDATE client_traffics SET inbound_id = ?, enable = ? WHERE email = ?",
            (inbound_id, 1 if enable else 0, email),
        )


def migrate_client_accounting(
    conn: sqlite3.Connection,
    inbound_id: int,
    old_email: str,
    new_email: str,
    enable: bool = True,
) -> None:
    if not old_email or old_email == new_email:
        ensure_client_traffic_row(conn, inbound_id, new_email, enable)
        return

    traffic_row = conn.execute(
        "SELECT id FROM client_traffics WHERE email = ? LIMIT 1",
        (old_email,),
    ).fetchone()
    if traffic_row:
        conn.execute(
            "UPDATE client_traffics SET inbound_id = ?, email = ?, enable = ? WHERE id = ?",
            (inbound_id, new_email, 1 if enable else 0, traffic_row["id"]),
        )
    else:
        ensure_client_traffic_row(conn, inbound_id, new_email, enable)

    conn.execute(
        "UPDATE inbound_client_ips SET client_email = ? WHERE client_email = ?",
        (new_email, old_email),
    )


def gen_sub_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=16))


def _preferred_candidates(port: int, mapping: dict[int, callable]) -> list[str]:
    factory = mapping.get(port)
    if not factory:
        return []
    return [item for item in factory() if item]


def _pick_preferred_value(values: list[str], preferred: list[str]) -> str:
    for candidate in preferred:
        if candidate in values:
            return candidate
    return values[0] if values else ""


def _pick_preferred_fingerprint(port: int) -> str:
    if port == 2083:
        return os.environ.get(
            "SECONDARY_REALITY_FINGERPRINT",
            os.environ.get("REALITY_FINGERPRINT", "qq"),
        )
    if port == 39829:
        return os.environ.get(
            "LEGACY_REALITY_FINGERPRINT",
            os.environ.get("REALITY_FINGERPRINT", "qq"),
        )
    return os.environ.get("REALITY_FINGERPRINT", "qq")


def ensure_client(
    conn: sqlite3.Connection,
    inbound_id: int,
    client_uuid: str,
    email: str,
    flow: str = "xtls-rprx-vision",
    tg_id: int = 0,
) -> str:
    """Add or update client. Returns 'added', 'updated', or 'unchanged'."""
    clients = get_clients(conn, inbound_id)

    for client in clients:
        if client.get("id") == client_uuid or client.get("email") == email:
            changed = False
            old_email = client.get("email") or ""
            if client.get("id") != client_uuid:
                client["id"] = client_uuid
                changed = True
            if client.get("email") != email:
                client["email"] = email
                changed = True
            if flow and client.get("flow") != flow:
                client["flow"] = flow
                changed = True
            if client.get("enable") is False:
                client["enable"] = True
                changed = True
            if tg_id and client.get("tgId") != tg_id:
                client["tgId"] = tg_id
                changed = True
            if changed:
                client["updated_at"] = int(time.time() * 1000)
                save_clients(conn, inbound_id, clients)
                migrate_client_accounting(
                    conn,
                    inbound_id,
                    old_email,
                    email,
                    bool(client.get("enable", True)),
                )
                conn.commit()
                return "updated"
            ensure_client_traffic_row(conn, inbound_id, email, bool(client.get("enable", True)))
            conn.commit()
            return "unchanged"

    new_client = {
        "id": client_uuid,
        "email": email,
        "enable": True,
        "flow": flow,
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": 0,
        "reset": 0,
        "tgId": tg_id or 0,
        "subId": gen_sub_id(),
        "comment": "",
        "created_at": int(time.time() * 1000),
        "updated_at": int(time.time() * 1000),
    }
    clients.append(new_client)
    save_clients(conn, inbound_id, clients)
    ensure_client_traffic_row(conn, inbound_id, email, True)
    conn.commit()
    return "added"


def remove_client(
    conn: sqlite3.Connection,
    inbound_id: int,
    client_uuid: str | None = None,
    email: str | None = None,
) -> bool:
    """Remove client by UUID or email. Returns True if removed."""
    clients = get_clients(conn, inbound_id)
    original_len = len(clients)
    filtered = []
    for client in clients:
        if client_uuid and client.get("id") == client_uuid:
            continue
        if email and client.get("email") == email:
            continue
        filtered.append(client)

    if len(filtered) == original_len:
        return False

    save_clients(conn, inbound_id, filtered)
    return True


def show_profile(conn: sqlite3.Connection, inbound_id: int) -> dict:
    """Extract connection profile from inbound settings."""
    inbound = get_inbound(conn, inbound_id)
    stream = json.loads(inbound.get("stream_settings") or "{}")
    port = int(inbound.get("port") or 0)

    clients = get_clients(conn, inbound_id)
    if not clients:
        raise RuntimeError("No clients found")

    profile = {
        "uuid": clients[0]["id"],
        "flow": clients[0].get("flow", ""),
        "security": stream.get("security", "none"),
        "network": stream.get("network", "tcp"),
    }

    if profile["security"] == "reality":
        reality = stream.get("realitySettings", {})
        reality_settings = reality.get("settings") or {}
        server_names = reality.get("serverNames") or []
        short_ids = reality.get("shortIds") or []
        profile.update(
            {
                "public_key": reality.get("publicKey")
                or reality_settings.get("publicKey")
                or os.environ.get("REALITY_PUBLIC_KEY", ""),
                "server_name": _pick_preferred_value(
                    server_names, _preferred_candidates(port, PORT_PREFERRED_SERVER_NAMES)
                )
                or os.environ.get("REALITY_SNI", "eh.vk.com"),
                "short_id": _pick_preferred_value(
                    short_ids, _preferred_candidates(port, PORT_PREFERRED_SHORT_IDS)
                ),
                "fingerprint": _pick_preferred_fingerprint(port),
                "type": stream.get("network", "tcp"),
                "padding": 0,
            }
        )
    elif profile["security"] == "tls":
        xhttp = stream.get("xhttpSettings", {})
        profile.update(
            {
                "path": xhttp.get("path", "/"),
                "mode": xhttp.get("mode", "auto"),
                "type": stream.get("network", "tcp"),
            }
        )

    return profile


def list_clients_cmd(conn: sqlite3.Connection, inbound_id: int) -> list[dict]:
    clients = get_clients(conn, inbound_id)
    return [
        {
            "uuid": c.get("id"),
            "email": c.get("email"),
            "enable": c.get("enable", True),
            "tgId": c.get("tgId", 0),
        }
        for c in clients
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="x-ui client manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure = subparsers.add_parser("ensure-client")
    ensure.add_argument("--db", default=str(DEFAULT_DB))
    ensure.add_argument("--inbound-id", type=int)
    ensure.add_argument("--port", type=int)
    ensure.add_argument("--config")
    ensure.add_argument("--uuid", required=True)
    ensure.add_argument("--email", required=True)
    ensure.add_argument("--flow", default="xtls-rprx-vision")
    ensure.add_argument("--tg-id", type=int, default=0)

    show = subparsers.add_parser("show-profile")
    show.add_argument("--db", default=str(DEFAULT_DB))
    show.add_argument("--inbound-id", type=int)
    show.add_argument("--port", type=int)
    show.add_argument("--config")

    remove = subparsers.add_parser("remove-client")
    remove.add_argument("--db", default=str(DEFAULT_DB))
    remove.add_argument("--inbound-id", type=int)
    remove.add_argument("--port", type=int)
    remove.add_argument("--config")
    remove.add_argument("--uuid")
    remove.add_argument("--email")

    ls = subparsers.add_parser("list-clients")
    ls.add_argument("--db", default=str(DEFAULT_DB))
    ls.add_argument("--inbound-id", type=int)
    ls.add_argument("--port", type=int)
    ls.add_argument("--config")

    args = parser.parse_args()
    conn = get_db(Path(args.db))

    try:
        if args.command == "ensure-client":
            inbound_id = resolve_inbound_id(conn, args.inbound_id, args.port)
            result = ensure_client(conn, inbound_id, args.uuid, args.email, args.flow, args.tg_id)
            print(result)

        elif args.command == "show-profile":
            inbound_id = resolve_inbound_id(conn, args.inbound_id, args.port)
            print(json.dumps(show_profile(conn, inbound_id), ensure_ascii=False))

        elif args.command == "remove-client":
            if not args.uuid and not args.email:
                raise RuntimeError("--uuid or --email required")
            inbound_id = resolve_inbound_id(conn, args.inbound_id, args.port)
            removed = remove_client(conn, inbound_id, args.uuid, args.email)
            print("removed" if removed else "unchanged")

        elif args.command == "list-clients":
            inbound_id = resolve_inbound_id(conn, args.inbound_id, args.port)
            print(json.dumps(list_clients_cmd(conn, inbound_id), ensure_ascii=False, indent=2))

    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
