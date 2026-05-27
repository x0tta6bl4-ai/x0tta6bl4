#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("refresh_vpn_planning_reports.py")
SPEC = importlib.util.spec_from_file_location("refresh_vpn_planning_reports", MODULE_PATH)
assert SPEC and SPEC.loader
refresh = importlib.util.module_from_spec(SPEC)
sys.modules["refresh_vpn_planning_reports"] = refresh
SPEC.loader.exec_module(refresh)


class RefreshVpnPlanningReportsTests(unittest.TestCase):
    def test_latest_snapshot_uses_lexicographic_timestamp_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "20260527T221810Z").mkdir()
            (root / "20260527T210659Z").mkdir()

            latest = refresh.latest_snapshot(root)

        self.assertEqual(latest.name, "20260527T221810Z")

    def test_command_plan_is_local_only_and_ordered(self):
        snapshot = Path("nl-diagnostics/snapshots/20260527T221810Z")
        plan = refresh.command_plan(snapshot, Path("nl-diagnostics"))

        self.assertEqual(
            [item["id"] for item in plan],
            [
                "blocking_history",
                "decision_report",
                "boot_gap_watch",
                "provider_packet",
                "improvement_backlog",
                "manual_failover_plan",
                "nl_transport_probe",
                "secondary_probe_template_check",
                "operator_card",
                "readiness_audit",
            ],
        )
        for item in plan:
            self.assertTrue(refresh.command_is_local_only(item["command"]))
            self.assertNotIn("collect_vpn_readonly_snapshot.sh", " ".join(item["command"]))

    def test_provider_packet_paths_are_snapshot_stable(self):
        paths = refresh.provider_packet_paths(
            Path("nl-diagnostics/snapshots/20260527T221810Z"),
            Path("nl-diagnostics"),
        )

        self.assertEqual(
            paths,
            [
                "nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T221810Z.json",
                "nl-diagnostics/provider-incident-packets/provider-incident-packet-20260527T221810Z.md",
            ],
        )

    def test_run_plan_blocks_non_local_command(self):
        plan = [{"id": "bad", "command": ["ssh", "nl", "true"], "outputs": []}]

        rows = refresh.run_plan(plan, cwd=Path("/mnt/projects"))

        self.assertFalse(rows[0]["ok"])
        self.assertEqual(rows[0]["exit_code"], 126)

    def test_run_plan_records_successful_steps(self):
        def runner(command, cwd, stdout, stderr, text, check):
            return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

        rows = refresh.run_plan(
            [{"id": "ok", "command": ["python3", "tool.py"], "outputs": ["out.json"]}],
            cwd=Path("/mnt/projects"),
            runner=runner,
        )

        self.assertTrue(rows[0]["ok"])
        self.assertEqual(rows[0]["outputs"], ["out.json"])


if __name__ == "__main__":
    unittest.main()
