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
MODULE_PATH = ROOT / "ghost-access" / "record_remote_client_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("record_remote_client_evidence", MODULE_PATH)
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
                "checked_at": "2026-06-02T01:00:00Z",
                "client": "v2rayN",
                "client_version": "7.12",
                "network_type": "desktop",
                "transport": "reality",
                "port": 443,
                "status": "pass",
                "symptom": "connected",
                "raw_secret_material_stored": False,
            }
        ],
        "completion_rule": {"current_status": "not_complete"},
    }


class RecordRemoteClientEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.recorder = self.module.load_recorder()

    def test_ready_report_is_privacy_safe_without_candidate(self) -> None:
        report = self.module.build_report(
            recorder=self.recorder,
            matrix=base_matrix(),
            candidate=None,
            matrix_after=None,
            record_matrix=False,
            wrote_matrix=False,
            generated_at="2026-06-02T02:00:00Z",
        )

        self.assertEqual(report["decision"], "REMOTE_CLIENT_EVIDENCE_INTAKE_READY")
        self.assertFalse(report["matrix_updated"])
        self.assertTrue(report["privacy"]["output_privacy_ok"])
        self.assertIn("record_remote_client_evidence.py", report["safe_remote_record_command_template"])
        self.assertEqual(self.module.validate_safe_payload(report, self.recorder), [])

    def test_mobile_happ_pass_marks_android_and_mobile_requirements(self) -> None:
        candidate = self.module.build_candidate(
            recorder=self.recorder,
            checked_at="2026-06-02T02:00:00Z",
            evidence_source="remote_user_report",
            reporter_label="remote-city-user",
            client="Happ",
            client_version="unknown",
            network_type="mobile",
            transport="reality",
            port=443,
            result="pass",
            symptom="connected normal HTTPS sites",
        )

        updated = self.recorder.add_or_update_check(base_matrix(), candidate)

        evidence = updated["completion_rule"]["evidence"]
        self.assertTrue(evidence["desktop_v2rayn"])
        self.assertTrue(evidence["android_happ_or_hiddify"])
        self.assertTrue(evidence["mobile_network"])
        self.assertFalse(evidence["restricted_or_work_wifi"])
        self.assertEqual(candidate["evidence_source"], "remote_user_report")
        self.assertEqual(candidate["evidence_session_id"], "nl-anti-block-2026-06-02")
        self.assertFalse(candidate["raw_reporter_identifier_stored"])

    def test_work_wifi_pass_marks_restricted_or_work_requirement(self) -> None:
        candidate = self.module.build_candidate(
            recorder=self.recorder,
            checked_at="2026-06-02T02:00:00Z",
            evidence_source="support_call_summary",
            reporter_label="workplace-user",
            client="any",
            client_version="unknown",
            network_type="work-wifi",
            transport="reality",
            port=443,
            result="pass",
            symptom="connected",
        )

        updated = self.recorder.add_or_update_check(base_matrix(), candidate)

        self.assertTrue(updated["completion_rule"]["evidence"]["restricted_or_work_wifi"])

    def test_rejects_remote_secret_patterns(self) -> None:
        unsafe_values = [
            "vless://secret",
            "subscription /sub/abcdef1234567890",
            "uuid 123e4567-e89b-12d3-a456-426614174000",
            "ip 203.0.113.10",
            "email user@example.test",
            "handle @someuser",
            "phone +7 999 111 22 33",
            "url https://example.test/path",
        ]
        for symptom in unsafe_values:
            with self.subTest(symptom=symptom):
                with self.assertRaises(self.module.RemoteEvidenceError):
                    self.module.build_candidate(
                        recorder=self.recorder,
                        checked_at="2026-06-02T02:00:00Z",
                        evidence_source="remote_user_report",
                        reporter_label="friend",
                        client="Happ",
                        client_version="unknown",
                        network_type="mobile",
                        transport="reality",
                        port=443,
                        result="pass",
                        symptom=symptom,
                    )

    def test_rejects_freeform_reporter_identifier(self) -> None:
        with self.assertRaises(self.module.RemoteEvidenceError):
            self.module.build_candidate(
                recorder=self.recorder,
                checked_at="2026-06-02T02:00:00Z",
                evidence_source="remote_user_report",
                reporter_label="@hip3.14cirz",
                client="Happ",
                client_version="unknown",
                network_type="mobile",
                transport="reality",
                port=443,
                result="pass",
                symptom="connected",
            )

    def test_rejects_stale_session_for_session_bound_remote_report(self) -> None:
        with self.assertRaisesRegex(
            self.module.RemoteEvidenceError,
            "session-bound remote evidence must use evidence_session_id=nl-anti-block-2026-06-02",
        ):
            self.module.build_candidate(
                recorder=self.recorder,
                checked_at="2026-06-02T02:00:00Z",
                evidence_source="remote_user_report",
                reporter_label="remote-city-user",
                client="Happ",
                client_version="unknown",
                network_type="mobile",
                transport="reality",
                port=443,
                result="fail",
                symptom="timeout",
                evidence_session_id="nl-anti-block-2026-05-28",
            )

    def test_rejects_wrong_transport_or_port_for_session_bound_remote_report(self) -> None:
        with self.assertRaisesRegex(
            self.module.RemoteEvidenceError,
            "session-bound remote evidence must use transport=reality",
        ):
            self.module.build_candidate(
                recorder=self.recorder,
                checked_at="2026-06-02T02:00:00Z",
                evidence_source="remote_user_report",
                reporter_label="remote-city-user",
                client="Happ",
                client_version="unknown",
                network_type="mobile",
                transport="ws",
                port=443,
                result="fail",
                symptom="timeout",
            )

        with self.assertRaisesRegex(
            self.module.RemoteEvidenceError,
            "session-bound remote evidence must use port=443",
        ):
            self.module.build_candidate(
                recorder=self.recorder,
                checked_at="2026-06-02T02:00:00Z",
                evidence_source="support_call_summary",
                reporter_label="workplace-user",
                client="any",
                client_version="unknown",
                network_type="work-wifi",
                transport="reality",
                port=8443,
                result="fail",
                symptom="timeout",
            )

    def test_cli_rejects_stale_session_without_writing_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            report_json = tmp / "remote.json"
            report_md = tmp / "remote.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--checked-at",
                        "2026-06-02T02:00:00Z",
                        "--evidence-source",
                        "remote_user_report",
                        "--reporter-label",
                        "remote-city-user",
                        "--client",
                        "Happ",
                        "--client-version",
                        "unknown",
                        "--network-type",
                        "mobile",
                        "--transport",
                        "reality",
                        "--port",
                        "443",
                        "--result",
                        "fail",
                        "--symptom",
                        "timeout",
                        "--evidence-session-id",
                        "nl-anti-block-2026-05-28",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("session-bound remote evidence must use evidence_session_id", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_record_matrix_writes_matrix_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            report_json = tmp / "remote.json"
            report_md = tmp / "remote.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--checked-at",
                        "2026-06-02T02:00:00Z",
                        "--evidence-source",
                        "remote_user_report",
                        "--reporter-label",
                        "remote-city-user",
                        "--client",
                        "Happ",
                        "--client-version",
                        "unknown",
                        "--network-type",
                        "mobile",
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
            updated = json.loads(matrix.read_text(encoding="utf-8"))
            markdown = report_md.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "REMOTE_CLIENT_EVIDENCE_RECORDED")
        self.assertTrue(payload["recording"]["recorded"])
        self.assertEqual(
            payload["candidate"]["evidence_session_id"],
            "nl-anti-block-2026-06-02",
        )
        self.assertTrue(updated["completion_rule"]["evidence"]["android_happ_or_hiddify"])
        self.assertIn("REMOTE_CLIENT_EVIDENCE_RECORDED", markdown)
        self.assertNotIn("vless://", markdown)


if __name__ == "__main__":
    unittest.main()
