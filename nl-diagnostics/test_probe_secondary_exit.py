#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("probe_secondary_exit.py")
SPEC = importlib.util.spec_from_file_location("probe_secondary_exit", MODULE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules["probe_secondary_exit"] = probe
SPEC.loader.exec_module(probe)


def base_config():
    return {
        "candidate": {
            "label": "secondary-test",
            "provider": "new-provider",
            "region": "new-region",
            "host": "203.0.113.10",
            "tcp_ports": [443, "8443"],
        },
        "client_probe": {
            "enabled": False,
            "socks_host": "127.0.0.1",
            "socks_port": 10918,
            "expected_exit_ip": "203.0.113.10",
            "exit_ip_url": "https://api.ipify.org",
        },
    }


class SecondaryExitProbeTests(unittest.TestCase):
    def test_placeholder_config_is_planning_template(self):
        payload = probe.build_payload(
            {
                "candidate": {
                    "host": "REPLACE_WITH_SECONDARY_HOST_OR_IP",
                    "tcp_ports": [443],
                },
                "client_probe": {"enabled": False},
            }
        )

        self.assertEqual(payload["status"], "planning_template")
        self.assertFalse(payload["candidate_configured"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_rejects_vpn_uri_secret_in_config(self):
        with self.assertRaises(ValueError):
            probe.validate_no_secrets({"profile": "vless" + "://secret-value"})

    def test_endpoint_reachable_profile_unverified_when_tcp_ok(self):
        def connector(host, port, timeout):
            return {"host": host, "port": port, "ok": True, "latency_ms": 1.0, "error": ""}

        payload = probe.build_payload(base_config(), connector=connector)

        self.assertEqual(payload["status"], "endpoint_reachable_profile_unverified")
        self.assertEqual(len(payload["tcp_results"]), 2)
        self.assertTrue(all(row["ok"] for row in payload["tcp_results"]))

    def test_client_exit_match_is_healthy(self):
        config = base_config()
        config["client_probe"]["enabled"] = True

        def connector(host, port, timeout):
            return {"host": host, "port": port, "ok": True, "latency_ms": 1.0, "error": ""}

        def runner(cmd, stdout, stderr, text, check):
            return subprocess.CompletedProcess(cmd, 0, stdout="203.0.113.10\n", stderr="")

        payload = probe.build_payload(config, connector=connector, runner=runner)

        self.assertEqual(payload["status"], "healthy")
        self.assertTrue(payload["client_exit_probe"]["ok"])
        self.assertEqual(payload["client_exit_probe"]["command_shape"], "curl --proxy <redacted-socks> EXIT_IP_URL")

    def test_client_exit_mismatch_is_not_healthy(self):
        config = base_config()
        config["client_probe"]["enabled"] = True

        def connector(host, port, timeout):
            return {"host": host, "port": port, "ok": True, "latency_ms": 1.0, "error": ""}

        def runner(cmd, stdout, stderr, text, check):
            return subprocess.CompletedProcess(cmd, 0, stdout="198.51.100.55\n", stderr="")

        payload = probe.build_payload(config, connector=connector, runner=runner)

        self.assertEqual(payload["status"], "client_exit_mismatch")
        self.assertFalse(payload["client_exit_probe"]["ok"])


if __name__ == "__main__":
    unittest.main()
