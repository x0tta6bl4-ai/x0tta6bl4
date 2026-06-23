#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_completion_audit.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_completion_audit",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
completion = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_completion_audit"] = completion
SPEC.loader.exec_module(completion)


NOW = "2026-06-07T03:00:00Z"


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def runbook_summary(*, passed: bool = True) -> dict:
    checks = {name: passed for name in completion.REQUIRED_RUNBOOK_CHECKS}
    commands = [
        {"id": item_id, "command": f"python3 x0vpn_node.py {item_id}"}
        for item_id in completion.REQUIRED_RUNBOOK_COMMAND_IDS
    ]
    if not passed:
        checks["rollback_commands_present"] = False
        commands = [
            row
            for row in commands
            if row["id"] != "rollback_server_service_after_approval"
        ]
    return {
        "ok": passed,
        "approval_phrase_required": completion.APPROVAL_PHRASE,
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "endpoint": {
            "host": "89.125.1.107",
            "port": 40467,
            "transport": "tcp",
        },
        "service_names": {
            "server": completion.SERVER_SERVICE,
            "client": completion.CLIENT_SERVICE,
        },
        "legacy_command_findings": [] if passed else ["xray"],
        "checks": checks,
        "commands": commands,
    }


def server_health(*, passed: bool = True, port: int = 40467) -> dict:
    return {
        "ok": passed,
        "mode": "server-health",
        "port": port,
        "transport": "tcp",
        "service_name": completion.SERVER_SERVICE,
        "os_mutation_performed": False,
        "checks": [{"name": "server_tun_route_nat_dns", "ok": passed, "required": True}],
    }


def client_health(*, passed: bool = True, host: str = "89.125.1.107") -> dict:
    return {
        "ok": passed,
        "mode": "client-health",
        "host": host,
        "port": 40467,
        "service_name": completion.CLIENT_SERVICE,
        "os_mutation_performed": False,
        "checks": [{"name": "client_tun_route_dns", "ok": passed, "required": True}],
    }


def client_doctor(*, passed: bool = True, require_installed_health: bool = True) -> dict:
    return {
        "ok": passed,
        "mode": "client-doctor",
        "host": "89.125.1.107",
        "port": 40467,
        "service_name": completion.CLIENT_SERVICE,
        "require_installed_health": require_installed_health,
        "os_mutation_performed": False,
        "failed_required_checks": [] if passed else ["installed_client_health"],
        "checks": [{"name": "installed_client_health", "ok": passed, "required": True}],
    }


class FirstPartyProductionCompletionAuditTests(unittest.TestCase):
    def test_accepts_runbook_and_post_apply_health_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            runbook_path = write_json(tmp / "runbook.json", runbook_summary())
            server_path = write_json(tmp / "server-health.json", server_health())
            client_path = write_json(tmp / "client-health.json", client_health())
            doctor_path = write_json(tmp / "client-doctor.json", client_doctor())

            payload = completion.build_payload(
                runbook_summary_path=runbook_path,
                server_health_path=server_path,
                client_health_path=client_path,
                client_doctor_path=doctor_path,
                generated_at=NOW,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["completion_decision"], "FIRSTPARTY_VPN_PRODUCTION_COMPLETE")
        self.assertTrue(payload["goal_completion_claim_allowed"])
        self.assertFalse(payload["production_apply_still_required"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["endpoint_matches_runbook"])
        self.assertTrue(payload["checks"]["service_names_match"])

    def test_missing_post_apply_evidence_blocks_completion_but_preserves_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            runbook_path = write_json(tmp / "runbook.json", runbook_summary())

            payload = completion.build_payload(
                runbook_summary_path=runbook_path,
                generated_at=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["completion_decision"], "FIRSTPARTY_VPN_PRODUCTION_NOT_PROVEN")
        self.assertFalse(payload["goal_completion_claim_allowed"])
        self.assertTrue(payload["production_apply_still_required"])
        self.assertIn("completion_evidence_present", payload["failed_checks"])
        self.assertIn("server_health_ok", payload["failed_checks"])
        self.assertIn("client_health_ok", payload["failed_checks"])
        self.assertIn("client_doctor_ok", payload["failed_checks"])
        self.assertIn(
            "server_health_post_apply",
            payload["required_operator_evidence_commands"],
        )
        self.assertIn(
            "rollback_server_service_after_approval",
            payload["rollback_commands"]["server"],
        )
        self.assertFalse(payload["os_mutation_performed"])
        self.assertTrue(payload["no_nl_or_spb_writes_performed"])

    def test_rejects_unhealthy_or_mismatched_post_apply_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            runbook_path = write_json(tmp / "runbook.json", runbook_summary())
            server_path = write_json(tmp / "server-health.json", server_health(port=40468))
            client_path = write_json(tmp / "client-health.json", client_health(host="127.0.0.1"))
            doctor_path = write_json(
                tmp / "client-doctor.json",
                client_doctor(passed=False, require_installed_health=False),
            )

            payload = completion.build_payload(
                runbook_summary_path=runbook_path,
                server_health_path=server_path,
                client_health_path=client_path,
                client_doctor_path=doctor_path,
                generated_at=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("endpoint_matches_runbook", payload["failed_checks"])
        self.assertIn("client_doctor_ok", payload["failed_checks"])
        self.assertIn("client_doctor_requires_installed_health", payload["failed_checks"])


if __name__ == "__main__":
    unittest.main()
