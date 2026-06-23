#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "build_client_compatibility_runtime_summary.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_client_compatibility_runtime_summary", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def matrix_payload() -> dict:
    return {
        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
        "last_updated_utc": "2026-06-02T02:00:00Z",
        "completion_rule": {
            "current_status": "not_complete",
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
                }
            ],
            "evidence_session": {
                "id": "nl-anti-block-2026-06-02",
                "started_at": "2026-06-02T00:00:00Z",
                "required_transport": "xhttp",
                "required_port": 8443,
                "required_for_network_types": [
                    "mobile",
                    "restricted-wifi",
                    "work-wifi",
                ],
                "session_bound_current_passing_checks": 0,
                "session_bound_requirements": {
                    "android_happ_or_hiddify": False,
                    "mobile_network": False,
                    "restricted_or_work_wifi": False,
                },
            },
        },
        "real_client_checks": [
            {
                "client": "v2rayN",
                "network_type": "desktop",
                "transport": "xhttp",
                "port": 8443,
                "status": "pass",
                "symptom": "connected",
            }
        ],
    }


class BuildClientCompatibilityRuntimeSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_profile_status_api_path_can_be_overridden_for_runtime_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            status_api = Path(tmpdir) / "profile_status_api.py"
            status_api.write_text("# runtime status api placeholder\n", encoding="utf-8")
            previous = os.environ.get("PROFILE_STATUS_API_PATH")
            os.environ["PROFILE_STATUS_API_PATH"] = str(status_api)
            try:
                resolved = self.module.profile_status_api_path()
            finally:
                if previous is None:
                    os.environ.pop("PROFILE_STATUS_API_PATH", None)
                else:
                    os.environ["PROFILE_STATUS_API_PATH"] = previous

        self.assertEqual(resolved, status_api)

    def test_build_summary_outputs_runtime_safe_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            matrix = Path(tmpdir) / "matrix.json"
            matrix.write_text(json.dumps(matrix_payload()), encoding="utf-8")

            payload = self.module.build_summary(matrix)
            rendered = json.dumps(payload, ensure_ascii=False)

        self.assertTrue(payload["ok"])
        self.assertFalse(payload["complete"])
        self.assertEqual(payload["real_client_checks"], 1)
        self.assertEqual(payload["passing_real_client_checks"], 1)
        self.assertEqual(payload["next_required_checks"][0]["client"], "Happ")
        self.assertEqual(payload["evidence_session"]["id"], "nl-anti-block-2026-06-02")
        self.assertEqual(payload["evidence_session"]["required_transport"], "xhttp")
        self.assertEqual(payload["evidence_session"]["required_port"], 8443)
        self.assertFalse(payload["privacy"]["raw_real_client_rows_returned"])
        self.assertNotIn("symptom", rendered)
        self.assertNotIn("vless://", rendered)

    def test_cli_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            json_out = tmp / "summary.json"
            md_out = tmp / "summary.md"
            matrix.write_text(json.dumps(matrix_payload()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
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
            json_written = json_out.exists()

        self.assertEqual(rc, 0)
        self.assertTrue(json_written)
        self.assertEqual(payload["decision"], "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED")
        self.assertIn("/client-compatibility", markdown)
        self.assertIn("nl-anti-block-2026-06-02", markdown)
        self.assertIn("xhttp", markdown)
        self.assertNotIn("connected", markdown)

    def test_missing_matrix_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(self.module.RuntimeSummaryError):
                self.module.build_summary(Path(tmpdir) / "missing.json")


if __name__ == "__main__":
    unittest.main()
