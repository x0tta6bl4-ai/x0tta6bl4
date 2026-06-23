#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "refresh_client_evidence_artifacts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("refresh_client_evidence_artifacts", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def matrix_payload() -> dict:
    return {
        "matrix_id": "test",
        "decision": "stale",
        "real_client_checks": [
            {
                "checked_at": "2026-06-02T01:00:00Z",
                "client": "v2rayN",
                "client_version": "7.12",
                "network_type": "desktop",
                "transport": "xhttp",
                "port": 8443,
                "status": "pass",
                "symptom": "connected",
                "raw_secret_material_stored": False,
            }
        ],
        "completion_rule": {"current_status": "stale"},
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


def write_supporting_artifacts(tmp: Path) -> dict[str, Path]:
    paths = {
        "server": tmp / "server-evidence.json",
        "runtime_probe": tmp / "runtime-probe.json",
        "runtime_deploy": tmp / "runtime-deploy.json",
    }
    paths["server"].write_text(json.dumps(server_evidence_payload()), encoding="utf-8")
    paths["runtime_probe"].write_text(json.dumps(runtime_probe_payload()), encoding="utf-8")
    paths["runtime_deploy"].write_text(json.dumps(runtime_deploy_plan_payload()), encoding="utf-8")
    return paths


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
        "checks": [
            {"name": "remote_client_evidence_request_hash_binding_policy_present", "ok": True},
            {"name": "remote_client_evidence_request_reply_commands_present", "ok": True},
            {"name": "remote_client_evidence_reply_dry_run_uses_packet_hash", "ok": True},
        ],
        "validator_exit_code": 0,
    }


def write_goal_supporting_artifacts(tmp: Path) -> dict[str, Path]:
    paths = {
        "decision": tmp / "goal-decision.json",
        "warp": tmp / "goal-warp.json",
        "readiness": tmp / "goal-readiness.json",
        "manifest": tmp / "goal-manifest.json",
        "preflight": tmp / "goal-preflight.json",
        "goal_json": tmp / "goal-status.json",
        "goal_md": tmp / "goal-status.md",
    }
    paths["decision"].write_text(json.dumps(goal_decision_payload()), encoding="utf-8")
    paths["warp"].write_text(json.dumps(goal_warp_plan_payload()), encoding="utf-8")
    paths["readiness"].write_text(json.dumps(goal_readiness_payload()), encoding="utf-8")
    paths["manifest"].write_text(json.dumps(goal_manifest_payload()), encoding="utf-8")
    paths["preflight"].write_text(json.dumps(goal_preflight_payload()), encoding="utf-8")
    return paths


def goal_args(paths: dict[str, Path]) -> list[str]:
    return [
        "--goal-status-json-out",
        str(paths["goal_json"]),
        "--goal-status-markdown-out",
        str(paths["goal_md"]),
        "--goal-decision-json",
        str(paths["decision"]),
        "--goal-telegram-warp-plan-json",
        str(paths["warp"]),
        "--goal-readiness-audit-json",
        str(paths["readiness"]),
        "--goal-manifest-json",
        str(paths["manifest"]),
        "--goal-preflight-json",
        str(paths["preflight"]),
    ]


class RefreshClientEvidenceArtifactsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_refresh_dry_run_recomputes_status_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            android = tmp / "android.json"
            matrix.write_text(json.dumps(matrix_payload()), encoding="utf-8")
            android.write_text(json.dumps(android_probe_payload()), encoding="utf-8")
            support = write_supporting_artifacts(tmp)
            goal_support = write_goal_supporting_artifacts(tmp)

            args = self.module.parser().parse_args(
                [
                    "--matrix",
                    str(matrix),
                    "--android-adb-probe",
                    str(android),
                    "--server-evidence-json",
                    str(support["server"]),
                    "--runtime-probe-json",
                    str(support["runtime_probe"]),
                    "--runtime-deploy-plan-json",
                    str(support["runtime_deploy"]),
                ]
                + goal_args(goal_support)
            )
            report = self.module.refresh(args)
            stored = json.loads(matrix.read_text(encoding="utf-8"))

        self.assertEqual(report["decision"], "CLIENT_EVIDENCE_ARTIFACTS_REFRESH_DRY_RUN")
        self.assertFalse(report["written"])
        self.assertEqual(report["matrix_decision"], "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED")
        self.assertEqual(report["goal_status_decision"], "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE")
        self.assertFalse(report["goal_complete"])
        self.assertIn("android_happ_or_hiddify", report["missing_requirements"])
        self.assertEqual(stored["decision"], "stale")

    def test_cli_write_refreshes_all_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            matrix = tmp / "matrix.json"
            matrix_md = tmp / "matrix.md"
            android = tmp / "android.json"
            remote_json = tmp / "remote.json"
            remote_md = tmp / "remote.md"
            runtime_json = tmp / "runtime.json"
            runtime_md = tmp / "runtime.md"
            plan_json = tmp / "plan.json"
            plan_md = tmp / "plan.md"
            request_json = tmp / "request.json"
            request_md = tmp / "request.md"
            audit_json = tmp / "audit.json"
            audit_md = tmp / "audit.md"
            matrix.write_text(json.dumps(matrix_payload()), encoding="utf-8")
            android.write_text(json.dumps(android_probe_payload()), encoding="utf-8")
            support = write_supporting_artifacts(tmp)
            goal_support = write_goal_supporting_artifacts(tmp)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(matrix),
                        "--matrix-markdown",
                        str(matrix_md),
                        "--android-adb-probe",
                        str(android),
                        "--remote-intake-json-out",
                        str(remote_json),
                        "--remote-intake-markdown-out",
                        str(remote_md),
                        "--runtime-summary-json-out",
                        str(runtime_json),
                        "--runtime-summary-markdown-out",
                        str(runtime_md),
                        "--evidence-plan-json-out",
                        str(plan_json),
                        "--evidence-plan-markdown-out",
                        str(plan_md),
                        "--remote-request-json-out",
                        str(request_json),
                        "--remote-request-markdown-out",
                        str(request_md),
                        "--server-evidence-json",
                        str(support["server"]),
                        "--runtime-probe-json",
                        str(support["runtime_probe"]),
                        "--runtime-deploy-plan-json",
                        str(support["runtime_deploy"]),
                        "--production-audit-json-out",
                        str(audit_json),
                        "--production-audit-markdown-out",
                        str(audit_md),
                        "--write",
                        "--json",
                    ]
                    + goal_args(goal_support)
                )
            report = json.loads(stdout.getvalue())
            refreshed_matrix = json.loads(matrix.read_text(encoding="utf-8"))
            runtime_payload = json.loads(runtime_json.read_text(encoding="utf-8"))
            plan_payload = json.loads(plan_json.read_text(encoding="utf-8"))
            request_payload = json.loads(request_json.read_text(encoding="utf-8"))
            remote_payload = json.loads(remote_json.read_text(encoding="utf-8"))
            audit_payload = json.loads(audit_json.read_text(encoding="utf-8"))
            goal_payload = json.loads(goal_support["goal_json"].read_text(encoding="utf-8"))
            anti_block = next(
                row
                for row in goal_payload["requirements"]
                if row["id"] == "ANTIBLOCK-CLIENTS-01"
            )
            written_paths = {
                "matrix_md": matrix_md.exists(),
                "remote_md": remote_md.exists(),
                "runtime_md": runtime_md.exists(),
                "plan_md": plan_md.exists(),
                "request_md": request_md.exists(),
                "audit_md": audit_md.exists(),
                "goal_md": goal_support["goal_md"].exists(),
            }

        self.assertEqual(rc, 0)
        self.assertEqual(report["decision"], "CLIENT_EVIDENCE_ARTIFACTS_REFRESHED")
        self.assertEqual(refreshed_matrix["decision"], "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED")
        self.assertTrue(runtime_payload["ok"])
        self.assertFalse(runtime_payload["complete"])
        self.assertEqual(plan_payload["decision"], "CLIENT_EVIDENCE_REQUIRED")
        self.assertEqual(request_payload["decision"], "REMOTE_CLIENT_EVIDENCE_REQUEST_READY")
        self.assertEqual(remote_payload["decision"], "REMOTE_CLIENT_EVIDENCE_INTAKE_READY")
        self.assertEqual(
            audit_payload["decision"],
            "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE",
        )
        self.assertEqual(
            report["production_audit_decision"],
            "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE",
        )
        self.assertEqual(
            report["goal_status_decision"],
            "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
        )
        self.assertFalse(goal_payload["goal_complete"])
        self.assertEqual(goal_payload["requirements_passed"], 7)
        self.assertEqual(goal_payload["requirements_total"], 22)
        self.assertIn("remote_request_ready=true", anti_block["evidence"])
        self.assertIn("remote_request_validate_commands_no_write=true", anti_block["evidence"])
        self.assertIn("remote_request_hash_binding_policy_ok=true", anti_block["evidence"])
        self.assertIn("remote_request_reply_commands_hash_guard_ok=true", anti_block["evidence"])
        self.assertIn("remote_request_reply_dry_run_uses_packet_hash=true", anti_block["evidence"])
        self.assertEqual(
            written_paths,
            {
                "matrix_md": True,
                "remote_md": True,
                "runtime_md": True,
                "plan_md": True,
                "request_md": True,
                "audit_md": True,
                "goal_md": True,
            },
        )

    def test_missing_matrix_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--matrix",
                        str(Path(tmpdir) / "missing.json"),
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(rc, 2)
        self.assertFalse(payload["ok"])
        self.assertIn("matrix not found", payload["error"])


if __name__ == "__main__":
    unittest.main()
