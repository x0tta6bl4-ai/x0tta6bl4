#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_provisioning_plan.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_provisioning_plan", MODULE_PATH)
assert SPEC and SPEC.loader
provisioning = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_provisioning_plan"] = provisioning
SPEC.loader.exec_module(provisioning)


def provider_shortlist() -> dict:
    return {
        "status": "shortlist_ready_no_endpoint",
        "summary": {
            "shortlist_count": 3,
            "endpoint_count": 0,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "shortlist": [
            {"label": "upcloud-fi-hel", "country": "Finland", "priority": 1, "status": "shortlist_ready_no_endpoint"},
            {"label": "ovhcloud-pl-waw", "country": "Poland", "priority": 2, "status": "shortlist_ready_no_endpoint"},
            {"label": "hetzner-de-or-fi", "country": "Germany", "priority": 3, "status": "shortlist_ready_no_endpoint"},
        ],
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def candidate_intake(status: str = "awaiting_public_candidate_metadata") -> dict:
    return {
        "status": status,
        "summary": {
            "candidate_file": "/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json",
            "allowed_field_count": 7,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def requirements(status: str = "requirements_ready_no_candidate") -> dict:
    return {
        "status": status,
        "summary": {
            "missing_items": ["NET-01"],
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class SecondaryExitProvisioningPlanTests(unittest.TestCase):
    def test_ready_plan_requires_external_action_and_no_endpoint(self):
        payload = provisioning.build_payload(
            provider_shortlist=provider_shortlist(),
            candidate_intake=candidate_intake(),
            requirements=requirements(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "provisioning_plan_ready_no_endpoint")
        self.assertTrue(payload["summary"]["external_action_required"])
        self.assertEqual(payload["summary"]["endpoint_count"], 0)
        self.assertEqual(payload["summary"]["preferred_labels"][0], "upcloud-fi-hel")
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])
        self.assertFalse(payload["automatic_failover_allowed"])

    def test_unsafe_source_flags_fail_plan(self):
        bad_shortlist = provider_shortlist()
        bad_shortlist["spb_fallback_allowed"] = True

        payload = provisioning.build_payload(
            provider_shortlist=bad_shortlist,
            candidate_intake=candidate_intake(),
            requirements=requirements(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "provisioning_plan_needs_attention")
        self.assertFalse(payload["summary"]["safe_sources"])

    def test_existing_endpoint_keeps_plan_attention_only(self):
        shortlist = provider_shortlist()
        shortlist["summary"]["endpoint_count"] = 1

        payload = provisioning.build_payload(
            provider_shortlist=shortlist,
            candidate_intake=candidate_intake(),
            requirements=requirements(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "provisioning_plan_needs_attention")

    def test_markdown_contains_forbidden_material_and_no_write_notice(self):
        payload = provisioning.build_payload(
            provider_shortlist=provider_shortlist(),
            candidate_intake=candidate_intake(),
            requirements=requirements(),
        )

        markdown = provisioning.render_markdown(payload)

        self.assertIn("Forbidden Material", markdown)
        self.assertIn("provider API token", markdown)
        self.assertIn("No NL or SPB writes", markdown)
        self.assertIn("score_secondary_exit_candidates.py", markdown)


if __name__ == "__main__":
    unittest.main()
