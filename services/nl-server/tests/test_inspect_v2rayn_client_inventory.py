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
MODULE_PATH = ROOT / "ghost-access" / "inspect_v2rayn_client_inventory.py"


def load_module():
    spec = importlib.util.spec_from_file_location("inspect_v2rayn_client_inventory", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE ProfileItem (Network varchar, Port INTEGER, StreamSecurity varchar, IsSub INTEGER)"
        )
        conn.execute("CREATE TABLE SubItem (Url varchar, Enabled INTEGER)")
        conn.executemany(
            "INSERT INTO ProfileItem VALUES (?, ?, ?, ?)",
            [
                ("tcp", 443, "reality", 1),
                ("tcp", 2083, "reality", 1),
                ("tcp", 39829, "reality", 0),
            ],
        )
        conn.execute("INSERT INTO SubItem VALUES (?, ?)", ("https://example.invalid/sub/redacted", 1))
        conn.commit()


class InspectV2rayNClientInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_parse_subscription_payload_counts_fallback_without_leaking_uri(self) -> None:
        payload = "\n".join(
            [
                "vless://11111111-1111-1111-1111-111111111111@example.test:8443?type=xhttp&security=tls#xhttp",
                "vless://22222222-2222-2222-2222-222222222222@example.test:8443?type=ws&security=tls#ws",
                "vless://33333333-3333-3333-3333-333333333333@example.test:443?type=tcp&security=reality#reality",
            ]
        )

        summary = self.module.parse_subscription_payload(payload)
        rendered = json.dumps(summary)

        self.assertEqual(summary["counts"]["xhttp"], 1)
        self.assertEqual(summary["counts"]["ws"], 1)
        self.assertEqual(summary["counts"]["reality"], 1)
        self.assertEqual(summary["ports"], [443, 8443])
        self.assertNotIn("11111111", rendered)
        self.assertNotIn("example.test", rendered)

    def test_build_report_detects_subscription_fallback_missing_from_local_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "guiNDB.db"
            create_db(db_path)
            raw_subscription = "\n".join(
                [
                    "vless://11111111-1111-1111-1111-111111111111@example.test:8443?type=xhttp&security=tls#xhttp",
                    "vless://22222222-2222-2222-2222-222222222222@example.test:8443?type=ws&security=tls#ws",
                    "vless://33333333-3333-3333-3333-333333333333@example.test:443?type=tcp&security=reality#reality",
                ]
            )
            encoded = base64.b64encode(raw_subscription.encode()).decode()

            def fake_fetcher(url: str, timeout: float) -> bytes:
                assert url == "https://example.invalid/sub/redacted"
                return encoded.encode()

            report = self.module.build_report(db_path, fetcher=fake_fetcher)
            rendered = json.dumps(report)

        self.assertTrue(report["ok"])
        self.assertEqual(report["profile_inventory"]["counts"]["reality"], 3)
        self.assertEqual(report["profile_inventory"]["counts"]["xhttp"], 0)
        self.assertEqual(report["subscription_inventory"]["aggregate"]["counts"]["xhttp"], 1)
        self.assertEqual(
            report["diagnosis"],
            "subscription_has_xhttp_but_local_v2rayn_db_has_no_xhttp",
        )
        self.assertTrue(report["privacy"]["output_privacy_ok"])
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("example.invalid/sub", rendered)
        self.assertNotIn("11111111", rendered)


if __name__ == "__main__":
    unittest.main()
