#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "record_client_compatibility.py"


def load_module():
    spec = importlib.util.spec_from_file_location("record_client_compatibility", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_matrix() -> dict:
    return {
        "matrix_id": "test",
        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
        "real_client_checks": [
            {
                "client": "v2rayN",
                "network_type": "desktop",
                "transport": "reality",
                "port": 443,
                "status": "not_tested",
            }
        ],
        "completion_rule": {"current_status": "not_complete"},
    }


def matrix_with_inventory() -> dict:
    matrix = base_matrix()
    matrix["local_client_inventory"] = {
        "source": "local_v2rayn_gui_db",
        "diagnosis": "subscription_has_xhttp_but_local_v2rayn_db_has_no_xhttp",
        "profile_inventory": {
            "counts": {"reality": 6, "xhttp": 0, "ws": 0, "other": 0},
            "ports": [443, 2083, 39829],
        },
        "subscription_inventory": {
            "aggregate": {
                "counts": {"reality": 2, "xhttp": 1, "ws": 1, "other": 0},
                "ports": [443, 2083, 8443],
            }
        },
    }
    matrix["local_v2rayn_fallback_import_copy_test"] = {
        "decision": "APPLIED_TO_COPY",
        "applied_to_live_db": False,
        "inserted_profiles": {
            "counts": {"reality": 0, "xhttp": 1, "ws": 1, "other": 0},
            "ports": [8443],
            "total": 2,
        },
        "remaining_missing_after_copy": {
            "counts": {"reality": 0, "xhttp": 0, "ws": 0, "other": 0},
            "ports": [],
            "total": 0,
        },
        "copy_inventory_after_import": {
            "counts": {"reality": 6, "xhttp": 1, "ws": 1, "other": 0},
            "ports": [443, 2083, 8443, 39829],
        },
    }
    matrix["local_v2rayn_fallback_import_live"] = {
        "decision": "APPLIED_TO_LIVE_DB",
        "applied_to_live_db": True,
        "restarted_v2rayn": False,
        "backup_path": "/tmp/guiNDB.db.bak-v2rayn-fallbacks",
        "inserted_profiles": {
            "counts": {"reality": 0, "xhttp": 1, "ws": 1, "other": 0},
            "ports": [8443],
            "total": 2,
        },
        "remaining_missing_after_live": {
            "counts": {"reality": 0, "xhttp": 0, "ws": 0, "other": 0},
            "ports": [],
            "total": 0,
        },
    }
    matrix["local_v2rayn_dataplane_probe"] = {
        "checked_at": "2026-06-01T22:52:59Z",
        "ok": True,
        "passed_transports": ["ws", "xhttp"],
        "profile_count": 2,
        "results": [
            {
                "transport": "ws",
                "port": 8443,
                "ok": True,
                "http_code": 204,
                "total_s": 0.723578,
                "error_type": None,
            },
            {
                "transport": "xhttp",
                "port": 8443,
                "ok": True,
                "http_code": 204,
                "total_s": 0.604912,
                "error_type": None,
            },
        ],
        "source": "local_v2rayn_db_profiles_with_v2rayn_bundled_xray",
        "privacy": {
            "output_privacy_ok": True,
            "raw_address_stored": False,
            "raw_path_stored": False,
            "raw_sni_stored": False,
            "raw_uuid_stored": False,
            "raw_vpn_uri_stored": False,
        },
    }
    return matrix


class RecordClientCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_add_check_updates_existing_row_without_raw_secret_material(self) -> None:
        row = self.module.build_check_row(
            checked_at="2026-06-02T01:00:00Z",
            client="v2rayn",
            client_version="7.12",
            network_type="desktop",
            transport="reality",
            port=443,
            result="pass",
            symptom="connected normal https sites",
        )

        updated = self.module.add_or_update_check(base_matrix(), row)

        [check] = updated["real_client_checks"]
        self.assertEqual(check["client"], "v2rayN")
        self.assertEqual(check["status"], "pass")
        self.assertFalse(check["raw_secret_material_stored"])
        self.assertEqual(updated["completion_rule"]["evidence"]["desktop_v2rayn"], True)
        self.assertIn("android_happ_or_hiddify", updated["completion_rule"]["missing_requirements"])
        self.assertIn("next_required_checks", updated["completion_rule"])
        self.assertEqual(updated["completion_rule"]["current_status"], "not_complete")

    def test_rejects_vpn_uri_uuid_ip_and_email_in_symptom(self) -> None:
        unsafe_values = [
            "vless://secret",
            "sub path /sub/abcdef1234567890",
            "uuid 123e4567-e89b-12d3-a456-426614174000",
            "ip 203.0.113.10",
            "email user@example.test",
        ]
        for symptom in unsafe_values:
            with self.subTest(symptom=symptom):
                with self.assertRaises(self.module.CompatibilityError):
                    self.module.build_check_row(
                        checked_at="2026-06-02T01:00:00Z",
                        client="Happ",
                        client_version="unknown",
                        network_type="mobile",
                        transport="ws",
                        port=8443,
                        result="pass",
                        symptom=symptom,
                    )

    def test_completion_requires_desktop_android_mobile_and_work_wifi_evidence(self) -> None:
        matrix = base_matrix()
        rows = [
            ("v2rayN", "desktop", "reality", 443),
            ("Hiddify", "mobile", "reality", 443),
            ("any", "work-wifi", "reality", 443),
        ]
        for client, network, transport, port in rows:
            row = self.module.build_check_row(
                checked_at="2026-06-02T01:00:00Z",
                client=client,
                client_version="unknown",
                network_type=network,
                transport=transport,
                port=port,
                result="pass",
                symptom="connected",
            )
            matrix = self.module.add_or_update_check(matrix, row)

        self.assertEqual(matrix["decision"], "CLIENT_MATRIX_COMPLETE")
        self.assertEqual(matrix["completion_rule"]["current_status"], "complete")

    def test_happ_hiddify_alias_counts_as_android_mobile_evidence(self) -> None:
        row = self.module.build_check_row(
            checked_at="2026-06-02T01:00:00Z",
            client="Happ/Hiddify",
            client_version="unknown",
            network_type="mobile",
            transport="reality",
            port=443,
            result="pass",
            symptom="connected",
        )
        matrix = self.module.add_or_update_check(base_matrix(), row)

        self.assertEqual(row["client"], "Happ")
        self.assertEqual(row["evidence_session_id"], "nl-anti-block-2026-06-02")
        self.assertTrue(matrix["completion_rule"]["evidence"]["android_happ_or_hiddify"])
        self.assertTrue(matrix["completion_rule"]["evidence"]["mobile_network"])

    def test_mobile_pass_without_current_session_does_not_close_mobile_requirements(self) -> None:
        matrix = base_matrix()
        matrix["real_client_checks"].append(
            {
                "checked_at": "2026-05-01T01:00:00Z",
                "client": "Happ",
                "client_version": "unknown",
                "network_type": "mobile",
                "transport": "xhttp",
                "port": 8443,
                "status": "pass",
                "symptom": "old connected report",
                "raw_secret_material_stored": False,
            }
        )

        self.module.refresh_completion(matrix)

        evidence = matrix["completion_rule"]["evidence"]
        self.assertFalse(evidence["android_happ_or_hiddify"])
        self.assertFalse(evidence["mobile_network"])
        self.assertIn("android_happ_or_hiddify", matrix["completion_rule"]["missing_requirements"])
        self.assertEqual(
            matrix["completion_rule"]["evidence_session"]["id"],
            "nl-anti-block-2026-06-02",
        )

    def test_current_session_mobile_pass_before_session_start_is_rejected(self) -> None:
        with self.assertRaises(self.module.CompatibilityError):
            self.module.build_check_row(
                checked_at="2026-06-01T23:59:59Z",
                client="Happ",
                client_version="unknown",
                network_type="mobile",
                transport="xhttp",
                port=8443,
                result="pass",
                symptom="connected",
                evidence_session_id="nl-anti-block-2026-06-02",
            )

    def test_current_session_mobile_pass_requires_reality_443(self) -> None:
        for transport, port in (("ws", 8443), ("xhttp", 443), ("xhttp", 8443), ("reality", 8443)):
            with self.subTest(transport=transport, port=port):
                with self.assertRaises(self.module.CompatibilityError):
                    self.module.build_check_row(
                        checked_at="2026-06-02T01:00:00Z",
                        client="Happ",
                        client_version="unknown",
                        network_type="mobile",
                        transport=transport,
                        port=port,
                        result="pass",
                        symptom="connected",
                        evidence_session_id="nl-anti-block-2026-06-02",
                    )

    def test_cli_validate_reports_partial_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix_path = Path(tmpdir) / "matrix.json"
            matrix_path.write_text(json.dumps(base_matrix()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(["--matrix", str(matrix_path), "--validate", "--json"])
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["complete"])
        self.assertIn("desktop_v2rayn", payload["missing_requirements"])
        self.assertGreaterEqual(len(payload["next_required_checks"]), 1)

    def test_render_markdown_contains_completion_and_real_client_rows(self) -> None:
        row = self.module.build_check_row(
            checked_at="2026-06-02T01:00:00Z",
            client="v2rayN",
            client_version="7.12",
            network_type="desktop",
            transport="reality",
            port=443,
            result="pass",
            symptom="connected",
        )
        matrix = self.module.add_or_update_check(base_matrix(), row)

        markdown = self.module.render_markdown(matrix)

        self.assertIn("CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED", markdown)
        self.assertIn("| Desktop v2rayN | true |", markdown)
        self.assertIn("## Next Required Checks", markdown)
        self.assertIn("evidence_session_id=nl-anti-block-2026-06-02", markdown)
        self.assertIn("Android Happ/Hiddify", markdown)
        self.assertIn("| Android Happ/Hiddify | Happ | mobile | reality | 443 |", markdown)
        self.assertIn("| v2rayN | 7.12 | desktop | reality | 443 | pass |", markdown)
        self.assertNotIn("vless://", markdown)

    def test_render_markdown_includes_local_client_inventory_when_present(self) -> None:
        matrix = matrix_with_inventory()

        markdown = self.module.render_markdown(matrix)

        self.assertIn("## Local Client Inventory", markdown)
        self.assertIn("subscription_has_xhttp_but_local_v2rayn_db_has_no_xhttp", markdown)
        self.assertIn("enabled_subscription_fetch", markdown)
        self.assertIn("## Local Import Copy-Test", markdown)
        self.assertIn("APPLIED_TO_COPY", markdown)
        self.assertIn("## Local Live Import", markdown)
        self.assertIn("APPLIED_TO_LIVE_DB", markdown)
        self.assertIn("## Local Dataplane Probe", markdown)
        self.assertIn("local_v2rayn_db_profiles_with_v2rayn_bundled_xray", markdown)
        self.assertIn("| ws | 8443 | 204 |", markdown)
        self.assertIn("| xhttp | 8443 | 204 |", markdown)

    def test_cli_add_check_writes_json_and_synced_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix_path = Path(tmpdir) / "matrix.json"
            markdown_path = Path(tmpdir) / "matrix.md"
            matrix_path.write_text(json.dumps(base_matrix()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix_path),
                        "--markdown",
                        str(markdown_path),
                        "--add-check",
                        "--checked-at",
                        "2026-06-02T01:00:00Z",
                        "--client",
                        "v2rayN",
                        "--client-version",
                        "7.12",
                        "--network-type",
                        "windows",
                        "--transport",
                        "reality",
                        "--port",
                        "443",
                        "--result",
                        "pass",
                        "--symptom",
                        "connected",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            updated = json.loads(matrix_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertEqual(updated["real_client_checks"][0]["status"], "pass")
        self.assertIn("| v2rayN | 7.12 | desktop | reality | 443 | pass |", markdown)

    def test_cli_sync_writes_completion_metadata_without_adding_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix_path = Path(tmpdir) / "matrix.json"
            markdown_path = Path(tmpdir) / "matrix.md"
            matrix_path.write_text(json.dumps(base_matrix()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix_path),
                        "--markdown",
                        str(markdown_path),
                        "--sync",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            updated = json.loads(matrix_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["complete"])
        self.assertIn("missing_requirements", updated["completion_rule"])
        self.assertIn("Next Required Checks", markdown)


if __name__ == "__main__":
    unittest.main()
