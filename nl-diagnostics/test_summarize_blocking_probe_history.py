#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("summarize_blocking_probe_history.py")
SPEC = importlib.util.spec_from_file_location("summarize_blocking_probe_history", MODULE_PATH)
assert SPEC and SPEC.loader
history = importlib.util.module_from_spec(SPEC)
sys.modules["summarize_blocking_probe_history"] = history
SPEC.loader.exec_module(history)


def write_probe(root: Path, snapshot: str, assessment: str, targets: list[dict]):
    local = root / snapshot / "local"
    local.mkdir(parents=True)
    (local / "blocking_probe.json").write_text(
        json.dumps(
            {
                "generated_at": f"{snapshot}-generated",
                "summary": {
                    "assessment": assessment,
                    "group_assessments": {"telegram": {"ok": 1}},
                },
                "targets": targets,
                "socks_proxy_detected": True,
                "socks_port": 10918,
                "http_proxy_configured": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )


class BlockingProbeHistoryTests(unittest.TestCase):
    def test_history_summary_detects_stable_no_probe_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_probe(root, "20260527T210659Z", "no_probe_evidence", [{"label": "telegram", "assessment": "ok"}])
            write_probe(root, "20260527T220219Z", "no_probe_evidence", [{"label": "telegram", "assessment": "ok"}])

            payload = history.build_payload(root)

        self.assertEqual(payload["summary"]["snapshot_count"], 2)
        self.assertEqual(payload["summary"]["trend"], "stable_no_probe_evidence")
        self.assertEqual(payload["summary"]["latest"]["snapshot"], "20260527T220219Z")

    def test_history_summary_counts_degraded_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_probe(
                root,
                "20260527T220219Z",
                "vpn_path_degraded",
                [
                    {"label": "telegram", "group": "telegram", "assessment": "ok"},
                    {"label": "connectivity", "group": "baseline", "assessment": "vpn_path_degraded"},
                ],
            )

            payload = history.build_payload(root)
            markdown = history.render_markdown(payload)

        self.assertEqual(payload["summary"]["trend"], "has_degradation")
        self.assertEqual(payload["summary"]["degraded_by_target"]["connectivity"], 1)
        self.assertIn("connectivity=vpn_path_degraded", markdown)


if __name__ == "__main__":
    unittest.main()
