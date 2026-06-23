#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_apply_transcript_audit.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_apply_transcript_audit",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_apply_transcript_audit"] = audit
SPEC.loader.exec_module(audit)


NOW = "2026-06-07T04:00:00Z"


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_jsonl(path: Path, rows: list[dict]) -> Path:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return path


def script(path: Path, text: str = "#!/usr/bin/env bash\ntrue\n") -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def operator_summary(tmp: Path) -> tuple[Path, dict]:
    apply_script = script(tmp / "apply.sh")
    rollback_script = script(tmp / "rollback.sh")
    payload = {
        "ok": True,
        "approval_phrase_required": audit.APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "runbook_summary_sha256": "a" * 64,
        "transcript_dir": str(tmp / "transcripts"),
        "script_paths": {
            "apply": str(apply_script),
            "rollback": str(rollback_script),
        },
        "script_file_hashes": {
            "apply_script_sha256": audit.file_sha256(apply_script),
            "rollback_script_sha256": audit.file_sha256(rollback_script),
        },
        "apply_command_ids": sorted(audit.FALLBACK_APPLY_COMMAND_IDS),
        "rollback_command_ids": sorted(audit.FALLBACK_ROLLBACK_COMMAND_IDS),
    }
    return write_json(tmp / "operator-summary.json", payload), payload


def transcript_rows(
    *,
    summary: dict | None = None,
    bad_meta: bool = False,
    include_dry_run: bool = False,
    include_rollback: bool = False,
    fail_one: bool = False,
) -> list[dict]:
    rows: list[dict] = []
    if summary is not None:
        hashes = summary.get("script_file_hashes") if isinstance(summary.get("script_file_hashes"), dict) else {}
        rows.append(
            {
                "ts": NOW,
                "event": "meta",
                "script_role": "rollback" if bad_meta else "apply",
                "execute": False if bad_meta else True,
                "dry_run": True if bad_meta else False,
                "approval_ok": False if bad_meta else True,
                "runbook_sha256": "bad" if bad_meta else summary.get("runbook_summary_sha256"),
                "script_sha256": "bad" if bad_meta else hashes.get("apply_script_sha256"),
            }
        )
    for item_id in sorted(audit.FALLBACK_APPLY_COMMAND_IDS):
        rows.append({"ts": NOW, "event": "start", "step_id": item_id, "rc": 0})
        if include_dry_run and item_id == "server_health_post_apply":
            rows.append({"ts": NOW, "event": "dry_run", "step_id": item_id, "rc": 0})
        rc = 2 if fail_one and item_id == "client_doctor_post_apply" else 0
        rows.append({"ts": NOW, "event": "finish", "step_id": item_id, "rc": rc})
    if include_rollback:
        rows.append(
            {
                "ts": NOW,
                "event": "start",
                "step_id": "rollback_server_service_after_approval",
                "rc": 0,
            }
        )
    return rows


class FirstPartyProductionApplyTranscriptAuditTests(unittest.TestCase):
    def test_accepts_complete_apply_execution_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            summary_path, summary = operator_summary(tmp)
            transcript = write_jsonl(
                tmp / "apply-execution.jsonl",
                transcript_rows(summary=summary),
            )

            payload = audit.build_payload(
                operator_summary_path=summary_path,
                apply_transcript_path=transcript,
                generated_at=NOW,
            )

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["apply_execution_proven"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["apply_transcript_all_expected_starts_present"])
        self.assertTrue(payload["checks"]["apply_transcript_all_expected_finishes_rc0"])
        self.assertTrue(payload["checks"]["apply_transcript_no_dry_run_events"])
        self.assertTrue(payload["checks"]["apply_transcript_excludes_rollback_steps"])
        self.assertTrue(payload["checks"]["apply_transcript_has_only_expected_apply_steps"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_present"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_role_apply"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_execute_enabled"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_dry_run_disabled"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_approval_ok"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_runbook_hash_matches"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_script_hash_matches"])

    def test_rejects_dryrun_rollback_or_failed_finish_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            summary_path, summary = operator_summary(tmp)
            transcript = write_jsonl(
                tmp / "bad-apply-execution.jsonl",
                transcript_rows(
                    summary=summary,
                    bad_meta=True,
                    include_dry_run=True,
                    include_rollback=True,
                    fail_one=True,
                ),
            )

            payload = audit.build_payload(
                operator_summary_path=summary_path,
                apply_transcript_path=transcript,
                generated_at=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("apply_transcript_all_expected_finishes_rc0", payload["failed_checks"])
        self.assertIn("apply_transcript_no_dry_run_events", payload["failed_checks"])
        self.assertIn("apply_transcript_excludes_rollback_steps", payload["failed_checks"])
        self.assertIn("apply_transcript_has_only_expected_apply_steps", payload["failed_checks"])
        self.assertIn("apply_transcript_meta_role_apply", payload["failed_checks"])
        self.assertIn("apply_transcript_meta_execute_enabled", payload["failed_checks"])
        self.assertIn("apply_transcript_meta_dry_run_disabled", payload["failed_checks"])
        self.assertIn("apply_transcript_meta_approval_ok", payload["failed_checks"])
        self.assertIn("apply_transcript_meta_runbook_hash_matches", payload["failed_checks"])
        self.assertIn("apply_transcript_meta_script_hash_matches", payload["failed_checks"])
        self.assertIn("client_doctor_post_apply:rc=2", payload["failed_finish_rows"])

    def test_rejects_missing_transcript_and_tampered_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            summary_path, summary = operator_summary(tmp)
            Path(summary["script_paths"]["apply"]).write_text(
                "#!/usr/bin/env bash\nfalse\n",
                encoding="utf-8",
            )

            payload = audit.build_payload(
                operator_summary_path=summary_path,
                generated_at=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("apply_script_hash_matches_summary", payload["failed_checks"])
        self.assertIn("apply_transcript_present", payload["failed_checks"])
        self.assertIn("apply_transcript_nonempty", payload["failed_checks"])

    def test_write_packet_records_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            summary_path, summary = operator_summary(tmp)
            transcript = write_jsonl(
                tmp / "apply-execution.jsonl",
                transcript_rows(summary=summary),
            )
            payload = audit.build_payload(
                operator_summary_path=summary_path,
                apply_transcript_path=transcript,
                generated_at=NOW,
            )

            out_dir = audit.write_packet(payload, diagnostics_dir=tmp)
            summary = json.loads((out_dir / "summary.json").read_text())
            markdown_exists = (out_dir / "summary.md").is_file()

            self.assertTrue(summary["ok"])
            self.assertTrue(markdown_exists)


if __name__ == "__main__":
    unittest.main()
