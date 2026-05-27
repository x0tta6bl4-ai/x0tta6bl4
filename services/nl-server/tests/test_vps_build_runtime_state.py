#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "mesh-runtime" / "vps_build_runtime_state.py"


def load_module():
    spec = importlib.util.spec_from_file_location("vps_build_runtime_state", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def base_probes(**overrides):
    probes = {
        "xui_service_ok": True,
        "listener_443_ok": True,
        "ghost_ready": False,
        "secondary_listener_failures": [],
        "established_public_total": 3,
        "listener_loss_detector": {},
        "warp_ok": True,
        "transport_summary": {
            "status": "healthy",
            "best_path": "main",
            "telegram_media_status": "healthy",
        },
    }
    probes.update(overrides)
    return probes


class RuntimeStateDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_telegram_degraded_with_healthy_transport_is_advisory(self) -> None:
        probes = base_probes(
            transport_summary={
                "status": "healthy",
                "best_path": "main",
                "telegram_media_status": "degraded",
            }
        )

        mode, action, reason = self.module.decide(probes, {})

        self.assertEqual(mode, "advisory")
        self.assertEqual(action, "observe")
        self.assertIn("transport is usable", reason)

    def test_telegram_degraded_without_transport_health_needs_review(self) -> None:
        probes = base_probes(
            transport_summary={
                "status": "unknown",
                "telegram_media_status": "degraded",
            }
        )

        mode, action, reason = self.module.decide(probes, {})

        self.assertEqual(mode, "degraded")
        self.assertEqual(action, "operator_review")
        self.assertIn("not confirmed", reason)

    def test_xui_inactive_with_ghost_ready_uses_fallback(self) -> None:
        probes = base_probes(xui_service_ok=False, ghost_ready=True)

        mode, action, reason = self.module.decide(probes, {})

        self.assertEqual(mode, "fallback")
        self.assertEqual(action, "switch_fallback")
        self.assertIn("ghost fallback ready", reason)

    def test_xui_inactive_without_ghost_restarts_primary(self) -> None:
        probes = base_probes(xui_service_ok=False, ghost_ready=False)

        mode, action, reason = self.module.decide(probes, {})

        self.assertEqual(mode, "degraded")
        self.assertEqual(action, "restart_primary")
        self.assertIn("x-ui inactive", reason)

    def test_load_public_ports_reads_current_nl_xui_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "inbounds": [
                            {"protocol": "dokodemo-door", "port": 62789},
                            {"protocol": "vless", "port": 39829},
                            {"protocol": "vless", "port": 443},
                            {"protocol": "vless", "port": 2083},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            ports = self.module.load_public_ports([Path(tmpdir) / "missing.json", config_path])

        self.assertEqual(ports, [443, 2083, 39829])

    def test_load_public_ports_default_matches_current_nl_shape(self) -> None:
        self.assertEqual(self.module.load_public_ports([]), [443, 2083, 39829])

    def test_hot_path_summary_uses_real_secondary_port(self) -> None:
        summary = self.module.build_hot_path_summary(
            {
                "transport_summary": {},
                "public_listener_status": {"443": False, "2083": True, "39829": True},
                "listener_443_ok": False,
                "subscription_health_status": "healthy",
                "warp_ok": True,
                "ghost_ready": False,
            },
            "advisory",
            "observe",
            "secondary path available",
        )

        self.assertEqual(summary["best_path"], "secondary")
        self.assertEqual(summary["best_path_port"], 2083)
        self.assertEqual(summary["secondary_path_port"], 2083)
        self.assertEqual(summary["fallback_nl_path_port"], 2443)


if __name__ == "__main__":
    unittest.main()
