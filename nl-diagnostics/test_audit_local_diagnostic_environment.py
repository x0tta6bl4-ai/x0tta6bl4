#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from collections import namedtuple
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("audit_local_diagnostic_environment.py")
SPEC = importlib.util.spec_from_file_location("audit_local_diagnostic_environment", MODULE_PATH)
assert SPEC and SPEC.loader
localenv = importlib.util.module_from_spec(SPEC)
sys.modules["audit_local_diagnostic_environment"] = localenv
SPEC.loader.exec_module(localenv)

Usage = namedtuple("Usage", ["total", "used", "free"])
GIB = 1024**3


def usage_provider(rows: dict[str, Usage]):
    def fake(path: Path):
        return rows[str(path)]

    return fake


def writable_tmpdir(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": True,
        "is_dir": True,
        "writable": True,
        "error": "",
    }


def missing_tmpdir(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": False,
        "is_dir": False,
        "writable": False,
        "error": "tmpdir_missing",
    }


def cleanup_candidates() -> list[dict]:
    return [
        {
            "path": "/tmp/antigravity_restore",
            "exists": True,
            "action": "manual_review_before_delete",
        },
        {
            "path": "/tmp/antigravity_restore_correct",
            "exists": False,
            "action": "manual_review_before_delete",
        },
    ]


class LocalDiagnosticEnvironmentAuditTests(unittest.TestCase):
    def test_full_root_is_watch_when_project_tmpdir_is_writable(self):
        payload = localenv.build_payload(
            usage_provider=usage_provider(
                {
                    "/": Usage(100 * GIB, 100 * GIB, 0),
                    "/tmp": Usage(100 * GIB, 100 * GIB, 0),
                    "/mnt/projects": Usage(466 * GIB, 405 * GIB, 61 * GIB),
                }
            ),
            tmpdir_probe_provider=writable_tmpdir,
            cleanup_provider=cleanup_candidates,
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "watch_root_full_tmpdir_available")
        self.assertEqual(payload["summary"]["root_status"], "critical_full")
        self.assertTrue(payload["summary"]["diagnostic_tmpdir_writable"])
        self.assertTrue(payload["summary"]["cleanup_required"])
        self.assertEqual(payload["summary"]["cleanup_candidate_count"], 1)
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_missing_project_tmpdir_blocks_local_diagnostics(self):
        payload = localenv.build_payload(
            usage_provider=usage_provider(
                {
                    "/": Usage(100 * GIB, 80 * GIB, 20 * GIB),
                    "/tmp": Usage(100 * GIB, 80 * GIB, 20 * GIB),
                    "/mnt/projects": Usage(466 * GIB, 405 * GIB, 61 * GIB),
                }
            ),
            tmpdir_probe_provider=missing_tmpdir,
            cleanup_provider=lambda: [],
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "missing_writable_temp")
        self.assertFalse(payload["summary"]["diagnostic_tmpdir_writable"])

    def test_clean_disk_and_writable_tmpdir_are_ok(self):
        payload = localenv.build_payload(
            usage_provider=usage_provider(
                {
                    "/": Usage(100 * GIB, 50 * GIB, 50 * GIB),
                    "/tmp": Usage(100 * GIB, 50 * GIB, 50 * GIB),
                    "/mnt/projects": Usage(466 * GIB, 100 * GIB, 366 * GIB),
                }
            ),
            tmpdir_probe_provider=writable_tmpdir,
            cleanup_provider=lambda: [],
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["summary"]["cleanup_required"])

    def test_markdown_renders_tmpdir_and_no_write_notice(self):
        payload = localenv.build_payload(
            usage_provider=usage_provider(
                {
                    "/": Usage(100 * GIB, 100 * GIB, 0),
                    "/tmp": Usage(100 * GIB, 100 * GIB, 0),
                    "/mnt/projects": Usage(466 * GIB, 405 * GIB, 61 * GIB),
                }
            ),
            tmpdir_probe_provider=writable_tmpdir,
            cleanup_provider=cleanup_candidates,
        )

        markdown = localenv.render_markdown(payload)

        self.assertIn("TMPDIR=/mnt/projects/.tmp", markdown)
        self.assertIn("manual_review_before_delete", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
