#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "probe_android_adb_vpn.py"
RECORDER_PATH = ROOT / "ghost-access" / "record_client_compatibility.py"


def load_module():
    spec = importlib.util.spec_from_file_location("probe_android_adb_vpn", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProbeAndroidAdbVpnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_no_device_report_stores_no_serials(self) -> None:
        def runner(args):
            self.assertEqual(list(args), ["adb", "devices", "-l"])
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="List of devices attached\n\n",
                stderr="",
            )

        report = self.module.build_report(
            runner=runner,
            checked_at="2026-06-02T01:00:00Z",
        )

        self.assertEqual(report["decision"], "ANDROID_DEVICE_NOT_CONNECTED")
        self.assertFalse(report["ok"])
        self.assertEqual(report["adb"]["connected_device_count"], 0)
        self.assertFalse(report["adb"]["raw_serials_stored"])
        self.assertEqual(self.module.validate_output(report), [])

    def test_connected_device_with_vpn_and_http_204_passes(self) -> None:
        calls: list[list[str]] = []

        def runner(args):
            calls.append(list(args))
            if list(args) == ["adb", "devices", "-l"]:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="List of devices attached\nABCDEF012345 device product:test\n",
                    stderr="",
                )
            command = " ".join(args)
            if "dumpsys connectivity" in command:
                return subprocess.CompletedProcess(args, 0, stdout="TRANSPORT_VPN\n", stderr="")
            if "generate_204" in command:
                return subprocess.CompletedProcess(args, 0, stdout="code=204 tool=curl", stderr="")
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

        report = self.module.build_report(
            runner=runner,
            checked_at="2026-06-02T01:00:00Z",
        )
        rendered = json.dumps(report, ensure_ascii=False)

        self.assertEqual(report["decision"], "ANDROID_ADB_VPN_DATAPLANE_PASS")
        self.assertTrue(report["ok"])
        self.assertEqual(report["adb"]["connected_device_count"], 1)
        self.assertTrue(report["vpn_runtime"]["vpn_transport_seen"])
        self.assertEqual(report["dataplane"]["http_code"], 204)
        self.assertNotIn("ABCDEF012345", rendered)
        self.assertEqual(self.module.validate_output(report), [])

    def test_output_validator_rejects_secret_patterns(self) -> None:
        findings = self.module.validate_output(
            {
                "bad_uri": "vless://secret",
                "bad_uuid": "11111111-1111-1111-1111-111111111111",
            }
        )

        self.assertEqual({item["kind"] for item in findings}, {"vpn_uri", "uuid"})

    def test_record_probe_pass_updates_client_matrix(self) -> None:
        matrix = {
            "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
            "real_client_checks": [
                {
                    "client": "Happ",
                    "network_type": "mobile",
                    "transport": "reality",
                    "port": 443,
                    "status": "not_tested",
                },
                {
                    "client": "v2rayN",
                    "network_type": "desktop",
                    "transport": "reality",
                    "port": 443,
                    "status": "pass",
                    "checked_at": "2026-06-02T01:00:00Z",
                    "client_version": "unknown",
                    "symptom": "connected",
                    "raw_secret_material_stored": False,
                },
            ],
            "completion_rule": {"current_status": "not_complete"},
        }
        report = {
            "checked_at": "2026-06-02T01:00:00Z",
            "decision": "ANDROID_ADB_VPN_DATAPLANE_PASS",
            "ok": True,
            "vpn_runtime": {"vpn_transport_seen": True},
            "dataplane": {"http_code": 204},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix_path = Path(tmpdir) / "matrix.json"
            markdown_path = Path(tmpdir) / "matrix.md"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")

            recording = self.module.record_probe_to_matrix(
                report,
                recorder_path=RECORDER_PATH,
                matrix_path=matrix_path,
                markdown_path=markdown_path,
                client="Happ",
                client_version="unknown",
                network_type="mobile",
                transport="reality",
                port=443,
                record_fail=False,
            )
            updated = json.loads(matrix_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertTrue(recording["recorded"])
        self.assertEqual(recording["result"], "pass")
        self.assertTrue(updated["completion_rule"]["evidence"]["android_happ_or_hiddify"])
        self.assertTrue(updated["completion_rule"]["evidence"]["mobile_network"])
        self.assertIn("| Happ | unknown | mobile | reality | 443 | pass |", markdown)

    def test_record_probe_fail_is_skipped_without_explicit_fail_flag(self) -> None:
        report = {
            "checked_at": "2026-06-02T01:00:00Z",
            "decision": "ANDROID_DEVICE_NOT_CONNECTED",
            "ok": False,
            "vpn_runtime": {"vpn_transport_seen": False},
            "dataplane": {"http_code": 0},
        }

        recording = self.module.record_probe_to_matrix(
            report,
            recorder_path=RECORDER_PATH,
            matrix_path=Path("/tmp/unused-matrix.json"),
            markdown_path=None,
            client="Happ",
            client_version="unknown",
            network_type="mobile",
            transport="reality",
            port=443,
            record_fail=False,
        )

        self.assertFalse(recording["attempted"])
        self.assertFalse(recording["recorded"])
        self.assertEqual(recording["would_result"], "fail")

    def test_cli_write_outputs_json_and_markdown(self) -> None:
        def runner(args):
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="List of devices attached\n\n",
                stderr="",
            )

        original = self.module.default_runner
        self.module.default_runner = runner
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                json_out = Path(tmpdir) / "probe.json"
                md_out = Path(tmpdir) / "probe.md"
                rc = self.module.run(
                    [
                        "--json-out",
                        str(json_out),
                        "--markdown-out",
                        str(md_out),
                        "--write",
                    ]
                )
                payload = json.loads(json_out.read_text(encoding="utf-8"))
                markdown = md_out.read_text(encoding="utf-8")
        finally:
            self.module.default_runner = original

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "ANDROID_DEVICE_NOT_CONNECTED")
        self.assertEqual(payload["matrix_recording"]["reason"], "record_matrix_not_requested")
        self.assertIn("## Dataplane", markdown)
        self.assertIn("## Matrix Recording", markdown)
        self.assertIn("record_matrix_not_requested", markdown)
        self.assertNotIn("vless://", markdown)


if __name__ == "__main__":
    unittest.main()
