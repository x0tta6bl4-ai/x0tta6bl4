#!/usr/bin/env python3
"""Unit tests for classify_vpn_snapshot.py.

These tests build temporary snapshot directories. They do not access NL.
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("classify_vpn_snapshot.py")
SPEC = importlib.util.spec_from_file_location("classify_vpn_snapshot", MODULE_PATH)
assert SPEC and SPEC.loader
classifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(classifier)


RUNTIME_OK = """# command: jq "{header with braces}"
{
  "mode": "ok",
  "hot_path_summary": {
    "transport_health_status": "healthy",
    "telegram_media_status": "healthy"
  },
  "probes": {
    "transport_summary": {
      "status": "healthy",
      "telegram_media_status": "healthy"
    }
  }
}
"""

RUNTIME_TELEGRAM_ADVISORY = """# command: jq "{header with braces}"
{
  "mode": "degraded",
  "reason": "telegram media edges are slow from the current egress path",
  "hot_path_summary": {
    "transport_health_status": "healthy",
    "telegram_media_status": "degraded"
  },
  "probes": {
    "transport_summary": {
      "status": "healthy",
      "telegram_media_status": "degraded"
    }
  }
}
"""

RUNTIME_ANTI_BLOCK_SWITCH_PROFILE = """# command: jq "{header with braces}"
{
  "mode": "anti_block",
  "reason": "listener-loss detector reported anomaly on primary ingress path",
  "recommended_action": "switch_profile",
  "hot_path_summary": {
    "transport_health_status": "healthy",
    "telegram_media_status": "degraded",
    "recommended_action": "switch_profile"
  },
  "probes": {
    "transport_summary": {
      "status": "healthy",
      "telegram_media_status": "degraded"
    }
  }
}
"""


class SnapshotBuilder:
    def __init__(self, root: Path):
        self.root = root
        (root / "local").mkdir()
        (root / "nl").mkdir()

    def write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def healthy(self, runtime: str = RUNTIME_OK) -> "SnapshotBuilder":
        self.write(
            "local/vpn_status.txt",
            "Internet reachable via VPN — exit IP is VPN server: 89.125.1.107\nResult: PASS (warnings=0)\n",
        )
        self.write(
            "local/route_to_vpn.txt",
            "89.125.1.107 via 192.168.0.1 dev enp8s0 src 192.168.0.104\n",
        )
        self.write(
            "local/route_to_public.txt",
            "1.1.1.1 via 172.18.0.2 dev singbox_tun table 2022\n",
        )
        self.write(
            "local/watchdog_metrics.txt",
            "\n".join(
                [
                    "vpn_proxy_healthy 1",
                    "vpn_packet_loss_percent 0",
                    "vpn_fin_wait2_connections 0",
                    "vpn_close_wait_connections 0",
                ]
            )
            + "\n",
        )
        self.write("nl/failed_units.txt", "0 loaded units listed.\n")
        self.write("nl/key_services.txt", "active\nactive\nactive\nactive\nactive\nactive\nactive\nactive\n")
        self.write(
            "nl/listeners.txt",
            "\n".join(
                [
                    "tcp LISTEN 0 65535 *:443 *:*",
                    "tcp LISTEN 0 65535 *:2083 *:*",
                    "tcp LISTEN 0 65535 *:39829 *:*",
                ]
            )
            + "\n",
        )
        self.write("nl/runtime_state_summary.txt", runtime)
        self.write("nl/boot_history.txt", "IDX BOOT ID FIRST ENTRY LAST ENTRY\n")
        self.write("nl/provider_signals.txt", "")
        return self


class ClassifyVpnSnapshotTests(unittest.TestCase):
    def classify(self, builder_fn):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            builder = SnapshotBuilder(root).healthy()
            builder_fn(builder)
            return classifier.classify(root)

    def test_ok_snapshot(self):
        result = self.classify(lambda builder: None)
        self.assertEqual(result["overall_status"], "ok")
        self.assertEqual(result["failure_domain"], "none")
        self.assertEqual(result["recommended_action"], "observe")

    def test_telegram_degradation_is_advisory_not_critical(self):
        result = self.classify(
            lambda builder: builder.write("nl/runtime_state_summary.txt", RUNTIME_TELEGRAM_ADVISORY)
        )
        self.assertEqual(result["overall_status"], "advisory")
        self.assertEqual(result["transport_status"], "healthy")
        self.assertEqual(result["telegram_media_status"], "degraded")
        self.assertEqual(result["recommended_action"], "observe")
        self.assertEqual(result["blocking_assessment"]["category"], "app_specific_degradation")
        self.assertFalse(result["blocking_assessment"]["nl_mutation_allowed"])
        self.assertIn("Telegram", result["blocking_assessment"]["recommended_probe"])

    def test_runtime_switch_profile_signal_is_preserved_as_warning(self):
        result = self.classify(
            lambda builder: builder.write("nl/runtime_state_summary.txt", RUNTIME_ANTI_BLOCK_SWITCH_PROFILE)
        )
        self.assertEqual(result["overall_status"], "advisory")
        self.assertEqual(result["failure_domain"], "external_network")
        self.assertEqual(result["runtime_mode"], "anti_block")
        self.assertEqual(result["runtime_recommended_action"], "switch_profile")
        self.assertIn("NL runtime recommended_action=switch_profile", result["warnings"])
        self.assertIn("profile_switch_policy=", " ".join(result["warnings"]))
        self.assertFalse(result["profile_switch_policy"]["automatic_allowed"])
        self.assertFalse(result["profile_switch_policy"]["nl_mutation_allowed"])
        self.assertEqual(result["blocking_assessment"]["category"], "anti_block_candidate")
        self.assertFalse(result["blocking_assessment"]["auto_profile_switch_allowed"])
        self.assertIn("profile switch manually", result["blocking_assessment"]["recommended_probe"])

    def test_blocking_probe_exit_rejected_overrides_generic_app_degradation(self):
        def mutate(builder: SnapshotBuilder) -> None:
            builder.write("nl/runtime_state_summary.txt", RUNTIME_TELEGRAM_ADVISORY)
            builder.write(
                "local/blocking_probe.json",
                """{
  "summary": {
    "assessment": "exit_ip_or_vpn_rejected",
    "target_count": 2
  }
}
""",
            )

        result = self.classify(mutate)
        self.assertEqual(result["blocking_probe_summary"]["assessment"], "exit_ip_or_vpn_rejected")
        self.assertEqual(result["blocking_assessment"]["category"], "exit_ip_or_vpn_rejected")
        self.assertFalse(result["blocking_assessment"]["nl_mutation_allowed"])

    def test_route_loop_is_local_critical(self):
        result = self.classify(
            lambda builder: builder.write(
                "local/route_to_vpn.txt",
                "89.125.1.107 via 172.18.0.2 dev singbox_tun table 2022\n",
            )
        )
        self.assertEqual(result["overall_status"], "critical")
        self.assertEqual(result["failure_domain"], "local_client")
        self.assertEqual(result["recommended_action"], "local_soft_heal")

    def test_local_vpn_status_json_is_used_when_present(self):
        def mutate(builder: SnapshotBuilder) -> None:
            builder.write(
                "local/vpn_status.json",
                """{
  "overall_status": "critical",
  "exit_ip": "203.0.113.1",
  "packet_loss_percent": 0,
  "tcp_connections": {"fin_wait_2": 0, "close_wait": 0}
}
""",
            )

        result = self.classify(mutate)
        self.assertEqual(result["overall_status"], "critical")
        self.assertEqual(result["failure_domain"], "local_client")
        self.assertIn("external exit IP is not confirmed as VPN server", result["problems"])

    def test_local_vpn_status_json_packet_loss_overrides_watchdog_metric(self):
        def mutate(builder: SnapshotBuilder) -> None:
            builder.write(
                "local/vpn_status.json",
                """{
  "overall_status": "ok",
  "exit_ip": "89.125.1.107",
  "packet_loss_percent": 0,
  "tcp_connections": {"fin_wait_2": 0, "close_wait": 0}
}
""",
            )
            builder.write(
                "local/watchdog_metrics.txt",
                "\n".join(
                    [
                        "vpn_proxy_healthy 1",
                        "vpn_packet_loss_percent 20",
                        "vpn_fin_wait2_connections 0",
                        "vpn_close_wait_connections 0",
                    ]
                )
                + "\n",
            )

        result = self.classify(mutate)
        self.assertNotIn("elevated packet loss", result["problems"])
        self.assertIn("packet_loss_percent=0", result["evidence"])

    def test_provider_signal_ignores_snapshot_command_header(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/provider_signals.txt",
                '# command: grep -Ei "guest-shutdown|hypervisor initiated shutdown|System is powering down"\n'
                "PROVIDER_SHUTDOWN_LINES\n"
                "May 27 02:50:42 01164.com systemd[1]: Finished finalrd.service - Create final runtime dir.\n",
            )
        )
        self.assertEqual(result["provider_status"], "normal")
        self.assertNotEqual(result["overall_status"], "provider_outage")

    def test_recent_boot_gap_is_warning_not_provider_outage_when_core_is_healthy(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/boot_history.txt",
                "IDX BOOT ID FIRST ENTRY LAST ENTRY\n"
                " -1 abc Wed 2026-05-27 02:50:41 UTC Wed 2026-05-27 08:53:30 UTC\n"
                "  0 def Wed 2026-05-27 14:58:37 UTC Wed 2026-05-27 15:09:13 UTC\n",
            )
        )
        self.assertEqual(result["overall_status"], "ok")
        self.assertEqual(result["provider_status"], "recent_boot_gap")
        self.assertIn("NL boot gap seconds=", " ".join(result["warnings"]))

    def test_unclean_boot_integrity_is_provider_warning_not_critical(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/current_boot_integrity.txt",
                "May 27 14:58:38 01164.com systemd-journald[302]: "
                "File /var/log/journal/system.journal corrupted or uncleanly shut down, renaming and replacing.\n",
            )
        )
        self.assertEqual(result["overall_status"], "ok")
        self.assertEqual(result["provider_status"], "unclean_reboot")
        self.assertIn("NL previous boot ended uncleanly", result["warnings"])

    def test_missing_nl_listener_is_nl_critical(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/listeners.txt",
                "tcp LISTEN 0 65535 *:443 *:*\ntcp LISTEN 0 65535 *:39829 *:*\n",
            )
        )
        self.assertEqual(result["overall_status"], "critical")
        self.assertEqual(result["failure_domain"], "nl_service")
        self.assertIn("2083", " ".join(result["problems"]))

    def test_known_ifup_failed_unit_is_warning_not_critical(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/failed_units.txt",
                "  UNIT              LOAD   ACTIVE SUB    DESCRIPTION\n"
                "● ifup@eth0.service loaded failed failed ifup for eth0\n"
                "1 loaded units listed.\n",
            )
        )
        self.assertEqual(result["overall_status"], "ok")
        self.assertIn("NL non-critical failed units: ifup@eth0.service", result["warnings"])

    def test_unknown_failed_unit_is_nl_critical(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/failed_units.txt",
                "  UNIT              LOAD   ACTIVE SUB    DESCRIPTION\n"
                "● x-ui.service loaded failed failed x-ui\n"
                "1 loaded units listed.\n",
            )
        )
        self.assertEqual(result["overall_status"], "critical")
        self.assertEqual(result["failure_domain"], "nl_service")
        self.assertIn("x-ui.service", " ".join(result["problems"]))

    def test_historical_provider_signal_does_not_override_current_healthy(self):
        result = self.classify(
            lambda builder: builder.write(
                "nl/provider_signals.txt",
                "qemu-ga[785]: info: guest-shutdown called, mode: powerdown\n"
                "systemd-logind[641]: System is powering down (hypervisor initiated shutdown).\n",
            )
        )
        self.assertEqual(result["overall_status"], "ok")
        self.assertEqual(result["provider_status"], "historical_incident")

    def test_provider_signal_with_unhealthy_current_state_is_provider_outage(self):
        def mutate(builder: SnapshotBuilder) -> None:
            builder.write("local/vpn_status.txt", "Result: FAIL (warnings=1)\n")
            builder.write(
                "nl/provider_signals.txt",
                "systemd-logind[641]: System is powering down (hypervisor initiated shutdown).\n",
            )

        result = self.classify(mutate)
        self.assertEqual(result["overall_status"], "provider_outage")
        self.assertEqual(result["failure_domain"], "provider_host")
        self.assertEqual(result["recommended_action"], "provider_ticket")
        self.assertEqual(result["blocking_assessment"]["category"], "provider_or_host_issue")
        self.assertIn("provider incident packet", result["blocking_assessment"]["recommended_probe"])


if __name__ == "__main__":
    unittest.main()
