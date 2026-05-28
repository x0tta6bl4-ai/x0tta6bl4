#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path("/mnt/projects")
SERVICE = ROOT / "infra/systemd/x0tta-vpn-nl-transport-uptime.service"
TIMER = ROOT / "infra/systemd/x0tta-vpn-nl-transport-uptime.timer"
FORBIDDEN_REMOTE_OR_MUTATION = re.compile(r"\b(ssh|scp|rsync|sudo|systemctl|restart|reload|enable|disable)\b")


class LocalUptimeSystemdTemplateTests(unittest.TestCase):
    def test_service_template_runs_only_local_probe_and_recorder(self):
        text = SERVICE.read_text(encoding="utf-8")

        self.assertIn("Type=oneshot", text)
        self.assertIn("probe_nl_transport_ports.py", text)
        self.assertIn("record_nl_transport_uptime.py", text)
        self.assertNotRegex(text, FORBIDDEN_REMOTE_OR_MUTATION)

    def test_timer_template_is_periodic_and_not_installed_by_test(self):
        text = TIMER.read_text(encoding="utf-8")

        self.assertIn("OnUnitActiveSec=5min", text)
        self.assertIn("Unit=x0tta-vpn-nl-transport-uptime.service", text)
        self.assertNotRegex(text, FORBIDDEN_REMOTE_OR_MUTATION)

    def test_templates_point_to_local_workspace_only(self):
        combined = SERVICE.read_text(encoding="utf-8") + "\n" + TIMER.read_text(encoding="utf-8")

        self.assertIn("/mnt/projects/nl-diagnostics", combined)
        self.assertNotIn("nl:", combined)
        self.assertNotIn("89.125.1.107:/", combined)


if __name__ == "__main__":
    unittest.main()
