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
MODULE_PATH = ROOT / "ghost-access" / "build_anti_block_production_audit.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_anti_block_production_audit", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def server_seed() -> dict:
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


def partial_matrix() -> dict:
    return {
        "decision": "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
        "real_client_checks": [
            {
                "status": "pass",
                "raw_secret_material_stored": False,
                "client": "v2rayN",
                "network_type": "desktop",
                "transport": "reality",
            }
        ],
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
                }
            ],
        },
    }


def complete_matrix() -> dict:
    matrix = partial_matrix()
    matrix["decision"] = "CLIENT_MATRIX_COMPLETE"
    matrix["completion_rule"]["evidence"] = {
        "desktop_v2rayn": True,
        "android_happ_or_hiddify": True,
        "mobile_network": True,
        "restricted_or_work_wifi": True,
    }
    matrix["completion_rule"]["missing_requirements"] = []
    matrix["completion_rule"]["next_required_checks"] = []
    matrix["real_client_checks"].extend(
        [
            {
                "status": "pass",
                "raw_secret_material_stored": False,
                "checked_at": "2026-06-02T01:00:00Z",
                "client": "Happ",
                "network_type": "mobile",
                "transport": "reality",
                "port": 443,
                "evidence_session_id": "nl-anti-block-2026-06-02",
            },
            {
                "status": "pass",
                "raw_secret_material_stored": False,
                "checked_at": "2026-06-02T01:00:00Z",
                "client": "Happ",
                "network_type": "work-wifi",
                "transport": "reality",
                "port": 443,
                "evidence_session_id": "nl-anti-block-2026-06-02",
            },
        ]
    )
    return matrix


def evidence_plan(missing: list[str]) -> dict:
    return {
        "decision": "CLIENT_EVIDENCE_REQUIRED" if missing else "CLIENT_EVIDENCE_COMPLETE",
        "adb_context": {
            "adb_available": True,
            "connected_device_count": 0,
            "raw_serials_stored": False,
        },
        "android_adb_probe": {"decision": "ANDROID_DEVICE_NOT_CONNECTED"},
        "required_tasks": [
            {
                "requirement": requirement,
                "client": "Happ",
                "network_type": "mobile",
                "transport": "reality",
                "port": 443,
                "android_adb_probe_record_command_template": "probe_android_adb_vpn.py --write --json --record-matrix",
                "remote_client_evidence_record_command_template": "record_remote_client_evidence.py --write --record-matrix",
            }
            for requirement in missing
        ],
        "privacy": {"output_privacy_ok": True},
    }


def remote_intake(missing: list[str]) -> dict:
    return {
        "decision": "REMOTE_CLIENT_EVIDENCE_INTAKE_READY",
        "matrix_summary": {"missing_requirements": missing},
        "safe_remote_record_command_template": "record_remote_client_evidence.py --write --record-matrix",
        "recording": {"attempted": False, "recorded": False},
        "privacy": {"output_privacy_ok": True},
    }


def remote_request(missing: list[str]) -> dict:
    requests = []
    if missing:
        requests = [
            {
                "request_id": "remote-client-evidence-1",
                "covers_requirements": ["android_happ_or_hiddify", "mobile_network"],
                "client": "Happ",
                "network_type": "mobile",
                "transport": "reality",
                "port": 443,
                "evidence_session_id": "nl-anti-block-2026-06-02",
                "minimum_result_to_close_requirements": "pass",
                "operator_record_pass_command": "record_remote_client_evidence.py --write --record-matrix --result pass",
                "operator_record_fail_command": "record_remote_client_evidence.py --write --record-matrix --result fail",
            },
            {
                "request_id": "remote-client-evidence-2",
                "covers_requirements": ["restricted_or_work_wifi"],
                "client": "any",
                "network_type": "work-wifi",
                "transport": "reality",
                "port": 443,
                "evidence_session_id": "nl-anti-block-2026-06-02",
                "minimum_result_to_close_requirements": "pass",
                "operator_record_pass_command": "record_remote_client_evidence.py --write --record-matrix --result pass",
                "operator_record_fail_command": "record_remote_client_evidence.py --write --record-matrix --result fail",
            },
        ]
    return {
        "decision": (
            "REMOTE_CLIENT_EVIDENCE_REQUEST_READY"
            if missing
            else "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED"
        ),
        "minimum_reports_required": len(requests),
        "request_count": len(requests),
        "missing_requirements": missing,
        "requests": requests,
        "privacy": {"output_privacy_ok": True},
    }


