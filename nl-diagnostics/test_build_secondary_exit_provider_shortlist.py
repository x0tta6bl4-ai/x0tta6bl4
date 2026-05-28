#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_secondary_exit_provider_shortlist.py")
SPEC = importlib.util.spec_from_file_location("build_secondary_exit_provider_shortlist", MODULE_PATH)
assert SPEC and SPEC.loader
shortlist = importlib.util.module_from_spec(SPEC)
sys.modules["build_secondary_exit_provider_shortlist"] = shortlist
SPEC.loader.exec_module(shortlist)


class SecondaryExitProviderShortlistTests(unittest.TestCase):
    def test_shortlist_is_safe_planning_without_endpoint(self):
        payload = shortlist.build_payload()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "shortlist_ready_no_endpoint")
        self.assertGreaterEqual(payload["summary"]["shortlist_count"], 3)
        self.assertEqual(payload["summary"]["endpoint_count"], 0)
        self.assertFalse(payload["summary"]["candidate_configured"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])
        self.assertFalse(payload["automatic_failover_allowed"])

    def test_shortlist_avoids_nl_spb_and_secrets(self):
        payload = shortlist.build_payload()
        text = str(payload).lower()

        for scheme in ("vless", "vmess", "trojan"):
            self.assertNotIn(f"{scheme}://", text)
        self.assertNotIn("private key", " ".join(row["label"].lower() for row in payload["shortlist"]))
        for option in payload["shortlist"]:
            combined = " ".join(
                [
                    option["label"],
                    option["provider"],
                    option["country"],
                    option["region"],
                    " ".join(option["risk_notes"]),
                ]
            ).lower()
            self.assertNotIn("spb", combined)
            self.assertNotIn("russia", option["country"].lower())
            self.assertNotEqual(option["country"].lower(), "netherlands")

    def test_every_provider_option_has_a_source(self):
        payload = shortlist.build_payload()
        source_ids = {row["id"] for row in payload["provider_sources"]}

        self.assertEqual(payload["summary"]["invalid_source_refs"], [])
        for option in payload["shortlist"]:
            self.assertIn(option["source_id"], source_ids)

    def test_markdown_renders_sources_and_no_write_notice(self):
        markdown = shortlist.render_markdown(shortlist.build_payload())

        self.assertIn("Provider Options", markdown)
        self.assertIn("Blocking Context", markdown)
        self.assertIn("No NL or SPB writes", markdown)
        self.assertIn("https://", markdown)


if __name__ == "__main__":
    unittest.main()
