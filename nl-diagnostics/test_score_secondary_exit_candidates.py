#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("score_secondary_exit_candidates.py")
SPEC = importlib.util.spec_from_file_location("score_secondary_exit_candidates", MODULE_PATH)
assert SPEC and SPEC.loader
score = importlib.util.module_from_spec(SPEC)
sys.modules["score_secondary_exit_candidates"] = score
SPEC.loader.exec_module(score)


def candidate(**overrides):
    value = {
        "label": "candidate-a",
        "provider": "new-provider",
        "region": "new-region",
        "host": "198.51.100.20",
        "tcp_ports": [443],
    }
    value.update(overrides)
    return value


class SecondaryExitCandidateScoreTests(unittest.TestCase):
    def test_empty_candidate_file_is_missing_candidates_not_failure(self):
        with tempfile.TemporaryDirectory(dir="/mnt/projects/.tmp") as tmp:
            path = Path(tmp) / "candidates.json"
            path.write_text('{"candidates":[]}\n', encoding="utf-8")

            payload = score.build_payload(path)

        self.assertEqual(payload["status"], "missing_candidates")
        self.assertEqual(payload["summary"]["candidate_count"], 0)
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_viable_public_candidate_scores_ready(self):
        with tempfile.TemporaryDirectory(dir="/mnt/projects/.tmp") as tmp:
            path = Path(tmp) / "candidates.json"
            path.write_text(
                '{"candidates":[{"label":"a","provider":"new-provider","region":"new-region","host":"8.8.8.8","tcp_ports":[443]}]}\n',
                encoding="utf-8",
            )

            payload = score.build_payload(path)

        self.assertEqual(payload["status"], "candidate_pool_ready")
        self.assertEqual(payload["summary"]["viable_count"], 1)
        self.assertEqual(payload["summary"]["top_candidate_label"], "a")

    def test_nl_ip_nl_region_and_spb_marker_are_rejected(self):
        row_nl = score.score_candidate(candidate(host=score.NL_IP))
        row_nl_region = score.score_candidate(candidate(region="Netherlands", host="8.8.8.8"))
        row_nl_tld = score.score_candidate(candidate(host="vpn.example.nl"))
        row_spb = score.score_candidate(candidate(provider="spb-provider", host="8.8.4.4"))

        self.assertFalse(row_nl["viable"])
        self.assertIn("current_nl_ip", row_nl["issues"])
        self.assertFalse(row_nl_region["viable"])
        self.assertIn("nl_marker", row_nl_region["issues"])
        self.assertFalse(row_nl_tld["viable"])
        self.assertIn("nl_marker", row_nl_tld["issues"])
        self.assertFalse(row_spb["viable"])
        self.assertIn("spb_marker", row_spb["issues"])

    def test_secret_like_candidate_file_is_rejected(self):
        marker = "trojan" + "://secret"
        with tempfile.TemporaryDirectory(dir="/mnt/projects/.tmp") as tmp:
            path = Path(tmp) / "candidates.json"
            path.write_text(
                '{"candidates":[{"label":"bad","provider":"p","region":"r","host":"'
                + marker
                + '","tcp_ports":[443]}]}\n',
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                score.build_payload(path)

    def test_markdown_has_no_write_notice(self):
        payload = {
            "generated_at": "2026-05-28T00:00:00+00:00",
            "candidate_file": "example.json",
            "status": "missing_candidates",
            "summary": {
                "candidate_count": 0,
                "viable_count": 0,
                "rejected_count": 0,
                "top_candidate_label": "none",
            },
            "next_step": "fill public metadata",
            "candidates": [],
        }

        markdown = score.render_markdown(payload)

        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