def runtime_summary(missing: list[str], complete: bool) -> dict:
    return {
        "decision": "CLIENT_MATRIX_COMPLETE" if complete else "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
        "complete": complete,
        "missing_requirements": missing,
        "real_client_checks": 3 if complete else 1,
        "passing_real_client_checks": 3 if complete else 1,
        "local_v2rayn_dataplane_probe": {"ok": True},
        "privacy": {"output_privacy_ok": True},
    }


def runtime_probe(missing: list[str]) -> dict:
    return {
        "decision": "NL_CLIENT_COMPAT_RUNTIME_READY",
        "checked_at": "2026-06-02T01:00:00Z",
        "profile_status_api_unit": {"active": "active"},
        "transport_usage_endpoint": {"ok": True},
        "client_compatibility_endpoint": {
            "http_code": 200,
            "missing_requirements": missing,
            "raw_real_client_rows_returned": False,
        },
        "systemd_wiring": {
            "matrix_present": True,
            "summary_present": True,
            "timer_enabled": "enabled",
            "timer_active": "active",
        },
        "required_actions": [],
        "privacy": {"output_privacy_ok": True},
    }


def runtime_deploy_plan() -> dict:
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
        "mutation_policy": {
            "forbidden_service_restarts": [
                "x-ui",
                "nginx",
                "telegram-bot-simple.service",
                "ghost-access-nl-xhttp.service",
                "ghost-access-nl-https-ws.service",
            ],
        },
        "runtime_generated_targets": [
            "/var/lib/ghost-access/client-compatibility/latest.json"
        ],
        "files": [],
        "privacy": {"output_privacy_ok": True},
    }


class BuildAntiBlockProductionAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def build(self, matrix: dict) -> dict:
        missing = matrix["completion_rule"]["missing_requirements"]
        return self.module.build_audit(
            server_evidence_seed=server_seed(),
            matrix=matrix,
            evidence_plan=evidence_plan(missing),
            remote_intake=remote_intake(missing),
            remote_request=remote_request(missing),
            runtime_summary=runtime_summary(missing, complete=not missing),
            runtime_probe=runtime_probe(missing),
            runtime_deploy_plan=runtime_deploy_plan(),
            generated_at="2026-06-02T01:00:00Z",
        )

    def test_partial_client_matrix_keeps_goal_not_complete(self) -> None:
        audit = self.build(partial_matrix())

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE")
        self.assertEqual(
            audit["requirements"]["user_client_matrix_after_rollout"],
            "partial_desktop_pass_mobile_pending",
        )
        self.assertIn(
            "record Android Happ/Hiddify client evidence after rollout",
            audit["remaining_before_goal_complete"],
        )
        self.assertEqual(
            audit["client_compatibility_matrix"]["remote_client_evidence_request"]["request_count"],
            2,
        )
        self.assertEqual(self.module.validate_output(audit), [])

    def test_complete_client_matrix_marks_candidate_ready(self) -> None:
        audit = self.build(complete_matrix())

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_READY")
        self.assertEqual(audit["remaining_before_goal_complete"], [])
        self.assertEqual(audit["requirements"]["user_client_matrix_after_rollout"], "pass")

    def test_complete_matrix_without_current_session_evidence_is_not_ready(self) -> None:
        matrix = complete_matrix()
        for row in matrix["real_client_checks"]:
            row.pop("evidence_session_id", None)

        audit = self.build(matrix)

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE")
        self.assertEqual(
            audit["requirements"]["user_client_matrix_after_rollout"],
            "client_evidence_session_mismatch",
        )
        self.assertIn(
            "record mobile/work-Wi-Fi pass evidence with current evidence_session_id=nl-anti-block-2026-06-02",
            audit["remaining_before_goal_complete"],
        )

    def test_complete_matrix_with_stale_current_session_timestamps_is_not_ready(self) -> None:
        matrix = complete_matrix()
        for row in matrix["real_client_checks"]:
            if row.get("network_type") in {"mobile", "work-wifi"}:
                row["checked_at"] = "2026-06-01T23:59:59Z"

        audit = self.build(matrix)

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE")
        self.assertEqual(
            audit["requirements"]["user_client_matrix_after_rollout"],
            "client_evidence_session_mismatch",
        )
        self.assertFalse(
            audit["client_compatibility_matrix"]["current_evidence_session"]["complete"]
        )

    def test_complete_matrix_with_wrong_rollout_transport_is_not_ready(self) -> None:
        matrix = complete_matrix()
        for row in matrix["real_client_checks"]:
            if row.get("network_type") == "mobile":
                row["transport"] = "ws"

        audit = self.build(matrix)

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE")
        self.assertEqual(
            audit["requirements"]["user_client_matrix_after_rollout"],
            "client_evidence_session_mismatch",
        )
        self.assertFalse(
            audit["client_compatibility_matrix"]["current_evidence_session"]["complete"]
        )

    def test_runtime_regression_blocks_production_candidate(self) -> None:
        matrix = complete_matrix()
        missing: list[str] = []
        broken_probe = runtime_probe(missing)
        broken_probe["client_compatibility_endpoint"]["http_code"] = 404

        audit = self.module.build_audit(
            server_evidence_seed=server_seed(),
            matrix=matrix,
            evidence_plan=evidence_plan(missing),
            remote_intake=remote_intake(missing),
            remote_request=remote_request(missing),
            runtime_summary=runtime_summary(missing, complete=True),
            runtime_probe=broken_probe,
            runtime_deploy_plan=runtime_deploy_plan(),
            generated_at="2026-06-02T01:00:00Z",
        )

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_BLOCKED")
        self.assertIn(
            "restore requirement evidence: client_compatibility_runtime_on_nl",
            audit["remaining_before_goal_complete"],
        )

    def test_stale_runtime_probe_blocks_production_candidate(self) -> None:
        matrix = complete_matrix()
        missing: list[str] = []
        stale_probe = runtime_probe(missing)
        stale_probe["checked_at"] = "2026-06-01T23:59:59Z"

        audit = self.module.build_audit(
            server_evidence_seed=server_seed(),
            matrix=matrix,
            evidence_plan=evidence_plan(missing),
            remote_intake=remote_intake(missing),
            remote_request=remote_request(missing),
            runtime_summary=runtime_summary(missing, complete=True),
            runtime_probe=stale_probe,
            runtime_deploy_plan=runtime_deploy_plan(),
            generated_at="2026-06-02T01:00:00Z",
        )

        self.assertEqual(audit["decision"], "PRODUCTION_CANDIDATE_BLOCKED")
        self.assertEqual(audit["requirements"]["runtime_evidence"], "not_proven")
        self.assertFalse(
            audit["client_compatibility_matrix"]["nl_runtime_probe"][
                "current_evidence_session_ok"
            ]
        )
        self.assertIn(
            "restore requirement evidence: runtime_evidence",
            audit["remaining_before_goal_complete"],
        )

    def test_cli_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            paths = {
                "server": tmp / "server.json",
                "matrix": tmp / "matrix.json",
                "plan": tmp / "plan.json",
                "intake": tmp / "intake.json",
                "request": tmp / "request.json",
                "summary": tmp / "summary.json",
                "probe": tmp / "probe.json",
                "deploy": tmp / "deploy.json",
                "audit": tmp / "audit.json",
                "markdown": tmp / "audit.md",
            }
            missing = partial_matrix()["completion_rule"]["missing_requirements"]
            fixtures = {
                "server": server_seed(),
                "matrix": partial_matrix(),
                "plan": evidence_plan(missing),
                "intake": remote_intake(missing),
                "request": remote_request(missing),
                "summary": runtime_summary(missing, complete=False),
                "probe": runtime_probe(missing),
                "deploy": runtime_deploy_plan(),
            }
            for key, payload in fixtures.items():
                paths[key].write_text(json.dumps(payload), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--server-evidence-json",
                        str(paths["server"]),
                        "--matrix",
                        str(paths["matrix"]),
                        "--evidence-plan",
                        str(paths["plan"]),
                        "--remote-intake",
                        str(paths["intake"]),
                        "--remote-request",
                        str(paths["request"]),
                        "--runtime-summary",
                        str(paths["summary"]),
                        "--runtime-probe",
                        str(paths["probe"]),
                        "--runtime-deploy-plan",
                        str(paths["deploy"]),
                        "--json-out",
                        str(paths["audit"]),
                        "--markdown-out",
                        str(paths["markdown"]),
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            audit_exists = paths["audit"].exists()
            markdown_text = paths["markdown"].read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE")
        self.assertTrue(audit_exists)
        self.assertIn("Current Blockers", markdown_text)


if __name__ == "__main__":
    unittest.main()
