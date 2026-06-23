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
MODULE_PATH = ROOT / "ghost-access" / "record_legacy_client_migration_reply.py"


def load_module():
    spec = importlib.util.spec_from_file_location("record_legacy_client_migration_reply", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ready_packet() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T12:46:31Z",
        "decision": "LEGACY_CLIENT_MIGRATION_PACKET_READY",
        "operator_action": "ask_legacy_clients_to_refresh_reality_profile",
        "send_policy": {
            "automatic_broadcast_allowed": False,
            "manual_operator_review_required": True,
        },
        "target_audience": {
            "active_subscription_count": 2,
            "expired_users_excluded": 1,
            "users_with_devices": 3,
            "raw_user_ids_printed": False,
            "raw_chat_ids_printed": False,
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


class RecordLegacyClientMigrationReplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_parse_reply_accepts_only_safe_short_values(self) -> None:
        self.assertEqual(
            self.module.parse_reply("done updated"),
            {"reply": "done updated", "result": "done", "symptom": "updated"},
        )
        self.assertEqual(
            self.module.parse_reply("fail no-internet"),
            {"reply": "fail no-internet", "result": "fail", "symptom": "no-internet"},
        )
        with self.assertRaises(self.module.LegacyMigrationReplyError):
            self.module.parse_reply("done vless://secret")
        with self.assertRaises(self.module.LegacyMigrationReplyError):
            self.module.parse_reply("pass connected")

    def test_write_requires_packet_sha_and_stdin_or_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")

            with self.assertRaises(self.module.LegacyMigrationReplyError):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--json-out",
                        str(tmp / "replies.json"),
                        "--reply",
                        "done updated",
                        "--write",
                    ]
                )

    def test_records_reply_aggregate_without_private_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            replies_path = tmp / "replies.json"
            md_path = tmp / "replies.md"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            reply_file = tmp / "reply.txt"
            reply_file.write_text("done updated\n", encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--json-out",
                        str(replies_path),
                        "--markdown-out",
                        str(md_path),
                        "--reporter-label",
                        "legacy-client-1",
                        "--reply-file",
                        str(reply_file),
                        "--expect-packet-sha256",
                        packet_sha,
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            markdown = md_path.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["status"], "partial_client_replies")
        self.assertEqual(payload["total_replies"], 1)
        self.assertEqual(payload["done_updated_count"], 1)
        self.assertEqual(payload["reply_counts"], {"done updated": 1})
        self.assertFalse(payload["privacy"]["raw_user_ids_stored"])
        rendered = json.dumps(payload, ensure_ascii=False) + markdown
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("/sub/", rendered)
        self.assertNotIn("http://", rendered)
        self.assertNotIn("https://", rendered)
        self.assertNotIn("@", rendered)

    def test_rejects_packet_sha_mismatch_and_private_reporter_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            reply_file = tmp / "reply.txt"
            reply_file.write_text("done updated\n", encoding="utf-8")

            with self.assertRaises(self.module.LegacyMigrationReplyError):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--json-out",
                        str(tmp / "replies.json"),
                        "--reporter-label",
                        "user@example.test",
                        "--reply-file",
                        str(reply_file),
                        "--expect-packet-sha256",
                        "0" * 64,
                        "--write",
                    ]
                )


if __name__ == "__main__":
    unittest.main()
