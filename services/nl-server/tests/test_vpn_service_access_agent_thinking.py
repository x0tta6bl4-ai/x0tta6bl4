#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "run_vpn_service_access_agent.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_vpn_service_access_agent", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class VpnServiceAccessAgentThinkingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_thinking_context_is_privacy_safe_and_role_specific(self) -> None:
        context = self.module._thinking_context(
            "vpn_service_access_probe",
            "Compare transport paths without leaking secrets.",
            {"service_count": 3},
        )

        self.assertEqual(
            context["contract"]["role"],
            "vpn_service_access_probe_agent",
        )
        self.assertIn("weighted_decision_matrix", context["contract"]["techniques"])
        self.assertEqual(
            context["applied"]["framing"]["problem"],
            "vpn_service_access_probe",
        )
        self.assertNotIn("vless://", str(context))
        self.assertNotIn("/sub/", str(context))


if __name__ == "__main__":
    unittest.main()
