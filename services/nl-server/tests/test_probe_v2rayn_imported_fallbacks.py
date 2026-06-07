#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "probe_v2rayn_imported_fallbacks.py"


def load_module():
    spec = importlib.util.spec_from_file_location("probe_v2rayn_imported_fallbacks", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def create_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE ProfileItem (Network varchar, Address varchar, Port integer, Id varchar, "
            "Security varchar, Flow varchar, StreamSecurity varchar, RequestHost varchar, Path varchar, "
            "Sni varchar, Alpn varchar, Fingerprint varchar, PublicKey varchar, ShortId varchar, "
            "SpiderX varchar, ProtoExtra varchar)"
        )
        conn.executemany(
            "INSERT INTO ProfileItem VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "xhttp",
                    "example.test",
                    8443,
                    "11111111-1111-1111-1111-111111111111",
                    "none",
                    "",
                    "tls",
                    "example.test",
                    "/ghost-xhttp",
                    "example.test",
                    "",
                    "chrome",
                    "",
                    "",
                    "",
                    "",
                ),
                (
                    "ws",
                    "example.test",
                    8443,
                    "22222222-2222-2222-2222-222222222222",
                    "none",
                    "",
                    "tls",
                    "example.test",
                    "/ghost-ws",
                    "example.test",
                    "",
                    "chrome",
                    "",
                    "",
                    "",
                    "",
                ),
            ],
        )
        conn.commit()


class ProbeV2rayNImportedFallbacksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_load_profiles_and_build_config_without_secret_in_report_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "db.sqlite"
            create_db(db_path)

            profiles = self.module.load_profiles(db_path)
            config = self.module.build_xray_config(profiles[0], 24080)
            report = {
                "ok": True,
                "results": [{"transport": profiles[0].transport, "port": profiles[0].port}],
                "privacy": {
                    "raw_vpn_uri_stored": False,
                    "raw_uuid_stored": False,
                    "raw_address_stored": False,
                },
            }
            findings = self.module.validate_output(report)

        self.assertEqual([profile.transport for profile in profiles], ["ws", "xhttp"])
        self.assertEqual(config["outbounds"][0]["protocol"], "vless")
        self.assertEqual(config["outbounds"][0]["streamSettings"]["network"], "ws")
        self.assertEqual(findings, [])
        self.assertNotIn("11111111", json.dumps(report))

    def test_output_validator_rejects_uuid_leaks(self) -> None:
        findings = self.module.validate_output(
            {"bad": "11111111-1111-1111-1111-111111111111"}
        )

        self.assertEqual(findings[0]["kind"], "uuid")


if __name__ == "__main__":
    unittest.main()
