#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "collect_legacy_migration_progress.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_legacy_migration_progress", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ready_packet() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T13:01:20Z",
        "decision": "LEGACY_CLIENT_MIGRATION_PACKET_READY",
        "target_audience": {
            "active_subscription_count": 2,
            "expired_users_excluded": 1,
            "users_with_devices": 3,
        },
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


def message_send() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T13:27:02Z",
        "decision": "LEGACY_CLIENT_MIGRATION_MESSAGE_SENT",
        "sent_count": 2,
        "selected_user_count": 2,
    }


def replies() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T13:40:00Z",
        "status": "no_client_replies",
        "total_replies": 0,
        "done_updated_count": 0,
        "failure_count": 0,
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


def create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                subscription_token TEXT,
                expires_at TEXT
            );
            CREATE TABLE devices (
                device_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                profile_kind TEXT,
                status TEXT,
                last_seen_at TEXT,
                last_handshake_at TEXT,
                vpn_uuid TEXT,
                last_ip TEXT
            );
            CREATE TABLE subscription_accesses (
                access_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_agent TEXT,
                client_app TEXT,
                ip_address TEXT,
                last_seen_at TEXT
            );
            CREATE TABLE request_events (
                event_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                action TEXT,
                created_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (111, 'token-a', '2027-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (222, 'token-b', '2027-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (333, 'token-c', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO devices(user_id, profile_kind, status, last_seen_at, last_handshake_at, vpn_uuid, last_ip) "
            "VALUES (111, 'reality', 'active', '2026-06-05T13:52:35.011000', '2026-06-05T13:52:35.011000', 'secret-uuid', '127.0.0.1')"
        )
        conn.execute(
            "INSERT INTO devices(user_id, profile_kind, status, last_seen_at, last_handshake_at, vpn_uuid, last_ip) "
            "VALUES (222, 'reality', 'active', '2026-06-05T13:54:35.011000', '2026-06-05T13:54:35.011000', 'secret-uuid', '127.0.0.2')"
        )
        conn.execute(
            "INSERT INTO devices(user_id, profile_kind, status, last_seen_at, last_handshake_at, vpn_uuid, last_ip) "
            "VALUES (333, 'reality', 'active', '2026-06-05T13:55:35.011000', '2026-06-05T13:55:35.011000', 'secret-uuid', '127.0.0.3')"
        )
        conn.execute(
            "INSERT INTO subscription_accesses(user_id, user_agent, client_app, ip_address, last_seen_at) "
            "VALUES (111, 'v2rayN/7.20.4', 'v2rayn', '198.51.100.10', '2026-06-05 13:53:08')"
        )
        conn.execute(
            "INSERT INTO subscription_accesses(user_id, user_agent, client_app, ip_address, last_seen_at) "
            "VALUES (222, 'Hiddify/1.0', 'hiddify', '198.51.100.11', '2026-06-05 13:53:09')"
        )
        conn.execute(
            "INSERT INTO subscription_accesses(user_id, user_agent, client_app, ip_address, last_seen_at) "
            "VALUES (111, 'x0tta-live-subscription-payload-check/1.0', 'x0tta-live-subscription-payload-check', '127.0.0.1', '2026-06-05 13:54:09')"
        )
        conn.execute(
            "INSERT INTO request_events(user_id, action, created_at) VALUES (111, 'config', '2026-06-05T13:31:01')"
        )
        conn.commit()


class CollectLegacyMigrationProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_collects_progress_without_private_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            replies_path = tmp / "replies.json"
            db_path = tmp / "ghost.db"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            replies_path.write_text(json.dumps(replies()), encoding="utf-8")
            create_db(db_path)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--replies",
                        str(replies_path),
                        "--db-path",
                        str(db_path),
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 0)
        self.assertEqual(payload["status"], "all_active_device_activity_seen_after_message")
        self.assertEqual(
            payload["db_progress"]["subscription_refresh"]["active_users_with_subscription_pull_since_message"],
            2,
        )
        self.assertEqual(
            payload["db_progress"]["device_activity"]["active_users_with_device_activity_since_message"],
            2,
        )
        self.assertEqual(payload["db_progress"]["request_events"]["config_requests_since_message"], 1)
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("111", rendered)
        self.assertNotIn("222", rendered)
        self.assertNotIn("333", rendered)
        self.assertNotIn("token-a", rendered)
        self.assertNotIn("secret-uuid", rendered)
        self.assertNotIn("127.0.0.1", rendered)
        self.assertFalse(payload["privacy"]["raw_user_ids_stored"])

    def test_write_requires_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            create_db(db_path)
            with self.assertRaises(self.module.LegacyMigrationProgressError):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(tmp / "progress.json"),
                        "--write",
                    ]
                )

    def test_parse_time_handles_sqlite_and_iso_formats(self) -> None:
        self.assertEqual(
            self.module.parse_time("2026-06-05 13:53:08"),
            datetime(2026, 6, 5, 13, 53, 8, tzinfo=UTC),
        )
        self.assertEqual(
            self.module.parse_time("2026-06-05T13:53:08Z"),
            datetime(2026, 6, 5, 13, 53, 8, tzinfo=UTC),
        )


if __name__ == "__main__":
    unittest.main()
