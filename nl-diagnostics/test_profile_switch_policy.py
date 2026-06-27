#!/usr/bin/env python3
"""Tests for profile_switch_policy.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).with_name("profile_switch_policy.py")
SPEC = importlib.util.spec_from_file_location("profile_switch_policy", MODULE_PATH)
assert SPEC and SPEC.loader
policy = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy
SPEC.loader.exec_module(policy)


def switch_state(**overrides):
    state = {
        "runtime_mode": "anti_block",
        "runtime_recommended_action": "switch_profile",
        "overall_status": "advisory",
        "failure_domain": "external_network",
        "transport_status": "healthy",
        "provider_status": "historical_incident",
    }
    state.update(overrides)
    return state


class ProfileSwitchPolicyTests(unittest.TestCase):
    def test_observe_when_runtime_does_not_request_switch(self):
        decision = policy.decide_profile_switch(
            {"runtime_recommended_action": "observe"},
            snapshot_fresh=True,
        )

        self.assertEqual(decision.decision, "observe")
        self.assertFalse(decision.automatic_allowed)
        self.assertFalse(decision.manual_review_required)

    def test_switch_profile_is_manual_review_when_transport_is_healthy(self):
        decision = policy.decide_profile_switch(switch_state(), snapshot_fresh=True)

        self.assertEqual(decision.decision, "manual_profile_review")
        self.assertFalse(decision.automatic_allowed)
        self.assertFalse(decision.manual_allowed)
        self.assertTrue(decision.manual_review_required)
        self.assertTrue(decision.requires_fresh_snapshot)
        self.assertFalse(decision.nl_mutation_allowed)

    def test_stale_snapshot_blocks_switch_review(self):
        decision = policy.decide_profile_switch(switch_state(), snapshot_fresh=False)

        self.assertEqual(decision.decision, "blocked_stale_snapshot")
        self.assertFalse(decision.manual_allowed)
        self.assertIn("fresh", decision.reason)

    def test_provider_outage_blocks_switch(self):
        decision = policy.decide_profile_switch(
            switch_state(overall_status="provider_outage", failure_domain="provider_host"),
            snapshot_fresh=True,
        )

        self.assertEqual(decision.decision, "blocked_provider_guard")

    def test_local_client_critical_blocks_switch(self):
        decision = policy.decide_profile_switch(
            switch_state(overall_status="critical", failure_domain="local_client"),
            snapshot_fresh=True,
        )

        self.assertEqual(decision.decision, "blocked_local_client")

    def test_unhealthy_transport_needs_operator_review(self):
        decision = policy.decide_profile_switch(
            switch_state(transport_status="degraded"),
            snapshot_fresh=True,
        )

        self.assertEqual(decision.decision, "operator_review")
        self.assertFalse(decision.manual_allowed)

    def test_explicit_manual_approval_can_allow_manual_not_automatic_action(self):
        decision = policy.decide_profile_switch(
            switch_state(),
            snapshot_fresh=True,
            explicit_manual_approval=True,
        )

        self.assertEqual(decision.decision, "manual_profile_switch_approved")
        self.assertTrue(decision.manual_allowed)
        self.assertFalse(decision.automatic_allowed)
        self.assertFalse(decision.nl_mutation_allowed)


if __name__ == "__main__":
    unittest.main()
