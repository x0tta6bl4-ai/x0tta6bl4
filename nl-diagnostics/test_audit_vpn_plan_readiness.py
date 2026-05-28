#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("audit_vpn_plan_readiness.py")
SPEC = importlib.util.spec_from_file_location("audit_vpn_plan_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules["audit_vpn_plan_readiness"] = audit
SPEC.loader.exec_module(audit)

FRESH_NOW = datetime(2026, 5, 27, 23, 10, tzinfo=timezone.utc)
STALE_NOW = datetime(2026, 5, 28, 2, 30, tzinfo=timezone.utc)


def sample_decision() -> dict:
    return {
        "snapshot": "nl-diagnostics/snapshots/20260527T230246Z",
        "decision": {
            "decision": "observe",
            "confidence": "high",
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "auto_profile_switch_allowed": False,
            "spb_fallback_allowed": False,
        },
        "classification": {
            "transport_status": "healthy",
            "failure_domain": "external_network",
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def sample_history() -> dict:
    return {
        "summary": {
            "snapshot_count": 4,
            "trend": "stable_no_probe_evidence",
            "latest": {
                "snapshot": "20260527T230246Z",
                "target_count": 8,
                "ok_count": 8,
            },
        }
    }


def sample_boot_gap() -> dict:
    return {
        "status": "watch",
        "boot_gap_seconds": 21907,
        "classification": {
            "provider_status": "recent_boot_gap",
            "transport_status": "healthy",
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_provider_packet() -> dict:
    return {
        "packet_type": "provider_watch",
        "snapshot_dir": "nl-diagnostics/snapshots/20260527T230246Z",
        "snapshot_stale": False,
        "nl_write_performed": False,
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_refresh() -> dict:
    return {
        "snapshot": "nl-diagnostics/snapshots/20260527T230246Z",
        "ok": True,
        "summary": {
            "operator_status": "observe",
            "manual_failover_status": "planning_not_active",
            "nl_mutation_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_operator_card() -> dict:
    return {
        "operator": {
            "operator_status": "observe",
            "plain_action": "VPN core is healthy.",
        },
        "current_state": {"blocking_history_trend": "stable_no_probe_evidence"},
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_failover() -> dict:
    return {
        "status": "planning_not_active",
        "summary": {
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_transport_probe() -> dict:
    return {
        "status": "healthy",
        "ok_count": 3,
        "port_count": 3,
        "failure_domain_hint": "none",
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_transport_uptime() -> dict:
    return {
        "summary": {
            "status": "stable_healthy",
            "sample_count": 1,
            "latest_status": "healthy",
            "consecutive_non_healthy": 0,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_secondary() -> dict:
    return {
        "status": "planning_template",
        "candidate_configured": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def sample_manifest() -> dict:
    return {
        "nl_write_allowed": False,
        "gap_summary": {
            "accepted_local_delta": 5,
            "missing_local_source": 0,
            "local_name_drift": 0,
        },
        "source_promotion_status": {"deployable_to_nl": False},
        "inactive_integrations": [
            {
                "name": "spb_standalone_xray",
                "enabled": False,
            }
        ],
    }


def sample_preflight() -> dict:
    return {
        "ok": True,
        "deploy_status": "local_ready_but_deploy_blocked",
        "nl_write_allowed": False,
        "checks": [{"name": "manifest_json", "ok": True}],
    }


def sample_inputs() -> dict:
    return {
        "decision": sample_decision(),
        "boot_gap": sample_boot_gap(),
        "provider_packet": sample_provider_packet(),
        "history": sample_history(),
        "refresh": sample_refresh(),
        "operator_card": sample_operator_card(),
        "failover": sample_failover(),
        "transport_probe": sample_transport_probe(),
        "transport_uptime": sample_transport_uptime(),
        "secondary": sample_secondary(),
        "manifest": sample_manifest(),
        "preflight": sample_preflight(),
        "approval_text": audit.APPROVAL_PHRASE,
        "report_texts": ["spb_fallback_allowed=false"],
    }


def prepare_root(root: Path) -> None:
    (root / "nl-diagnostics" / "snapshots" / "20260527T230246Z").mkdir(parents=True)
    systemd = root / "infra" / "systemd"
    systemd.mkdir(parents=True)
    (systemd / "x0tta-vpn-nl-transport-uptime.service").write_text(
        "\n".join(
            [
                "[Service]",
                "Type=oneshot",
                "ExecStart=/usr/bin/python3 /mnt/projects/nl-diagnostics/probe_nl_transport_ports.py",
                "ExecStart=/usr/bin/python3 /mnt/projects/nl-diagnostics/record_nl_transport_uptime.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (systemd / "x0tta-vpn-nl-transport-uptime.timer").write_text(
        "\n".join(
            [
                "[Timer]",
                "OnUnitActiveSec=5min",
                "Unit=x0tta-vpn-nl-transport-uptime.service",
                "",
            ]
        ),
        encoding="utf-8",
    )


class VpnPlanReadinessAuditTests(unittest.TestCase):
    def test_ready_audit_has_future_blocks_but_no_missing_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)

            payload = audit.build_payload(sample_inputs(), root=root, now=FRESH_NOW)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["overall_status"], "ready_local_with_future_blocks")
        self.assertEqual(payload["summary"]["missing"], 0)
        self.assertEqual(payload["summary"]["watch"], 1)
        self.assertGreaterEqual(payload["summary"]["ready_local"], 1)
        self.assertIn("BOOT-01", payload["summary"]["watch_items"])
        self.assertIn("GATE-01", payload["summary"]["blocked_items"])
        self.assertIn("FAILOVER-02", payload["summary"]["blocked_items"])
        self.assertEqual(payload["summary"]["boot_gap_watch_status"], "watch")
        self.assertEqual(payload["summary"]["provider_packet_type"], "provider_watch")
        self.assertFalse(payload["summary"]["provider_packet_stale"])
        self.assertEqual(payload["summary"]["transport_probe_status"], "healthy")
        self.assertEqual(payload["summary"]["transport_uptime_status"], "stable_healthy")
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_degraded_transport_probe_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["transport_probe"] = {
                **sample_transport_probe(),
                "status": "degraded",
                "ok_count": 2,
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        transport = next(item for item in payload["items"] if item["id"] == "TRANSPORT-01")
        self.assertEqual(transport["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_degraded_uptime_history_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["transport_uptime"] = {
                **sample_transport_uptime(),
                "summary": {
                    **sample_transport_uptime()["summary"],
                    "status": "watch",
                    "latest_status": "degraded",
                    "consecutive_non_healthy": 1,
                },
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        uptime_item = next(item for item in payload["items"] if item["id"] == "UPTIME-01")
        self.assertEqual(uptime_item["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_stale_snapshot_chain_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)

            payload = audit.build_payload(sample_inputs(), root=root, now=STALE_NOW)

        evidence = next(item for item in payload["items"] if item["id"] == "EVIDENCE-01")
        self.assertEqual(evidence["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_stale_provider_packet_is_watch_not_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["provider_packet"] = {
                **sample_provider_packet(),
                "snapshot_stale": True,
            }

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        provider = next(item for item in payload["items"] if item["id"] == "PROVIDER-01")
        self.assertEqual(provider["status"], audit.WATCH)
        self.assertTrue(payload["ok"])

    def test_spb_true_marker_makes_audit_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["report_texts"] = ["spb_fallback_allowed=true"]

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        spb = next(item for item in payload["items"] if item["id"] == "SPB-01")
        self.assertEqual(spb["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_spb_true_marker_with_colon_makes_audit_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["report_texts"] = ['"spb_fallback_allowed": true']

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        spb = next(item for item in payload["items"] if item["id"] == "SPB-01")
        self.assertEqual(spb["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_missing_approval_phrase_keeps_future_write_gate_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            inputs = sample_inputs()
            inputs["approval_text"] = "different text"

            payload = audit.build_payload(inputs, root=root, now=FRESH_NOW)

        gate = next(item for item in payload["items"] if item["id"] == "GATE-01")
        self.assertEqual(gate["status"], audit.MISSING)
        self.assertFalse(payload["ok"])

    def test_markdown_renders_matrix_and_no_write_notice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare_root(root)
            payload = audit.build_payload(sample_inputs(), root=root, now=FRESH_NOW)

        markdown = audit.render_markdown(payload)

        self.assertIn("Readiness Matrix", markdown)
        self.assertIn("blocked_future_approval", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
