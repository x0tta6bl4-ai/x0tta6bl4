#!/usr/bin/env python3
"""Unit tests for analyze_nl_profile_gaps.py.

These tests use temporary local profiles only. They do not access NL.
"""

from __future__ import annotations

from collections import defaultdict
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("analyze_nl_profile_gaps.py")
SPEC = importlib.util.spec_from_file_location("analyze_nl_profile_gaps", MODULE_PATH)
assert SPEC and SPEC.loader
analyzer = importlib.util.module_from_spec(SPEC)
sys.modules["analyze_nl_profile_gaps"] = analyzer
SPEC.loader.exec_module(analyzer)


class AnalyzeNlProfileGapsTests(unittest.TestCase):
    def test_sensitive_remote_with_redacted_meta_is_not_plain_missing(self) -> None:
        raw_sha256 = "a" * 64
        remote_path = "/opt/ghost-access-bot/current/telegram_bot_simple.py"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            redacted_dir = root / "services/nl-server/redacted/ghost-access"
            redacted_dir.mkdir(parents=True)
            redacted_file = redacted_dir / "telegram_bot_simple.redacted.py"
            redacted_file.write_text("# REDACTED REVIEW COPY - NOT DEPLOYABLE\n", encoding="utf-8")
            (redacted_dir / "telegram_bot_simple.redacted.py.meta.json").write_text(
                json.dumps(
                    {
                        "remote_path": remote_path,
                        "target_path": "redacted/ghost-access/telegram_bot_simple.redacted.py",
                        "raw_sha256": raw_sha256,
                        "redacted_sha256": "b" * 64,
                        "deployable": False,
                        "raw_saved_locally": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            artifact = analyzer.RemoteArtifact("ghost-access", raw_sha256, remote_path)
            rows = [
                analyzer.classify_artifact(
                    artifact=artifact,
                    root=root,
                    by_name=defaultdict(list),
                    local_hash_cache={},
                    redacted_reviews=analyzer.load_redacted_reviews(root),
                    redacted_templates=analyzer.load_redacted_templates(root),
                    accepted_local_deltas=analyzer.load_accepted_local_deltas(root),
                )
            ]

        self.assertEqual(rows[0]["status"], "redacted_review_only")
        self.assertEqual(
            rows[0]["local_matches"],
            ["services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py"],
        )
        self.assertIn("not deployable", rows[0]["notes"])

    def test_sensitive_remote_with_redacted_template_meta_is_not_plain_missing(self) -> None:
        raw_sha256 = "c" * 64
        remote_path = "/etc/ghost-access/nl-beta-2443.json"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template_dir = root / "services/nl-server/templates"
            template_dir.mkdir(parents=True)
            template_file = template_dir / "nl-beta-2443.example.json"
            template_file.write_text('{"production_values_saved": false}\n', encoding="utf-8")
            (template_dir / "nl-beta-2443.example.json.meta.json").write_text(
                json.dumps(
                    {
                        "remote_path": remote_path,
                        "target_path": "templates/nl-beta-2443.example.json",
                        "raw_sha256": raw_sha256,
                        "redacted_sha256": "d" * 64,
                        "deployable_to_nl": False,
                        "raw_saved_locally": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            artifact = analyzer.RemoteArtifact("ghost-vpn", raw_sha256, remote_path)
            rows = [
                analyzer.classify_artifact(
                    artifact=artifact,
                    root=root,
                    by_name=defaultdict(list),
                    local_hash_cache={},
                    redacted_reviews=analyzer.load_redacted_reviews(root),
                    redacted_templates=analyzer.load_redacted_templates(root),
                    accepted_local_deltas=analyzer.load_accepted_local_deltas(root),
                )
            ]

        self.assertEqual(rows[0]["status"], "redacted_template_only")
        self.assertEqual(
            rows[0]["local_matches"],
            ["services/nl-server/templates/nl-beta-2443.example.json"],
        )
        self.assertIn("production values are not stored", rows[0]["notes"])

    def test_manifest_accepted_local_delta_is_not_plain_drift(self) -> None:
        remote_sha256 = "e" * 64
        local_sha256 = "f" * 64
        remote_path = "/opt/x0tta6bl4-mesh/scripts/vps_build_runtime_state.py"
        local_path = "services/nl-server/mesh-runtime/vps_build_runtime_state.py"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_file = root / local_path
            local_file.parent.mkdir(parents=True)
            local_file.write_text("# local delta\n", encoding="utf-8")
            manifest_path = root / "services/nl-server/manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "accepted_local_deltas": [
                            {
                                "remote_path": remote_path,
                                "local_path": local_path,
                                "remote_sha256": remote_sha256,
                                "local_sha256": local_sha256,
                                "deployable_to_nl": False,
                                "reason": "local policy fix",
                            }
                        ]
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            artifact = analyzer.RemoteArtifact("mesh", remote_sha256, remote_path)
            rows = [
                analyzer.classify_artifact(
                    artifact=artifact,
                    root=root,
                    by_name=defaultdict(list, {"vps_build_runtime_state.py": [local_file]}),
                    local_hash_cache={local_file.resolve(): local_sha256},
                    redacted_reviews=analyzer.load_redacted_reviews(root),
                    redacted_templates=analyzer.load_redacted_templates(root),
                    accepted_local_deltas=analyzer.load_accepted_local_deltas(root),
                )
            ]

        self.assertEqual(rows[0]["status"], "accepted_local_delta")
        self.assertEqual(rows[0]["local_matches"], [local_path])
        self.assertIn("local policy fix", rows[0]["notes"])


if __name__ == "__main__":
    unittest.main()
