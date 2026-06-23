#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "collect_legacy_migration_replies_from_bot_journal.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "collect_legacy_migration_replies_from_bot_journal",
        MODULE_PATH,
    )
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


class CollectLegacyMigrationRepliesFromBotJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_collects_allowed_replies_and_dedupes_per_reporter_without_private_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            journal_path = tmp / "journal.log"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            journal_path.write_text(
                "\n".join(
                    [
                        "Jun 05 host bot[1]: INFO:__main__:incoming fallback text='done updated' from chat_id=111 user_id=111",
                        "Jun 05 host bot[1]: INFO:__main__:incoming fallback text='fail timeout' from chat_id=222 user_id=222",
                        "Jun 05 host bot[1]: INFO:__main__:incoming fallback text='done updated' from chat_id=222 user_id=222",
                        "Jun 05 host bot[1]: INFO:__main__:incoming fallback text='vless://secret' from chat_id=333 user_id=333",
                    ]
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--journal-file",
                        str(journal_path),
                        "--expect-packet-sha256",
                        packet_sha,
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 0)
        self.assertEqual(payload["status"], "all_reported_updated_by_count")
        self.assertEqual(payload["total_replies"], 2)
        self.assertEqual(payload["done_updated_count"], 2)
        self.assertEqual(payload["failure_count"], 0)
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("111", rendered)
        self.assertNotIn("222", rendered)
        self.assertNotIn("333", rendered)
        self.assertNotIn("vless://", rendered)
        self.assertFalse(payload["privacy"]["raw_user_ids_stored"])
        self.assertFalse(payload["privacy"]["raw_chat_ids_stored"])

    def test_write_requires_sha_or_current_packet_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            journal_path = tmp / "journal.log"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            journal_path.write_text("", encoding="utf-8")

            with self.assertRaises(self.module.LegacyMigrationJournalReplyError):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--journal-file",
                        str(journal_path),
                        "--json-out",
                        str(tmp / "replies.json"),
                        "--write",
                    ]
                )

    def test_writes_no_client_replies_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            journal_path = tmp / "journal.log"
            replies_path = tmp / "replies.json"
            markdown_path = tmp / "replies.md"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            journal_path.write_text(
                "Jun 05 host bot[1]: INFO:__main__:incoming fallback text='hello' from chat_id=111 user_id=111",
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--journal-file",
                        str(journal_path),
                        "--json-out",
                        str(replies_path),
                        "--markdown-out",
                        str(markdown_path),
                        "--confirm-current-packet",
                        "COLLECT_CURRENT_LEGACY_REPLIES",
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

            self.assertEqual(rc, 0)
            self.assertEqual(payload["status"], "no_client_replies")
            self.assertEqual(payload["total_replies"], 0)
            self.assertEqual(
                json.loads(replies_path.read_text(encoding="utf-8"))["status"],
                "no_client_replies",
            )
            self.assertIn("none", markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
