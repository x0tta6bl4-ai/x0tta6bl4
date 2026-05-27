#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("probe_nl_transport_ports.py")
SPEC = importlib.util.spec_from_file_location("probe_nl_transport_ports", MODULE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules["probe_nl_transport_ports"] = probe
SPEC.loader.exec_module(probe)


def connector_with_failed_ports(failed: set[int]):
    def connector(host: str, port: int, timeout: float) -> dict:
        return {
            "host": host,
            "port": port,
            "ok": port not in failed,
            "latency_ms": 12.3 if port not in failed else None,
            "error": "" if port not in failed else "connection refused",
        }

    return connector


class ProbeNlTransportPortsTests(unittest.TestCase):
    def test_all_ports_ok_is_healthy_and_non_mutating(self):
        payload = probe.build_payload(
            host="89.125.1.107",
            ports=[443, 2083, 39829],
            connector=connector_with_failed_ports(set()),
        )

        self.assertEqual(payload["status"], "healthy")
        self.assertEqual(payload["ok_count"], 3)
        self.assertEqual(payload["recommended_action"], "observe")
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_partial_failure_is_degraded_evidence_not_execution_error(self):
        payload = probe.build_payload(
            host="89.125.1.107",
            ports=[443, 2083, 39829],
            connector=connector_with_failed_ports({2083}),
        )

        self.assertEqual(payload["status"], "degraded")
        self.assertEqual(payload["ok_count"], 2)
        self.assertEqual(payload["failure_domain_hint"], "nl_or_provider_or_path")

    def test_all_failed_is_critical(self):
        payload = probe.build_payload(
            host="89.125.1.107",
            ports=[443, 2083],
            connector=connector_with_failed_ports({443, 2083}),
        )

        self.assertEqual(payload["status"], "critical")
        self.assertEqual(payload["ok_count"], 0)

    def test_parse_ports_deduplicates_values(self):
        self.assertEqual(probe.parse_ports(["443,2083", "443"]), [443, 2083])

    def test_markdown_contains_no_write_notice(self):
        payload = probe.build_payload(ports=[443], connector=connector_with_failed_ports(set()))

        markdown = probe.render_markdown(payload)

        self.assertIn("NL Transport Probe", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
