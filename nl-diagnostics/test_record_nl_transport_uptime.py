#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("record_nl_transport_uptime.py")
SPEC = importlib.util.spec_from_file_location("record_nl_transport_uptime", MODULE_PATH)
assert SPEC and SPEC.loader
uptime = importlib.util.module_from_spec(SPEC)
sys.modules["record_nl_transport_uptime"] = uptime
SPEC.loader.exec_module(uptime)


def probe(status: str = "healthy", ok_count: int = 3) -> dict:
    return {
        "generated_at": f"2026-05-27T23:00:0{ok_count}+00:00",
        "host": "89.125.1.107",
        "ports": [443, 2083, 39829],
        "status": status,
        "ok_count": ok_count,
        "port_count": 3,
        "results": [
            {"port": 443, "ok": ok_count >= 1, "latency_ms": 10.0, "error": ""},
            {"port": 2083, "ok": ok_count >= 2, "latency_ms": 11.0, "error": ""},
            {"port": 39829, "ok": ok_count >= 3, "latency_ms": 12.0, "error": ""},
        ],
    }


class RecordNlTransportUptimeTests(unittest.TestCase):
    def test_compact_probe_is_non_mutating(self):
        row = uptime.compact_probe(probe())

        self.assertEqual(row["status"], "healthy")
        self.assertFalse(row["nl_mutation_allowed"])
        self.assertFalse(row["spb_fallback_allowed"])
        self.assertEqual(len(row["results"]), 3)

    def test_healthy_history_is_stable(self):
        payload = uptime.build_payload([uptime.compact_probe(probe())], Path("history.jsonl"))

        self.assertEqual(payload["summary"]["status"], "stable_healthy")
        self.assertEqual(payload["summary"]["sample_count"], 1)
        self.assertEqual(payload["summary"]["consecutive_non_healthy"], 0)

    def test_degraded_latest_is_watch(self):
        history = [
            uptime.compact_probe(probe("healthy", 3)),
            uptime.compact_probe(probe("degraded", 2)),
        ]

        payload = uptime.build_payload(history, Path("history.jsonl"))

        self.assertEqual(payload["summary"]["status"], "watch")
        self.assertEqual(payload["summary"]["consecutive_non_healthy"], 1)

    def test_append_record_writes_jsonl_once_for_same_timestamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            record = uptime.compact_probe(probe())

            first = uptime.append_record(path, record)
            second = uptime.append_record(path, record)
            line_count = len(path.read_text(encoding="utf-8").splitlines())

        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(line_count, 1)

    def test_load_history_skips_bad_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text('bad\n{"status":"healthy"}\n', encoding="utf-8")

            rows = uptime.load_history(path)

        self.assertEqual(rows, [{"status": "healthy"}])

    def test_markdown_contains_no_write_notice(self):
        payload = uptime.build_payload([uptime.compact_probe(probe())], Path("history.jsonl"))

        markdown = uptime.render_markdown(payload)

        self.assertIn("NL Transport Uptime Summary", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
