#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_local_root_cleanup_approval_packet.py")
SPEC = importlib.util.spec_from_file_location("build_local_root_cleanup_approval_packet", MODULE_PATH)
assert SPEC and SPEC.loader
packet = importlib.util.module_from_spec(SPEC)
sys.modules["build_local_root_cleanup_approval_packet"] = packet
SPEC.loader.exec_module(packet)


def local_env(cleanup_required: bool = True) -> dict:
    return {
        "status": "watch_root_full_tmpdir_available",
        "summary": {
            "root_status": "critical_full",
            "root_free_gib": 0.0,
            "diagnostic_tmpdir": "/mnt/projects/.tmp",
            "diagnostic_tmpdir_writable": True,
            "cleanup_required": cleanup_required,
        },
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def cleanup_plan(status: str = "manual_cleanup_plan_ready") -> dict:
    return {
        "status": status,
        "summary": {
            "existing_candidate_count": 2,
            "estimated_reclaim_gib": 1.5,
            "cleanup_execute_allowed": False,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "candidates": [
            {
                "id": "APT-CACHE-01",
                "path": "/var/cache/apt/archives",
                "exists": True,
                "size_gib": 0.85,
                "risk": "low_standard_cache",
                "command_preview": "sudo apt-get clean",
            },
            {
                "id": "TMP-ANTIGRAVITY-01",
                "path": "/tmp/antigravity_restore",
                "exists": True,
                "size_gib": 0.67,
                "risk": "medium_manual_review",
                "command_preview": "sudo rm -rf /tmp/antigravity_restore",
            },
        ],
        "review_order": ["TMP-ANTIGRAVITY-01", "APT-CACHE-01"],
        "cleanup_execute_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


class LocalRootCleanupApprovalPacketTests(unittest.TestCase):
    def test_packet_ready_sorts_low_risk_cache_first(self):
        payload = packet.build_payload(local_env=local_env(), cleanup_plan=cleanup_plan())

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "cleanup_approval_packet_ready")
        self.assertTrue(payload["summary"]["approval_required"])
        self.assertEqual(payload["summary"]["commands_executed"], 0)
        self.assertEqual(payload["summary"]["first_review_id"], "APT-CACHE-01")
        self.assertEqual(payload["command_previews"][0]["approval_level"], "single_command_approval")
        self.assertFalse(payload["cleanup_execute_allowed"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_unsafe_cleanup_execute_flag_fails_packet(self):
        plan = cleanup_plan()
        plan["cleanup_execute_allowed"] = True

        payload = packet.build_payload(local_env=local_env(), cleanup_plan=plan)

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "cleanup_approval_packet_unsafe_flags")

    def test_no_cleanup_needed_status_is_safe(self):
        payload = packet.build_payload(
            local_env=local_env(cleanup_required=False),
            cleanup_plan=cleanup_plan("no_cleanup_needed"),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "cleanup_approval_packet_no_cleanup_needed")

    def test_markdown_contains_precheck_postcheck_and_no_execution_notice(self):
        markdown = packet.render_markdown(packet.build_payload(local_env=local_env(), cleanup_plan=cleanup_plan()))

        self.assertIn("Precheck Commands", markdown)
        self.assertIn("Postcheck Commands", markdown)
        self.assertIn("No cleanup, NL writes, or SPB fallback", markdown)
        self.assertIn("cleanup_execute_allowed=false", markdown)


if __name__ == "__main__":
    unittest.main()
