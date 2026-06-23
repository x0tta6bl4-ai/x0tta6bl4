#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "ghost-access" / "plan_telegram_media_warp_route.py"


def load_module():
    spec = importlib.util.spec_from_file_location("plan_telegram_media_warp_route", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def config_summary() -> dict:
    return {
        "outbound_tags": ["direct", "warp", "blocked"],
        "routing_rule_count": 10,
    }


def runtime_summary() -> dict:
    return {
        "reason": "telegram media edges are slow from the current egress path",
        "hot_path_summary": {
            "telegram_media_status": "degraded",
            "warp_status": "healthy",
        },
    }


class TelegramMediaWarpRoutePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_build_plan_selects_warp_route_when_warp_exists(self) -> None:
        plan = self.module.build_plan(
            config_summary=config_summary(),
            runtime_summary=runtime_summary(),
            generated_at="2026-06-02T03:00:00Z",
        )

        self.assertEqual(plan["decision"], "TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE")
        self.assertEqual(plan["blockers"], [])
        self.assertEqual(plan["target_rule"]["outboundTag"], "warp")
        self.assertIn("149.154.160.0/20", plan["target_rule"]["ip"])
        self.assertIn("91.108.56.0/22", plan["target_rule"]["ip"])
        self.assertEqual(plan["current_evidence"]["warp_status"], "healthy")
        self.assertTrue(plan["privacy"]["output_privacy_ok"])

    def test_plan_blocks_when_warp_outbound_missing(self) -> None:
        summary = config_summary()
        summary["outbound_tags"] = ["direct", "blocked"]

        plan = self.module.build_plan(
            config_summary=summary,
            runtime_summary=runtime_summary(),
            generated_at="2026-06-02T03:00:00Z",
        )

        self.assertEqual(plan["decision"], "TELEGRAM_MEDIA_WARP_ROUTE_BLOCKED")
        self.assertIn("xray_warp_outbound_missing", plan["blockers"])

    def test_apply_rule_inserts_before_direct_catchall_and_is_idempotent(self) -> None:
        config = {
            "outbounds": [{"tag": "direct"}, {"tag": "warp"}],
            "routing": {
                "rules": [
                    {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
                    {"type": "field", "network": ["tcp", "udp"], "outboundTag": "direct"},
                ]
            },
        }

        updated, patch = self.module.apply_telegram_media_warp_rule(config)

        self.assertTrue(patch["changed"])
        self.assertEqual(patch["reason"], "insert_before_direct_catchall")
        self.assertEqual(updated["routing"]["rules"][1]["outboundTag"], "warp")
        self.assertEqual(updated["routing"]["rules"][2]["outboundTag"], "direct")

        updated_again, patch_again = self.module.apply_telegram_media_warp_rule(updated)

        self.assertFalse(patch_again["changed"])
        self.assertEqual(updated_again, updated)

    def test_cli_writes_privacy_safe_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_summary_path = tmp / "summary.json"
            runtime_summary_path = tmp / "runtime.json"
            json_out = tmp / "plan.json"
            md_out = tmp / "plan.md"
            config_summary_path.write_text(
                "# command: redacted\n" + json.dumps(config_summary()),
                encoding="utf-8",
            )
            runtime_summary_path.write_text(json.dumps(runtime_summary()), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = self.module.run(
                    [
                        "--config-summary",
                        str(config_summary_path),
                        "--runtime-summary",
                        str(runtime_summary_path),
                        "--json-out",
                        str(json_out),
                        "--markdown-out",
                        str(md_out),
                        "--write",
                        "--json",
                    ]
                )
            payload = json.loads(stdout.getvalue())
            markdown = md_out.read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        self.assertEqual(payload["decision"], "TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE")
        self.assertIn("Telegram media", markdown)
        self.assertNotIn("vless://", markdown)
        self.assertNotIn("subscription", markdown.lower())


if __name__ == "__main__":
    unittest.main()
