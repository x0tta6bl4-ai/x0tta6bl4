from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "diagnose_user_subscription.py"


def load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("diagnose_user_subscription_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_args(module: types.ModuleType, ghost_db: Path, xui_db: Path, access_log: Path, *extra: str):
    return module.parse_args(
        [
            "--username",
            "hippycirz",
            "--ghost-db-path",
            str(ghost_db),
            "--xui-db-path",
            str(xui_db),
            "--access-log",
            str(access_log),
            *extra,
        ]
    )


def future_iso() -> str:
    return (datetime.now(UTC) + timedelta(days=365)).isoformat()


def recent_iso() -> str:
    return datetime.now(UTC).isoformat()


def create_ghost_db(path: Path, *, token: str = "user-token-12345678901234567890") -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                plan TEXT,
                expires_at TEXT,
                vpn_uuid TEXT,
                subscription_token TEXT,
                subscription_updated_at TEXT,
                delivery_profile TEXT,
                entry_node TEXT,
                client_family TEXT,
                transport_preference TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE devices (
                device_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                device_name TEXT,
                device_type TEXT,
                vpn_uuid TEXT,
                xray_email TEXT,
                status TEXT,
                profile_kind TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                last_ip TEXT,
                last_handshake_at TEXT,
                created_at TEXT,
                revoked_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                user_id, username, plan, expires_at, vpn_uuid, subscription_token,
                subscription_updated_at, delivery_profile, entry_node, client_family,
                transport_preference
            )
            VALUES (
                5330612764, 'hippycirz', 'basic_12m', ?, 'user-uuid',
                ?, ?, 'default_nl', 'nl', 'generic', ''
            )
            """,
            (future_iso(), token, recent_iso()),
        )
        rows = [
            (
                37,
                "Device 1",
                "unknown",
                "378042ee-5c74-43dd-9156-826fed6e6b66",
                "hippycirz__5330612764__device_1",
            ),
            (
                41,
                "My phone",
                "my_phone",
                "752de297-019b-4fe9-ad19-932e5391e7ef",
                "hippycirz__5330612764__my_phone",
            ),
        ]
        for device_id, name, dtype, uuid, email in rows:
            conn.execute(
                """
                INSERT INTO devices (
                    device_id, user_id, device_name, device_type, vpn_uuid, xray_email,
                    status, profile_kind, first_seen_at, last_seen_at, last_ip,
                    last_handshake_at, created_at, revoked_at
                )
                VALUES (?, 5330612764, ?, ?, ?, ?, 'active', 'reality', ?, ?, '192.0.2.10', ?, ?, NULL)
                """,
                (device_id, name, dtype, uuid, email, recent_iso(), recent_iso(), recent_iso(), recent_iso()),
            )


def create_xui_db(path: Path, *, omit_email_on_port: tuple[str, int] | None = None, disabled_email: str = "") -> None:
    clients = [
        {
            "id": "378042ee-5c74-43dd-9156-826fed6e6b66",
            "email": "hippycirz__5330612764__device_1",
            "enable": True,
            "flow": "xtls-rprx-vision",
            "tgId": 5330612764,
        },
        {
            "id": "752de297-019b-4fe9-ad19-932e5391e7ef",
            "email": "hippycirz__5330612764__my_phone",
            "enable": True,
            "flow": "xtls-rprx-vision",
            "tgId": 5330612764,
        },
    ]
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE inbounds (
                id INTEGER PRIMARY KEY,
                port INTEGER,
                tag TEXT,
                remark TEXT,
                enable INTEGER,
                settings TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE client_traffics (
                inbound_id INTEGER,
                enable INTEGER,
                email TEXT,
                up INTEGER,
                down INTEGER,
                all_time INTEGER,
                expiry_time INTEGER,
                total INTEGER,
                reset INTEGER,
                last_online INTEGER
            )
            """
        )
        for inbound_id, port in [(2, 443), (3, 2083)]:
            port_clients = []
            for client in clients:
                if omit_email_on_port == (client["email"], port):
                    continue
                row = dict(client)
                if disabled_email == row["email"]:
                    row["enable"] = False
                port_clients.append(row)
            conn.execute(
                """
                INSERT INTO inbounds (id, port, tag, remark, enable, settings)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                (
                    inbound_id,
                    port,
                    f"inbound-{port}",
                    f"VLESS-{port}",
                    json.dumps({"clients": port_clients}),
                ),
            )
        for client in clients:
            conn.execute(
                """
                INSERT INTO client_traffics (
                    inbound_id, enable, email, up, down, all_time, expiry_time,
                    total, reset, last_online
                )
                VALUES (3, 1, ?, 10, 20, 30, 0, 0, 0, 1780235513009)
                """,
                (client["email"],),
            )


class FakeSubscriptionResponse:
    status = 200
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "subscription-userinfo": "upload=0; download=0; total=0; expire=9999999999",
    }

    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "FakeSubscriptionResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self._body


class DiagnoseUserSubscriptionTests(unittest.TestCase):
    def test_healthy_user_subscription_report(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            ghost_db = Path(tmp) / "ghost.db"
            xui_db = Path(tmp) / "xui.db"
            access_log = Path(tmp) / "access.log"
            create_ghost_db(ghost_db)
            create_xui_db(xui_db)
            access_log.write_text(
                "2026/05/31 13:54:50 accepted tcp:example.com:443 "
                "[inbound-443 -> direct] email: hippycirz__5330612764__device_1\n",
                encoding="utf-8",
            )

            report = module.build_report(make_args(module, ghost_db, xui_db, access_log))

        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["summary"]["active_device_count"], 2)
        self.assertEqual(report["summary"]["active_device_missing_xui_port_count"], 0)
        self.assertEqual(report["summary"]["blocked_route_count"], 0)

    def test_missing_xui_client_marks_broken(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            ghost_db = Path(tmp) / "ghost.db"
            xui_db = Path(tmp) / "xui.db"
            access_log = Path(tmp) / "access.log"
            create_ghost_db(ghost_db)
            create_xui_db(xui_db, omit_email_on_port=("hippycirz__5330612764__my_phone", 2083))
            access_log.write_text("", encoding="utf-8")

            report = module.build_report(make_args(module, ghost_db, xui_db, access_log))

        self.assertEqual(report["status"], "broken")
        self.assertIn("active_device_missing_xui_port", report["summary"]["hard_failures"])
        self.assertEqual(report["summary"]["active_device_missing_xui_port_count"], 1)

    def test_empty_subscription_token_marks_broken(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            ghost_db = Path(tmp) / "ghost.db"
            xui_db = Path(tmp) / "xui.db"
            access_log = Path(tmp) / "access.log"
            create_ghost_db(ghost_db, token="")
            create_xui_db(xui_db)
            access_log.write_text("", encoding="utf-8")

            report = module.build_report(make_args(module, ghost_db, xui_db, access_log))

        self.assertEqual(report["status"], "broken")
        self.assertIn("subscription_token_missing", report["summary"]["hard_failures"])

    def test_blocked_routes_mark_attention_without_subscription_failure(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            ghost_db = Path(tmp) / "ghost.db"
            xui_db = Path(tmp) / "xui.db"
            access_log = Path(tmp) / "access.log"
            create_ghost_db(ghost_db)
            create_xui_db(xui_db)
            access_log.write_text(
                "2026/05/31 13:54:50 accepted tcp:ads.example:443 "
                "[inbound-443 -> blocked] email: hippycirz__5330612764__my_phone\n",
                encoding="utf-8",
            )

            report = module.build_report(make_args(module, ghost_db, xui_db, access_log))

        self.assertEqual(report["status"], "attention")
        self.assertIn("blocked_routes_observed", report["summary"]["warnings"])
        self.assertEqual(report["access_log"]["inbounds"], {"inbound-443": 1})
        self.assertEqual(report["access_log"]["blocked_targets"][0]["target"], "ads.example")

    def test_access_log_tail_lines_limits_scan_window(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            access_log = Path(tmp) / "access.log"
            access_log.write_text(
                "2026/05/31 13:54:50 accepted tcp:ads.example:443 "
                "[inbound-443 -> blocked] email: hippycirz__5330612764__my_phone\n"
                "2026/05/31 13:55:00 accepted tcp:other.example:443 "
                "[inbound-443 -> direct] email: another_user\n",
                encoding="utf-8",
            )

            report = module.parse_access_log(access_log, "hippycirz", 1)

        self.assertTrue(report["checked"])
        self.assertEqual(report["sample_line_count"], 0)
        self.assertEqual(report["blocked_total"], 0)

    def test_subscription_http_check_verifies_device_uuids(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            ghost_db = Path(tmp) / "ghost.db"
            xui_db = Path(tmp) / "xui.db"
            access_log = Path(tmp) / "access.log"
            create_ghost_db(ghost_db, token="token-for-http")
            create_xui_db(xui_db)
            access_log.write_text("", encoding="utf-8")
            body = "\n".join(
                [
                    "vless://378042ee-5c74-43dd-9156-826fed6e6b66@example#device1",
                    "vless://752de297-019b-4fe9-ad19-932e5391e7ef@example#phone",
                ]
            ).encode()
            with patch.object(
                module.request,
                "urlopen",
                return_value=FakeSubscriptionResponse(base64.b64encode(body)),
            ):
                report = module.build_report(
                    make_args(
                        module,
                        ghost_db,
                        xui_db,
                        access_log,
                        "--check-subscription-http",
                        "--subscription-base-url",
                        "https://vpn.example",
                    )
                )

        self.assertEqual(report["status"], "healthy")
        self.assertEqual(report["subscription"]["http_status"], 200)
        self.assertEqual(report["subscription"]["vless_line_count"], 2)
        self.assertTrue(all(item["uuid_present"] for item in report["subscription"]["uuid_presence"]))


if __name__ == "__main__":
    unittest.main()
