#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_operator_script.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_operator_script",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
operator_script = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_operator_script"] = operator_script
SPEC.loader.exec_module(operator_script)


NOW = "2026-06-07T03:20:00Z"


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


def runbook_summary(*, passed: bool = True, legacy: bool = False) -> dict:
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
    commands = [
        command_row(item_id, phase=phase, command=command, mutation=mutation)
        for item_id, phase, command, mutation in command_specs
    ]
    if legacy:
        commands[7]["command"] = guarded_command("sudo systemctl restart xray")
    if not passed:
        commands = commands[:-1]
    return {
        "ok": passed,
        "approval_phrase_required": operator_script.APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "legacy_command_findings": ["install_server_service_after_approval:xray"] if legacy else [],
        "checks": {
            "runbook_does_not_execute_commands": True,
        },
        "commands": commands,
    }


class FirstPartyProductionOperatorScriptTests(unittest.TestCase):
    def test_build_payload_creates_guarded_dry_run_apply_and_rollback_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            runbook_path = write_json(tmp / "runbook.json", runbook_summary())

            payload = operator_script.build_payload(
                runbook_summary_path=runbook_path,
                generated_at=NOW,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["apply_script_excludes_rollback"])
        self.assertTrue(payload["checks"]["rollback_script_contains_only_rollback"])
        self.assertTrue(payload["checks"]["scripts_default_dry_run"])
        self.assertTrue(payload["checks"]["scripts_require_approval_to_execute"])
        self.assertTrue(payload["checks"]["scripts_hash_bound_to_runbook"])
        self.assertTrue(payload["checks"]["scripts_log_self_hash_meta"])
        self.assertTrue(payload["checks"]["commands_syntax_ok"])
        self.assertNotIn(
            "rollback_client_policy_and_service_after_approval",
            payload["apply_script_text"],
        )
        self.assertIn(
            "rollback_client_policy_and_service_after_approval",
            payload["rollback_script_text"],
        )
        self.assertIn('DRY_RUN="${DRY_RUN:-1}"', payload["apply_script_text"])
        self.assertIn('EXECUTE="${EXECUTE:-0}"', payload["apply_script_text"])
        self.assertIn(operator_script.APPROVAL_PHRASE, payload["apply_script_text"])
        self.assertIn('SCRIPT_ROLE=apply', payload["apply_script_text"])
        self.assertIn('"event":"meta"', payload["apply_script_text"])
        self.assertIn('script_sha256', payload["apply_script_text"])
        self.assertIn('runbook_sha256', payload["apply_script_text"])

    def test_write_packet_writes_private_executable_hash_bound_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            runbook_path = write_json(tmp / "runbook.json", runbook_summary())
            payload = operator_script.build_payload(
                runbook_summary_path=runbook_path,
                generated_at=NOW,
            )

            out_dir = operator_script.write_packet(payload, diagnostics_dir=tmp)
            summary = json.loads((out_dir / "summary.json").read_text())
            apply_script_exists = Path(summary["script_paths"]["apply"]).is_file()
            rollback_script_exists = Path(summary["script_paths"]["rollback"]).is_file()

            self.assertTrue(summary["ok"])
            self.assertTrue(
                operator_script.mode_executable_not_group_world_writable(
                    summary["script_file_modes"]["apply"]
                )
            )
            self.assertTrue(
                operator_script.mode_executable_not_group_world_writable(
                    summary["script_file_modes"]["rollback"]
                )
            )
            self.assertTrue(
                summary["checks"][
                    "script_files_written_executable_not_group_world_writable"
                ]
            )
            self.assertTrue(summary["checks"]["script_file_hashes_match_preview"])
            self.assertTrue(apply_script_exists)
            self.assertTrue(rollback_script_exists)

    def test_rejects_missing_rollback_or_legacy_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            missing_runbook_path = write_json(tmp / "missing.json", runbook_summary(passed=False))
            legacy_runbook_path = write_json(tmp / "legacy.json", runbook_summary(legacy=True))

            missing_payload = operator_script.build_payload(
                runbook_summary_path=missing_runbook_path,
                generated_at=NOW,
            )
            legacy_payload = operator_script.build_payload(
                runbook_summary_path=legacy_runbook_path,
                generated_at=NOW,
            )

        self.assertFalse(missing_payload["ok"])
        self.assertIn("required_rollback_commands_present", missing_payload["failed_checks"])
        self.assertFalse(legacy_payload["ok"])
        self.assertIn("no_legacy_commands", legacy_payload["failed_checks"])
        self.assertIn("install_server_service_after_approval:xray", legacy_payload["legacy_command_findings"])


if __name__ == "__main__":
    unittest.main()
