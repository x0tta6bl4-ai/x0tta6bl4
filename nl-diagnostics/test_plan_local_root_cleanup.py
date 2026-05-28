#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("plan_local_root_cleanup.py")
SPEC = importlib.util.spec_from_file_location("plan_local_root_cleanup", MODULE_PATH)
assert SPEC and SPEC.loader
cleanup = importlib.util.module_from_spec(SPEC)
sys.modules["plan_local_root_cleanup"] = cleanup
SPEC.loader.exec_module(cleanup)

GIB = 1024**3


def local_env(root_status: str = "critical_full", root_free_gib: float = 0.0) -> dict:
    return {
        "summary": {
            "root_status": root_status,
            "root_free_gib": root_free_gib,
        }
    }


def candidates() -> list[dict]:
    return [
        cleanup.cleanup_candidate(
            candidate_id="BIG-01",
            path="/tmp/big",
            title="big candidate",
            risk="medium_manual_review",
            action="manual_review_before_delete",
            command_preview="sudo rm -rf /tmp/big",
            approval="manual",
        ),
        cleanup.cleanup_candidate(
            candidate_id="SMALL-01",
            path="/tmp/small",
            title="small candidate",
            risk="low_standard_cache",
            action="command_requires_approval",
            command_preview="sudo true",
            approval="manual",
        ),
    ]


def size_provider(rows: dict[str, tuple[bool, int]]):
    def fake(path: Path) -> dict:
        exists, size = rows[str(path)]
        return {
            "exists": exists,
            "is_dir": exists,
            "size_bytes": size,
            "size_gib": cleanup.bytes_to_gib(size),
            "error_count": 0,
            "errors": [],
        }

    return fake


class LocalRootCleanupPlanTests(unittest.TestCase):
    def test_full_root_with_enough_candidates_is_manual_plan_ready(self):
        payload = cleanup.build_payload(
            local_env(),
            candidate_provider=candidates,
            size_provider=size_provider(
                {
                    "/tmp/big": (True, 3 * GIB),
                    "/tmp/small": (True, 1 * GIB),
                }
            ),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "manual_cleanup_plan_ready")
        self.assertEqual(payload["summary"]["estimated_reclaim_gib"], 4.0)
        self.assertEqual(payload["summary"]["top_candidate_id"], "BIG-01")
        self.assertEqual(payload["review_order"], ["BIG-01", "SMALL-01"])
        self.assertFalse(payload["cleanup_execute_allowed"])
        self.assertFalse(payload["nl_mutation_allowed"])
        self.assertFalse(payload["spb_fallback_allowed"])

    def test_low_reclaim_is_reported_without_blocking_plan_generation(self):
        payload = cleanup.build_payload(
            local_env(),
            candidate_provider=candidates,
            size_provider=size_provider(
                {
                    "/tmp/big": (True, int(0.5 * GIB)),
                    "/tmp/small": (False, 0),
                }
            ),
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], "manual_cleanup_plan_low_reclaim")
        self.assertEqual(payload["summary"]["existing_candidate_count"], 1)

    def test_clean_root_needs_no_cleanup(self):
        payload = cleanup.build_payload(
            local_env("ok", 10.0),
            candidate_provider=candidates,
            size_provider=size_provider(
                {
                    "/tmp/big": (True, 3 * GIB),
                    "/tmp/small": (True, 1 * GIB),
                }
            ),
        )

        self.assertEqual(payload["status"], "no_cleanup_needed")

    def test_missing_local_environment_is_not_ok(self):
        payload = cleanup.build_payload(
            {"summary": {}},
            candidate_provider=candidates,
            size_provider=size_provider(
                {
                    "/tmp/big": (False, 0),
                    "/tmp/small": (False, 0),
                }
            ),
        )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "missing_local_environment")

    def test_markdown_contains_command_previews_and_no_execution_notice(self):
        payload = cleanup.build_payload(
            local_env(),
            candidate_provider=candidates,
            size_provider=size_provider(
                {
                    "/tmp/big": (True, 3 * GIB),
                    "/tmp/small": (True, 1 * GIB),
                }
            ),
        )

        markdown = cleanup.render_markdown(payload)

        self.assertIn("sudo rm -rf /tmp/big", markdown)
        self.assertIn("cleanup_execute_allowed=false", markdown)
        self.assertIn("No cleanup, NL writes, or SPB fallback", markdown)


if __name__ == "__main__":
    unittest.main()
