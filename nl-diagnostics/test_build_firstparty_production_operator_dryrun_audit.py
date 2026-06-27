#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


OPERATOR_MODULE_PATH = Path(__file__).with_name("build_firstparty_production_operator_script.py")
OPERATOR_SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_operator_script_for_dryrun_tests",
    OPERATOR_MODULE_PATH,
)
assert OPERATOR_SPEC and OPERATOR_SPEC.loader
operator_script = importlib.util.module_from_spec(OPERATOR_SPEC)
sys.modules["build_firstparty_production_operator_script_for_dryrun_tests"] = operator_script
OPERATOR_SPEC.loader.exec_module(operator_script)

MODULE_PATH = Path(__file__).with_name("build_firstparty_production_operator_dryrun_audit.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_operator_dryrun_audit",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
dryrun = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_operator_dryrun_audit"] = dryrun
SPEC.loader.exec_module(dryrun)


NOW = "2026-06-07T03:40:00Z"


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def guarded_command(command: str) -> str:
    return (
        'APPROVAL="${APPROVAL:-}"; test "$APPROVAL" = '
        f"{operator_script.APPROVAL_PHRASE} && {command}"
    )


def command_row(
    item_id: str,
    *,
    phase: str,
    command: str,
    mutation: bool = False,
) -> dict:
    return {
        "id": item_id,
        "phase": phase,
        "run_on": "operator-workstation",
        "mutation": mutation,
        "approval_required": mutation,
        "command": guarded_command(command) if mutation else command,
    }


def runbook_summary() -> dict:
    command_specs = [
        ("verify_authorization_summary_hash", "local-precheck", "test 1 = 1", False),
        ("verify_apply_packet_hash", "local-precheck", "test 1 = 1", False),
        ("verify_handoff_summary_hash", "local-precheck", "test 1 = 1", False),
        ("verify_handoff_archive_hash_and_mode", "local-precheck", "test 1 = 1", False),
        ("verify_handoff_manifest_hash_and_mode", "local-precheck", "test 1 = 1", False),
        ("verify_nl_port_still_free_readonly", "remote-readonly-precheck", "ssh nl true", False),
        ("copy_handoff_to_nl_after_approval", "guarded-copy", "rsync handoff nl:/tmp/handoff", True),
        ("install_server_service_after_approval", "server-apply", "sudo python3 x0vpn_node.py install-server-service --allow-os-mutation", True),
        ("server_health_post_apply", "post-apply-validation", "echo server | tee server-health.json", False),
        ("apply_client_config_after_approval", "client-apply", "sudo python3 x0vpn_node.py install-client-service --allow-os-mutation", True),
        ("client_health_post_apply", "post-apply-validation", "echo client | tee client-health.json", False),
        ("client_doctor_post_apply", "post-apply-validation", "echo doctor | tee client-doctor.json", False),
        ("build_completion_audit_after_post_apply", "post-apply-validation", "python3 nl-diagnostics/build_firstparty_production_completion_audit.py --write --json", False),
        ("rollback_client_policy_and_service_after_approval", "rollback", "sudo python3 x0vpn_node.py client-policy-rollback --allow-os-mutation", True),
        ("rollback_server_service_after_approval", "rollback", "sudo python3 x0vpn_node.py uninstall-server-service --allow-os-mutation", True),
    ]
    return {
        "ok": True,
        "approval_phrase_required": operator_script.APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "legacy_command_findings": [],
        "checks": {
            "runbook_does_not_execute_commands": True,
        },
        "commands": [
            command_row(item_id, phase=phase, command=command, mutation=mutation)
            for item_id, phase, command, mutation in command_specs
        ],
    }


def build_operator_summary(tmp: Path) -> Path:
    runbook_path = write_json(tmp / "runbook.json", runbook_summary())
    payload = operator_script.build_payload(
        runbook_summary_path=runbook_path,
        generated_at=NOW,
    )
    out_dir = operator_script.write_packet(payload, diagnostics_dir=tmp)
    return out_dir / "summary.json"


class FirstPartyProductionOperatorDryRunAuditTests(unittest.TestCase):
    def test_build_payload_runs_apply_and_rollback_in_dryrun_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            operator_summary = build_operator_summary(tmp)

            payload = dryrun.build_payload(
                operator_summary_path=operator_summary,
                evidence_dir=tmp / "dryrun-audit",
                generated_at=NOW,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["apply_dryrun_exit_zero"])
        self.assertTrue(payload["checks"]["rollback_dryrun_exit_zero"])
        self.assertTrue(payload["checks"]["apply_transcript_complete"])
        self.assertTrue(payload["checks"]["rollback_transcript_complete"])
        self.assertTrue(payload["checks"]["apply_transcript_excludes_rollback"])
        self.assertTrue(payload["checks"]["rollback_transcript_contains_only_rollback"])
        self.assertTrue(payload["checks"]["dryrun_transcripts_have_no_finish_events"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_present"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_present"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_role_apply"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_role_rollback"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_execute_disabled"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_execute_disabled"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_dry_run_enabled"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_dry_run_enabled"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_approval_not_ok"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_approval_not_ok"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_runbook_hash_matches"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_runbook_hash_matches"])
        self.assertTrue(payload["checks"]["apply_transcript_meta_script_hash_matches"])
        self.assertTrue(payload["checks"]["rollback_transcript_meta_script_hash_matches"])
        self.assertTrue(payload["checks"]["guard_blocks_execute_without_dryrun_pair"])
        self.assertTrue(payload["checks"]["guard_blocks_wrong_approval"])
        self.assertTrue(payload["checks"]["guard_checks_do_not_start_steps"])
        self.assertEqual(payload["transcript_meta"]["apply"]["script_role"], "apply")
        self.assertEqual(payload["transcript_meta"]["rollback"]["script_role"], "rollback")
        self.assertEqual(payload["dryrun_results"]["apply"]["exit_code"], 0)
        self.assertEqual(payload["dryrun_results"]["rollback"]["exit_code"], 0)
        self.assertEqual(
            payload["guard_results"]["execute_without_dryrun_pair"]["exit_code"],
            41,
        )
        self.assertEqual(payload["guard_results"]["wrong_approval"]["exit_code"], 42)
        self.assertNotIn(
            "rollback_client_policy_and_service_after_approval",
            payload["apply_transcript_start_ids"],
        )

    def test_rejects_tampered_script_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            operator_summary = build_operator_summary(tmp)
            summary = json.loads(operator_summary.read_text())
            Path(summary["script_paths"]["apply"]).write_text(
                Path(summary["script_paths"]["apply"]).read_text() + "\n# tampered\n",
                encoding="utf-8",
            )

            payload = dryrun.build_payload(
                operator_summary_path=operator_summary,
                evidence_dir=tmp / "dryrun-audit",
                generated_at=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("script_hashes_match_summary", payload["failed_checks"])

    def test_write_packet_records_summary_and_transcripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            operator_summary = build_operator_summary(tmp)
            evidence_dir = tmp / "firstparty-production-operator-dryrun-audit-test"
            payload = dryrun.build_payload(
                operator_summary_path=operator_summary,
                evidence_dir=evidence_dir,
                generated_at=NOW,
            )
            payload["evidence_dir"] = str(evidence_dir)

            out_dir = dryrun.write_packet(payload, diagnostics_dir=tmp)
            summary = json.loads((out_dir / "summary.json").read_text())

            self.assertTrue(summary["ok"])
            self.assertTrue((out_dir / "summary.md").is_file())
            self.assertTrue(Path(summary["transcript_paths"]["apply"]).is_file())
            self.assertTrue(Path(summary["transcript_paths"]["rollback"]).is_file())


if __name__ == "__main__":
    unittest.main()
