#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ListenerLossSignalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(
            "listener_loss_signal",
            ROOT / "mesh-runtime" / "listener_loss_signal.py",
        )

    def test_missing_listener_is_anomaly(self) -> None:
        metrics = {
            "listening_sockets": 0,
            "established_connections": 0,
            "time_wait_connections": 0,
            "syn_recv_connections": 0,
        }

        confidence = self.module.score(metrics)
        status, reason = self.module.classify(metrics, confidence)

        self.assertEqual(confidence, 0.0)
        self.assertEqual(status, "ANOMALY_DETECTED")
        self.assertEqual(reason, "primary listener missing")

    def test_healthy_listener_is_baseline(self) -> None:
        metrics = {
            "listening_sockets": 1,
            "established_connections": 20,
            "time_wait_connections": 0,
            "syn_recv_connections": 0,
        }

        confidence = self.module.score(metrics)
        status, reason = self.module.classify(metrics, confidence)

        self.assertEqual(confidence, 1.0)
        self.assertEqual(status, "BASELINE_OK")
        self.assertIn("normal", reason)

    def test_tcp_symptom_pattern_is_anomaly(self) -> None:
        metrics = {
            "listening_sockets": 1,
            "established_connections": 0,
            "time_wait_connections": 15,
            "syn_recv_connections": 8,
        }

        confidence = self.module.score(metrics)
        status, reason = self.module.classify(metrics, confidence)

        self.assertLess(confidence, 0.70)
        self.assertEqual(status, "ANOMALY_DETECTED")
        self.assertIn("degraded", reason)


class ClientProfileHintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(
            "publish_client_profile_hint",
            ROOT / "mesh-runtime" / "publish_client_profile_hint.py",
        )

    def test_degraded_mode_prefers_non_443_public_ports(self) -> None:
        hint = self.module.choose_hint(
            {
                "mode": "degraded",
                "reason": "listener-loss detector reported anomaly",
                "probes": {
                    "public_listener_status": {
                        "443": True,
                        "2083": True,
                        "39829": True,
                    }
                },
            }
        )

        self.assertEqual(hint["recommended_profile"], "anti-block-public-ingress")
        self.assertEqual(hint["candidate_ports"], [2083, 39829])

    def test_advisory_mode_keeps_stable_primary(self) -> None:
        hint = self.module.choose_hint(
            {
                "mode": "advisory",
                "reason": "telegram media edges are slow",
                "probes": {
                    "public_listener_status": {
                        "443": True,
                        "2083": True,
                        "39829": True,
                    }
                },
            }
        )

        self.assertEqual(hint["recommended_profile"], "stable-primary")
        self.assertEqual(hint["candidate_ports"], [443])

    def test_fallback_mode_uses_ghost_transport(self) -> None:
        hint = self.module.choose_hint({"mode": "fallback", "reason": "x-ui inactive"})

        self.assertEqual(hint["recommended_profile"], "ghost-fallback")
        self.assertEqual(hint["transport_family"], "ghostvpn")
        self.assertEqual(hint["candidate_ports"], [4433, 4434])

    def test_load_runtime_state_missing_or_invalid_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing = root / "missing.json"
            invalid = root / "runtime-state.json"
            invalid.write_text("{bad-json", encoding="utf-8")

            self.module.RUNTIME_STATE_PATH = missing
            self.assertEqual(self.module.load_runtime_state(), {})

            self.module.RUNTIME_STATE_PATH = invalid
            self.assertEqual(self.module.load_runtime_state(), {})

    def test_load_runtime_state_accepts_dict_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "runtime-state.json"
            path.write_text(json.dumps([{"mode": "ok"}]), encoding="utf-8")

            self.module.RUNTIME_STATE_PATH = path

            self.assertEqual(self.module.load_runtime_state(), {})


if __name__ == "__main__":
    unittest.main()
