#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_candidate_intake.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_candidate_intake", MODULE_PATH)
assert SPEC and SPEC.loader
intake = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_candidate_intake"] = intake
SPEC.loader.exec_module(intake)


def score(status: str = "missing_candidates", candidate_count: int = 0, viable_count: int = 0) -> dict:
    return {
        "status": status,
        "summary": {
            "candidate_count": candidate_count,
            "viable_count": viable_count,
            "top_candidate_label": "secondary-a" if viable_count else "none",
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


class SecondaryExitCandidateIntakeTests(unittest.TestCase):
    def test_empty_candidates_wait_for_public_metadata(self):
        payload = intake.build_payload(
            candidate_file=Path("candidates.json"),
            candidate_score=score(),
            requirements=requirements(),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "awaiting_public_candidate_metadata")
        self.assertIn("host", payload["allowed_fields"])
        self.assertIn("raw VPN URI", payload["forbidden_material"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_rejected_candidates_need_fix(self):
        payload = intake.build_payload(
            candidate_file=Path("candidates.json"),
            candidate_score=score("candidate_pool_no_viable", candidate_count=1),
            requirements=requirements(),
        )

        self.assertEqual(payload["status"], "candidate_metadata_needs_fix")

    def test_viable_candidate_metadata_is_ready(self):
        payload = intake.build_payload(
            candidate_file=Path("candidates.json"),
            candidate_score=score("candidate_pool_ready", candidate_count=1, viable_count=1),
            requirements=requirements(),
        )

        self.assertEqual(payload["status"], "candidate_metadata_ready")
        self.assertEqual(payload["summary"]["top_candidate_label"], "secondary-a")

    def test_unsafe_flags_fail_intake(self):
        bad_score = score()
        bad_score["spb_fallback_allowed"] = True

        payload = intake.build_payload(
            candidate_file=Path("candidates.json"),
            candidate_score=bad_score,
            requirements=requirements(),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "unsafe_flags")

    def test_markdown_has_template_commands_and_no_write_notice(self):
        payload = intake.build_payload(
            candidate_file=Path("candidates.json"),
            candidate_score=score(),
            requirements=requirements(),
        )

        markdown = intake.render_markdown(payload)

        self.assertIn("Candidate Template", markdown)
        self.assertIn("score_secondary_exit_candidates.py", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
