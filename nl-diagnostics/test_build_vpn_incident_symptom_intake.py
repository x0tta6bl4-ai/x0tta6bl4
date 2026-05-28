#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_vpn_incident_symptom_intake.py")
SPEC = importlib.util.spec_from_file_location("build_vpn_incident_symptom_intake", MODULE_PATH)
assert SPEC and SPEC.loader
intake = importlib.util.module_from_spec(SPEC)
sys.modules["build_vpn_incident_symptom_intake"] = intake
SPEC.loader.exec_module(intake)


def decision_report(decision_name: str = "observe") -> dict:
    return {
        "decision": {
            "decision": decision_name,
            "confidence": "high",
            "nl_mutation_allowed": False,
            "auto_profile_switch_allowed": False,
            "spb_fallback_allowed": False,
        },
        "classification": {
            "transport_status": "healthy",
            "failure_domain": "external_network",
            "provider_status": "advisory",
        },
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def operator_card(status: str = "observe") -> dict:
    return {
        "operator": {
            "operator_status": status,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def blocking_history() -> dict:
    return {
        "summary": {
            "trend": "stable_no_probe_evidence",
            "snapshot_count": 7,
            "latest": {
                "ok_count": 8,
                "target_count": 8,
            },
        }
    }


def transport_probe() -> dict:
    return {
        "status": "healthy",
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def failover_readiness() -> dict:
    return {
        "status": "blocked_no_incident_trigger",
        "manual_probe_allowed": False,
        "manual_switch_allowed": False,
        "summary": {
            "nl_write_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class VpnIncidentSymptomIntakeTests(unittest.TestCase):
    def test_observe_state_builds_safe_intake(self):
        payload = intake.build_payload(
            decision_report=decision_report(),
            operator_card=operator_card(),
            blocking_history=blocking_history(),
            transport_probe=transport_probe(),
            failover_readiness=failover_readiness(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "symptom_intake_ready_observe")
        self.assertIn("profile_label_without_uri", payload["required_fields"])
        self.assertIn("direct_without_vpn_result", payload["required_fields"])
        self.assertIn("vpn_result", payload["required_fields"])
        self.assertIn("raw VPN URI", payload["forbidden_material"])
        self.assertIn("full screenshots with private data", payload["forbidden_material"])
        self.assertIn("core_transport", payload["triage_groups"])
        self.assertEqual(payload["summary"]["required_field_count"], len(payload["required_fields"]))
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_incident_decision_is_ready_but_still_no_failover(self):
        payload = intake.build_payload(
            decision_report=decision_report("provider_ticket"),
            operator_card=operator_card("provider_ticket"),
            blocking_history=blocking_history(),
            transport_probe=transport_probe(),
            failover_readiness=failover_readiness(),
        )

        self.assertEqual(payload["status"], "symptom_intake_ready_incident")
        self.assertFalse(payload["summary"]["automatic_failover_allowed"])

    def test_unsafe_flags_fail_intake(self):
        bad_decision = decision_report()
        bad_decision["spb_fallback_allowed"] = True

        payload = intake.build_payload(
            decision_report=bad_decision,
            operator_card=operator_card(),
            blocking_history=blocking_history(),
            transport_probe=transport_probe(),
            failover_readiness=failover_readiness(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "symptom_intake_unsafe_flags")

    def test_markdown_contains_secret_warning_and_no_write_notice(self):
        payload = intake.build_payload(
            decision_report=decision_report(),
            operator_card=operator_card(),
            blocking_history=blocking_history(),
            transport_probe=transport_probe(),
            failover_readiness=failover_readiness(),
        )

        markdown = intake.render_markdown(payload)

        self.assertIn("Forbidden Material", markdown)
        self.assertIn("Safe Local Steps", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
