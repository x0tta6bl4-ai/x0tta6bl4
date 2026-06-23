#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
from contextlib import chdir, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "record_remote_client_evidence_reply.py"


def load_module():
    spec = importlib.util.spec_from_file_location("record_remote_client_evidence_reply", MODULE_PATH)
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


def request_packet() -> dict:
    return {
        "generated_at": "2026-06-02T04:00:00Z",
        "decision": "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
        "minimum_reports_required": 2,
        "request_count": 2,
        "missing_requirements": [
            "android_happ_or_hiddify",
            "mobile_network",
            "restricted_or_work_wifi",
        ],
        "requests": [
            {
                "request_id": "remote-client-evidence-1",
                "covers_requirements": [
                    "android_happ_or_hiddify",
                    "mobile_network",
                ],
                "client": "Happ",
                "network_type": "mobile",
                "transport": "reality",
                "port": 443,
                "evidence_session_id": "nl-anti-block-2026-06-02",
                "evidence_session_started_at": "2026-06-02T00:00:00Z",
                "minimum_result_to_close_requirements": "pass",
            },
            {
                "request_id": "remote-client-evidence-2",
                "covers_requirements": ["restricted_or_work_wifi"],
                "client": "any",
                "network_type": "work-wifi",
                "transport": "reality",
                "port": 443,
                "evidence_session_id": "nl-anti-block-2026-06-02",
                "evidence_session_started_at": "2026-06-02T00:00:00Z",
                "minimum_result_to_close_requirements": "pass",
            },
        ],
        "privacy": {"output_privacy_ok": True},
    }


def android_probe_payload() -> dict:
    return {
        "decision": "ANDROID_DEVICE_NOT_CONNECTED",
        "ok": False,
        "adb": {
            "adb_available": True,
            "connected_device_count": 0,
            "device_state_counts": {},
            "raw_serials_stored": False,
        },
        "vpn_runtime": {"vpn_transport_seen": False},
        "dataplane": {"ok": False, "http_code": 0, "tool": "not_run"},
        "matrix_recording": {
            "attempted": False,
            "recorded": False,
            "reason": "record_matrix_not_requested",
        },
        "privacy": {"output_privacy_ok": True},
    }


def server_evidence_payload() -> dict:
    return {
        "live_evidence": {
            "fallback_subscription": {
                "has_reality": True,
                "has_ws": True,
                "has_xhttp": True,
            },
            "runtime": {
                "ghost_xhttp_ready": True,
                "ghost_https_ws_ready": True,
                "status_api_privacy_ok": True,
            },
            "usage_60m": {"privacy_ok": True},
            "rollback_dry_run": {
                "ok": True,
                "confirm_required": "ROLLBACK_GHOST_FALLBACKS",
            },
            "rollback_drill": {
                "rollback_apply": {"ok": True},
                "after_restore": {
                    "x-ui": "active",
                    "telegram-bot-simple.service": "active",
                    "ghost-access-nl-xhttp.service": "active",
                    "ghost-access-nl-https-ws.service": "active",
                    "status_api_health_ok": True,
                },
            },
            "reality_canary_after_rollback_restore": {
                "results": [{"ok": True}, {"ok": True}],
            },
        }
    }


def runtime_probe_payload() -> dict:
    return {
        "decision": "NL_CLIENT_COMPAT_RUNTIME_READY",
        "checked_at": "2026-06-02T01:00:00Z",
        "profile_status_api_unit": {"active": "active"},
        "transport_usage_endpoint": {"ok": True},
        "client_compatibility_endpoint": {
            "http_code": 200,
            "missing_requirements": [
                "android_happ_or_hiddify",
                "mobile_network",
                "restricted_or_work_wifi",
            ],
            "raw_real_client_rows_returned": False,
        },
        "systemd_wiring": {
            "matrix_present": True,
            "summary_present": True,
            "timer_enabled": "enabled",
            "timer_active": "active",
        },
        "required_actions": [],
        "privacy": {
            "output_privacy_ok": True,
            "raw_client_rows_stored": False,
        },
    }


