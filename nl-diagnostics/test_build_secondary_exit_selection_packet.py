#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_selection_packet.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_selection_packet", MODULE_PATH)
assert SPEC and SPEC.loader
selection = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_selection_packet"] = selection
SPEC.loader.exec_module(selection)


def provider_shortlist() -> dict:
    return {
        "status": "shortlist_ready_no_endpoint",
        "summary": {
            "shortlist_count": 4,
            "endpoint_count": 0,
        },
        "provider_sources": [
            {"id": "upcloud-locations", "url": "https://upcloud.com/docs/getting-started/locations/"},
            {
                "id": "ovhcloud-public-cloud-regions",
                "url": "https://www.ovhcloud.com/en/public-cloud/regions-availability/",
            },
            {"id": "hetzner-cloud-locations", "url": "https://docs.hetzner.com/cloud/general/locations/"},
        ],
        "shortlist": [
            {
                "label": "upcloud-fi-hel",
                "provider": "UpCloud",
                "country": "Finland",
                "region": "Helsinki",
                "region_slugs": ["fi-hel1", "fi-hel2"],
                "priority": 1,
                "source_id": "upcloud-locations",
                "expected_tcp_ports": [443],
                "status": "shortlist_ready_no_endpoint",
                "why": ["not NL and not SPB/Russia"],
                "risk_notes": ["verify stock"],
            },
            {
                "label": "ovhcloud-pl-waw",
                "provider": "OVHcloud",
                "country": "Poland",
                "region": "Warsaw",
                "region_slugs": ["WAW"],
                "priority": 2,
                "source_id": "ovhcloud-public-cloud-regions",
                "expected_tcp_ports": [443],
                "status": "shortlist_ready_no_endpoint",
                "why": ["provider and country diversity"],
                "risk_notes": ["verify flavor"],
            },
            {
                "label": "hetzner-de-or-fi",
                "provider": "Hetzner",
                "country": "Germany or Finland",
                "region": "Nuremberg/Falkenstein/Helsinki",
                "region_slugs": ["nbg1", "fsn1", "hel1"],
                "priority": 3,
                "source_id": "hetzner-cloud-locations",
                "expected_tcp_ports": [443],
                "status": "shortlist_ready_no_endpoint",
                "why": ["low-cost emergency profile"],
                "risk_notes": ["verify provider independence"],
            },
            {
                "label": "do-not-use-amsterdam",
                "provider": "Example",
                "country": "Netherlands",
                "region": "Amsterdam",
                "priority": 4,
                "status": "shortlist_ready_no_endpoint",
            },
        ],
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def provisioning_plan(endpoint_count: int = 0) -> dict:
    return {
        "status": "provisioning_plan_ready_no_endpoint",
        "summary": {
            "endpoint_count": endpoint_count,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def candidate_intake() -> dict:
    return {
        "status": "awaiting_public_candidate_metadata",
        "summary": {
            "candidate_file": "/mnt/projects/nl-diagnostics/secondary-exit-candidates.example.json",
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def requirements() -> dict:
    return {
        "status": "requirements_ready_no_candidate",
        "summary": {
            "missing_items": ["NET-01"],
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def secondary_flow() -> dict:
    return {
        "status": "blocked_missing_candidate",
        "summary": {
            "manual_switch_allowed": False,
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
            "rollback_required": True,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class SecondaryExitSelectionPacketTests(unittest.TestCase):
    def test_selection_packet_recommends_primary_and_backup_without_endpoint(self):
        payload = selection.build_payload(
            provider_shortlist=provider_shortlist(),
            provisioning_plan=provisioning_plan(),
            candidate_intake=candidate_intake(),
            requirements=requirements(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "selection_packet_ready_no_endpoint")
        self.assertEqual(payload["summary"]["recommended_label"], "upcloud-fi-hel")
        self.assertEqual(payload["summary"]["backup_label"], "ovhcloud-pl-waw")
        self.assertEqual(payload["summary"]["decision_option_count"], 3)
        self.assertFalse(payload["summary"]["may_create_endpoint_now"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_selection_filters_nl_and_amsterdam_options(self):
        rows = selection.decision_rows(provider_shortlist())
        labels = [row["label"] for row in rows]

        self.assertNotIn("do-not-use-amsterdam", labels)

    def test_unsafe_flags_fail_selection(self):
        bad = provider_shortlist()
        bad["spb_fallback_allowed"] = True

        payload = selection.build_payload(
            provider_shortlist=bad,
            provisioning_plan=provisioning_plan(),
            candidate_intake=candidate_intake(),
            requirements=requirements(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "selection_packet_unsafe_flags")

    def test_existing_endpoint_changes_to_review_not_auto_switch(self):
        payload = selection.build_payload(
            provider_shortlist=provider_shortlist(),
            provisioning_plan=provisioning_plan(endpoint_count=1),
            candidate_intake=candidate_intake(),
            requirements=requirements(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "selection_packet_ready_review_endpoint")
        self.assertFalse(payload["automatic_failover_allowed"])

    def test_markdown_contains_stop_conditions_and_no_write_notice(self):
        payload = selection.build_payload(
            provider_shortlist=provider_shortlist(),
            provisioning_plan=provisioning_plan(),
            candidate_intake=candidate_intake(),
            requirements=requirements(),
            secondary_flow=secondary_flow(),
            manual_drill=manual_drill(),
        )

        markdown = selection.render_markdown(payload)

        self.assertIn("Stop Conditions", markdown)
        self.assertIn("provider/account is the current NL provider/account", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
