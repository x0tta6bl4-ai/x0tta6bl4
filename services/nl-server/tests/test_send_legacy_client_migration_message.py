#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import hashlib
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
MODULE_PATH = ROOT / "ghost-access" / "send_legacy_client_migration_message.py"


def load_module():
    spec = importlib.util.spec_from_file_location("send_legacy_client_migration_message", MODULE_PATH)
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
        "send_policy": {
            "automatic_broadcast_allowed": False,
            "manual_operator_review_required": True,
        },
        "migration_request": {
            "message_ru": (
                "Если VPN сейчас не подключается, обновите профиль. "
                "Откройте этого бота, нажмите Подключить и импортируйте свежий профиль Reality. "
                "После проверки ответьте только одним вариантом: done updated, fail import, "
                "fail timeout или fail no-internet. "
                "Не присылайте ссылки, QR-коды, UUID, IP-адреса, скриншоты, логи, телефон или username."
            )
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
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (111, 'active-token', '2027-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (222, 'expired-token', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (333, 'active-no-device', '2027-01-01T00:00:00Z')"
        )
        conn.execute("INSERT INTO devices(user_id) VALUES (111)")
        conn.execute("INSERT INTO devices(user_id) VALUES (222)")
        conn.commit()


class SendLegacyClientMigrationMessageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_read_active_user_ids_excludes_expired_and_no_device(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ghost.db"
            create_db(db_path)
            user_ids = self.module.read_active_user_ids(
                db_path,
                now=datetime(2026, 6, 5, tzinfo=UTC),
            )

        self.assertEqual(user_ids, [111])

    def test_dry_run_reports_counts_without_private_ids_or_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db_path = tmp / "ghost.db"
            packet_path = tmp / "packet.json"
            create_db(db_path)
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--db-path",
                        str(db_path),
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 0)
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["candidate_active_user_count"], 1)
        self.assertEqual(payload["selected_user_count"], 0)
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("111", rendered)
        self.assertNotIn("active-token", rendered)
        self.assertFalse(payload["privacy"]["raw_user_ids_printed"])
        self.assertFalse(payload["privacy"]["raw_chat_ids_printed"])

    def test_apply_requires_confirm_packet_sha_limit_and_bot_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db_path = tmp / "ghost.db"
            packet_path = tmp / "packet.json"
            create_db(db_path)
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")

            with self.assertRaises(self.module.LegacyMigrationSendError):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--db-path",
                        str(db_path),
                        "--apply",
                    ]
                )

    def test_apply_with_fake_sender_reports_only_aggregate_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            db_path = tmp / "ghost.db"
            packet_path = tmp / "packet.json"
            create_db(db_path)
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            sent_to: list[int] = []

            def fake_sender(uid: int, text: str) -> str:
                sent_to.append(uid)
                self.assertIn("Reality", text)
                return "sent"

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--db-path",
                        str(db_path),
                        "--apply",
                        "--confirm",
                        "SEND_LEGACY_MIGRATION",
                        "--expect-packet-sha256",
                        packet_sha,
                        "--limit",
                        "1",
                        "--bot-token",
                        "test-token",
                        "--sleep-seconds",
                        "0",
                        "--json",
                    ],
                    sender=fake_sender,
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 0)
        self.assertEqual(sent_to, [111])
        self.assertEqual(payload["mode"], "apply")
        self.assertEqual(payload["selected_user_count"], 1)
        self.assertEqual(payload["sent_count"], 1)
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("111", rendered)
        self.assertNotIn("test-token", rendered)


if __name__ == "__main__":
    unittest.main()
