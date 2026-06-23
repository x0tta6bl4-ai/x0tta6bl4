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
MODULE_PATH = ROOT / "ghost-access" / "build_legacy_client_migration_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_legacy_client_migration_packet", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def transport_attention() -> dict:
    return {
        "generated_at": "2026-06-05T12:30:05Z",
        "ok": False,
        "decision": "TRANSPORT_USAGE_ATTENTION",
        "operator_action": "check_legacy_clients_and_migrate_to_reality",
        "findings": [
            "15m:ghost_xhttp:legacy_proxy_4xx_seen",
            "15m:ghost_xhttp:legacy_proxy_requests_without_dataplane",
        ],
        "privacy": {
            "raw_identifiers_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_target_host_stored": False,
        },
        "windows": {
            "15m": {
                "legacy_transport_health": {
                    "ok": False,
                    "status": "attention",
                    "findings": [
                        "ghost_xhttp:legacy_proxy_4xx_seen",
                        "ghost_xhttp:legacy_proxy_requests_without_dataplane",
                    ],
                    "transports": {
                        "ghost_xhttp": {
                            "status": "legacy_attention",
                            "proxy_requests": 17,
                            "proxy_4xx": 17,
                            "proxy_5xx": 0,
                            "dataplane_events": 0,
                            "unique_client_count": 0,
                            "findings": [
                                "legacy_proxy_requests_without_dataplane",
                                "legacy_proxy_4xx_seen",
                            ],
                        }
                    },
                }
            },
            "60m": {
                "legacy_transport_health": {
                    "ok": False,
                    "status": "attention",
                    "findings": ["ghost_xhttp:legacy_proxy_4xx_seen"],
                    "transports": {
                        "ghost_xhttp": {
                            "status": "legacy_attention",
                            "proxy_requests": 67,
                            "proxy_4xx": 67,
                            "proxy_5xx": 0,
                            "dataplane_events": 0,
                            "unique_client_count": 0,
                            "findings": ["legacy_proxy_4xx_seen"],
                        }
                    },
                }
            },
        },
    }


def safe_subscription() -> dict:
    return {
        "generated_at": "2026-06-05T12:30:05Z",
        "ok": True,
        "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
        "checked_subscription_count": 14,
        "candidate_subscription_count": 14,
        "ports": [443, 2083],
        "transport_counts": {"reality": 76},
        "failures": [],
        "privacy": {
            "raw_tokens_printed": False,
            "raw_profile_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_host_printed": False,
        },
    }


class BuildLegacyClientMigrationPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_packet_is_ready_when_legacy_attention_and_reality_subscription_safe(self) -> None:
        packet = self.module.build_packet(
            transport_usage=transport_attention(),
            subscription_payload=safe_subscription(),
            db_summary={
                "available": True,
                "active_users": 14,
                "expired_users": 13,
                "users_with_devices": 27,
                "raw_user_ids_printed": False,
                "raw_tokens_printed": False,
            },
            generated_at="2026-06-05T12:40:00Z",
        )

        self.assertEqual(packet["decision"], "LEGACY_CLIENT_MIGRATION_PACKET_READY")
        self.assertEqual(
            packet["operator_action"],
            "ask_legacy_clients_to_refresh_reality_profile",
        )
        self.assertFalse(packet["send_policy"]["automatic_broadcast_allowed"])
        self.assertEqual(packet["target_audience"]["active_subscription_count"], 14)
        self.assertEqual(packet["target_audience"]["expired_users_excluded"], 13)
        self.assertEqual(packet["current_safe_profile"]["ports"], [443, 2083])
        self.assertIn("Reality", packet["migration_request"]["message_ru"])
        self.assertIn("done updated", packet["migration_request"]["safe_reply_options"])
        record_command = packet["migration_request"]["operator_reply_record_commands"]["done updated"]
        validate_command = packet["migration_request"]["operator_reply_validate_commands"]["done updated"]
        self.assertIn("record_legacy_client_migration_reply.py", record_command)
        self.assertIn("--expect-packet-sha256", record_command)
        self.assertIn("--reply-stdin", record_command)
        self.assertIn("--write", record_command)
        self.assertIn("record_legacy_client_migration_reply.py", validate_command)
        self.assertIn("--expect-packet-sha256", validate_command)
        self.assertIn("--reply-stdin", validate_command)
        self.assertNotIn("--write", validate_command)
        self.assertEqual(self.module.validate_output(packet), [])

    def test_packet_blocks_when_subscription_payload_is_unsafe(self) -> None:
        subscription = safe_subscription()
        subscription["ok"] = False
        subscription["transport_counts"] = {"reality": 1, "xhttp": 1}
        subscription["ports"] = [443, 8443]
        subscription["failures"] = ["subscription_disallowed_transport"]

        packet = self.module.build_packet(
            transport_usage=transport_attention(),
            subscription_payload=subscription,
            db_summary={},
            generated_at="2026-06-05T12:40:00Z",
        )

        self.assertEqual(packet["decision"], "LEGACY_CLIENT_MIGRATION_BLOCKED_SUBSCRIPTION_UNSAFE")
        self.assertEqual(packet["operator_action"], "fix_subscription_payload_before_migration")

    def test_db_summary_counts_users_without_printing_ids_or_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "ghost.db"
            with sqlite3.connect(db_path) as conn:
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
                    "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (1, 'token-one', '2027-01-01T00:00:00Z')"
                )
                conn.execute(
                    "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (2, 'token-two', '2026-01-01T00:00:00Z')"
                )
                conn.execute("INSERT INTO devices(user_id) VALUES (1)")
                conn.commit()

            summary = self.module.read_db_summary(
                db_path,
                now=datetime(2026, 6, 5, tzinfo=UTC),
            )

        rendered = json.dumps(summary, ensure_ascii=False)
        self.assertTrue(summary["available"])
        self.assertEqual(summary["total_users"], 2)
        self.assertEqual(summary["active_users"], 1)
        self.assertEqual(summary["expired_users"], 1)
        self.assertEqual(summary["users_with_devices"], 1)
        self.assertEqual(summary["users_without_devices"], 1)
        self.assertNotIn("token-one", rendered)
        self.assertFalse(summary["raw_user_ids_printed"])
        self.assertFalse(summary["raw_tokens_printed"])

    def test_cli_writes_privacy_safe_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            transport_path = tmp / "transport.json"
            subscription_path = tmp / "subscription.json"
            json_out = tmp / "packet.json"
            md_out = tmp / "packet.md"
            transport_path.write_text(json.dumps(transport_attention()), encoding="utf-8")
            subscription_path.write_text(json.dumps(safe_subscription()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--transport-usage",
                        str(transport_path),
                        "--subscription-payload",
                        str(subscription_path),
                        "--db-path",
                        str(tmp / "missing.db"),
                        "--json-out",
                        str(json_out),
                        "--markdown-out",
                        str(md_out),
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            markdown = md_out.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "LEGACY_CLIENT_MIGRATION_PACKET_READY")
        self.assertIn("LEGACY_CLIENT_MIGRATION_PACKET_READY", markdown)
        self.assertIn("record_legacy_client_migration_reply.py", markdown)
        self.assertIn("--expect-packet-sha256", markdown)
        rendered = json.dumps(payload, ensure_ascii=False) + markdown
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("/sub/", rendered)
        self.assertNotIn("http://", rendered)
        self.assertNotIn("https://", rendered)
        self.assertNotIn("@", rendered)


if __name__ == "__main__":
    unittest.main()
