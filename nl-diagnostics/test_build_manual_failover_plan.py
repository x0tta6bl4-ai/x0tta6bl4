#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_manual_failover_plan.py")
SPEC = importlib.util.spec_from_file_location("build_manual_failover_plan", MODULE_PATH)
assert SPEC and SPEC.loader
failover = importlib.util.module_from_spec(SPEC)
sys.modules["build_manual_failover_plan"] = failover
SPEC.loader.exec_module(failover)


def decision(decision_name="observe", failure_domain="external_network"):
    return {
        "decision": {"decision": decision_name, "confidence": "high"},
        "classification": {
            "overall_status": "advisory",
            "transport_status": "healthy",
            "failure_domain": failure_domain,
            "provider_status": "recent_boot_gap",
        },
    }


def backlog():
    return {
        "summary": {
            "blocking_history_trend": "stable_no_probe_evidence",
        }
    }


class ManualFailoverPlanTests(unittest.TestCase):
    def test_observe_status_is_planning_not_active(self):
        payload = failover.build_payload(decision(), backlog())

        self.assertEqual(payload["status"], "planning_not_active")
        self.assertFalse(payload["spb_fallback_allowed"])
        self.assertFalse(payload["automatic_failover_allowed"])
        self.assertFalse(payload["nl_mutation_allowed"])

    def test_provider_failure_becomes_manual_failover_candidate(self):
        payload = failover.build_payload(decision("provider_ticket", "provider_host"), backlog())

        self.assertEqual(payload["status"], "manual_failover_candidate")
        gate_text = "\n".join(gate["gate"] for gate in payload["activation_gates"])
        self.assertIn("explicit manual approval", gate_text)

    def test_spb_is_explicitly_blocked(self):
        payload = failover.build_payload(decision(), backlog())
        markdown = failover.render_markdown(payload)

        self.assertIn("Use a new secondary exit node, not SPB", markdown)
        self.assertIn("do not use SPB as fallback", markdown)
        self.assertIn("No NL or SPB writes", markdown)

    def test_plan_references_secondary_probe_template(self):
        payload = failover.build_payload(decision(), backlog())
        markdown = failover.render_markdown(payload)

        self.assertEqual(payload["local_probe"]["script"], "nl-diagnostics/probe_secondary_exit.py")
        self.assertEqual(payload["local_probe"]["config_generator"], "nl-diagnostics/create_secondary_exit_config.py")
        self.assertEqual(payload["local_probe"]["placeholder_status"], "planning_template")
        self.assertIn("probe_secondary_exit.py", markdown)


if __name__ == "__main__":
    unittest.main()
