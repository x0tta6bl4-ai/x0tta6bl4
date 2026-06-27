#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


MODULE_PATH = Path(__file__).with_name("build_firstparty_rollout_packet.py")
SPEC = importlib.util.spec_from_file_location("build_firstparty_rollout_packet", MODULE_PATH)
assert SPEC and SPEC.loader
rollout = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_rollout_packet"] = rollout
SPEC.loader.exec_module(rollout)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def create_fixture(root: Path, *, server_restart: bool = False) -> tuple[Path, Path, Path]:
    staging = root / "firstparty-staging-packet-test"
    readiness = root / "firstparty-production-readiness-test"
    canary = root / "firstparty-live-canary-test"
    staging.mkdir()
    readiness.mkdir()
    canary.mkdir()
    server_hash = "a" * 64
    client_hash = "b" * 64
    write_json(
        staging / "summary.json",
        {
            "ok": True,
            "deployment_epoch": "test-epoch",
            "server_candidate_hash": server_hash,
            "client_candidate_hash": client_hash,
            "raw_secret_material_stored_in_evidence": False,
            "kit_material_persisted_in_repo": False,
        },
    )
    write_json(readiness / "summary.json", {"ok": True, "decision_allowed": True})
    write_json(canary / "summary.json", {"ok": True})
    write_json(
        staging / "server-service-plan.raw.json",
        {
            "ok": True,
            "service_name": "x0tta-firstparty-vpn.service",
            "unit_path": "/etc/systemd/system/x0tta-firstparty-vpn.service",
            "unit_content": (
                "ExecStart=/usr/bin/python3 /opt/x0tta-firstparty-vpn-server/"
                "x0vpn_node.py server-tun --config /etc/x0/server.json "
                "--allow-os-mutation --uplink-interface eth0"
            ),
        },
    )
    write_json(
        staging / "client-service-plan.raw.json",
        {
            "ok": True,
            "service_name": "x0tta-firstparty-vpn-client.service",
            "unit_path": "/etc/systemd/system/x0tta-firstparty-vpn-client.service",
            "unit_content": (
                "ExecStart=/usr/bin/python3 /opt/x0tta-firstparty-vpn-client/"
                "x0vpn_node.py client-tun --config /etc/x0/client.json "
                "--allow-os-mutation --apply-client-policy --enable-kill-switch\n"
                "ExecStopPost=-/usr/bin/python3 /opt/x0tta-firstparty-vpn-client/"
                "x0vpn_node.py client-policy-rollback --config /etc/x0/client.json "
                "--allow-os-mutation --enable-kill-switch"
            ),
        },
    )
    write_json(
        staging / "apply-server-config-dry-run.raw.json",
        {
            "ok": True,
            "dry_run": True,
            "file_mutation_performed": False,
            "os_mutation_performed": False,
            "service_restart_performed": server_restart,
            "rollback_on_failure": True,
            "rollback_performed": False,
            "candidate_hash": server_hash,
            "installed_config": "/etc/x0/server.json",
        },
    )
    write_json(
        staging / "apply-client-config-dry-run.raw.json",
        {
            "ok": True,
            "dry_run": True,
            "file_mutation_performed": False,
            "os_mutation_performed": False,
            "service_restart_performed": False,
            "rollback_on_failure": True,
            "rollback_performed": False,
            "candidate_hash": client_hash,
            "installed_config": "/etc/x0/client.json",
        },
    )
    write_json(
        staging / "verify-client-kits.raw.json",
        {
            "ok": True,
            "kit_count": 1,
            "require_signature": True,
            "readiness_required": True,
            "exports": [
                {
                    "ok": True,
                    "signature_present": True,
                    "readiness": {"ok": True},
                    "server_secrets_included": False,
                }
            ],
        },
    )
    write_json(
        staging / "export-client-kits.raw.json",
        {"ok": True, "server_secrets_included": False},
    )
    return staging, readiness, canary


class FirstPartyRolloutPacketTests(unittest.TestCase):
    def test_build_payload_accepts_safe_firstparty_rollout_packet(self) -> None:
        with TemporaryDirectory() as tmp:
            staging, readiness, canary = create_fixture(Path(tmp))

            payload = rollout.build_payload(
                staging_dir=staging,
                production_readiness_dir=readiness,
                canary_dir=canary,
                generated_at="2026-06-06T00:00:00Z",
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertFalse(payload["production_mutation_allowed"])
        self.assertEqual(
            payload["approval_phrase_required"],
            rollout.APPROVAL_PHRASE,
        )
        self.assertTrue(payload["checks"]["client_unit_has_rollback_exec_stop"])

    def test_build_payload_rejects_restart_in_dry_run(self) -> None:
        with TemporaryDirectory() as tmp:
            staging, readiness, canary = create_fixture(Path(tmp), server_restart=True)

            payload = rollout.build_payload(
                staging_dir=staging,
                production_readiness_dir=readiness,
                canary_dir=canary,
                generated_at="2026-06-06T00:00:00Z",
            )

        self.assertFalse(payload["ok"])
        self.assertIn("server_apply_dry_run_ok", payload["failed_checks"])


if __name__ == "__main__":
    unittest.main()
