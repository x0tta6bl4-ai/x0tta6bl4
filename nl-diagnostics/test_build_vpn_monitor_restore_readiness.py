#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_vpn_monitor_restore_readiness.py")
SPEC = importlib.util.spec_from_file_location("build_vpn_monitor_restore_readiness", MODULE_PATH)
assert SPEC and SPEC.loader
readiness = importlib.util.module_from_spec(SPEC)
sys.modules["build_vpn_monitor_restore_readiness"] = readiness
SPEC.loader.exec_module(readiness)


def decision() -> dict:
    return {
        "decision": {
            "decision": "restore_transport_canary_monitor",
            "mutation_allowed": False,
            "nl_mutation_allowed": False,
            "auto_profile_switch_allowed": False,
            "spb_fallback_allowed": False,
        },
        "classification": {
            "failure_domain": "monitoring",
            "recommended_action": "restore_transport_canary_monitor",
            "blocking_assessment": {"category": "monitoring_gap"},
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
        "spb_fallback_allowed": False,
    }


def goal_status() -> dict:
    return {
        "decision": "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE",
        "requirements": [
            {
                "id": "CORE-REALITY-01",
                "status": "missing",
                "next_step": (
                    "run restore_nl_vpn_monitor_canary_timer.sh --dry-run/--precheck, "
                    "then apply only after APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER and collect a fresh snapshot"
                ),
            }
        ],
        "no_nl_or_spb_writes_performed": True,
    }


def script_text() -> str:
    return """
MODE="dry-run"
REQUIRED_CONFIRM="APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER"
CONFIRM_VALUE="${RESTORE_NL_VPN_MONITOR_CONFIRM:-}"
if [[ "$CONFIRM_VALUE" != "$REQUIRED_CONFIRM" ]]; then exit 2; fi
sudo systemctl enable --now ghost-access-vpn-monitor.timer
sudo systemctl start ghost-access-vpn-monitor.service
sudo systemctl start x0tta6bl4-runtime-state.service
printf "rollback_hint=sudo systemctl disable --now ghost-access-vpn-monitor.timer\\n"
"""


class VpnMonitorRestoreReadinessTests(unittest.TestCase):
    def test_ready_for_approval_when_decision_goal_and_script_align(self):
        payload = readiness.build_payload(
            decision=decision(),
            goal_status=goal_status(),
            script_text=script_text(),
        )

        self.assertEqual(payload["decision"], "MONITOR_RESTORE_READY_FOR_APPROVAL")
        self.assertTrue(payload["ready_for_approval"])
        self.assertFalse(payload["apply_allowed_now"])
        self.assertEqual(payload["approval_phrase"], "APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER")

    def test_provider_ticket_decision_blocks_monitor_restore_packet(self):
        current = decision()
        current["decision"]["decision"] = "provider_ticket"

        payload = readiness.build_payload(
            decision=current,
            goal_status=goal_status(),
            script_text=script_text(),
        )

        self.assertEqual(payload["decision"], "MONITOR_RESTORE_NOT_READY")
        self.assertFalse(payload["ready_for_approval"])

    def test_forbidden_restart_blocks_script_gate(self):
        payload = readiness.build_payload(
            decision=decision(),
            goal_status=goal_status(),
            script_text=script_text() + "\nsystemctl restart x-ui\n",
        )

        script_gate = next(row for row in payload["gates"] if row["id"] == "SCRIPT-01")
        self.assertEqual(script_gate["status"], readiness.MISSING)
        self.assertFalse(payload["ready_for_approval"])

    def test_markdown_contains_no_write_notice_and_commands(self):
        payload = readiness.build_payload(
            decision=decision(),
            goal_status=goal_status(),
            script_text=script_text(),
        )

        markdown = readiness.render_markdown(payload)

        self.assertIn("VPN Monitor Restore Readiness", markdown)
        self.assertIn("restore_nl_vpn_monitor_canary_timer.sh", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
