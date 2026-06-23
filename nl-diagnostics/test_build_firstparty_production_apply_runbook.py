#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_apply_runbook.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_apply_runbook",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
runbook = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_apply_runbook"] = runbook
SPEC.loader.exec_module(runbook)


NOW = "2026-06-07T01:30:00Z"


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def guarded_summary() -> dict:
    return {
        "generated_at": NOW,
        "ok": True,
        "host": "89.125.1.107",
        "bind_host": "0.0.0.0",
        "port": 40467,
        "transport": "tcp",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
    }


def apply_packet() -> dict:
    payload = guarded_summary()
    payload.update(
        {
            "mode": "firstparty-production-apply-packet-summary",
            "post_apply_validation_required": True,
            "secure_material_handoff_required": True,
            "server_service_name": "x0tta-firstparty-vpn.service",
            "client_service_name": "x0tta-firstparty-vpn-client.service",
            "server_config_target": "/etc/x0tta-firstparty-vpn-server/server.json",
            "client_config_target": "/etc/x0tta-firstparty-vpn-client/client.json",
            "deployment_epoch": "production-firstparty-apply-test",
        }
    )
    return payload


def handoff_summary(
    handoff_dir: Path,
    archive: Path,
    manifest: Path,
) -> dict:
    payload = guarded_summary()
    payload.update(
        {
            "mode": "firstparty-secure-material-handoff-summary",
            "handoff_dir": str(handoff_dir),
            "handoff_archive": str(archive),
            "handoff_manifest": str(manifest),
            "archive_sha256": sha(archive),
            "manifest_sha256": sha(manifest),
            "deployment_epoch": "production-firstparty-handoff-test",
            "server_service_name": "x0tta-firstparty-vpn.service",
            "client_service_name": "x0tta-firstparty-vpn-client.service",
        }
    )
    return payload


def authorization(
    *,
    apply_path: Path,
    handoff_path: Path,
    archive: Path,
    manifest: Path,
    handoff_dir: Path,
    bad_archive_hash: bool = False,
) -> dict:
    payload = guarded_summary()
    payload.update(
        {
            "mode": "firstparty-production-authorization-summary",
            "endpoint": {
                "host": "89.125.1.107",
                "bind_host": "0.0.0.0",
                "port": 40467,
                "transport": "tcp",
            },
            "evidence_paths": {
                "apply_packet_summary_path": str(apply_path),
                "handoff_summary_path": str(handoff_path),
                "handoff_dir": str(handoff_dir),
                "handoff_archive": str(archive),
                "handoff_manifest": str(manifest),
            },
            "evidence_hashes": {
                "apply_packet_summary_sha256": sha(apply_path),
                "handoff_summary_sha256": sha(handoff_path),
                "handoff_archive_sha256": "0" * 64 if bad_archive_hash else sha(archive),
                "handoff_manifest_sha256": sha(manifest),
            },
            "checks": {
                "all_evidence_fresh": True,
            },
        }
    )
    return payload


def make_material(tmp: Path) -> tuple[Path, Path, Path]:
    handoff_dir = tmp / "handoff"
    handoff_dir.mkdir()
    os.chmod(handoff_dir, 0o700)
    archive = tmp / "handoff.tar.gz"
    archive.write_bytes(b"private archive placeholder")
    os.chmod(archive, 0o600)
    manifest = handoff_dir / "MANIFEST.secret-free.json"
    manifest.write_text(
        json.dumps(
            {
                "secret_free": True,
                "server_service_name": "x0tta-firstparty-vpn.service",
                "client_service_name": "x0tta-firstparty-vpn-client.service",
                "server_config_target": "/etc/x0tta-firstparty-vpn-server/server.json",
                "client_config_target": "/etc/x0tta-firstparty-vpn-client/client.json",
            }
        ),
        encoding="utf-8",
    )
    os.chmod(manifest, 0o600)
    return handoff_dir, archive, manifest