def runtime_deploy_plan_payload() -> dict:
    return {
        "decision": "CLIENT_COMPAT_RUNTIME_ALREADY_APPLIED",
        "ok": True,
        "apply_required": False,
        "applied_to_nl": True,
        "dry_run_mutated_nl": False,
        "current_blocker": "none",
        "remote_state": {
            "status_api_endpoints": {
                "transport_usage_http_code": 200,
                "client_compatibility_http_code": 200,
            }
        },
        "runtime_generated_targets": [
            "/var/lib/ghost-access/client-compatibility/latest.json"
        ],
        "mutation_policy": {
            "forbidden_service_restarts": [
                "x-ui",
                "nginx",
                "telegram-bot-simple.service",
                "ghost-access-nl-xhttp.service",
                "ghost-access-nl-https-ws.service",
            ],
        },
        "files": [],
        "privacy": {
            "output_privacy_ok": True,
            "raw_commands_stored": False,
            "raw_client_rows_stored": False,
        },
    }


def goal_decision_payload() -> dict:
    return {
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "decision": {
            "decision": "observe",
            "nl_mutation_allowed": False,
        },
        "classification": {
            "overall_status": "advisory",
            "transport_status": "advisory",
            "telegram_media_status": "degraded",
            "evidence": [
                "external exit IP is VPN server",
                "packet_loss_percent=0",
                "NL key services active",
                "NL core listeners 443/2083/39829 present",
            ],
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
    }


def goal_warp_plan_payload() -> dict:
    return {
        "decision": "TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE",
        "blockers": [],
        "current_evidence": {
            "telegram_media_status": "degraded",
            "warp_status": "healthy",
            "xray_outbound_tags": ["direct", "warp", "blocked"],
        },
        "target_rule": {"outboundTag": "warp"},
        "rollout": {
            "requires_explicit_operator_confirm": "APPLY_TELEGRAM_MEDIA_WARP_ROUTE",
            "requires_fresh_readonly_snapshot": True,
            "requires_config_backup": True,
            "requires_xray_config_test_before_restart": True,
            "restart_scope": ["x-ui"],
            "forbidden_restarts": [
                "ghost-access-nl-xhttp.service",
                "ghost-access-nl-https-ws.service",
                "telegram-bot-simple.service",
                "nginx",
            ],
            "mutation_scope": "routing.rules only",
        },
        "privacy": {"output_privacy_ok": True, "raw_uuid_stored": False},
    }


def goal_readiness_payload() -> dict:
    return {
        "ok": True,
        "summary": {
            "nl_write_allowed": False,
            "automatic_failover_allowed": False,
            "spb_fallback_allowed": False,
        },
    }


def goal_manifest_payload() -> dict:
    return {
        "status": "planning_only",
        "nl_write_allowed": False,
    }


def goal_preflight_payload() -> dict:
    return {
        "ok": True,
        "deploy_status": "local_ready_but_deploy_blocked",
        "nl_write_allowed": False,
        "checks": [{}, {}, {}],
        "validator_exit_code": 0,
    }


def write_default_refresh_inputs(base: Path) -> None:
    diagnostics = base / "nl-diagnostics"
    services = base / "services" / "nl-server"
    diagnostics.mkdir(parents=True, exist_ok=True)
    services.mkdir(parents=True, exist_ok=True)
    (diagnostics / "nl-anti-block-client-compatibility-matrix-2026-06-02.json").write_text(
        json.dumps(base_matrix()),
        encoding="utf-8",
    )
    (diagnostics / "nl-anti-block-remote-client-evidence-request-2026-06-02.json").write_text(
        json.dumps(request_packet()),
        encoding="utf-8",
    )
    (diagnostics / "nl-anti-block-android-adb-probe-2026-06-02.json").write_text(
        json.dumps(android_probe_payload()),
        encoding="utf-8",
    )
    (
        diagnostics / "nl-anti-block-client-compatibility-runtime-probe-2026-06-02.json"
    ).write_text(json.dumps(runtime_probe_payload()), encoding="utf-8")
    (
        diagnostics
        / "nl-anti-block-client-compatibility-runtime-deploy-plan-2026-06-02.json"
    ).write_text(json.dumps(runtime_deploy_plan_payload()), encoding="utf-8")
    (diagnostics / "nl-anti-block-production-audit-2026-06-02.json").write_text(
        json.dumps(server_evidence_payload()),
        encoding="utf-8",
    )
    (diagnostics / "current-vpn-decision-2026-05-28.json").write_text(
        json.dumps(goal_decision_payload()),
        encoding="utf-8",
    )
    (diagnostics / "nl-telegram-media-warp-route-plan-2026-06-02-fresh.json").write_text(
        json.dumps(goal_warp_plan_payload()),
        encoding="utf-8",
    )
    (diagnostics / "vpn-plan-readiness-audit-2026-05-28.json").write_text(
        json.dumps(goal_readiness_payload()),
        encoding="utf-8",
    )
    (services / "manifest.json").write_text(
        json.dumps(goal_manifest_payload()),
        encoding="utf-8",
    )
    (diagnostics / "goal-preflight.json").write_text(
        json.dumps(goal_preflight_payload()),
        encoding="utf-8",
    )


class RecordRemoteClientEvidenceReplyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.remote = self.module.load_module(
            "record_remote_client_evidence",
            ROOT / "ghost-access" / "record_remote_client_evidence.py",
        )
        self.recorder = self.remote.load_recorder()

    def test_parse_reply_accepts_only_short_allowed_values(self) -> None:
        self.assertEqual(
            self.module.parse_reply("pass connected"),
            {"result": "pass", "symptom": "connected"},
        )
        self.assertEqual(
            self.module.parse_reply("fail no-internet"),
            {"result": "fail", "symptom": "no-internet"},
        )
        with self.assertRaises(self.module.RemoteReplyError):
            self.module.parse_reply("pass timeout")
        with self.assertRaises(self.module.RemoteReplyError):
            self.module.parse_reply("pass connected plus extra text")
        with self.assertRaisesRegex(self.module.RemoteReplyError, "reply is too long"):
            self.module.parse_reply("pass connected " + ("x" * 80))

    def test_rejects_secret_like_reply_text(self) -> None:
        unsafe_replies = [
            "pass connected https://example.test",
            "pass connected 123e4567-e89b-12d3-a456-426614174000",
            "fail timeout 203.0.113.10",
            "fail import @tester",
        ]
        for reply in unsafe_replies:
            with self.subTest(reply=reply):
                with self.assertRaises(self.module.RemoteReplyError):
                    self.module.parse_reply(reply)

    def test_read_reply_from_file_and_stdin(self) -> None:
        parser = self.module.parser()
        with tempfile.TemporaryDirectory() as tmpdir:
            reply_file = Path(tmpdir) / "reply.txt"
            reply_file.write_text("pass connected\n", encoding="utf-8")
            from_file = parser.parse_args(
                [
                    "--request-id",
                    "remote-client-evidence-1",
                    "--reply-file",
                    str(reply_file),
                ]
            )
            self.assertEqual(self.module.read_reply_from_args(from_file), "pass connected\n")

        from_stdin = parser.parse_args(
            ["--request-id", "remote-client-evidence-1", "--reply-stdin"]
        )
        with patch("sys.stdin", io.StringIO("fail timeout\n")):
            self.assertEqual(self.module.read_reply_from_args(from_stdin), "fail timeout\n")

    def test_rejects_multiple_reply_sources_before_recording(self) -> None:
        args = self.module.parser().parse_args(
            [
                "--request-id",
                "remote-client-evidence-1",
                "--reply",
                "pass connected",
                "--reply-stdin",
            ]
        )

        with self.assertRaisesRegex(self.module.RemoteReplyError, "provide exactly one reply source"):
            self.module.read_reply_from_args(args)

    def test_packet_freshness_rejects_missing_future_and_stale_packets(self) -> None:
        packet = request_packet()
        self.module.validate_packet_freshness(
            packet,
            max_age_hours=24,
            now=self.module.parse_timestamp("2026-06-02T05:00:00Z"),
        )

        missing = request_packet()
        missing.pop("generated_at")
        with self.assertRaisesRegex(self.module.RemoteReplyError, "generated_at is missing"):
            self.module.validate_packet_freshness(
                missing,
                max_age_hours=24,
                now=self.module.parse_timestamp("2026-06-02T05:00:00Z"),
            )

        future = request_packet()
        future["generated_at"] = "2026-06-03T05:00:00Z"
        with self.assertRaisesRegex(self.module.RemoteReplyError, "in the future"):
            self.module.validate_packet_freshness(
                future,
                max_age_hours=24,
                now=self.module.parse_timestamp("2026-06-02T05:00:00Z"),
            )

        with self.assertRaisesRegex(self.module.RemoteReplyError, "request packet is stale"):
            self.module.validate_packet_freshness(
                packet,
                max_age_hours=24,
                now=self.module.parse_timestamp("2026-06-04T05:01:00Z"),
            )

    def test_mobile_pass_reply_marks_android_and_mobile_requirements(self) -> None:
        request = self.module.find_request(request_packet(), "remote-client-evidence-1")
        candidate = self.module.build_candidate_from_reply(
            remote_module=self.remote,
            recorder=self.recorder,
            request=request,
            parsed_reply={"result": "pass", "symptom": "connected"},
            checked_at="2026-06-02T04:00:00Z",
        )

        updated = self.recorder.add_or_update_check(base_matrix(), candidate)

        evidence = updated["completion_rule"]["evidence"]
        self.assertTrue(evidence["android_happ_or_hiddify"])
        self.assertTrue(evidence["mobile_network"])
        self.assertFalse(evidence["restricted_or_work_wifi"])
        self.assertEqual(candidate["reporter_label"], "remote-city-user")
        self.assertEqual(candidate["evidence_session_id"], "nl-anti-block-2026-06-02")
        self.assertFalse(candidate["raw_reporter_identifier_stored"])

    def test_fail_reply_records_evidence_without_closing_requirement(self) -> None:
        request = self.module.find_request(request_packet(), "remote-client-evidence-2")
        candidate = self.module.build_candidate_from_reply(
            remote_module=self.remote,
            recorder=self.recorder,
            request=request,
            parsed_reply={"result": "fail", "symptom": "timeout"},
            checked_at="2026-06-02T04:00:00Z",
        )

        updated = self.recorder.add_or_update_check(base_matrix(), candidate)

        self.assertEqual(candidate["status"], "fail")
        self.assertFalse(updated["completion_rule"]["evidence"]["restricted_or_work_wifi"])
        self.assertEqual(candidate["evidence_source"], "support_call_summary")
        self.assertEqual(candidate["reporter_label"], "workplace-user")

    def test_rejects_stale_request_contract_before_recording(self) -> None:
        request = self.module.find_request(request_packet(), "remote-client-evidence-1")
        request["evidence_session_id"] = "nl-anti-block-2026-05-28"

        with self.assertRaisesRegex(
            self.module.RemoteReplyError,
            "request evidence_session_id must be nl-anti-block-2026-06-02",
        ):
            self.module.validate_request_contract(request)

    def test_rejects_wrong_transport_or_port_before_recording(self) -> None:
        request = self.module.find_request(request_packet(), "remote-client-evidence-1")
        request["transport"] = "ws"

        with self.assertRaisesRegex(self.module.RemoteReplyError, "request transport must be reality"):
            self.module.validate_request_contract(request)

        request["transport"] = "reality"
        request["port"] = 8443

        with self.assertRaisesRegex(self.module.RemoteReplyError, "request port must be 443"):
            self.module.validate_request_contract(request)

    def test_cli_record_matrix_writes_reply_report_and_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")
            packet_sha256 = hashlib.sha256(packet.read_bytes()).hexdigest()

            stdout = io.StringIO()
            with patch("sys.stdin", io.StringIO("pass connected\n")), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--expect-request-packet-sha256",
                        packet_sha256,
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply-stdin",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            updated = json.loads(matrix.read_text(encoding="utf-8"))
            markdown = report_md.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "REMOTE_CLIENT_EVIDENCE_REPLY_RECORDED")
        self.assertEqual(payload["source_request_packet"], str(packet))
        self.assertEqual(payload["source_request_packet_sha256"], packet_sha256)
        self.assertGreater(payload["source_request_packet_size_bytes"], 0)
        self.assertFalse(payload["privacy"]["raw_reply_stored"])
        self.assertEqual(
            payload["candidate"]["evidence_session_id"],
            "nl-anti-block-2026-06-02",
        )
        self.assertTrue(payload["next_steps"]["refresh_artifacts_required"])
        self.assertEqual(
            payload["next_steps"]["refresh_artifacts_command"],
            "python3 services/nl-server/ghost-access/refresh_client_evidence_artifacts.py --write --json",
        )
        self.assertTrue(updated["completion_rule"]["evidence"]["android_happ_or_hiddify"])
        self.assertIn("REMOTE_CLIENT_EVIDENCE_REPLY_RECORDED", markdown)
        self.assertIn("refresh_client_evidence_artifacts.py", markdown)
        self.assertNotIn("https://", markdown)

    def test_cli_rejects_request_packet_sha256_mismatch_without_writing_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")

            stdout = io.StringIO()
            with patch("sys.stdin", io.StringIO("pass connected\n")), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--expect-request-packet-sha256",
                        "0" * 64,
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply",
                        "pass connected",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("request packet sha256 mismatch", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_record_matrix_accepts_reply_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            reply_file = tmp / "reply.txt"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")
            reply_file.write_text("pass connected\n", encoding="utf-8")
            packet_sha256 = hashlib.sha256(packet.read_bytes()).hexdigest()

            stdout = io.StringIO()
            with patch("sys.stdin", io.StringIO("pass connected\n")), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--expect-request-packet-sha256",
                        packet_sha256,
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply-file",
                        str(reply_file),
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            updated = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "REMOTE_CLIENT_EVIDENCE_REPLY_RECORDED")
        self.assertTrue(updated["completion_rule"]["evidence"]["android_happ_or_hiddify"])

    def test_cli_rejects_matrix_write_without_request_packet_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply",
                        "pass connected",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("--expect-request-packet-sha256 is required with --write", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_rejects_reply_report_write_without_request_packet_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply",
                        "pass connected",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("--expect-request-packet-sha256 is required with --write", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_reply_report_write_accepts_request_packet_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")
            packet_sha256 = hashlib.sha256(packet.read_bytes()).hexdigest()

            stdout = io.StringIO()
            with patch("sys.stdin", io.StringIO("pass connected\n")), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--expect-request-packet-sha256",
                        packet_sha256,
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply-stdin",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))
            report = json.loads(report_json.read_text(encoding="utf-8"))
            report_md_exists = report_md.exists()

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "REMOTE_CLIENT_EVIDENCE_REPLY_VALIDATED")
        self.assertEqual(payload["source_request_packet_sha256"], packet_sha256)
        self.assertEqual(report["source_request_packet_sha256"], packet_sha256)
        self.assertEqual(unchanged, base_matrix())
        self.assertTrue(report_md_exists)

    def test_cli_rejects_reply_argument_for_persisted_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")
            packet_sha256 = hashlib.sha256(packet.read_bytes()).hexdigest()

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--expect-request-packet-sha256",
                        packet_sha256,
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply",
                        "pass connected",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("--write requires --reply-stdin or --reply-file", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_rejects_oversized_stdin_reply_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")
            packet_sha256 = hashlib.sha256(packet.read_bytes()).hexdigest()

            stdout = io.StringIO()
            long_reply = "pass connected " + ("x" * 80)
            with patch("sys.stdin", io.StringIO(long_reply)), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--expect-request-packet-sha256",
                        packet_sha256,
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply-stdin",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("reply is too long", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_reply_stdin_dry_run_keeps_matrix_and_reports_unwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            packet.write_text(json.dumps(request_packet()), encoding="utf-8")
            before = matrix.read_bytes()

            stdout = io.StringIO()
            with patch("sys.stdin", io.StringIO("pass connected\n")), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply-stdin",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            after = matrix.read_bytes()

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "REMOTE_CLIENT_EVIDENCE_REPLY_VALIDATED")
        self.assertEqual(payload["recording"]["attempted"], False)
        self.assertEqual(payload["recording"]["recorded"], False)
        self.assertEqual(payload["recording"]["reason"], "record_matrix_not_requested")
        self.assertEqual(before, after)
        self.assertEqual(json.loads(after.decode("utf-8")), base_matrix())
        self.assertFalse(matrix_md.exists())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())
        self.assertFalse(payload["next_steps"]["refresh_artifacts_required"])
        self.assertEqual(payload["privacy"]["output_privacy_ok"], True)

    def test_cli_rejects_wrong_request_contract_without_writing_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            stale_packet = request_packet()
            stale_packet["requests"][0]["evidence_session_id"] = "nl-anti-block-2026-05-28"
            packet.write_text(json.dumps(stale_packet), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply",
                        "pass connected",
                        "--max-request-age-hours",
                        "9999",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("request evidence_session_id must be", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_rejects_stale_request_packet_without_writing_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            packet = tmp / "request.json"
            report_json = tmp / "reply.json"
            report_md = tmp / "reply.md"
            matrix.write_text(json.dumps(base_matrix()), encoding="utf-8")
            stale_packet = request_packet()
            stale_packet["generated_at"] = "2026-01-01T00:00:00Z"
            packet.write_text(json.dumps(stale_packet), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--request-packet",
                        str(packet),
                        "--request-id",
                        "remote-client-evidence-1",
                        "--reply",
                        "pass connected",
                        "--json-out",
                        str(report_json),
                        "--markdown-out",
                        str(report_md),
                        "--write",
                        "--record-matrix",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            unchanged = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(rc, 2)
        self.assertIn("request packet is stale", payload["error"])
        self.assertEqual(unchanged, base_matrix())
        self.assertFalse(report_json.exists())
        self.assertFalse(report_md.exists())

    def test_cli_refresh_artifacts_updates_downstream_after_matrix_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            write_default_refresh_inputs(tmp)
            packet = (
                tmp
                / "nl-diagnostics"
                / "nl-anti-block-remote-client-evidence-request-2026-06-02.json"
            )
            packet_sha256 = hashlib.sha256(packet.read_bytes()).hexdigest()
            stdout = io.StringIO()
            with chdir(tmp), patch("sys.stdin", io.StringIO("pass connected\n")), redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--request-id",
                        "remote-client-evidence-1",
                        "--expect-request-packet-sha256",
                        packet_sha256,
                        "--reply-stdin",
                        "--checked-at",
                        "2026-06-02T04:00:00Z",
                        "--max-request-age-hours",
                        "9999",
                        "--write",
                        "--record-matrix",
                        "--refresh-artifacts",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            diagnostics = tmp / "nl-diagnostics"
            matrix = json.loads(
                (
                    diagnostics
                    / "nl-anti-block-client-compatibility-matrix-2026-06-02.json"
                ).read_text(encoding="utf-8")
            )
            request = json.loads(
                (
                    diagnostics
                    / "nl-anti-block-remote-client-evidence-request-2026-06-02.json"
                ).read_text(encoding="utf-8")
            )
            audit = json.loads(
                (
                    diagnostics / "nl-anti-block-production-audit-2026-06-02.json"
                ).read_text(encoding="utf-8")
            )

        evidence = matrix["completion_rule"]["evidence"]
        self.assertEqual(rc, 0)
        self.assertTrue(evidence["android_happ_or_hiddify"])
        self.assertTrue(evidence["mobile_network"])
        self.assertFalse(evidence["restricted_or_work_wifi"])
        self.assertTrue(payload["artifact_refresh"]["requested"])
        self.assertTrue(payload["artifact_refresh"]["ran"])
        self.assertEqual(
            payload["artifact_refresh"]["decision"],
            "CLIENT_EVIDENCE_ARTIFACTS_REFRESHED",
        )
        self.assertEqual(
            payload["artifact_refresh"]["goal_status_decision"],
            "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
        )
        self.assertFalse(payload["artifact_refresh"]["goal_complete"])
        self.assertGreaterEqual(payload["artifact_refresh"]["goal_requirements_passed"], 6)
        self.assertEqual(payload["artifact_refresh"]["goal_requirements_total"], 22)
        self.assertFalse(payload["next_steps"]["refresh_artifacts_required"])
        self.assertEqual(
            request["missing_requirements"],
            ["restricted_or_work_wifi"],
        )
        self.assertEqual(
            audit["decision"],
            "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE",
        )
        self.assertLess(
            payload["artifact_refresh"]["production_audit_remaining_count"],
            6,
        )

    def test_unknown_request_id_fails_closed(self) -> None:
        with self.assertRaises(self.module.RemoteReplyError):
            self.module.find_request(request_packet(), "missing-request")


if __name__ == "__main__":
    unittest.main()
