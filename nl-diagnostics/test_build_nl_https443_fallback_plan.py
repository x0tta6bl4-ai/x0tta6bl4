#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_nl_https443_fallback_plan.py")
SPEC = importlib.util.spec_from_file_location("build_nl_https443_fallback_plan", MODULE_PATH)
assert SPEC and SPEC.loader
plan = importlib.util.module_from_spec(SPEC)
sys.modules["build_nl_https443_fallback_plan"] = plan
SPEC.loader.exec_module(plan)


def config_summary() -> dict:
    return {
        "inbounds": [
            {
                "tag": "inbound-443",
                "port": 443,
                "protocol": "vless",
                "listen": "0.0.0.0",
                "network": "tcp",
                "security": "reality",
            },
            {
                "tag": "inbound-2083",
                "port": 2083,
                "protocol": "vless",
                "listen": None,
                "network": "tcp",
                "security": "reality",
            },
        ]
    }


def listeners() -> str:
    return "\n".join(
        [
            'tcp LISTEN 0 511 0.0.0.0:8443 0.0.0.0:* users:(("nginx",pid=100,fd=7))',
            'tcp LISTEN 0 65535 *:443 *:* users:(("xray-linux-amd64",pid=939,fd=8))',
            'tcp LISTEN 0 65535 *:2083 *:* users:(("xray-linux-amd64",pid=939,fd=9))',
        ]
    )


def production_audit() -> dict:
    return {
        "client_compatibility_matrix": {
            "current_evidence_session": {
                "required_transport": "xhttp",
                "required_port": 8443,
            }
        }
    }


def transport_probe() -> dict:
    return {
        "status": "healthy",
        "ports": [
            {"port": 443, "ok": True},
            {"port": 2083, "ok": True},
            {"port": 39829, "ok": True},
        ],
    }


def secondary_plan() -> dict:
    return {
        "status": "provisioning_plan_ready_no_endpoint",
        "summary": {"endpoint_count": 0},
    }


def rollout_text() -> str:
    return (
        "fallback path: VLESS over TLS XHTTP on nginx 8443, path /ghost-xhttp\n"
        "fallback path: VLESS over TLS WebSocket on nginx 8443, path /ghost-ws\n"
    )


class NlHttps443FallbackPlanTests(unittest.TestCase):
    def test_all_config_ports_failed_requires_https443_fallback(self):
        payload = plan.build_payload(
            profile_dir=Path("/mnt/projects/nl-diagnostics/nl-server-profile/20260602T181820Z"),
            config_summary=config_summary(),
            listeners_text=listeners(),
            rollout_text=rollout_text(),
            production_audit=production_audit(),
            transport_probe=transport_probe(),
            secondary_provisioning_plan=secondary_plan(),
            user_report_all_config_ports_failed=True,
        )

        self.assertEqual(payload["decision"], "HTTPS443_FALLBACK_REQUIRED")
        self.assertEqual(payload["status"], "ready_to_prepare_secondary_https443_endpoint")
        self.assertTrue(payload["summary"]["current_gap_verified"])
        self.assertEqual(payload["summary"]["public_443_owner"], "xray")
        self.assertFalse(payload["summary"]["in_place_nl_443_change_allowed_now"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertEqual(payload["recommended_path"][1]["minimum_endpoint_shape"]["public_tcp_port"], 443)

    def test_without_user_report_collects_evidence_first(self):
        payload = plan.build_payload(
            profile_dir=Path("/mnt/projects/nl-diagnostics/nl-server-profile/20260602T181820Z"),
            config_summary=config_summary(),
            listeners_text=listeners(),
            rollout_text=rollout_text(),
            production_audit=production_audit(),
            transport_probe=transport_probe(),
            secondary_provisioning_plan=secondary_plan(),
            user_report_all_config_ports_failed=False,
        )

        self.assertEqual(payload["decision"], "RESTRICTED_NETWORK_EVIDENCE_REQUIRED")
        self.assertEqual(payload["status"], "collect_work_wifi_result_first")
        user_gate = next(row for row in payload["gates"] if row["id"] == "USER-01")
        self.assertEqual(user_gate["status"], "blocked")

    def test_missing_profile_blocks_current_state(self):
        payload = plan.build_payload(
            profile_dir=None,
            config_summary={},
            listeners_text="",
            rollout_text=rollout_text(),
            production_audit=production_audit(),
            transport_probe=transport_probe(),
            secondary_provisioning_plan=secondary_plan(),
            user_report_all_config_ports_failed=True,
        )

        self.assertEqual(payload["decision"], "CURRENT_STATE_NEEDS_RECHECK")
        self.assertFalse(payload["ok"])

    def test_markdown_contains_confirm_gate_and_no_write_notice(self):
        payload = plan.build_payload(
            profile_dir=Path("/mnt/projects/nl-diagnostics/nl-server-profile/20260602T181820Z"),
            config_summary=config_summary(),
            listeners_text=listeners(),
            rollout_text=rollout_text(),
            production_audit=production_audit(),
            transport_probe=transport_probe(),
            secondary_provisioning_plan=secondary_plan(),
            user_report_all_config_ports_failed=True,
        )

        markdown = plan.render_markdown(payload)

        self.assertIn("NL HTTPS 443 Fallback Plan", markdown)
        self.assertIn("APPLY_HTTPS443_FALLBACK_PLAN", markdown)
        self.assertIn("No NL or SPB writes", markdown)
        self.assertIn("move NL public 443 from Reality to nginx without tested replacement", markdown)


if __name__ == "__main__":
    unittest.main()
