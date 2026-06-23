#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("build_firstparty_secure_material_handoff.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_secure_material_handoff",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
handoff = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_secure_material_handoff"] = handoff
SPEC.loader.exec_module(handoff)


def sample_apply_packet(*, passed: bool = True) -> dict:
    return {
        "ok": passed,
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "secure_material_handoff_required": True,
        "host": "89.125.1.107" if passed else "127.0.0.1",
        "bind_host": "0.0.0.0" if passed else "127.0.0.1",
        "port": 40467,
        "transport": "tcp",
        "server_candidate_hash": "a" * 64,
        "client_candidate_hash": "b" * 64,
    }


def sample_material(*, passed: bool = True) -> dict:
    apply_server = {
        "ok": passed,
        "dry_run": True,
        "file_mutation_performed": False,
        "os_mutation_performed": False,
        "service_restart_performed": False,
        "rollback_on_failure": True,
        "rollback_performed": False,
    }
    return {
        "generate_ok": passed,
        "server_service_plan_ok": passed,
        "client_service_plan_ok": passed,
        "server_apply_dry_run": apply_server,
        "client_apply_dry_run": dict(apply_server),
        "export_client_kits_ok": passed,
        "verify_client_kits_ok": passed,
        "deployment_epoch": "production-firstparty-handoff-test",
        "server_bind_host": "0.0.0.0",
        "client_host": "89.125.1.107",
        "port": 40467,
        "transport": "tcp",
        "server_candidate_hash": "a" * 64,
        "client_candidate_hash": "b" * 64,
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "client_kit_count": 2,
        "verified_kit_count": 2 if passed else 1,
        "server_secrets_included": False,
        "source_tree_included": passed,
        "source_tree_hash": "c" * 64,
        "current_source_tree_hash": "c" * 64,
        "legacy_protocol_findings": [] if passed else ["value0:xray"],
        "manifest_secret_free": passed,
        "manifest_path": "/home/user/.local/share/x0tta-firstparty-vpn/handoff/MANIFEST.secret-free.json",
        "manifest_sha256": "d" * 64,
        "handoff_dir": "/home/user/.local/share/x0tta-firstparty-vpn/handoff",
        "handoff_dir_outside_repo": passed,
        "handoff_dir_mode": "0700" if passed else "0755",
        "handoff_file_count": 20,
        "archive_path": "/home/user/.local/share/x0tta-firstparty-vpn/handoff.tar.gz",
        "archive_outside_repo": passed,
        "archive_mode": "0600" if passed else "0644",
        "archive_sha256": "e" * 64,
        "private_files_mode_ok": passed,
    }


class FirstPartySecureMaterialHandoffTests(unittest.TestCase):
    def test_build_payload_accepts_private_handoff_outside_repo(self):
        with tempfile.TemporaryDirectory() as tmp_raw:
            apply_path = Path(tmp_raw) / "apply.json"
            apply_path.write_text(json.dumps(sample_apply_packet()), encoding="utf-8")
            with patch.object(
                handoff,
                "_build_handoff_material",
                return_value=sample_material(),
            ):
                payload = handoff.build_payload(
                    apply_packet_summary_path=apply_path,
                    handoff_root=Path("/home/user/.local/share/x0tta-firstparty-vpn/handoffs"),
                )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertFalse(payload["production_mutation_allowed"])
        self.assertFalse(payload["raw_secret_material_stored_in_evidence"])
        self.assertFalse(payload["repo_material_persisted"])
        self.assertEqual(payload["handoff_dir_mode"], "0700")
        self.assertEqual(payload["handoff_archive_mode"], "0600")
        self.assertTrue(payload["checks"]["server_apply_dry_run_ok"])
        self.assertTrue(payload["checks"]["manifest_secret_free"])
        self.assertTrue(payload["checks"]["generated_client_host_matches_apply_packet"])
        self.assertTrue(payload["checks"]["generated_transport_matches_apply_packet"])

    def test_build_payload_rejects_unsafe_handoff_or_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp_raw:
            apply_path = Path(tmp_raw) / "apply.json"
            apply_path.write_text(
                json.dumps(sample_apply_packet(passed=False)),
                encoding="utf-8",
            )
            with patch.object(
                handoff,
                "_build_handoff_material",
                return_value=sample_material(passed=False),
            ):
                payload = handoff.build_payload(
                    apply_packet_summary_path=apply_path,
                    handoff_root=Path("/home/user/.local/share/x0tta-firstparty-vpn/handoffs"),
                )

        self.assertFalse(payload["ok"])
        self.assertIn("apply_packet_ok", payload["failed_checks"])
        self.assertIn("apply_packet_external_endpoint", payload["failed_checks"])
        self.assertIn("handoff_dir_private", payload["failed_checks"])
        self.assertIn("handoff_archive_private", payload["failed_checks"])
        self.assertIn("private_files_mode_ok", payload["failed_checks"])
        self.assertIn("legacy_protocol_markers_absent", payload["failed_checks"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
