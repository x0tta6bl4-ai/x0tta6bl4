#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "collect_transport_usage_evidence.py"


def load_module():
    spec = importlib.util.spec_from_file_location("collect_transport_usage_evidence", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TransportUsageEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_parse_xray_line_hashes_client_without_raw_identifiers(self) -> None:
        line = (
            "2026/06/01 20:45:13.536605 from 89.125.1.107:0 accepted "
            "tcp:api.ipify.org:443 [ghost-https-xhttp >> direct] "
            "email: user@example.test"
        )

        event = self.module.parse_xray_line(
            line,
            transport="ghost_xhttp",
            hash_key=b"local-test-key",
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.transport, "ghost_xhttp")
        self.assertEqual(event.network, "tcp")
        self.assertEqual(event.dest_port, "443")
        self.assertRegex(event.client_hash or "", r"^[0-9a-f]{16}$")
        self.assertNotEqual(event.client_hash, "user@example.test")

    def test_report_does_not_store_raw_email_ip_or_target_host(self) -> None:
        event = self.module.parse_xray_line(
            "2026/06/01 20:45:13.536605 from 89.125.1.107:0 accepted "
            "tcp:api.ipify.org:443 [ghost-https-xhttp >> direct] "
            "email: user@example.test",
            transport="ghost_xhttp",
            hash_key=b"local-test-key",
        )
        assert event is not None

        report = self.module.build_report(
            xray_events=[event],
            nginx_events=[],
            windows=[60],
            now=datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            hash_key_present=True,
        )
        rendered = str(report)

        self.assertNotIn("user@example.test", rendered)
        self.assertNotIn("89.125.1.107", rendered)
        self.assertNotIn("api.ipify.org", rendered)
        self.assertFalse(report["privacy"]["raw_identifiers_stored"])
        self.assertEqual(
            report["windows"]["60m"]["xray"]["ghost_xhttp"]["dataplane_events"],
            1,
        )

    def test_write_json_creates_output_without_raw_identifiers(self) -> None:
        event = self.module.parse_xray_line(
            "2026/06/01 20:45:13 from 176.101.1.175:0 accepted "
            "udp:8.8.8.8:53 [ghost-https-ws >> direct] "
            "email: offline-user@example.test",
            transport="ghost_https_ws",
            hash_key=b"local-test-key",
        )
        assert event is not None

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "latest.json"
            report = self.module.build_report(
                xray_events=[event],
                nginx_events=[],
                windows=[15],
                now=datetime(2026, 6, 1, 20, 50, tzinfo=UTC),
                hash_key_present=True,
            )
            self.module.write_json(output, report)
            text = output.read_text(encoding="utf-8")

        self.assertIn("ghost_https_ws", text)
        self.assertNotIn("offline-user@example.test", text)
        self.assertNotIn("176.101.1.175", text)

    def test_report_flags_legacy_proxy_requests_without_dataplane(self) -> None:
        nginx_event = self.module.NginxEvent(
            ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
            path="/ghost-xhttp",
            status="404",
            source_hash="abcd1234abcd1234",
            method="GET",
            user_agent_family="xray",
        )

        report = self.module.build_report(
            xray_events=[],
            nginx_events=[nginx_event],
            windows=[15],
            now=datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            hash_key_present=True,
        )

        self.assertFalse(report["ok"])
        self.assertEqual(report["decision"], "TRANSPORT_USAGE_ATTENTION")
        self.assertIn(
            "15m:ghost_xhttp:legacy_proxy_requests_without_dataplane",
            report["findings"],
        )
        self.assertIn("15m:ghost_xhttp:legacy_proxy_4xx_seen", report["findings"])
        health = report["windows"]["15m"]["legacy_transport_health"]
        self.assertEqual(health["status"], "attention")
        self.assertEqual(health["severity"], "single_source_stale_legacy")
        self.assertEqual(health["attention_scope"], "single_proxy_source")
        self.assertFalse(health["restart_relevant"])
        self.assertEqual(
            health["operator_action"],
            "monitor_single_stale_legacy_source_after_migration",
        )
        self.assertEqual(report["summary"]["recent_window_minutes"], 15)
        self.assertEqual(report["summary"]["severity"], "single_source_stale_legacy")
        self.assertEqual(report["summary"]["attention_scope"], "single_proxy_source")
        self.assertFalse(report["summary"]["restart_relevant"])
        self.assertEqual(report["summary"]["aggregate_unique_proxy_source_count"], 1)
        self.assertEqual(report["summary"]["attention_unique_proxy_source_count"], 1)
        self.assertEqual(
            health["transports"]["ghost_xhttp"]["findings"],
            ["legacy_proxy_requests_without_dataplane", "legacy_proxy_4xx_seen"],
        )
        self.assertEqual(
            health["transports"]["ghost_xhttp"]["attention_scope"],
            "single_proxy_source",
        )
        self.assertFalse(health["transports"]["ghost_xhttp"]["restart_relevant"])
        self.assertEqual(
            health["transports"]["ghost_xhttp"]["unique_proxy_source_count"],
            1,
        )
        self.assertEqual(
            health["transports"]["ghost_xhttp"]["proxy_source_hashes_sample"],
            ["abcd1234abcd1234"],
        )
        self.assertEqual(
            health["transports"]["ghost_xhttp"]["proxy_user_agent_family_counts"],
            {"xray": 1},
        )

    def test_report_counts_distinct_single_sources_across_legacy_paths(self) -> None:
        report = self.module.build_report(
            xray_events=[],
            nginx_events=[
                self.module.NginxEvent(
                    ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
                    path="/ghost-xhttp",
                    status="404",
                    source_hash="abcd1234abcd1234",
                    method="GET",
                    user_agent_family="xray",
                ),
                self.module.NginxEvent(
                    ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
                    path="/ghost-ws",
                    status="101",
                    source_hash="ffff1234ffff1234",
                    method="GET",
                    user_agent_family="xray",
                ),
            ],
            windows=[15],
            now=datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            hash_key_present=True,
        )

        health = report["windows"]["15m"]["legacy_transport_health"]
        self.assertEqual(health["severity"], "multi_source_legacy_attention")
        self.assertEqual(health["attention_scope"], "multiple_proxy_sources")
        self.assertFalse(health["restart_relevant"])
        self.assertEqual(health["aggregate_unique_proxy_source_count"], 2)
        self.assertEqual(health["attention_unique_proxy_source_count"], 2)
        self.assertEqual(report["summary"]["aggregate_unique_proxy_source_count"], 2)
        self.assertEqual(report["summary"]["attention_unique_proxy_source_count"], 2)
        self.assertEqual(report["summary"]["severity"], "multi_source_legacy_attention")

    def test_report_marks_active_legacy_dataplane_with_remaining_attention(self) -> None:
        xray_event = self.module.parse_xray_line(
            "2026/06/01 20:59:13.536605 from 89.125.1.107:0 accepted "
            "tcp:api.ipify.org:443 [ghost-https-ws >> direct] "
            "email: user@example.test",
            transport="ghost_https_ws",
            hash_key=b"local-test-key",
        )
        assert xray_event is not None
        report = self.module.build_report(
            xray_events=[xray_event],
            nginx_events=[
                self.module.NginxEvent(
                    ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
                    path="/ghost-ws",
                    status="101",
                    source_hash="aaaa1234aaaa1234",
                    method="GET",
                    user_agent_family="go-http-client",
                ),
                self.module.NginxEvent(
                    ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
                    path="/ghost-xhttp",
                    status="404",
                    source_hash="bbbb1234bbbb1234",
                    method="GET",
                    user_agent_family="other",
                ),
            ],
            windows=[15],
            now=datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            hash_key_present=True,
        )

        health = report["windows"]["15m"]["legacy_transport_health"]
        self.assertEqual(health["severity"], "legacy_dataplane_active_with_attention")
        self.assertEqual(health["attention_scope"], "mixed_legacy_dataplane_and_attention")
        self.assertFalse(health["restart_relevant"])
        self.assertEqual(
            health["operator_action"],
            "monitor_active_legacy_source_and_migrate_to_reality",
        )
        self.assertEqual(health["dataplane_events"], 1)
        self.assertEqual(health["aggregate_unique_proxy_source_count"], 2)
        self.assertEqual(health["attention_unique_proxy_source_count"], 1)
        self.assertEqual(report["summary"]["severity"], "legacy_dataplane_active_with_attention")

    def test_report_marks_legacy_transport_ok_when_dataplane_is_seen(self) -> None:
        xray_event = self.module.parse_xray_line(
            "2026/06/01 20:59:13.536605 from 89.125.1.107:0 accepted "
            "tcp:api.ipify.org:443 [ghost-https-xhttp >> direct] "
            "email: user@example.test",
            transport="ghost_xhttp",
            hash_key=b"local-test-key",
        )
        assert xray_event is not None
        nginx_event = self.module.NginxEvent(
            ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
            path="/ghost-xhttp",
            status="200",
        )

        report = self.module.build_report(
            xray_events=[xray_event],
            nginx_events=[nginx_event],
            windows=[15],
            now=datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            hash_key_present=True,
        )

        self.assertTrue(report["ok"])
        self.assertEqual(report["decision"], "TRANSPORT_USAGE_OK")
        self.assertEqual(report["findings"], [])
        self.assertEqual(
            report["windows"]["15m"]["legacy_transport_health"]["transports"]["ghost_xhttp"]["status"],
            "legacy_dataplane_seen",
        )
        self.assertEqual(report["summary"]["severity"], "none")
        self.assertEqual(report["summary"]["attention_scope"], "none")
        self.assertFalse(report["summary"]["restart_relevant"])
        self.assertEqual(report["summary"]["aggregate_unique_proxy_source_count"], 0)
        self.assertEqual(report["summary"]["attention_unique_proxy_source_count"], 0)

    def test_report_marks_legacy_5xx_as_restart_relevant_server_error(self) -> None:
        nginx_event = self.module.NginxEvent(
            ts=datetime(2026, 6, 1, 20, 59, tzinfo=UTC),
            path="/ghost-ws",
            status="502",
            source_hash="abcd1234abcd1234",
            method="GET",
            user_agent_family="xray",
        )

        report = self.module.build_report(
            xray_events=[],
            nginx_events=[nginx_event],
            windows=[15],
            now=datetime(2026, 6, 1, 21, 0, tzinfo=UTC),
            hash_key_present=True,
        )

        health = report["windows"]["15m"]["legacy_transport_health"]
        self.assertEqual(health["severity"], "legacy_proxy_server_error")
        self.assertEqual(health["attention_scope"], "legacy_proxy_server_error")
        self.assertTrue(health["restart_relevant"])
        self.assertEqual(
            health["operator_action"],
            "inspect_legacy_proxy_upstream_before_restart",
        )
        self.assertEqual(report["summary"]["severity"], "legacy_proxy_server_error")
        self.assertTrue(report["summary"]["restart_relevant"])

    def test_parse_nginx_line_hashes_source_and_buckets_user_agent(self) -> None:
        event = self.module.parse_nginx_line(
            '198.51.100.9 - - [01/Jun/2026:20:59:13 +0000] '
            '"GET /ghost-ws HTTP/1.1" 101 0 "-" "Xray-core/25.5.16"',
            hash_key=b"local-test-key",
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.path, "/ghost-ws")
        self.assertEqual(event.status, "101")
        self.assertEqual(event.method, "GET")
        self.assertEqual(event.user_agent_family, "xray")
        self.assertRegex(event.source_hash or "", r"^[0-9a-f]{16}$")
        self.assertNotEqual(event.source_hash, "198.51.100.9")


if __name__ == "__main__":
    unittest.main()
