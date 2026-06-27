#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mesh-runtime" / "rotation_timer.sh"


class RotationTimerSourceTests(unittest.TestCase):
    def test_rotation_timer_shell_syntax(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(SOURCE)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rotation_timer_is_class_c_signal_tool(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")

        self.assertIn("/opt/x0tta6bl4-mesh/scripts/full_stealth_config.py", text)
        self.assertIn("pkill -USR1", text)
        self.assertIn("xray-linux-amd64.real -c bin/config.json", text)
        self.assertIn("ss -ltnp", text)
        self.assertNotIn("systemctl restart", text)


if __name__ == "__main__":
    unittest.main()
