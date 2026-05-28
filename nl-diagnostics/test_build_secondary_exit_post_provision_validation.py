#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_post_provision_validation.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_post_provision_validation", MODULE_PATH)
assert SPEC and SPEC.loader
validation = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_post_provision_validation"] = validation
SPEC.loader.exec_module(validation)


def public_template(endpoint_count: int = 0) -> dict:
    return {
        "status": "public_metadata_template_ready_no_endpoint",
        "summary": {
            "selected_label": "upcloud-fi-hel",
            "endpoint_count": endpoint_count,
            "candidate_file_update_allowed": endpoint_count > 0,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidate_file_template": {
            "candidates": [
                {
                    "label": "upcloud-fi-hel",
                    "provider": "UpCloud",
                    "region": "Helsinki",
                    "host": "FILL_PUBLIC_IPV4_OR_HOST_AFTER_PROVISIONING",
                    "tcp_ports": [443],
                }
            ]
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def candidate_score(viable_count: int = 0) -> dict:
    candidates = []
    if viable_count:
        candidates = [
            {
                "label": "upcloud-fi-hel",
                "provider": "UpCloud",
                "region": "Helsinki",
                "host": "8.8.8.8",
                "tcp_ports": [443],
                "score": 85,
                "viable": True,
                "issues": [],
            }
        ]
    return {
        "status": "candidate_pool_ready" if viable_count else "missing_candidates",
        "summary": {
            "candidate_count": viable_count,
            "viable_count": viable_count,
            "top_candidate_label": "upcloud-fi-hel" if viable_count else "none",
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidates": candidates,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def secondary_probe(status: str = "planning_template", configured: bool = False) -> dict:
    return {
        "status": status,
        "candidate_configured": configured,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def failover_readiness(probe_allowed: bool = False, switch_allowed: bool = False) -> dict:
    return {
        "status": "blocked_no_incident_trigger" if not probe_allowed else "ready_for_profile_test_only",
        "manual_probe_allowed": probe_allowed,
        "manual_switch_allowed": switch_allowed,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def secondary_flow() -> dict:
    return {
        "status": "blocked_missing_candidate",
        "summary": {
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def manual_drill() -> dict:
    return {
        "status": "drill_plan_ready_blocked_no_endpoint",
        "summary": {
            "bulk_user_switch_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class SecondaryExitPostProvisionValidationTests(unittest.TestCase):
    def test_waiting_endpoint_state_is_safe_and_blocks_probe_generation(self):
        payload = validation.build_payload(
            public_template=public_template(),
            candidate_score=candidate_score(),
            secondary_probe=secondary_probe(),
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "post_provision_validation_ready_waiting_endpoint")
        self.assertFalse(payload["summary"]["can_generate_probe_config"])
        self.assertFalse(payload["summary"]["can_run_public_probe"])
        self.assertFalse(payload["summary"]["manual_switch_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_viable_candidate_allows_probe_config_generation_only(self):
        payload = validation.build_payload(
            public_template=public_template(endpoint_count=1),
            candidate_score=candidate_score(viable_count=1),
            secondary_probe=secondary_probe(),
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertEqual(payload["status"], "post_provision_validation_ready_for_probe_config")
        self.assertTrue(payload["summary"]["can_generate_probe_config"])
        self.assertIn("--host 8.8.8.8", payload["safe_commands"]["generate_probe_config"])
        self.assertFalse(payload["summary"]["test_client_allowed"])

    def test_reachable_endpoint_without_incident_does_not_allow_switch(self):
        payload = validation.build_payload(
            public_template=public_template(endpoint_count=1),
            candidate_score=candidate_score(viable_count=1),
            secondary_probe=secondary_probe("endpoint_reachable_profile_unverified", configured=True),
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertEqual(payload["status"], "post_provision_validation_endpoint_ready_no_incident")
        self.assertTrue(payload["summary"]["can_run_public_probe"])
        self.assertFalse(payload["summary"]["manual_switch_allowed"])

    def test_unsafe_flags_fail_validation(self):
        bad_score = candidate_score()
        bad_score["spb_fallback_allowed"] = True

        payload = validation.build_payload(
            public_template=public_template(),
            candidate_score=bad_score,
            secondary_probe=secondary_probe(),
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "post_provision_validation_unsafe_flags")

    def test_markdown_contains_safe_commands_and_blocked_actions(self):
        payload = validation.build_payload(
            public_template=public_template(),
            candidate_score=candidate_score(),
            secondary_probe=secondary_probe(),
            failover_readiness=failover_readiness(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        markdown = validation.render_markdown(payload)

        self.assertIn("score_secondary_exit_candidates.py", markdown)
        self.assertIn("probe_secondary_exit.py", markdown)
        self.assertIn("Blocked Actions", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
