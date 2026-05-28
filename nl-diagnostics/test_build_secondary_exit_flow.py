#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_flow.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_flow", MODULE_PATH)
assert SPEC and SPEC.loader
flow = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_flow"] = flow
SPEC.loader.exec_module(flow)


def candidate_score(status: str = "missing_candidates", viable_count: int = 0) -> dict:
    rows = []
    if viable_count:
        rows = [
            {
                "label": "secondary-a",
                "provider": "new-provider",
                "region": "new-region",
                "host": "8.8.8.8",
                "tcp_ports": [443],
                "score": 85,
                "viable": True,
                "issues": [],
            }
        ]
    return {
        "status": status,
        "summary": {
            "candidate_count": viable_count,
            "viable_count": viable_count,
            "rejected_count": 0,
            "top_candidate_label": "secondary-a" if viable_count else "none",
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidates": rows,
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


def failover_readiness(manual_probe_allowed: bool = False, manual_switch_allowed: bool = False) -> dict:
    return {
        "status": "blocked_no_incident_trigger" if not manual_probe_allowed else "ready_for_profile_test_only",
        "manual_probe_allowed": manual_probe_allowed,
        "manual_switch_allowed": manual_switch_allowed,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def requirements() -> dict:
    return {
        "status": "requirements_ready_no_candidate",
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


class SecondaryExitFlowTests(unittest.TestCase):
    def test_missing_candidate_blocks_flow_without_failure(self):
        payload = flow.build_payload(
            candidate_score(),
            secondary_probe(),
            failover_readiness(),
            requirements(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "blocked_missing_candidate")
        self.assertEqual(payload["summary"]["candidate_viable_count"], 0)
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])
        candidate_phase = next(row for row in payload["phases"] if row["id"] == "CANDIDATE-01")
        self.assertEqual(candidate_phase["status"], flow.BLOCKED)

    def test_viable_candidate_needs_probe_config(self):
        payload = flow.build_payload(
            candidate_score("candidate_pool_ready", 1),
            secondary_probe(),
            failover_readiness(),
            requirements(),
        )

        self.assertEqual(payload["status"], "candidate_ready_probe_config_needed")
        self.assertEqual(payload["summary"]["top_candidate_label"], "secondary-a")
        self.assertIn("--host 8.8.8.8", payload["safe_commands"]["generate_probe_config"])

    def test_endpoint_reachable_waits_for_incident_trigger(self):
        payload = flow.build_payload(
            candidate_score("candidate_pool_ready", 1),
            secondary_probe("endpoint_reachable_profile_unverified", configured=True),
            failover_readiness(),
            requirements(),
        )

        self.assertEqual(payload["status"], "endpoint_ready_but_no_incident_trigger")
        probe_phase = next(row for row in payload["phases"] if row["id"] == "PROBE-01")
        self.assertEqual(probe_phase["status"], flow.PASS)
        switch_phase = next(row for row in payload["phases"] if row["id"] == "SWITCH-01")
        self.assertEqual(switch_phase["status"], flow.BLOCKED)

    def test_healthy_secondary_with_switch_allowed_is_ready(self):
        payload = flow.build_payload(
            candidate_score("candidate_pool_ready", 1),
            secondary_probe("healthy", configured=True),
            failover_readiness(manual_probe_allowed=True, manual_switch_allowed=True),
            requirements(),
        )

        self.assertEqual(payload["status"], "ready_for_manual_switch")
        self.assertTrue(payload["summary"]["manual_switch_allowed"])

    def test_unsafe_flags_make_report_not_ok(self):
        score = candidate_score()
        score["spb_fallback_allowed"] = True

        payload = flow.build_payload(score, secondary_probe(), failover_readiness(), requirements())

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "unsafe_flags")

    def test_markdown_contains_safe_commands_and_no_write_notice(self):
        payload = flow.build_payload(
            candidate_score(),
            secondary_probe(),
            failover_readiness(),
            requirements(),
        )

        markdown = flow.render_markdown(payload)

        self.assertIn("create_secondary_exit_config.py", markdown)
        self.assertIn("probe_secondary_exit.py", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
