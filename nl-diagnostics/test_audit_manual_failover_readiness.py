#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("audit_manual_failover_readiness.py")
SPEC = importlib.util.spec_from_file_location("audit_manual_failover_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
gate = importlib.util.module_from_spec(SPEC)
sys.modules["audit_manual_failover_readiness"] = gate
SPEC.loader.exec_module(gate)


def decision(decision_name: str = "observe", failure_domain: str = "external_network") -> dict:
    return {
        "decision": {"decision": decision_name, "confidence": "high"},
        "classification": {
            "overall_status": "advisory",
            "transport_status": "healthy",
            "failure_domain": failure_domain,
            "provider_status": "recent_boot_gap",
        },
    }


def failover() -> dict:
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


def secondary(status: str = "planning_template", configured: bool = False) -> dict:
    return {
        "status": status,
        "candidate_configured": configured,
        "candidate": {
            "label": "secondary-1" if configured else "secondary-placeholder",
            "provider": "new-provider" if configured else "TBD",
            "region": "new-region" if configured else "TBD",
            "host": "203.0.113.10" if configured else "UNCONFIGURED",
            "tcp_ports": [443] if configured else [],
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class ManualFailoverReadinessTests(unittest.TestCase):
    def test_current_observe_state_blocks_manual_switch(self):
        payload = gate.build_payload(decision(), failover(), secondary())

        self.assertEqual(payload["status"], "blocked_no_incident_trigger")
        self.assertFalse(payload["manual_probe_allowed"])
        self.assertFalse(payload["manual_switch_allowed"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_provider_ticket_without_secondary_blocks_missing_secondary(self):
        payload = gate.build_payload(decision("provider_ticket", "provider_host"), failover(), secondary())

        self.assertEqual(payload["status"], "blocked_missing_secondary")
        secondary_gate = next(row for row in payload["gates"] if row["id"] == "SECONDARY-01")
        self.assertEqual(secondary_gate["status"], gate.BLOCKED)

    def test_reachable_secondary_allows_profile_test_but_not_switch(self):
        payload = gate.build_payload(
            decision("provider_ticket", "provider_host"),
            failover(),
            secondary("endpoint_reachable_profile_unverified", True),
        )

        self.assertEqual(payload["status"], "ready_for_profile_test_only")
        self.assertTrue(payload["manual_probe_allowed"])
        self.assertFalse(payload["manual_switch_allowed"])

    def test_healthy_secondary_allows_manual_switch_only(self):
        payload = gate.build_payload(
            decision("provider_ticket", "provider_host"),
            failover(),
            secondary("healthy", True),
        )

        self.assertEqual(payload["status"], "ready_for_manual_switch")
        self.assertTrue(payload["manual_switch_allowed"])
        self.assertFalse(payload["automatic_failover_allowed"])

    def test_spb_marker_blocks_readiness(self):
        probe = secondary("healthy", True)
        probe["candidate"]["provider"] = "spb"

        payload = gate.build_payload(decision("provider_ticket", "provider_host"), failover(), probe)

        spb_gate = next(row for row in payload["gates"] if row["id"] == "SPB-01")
        self.assertEqual(spb_gate["status"], gate.BLOCKED)
        self.assertFalse(payload["manual_switch_allowed"])

    def test_markdown_states_no_writes(self):
        payload = gate.build_payload(decision(), failover(), secondary())
        markdown = gate.render_markdown(payload)

        self.assertIn("manual_switch_allowed=false", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
