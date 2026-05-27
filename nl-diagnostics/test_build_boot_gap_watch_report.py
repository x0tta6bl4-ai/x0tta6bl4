#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_boot_gap_watch_report.py")
SPEC = importlib.util.spec_from_file_location("build_boot_gap_watch_report", MODULE_PATH)
assert SPEC and SPEC.loader
boot = importlib.util.module_from_spec(SPEC)
sys.modules["build_boot_gap_watch_report"] = boot
SPEC.loader.exec_module(boot)


BOOT_HISTORY = """
-1  2026-05-27 00:00:00  Wed 2026-05-27 00:00:00 UTC Wed 2026-05-27 08:53:30 UTC
0   2026-05-27 14:58:37  Wed 2026-05-27 14:58:37 UTC still running
"""


def classifier(**overrides):
    payload = {
        "overall_status": "advisory",
        "transport_status": "healthy",
        "provider_status": "recent_boot_gap",
        "failure_domain": "external_network",
        "recommended_action": "observe",
    }
    payload.update(overrides)
    return lambda _snapshot: payload


def write_snapshot(root: Path, *, unclean: bool = True, provider_signal: bool = False) -> Path:
    snapshot = root / "nl-diagnostics" / "snapshots" / "20260527T230246Z"
    (snapshot / "nl").mkdir(parents=True)
    (snapshot / "nl" / "boot_history.txt").write_text(BOOT_HISTORY, encoding="utf-8")
    (snapshot / "nl" / "current_boot_integrity.txt").write_text(
        "system.journal corrupted or uncleanly shut down\n" if unclean else "",
        encoding="utf-8",
    )
    (snapshot / "nl" / "provider_signals.txt").write_text(
        "hypervisor initiated shutdown\n" if provider_signal else "",
        encoding="utf-8",
    )
    (snapshot / "nl" / "previous_boot_tail.txt").write_text("", encoding="utf-8")
    return snapshot


class BuildBootGapWatchReportTests(unittest.TestCase):
    def test_recent_boot_gap_with_healthy_transport_is_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = write_snapshot(Path(tmp))

            payload = boot.build_payload(snapshot, classifier=classifier())

        self.assertEqual(payload["status"], "watch")
        self.assertEqual(payload["boot_gap_seconds"], 21907)
        self.assertIn("do not restart NL", payload["recommended_action"])
        self.assertFalse(payload["nl_mutation_allowed"])

    def test_provider_outage_classification_becomes_provider_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = write_snapshot(Path(tmp), provider_signal=True)

            payload = boot.build_payload(
                snapshot,
                classifier=classifier(
                    overall_status="provider_outage",
                    failure_domain="provider_host",
                    recommended_action="provider_ticket",
                ),
            )

        self.assertEqual(payload["status"], "provider_ticket")
        self.assertIn("provider incident packet", payload["recommended_action"])

    def test_normal_classification_without_gap_is_normal(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = write_snapshot(Path(tmp), unclean=False)
            (snapshot / "nl" / "boot_history.txt").write_text("", encoding="utf-8")

            payload = boot.build_payload(snapshot, classifier=classifier(provider_status="normal"))

        self.assertEqual(payload["status"], "normal")
        self.assertIsNone(payload["boot_gap_seconds"])

    def test_markdown_contains_no_write_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = write_snapshot(Path(tmp))
            payload = boot.build_payload(snapshot, classifier=classifier())

        markdown = boot.render_markdown(payload)

        self.assertIn("Boot Gap Watch", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
