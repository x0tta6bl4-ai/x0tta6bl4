#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "diagnose_subscription_404.py"


def load_module() -> types.ModuleType:
    spec = importlib.util.spec_from_file_location("diagnose_subscription_404_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_args(module: types.ModuleType, db_path: Path, *extra: str):
    return module.parse_args(["--db-path", str(db_path), *extra])


def create_db(path: Path) -> None:
    future = (datetime.now() + timedelta(days=365)).isoformat()
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
                subscription_updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE offline_subscriptions (
                claim_code TEXT PRIMARY KEY,
                subscription_token TEXT UNIQUE,
                vpn_uuid TEXT NOT NULL UNIQUE,
                xray_email TEXT NOT NULL,
                plan TEXT NOT NULL,
                days INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                label TEXT,
                delivery_profile TEXT,
                entry_node TEXT,
                issued_at TEXT,
                claimed_at TEXT,
                claimed_by_tg_id INTEGER
            )
            """
        )
        conn.execute(
            """
            INSERT INTO users (
                user_id, username, plan, expires_at, vpn_uuid,
                subscription_token, subscription_updated_at
            )
            VALUES (42, 'alice', 'basic_12m', ?, 'user-uuid', 'user-token', ?)
            """,
            (future, datetime.now().isoformat()),
        )
        conn.execute(
            """
            INSERT INTO offline_subscriptions (
                claim_code, subscription_token, vpn_uuid, xray_email, plan,
                days, expires_at, label
            )
            VALUES (
                'OFFLINE-JWU8V2', 'offline-token', 'offline-uuid',
                'offline-offline-jwu8v2@x0tta6bl4', 'basic_12m',
                365, ?, 'Ghost Access-Offline-JWU8V2'
            )
            """,
            (future,),
        )
        conn.execute(
            """
            INSERT INTO offline_subscriptions (
                claim_code, subscription_token, vpn_uuid, xray_email, plan,
                days, expires_at, label
            )
            VALUES (
                'OFFLINE-BLANK1', '', 'blank-uuid',
                'offline-offline-blank1@x0tta6bl4', 'basic_12m',
                365, ?, 'Ghost Access-Offline-BLANK1'
            )
            """,
            (future,),
        )


class DiagnoseSubscription404Tests(unittest.TestCase):
    def test_found_offline_token_from_subscription_url(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ghost.db"
            create_db(db_path)

            args = make_args(
                module,
                db_path,
                "--subscription-url",
                "https://example.test/sub/offline-token?format=raw",
            )
            report = module.diagnose(args)

        self.assertEqual(report["status"], "found_offline")
        self.assertEqual(report["record_kind"], "offline")
        self.assertEqual(report["expected_http_status"], 200)
        self.assertEqual(report["matched_row"]["claim_code"], "OFFLINE-JWU8V2")
        self.assertEqual(report["matched_row"]["subscription_token"]["prefix"], "offlin")
        self.assertNotIn("offline-token", str(report["matched_row"]))

    def test_unknown_token_reports_404_not_found(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ghost.db"
            create_db(db_path)

            args = make_args(module, db_path, "--token", "missing-token")
            report = module.diagnose(args)

        self.assertEqual(report["status"], "not_found")
        self.assertEqual(report["expected_http_status"], 404)
        self.assertEqual(report["token"]["prefix"], "missin")

    def test_label_selector_finds_probable_offline_record_without_repair(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ghost.db"
            create_db(db_path)

            args = make_args(module, db_path, "--token", "stale-token", "--label-like", "JWU8V")
            report = module.diagnose(args)

        self.assertEqual(report["status"], "offline_selector_match")
        self.assertEqual(report["expected_http_status"], 404)
        self.assertEqual(report["matched_rows"][0]["claim_code"], "OFFLINE-JWU8V2")

    def test_repair_returns_existing_offline_subscription_url_without_rotation(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ghost.db"
            create_db(db_path)

            args = make_args(
                module,
                db_path,
                "--claim-code",
                "JWU8V2",
                "--repair-offline-token",
                "--base-url",
                "https://vpn.example",
            )
            report = module.diagnose(args)

        self.assertEqual(report["status"], "existing_offline_token")
        self.assertFalse(report["rotated"])
        self.assertEqual(report["subscription_url"], "https://vpn.example/sub/offline-token")

    def test_repair_by_visible_label_suffix_returns_existing_subscription_url(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ghost.db"
            create_db(db_path)

            args = make_args(
                module,
                db_path,
                "--label-like",
                "JWU8V",
                "--repair-offline-token",
                "--base-url",
                "https://vpn.example",
            )
            report = module.diagnose(args)

        self.assertEqual(report["status"], "existing_offline_token")
        self.assertFalse(report["rotated"])
        self.assertEqual(report["matched_row"]["claim_code"], "OFFLINE-JWU8V2")
        self.assertEqual(report["subscription_url"], "https://vpn.example/sub/offline-token")

    def test_repair_generates_token_for_blank_offline_subscription(self) -> None:
        module = load_module()
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "ghost.db"
            create_db(db_path)

            with patch.object(module.secrets, "token_urlsafe", return_value="new-token"):
                args = make_args(
                    module,
                    db_path,
                    "--claim-code",
                    "BLANK1",
                    "--repair-offline-token",
                    "--base-url",
                    "https://vpn.example/",
                )
                report = module.diagnose(args)

            with sqlite3.connect(db_path) as conn:
                token = conn.execute(
                    "SELECT subscription_token FROM offline_subscriptions WHERE claim_code = 'OFFLINE-BLANK1'"
                ).fetchone()[0]

        self.assertEqual(report["status"], "repaired_offline")
        self.assertTrue(report["rotated"])
        self.assertEqual(report["subscription_url"], "https://vpn.example/sub/new-token")
        self.assertEqual(token, "new-token")


if __name__ == "__main__":
    unittest.main()
