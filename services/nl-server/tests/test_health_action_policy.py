#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mesh-runtime" / "health_action_policy.py"


def load_module():
    spec = importlib.util.spec_from_file_location("health_action_policy", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def restart_state(**overrides):
    state = {
        "recommended_action": "restart_primary",
        "probes": {
            "listener_443_ok": False,
            "xui_service_ok": False,
        },
    }
    state.update(overrides)
    return state


class HealthActionPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_observe_action_never_restarts(self) -> None:
        decision = self.module.decide_xui_restart(
            {"recommended_action": "observe"},
            mutation_allowed=True,
            now_epoch=2000,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "observe")

    def test_requires_explicit_mutation_flag(self) -> None:
        decision = self.module.decide_xui_restart(
            restart_state(),
            mutation_allowed=False,
            now_epoch=2000,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "blocked_mutation_flag")

    def test_provider_guard_blocks_restart_before_mutation(self) -> None:
        decision = self.module.decide_xui_restart(
            restart_state(provider_status="provider_outage"),
            mutation_allowed=True,
            now_epoch=2000,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "blocked_provider_guard")

    def test_cooldown_is_30_minutes_by_default(self) -> None:
        decision = self.module.decide_xui_restart(
            restart_state(),
            mutation_allowed=True,
            now_epoch=2000,
            last_restart_epoch=1000,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "blocked_cooldown")
        self.assertEqual(decision.cooldown_remaining_sec, 800)

    def test_all_gates_pass_restart_allowed(self) -> None:
        decision = self.module.decide_xui_restart(
            restart_state(),
            mutation_allowed=True,
            now_epoch=4000,
            last_restart_epoch=1000,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.decision, "restart_xui")

    def test_healthy_primary_does_not_restart_even_with_flag(self) -> None:
        decision = self.module.decide_xui_restart(
            restart_state(
                probes={
                    "listener_443_ok": True,
                    "xui_service_ok": True,
                }
            ),
            mutation_allowed=True,
            now_epoch=4000,
            last_restart_epoch=0,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.decision, "observe")


if __name__ == "__main__":
    unittest.main()
