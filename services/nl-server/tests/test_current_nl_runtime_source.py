#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_HASHES = {
    "ghost-access/run_vpn_delivery_canary.py": "269fb1d88cf6e88f79c020682686019cbb829399aaf98d6ca1a46d36c8f7e050",
    "ghost-access/run_vpn_service_access_agent.py": "e12cfaad1aea267c937a4c9c0536976a0c24ed5b762515cf5a9ff27a85313ae7",
    "ghost-access/xray_runtime_user_manager.py": "3802f64e80e43fd8bdcf36afab6636b7b8a157ec018b2328d1ee258d517c08b4",
    "ghost-access/xui_client_manager.py": "104acccf5ef345e17f7b64c9e85975c2f35b20900b90c291922a3f81b2248769",
    "mesh-runtime/health_check.sh": "3b70430c20c8b828834fc01fc772cb09e149dd3c355fe59f782f9829d71f2590",
}


class CurrentNlRuntimeSourceTests(unittest.TestCase):
    def test_promoted_runtime_sources_match_current_nl_hashes(self) -> None:
        for relative, expected in EXPECTED_HASHES.items():
            with self.subTest(relative=relative):
                actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(actual, expected)

    def test_python_runtime_sources_are_syntax_valid_without_importing(self) -> None:
        for relative in EXPECTED_HASHES:
            if not relative.endswith(".py"):
                continue
            with self.subTest(relative=relative):
                path = ROOT / relative
                ast.parse(path.read_text(encoding="utf-8"))
                subprocess.run([sys.executable, "-m", "py_compile", str(path)], check=True)

    def test_shell_runtime_health_check_is_syntax_valid(self) -> None:
        subprocess.run(["bash", "-n", str(ROOT / "mesh-runtime" / "health_check.sh")], check=True)

    def test_manifest_marks_runtime_sources_class_c_and_not_deployable(self) -> None:
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        rows = {
            row["path"]: row
            for row in manifest["source_promotion_status"]["promoted_files"]
        }

        for relative in EXPECTED_HASHES:
            path = f"services/nl-server/{relative}"
            with self.subTest(path=path):
                row = rows[path]
                self.assertFalse(row["deployable_to_nl"])
                self.assertEqual(row["local_review_class"], "C")

        text = (ROOT / "mesh-runtime" / "health_check.sh").read_text(encoding="utf-8")
        self.assertIn("systemctl restart x-ui", text)


if __name__ == "__main__":
    unittest.main()
