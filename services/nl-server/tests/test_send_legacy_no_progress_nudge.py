#!/usr/bin/env python3
from __future__ import annotations

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
MODULE_PATH = ROOT / "ghost-access" / "send_legacy_no_progress_nudge.py"


def load_module():
    spec = importlib.util.spec_from_file_location("send_legacy_no_progress_nudge", MODULE_PATH)
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


def safe_subscription_payload_status() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T13:27:30Z",
        "decision": "LIVE_SUBSCRIPTION_PAYLOAD_SAFE",
        "ok": True,
        "checked_subscription_count": 2,
        "candidate_subscription_count": 2,
        "ports": [443, 2083],
        "transport_counts": {"reality": 4},
        "failures": [],
        "anti_dpi": {
            "status": "ready",
            "ready": True,
            "reality_only": True,
            "legacy_transports_absent": True,
            "checked_subscription_count": 2,
            "ready_subscription_count": 2,
            "all_checked_have_primary_reality_443": True,
            "all_checked_have_secondary_reality_port": True,
            "raw_tokens_or_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_host_printed": False,
        },
        "privacy": {
            "raw_tokens_printed": False,
            "raw_profile_uris_printed": False,
            "raw_uuid_printed": False,
            "raw_host_printed": False,
        },
    }


def safe_transport_usage_status() -> dict:
    return {
        "schema_version": 1,
        "generated_at": "2026-06-05T13:27:30Z",
        "decision": "TRANSPORT_USAGE_ATTENTION",
        "ok": False,
        "findings": ["ghost_xhttp:legacy_proxy_4xx_seen"],
        "summary": {
            "severity": "single_source_stale_legacy",
            "attention_scope": "single_proxy_source",
            "restart_relevant": False,
            "operator_action": "monitor_single_stale_legacy_source_after_migration",
        },
        "privacy": {
            "raw_identifiers_stored": False,
            "raw_ip_stored": False,
            "raw_email_stored": False,
            "raw_target_host_stored": False,
            "raw_nginx_source_ip_stored": False,
            "raw_user_agent_stored": False,
        },
    }


