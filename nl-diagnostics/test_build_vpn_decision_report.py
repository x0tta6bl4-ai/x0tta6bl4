#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_vpn_decision_report.py")
SPEC = importlib.util.spec_from_file_location("build_vpn_decision_report", MODULE_PATH)
assert SPEC and SPEC.loader
decision_report = importlib.util.module_from_spec(SPEC)
sys.modules["build_vpn_decision_report"] = decision_report
SPEC.loader.exec_module(decision_report)


def stable_history():
    return {
        "summary": {
            "snapshot_count": 3,
            "trend": "stable_no_probe_evidence",
            "latest": {"snapshot": "20260527T221810Z", "ok_count": 8, "target_count": 8},
        }
    }


class VpnDecisionReportTests(unittest.TestCase):
    def test_observe_when_core_is_healthy_and_probe_history_is_clean(self):
        classification = {
            "overall_status": "advisory",
            "failure_domain": "external_network",
            "recommended_action": "observe",
            "transport_status": "healthy",
            "provider_status": "recent_boot_gap",
            "blocking_assessment": {"category": "app_specific_degradation"},
            "profile_switch_policy": {"decision": "observe"},
        }

        decision = decision_report.decide_action(classification, stable_history())

        self.assertEqual(decision["decision"], "observe")
        self.assertFalse(decision["nl_mutation_allowed"])
        self.assertFalse(decision["auto_profile_switch_allowed"])
        self.assertFalse(decision["spb_fallback_allowed"])
        self.assertIn("keep provider boot gap on watch", decision["next_actions"][-1])

    def test_local_critical_status_prioritizes_local_fix(self):
        classification = {
            "overall_status": "critical",
            "failure_domain": "local_client",
            "recommended_action": "local_soft_heal",
            "transport_status": "unknown",
            "provider_status": "not_evaluated",
            "blocking_assessment": {"category": "local_client_issue"},
            "profile_switch_policy": {"decision": "observe"},
        }

        decision = decision_report.decide_action(classification, stable_history())

        self.assertEqual(decision["decision"], "local_fix")
        self.assertIn("fix local route/SOCKS/client state first", decision["next_actions"])

    def test_manual_profile_review_never_allows_auto_switch(self):
        classification = {
            "overall_status": "advisory",
            "failure_domain": "external_network",
            "recommended_action": "observe",
            "transport_status": "healthy",
            "provider_status": "not_evaluated",
            "blocking_assessment": {"category": "anti_block_candidate"},
            "profile_switch_policy": {"decision": "manual_profile_review"},
        }

        decision = decision_report.decide_action(classification, stable_history())

        self.assertEqual(decision["decision"], "manual_profile_review")
        self.assertFalse(decision["auto_profile_switch_allowed"])


if __name__ == "__main__":
    unittest.main()
