#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


MODULE_PATH = Path(__file__).with_name("build_firstparty_preapply_readiness.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_preapply_readiness",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
preapply = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_preapply_readiness"] = preapply
SPEC.loader.exec_module(preapply)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def create_fixture(root: Path, *, legacy_service_name: bool = False) -> tuple[Path, Path]:
    rollout = root / "rollout.json"
    manifest = root / "manifest.json"
    write_json(
        rollout,
        {
            "ok": True,
            "approval_phrase_required": preapply.APPROVAL_PHRASE,
            "approval_present": False,
            "production_mutation_allowed": False,
            "no_nl_or_spb_writes_performed": True,
            "deployment_epoch": "test-epoch",
            "server_service_name": (
                "xray.service" if legacy_service_name else "x0tta-firstparty-vpn.service"
            ),
            "client_service_name": "x0tta-firstparty-vpn-client.service",
            "server_unit_path": "/etc/systemd/system/x0tta-firstparty-vpn.service",
            "client_unit_path": "/etc/systemd/system/x0tta-firstparty-vpn-client.service",
            "server_config_target": "/etc/x0tta-firstparty-vpn-server/server.json",
            "client_config_target": "/etc/x0tta-firstparty-vpn-client/client.json",
        },
    )
    write_json(
        manifest,
        {
            "nl_write_allowed": False,
            "source_promotion_status": {"deployable_to_nl": False},
        },
    )
    return rollout, manifest


class FirstPartyPreapplyReadinessTests(unittest.TestCase):
    def test_build_payload_accepts_guarded_firstparty_preapply(self) -> None:
        with TemporaryDirectory() as tmp:
            rollout, manifest = create_fixture(Path(tmp))

            payload = preapply.build_payload(
                rollout_summary_path=rollout,
                manifest_path=manifest,
                generated_at="2026-06-06T00:00:00Z",
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["source_post_apply_validation_ready"])
        self.assertFalse(payload["production_mutation_allowed"])

    def test_build_payload_rejects_legacy_service_target(self) -> None:
        with TemporaryDirectory() as tmp:
            rollout, manifest = create_fixture(Path(tmp), legacy_service_name=True)

            payload = preapply.build_payload(
                rollout_summary_path=rollout,
                manifest_path=manifest,
                generated_at="2026-06-06T00:00:00Z",
            )

        self.assertFalse(payload["ok"])
        self.assertIn("firstparty_service_names_scoped", payload["failed_checks"])
        self.assertIn("legacy_service_markers_absent", payload["failed_checks"])


if __name__ == "__main__":
    unittest.main()