def safe_replies_status(packet_sha: str) -> dict:
    return {
        "schema_version": 1,
        "source": "collect_legacy_migration_replies_from_bot_journal.py",
        "generated_at": "2026-06-05T13:27:30Z",
        "status": "no_client_replies",
        "operator_action": "collect_legacy_migration_replies",
        "total_replies": 0,
        "done_updated_count": 0,
        "failure_count": 0,
        "reply_counts": {},
        "result_counts": {},
        "symptom_counts": {},
        "events": [],
        "packet": {
            "sha256": packet_sha,
            "decision": "LEGACY_CLIENT_MIGRATION_PACKET_READY",
            "source": "/var/lib/ghost-access/legacy-migration/latest.json",
        },
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
                last_seen_at TEXT,
                last_handshake_at TEXT
            );
            CREATE TABLE subscription_accesses (
                access_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                user_agent TEXT,
                client_app TEXT,
                ip_address TEXT,
                last_seen_at TEXT
            );
            """
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (910000001, 'token-a', '2027-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (920000002, 'token-b', '2027-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO users(user_id, subscription_token, expires_at) VALUES (930000003, 'token-c', '2026-01-01T00:00:00Z')"
        )
        conn.execute(
            "INSERT INTO devices(user_id, last_seen_at, last_handshake_at) VALUES (910000001, '2026-06-05T13:52:35Z', '2026-06-05T13:52:35Z')"
        )
        conn.execute(
            "INSERT INTO devices(user_id, last_seen_at, last_handshake_at) VALUES (920000002, '2026-06-05T13:00:00Z', '2026-06-05T13:00:00Z')"
        )
        conn.execute(
            "INSERT INTO devices(user_id, last_seen_at, last_handshake_at) VALUES (930000003, '2026-06-05T13:55:00Z', '2026-06-05T13:55:00Z')"
        )
        conn.execute(
            "INSERT INTO subscription_accesses(user_id, user_agent, client_app, ip_address, last_seen_at) "
            "VALUES (910000001, 'x0tta-live-subscription-payload-check/1.0', 'x0tta-live-subscription-payload-check', '127.0.0.1', '2026-06-05 13:54:09')"
        )
        conn.commit()


class SendLegacyNoProgressNudgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_dry_run_reports_no_progress_candidate_without_private_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            create_db(db_path)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--min-age-minutes",
                        "0",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 0)
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["active_user_count"], 2)
        self.assertEqual(payload["progress_user_count"], 1)
        self.assertEqual(payload["no_progress_candidate_count"], 1)
        self.assertEqual(payload["selected_user_count"], 0)
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn("910000001", rendered)
        self.assertNotIn("920000002", rendered)
        self.assertNotIn("930000003", rendered)
        self.assertNotIn("token-a", rendered)
        self.assertFalse(payload["privacy"]["raw_user_ids_printed"])

    def test_dry_run_write_persists_aggregate_report_without_sending(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            report_path = tmp / "dry-run.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            create_db(db_path)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(report_path),
                        "--min-age-minutes",
                        "0",
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            persisted = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(persisted["mode"], "dry_run")
        self.assertEqual(persisted["selected_user_count"], 0)
        self.assertEqual(persisted["no_progress_candidate_count"], 1)
        rendered = json.dumps(persisted, ensure_ascii=False)
        self.assertNotIn("920000002", rendered)
        self.assertNotIn("token-b", rendered)

    def test_apply_requires_confirm_packet_sha_limit_and_bot_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            create_db(db_path)

            with self.assertRaises(self.module.LegacyNoProgressNudgeError):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--min-age-minutes",
                        "0",
                        "--apply",
                    ]
                )

    def test_apply_with_fake_sender_writes_aggregate_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            report_path = tmp / "nudge.json"
            dry_run_path = tmp / "dry-run.json"
            subscription_path = tmp / "subscription.json"
            transport_path = tmp / "transport.json"
            replies_path = tmp / "replies.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            subscription_path.write_text(json.dumps(safe_subscription_payload_status()), encoding="utf-8")
            transport_path.write_text(json.dumps(safe_transport_usage_status()), encoding="utf-8")
            create_db(db_path)
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            replies_path.write_text(json.dumps(safe_replies_status(packet_sha)), encoding="utf-8")
            subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()
            transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()
            replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()
            dry_stdout = io.StringIO()
            with redirect_stdout(dry_stdout):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(dry_run_path),
                        "--min-age-minutes",
                        "0",
                        "--write",
                        "--json",
                    ]
                )
            dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()
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
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(report_path),
                        "--dry-run-report",
                        str(dry_run_path),
                        "--replies",
                        str(replies_path),
                        "--subscription-payload-status",
                        str(subscription_path),
                        "--transport-usage-status",
                        str(transport_path),
                        "--min-age-minutes",
                        "0",
                        "--cooldown-hours",
                        "0",
                        "--dry-run-max-age-minutes",
                        "999999",
                        "--subscription-payload-max-age-minutes",
                        "999999",
                        "--transport-usage-max-age-minutes",
                        "999999",
                        "--replies-max-age-minutes",
                        "999999",
                        "--apply",
                        "--confirm",
                        "SEND_LEGACY_NO_PROGRESS_NUDGE",
                        "--expect-packet-sha256",
                        packet_sha,
                        "--expect-dry-run-sha256",
                        dry_run_sha,
                        "--expect-subscription-payload-sha256",
                        subscription_sha,
                        "--expect-transport-usage-sha256",
                        transport_sha,
                        "--expect-replies-sha256",
                        replies_sha,
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
            self.assertEqual(sent_to, [920000002])
            self.assertEqual(payload["mode"], "apply")
            self.assertEqual(payload["selected_user_count"], 1)
            self.assertEqual(payload["sent_count"], 1)
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["sent_count"], 1)
            rendered = json.dumps(payload, ensure_ascii=False)
            self.assertNotIn("920000002", rendered)
            self.assertNotIn("test-token", rendered)

    def test_apply_checks_canonical_cooldown_even_with_custom_json_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            old_default_json_out = self.module.DEFAULT_JSON_OUT
            self.module.DEFAULT_JSON_OUT = tmp / "canonical-no-progress-nudge.json"
            try:
                packet_path = tmp / "packet.json"
                send_path = tmp / "send.json"
                db_path = tmp / "ghost.db"
                custom_report_path = tmp / "custom-nudge.json"
                dry_run_path = tmp / "dry-run.json"
                subscription_path = tmp / "subscription.json"
                transport_path = tmp / "transport.json"
                replies_path = tmp / "replies.json"
                packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
                send_path.write_text(json.dumps(message_send()), encoding="utf-8")
                subscription_path.write_text(json.dumps(safe_subscription_payload_status()), encoding="utf-8")
                transport_path.write_text(json.dumps(safe_transport_usage_status()), encoding="utf-8")
                create_db(db_path)
                packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
                replies_path.write_text(json.dumps(safe_replies_status(packet_sha)), encoding="utf-8")
                subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()
                transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()
                replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()
                with redirect_stdout(io.StringIO()):
                    self.module.run(
                        [
                            "--packet",
                            str(packet_path),
                            "--message-send",
                            str(send_path),
                            "--db-path",
                            str(db_path),
                            "--json-out",
                            str(dry_run_path),
                            "--min-age-minutes",
                            "0",
                            "--write",
                            "--json",
                        ]
                    )
                dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()
                canonical_report = json.loads(dry_run_path.read_text(encoding="utf-8"))
                canonical_report["mode"] = "apply"
                canonical_report["decision"] = "LEGACY_NO_PROGRESS_NUDGE_SENT"
                canonical_report["selected_user_count"] = 1
                canonical_report["sent_count"] = 1
                canonical_report["generated_at"] = self.module.utc_now()
                self.module.DEFAULT_JSON_OUT.write_text(
                    json.dumps(canonical_report),
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(
                    self.module.LegacyNoProgressNudgeError,
                    "no-progress nudge cooldown is active",
                ):
                    self.module.run(
                        [
                            "--packet",
                            str(packet_path),
                            "--message-send",
                            str(send_path),
                            "--db-path",
                            str(db_path),
                            "--json-out",
                            str(custom_report_path),
                            "--dry-run-report",
                            str(dry_run_path),
                            "--replies",
                            str(replies_path),
                            "--subscription-payload-status",
                            str(subscription_path),
                            "--transport-usage-status",
                            str(transport_path),
                            "--min-age-minutes",
                            "0",
                            "--cooldown-hours",
                            "12",
                            "--dry-run-max-age-minutes",
                            "999999",
                            "--subscription-payload-max-age-minutes",
                            "999999",
                            "--transport-usage-max-age-minutes",
                            "999999",
                            "--replies-max-age-minutes",
                            "999999",
                            "--apply",
                            "--confirm",
                            "SEND_LEGACY_NO_PROGRESS_NUDGE",
                            "--expect-packet-sha256",
                            packet_sha,
                            "--expect-dry-run-sha256",
                            dry_run_sha,
                            "--expect-subscription-payload-sha256",
                            subscription_sha,
                            "--expect-transport-usage-sha256",
                            transport_sha,
                            "--expect-replies-sha256",
                            replies_sha,
                            "--limit",
                            "1",
                            "--bot-token",
                            "test-token",
                        ],
                        sender=lambda _uid, _text: "sent",
                    )
            finally:
                self.module.DEFAULT_JSON_OUT = old_default_json_out

    def test_apply_ignores_canonical_dry_run_for_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            old_default_json_out = self.module.DEFAULT_JSON_OUT
            self.module.DEFAULT_JSON_OUT = tmp / "canonical-no-progress-nudge.json"
            try:
                packet_path = tmp / "packet.json"
                send_path = tmp / "send.json"
                db_path = tmp / "ghost.db"
                report_path = tmp / "nudge.json"
                dry_run_path = tmp / "dry-run.json"
                subscription_path = tmp / "subscription.json"
                transport_path = tmp / "transport.json"
                replies_path = tmp / "replies.json"
                packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
                send_path.write_text(json.dumps(message_send()), encoding="utf-8")
                subscription_path.write_text(json.dumps(safe_subscription_payload_status()), encoding="utf-8")
                transport_path.write_text(json.dumps(safe_transport_usage_status()), encoding="utf-8")
                create_db(db_path)
                packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
                replies_path.write_text(json.dumps(safe_replies_status(packet_sha)), encoding="utf-8")
                subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()
                transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()
                replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()
                with redirect_stdout(io.StringIO()):
                    self.module.run(
                        [
                            "--packet",
                            str(packet_path),
                            "--message-send",
                            str(send_path),
                            "--db-path",
                            str(db_path),
                            "--json-out",
                            str(dry_run_path),
                            "--min-age-minutes",
                            "0",
                            "--write",
                            "--json",
                        ]
                    )
                self.module.DEFAULT_JSON_OUT.write_text(
                    dry_run_path.read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
                dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()
                sent_to: list[int] = []

                def fake_sender(uid: int, _text: str) -> str:
                    sent_to.append(uid)
                    return "sent"

                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    rc = self.module.run(
                        [
                            "--packet",
                            str(packet_path),
                            "--message-send",
                            str(send_path),
                            "--db-path",
                            str(db_path),
                            "--json-out",
                            str(report_path),
                            "--dry-run-report",
                            str(dry_run_path),
                            "--replies",
                            str(replies_path),
                            "--subscription-payload-status",
                            str(subscription_path),
                            "--transport-usage-status",
                            str(transport_path),
                            "--min-age-minutes",
                            "0",
                            "--cooldown-hours",
                            "12",
                            "--dry-run-max-age-minutes",
                            "999999",
                            "--subscription-payload-max-age-minutes",
                            "999999",
                            "--transport-usage-max-age-minutes",
                            "999999",
                            "--replies-max-age-minutes",
                            "999999",
                            "--apply",
                            "--confirm",
                            "SEND_LEGACY_NO_PROGRESS_NUDGE",
                            "--expect-packet-sha256",
                            packet_sha,
                            "--expect-dry-run-sha256",
                            dry_run_sha,
                            "--expect-subscription-payload-sha256",
                            subscription_sha,
                            "--expect-transport-usage-sha256",
                            transport_sha,
                            "--expect-replies-sha256",
                            replies_sha,
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
                self.assertEqual(sent_to, [920000002])
                self.assertEqual(payload["decision"], "LEGACY_NO_PROGRESS_NUDGE_SENT")
            finally:
                self.module.DEFAULT_JSON_OUT = old_default_json_out

    def test_apply_rejects_stale_or_unbound_dry_run_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            dry_run_path = tmp / "dry-run.json"
            subscription_path = tmp / "subscription.json"
            transport_path = tmp / "transport.json"
            replies_path = tmp / "replies.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            subscription_path.write_text(json.dumps(safe_subscription_payload_status()), encoding="utf-8")
            transport_path.write_text(json.dumps(safe_transport_usage_status()), encoding="utf-8")
            create_db(db_path)
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            replies_path.write_text(json.dumps(safe_replies_status(packet_sha)), encoding="utf-8")
            subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()
            transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()
            replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()
            stale_report = {
                "schema_version": 1,
                "source": "send_legacy_no_progress_nudge.py",
                "generated_at": "2026-01-01T00:00:00Z",
                "mode": "dry_run",
                "decision": "LEGACY_NO_PROGRESS_NUDGE_DRY_RUN",
                "sent_at": "2026-06-05T13:27:02Z",
                "packet": {
                    "sha256": packet_sha,
                    "source": str(packet_path),
                    "size_bytes": len(packet_path.read_bytes()),
                },
                "active_user_count": 2,
                "progress_user_count": 1,
                "reply_user_count": 0,
                "no_progress_candidate_count": 1,
                "selected_user_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "blocked_count": 0,
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
            dry_run_path.write_text(json.dumps(stale_report), encoding="utf-8")
            dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()

            with self.assertRaisesRegex(
                self.module.LegacyNoProgressNudgeError,
                "dry-run report is stale",
            ):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--dry-run-report",
                        str(dry_run_path),
                        "--replies",
                        str(replies_path),
                        "--subscription-payload-status",
                        str(subscription_path),
                        "--transport-usage-status",
                        str(transport_path),
                        "--min-age-minutes",
                        "0",
                        "--cooldown-hours",
                        "0",
                        "--dry-run-max-age-minutes",
                        "1",
                        "--subscription-payload-max-age-minutes",
                        "999999",
                        "--transport-usage-max-age-minutes",
                        "999999",
                        "--replies-max-age-minutes",
                        "999999",
                        "--apply",
                        "--confirm",
                        "SEND_LEGACY_NO_PROGRESS_NUDGE",
                        "--expect-packet-sha256",
                        packet_sha,
                        "--expect-dry-run-sha256",
                        dry_run_sha,
                        "--expect-subscription-payload-sha256",
                        subscription_sha,
                        "--expect-transport-usage-sha256",
                        transport_sha,
                        "--expect-replies-sha256",
                        replies_sha,
                        "--limit",
                        "1",
                        "--bot-token",
                        "test-token",
                    ],
                    sender=lambda _uid, _text: "sent",
                )

    def test_apply_rejects_unsafe_subscription_payload_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            dry_run_path = tmp / "dry-run.json"
            subscription_path = tmp / "subscription.json"
            transport_path = tmp / "transport.json"
            replies_path = tmp / "replies.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            transport_path.write_text(json.dumps(safe_transport_usage_status()), encoding="utf-8")
            create_db(db_path)
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            replies_path.write_text(json.dumps(safe_replies_status(packet_sha)), encoding="utf-8")
            transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()
            replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(dry_run_path),
                        "--min-age-minutes",
                        "0",
                        "--write",
                        "--json",
                    ]
                )
            dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()
            subscription = safe_subscription_payload_status()
            subscription["ok"] = False
            subscription["decision"] = "LIVE_SUBSCRIPTION_PAYLOAD_UNSAFE"
            subscription_path.write_text(json.dumps(subscription), encoding="utf-8")
            subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()

            with self.assertRaisesRegex(
                self.module.LegacyNoProgressNudgeError,
                "subscription payload status is not safe",
            ):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--dry-run-report",
                        str(dry_run_path),
                        "--replies",
                        str(replies_path),
                        "--subscription-payload-status",
                        str(subscription_path),
                        "--transport-usage-status",
                        str(transport_path),
                        "--min-age-minutes",
                        "0",
                        "--cooldown-hours",
                        "0",
                        "--dry-run-max-age-minutes",
                        "999999",
                        "--subscription-payload-max-age-minutes",
                        "999999",
                        "--transport-usage-max-age-minutes",
                        "999999",
                        "--replies-max-age-minutes",
                        "999999",
                        "--apply",
                        "--confirm",
                        "SEND_LEGACY_NO_PROGRESS_NUDGE",
                        "--expect-packet-sha256",
                        packet_sha,
                        "--expect-dry-run-sha256",
                        dry_run_sha,
                        "--expect-subscription-payload-sha256",
                        subscription_sha,
                        "--expect-transport-usage-sha256",
                        transport_sha,
                        "--expect-replies-sha256",
                        replies_sha,
                        "--limit",
                        "1",
                        "--bot-token",
                        "test-token",
                    ],
                    sender=lambda _uid, _text: "sent",
                )

    def test_apply_rejects_stale_transport_usage_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            dry_run_path = tmp / "dry-run.json"
            subscription_path = tmp / "subscription.json"
            transport_path = tmp / "transport.json"
            replies_path = tmp / "replies.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            subscription_path.write_text(json.dumps(safe_subscription_payload_status()), encoding="utf-8")
            create_db(db_path)
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            replies_path.write_text(json.dumps(safe_replies_status(packet_sha)), encoding="utf-8")
            subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()
            replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()
            with redirect_stdout(io.StringIO()):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(dry_run_path),
                        "--min-age-minutes",
                        "0",
                        "--write",
                        "--json",
                    ]
                )
            dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()
            transport = safe_transport_usage_status()
            transport["generated_at"] = "2026-01-01T00:00:00Z"
            transport_path.write_text(json.dumps(transport), encoding="utf-8")
            transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()

            with self.assertRaisesRegex(
                self.module.LegacyNoProgressNudgeError,
                "transport usage status is stale",
            ):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--dry-run-report",
                        str(dry_run_path),
                        "--replies",
                        str(replies_path),
                        "--subscription-payload-status",
                        str(subscription_path),
                        "--transport-usage-status",
                        str(transport_path),
                        "--min-age-minutes",
                        "0",
                        "--cooldown-hours",
                        "0",
                        "--dry-run-max-age-minutes",
                        "999999",
                        "--subscription-payload-max-age-minutes",
                        "999999",
                        "--transport-usage-max-age-minutes",
                        "1",
                        "--replies-max-age-minutes",
                        "999999",
                        "--apply",
                        "--confirm",
                        "SEND_LEGACY_NO_PROGRESS_NUDGE",
                        "--expect-packet-sha256",
                        packet_sha,
                        "--expect-dry-run-sha256",
                        dry_run_sha,
                        "--expect-subscription-payload-sha256",
                        subscription_sha,
                        "--expect-transport-usage-sha256",
                        transport_sha,
                        "--expect-replies-sha256",
                        replies_sha,
                        "--limit",
                        "1",
                        "--bot-token",
                        "test-token",
                    ],
                    sender=lambda _uid, _text: "sent",
                )

    def test_apply_rejects_stale_replies_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            packet_path = tmp / "packet.json"
            send_path = tmp / "send.json"
            db_path = tmp / "ghost.db"
            dry_run_path = tmp / "dry-run.json"
            subscription_path = tmp / "subscription.json"
            transport_path = tmp / "transport.json"
            replies_path = tmp / "replies.json"
            packet_path.write_text(json.dumps(ready_packet()), encoding="utf-8")
            send_path.write_text(json.dumps(message_send()), encoding="utf-8")
            subscription_path.write_text(json.dumps(safe_subscription_payload_status()), encoding="utf-8")
            transport_path.write_text(json.dumps(safe_transport_usage_status()), encoding="utf-8")
            create_db(db_path)
            packet_sha = hashlib.sha256(packet_path.read_bytes()).hexdigest()
            subscription_sha = hashlib.sha256(subscription_path.read_bytes()).hexdigest()
            transport_sha = hashlib.sha256(transport_path.read_bytes()).hexdigest()
            with redirect_stdout(io.StringIO()):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--json-out",
                        str(dry_run_path),
                        "--min-age-minutes",
                        "0",
                        "--write",
                        "--json",
                    ]
                )
            dry_run_sha = hashlib.sha256(dry_run_path.read_bytes()).hexdigest()
            replies = safe_replies_status(packet_sha)
            replies["generated_at"] = "2026-01-01T00:00:00Z"
            replies_path.write_text(json.dumps(replies), encoding="utf-8")
            replies_sha = hashlib.sha256(replies_path.read_bytes()).hexdigest()

            with self.assertRaisesRegex(
                self.module.LegacyNoProgressNudgeError,
                "replies status is stale",
            ):
                self.module.run(
                    [
                        "--packet",
                        str(packet_path),
                        "--message-send",
                        str(send_path),
                        "--db-path",
                        str(db_path),
                        "--dry-run-report",
                        str(dry_run_path),
                        "--replies",
                        str(replies_path),
                        "--subscription-payload-status",
                        str(subscription_path),
                        "--transport-usage-status",
                        str(transport_path),
                        "--min-age-minutes",
                        "0",
                        "--cooldown-hours",
                        "0",
                        "--dry-run-max-age-minutes",
                        "999999",
                        "--subscription-payload-max-age-minutes",
                        "999999",
                        "--transport-usage-max-age-minutes",
                        "999999",
                        "--replies-max-age-minutes",
                        "1",
                        "--apply",
                        "--confirm",
                        "SEND_LEGACY_NO_PROGRESS_NUDGE",
                        "--expect-packet-sha256",
                        packet_sha,
                        "--expect-dry-run-sha256",
                        dry_run_sha,
                        "--expect-subscription-payload-sha256",
                        subscription_sha,
                        "--expect-transport-usage-sha256",
                        transport_sha,
                        "--expect-replies-sha256",
                        replies_sha,
                        "--limit",
                        "1",
                        "--bot-token",
                        "test-token",
                    ],
                    sender=lambda _uid, _text: "sent",
                )


if __name__ == "__main__":
    unittest.main()
