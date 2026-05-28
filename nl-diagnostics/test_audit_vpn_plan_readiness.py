#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("audit_vpn_plan_readiness.py")
SPEC = importlib.util.spec_from_file_location("audit_vpn_plan_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules["audit_vpn_plan_readiness"] = audit
SPEC.loader.exec_module(audit)

FRESH_NOW = datetime(2026, 5, 27, 23, 10, tzinfo=timezone.utc)
STALE_NOW = datetime(2026, 5, 28, 2, 30, tzinfo=timezone.utc)


def sample_decision() -> dict:
    return {
        "snapshot": "nl-diagnostics/snapshots/20260527T230246Z",
        "decision": {
            "decision": "observe",
            "confidence": "high",
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "auto_profile_switch_allowed": False,
            "spb_fallback_allowed": False,
        },
        "classification": {
            "transport_status": "healthy",
            "failure_domain": "external_network",
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def sample_history() -> dict:
    return {
        "summary": {
            "snapshot_count": 4,
            "trend": "stable_no_probe_evidence",
            "latest": {
                "snapshot": "20260527T230246Z",
                "target_count": 8,
                "ok_count": 8,
            },
        }
    }


def sample_boot_gap() -> dict:
    return {
        "status": "watch",
        "boot_gap_seconds": 21907,
        "classification": {
            "provider_status": "recent_boot_gap",
            "transport_status": "healthy",
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_provider_packet() -> dict:
    return {
        "packet_type": "provider_watch",
        "snapshot_dir": "nl-diagnostics/snapshots/20260527T230246Z",
        "snapshot_stale": False,
        "nl_write_performed": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_refresh() -> dict:
    return {
        "snapshot": "nl-diagnostics/snapshots/20260527T230246Z",
        "ok": True,
        "summary": {
            "operator_status": "observe",
            "manual_failover_status": "planning_not_active",
            "nl_mutation_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_operator_card() -> dict:
    return {
        "operator": {
            "operator_status": "observe",
            "plain_action": "VPN core is healthy.",
        },
        "current_state": {"blocking_history_trend": "stable_no_probe_evidence"},
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_failover() -> dict:
    return {
        "status": "planning_not_active",
        "summary": {
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_failover_readiness() -> dict:
    return {
        "status": "blocked_no_incident_trigger",
        "manual_probe_allowed": False,
        "manual_switch_allowed": False,
        "summary": {
            "secondary_probe_status": "planning_template",
            "candidate_configured": False,
            "spb_excluded": True,
            "nl_write_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_requirements() -> dict:
    return {
        "status": "requirements_ready_no_candidate",
        "summary": {
            "candidate_configured": False,
            "missing_items": ["NET-01"],
            "blocked_items": [],
            "manual_switch_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_score() -> dict:
    return {
        "status": "missing_candidates",
        "summary": {
            "candidate_count": 0,
            "viable_count": 0,
            "rejected_count": 0,
            "top_candidate_label": "none",
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_flow(status: str = "blocked_missing_candidate") -> dict:
    return {
        "status": status,
        "summary": {
            "candidate_score_status": "missing_candidates",
            "candidate_viable_count": 0,
            "top_candidate_label": "none",
            "secondary_probe_status": "planning_template",
            "candidate_configured": False,
            "manual_probe_allowed": False,
            "manual_switch_allowed": False,
            "requirements_status": "requirements_ready_no_candidate",
            "safe_flags": True,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_manual_drill(status: str = "drill_plan_ready_blocked_no_endpoint") -> dict:
    return {
        "status": status,
        "summary": {
            "manual_probe_allowed": False,
            "manual_switch_allowed": False,
            "candidate_configured": False,
            "endpoint_count": 0,
            "secondary_flow_status": "blocked_missing_candidate",
            "secondary_probe_status": "planning_template",
            "provisioning_plan_status": "provisioning_plan_ready_no_endpoint",
            "test_scope": "single_client",
            "bulk_user_switch_allowed": False,
            "rollback_required": True,
            "safe_flags": True,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_selection_packet(status: str = "selection_packet_ready_no_endpoint") -> dict:
    return {
        "status": status,
        "summary": {
            "recommended_label": "upcloud-fi-hel",
            "backup_label": "ovhcloud-pl-waw",
            "decision_option_count": 3,
            "endpoint_count": 0,
            "shortlist_status": "shortlist_ready_no_endpoint",
            "provisioning_plan_status": "provisioning_plan_ready_no_endpoint",
            "candidate_intake_status": "awaiting_public_candidate_metadata",
            "requirements_status": "requirements_ready_no_candidate",
            "secondary_flow_status": "blocked_missing_candidate",
            "manual_drill_status": "drill_plan_ready_blocked_no_endpoint",
            "external_action_required": True,
            "may_create_endpoint_now": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_intake(status: str = "awaiting_public_candidate_metadata") -> dict:
    return {
        "status": status,
        "summary": {
            "candidate_file": "nl-diagnostics/secondary-exit-candidates.example.json",
            "candidate_score_status": "missing_candidates",
            "candidate_count": 0,
            "viable_count": 0,
            "allowed_field_count": 7,
            "forbidden_material_count": 7,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_provider_shortlist(status: str = "shortlist_ready_no_endpoint") -> dict:
    return {
        "status": status,
        "summary": {
            "shortlist_count": 5,
            "source_count": 9,
            "endpoint_count": 0,
            "candidate_configured": False,
            "invalid_source_refs": [],
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary_provisioning_plan(status: str = "provisioning_plan_ready_no_endpoint") -> dict:
    return {
        "status": status,
        "summary": {
            "shortlist_status": "shortlist_ready_no_endpoint",
            "shortlist_count": 5,
            "preferred_labels": ["upcloud-fi-hel", "ovhcloud-pl-waw", "hetzner-de-or-fi"],
            "endpoint_count": 0,
            "external_action_required": True,
            "candidate_file": "/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json",
            "candidate_intake_status": "awaiting_public_candidate_metadata",
            "requirements_status": "requirements_ready_no_candidate",
            "safe_sources": True,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_local_env(status: str = "watch_root_full_tmpdir_available", tmpdir_writable: bool = True) -> dict:
    return {
        "status": status,
        "summary": {
            "root_status": "critical_full" if status == "watch_root_full_tmpdir_available" else "ok",
            "root_used_percent": 100.0 if status == "watch_root_full_tmpdir_available" else 50.0,
            "root_free_gib": 0.0 if status == "watch_root_full_tmpdir_available" else 10.0,
            "tmp_status": "critical_full" if status == "watch_root_full_tmpdir_available" else "ok",
            "diagnostic_tmpdir": "/mnt/projects/.tmp",
            "diagnostic_tmpdir_writable": tmpdir_writable,
            "recommended_tmpdir_prefix": "TMPDIR=/mnt/projects/.tmp",
            "cleanup_required": status != "ok",
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_local_cleanup_plan(status: str = "manual_cleanup_plan_ready") -> dict:
    return {
        "status": status,
        "summary": {
            "root_status": "critical_full",
            "root_free_gib": 0.0,
            "existing_candidate_count": 2,
            "estimated_reclaim_gib": 1.38,
            "top_candidate_id": "TMP-ANTIGRAVITY-01",
            "cleanup_execute_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "cleanup_execute_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_local_cleanup_packet(status: str = "cleanup_approval_packet_ready") -> dict:
    return {
        "status": status,
        "summary": {
            "root_status": "critical_full",
            "root_free_gib": 0.0,
            "existing_candidate_count": 2,
            "estimated_reclaim_gib": 1.38,
            "first_review_id": "APT-CACHE-01",
            "command_preview_count": 2,
            "approval_required": True,
            "commands_executed": 0,
            "cleanup_execute_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "cleanup_execute_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_symptom_intake(status: str = "symptom_intake_ready_observe") -> dict:
    return {
        "status": status,
        "summary": {
            "decision": "observe",
            "operator_status": "observe",
            "failure_domain": "external_network",
            "transport_status": "healthy",
            "required_field_count": 12,
            "forbidden_material_count": 12,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_transport_probe() -> dict:
    return {
        "status": "healthy",
        "ok_count": 3,
        "port_count": 3,
        "failure_domain_hint": "none",
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_transport_uptime() -> dict:
    return {
        "summary": {
            "status": "stable_healthy",
            "sample_count": 1,
            "latest_status": "healthy",
            "consecutive_non_healthy": 0,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary() -> dict:
    return {
        "status": "planning_template",
        "candidate_configured": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_manifest() -> dict:
    return {
        "nl_write_allowed": False,
        "gap_summary": {
            "accepted_local_delta": 5,
            "missing_local_source": 0,
            "local_name_drift": 0,
        },
        "source_promotion_status": {"deployable_to_nl": False},
        "inactive_integrations": [
            {
                "name": "spb_standalone_xray",
                "enabled": False,
            }
        ],
    }


def sample_preflight() -> dict:
    return {
        "ok": True,
        "deploy_status": "local_ready_but_deploy_blocked",
        "nl_write_allowed": False,
        "checks": [{"name": "manifest_json", "ok": True}],
    }


def sample_inputs() -> dict:
    return {
        "decision": sample_decision(),
        "boot_gap": sample_boot_gap(),
        "provider_packet": sample_provider_packet(),
        "history": sample_history(),
        "refresh": sample_refresh(),
        "operator_card": sample_operator_card(),
        "failover": sample_failover(),
        "failover_readiness": sample_failover_readiness(),
        "secondary_score": sample_secondary_score(),
        "secondary_requirements": sample_secondary_requirements(),
        "secondary_provider_shortlist": sample_secondary_provider_shortlist(),
        "secondary_intake": sample_secondary_intake(),
        "secondary_provisioning_plan": sample_secondary_provisioning_plan(),
        "secondary_flow": sample_secondary_flow(),
        "secondary_manual_drill": sample_secondary_manual_drill(),
        "secondary_selection_packet": sample_secondary_selection_packet(),
        "local_env": sample_local_env(),
        "local_cleanup_plan": sample_local_cleanup_plan(),
        "local_cleanup_packet": sample_local_cleanup_packet(),
        "symptom_intake": sample_symptom_intake(),
        "transport_probe": sample_transport_probe(),
        "transport_uptime": sample_transport_uptime(),
        "secondary": sample_secondary(),
        "manifest": sample_manifest(),
        "preflight": sample_preflight(),
        "approval_text": audit.APPROVAL_PHRASE,
        "report_texts": ["spb_fallback_allowed=false"],
    }


def prepare_root(root: Path) -> None:
    (root / "nl-diagnostics" / "snapshots" / "20260527T230246Z").mkdir(parents=True)
    systemd = root / "infra" / "systemd"
    systemd.mkdir(parents=True)
    (systemd / "x0tta-vpn-nl-transport-uptime.service").write_text(
        "\n".join(
            [
                "[Service]",
                "Type=oneshot",
                "Environment=TMPDIR=/mnt/projects/.tmp",
                "ExecStart=/usr/bin/python3 /mnt/projects/nl-diagnostics/probe_nl_transport_ports.py",
                "ExecStart=/usr/bin/python3 /mnt/projects/nl-diagnostics/record_nl_transport_uptime.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (systemd / "x0tta-vpn-nl-transport-uptime.timer").write_text(
        "\n".join(
            [
                "[Timer]",
                "OnUnitActiveSec=5min",
                "Unit=x0tta-vpn-nl-transport-uptime.service",
                "",
            ]
        ),
        encoding="utf-8",
    )


class VpnPlanReadinessAuditTests(unittest.TestCase):
    def test_default_provider_packet_matches_current_snapshot_bundle(self):
        self.assertEqual(
            audit.DEFAULT_PROVIDER_PACKET.name,
            "provider-incident-packet-20260528T021824Z.json",
        )

    def test_ready_audit_has_future_blocks_but_no_missing_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)

            payload = audit.build_payload(sample_inputs(), root=root, now=FRESH_NOW)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["overall_status"], "ready_local_with_future_blocks")
        self.assertEqual(payload["summary"]["missing"], 0)
        self.assertEqual(payload["summary"]["watch"], 3)
        self.assertGreaterEqual(payload["summary"]["ready_local"], 1)
        self.assertIn("BOOT-01", payload["summary"]["watch_items"])
        self.assertIn("LOCALENV-01", payload["summary"]["watch_items"])
        self.assertIn("LOCALCLEAN-01", payload["summary"]["watch_items"])
        self.assertIn("GATE-01", payload["summary"]["blocked_items"])
        self.assertIn("FAILOVER-02", payload["summary"]["blocked_items"])
        self.assertIn("FAILOVER-03", payload["summary"]["blocked_items"])
        self.assertIn("FAILOVER-06", payload["summary"]["blocked_items"])
        self.assertEqual(payload["summary"]["boot_gap_watch_status"], "watch")
        self.assertEqual(payload["summary"]["provider_packet_type"], "provider_watch")
        self.assertFalse(payload["summary"]["provider_packet_stale"])
        self.assertEqual(payload["summary"]["local_diagnostic_environment_status"], "watch_root_full_tmpdir_available")
        self.assertEqual(payload["summary"]["secondary_provider_shortlist_status"], "shortlist_ready_no_endpoint")
        self.assertEqual(payload["summary"]["secondary_provider_shortlist_count"], 5)
        self.assertEqual(payload["summary"]["secondary_provider_shortlist_endpoint_count"], 0)
        self.assertEqual(payload["summary"]["secondary_candidate_intake_status"], "awaiting_public_candidate_metadata")
        self.assertEqual(payload["summary"]["secondary_provisioning_plan_status"], "provisioning_plan_ready_no_endpoint")
        self.assertTrue(payload["summary"]["secondary_provisioning_external_action_required"])
        self.assertEqual(payload["summary"]["secondary_provisioning_endpoint_count"], 0)
        self.assertEqual(payload["summary"]["secondary_exit_flow_status"], "blocked_missing_candidate")
        self.assertFalse(payload["summary"]["secondary_exit_flow_manual_switch_allowed"])
        self.assertEqual(payload["summary"]["secondary_manual_drill_status"], "drill_plan_ready_blocked_no_endpoint")
        self.assertEqual(payload["summary"]["secondary_manual_drill_test_scope"], "single_client")
        self.assertTrue(payload["summary"]["secondary_manual_drill_rollback_required"])
        self.assertEqual(payload["summary"]["secondary_selection_packet_status"], "selection_packet_ready_no_endpoint")
        self.assertEqual(payload["summary"]["secondary_selection_recommended_label"], "upcloud-fi-hel")
        self.assertEqual(payload["summary"]["secondary_selection_backup_label"], "ovhcloud-pl-waw")
        self.assertEqual(payload["summary"]["secondary_selection_option_count"], 3)
        self.assertFalse(payload["summary"]["secondary_selection_may_create_endpoint_now"])
        self.assertTrue(payload["summary"]["local_tmpdir_writable"])
        self.assertEqual(payload["summary"]["local_root_cleanup_plan_status"], "manual_cleanup_plan_ready")
        self.assertFalse(payload["summary"]["local_root_cleanup_execute_allowed"])
        self.assertEqual(payload["summary"]["local_root_cleanup_approval_packet_status"], "cleanup_approval_packet_ready")
        self.assertTrue(payload["summary"]["local_root_cleanup_approval_required"])
        self.assertEqual(payload["summary"]["local_root_cleanup_commands_executed"], 0)
        self.assertEqual(payload["summary"]["incident_symptom_intake_status"], "symptom_intake_ready_observe")
        self.assertEqual(payload["summary"]["incident_symptom_required_fields"], 12)
        self.assertEqual(payload["summary"]["incident_symptom_forbidden_material"], 12)
        self.assertEqual(payload["summary"]["transport_probe_status"], "healthy")
        self.assertEqual(payload["summary"]["transport_uptime_status"], "stable_healthy")
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_degraded_transport_probe_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["transport_probe"] = {
                **sample_transport_probe(),
                "status": "degraded",
                "ok_count": 2,
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        transport = next(item for item in payload["items"] if item["id"] == "TRANSPORT-01")
        self.assertEqual(transport["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_missing_project_tmpdir_makes_readiness_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["local_env"] = sample_local_env("missing_writable_temp", tmpdir_writable=False)

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        local_env = next(item for item in payload["items"] if item["id"] == "LOCALENV-01")
        self.assertEqual(local_env["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_cleanup_plan_with_execution_enabled_makes_readiness_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["local_cleanup_plan"] = {
                **sample_local_cleanup_plan(),
                "cleanup_execute_allowed": True,
                "summary": {
                    **sample_local_cleanup_plan()["summary"],
                    "cleanup_execute_allowed": True,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        cleanup_item = next(item for item in payload["items"] if item["id"] == "LOCALCLEAN-01")
        self.assertEqual(cleanup_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_cleanup_packet_with_commands_executed_makes_readiness_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["local_cleanup_packet"] = {
                **sample_local_cleanup_packet(),
                "summary": {
                    **sample_local_cleanup_packet()["summary"],
                    "commands_executed": 1,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        packet_item = next(item for item in payload["items"] if item["id"] == "LOCALCLEAN-02")
        self.assertEqual(packet_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_symptom_intake_with_unsafe_flags_makes_readiness_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["symptom_intake"] = {
                **sample_symptom_intake("symptom_intake_unsafe_flags"),
                "spb_fallback_allowed": True,
                "summary": {
                    **sample_symptom_intake()["summary"],
                    "spb_fallback_allowed": True,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        symptom_item = next(item for item in payload["items"] if item["id"] == "INCIDENT-01")
        self.assertEqual(symptom_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_secondary_flow_with_unsafe_flags_makes_readiness_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["secondary_flow"] = {
                **sample_secondary_flow("unsafe_flags"),
                "spb_fallback_allowed": True,
                "summary": {
                    **sample_secondary_flow()["summary"],
                    "safe_flags": False,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        flow_item = next(item for item in payload["items"] if item["id"] == "FAILOVER-06")
        self.assertEqual(flow_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_secondary_intake_with_unsafe_flags_makes_readiness_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["secondary_intake"] = {
                **sample_secondary_intake("unsafe_flags"),
                "spb_fallback_allowed": True,
                "summary": {
                    **sample_secondary_intake()["summary"],
                    "spb_fallback_allowed": True,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        intake_item = next(item for item in payload["items"] if item["id"] == "FAILOVER-07")
        self.assertEqual(intake_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_secondary_provider_shortlist_with_endpoint_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["secondary_provider_shortlist"] = {
                **sample_secondary_provider_shortlist(),
                "summary": {
                    **sample_secondary_provider_shortlist()["summary"],
                    "endpoint_count": 1,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        shortlist_item = next(item for item in payload["items"] if item["id"] == "FAILOVER-08")
        self.assertEqual(shortlist_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_secondary_provisioning_plan_with_endpoint_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["secondary_provisioning_plan"] = {
                **sample_secondary_provisioning_plan(),
                "summary": {
                    **sample_secondary_provisioning_plan()["summary"],
                    "endpoint_count": 1,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        provisioning_item = next(item for item in payload["items"] if item["id"] == "FAILOVER-09")
        self.assertEqual(provisioning_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_secondary_manual_drill_without_rollback_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["secondary_manual_drill"] = {
                **sample_secondary_manual_drill(),
                "summary": {
                    **sample_secondary_manual_drill()["summary"],
                    "rollback_required": False,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        drill_item = next(item for item in payload["items"] if item["id"] == "FAILOVER-10")
        self.assertEqual(drill_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_secondary_selection_packet_with_unsafe_flags_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["secondary_selection_packet"] = {
                **sample_secondary_selection_packet("selection_packet_unsafe_flags"),
                "spb_fallback_allowed": True,
                "summary": {
                    **sample_secondary_selection_packet()["summary"],
                    "spb_fallback_allowed": True,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        selection_item = next(item for item in payload["items"] if item["id"] == "FAILOVER-11")
        self.assertEqual(selection_item["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_degraded_uptime_history_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["transport_uptime"] = {
                **sample_transport_uptime(),
                "summary": {
                    **sample_transport_uptime()["summary"],
                    "status": "watch",
                    "latest_status": "degraded",
                    "consecutive_non_healthy": 1,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        uptime_item = next(item for item in payload["items"] if item["id"] == "UPTIME-01")
        self.assertEqual(uptime_item["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_stale_snapshot_chain_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)

            payload = audit.build_payload(sample_inputs(), root=root, now=STALE_NOW)

        evidence = next(item for item in payload["items"] if item["id"] == "EVIDENCE-01")
        self.assertEqual(evidence["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_stale_provider_packet_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["provider_packet"] = {
                **sample_provider_packet(),
                "snapshot_stale": True,
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        provider = next(item for item in payload["items"] if item["id"] == "PROVIDER-01")
        self.assertEqual(provider["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_spb_true_marker_makes_audit_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["report_texts"] = ["spb_fallback_allowed=true"]

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        spb = next(item for item in payload["items"] if item["id"] == "SPB-01")
        self.assertEqual(spb["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_spb_true_marker_with_colon_makes_audit_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["report_texts"] = ['"spb_fallback_allowed": true']

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        spb = next(item for item in payload["items"] if item["id"] == "SPB-01")
        self.assertEqual(spb["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_missing_approval_phrase_keeps_future_write_gate_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["approval_text"] = "different text"

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        gate = next(item for item in payload["items"] if item["id"] == "GATE-01")
        self.assertEqual(gate["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_markdown_renders_matrix_and_no_write_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            payload = audit.build_payload(sample_inputs(), root=root, now=FRESH_NOW)

        markdown = audit.render_markdown(payload)

        self.assertIn("Readiness Matrix", markdown)
        self.assertIn("blocked_future_approval", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
