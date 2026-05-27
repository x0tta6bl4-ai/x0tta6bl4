#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("create_secondary_exit_config.py")
SPEC = importlib.util.spec_from_file_location("create_secondary_exit_config", MODULE_PATH)
assert SPEC and SPEC.loader
creator = importlib.util.module_from_spec(SPEC)
sys.modules["create_secondary_exit_config"] = creator
SPEC.loader.exec_module(creator)


class CreateSecondaryExitConfigTests(unittest.TestCase):
    def test_builds_safe_public_metadata_config(self):
        payload = creator.build_config(
            label="emergency-1",
            provider="new-provider",
            region="new-region",
            host="203.0.113.10",
            tcp_ports=[443, 8443],
            expected_exit_ip=None,
            enable_client_probe=False,
            socks_host="127.0.0.1",
            socks_port=10918,
            exit_ip_url="https://api.ipify.org",
        )

        self.assertEqual(payload["candidate"]["label"], "emergency-1")
        self.assertEqual(payload["candidate"]["tcp_ports"], [443, 8443])
        self.assertFalse(payload["policy"]["spb_fallback_allowed"])
        self.assertFalse(payload["policy"]["automatic_failover_allowed"])
        self.assertFalse(payload["policy"]["nl_write_allowed"])

    def test_rejects_current_nl_ip(self):
        with self.assertRaises(ValueError):
            creator.build_config(
                label="bad",
                provider="new-provider",
                region="new-region",
                host="89.125.1.107",
                tcp_ports=[443],
                expected_exit_ip=None,
                enable_client_probe=False,
                socks_host="127.0.0.1",
                socks_port=10918,
                exit_ip_url="https://api.ipify.org",
            )

    def test_rejects_spb_marker(self):
        with self.assertRaises(ValueError):
            creator.build_config(
                label="spb-fallback",
                provider="new-provider",
                region="new-region",
                host="203.0.113.10",
                tcp_ports=[443],
                expected_exit_ip=None,
                enable_client_probe=False,
                socks_host="127.0.0.1",
                socks_port=10918,
                exit_ip_url="https://api.ipify.org",
            )

    def test_rejects_secret_like_value(self):
        with self.assertRaises(ValueError):
            creator.build_config(
                label="bad",
                provider="new-provider",
                region="new-region",
                host="vless" + "://secret",
                tcp_ports=[443],
                expected_exit_ip=None,
                enable_client_probe=False,
                socks_host="127.0.0.1",
                socks_port=10918,
                exit_ip_url="https://api.ipify.org",
            )

    def test_client_probe_requires_expected_exit_ip(self):
        with self.assertRaises(ValueError):
            creator.build_config(
                label="emergency-1",
                provider="new-provider",
                region="new-region",
                host="203.0.113.10",
                tcp_ports=[443],
                expected_exit_ip=None,
                enable_client_probe=True,
                socks_host="127.0.0.1",
                socks_port=10918,
                exit_ip_url="https://api.ipify.org",
            )

    def test_parse_ports_deduplicates_and_validates(self):
        self.assertEqual(creator.parse_ports(["443,8443", "443"]), [443, 8443])
        with self.assertRaises(ValueError):
            creator.parse_ports(["70000"])


if __name__ == "__main__":
    unittest.main()
