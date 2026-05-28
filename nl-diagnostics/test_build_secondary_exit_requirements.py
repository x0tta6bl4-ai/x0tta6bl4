#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_requirements.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_requirements", MODULE_PATH)
assert SPEC and SPEC.loader
requirements = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_requirements"] = requirements
SPEC.loader.exec_module(requirements)


def decision() -> dict:
    return {
        "decision": {"decision": "observe", "confidence": "high"},
        "classification": {
            "overall_status": "advisory",
            "transport_status": "healthy",
            "failure_domain": "external_network",
        },
    }


def failover_readiness(spb_excluded: bool = True) -> dict:
    return {
        "status": "blocked_no_incident_trigger",
        "manual_probe_allowed": False,
        "manual_switch_allowed": False,
        "summary": {
            "spb_excluded": spb_excluded,
        },
    }


def secondary(configured: bool = False, status: str = "planning_template") -> dict:
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
    }


def candidate_score(status: str = "missing_candidates", viable_count: int = 0) -> dict:
    return {
        "status": status,
        "summary": {
            "candidate_count": viable_count,
            "viable_count": viable_count,
            "top_candidate_label": "candidate-a" if viable_count else "none",
        },
    }


class SecondaryExitRequirementsTests(unittest.TestCase):
    def test_current_state_is_ready_requirements_but_missing_candidate(self):
        payload = requirements.build_payload(decision(), failover_readiness(), secondary(), candidate_score())

        self.assertEqual(payload["status"], "requirements_ready_no_candidate")
        self.assertEqual(payload["summary"]["missing_items"], ["NET-01"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_configured_candidate_clears_missing_requirement(self):
        payload = requirements.build_payload(
            decision(),
            failover_readiness(),
            secondary(configured=True, status="endpoint_reachable_profile_unverified"),
            candidate_score("candidate_pool_ready", 1),
        )

        self.assertEqual(payload["status"], "requirements_ready_with_candidate")
        self.assertEqual(payload["summary"]["missing_items"], [])

    def test_spb_policy_gap_blocks_requirements(self):
        payload = requirements.build_payload(decision(), failover_readiness(spb_excluded=False), secondary(), candidate_score())

        self.assertEqual(payload["status"], "requirements_need_attention")
        self.assertIn("SEL-01", payload["summary"]["blocked_items"])

    def test_markdown_lists_allowed_and_forbidden_material(self):
        payload = requirements.build_payload(decision(), failover_readiness(), secondary(), candidate_score())
        markdown = requirements.render_markdown(payload)

        self.assertIn("Allowed Metadata", markdown)
        self.assertIn("Forbidden Material", markdown)
        self.assertIn("raw VPN URI", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
