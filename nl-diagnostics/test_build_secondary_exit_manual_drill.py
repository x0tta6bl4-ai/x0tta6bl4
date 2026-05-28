#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_manual_drill.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_manual_drill", MODULE_PATH)
assert SPEC and SPEC.loader
drill = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_manual_drill"] = drill
SPEC.loader.exec_module(drill)


def failover_readiness(probe_allowed: bool = False, switch_allowed: bool = False) -> dict:
    return {
        "status": "blocked_no_incident_trigger" if not probe_allowed else "ready_for_profile_test_only",
        "manual_probe_allowed": probe_allowed,
        "manual_switch_allowed": switch_allowed,
        "summary": {
            "nl_write_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def secondary_flow(
    status: str = "blocked_missing_candidate",
    candidate_configured: bool = False,
    secondary_probe_status: str = "planning_template",
) -> dict:
    return {
        "status": status,
        "summary": {
            "candidate_configured": candidate_configured,
            "secondary_probe_status": secondary_probe_status,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def provisioning(endpoint_count: int = 0) -> dict:
    return {
        "status": "provisioning_plan_ready_no_endpoint",
        "summary": {
            "endpoint_count": endpoint_count,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class SecondaryExitManualDrillTests(unittest.TestCase):
    def test_current_no_endpoint_state_is_safe_but_blocked(self):
        payload = drill.build_payload(
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            provisioning_plan=provisioning(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "drill_plan_ready_blocked_no_endpoint")
        self.assertFalse(payload["summary"]["manual_probe_allowed"])
        self.assertFalse(payload["summary"]["bulk_user_switch_allowed"])
        self.assertTrue(payload["summary"]["rollback_required"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_probe_allowed_state_is_test_client_only(self):
        payload = drill.build_payload(
            failover_readiness=failover_readiness(probe_allowed=True),
            secondary_flow=secondary_flow(
                "endpoint_ready_but_no_incident_trigger",
                candidate_configured=True,
                secondary_probe_status="endpoint_reachable_profile_unverified",
            ),
            provisioning_plan=provisioning(endpoint_count=1),
        )

        self.assertEqual(payload["status"], "drill_ready_for_test_client_only")
        self.assertTrue(payload["summary"]["manual_probe_allowed"])
        self.assertFalse(payload["summary"]["manual_switch_allowed"])

    def test_unsafe_flags_fail_drill(self):
        bad_flow = secondary_flow()
        bad_flow["spb_fallback_allowed"] = True

        payload = drill.build_payload(
            failover_readiness=failover_readiness(),
            secondary_flow=bad_flow,
            provisioning_plan=provisioning(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "unsafe_flags")

    def test_markdown_contains_test_scope_rollback_and_no_write_notice(self):
        payload = drill.build_payload(
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            provisioning_plan=provisioning(),
        )

        markdown = drill.render_markdown(payload)

        self.assertIn("single_client", markdown)
        self.assertIn("Rollback Checks", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
