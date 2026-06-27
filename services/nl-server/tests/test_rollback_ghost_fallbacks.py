#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "rollback_ghost_fallbacks.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rollback_ghost_fallbacks", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, args):
        command = tuple(args)
        self.calls.append(command)
        if command[:2] == ("systemctl", "is-active"):
            return self.result(0, "active\n")
        return self.result(0, "")

    @staticmethod
    def result(returncode: int, stdout: str):
        module = load_module()
        return module.CommandResult(returncode, stdout, "")


class RollbackGhostFallbacksTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_update_env_lines_updates_existing_and_appends_missing_flags(self) -> None:
        lines = [
            "TELEGRAM_BOT_TOKEN=secret",
            "EXPOSE_FALLBACK_TRANSPORTS=1",
            "ENABLE_GHOST_XHTTP_FALLBACK=1",
        ]

        updated = self.module.update_env_lines(lines, self.module.FALLBACK_ENV_UPDATES)

        self.assertIn("TELEGRAM_BOT_TOKEN=secret", updated)
        self.assertIn("EXPOSE_FALLBACK_TRANSPORTS=0", updated)
        self.assertIn("ENABLE_GHOST_XHTTP_FALLBACK=0", updated)
        self.assertIn("ENABLE_GHOST_HTTPS_WS_FALLBACK=0", updated)

    def test_dry_run_plan_is_read_only_and_mentions_delivery_only_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = Path(tmpdir) / ".env"
            env.write_text(
                "EXPOSE_FALLBACK_TRANSPORTS=1\n"
                "ENABLE_GHOST_XHTTP_FALLBACK=1\n"
                "ENABLE_GHOST_HTTPS_WS_FALLBACK=1\n"
                "PRIVATE_TOKEN=do-not-render\n",
                encoding="utf-8",
            )
            runner = FakeRunner()

            plan = self.module.build_plan(env, "delivery-only", runner)

        self.assertEqual(plan["current_env_flags"]["EXPOSE_FALLBACK_TRANSPORTS"], "1")
        self.assertEqual(plan["target_env_flags"]["ENABLE_GHOST_XHTTP_FALLBACK"], "0")
        rendered = str(plan)
        self.assertNotIn("do-not-render", rendered)
        self.assertIn("dry-run is read-only", rendered)
        self.assertNotIn(("systemctl", "restart", "telegram-bot-simple.service"), runner.calls)

    def test_apply_without_confirm_is_blocked_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = Path(tmpdir) / ".env"
            original = "EXPOSE_FALLBACK_TRANSPORTS=1\n"
            env.write_text(original, encoding="utf-8")
            runner = FakeRunner()

            result = self.module.apply_plan(
                env,
                "delivery-only",
                confirm=None,
                service_stop_confirm=None,
                skip_safety_checks=False,
                runner=runner,
            )

            self.assertFalse(result["ok"])
            self.assertEqual(result["decision"], "ROLLBACK_BLOCKED")
            self.assertEqual(env.read_text(encoding="utf-8"), original)

    def test_delivery_only_apply_updates_env_and_restarts_bot_without_stopping_services(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = Path(tmpdir) / ".env"
            env.write_text(
                "EXPOSE_FALLBACK_TRANSPORTS=1\n"
                "ENABLE_GHOST_XHTTP_FALLBACK=1\n"
                "ENABLE_GHOST_HTTPS_WS_FALLBACK=1\n",
                encoding="utf-8",
            )
            runner = FakeRunner()

            result = self.module.apply_plan(
                env,
                "delivery-only",
                confirm=self.module.CONFIRM_TOKEN,
                service_stop_confirm=None,
                skip_safety_checks=False,
                runner=runner,
            )

            self.assertTrue(result["ok"])
            updated = env.read_text(encoding="utf-8")
            self.assertIn("EXPOSE_FALLBACK_TRANSPORTS=0", updated)
            self.assertIn("ENABLE_GHOST_XHTTP_FALLBACK=0", updated)
            self.assertIn("ENABLE_GHOST_HTTPS_WS_FALLBACK=0", updated)
            self.assertIn(
                ("systemctl", "restart", "telegram-bot-simple.service"),
                runner.calls,
            )
            self.assertFalse(
                any(call[:3] == ("systemctl", "disable", "--now") for call in runner.calls)
            )

    def test_stop_services_mode_requires_second_confirm(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = Path(tmpdir) / ".env"
            original = "EXPOSE_FALLBACK_TRANSPORTS=1\n"
            env.write_text(original, encoding="utf-8")

            result = self.module.apply_plan(
                env,
                "stop-services",
                confirm=self.module.CONFIRM_TOKEN,
                service_stop_confirm=None,
                skip_safety_checks=False,
                runner=FakeRunner(),
            )

            self.assertFalse(result["ok"])
            self.assertIn("service-stop-confirm", " ".join(result["errors"]))
            self.assertEqual(env.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
