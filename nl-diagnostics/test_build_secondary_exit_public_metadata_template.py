#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_public_metadata_template.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_public_metadata_template", MODULE_PATH)
assert SPEC and SPEC.loader
template = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_public_metadata_template"] = template
SPEC.loader.exec_module(template)


def selection_packet(endpoint_count: int = 0) -> dict:
    return {
        "status": "selection_packet_ready_no_endpoint",
        "summary": {
            "endpoint_count": endpoint_count,
            "may_create_endpoint_now": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "operator_decision_order": [
            {
                "rank": 1,
                "selection_role": "primary_pick",
                "label": "upcloud-fi-hel",
                "provider": "UpCloud",
                "country": "Finland",
                "region": "Helsinki",
                "expected_tcp_ports": [443],
            }
        ],
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def candidate_intake() -> dict:
    return {
        "status": "awaiting_public_candidate_metadata",
        "summary": {
            "candidate_score_status": "missing_candidates",
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class SecondaryExitPublicMetadataTemplateTests(unittest.TestCase):
    def test_template_is_ready_without_endpoint_but_does_not_allow_update(self):
        payload = template.build_payload(
            selection_packet=selection_packet(),
            candidate_intake=candidate_intake(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "public_metadata_template_ready_no_endpoint")
        self.assertEqual(payload["summary"]["selected_label"], "upcloud-fi-hel")
        self.assertEqual(payload["summary"]["selected_provider"], "UpCloud")
        self.assertFalse(payload["summary"]["candidate_file_update_allowed"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_endpoint_count_allows_public_candidate_file_update_only(self):
        payload = template.build_payload(
            selection_packet=selection_packet(endpoint_count=1),
            candidate_intake=candidate_intake(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertEqual(payload["status"], "public_metadata_template_ready_for_public_metadata")
        self.assertTrue(payload["summary"]["candidate_file_update_allowed"])
        self.assertFalse(payload["automatic_failover_allowed"])

    def test_unsafe_flags_fail_template(self):
        bad_selection = selection_packet()
        bad_selection["spb_fallback_allowed"] = True

        payload = template.build_payload(
            selection_packet=bad_selection,
            candidate_intake=candidate_intake(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "public_metadata_template_unsafe_flags")

    def test_markdown_contains_template_and_no_write_notice(self):
        payload = template.build_payload(
            selection_packet=selection_packet(),
            candidate_intake=candidate_intake(),
            candidate_file=Path("nl-diagnostics/secondary-exit-candidates.example.json"),
        )

        markdown = template.render_markdown(payload)

        self.assertIn("Candidate File Template", markdown)
        self.assertIn("FILL_PUBLIC_IPV4_OR_HOST_AFTER_PROVISIONING", markdown)
        self.assertIn("No candidate file update, NL write, or SPB fallback", markdown)


if __name__ == "__main__":
    unittest.main()
