#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("probe_blocking_paths.py")
SPEC = importlib.util.spec_from_file_location("probe_blocking_paths", MODULE_PATH)
assert SPEC and SPEC.loader
probe = importlib.util.module_from_spec(SPEC)
sys.modules["probe_blocking_paths"] = probe
SPEC.loader.exec_module(probe)


def row(mode: str, ok: bool, code: int | None = 200):
    return {"label": "target", "mode": mode, "ok": ok, "http_code": code}


class ProbeBlockingPathsTests(unittest.TestCase):
    def test_parse_target_rejects_non_http_urls(self):
        with self.assertRaises(Exception):
            probe.parse_target("bad=ftp://example.com")

    def test_parse_target_accepts_tcp_target(self):
        target = probe.parse_target("telegram_media=tcp://149.154.166.111:443")

        self.assertEqual(target.kind, "tcp")
        self.assertEqual(target.host, "149.154.166.111")
        self.assertEqual(target.port, 443)

    def test_load_targets_file_reads_http_and_tcp_targets(self):
        targets = probe.load_targets_file(str(Path("nl-diagnostics/blocking_probe_targets.json")))

        kinds = {target.kind for target in targets}
        labels = {target.label for target in targets}
        self.assertIn("http", kinds)
        self.assertIn("tcp", kinds)
        self.assertIn("telegram_media_dc2_149_154_166_111_443", labels)

    def test_builds_socks_curl_command_with_redacted_shape(self):
        cmd = probe.build_curl_command(
            "https://example.com",
            mode="socks",
            timeout=5,
            socks_proxy="socks5h://127.0.0.1:10918",
            http_proxy=None,
        )

        self.assertIn("--proxy", cmd)
        self.assertIn("socks5h://127.0.0.1:10918", cmd)
        self.assertEqual(cmd[-1], "https://example.com")

    def test_probe_url_parses_curl_metrics(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="code=204 namelookup=0.001 connect=0.002 tls=0.003 starttransfer=0.004 total=0.005",
                stderr="",
            )

        result = probe.probe_url(
            probe.Target("connectivity", kind="http", url="https://www.gstatic.com/generate_204"),
            mode="direct",
            timeout=5,
            attempts=1,
            socks_proxy=None,
            http_proxy=None,
            runner=fake_run,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "http")
        self.assertEqual(result["http_code"], 204)
        self.assertEqual(result["metrics"]["total"], 0.005)

    def test_probe_url_retries_failed_attempt_once(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                return subprocess.CompletedProcess(cmd, 28, stdout="code=0 total=1.0", stderr="timeout")
            return subprocess.CompletedProcess(cmd, 0, stdout="code=200 total=0.1", stderr="")

        result = probe.probe_url(
            probe.Target("example", kind="http", url="https://example.com"),
            mode="direct",
            timeout=5,
            attempts=2,
            socks_proxy=None,
            http_proxy=None,
            runner=fake_run,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempt_count"], 2)
        self.assertEqual(len(calls), 2)

    def test_probe_tcp_direct_success(self):
        calls = []

        class FakeSocket:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        def fake_create_connection(endpoint, timeout):
            calls.append((endpoint, timeout))
            return FakeSocket()

        old_create_connection = probe.socket.create_connection
        probe.socket.create_connection = fake_create_connection
        try:
            result = probe.probe_tcp(
                probe.Target("telegram_media", kind="tcp", host="149.154.166.111", port=443),
                mode="direct",
                timeout=5,
                attempts=1,
                socks_host="127.0.0.1",
                socks_port=10918,
            )
        finally:
            probe.socket.create_connection = old_create_connection

        self.assertTrue(result["ok"])
        self.assertEqual(result["kind"], "tcp")
        self.assertEqual(calls[0][0], ("149.154.166.111", 443))

    def test_direct_ok_socks_403_is_exit_rejected(self):
        summary = probe.classify_target([
            row("direct", True, 200),
            row("socks", False, 403),
        ])

        self.assertEqual(summary["assessment"], "exit_ip_or_vpn_rejected")

    def test_tcp_direct_ok_socks_fail_is_vpn_path_degraded(self):
        summary = probe.classify_target([
            {"label": "telegram_media", "kind": "tcp", "mode": "direct", "ok": True},
            {"label": "telegram_media", "kind": "tcp", "mode": "socks", "ok": False},
        ])

        self.assertEqual(summary["assessment"], "vpn_path_degraded")
        self.assertEqual(summary["kind"], "tcp")

    def test_direct_fail_socks_ok_is_possible_local_isp_block(self):
        summary = probe.classify_target([
            row("direct", False, 0),
            row("socks", True, 200),
        ])

        self.assertEqual(summary["assessment"], "possible_local_isp_block")

    def test_summary_prefers_exit_rejected_over_other_target_failures(self):
        result = probe.summarize([
            {"assessment": "ok"},
            {"assessment": "exit_ip_or_vpn_rejected"},
            {"assessment": "target_or_global_unreachable"},
        ])

        self.assertEqual(result["assessment"], "exit_ip_or_vpn_rejected")

    def test_summary_groups_assessments(self):
        result = probe.summarize([
            {"assessment": "ok", "group": "telegram"},
            {"assessment": "vpn_path_degraded", "group": "telegram"},
            {"assessment": "ok", "group": "baseline"},
        ])

        self.assertEqual(result["group_assessments"]["telegram"]["ok"], 1)
        self.assertEqual(result["group_assessments"]["telegram"]["vpn_path_degraded"], 1)


if __name__ == "__main__":
    unittest.main()
