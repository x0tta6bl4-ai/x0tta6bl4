#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_vpn_improvement_backlog.py")
SPEC = importlib.util.spec_from_file_location("build_vpn_improvement_backlog", MODULE_PATH)
assert SPEC and SPEC.loader
backlog = importlib.util.module_from_spec(SPEC)
sys.modules["build_vpn_improvement_backlog"] = backlog
SPEC.loader.exec_module(backlog)


def sample_decision():
    return {
        "decision": {"decision": "observe", "confidence": "high"},
        "classification": {
            "overall_status": "advisory",
            "transport_status": "healthy",
            "telegram_media_status": "degraded",
            "provider_status": "recent_boot_gap",
            "failure_domain": "external_network",
        },
    }


def sample_history():
    return {
        "summary": {
            "trend": "stable_no_probe_evidence",
            "snapshot_count": 3,
        }
    }


def sample_manifest():
    return {
        "nl_write_allowed": False,
        "gap_summary": {"same_hash_elsewhere": 21},
        "source_promotion_status": {
            "promoted_count": 22,
            "deployable_to_nl": False,
        },
    }


class VpnImprovementBacklogTests(unittest.TestCase):
    def test_backlog_separates_local_now_from_future_nl_write(self):
        payload = backlog.build_payload(sample_decision(), sample_history(), sample_manifest())

        local_items = [item for item in payload["items"] if item["phase"] == "local_now"]
        future_nl_items = [item for item in payload["items"] if item["phase"] == "future_nl_write"]

        self.assertGreaterEqual(len(local_items), 1)
        self.assertGreaterEqual(len(future_nl_items), 1)
        self.assertTrue(all(item["allowed_now"] for item in local_items))
        self.assertTrue(all(item["nl_write_required"] for item in future_nl_items))
        self.assertTrue(all(not item["nl_mutation_allowed"] for item in payload["items"]))
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_current_summary_preserves_decision_and_source_state(self):
        payload = backlog.build_payload(sample_decision(), sample_history(), sample_manifest())
        summary = payload["summary"]

        self.assertEqual(summary["decision"], "observe")
        self.assertEqual(summary["blocking_history_trend"], "stable_no_probe_evidence")
        self.assertEqual(summary["promoted_source_count"], 22)
        self.assertFalse(summary["nl_write_allowed"])
        self.assertFalse(summary["deployable_to_nl"])

    def test_markdown_contains_blocked_future_write(self):
        payload = backlog.build_payload(sample_decision(), sample_history(), sample_manifest())
        markdown = backlog.render_markdown(payload)

        self.assertIn("NL-FUTURE-01", markdown)
        self.assertIn("blocked_waiting_approval", markdown)
        self.assertIn("No NL or SPB writes", markdown)

    def test_resilience_item_references_manual_failover_plan(self):
        payload = backlog.build_payload(sample_decision(), sample_history(), sample_manifest())
        resilience = next(item for item in payload["items"] if item["id"] == "FUTURE-RESILIENCE-01")

        self.assertEqual(resilience["status"], "requirements_documented")
        self.assertIn(
            "manual_failover_plan=nl-diagnostics/manual-failover-plan-2026-05-28.md",
            resilience["evidence"],
        )
        self.assertIn(
            "secondary_probe_template=nl-diagnostics/manual-failover-secondary.example.json",
            resilience["evidence"],
        )
        self.assertIn(
            "secondary_config_generator=nl-diagnostics/create_secondary_exit_config.py",
            resilience["evidence"],
        )
        self.assertFalse(resilience["spb_fallback_allowed"])


if __name__ == "__main__":
    unittest.main()
