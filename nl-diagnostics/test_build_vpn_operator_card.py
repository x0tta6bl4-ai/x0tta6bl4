#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_vpn_operator_card.py")
SPEC = importlib.util.spec_from_file_location("build_vpn_operator_card", MODULE_PATH)
assert SPEC and SPEC.loader
card = importlib.util.module_from_spec(SPEC)
sys.modules["build_vpn_operator_card"] = card
SPEC.loader.exec_module(card)


def decision_report(decision="observe", failure_domain="external_network"):
    return {
        "snapshot": "nl-diagnostics/snapshots/20260527T230246Z",
        "decision": {"decision": decision, "confidence": "high"},
        "classification": {
            "overall_status": "advisory",
            "transport_status": "healthy",
            "telegram_media_status": "degraded",
            "provider_status": "recent_boot_gap",
            "failure_domain": failure_domain,
        },
    }


def history():
    return {"summary": {"trend": "stable_no_probe_evidence", "snapshot_count": 4}}


def failover():
    return {"status": "planning_not_active"}


def secondary():
    return {"status": "planning_template"}


class VpnOperatorCardTests(unittest.TestCase):
    def test_observe_card_blocks_mutation_and_starts_with_snapshot(self):
        payload = card.build_payload(decision_report(), history(), failover(), secondary())

        self.assertEqual(payload["operator"]["operator_status"], "observe")
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])
        self.assertIn("collect_vpn_readonly_snapshot.sh", payload["commands"][0]["command"])
        self.assertIn("do not restart x-ui", payload["blocked_actions"][0])

    def test_provider_ticket_branch_prioritizes_provider_packet(self):
        payload = card.build_payload(decision_report("provider_ticket", "provider_host"), history(), failover(), secondary())

        self.assertEqual(payload["operator"]["operator_status"], "provider_ticket")
        self.assertIn("provider packet", payload["operator"]["plain_action"])

    def test_manual_profile_review_never_enables_auto_switch(self):
        payload = card.build_payload(decision_report("manual_profile_review"), history(), failover(), secondary())
        markdown = card.render_markdown(payload)

        self.assertEqual(payload["operator"]["operator_status"], "manual_profile_review")
        self.assertFalse(payload["automatic_failover_allowed"])
        self.assertIn("automatic profile switch", markdown)


if __name__ == "__main__":
    unittest.main()
