#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("record_vpn_incident_timeline.py")
SPEC = importlib.util.spec_from_file_location("record_vpn_incident_timeline", MODULE_PATH)
assert SPEC and SPEC.loader
timeline = importlib.util.module_from_spec(SPEC)
sys.modules["record_vpn_incident_timeline"] = timeline
SPEC.loader.exec_module(timeline)

NOW = datetime(2026, 5, 28, 0, 5, tzinfo=timezone.utc)


def decision_report(decision: str = "observe", failure_domain: str = "external_network") -> dict:
    return {
        "decision": {"decision": decision, "confidence": "high"},
        "classification": {
            "overall_status": "advisory",
            "transport_status": "healthy",
            "telegram_media_status": "degraded",
            "provider_status": "recent_boot_gap",
            "failure_domain": failure_domain,
        },
    }


def boot_gap(status: str = "watch") -> dict:
    return {"status": status, "boot_gap_seconds": 21907}


def provider_packet() -> dict:
    return {
        "packet_type": "provider_watch",
        "snapshot_stale": False,
        "snapshot_age_seconds": 3400,
    }


def history() -> dict:
    return {"summary": {"trend": "stable_no_probe_evidence", "snapshot_count": 4}}


def operator_card() -> dict:
    return {"operator": {"operator_status": "observe"}}


def failover() -> dict:
    return {"status": "planning_not_active"}


def transport_probe(status: str = "healthy") -> dict:
    return {"status": status, "ok_count": 3 if status == "healthy" else 2, "port_count": 3}


def transport_uptime(status: str = "stable_healthy") -> dict:
    return {"summary": {"status": status, "sample_count": 2, "consecutive_non_healthy": 0}}


def readiness() -> dict:
    return {"overall_status": "ready_local_with_future_blocks", "summary": {"missing": 0}}


class VpnIncidentTimelineTests(unittest.TestCase):
    def test_provider_packet_path_follows_snapshot_name(self):
        path = timeline.provider_packet_path(
            Path("/mnt/projects/nl-diagnostics/snapshots/20260528T000600Z"),
            Path("/tmp/nl-diagnostics"),
        )

        self.assertEqual(
            str(path),
            "/tmp/nl-diagnostics/provider-incident-packets/provider-incident-packet-20260528T000600Z.json",
        )

    def test_latest_snapshot_uses_highest_timestamp_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshots = Path(tmp)
            (snapshots / "20260527T230246Z").mkdir()
            (snapshots / "20260528T000600Z").mkdir()
            (snapshots / "README.txt").write_text("not a snapshot", encoding="utf-8")

            latest = timeline.latest_snapshot(snapshots)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.name, "20260528T000600Z")

    def test_build_event_records_provider_watch_without_mutation(self):
        event = timeline.build_event(
            snapshot=Path("nl-diagnostics/snapshots/20260527T230246Z"),
            decision_report=decision_report(),
            boot_gap=boot_gap(),
            provider_packet=provider_packet(),
            history=history(),
            operator_card=operator_card(),
            failover=failover(),
            transport_probe=transport_probe(),
            transport_uptime=transport_uptime(),
            readiness=readiness(),
            now=NOW,
        )

        self.assertEqual(event["event_type"], "provider_watch")
        self.assertEqual(event["snapshot_name"], "20260527T230246Z")
        self.assertEqual(event["nl_transport_probe_ok_count"], "3/3")
        self.assertFalse(event["nl_mutation_allowed"])
        self.assertFalse(event["spb_fallback_allowed"])
        self.assertFalse(event["automatic_failover_allowed"])

    def test_transport_degradation_becomes_transport_watch(self):
        event = timeline.build_event(
            snapshot=Path("nl-diagnostics/snapshots/20260527T230246Z"),
            decision_report=decision_report(),
            boot_gap=boot_gap(),
            provider_packet=provider_packet(),
            history=history(),
            operator_card=operator_card(),
            failover=failover(),
            transport_probe=transport_probe("degraded"),
            transport_uptime=transport_uptime(),
            readiness=readiness(),
            now=NOW,
        )

        self.assertEqual(event["event_type"], "transport_watch")

    def test_append_and_render_timeline_keeps_secret_material_out(self):
        event = timeline.build_event(
            snapshot=Path("nl-diagnostics/snapshots/20260527T230246Z"),
            decision_report=decision_report(),
            boot_gap=boot_gap(),
            provider_packet=provider_packet(),
            history=history(),
            operator_card=operator_card(),
            failover=failover(),
            transport_probe=transport_probe(),
            transport_uptime=transport_uptime(),
            readiness=readiness(),
            now=NOW,
        )

        with tempfile.TemporaryDirectory() as tmp:
            jsonl = Path(tmp) / "timeline.jsonl"
            timeline.append_event(jsonl, event)
            events = timeline.read_events(jsonl)
            markdown = timeline.render_markdown(events)

        self.assertEqual(len(events), 1)
        self.assertIn("provider_watch", markdown)
        self.assertNotIn("vless" + "://", markdown)
        self.assertNotIn("BEGIN " + "OPENSSH " + "PRIVATE KEY", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
