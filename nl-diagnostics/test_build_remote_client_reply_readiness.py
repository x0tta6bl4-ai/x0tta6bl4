#!/usr/bin/env python3
from __future__ import annotations

from datetime import UTC, datetime
import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_remote_client_reply_readiness.py")
SPEC = importlib.util.spec_from_file_location("build_remote_client_reply_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
readiness = importlib.util.module_from_spec(SPEC)
sys.modules["build_remote_client_reply_readiness"] = readiness
SPEC.loader.exec_module(readiness)


def command(request_id: str, reply: str, *, write: bool) -> str:
    write_flags = "--write --record-matrix --refresh-artifacts " if write else ""
    return (
        f"printf '%s\\n' \"{reply}\" | "
        "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
        f"{write_flags}"
        "--expect-request-packet-sha256 \"$(sha256sum "
        "nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json "
        "| awk '{print $1}')\" "
        f"--request-id {request_id} --reply-stdin --json"
    )


def request_packet() -> dict:
    return {
        "generated_at": "2026-06-06T15:47:38Z",
        "decision": "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
        "missing_requirements": [
            "android_happ_or_hiddify",
            "mobile_network",
            "restricted_or_work_wifi",
        ],
        "minimum_reports_required": 2,
        "request_count": 2,
        "privacy": {"output_privacy_ok": True},
        "requests": [
            {
                "request_id": "remote-client-evidence-1",
                "covers_requirements": ["android_happ_or_hiddify", "mobile_network"],
                "tester_message": "Reply only with allowed short replies. Do not send logs.",
                "operator_record_pass_command": "",
                "operator_record_fail_command": "",
                "operator_reply_record_pass_command": command(
                    "remote-client-evidence-1", "pass connected", write=True
                ),
                "operator_reply_record_fail_command": command(
                    "remote-client-evidence-1", "fail timeout", write=True
                ),
                "operator_reply_validate_pass_command": command(
                    "remote-client-evidence-1", "pass connected", write=False
                ),
                "operator_reply_validate_fail_command": command(
                    "remote-client-evidence-1", "fail timeout", write=False
                ),
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            },
            {
                "request_id": "remote-client-evidence-2",
                "covers_requirements": ["restricted_or_work_wifi"],
                "tester_message": "Reply only with allowed short replies. Do not send logs.",
                "operator_record_pass_command": "",
                "operator_record_fail_command": "",
                "operator_reply_record_pass_command": command(
                    "remote-client-evidence-2", "pass connected", write=True
                ),
                "operator_reply_record_fail_command": command(
                    "remote-client-evidence-2", "fail timeout", write=True
                ),
                "operator_reply_validate_pass_command": command(
                    "remote-client-evidence-2", "pass connected", write=False
                ),
                "operator_reply_validate_fail_command": command(
                    "remote-client-evidence-2", "fail timeout", write=False
                ),
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            },
        ],
    }


def goal_status() -> dict:
    return {
        "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
        "requirements": [
            {
                "id": "ANTIBLOCK-CLIENTS-01",
                "status": "blocked_external_evidence",
                "evidence": [
                    "remote_request_decision=REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
                    "remote_request_count=2",
                    "remote_request_record_commands_use_stdin=true",
                    "remote_request_reply_commands_hash_guard_ok=true",
                    "remote_request_reply_dry_run_uses_packet_hash=true",
                ],
            }
        ],
    }


def recorder_text() -> str:
    return '''
DEFAULT_MAX_REQUEST_AGE_HOURS = 24
MAX_REPLY_BYTES = 64
FORBIDDEN_REPLY_PATTERNS = {}
def validate_packet_freshness(): pass
def validate_write_requires_sha256(): pass
"--expect-request-packet-sha256 is required with --write"
def validate_write_reply_source(): pass
"--write requires --reply-stdin or --reply-file"
"unsafe tester reply"
"--refresh-artifacts requires --write and --record-matrix"
"raw_reply_stored": False
'''


def payload(packet: dict | None = None, *, now: datetime | None = None) -> dict:
    return readiness.build_payload(
        request_packet=packet or request_packet(),
        request_source={"path": "request.json", "sha256": "a" * 64, "size_bytes": 123},
        goal_status=goal_status(),
        reply_recorder_text=recorder_text(),
        now=now or datetime(2026, 6, 6, 16, 0, tzinfo=UTC),
    )


class RemoteClientReplyReadinessTests(unittest.TestCase):
    def test_ready_for_safe_intake_when_request_goal_and_recorder_align(self):
        report = payload()

        self.assertEqual(report["decision"], "REMOTE_CLIENT_REPLIES_READY_FOR_SAFE_INTAKE")
        self.assertTrue(report["ready_for_safe_intake"])
        self.assertFalse(report["server_write_allowed"])
        self.assertFalse(report["reply_recording_performed"])

    def test_stale_request_blocks_intake(self):
        stale = request_packet()
        stale["generated_at"] = "2026-06-01T00:00:00Z"

        report = payload(stale)

        self.assertEqual(report["decision"], "REMOTE_CLIENT_REPLIES_NOT_READY")
        freshness = next(row for row in report["gates"] if row["id"] == "REQUEST-FRESHNESS-01")
        self.assertEqual(freshness["status"], readiness.MISSING)

    def test_missing_hash_guard_blocks_commands_gate(self):
        packet = request_packet()
        packet["requests"][0]["operator_reply_record_pass_command"] = (
            "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
            "--write --record-matrix --refresh-artifacts --request-id remote-client-evidence-1 "
            "--reply-stdin --json"
        )

        report = payload(packet)

        commands = next(row for row in report["gates"] if row["id"] == "REQUEST-COMMANDS-01")
        self.assertEqual(commands["status"], readiness.MISSING)
        self.assertFalse(report["ready_for_safe_intake"])

    def test_reply_recorder_must_reject_inline_write_reply(self):
        report = readiness.build_payload(
            request_packet=request_packet(),
            request_source={"path": "request.json", "sha256": "a" * 64, "size_bytes": 123},
            goal_status=goal_status(),
            reply_recorder_text=recorder_text().replace("validate_write_reply_source", ""),
            now=datetime(2026, 6, 6, 16, 0, tzinfo=UTC),
        )

        recorder = next(row for row in report["gates"] if row["id"] == "REPLY-RECORDER-01")
        self.assertEqual(recorder["status"], readiness.MISSING)

    def test_markdown_contains_no_write_notice(self):
        markdown = readiness.render_markdown(payload())

        self.assertIn("Remote Client Reply Readiness", markdown)
        self.assertIn("No NL or SPB writes", markdown)
        self.assertIn("Validate pass without writing", markdown)


if __name__ == "__main__":
    unittest.main()
