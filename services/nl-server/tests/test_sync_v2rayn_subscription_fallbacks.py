#!/usr/bin/env python3
from __future__ import annotations

import base64
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "sync_v2rayn_subscription_fallbacks.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_v2rayn_subscription_fallbacks", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PROFILE_COLUMNS = [
    "IndexId varchar primary key not null",
    "ConfigType integer",
    "ConfigVersion integer",
    "Address varchar",
    "Port integer",
    "Ports varchar",
    "Id varchar",
    "AlterId integer",
    "Security varchar",
    "Network varchar",
    "Remarks varchar",
    "HeaderType varchar",
    "RequestHost varchar",
    "Path varchar",
    "StreamSecurity varchar",
    "AllowInsecure varchar",
    "Subid varchar",
    "IsSub integer",
    "Flow varchar",
    "Sni varchar",
    "Alpn varchar",
    "CoreType integer",
    "PreSocksPort integer",
    "Fingerprint varchar",
    "DisplayLog integer",
    "PublicKey varchar",
    "ShortId varchar",
    "SpiderX varchar",
    "Mldsa65Verify varchar",
    "Extra varchar",
    "MuxEnabled integer",
    "Password varchar",
    "Username varchar",
    "Cert varchar",
    "CertSha varchar",
    "EchConfigList varchar",
    "EchForceQuery varchar",
    "Finalmask varchar",
    "ProtoExtra varchar",
]


def create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(f"CREATE TABLE ProfileItem ({', '.join(PROFILE_COLUMNS)})")
        conn.execute(
            "CREATE TABLE ProfileExItem (IndexId varchar primary key not null, Delay integer, Speed float, Sort integer, Message varchar)"
        )
        conn.execute("CREATE TABLE SubItem (Id varchar primary key not null, Url varchar, Enabled integer)")
        conn.execute(
            "INSERT INTO SubItem VALUES (?, ?, ?)",
            ("sub-redacted", "https://example.invalid/sub/redacted", 1),
        )
        conn.commit()


def encoded_subscription() -> bytes:
    raw = "\n".join(
        [
            "vless://11111111-1111-1111-1111-111111111111@example.test:8443?type=xhttp&security=tls&path=%2Fghost-xhttp#xhttp",
            "vless://22222222-2222-2222-2222-222222222222@example.test:8443?type=ws&security=tls&path=%2Fghost-ws#ws",
            "vless://33333333-3333-3333-3333-333333333333@example.test:443?type=tcp&security=reality#reality",
        ]
    )
    return base64.b64encode(raw.encode())


def fake_fetcher(url: str, timeout: float) -> bytes:
    assert url == "https://example.invalid/sub/redacted"
    return encoded_subscription()


class SyncV2rayNSubscriptionFallbacksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_dry_run_reports_missing_xhttp_and_ws_without_leaking_uri(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "guiNDB.db"
            create_db(db_path)

            report = self.module.run_sync(
                db_path,
                timeout=1,
                apply_to_copy=None,
                confirm="",
                fetcher=fake_fetcher,
            )
            rendered = json.dumps(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "DRY_RUN")
        self.assertEqual(report["plan"]["missing_fallback_profiles"]["counts"]["xhttp"], 1)
        self.assertEqual(report["plan"]["missing_fallback_profiles"]["counts"]["ws"], 1)
        self.assertTrue(report["privacy"]["output_privacy_ok"])
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("example.invalid/sub", rendered)
        self.assertNotIn("11111111", rendered)

    def test_apply_to_copy_inserts_missing_profiles_without_touching_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.db"
            copy = Path(tmpdir) / "copy.db"
            create_db(source)

            report = self.module.run_sync(
                source,
                timeout=1,
                apply_to_copy=copy,
                confirm=self.module.CONFIRM_TOKEN,
                fetcher=fake_fetcher,
            )
            with sqlite3.connect(source) as conn:
                source_count = conn.execute("SELECT COUNT(*) FROM ProfileItem").fetchone()[0]
            with sqlite3.connect(copy) as conn:
                copy_counts = dict(
                    conn.execute(
                        "SELECT lower(Network), COUNT(*) FROM ProfileItem GROUP BY lower(Network)"
                    ).fetchall()
                )

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "APPLIED_TO_COPY")
        self.assertEqual(source_count, 0)
        self.assertEqual(copy_counts["xhttp"], 1)
        self.assertEqual(copy_counts["ws"], 1)
        self.assertEqual(report["remaining_missing_after_copy"]["total"], 0)

    def test_apply_to_copy_requires_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.db"
            copy = Path(tmpdir) / "copy.db"
            create_db(source)

            with self.assertRaises(self.module.SyncError):
                self.module.run_sync(
                    source,
                    timeout=1,
                    apply_to_copy=copy,
                    confirm="",
                    fetcher=fake_fetcher,
                )

    def test_apply_live_requires_live_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.db"
            create_db(source)

            with self.assertRaises(self.module.SyncError):
                self.module.run_sync(
                    source,
                    timeout=1,
                    apply_to_copy=None,
                    apply_live=True,
                    confirm=self.module.CONFIRM_TOKEN,
                    fetcher=fake_fetcher,
                )

    def test_apply_live_backs_up_and_inserts_without_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source.db"
            backup_dir = Path(tmpdir) / "backups"
            create_db(source)

            report = self.module.run_sync(
                source,
                timeout=1,
                apply_to_copy=None,
                apply_live=True,
                backup_dir=backup_dir,
                confirm=self.module.LIVE_CONFIRM_TOKEN,
                fetcher=fake_fetcher,
            )
            backup_path = Path(report["backup_path"])
            with sqlite3.connect(source) as conn:
                live_counts = dict(
                    conn.execute(
                        "SELECT lower(Network), COUNT(*) FROM ProfileItem GROUP BY lower(Network)"
                    ).fetchall()
                )
            with sqlite3.connect(backup_path) as conn:
                backup_count = conn.execute("SELECT COUNT(*) FROM ProfileItem").fetchone()[0]
            rendered = json.dumps(report)
            backup_exists = backup_path.exists()

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "APPLIED_TO_LIVE_DB")
        self.assertTrue(report["applied_to_live_db"])
        self.assertFalse(report["restarted_v2rayn"])
        self.assertTrue(backup_exists)
        self.assertEqual(backup_count, 0)
        self.assertEqual(live_counts["xhttp"], 1)
        self.assertEqual(live_counts["ws"], 1)
        self.assertEqual(report["remaining_missing_after_live"]["total"], 0)
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("11111111", rendered)


if __name__ == "__main__":
    unittest.main()
