#!/usr/bin/env python3
"""Tests for build_provider_incident_packet.py."""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "nl-diagnostics" / "build_provider_incident_packet.py"
SPEC = importlib.util.spec_from_file_location("build_provider_incident_packet", SCRIPT)
assert SPEC and SPEC.loader
packet_mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packet_mod)


class ProviderIncidentPacketTests(unittest.TestCase):
    def _write_snapshot(self, root: Path) -> Path:
        snapshot = root / "20260527T072732Z"
        fake_token = "123456789:" + ("A" * 35)
        fake_uuid = "-".join(("11111111", "2222", "3333", "4444", "555555555555"))
        fake_vpn_uri = "vless" + "://secret@example"
        (snapshot / "local").mkdir(parents=True)
        (snapshot / "nl").mkdir(parents=True)
        (snapshot / "local" / "vpn_status.json").write_text(
            json.dumps(
                {
                    "overall_status": "ok",
                    "failure_domain": "none",
                    "recommended_action": "observe",
                    "exit_ip": "89.125.1.107",
                    "packet_loss_percent": 0,
                    "tcp_connections": {"fin_wait_2": 0, "close_wait": 0, "established": 5},
                }
            ),
            encoding="utf-8",
        )
        (snapshot / "nl" / "runtime_state_summary.txt").write_text(
            """
# command: cat runtime
{
  "mode": "degraded",
  "reason": "telegram media edges are slow from the current egress path",
  "recommended_action": "observe",
  "hot_path_summary": {
    "transport_health_status": "advisory",
    "telegram_media_status": "degraded",
    "best_path_port": 2083,
    "reason": "telegram media edges are slow from the current egress path"
  }
}
""",
            encoding="utf-8",
        )
        (snapshot / "nl" / "provider_signals.txt").write_text(
            f"""
PROVIDER_SHUTDOWN_LINES
May 26 10:18:29 01164.com qemu-ga[785]: info: guest-shutdown called, mode: powerdown
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown). token {fake_token} uuid {fake_uuid} link {fake_vpn_uri}

CURRENT_CPU_STEAL
Average:     all    7.92    0.00    6.69    0.35    0.00    2.11    0.18    0.00    0.00   82.75
""",
            encoding="utf-8",
        )
        (snapshot / "nl" / "boot_history.txt").write_text(
            """
IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY
 -1 abc Mon 2026-05-25 18:43:23 UTC Tue 2026-05-26 10:21:04 UTC
  0 def Wed 2026-05-27 02:50:41 UTC Wed 2026-05-27 07:27:46 UTC
""",
            encoding="utf-8",
        )
        return snapshot

    def test_build_packet_historical_incident_and_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            snapshot = self._write_snapshot(tmp_path)
            incident = tmp_path / "incident.md"
            incident.write_text(
                """
CPU steal reached 43.78%
load average reached 31.09
vda disk await reached 187 ms
May 26 10:19:14 01164.com systemd-logind[641]: System is powering down (hypervisor initiated shutdown).
""",
                encoding="utf-8",
            )

            original_loader = packet_mod.load_classifier
            packet_mod.load_classifier = lambda: types.SimpleNamespace(
                classify=lambda _snapshot: {
                    "overall_status": "advisory",
                    "failure_domain": "external_network",
                    "recommended_action": "observe",
                    "transport_status": "advisory",
                    "telegram_media_status": "degraded",
                    "provider_status": "historical_incident",
                    "runtime_recommended_action": "switch_profile",
                    "warnings": ["NL runtime recommended_action=switch_profile"],
                    "mutation_allowed": False,
                    "nl_mutation_allowed": False,
                }
            )
            try:
                packet = packet_mod.build_packet(
                    snapshot,
                    incident,
                    now=datetime(2026, 5, 27, 7, 40, tzinfo=timezone.utc),
                )
            finally:
                packet_mod.load_classifier = original_loader

            markdown = packet_mod.render_markdown(packet)
            fake_token = "123456789:" + ("A" * 35)
            fake_uuid = "-".join(("11111111", "2222", "3333", "4444", "555555555555"))
            fake_vpn_uri = "vless" + "://secret@example"

            self.assertEqual(packet["packet_type"], "historical_provider_incident")
            self.assertFalse(packet["nl_write_performed"])
            self.assertFalse(packet["nl_mutation_allowed"])
            self.assertEqual(packet["provider_evidence"]["current_cpu_steal_percent"], 0.18)
            self.assertIn("43.78%", packet["provider_ticket_text"])
            self.assertIn("previous boot last entry", packet["provider_ticket_text"])
            self.assertIn("NL writes: 0", markdown)
            self.assertIn("runtime_recommended_action: switch_profile", markdown)
            self.assertNotIn(fake_token, markdown)
            self.assertNotIn(fake_uuid, markdown)
            self.assertNotIn(fake_vpn_uri, markdown)
            self.assertIn("REDACTED_BOT_TOKEN", markdown)
            self.assertIn("REDACTED_UUID", markdown)

    def test_redact_sensitive_values(self) -> None:
        fake_token = "123456789:" + ("A" * 35)
        fake_uuid = "-".join(("11111111", "2222", "3333", "4444", "555555555555"))
        fake_vpn_uri = "vless" + "://secret@example"
        text = packet_mod.redact(
            f"token=abcd {fake_vpn_uri} {fake_uuid} {fake_token}"
        )

        self.assertNotIn(fake_vpn_uri, text)
        self.assertNotIn(fake_uuid, text)
        self.assertNotIn(fake_token, text)
        self.assertIn("REDACTED_VPN_URI", text)
        self.assertIn("REDACTED_UUID", text)
        self.assertIn("REDACTED_BOT_TOKEN", text)


if __name__ == "__main__":
    unittest.main()
