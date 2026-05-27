#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mesh-runtime" / "full_stealth_config.py"


def load_module():
    spec = importlib.util.spec_from_file_location("full_stealth_config_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class FullStealthConfigSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_rotated_short_ids_have_expected_shape(self) -> None:
        ids = self.module.rotate_short_ids()

        self.assertEqual(len(ids), 3)
        for short_id in ids:
            self.assertRegex(short_id, r"^[0-9a-f]{2}$")

    def test_tls_profile_is_from_known_set(self) -> None:
        self.assertIn(self.module.rotate_tls_profile(), self.module.TLS_PROFILES)
        self.assertGreaterEqual(len(self.module.TLS_PROFILES), 3)

    def test_source_is_class_c_mutating_tool(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")

        self.assertIn("/usr/local/x-ui/bin/config.json", text)
        self.assertIn("/opt/x0tta6bl4-mesh/configs/rotation_metadata.json", text)
        self.assertRegex(text, re.compile(r'open\(CONFIG_FILE,\s*"w"\)'))
        self.assertIn("os.chmod(CONFIG_FILE, 0o644)", text)


if __name__ == "__main__":
    unittest.main()
