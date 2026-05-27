#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO_MONITOR = ROOT / "mesh-runtime" / "auto_monitor.py"


def load_function(name: str, extra_globals: dict | None = None):
    tree = ast.parse(AUTO_MONITOR.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = dict(extra_globals or {})
    exec(compile(module, str(AUTO_MONITOR), "exec"), namespace)
    return namespace[name]


class AutoMonitorSourceTests(unittest.TestCase):
    def test_format_secondary_failures_combines_probe_context(self) -> None:
        formatter = load_function("format_secondary_failures")

        suffix = formatter(
            {
                "probes": {
                    "secondary_listener_failures": [2083, 39829],
                    "xui_auxiliary_listener_status": {"2083": True, "39829": False},
                    "listener_loss_detector": {
                        "present": True,
                        "status": "ANOMALY_DETECTED",
                        "confidence": 0.42,
                        "stale": True,
                    },
                }
            }
        )

        self.assertIn("secondary_failures=2083,39829", suffix)
        self.assertIn("xui_aux_failures=39829", suffix)
        self.assertIn("listener_detector_status=ANOMALY_DETECTED", suffix)
        self.assertIn("confidence=0.42", suffix)
        self.assertIn("stale=true", suffix)
        self.assertEqual(formatter({"probes": {}}), "")

    def test_send_alert_keeps_last_100_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = Path(tmpdir) / "alerts.json"
            alert_file.write_text(
                json.dumps(
                    [
                        {"timestamp": "old", "level": "INFO", "message": f"old-{idx}"}
                        for idx in range(105)
                    ]
                ),
                encoding="utf-8",
            )
            logger = FakeLogger()
            send_alert = load_function(
                "send_alert",
                {
                    "ALERT_FILE": alert_file,
                    "datetime": datetime,
                    "json": json,
                    "logger": logger,
                },
            )

            send_alert("WARNING", "new warning")
            alerts = json.loads(alert_file.read_text(encoding="utf-8"))

        self.assertEqual(len(alerts), 100)
        self.assertEqual(alerts[-1]["level"], "WARNING")
        self.assertEqual(alerts[-1]["message"], "new warning")
        self.assertEqual(logger.warnings, ["new warning"])

    def test_auto_monitor_has_no_direct_service_mutation_commands(self) -> None:
        text = AUTO_MONITOR.read_text(encoding="utf-8")

        for forbidden in ("systemctl", "service ", "iptables", "ip route", "restart"):
            self.assertNotIn(forbidden, text)
        self.assertIn("/opt/x0tta6bl4-mesh/scripts/build_runtime_state.py", text)


class FakeLogger:
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)


if __name__ == "__main__":
    unittest.main()