class FirstPartyProductionApplyRunbookTests(unittest.TestCase):
    def test_build_payload_accepts_bound_guarded_runbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            handoff_dir, archive, manifest = make_material(tmp)
            apply_path = write_json(tmp / "apply.json", apply_packet())
            handoff_path = write_json(
                tmp / "handoff.json",
                handoff_summary(handoff_dir, archive, manifest),
            )
            authz_path = write_json(
                tmp / "authz.json",
                authorization(
                    apply_path=apply_path,
                    handoff_path=handoff_path,
                    archive=archive,
                    manifest=manifest,
                    handoff_dir=handoff_dir,
                ),
            )

            payload = runbook.build_payload(
                authorization_summary_path=authz_path,
                generated_at=NOW,
                remote_alias="nl",
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertFalse(payload["production_mutation_allowed"])
        self.assertTrue(payload["checks"]["mutating_commands_have_approval_guard"])
        self.assertTrue(payload["checks"]["post_apply_validation_commands_present"])
        self.assertTrue(payload["checks"]["post_apply_evidence_paths_present"])
        self.assertTrue(payload["checks"]["post_apply_validation_commands_capture_json"])
        self.assertTrue(payload["checks"]["completion_audit_command_present"])
        self.assertTrue(payload["checks"]["rollback_commands_present"])
        self.assertTrue(payload["checks"]["no_legacy_service_targets_in_commands"])
        post_apply_paths = payload["post_apply_evidence_paths"]
        self.assertTrue(post_apply_paths["server_health_local_path"].endswith("server-health.json"))
        self.assertTrue(post_apply_paths["client_health_local_path"].endswith("client-health.json"))
        self.assertTrue(post_apply_paths["client_doctor_local_path"].endswith("client-doctor.json"))
        command_text = "\n".join(row["command"] for row in payload["commands"])
        self.assertIn("APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT", command_text)
        self.assertIn("server-health", command_text)
        self.assertIn("client-doctor", command_text)
        self.assertIn("tee", command_text)
        self.assertIn("server-health.json", command_text)
        self.assertIn("client-health.json", command_text)
        self.assertIn("client-doctor.json", command_text)
        self.assertIn("build_firstparty_production_completion_audit.py", command_text)
        self.assertIn("client-policy-rollback", command_text)
        self.assertNotIn("x-ui", command_text)
        self.assertNotIn("xray", command_text)

    def test_build_payload_rejects_tampered_handoff_archive_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            handoff_dir, archive, manifest = make_material(tmp)
            apply_path = write_json(tmp / "apply.json", apply_packet())
            handoff_path = write_json(
                tmp / "handoff.json",
                handoff_summary(handoff_dir, archive, manifest),
            )
            authz_path = write_json(
                tmp / "authz.json",
                authorization(
                    apply_path=apply_path,
                    handoff_path=handoff_path,
                    archive=archive,
                    manifest=manifest,
                    handoff_dir=handoff_dir,
                    bad_archive_hash=True,
                ),
            )

            payload = runbook.build_payload(
                authorization_summary_path=authz_path,
                generated_at=NOW,
            )

        self.assertFalse(payload["ok"])
        self.assertIn(
            "handoff_archive_hash_bound_to_authorization",
            payload["failed_checks"],
        )

    def test_mutating_command_without_approval_guard_is_detected(self) -> None:
        commands = [
            {
                "id": "bad",
                "mutation": True,
                "approval_required": True,
                "command": "sudo python3 x0vpn_node.py install-server-service --allow-os-mutation",
            }
        ]

        self.assertFalse(runbook.mutating_commands_have_approval_guard(commands))

    def test_legacy_marker_in_command_is_detected(self) -> None:
        commands = [
            {
                "id": "bad",
                "mutation": True,
                "approval_required": True,
                "command": "sudo systemctl stop xray",
            }
        ]

        self.assertEqual(runbook.legacy_marker_findings(commands), ["bad:xray"])


if __name__ == "__main__":
    unittest.main()
