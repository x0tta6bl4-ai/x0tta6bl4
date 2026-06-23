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
MODULE_PATH = ROOT / "ghost-access" / "build_remote_client_evidence_request_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "build_remote_client_evidence_request_packet", MODULE_PATH
    )
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
                    "transport": "reality",
                    "port": 443,
                },
                {
                    "requirement": "restricted_or_work_wifi",
                    "client": "any",
                    "network_type": "work-wifi",
                    "transport": "reality",
                    "port": 443,
                },
            ],
        },
    }


class BuildRemoteClientEvidenceRequestPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_packet_groups_mobile_android_requirements_into_one_request(self) -> None:
        packet = self.module.build_packet(
            partial_matrix(),
            android_adb_probe={"decision": "ANDROID_DEVICE_NOT_CONNECTED"},
            generated_at="2026-06-02T03:00:00Z",
        )

        self.assertEqual(packet["decision"], "REMOTE_CLIENT_EVIDENCE_REQUEST_READY")
        self.assertEqual(packet["minimum_reports_required"], 2)
        self.assertEqual(packet["request_count"], 2)
        mobile = next(row for row in packet["requests"] if row["network_type"] == "mobile")
        self.assertEqual(mobile["transport"], "reality")
        self.assertEqual(mobile["port"], 443)
        self.assertEqual(
            mobile["covers_requirements"],
            ["android_happ_or_hiddify", "mobile_network"],
        )
        self.assertIn("pass connected", mobile["tester_message"])
        self.assertEqual(mobile["evidence_session_id"], "nl-anti-block-2026-06-02")
        self.assertEqual(mobile["evidence_session_started_at"], "2026-06-02T00:00:00Z")
        self.assertIn("Do not send profile links", mobile["tester_message"])
        self.assertEqual(mobile["operator_record_pass_command"], "")
        self.assertEqual(mobile["operator_record_fail_command"], "")
        self.assertIn(
            "Direct record_remote_client_evidence.py --write commands are disabled",
            mobile["operator_record_command_policy"],
        )
        self.assertIn(
            "record_remote_client_evidence_reply.py",
            mobile["operator_reply_record_pass_command"],
        )
        self.assertIn("--refresh-artifacts", mobile["operator_reply_record_pass_command"])
        self.assertIn("--reply-stdin", mobile["operator_reply_record_pass_command"])
        self.assertIn(
            "--expect-request-packet-sha256",
            mobile["operator_reply_record_pass_command"],
        )
        self.assertIn("sha256sum", mobile["operator_reply_record_pass_command"])
        self.assertIn('printf \'%s\\n\' "pass connected"', mobile["operator_reply_record_pass_command"])
        self.assertNotIn("--checked-at", mobile["operator_reply_record_pass_command"])
        self.assertIn("--reply-stdin", mobile["operator_reply_validate_pass_command"])
        self.assertIn(
            "--expect-request-packet-sha256",
            mobile["operator_reply_validate_pass_command"],
        )
        self.assertIn("sha256sum", mobile["operator_reply_validate_pass_command"])
        self.assertNotIn("--write", mobile["operator_reply_validate_pass_command"])
        self.assertNotIn("--record-matrix", mobile["operator_reply_validate_pass_command"])
        self.assertNotIn("--refresh-artifacts", mobile["operator_reply_validate_pass_command"])
        self.assertNotIn("<UTC_ISO_TIME>", json.dumps(packet, ensure_ascii=False))
        self.assertEqual(
            packet["checked_at_policy"],
            "generated commands omit --checked-at so the recorder stores current UTC; "
            "append --checked-at <ISO8601_Z> only when recording a delayed report",
        )
        self.assertIn("older than 24 hours", packet["request_freshness_policy"])
        self.assertIn(
            "--expect-request-packet-sha256",
            packet["request_packet_hash_binding_policy"],
        )
        self.assertIn("source_sha256", packet["request_packet_hash_binding_policy"])
        self.assertIn("sha256sum", packet["request_packet_hash_binding_policy"])
        self.assertEqual(
            mobile["safe_reply_options"],
            ["pass connected", "fail timeout", "fail import", "fail no-internet"],
        )
        for request in packet["requests"]:
            self.assertEqual(request["transport"], "reality")
            self.assertEqual(request["port"], 443)
            self.assertEqual(request["operator_record_pass_command"], "")
            self.assertEqual(request["operator_record_fail_command"], "")
            self.assertIn("operator_reply_record", request["operator_record_command_policy"])
        self.assertIn(
            "Direct record_remote_client_evidence.py --write commands are disabled",
            packet["direct_record_commands_policy"],
        )
        rendered = json.dumps(packet, ensure_ascii=False)
        self.assertNotIn("vless://", rendered)
        self.assertNotIn("/sub/", rendered)
        self.assertEqual(self.module.validate_output(packet), [])

    def test_completed_matrix_has_no_requests(self) -> None:
        matrix = partial_matrix()
        matrix["completion_rule"]["missing_requirements"] = []
        matrix["completion_rule"]["next_required_checks"] = []

        packet = self.module.build_packet(matrix, generated_at="2026-06-02T03:00:00Z")

        self.assertEqual(packet["decision"], "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED")
        self.assertEqual(packet["request_count"], 0)
        self.assertEqual(packet["minimum_reports_required"], 0)

    def test_cli_writes_privacy_safe_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            android = tmp / "android.json"
            json_out = tmp / "request.json"
            md_out = tmp / "request.md"
            matrix.write_text(json.dumps(partial_matrix()), encoding="utf-8")
            android.write_text(
                json.dumps({"decision": "ANDROID_DEVICE_NOT_CONNECTED"}),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--android-adb-probe",
                        str(android),
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
        self.assertEqual(payload["decision"], "REMOTE_CLIENT_EVIDENCE_REQUEST_READY")
        self.assertIn("REMOTE_CLIENT_EVIDENCE_REQUEST_READY", markdown)
        self.assertIn("Freshness policy", markdown)
        self.assertIn("Request packet hash binding policy", markdown)
        self.assertIn("--expect-request-packet-sha256", markdown)
        self.assertIn("Direct record command policy", markdown)
        self.assertIn("Direct record_remote_client_evidence.py --write commands are disabled", markdown)
        self.assertIn("Record pass from short reply", markdown)
        self.assertIn("Validate pass reply without writing", markdown)
        self.assertIn("record_remote_client_evidence_reply.py", markdown)
        self.assertNotIn("record_remote_client_evidence.py --write --record-matrix", markdown)
        self.assertNotIn("https://", markdown)
        self.assertNotIn("@", markdown)


if __name__ == "__main__":
    unittest.main()
