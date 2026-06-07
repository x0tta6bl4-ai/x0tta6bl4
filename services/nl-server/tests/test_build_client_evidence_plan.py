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
MODULE_PATH = ROOT / "ghost-access" / "build_client_evidence_plan.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_client_evidence_plan", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def partial_matrix() -> dict:
    return {
        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
        "completion_rule": {
            "evidence": {
                "desktop_v2rayn": True,
                "android_happ_or_hiddify": False,
                "mobile_network": False,
                "restricted_or_work_wifi": False,
            },
            "missing_requirements": [
                "android_happ_or_hiddify",
                "mobile_network",
                "restricted_or_work_wifi",
            ],
            "next_required_checks": [
                {
                    "requirement": "android_happ_or_hiddify",
                    "client": "Happ",
                    "network_type": "mobile",
                    "transport": "xhttp",
                    "port": 8443,
                },
                {
                    "requirement": "restricted_or_work_wifi",
                    "client": "any",
                    "network_type": "work-wifi",
                    "transport": "xhttp",
                    "port": 8443,
                },
            ],
        },
    }


class BuildClientEvidencePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_inspect_adb_counts_devices_without_storing_serials(self) -> None:
        def runner(args):
            self.assertEqual(list(args), ["adb", "devices", "-l"])
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=(
                    "List of devices attached\n"
                    "ABCDEF012345 device product:test model:Pixel\n"
                    "ZYX987 unauthorized usb:1-2\n"
                ),
                stderr="",
            )

        payload = self.module.inspect_adb(runner)

        self.assertTrue(payload["adb_available"])
        self.assertEqual(payload["connected_device_count"], 1)
        self.assertEqual(payload["device_state_counts"], {"device": 1, "unauthorized": 1})
        self.assertFalse(payload["raw_serials_stored"])
        self.assertNotIn("ABCDEF012345", json.dumps(payload))

    def test_build_plan_maps_missing_requirements_to_safe_tasks(self) -> None:
        plan = self.module.build_plan(
            partial_matrix(),
            adb={
                "adb_available": True,
                "connected_device_count": 0,
                "device_state_counts": {},
                "raw_serials_stored": False,
            },
            android_adb_probe={
                "decision": "ANDROID_DEVICE_NOT_CONNECTED",
                "ok": False,
                "vpn_runtime": {"vpn_transport_seen": False},
                "dataplane": {"ok": False, "http_code": 0, "tool": "not_run"},
            },
            generated_at="2026-06-02T01:00:00Z",
        )

        self.assertEqual(plan["decision"], "CLIENT_EVIDENCE_REQUIRED")
        self.assertEqual(
            plan["missing_requirements"],
            ["android_happ_or_hiddify", "mobile_network", "restricted_or_work_wifi"],
        )
        self.assertEqual(
            [task["requirement"] for task in plan["required_tasks"]],
            ["android_happ_or_hiddify", "restricted_or_work_wifi", "mobile_network"],
        )
        commands = "\n".join(
            task["safe_recorder_command_template"] for task in plan["required_tasks"]
        )
        adb_commands = "\n".join(
            task["android_adb_probe_record_command_template"] for task in plan["required_tasks"]
        )
        remote_commands = "\n".join(
            task["remote_client_evidence_record_command_template"]
            for task in plan["required_tasks"]
        )
        rendered = json.dumps(plan, ensure_ascii=False)
        self.assertIn('--client "Happ"', commands)
        self.assertIn("--network-type mobile", commands)
        self.assertIn("--network-type work-wifi", commands)
        self.assertIn("probe_android_adb_vpn.py --write --json --record-matrix", adb_commands)
        self.assertIn('--client "Happ"', adb_commands)
        self.assertIn("record_remote_client_evidence.py --write --record-matrix", remote_commands)
        self.assertIn("--evidence-source remote_user_report", remote_commands)
        self.assertIn("--reporter-label remote-city-user", remote_commands)
        self.assertNotIn("<UTC_ISO_TIME>", rendered)
        self.assertNotIn("--checked-at", remote_commands)
        self.assertNotIn("--checked-at", commands)
        self.assertEqual(
            plan["required_tasks"][0]["checked_at_policy"],
            "generated commands omit --checked-at so the recorder stores current UTC; "
            "append --checked-at <ISO8601_Z> only when recording a delayed report",
        )
        self.assertEqual(plan["android_adb_probe"]["decision"], "ANDROID_DEVICE_NOT_CONNECTED")
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("/sub/", rendered)
        self.assertTrue(plan["privacy"]["output_privacy_ok"])
        self.assertEqual(self.module.validate_output(plan), [])

    def test_write_json_and_markdown_outputs_safe_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix_path = Path(tmpdir) / "matrix.json"
            json_out = Path(tmpdir) / "plan.json"
            md_out = Path(tmpdir) / "plan.md"
            matrix_path.write_text(json.dumps(partial_matrix()), encoding="utf-8")

            rc = self.module.run(
                [
                    "--matrix",
                    str(matrix_path),
                    "--json-out",
                    str(json_out),
                    "--markdown-out",
                    str(md_out),
                    "--write",
                ]
            )
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            markdown = md_out.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "CLIENT_EVIDENCE_REQUIRED")
        self.assertIn("## Safe Recorder Commands", markdown)
        self.assertIn("Remote client evidence command", markdown)
        self.assertIn("Android ADB auto-record command", markdown)
        self.assertIn("Do not store VPN links", markdown)
        self.assertNotIn("vless://", markdown)

    def test_markdown_includes_latest_android_adb_probe_when_present(self) -> None:
        plan = self.module.build_plan(
            partial_matrix(),
            adb={
                "adb_available": True,
                "connected_device_count": 0,
                "device_state_counts": {},
                "raw_serials_stored": False,
            },
            android_adb_probe={
                "decision": "ANDROID_ADB_VPN_DATAPLANE_PASS",
                "ok": True,
                "vpn_runtime": {"vpn_transport_seen": True},
                "dataplane": {"ok": True, "http_code": 204, "tool": "curl"},
            },
            generated_at="2026-06-02T01:00:00Z",
        )

        markdown = self.module.render_markdown(plan)

        self.assertIn("## Latest Android ADB Probe", markdown)
        self.assertIn("ANDROID_ADB_VPN_DATAPLANE_PASS", markdown)
        self.assertIn("| ANDROID_ADB_VPN_DATAPLANE_PASS | true | true | true | 204 | curl |", markdown)


if __name__ == "__main__":
    unittest.main()
