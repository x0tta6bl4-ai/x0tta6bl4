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


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_authorization.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_authorization",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
authz = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_authorization"] = authz
SPEC.loader.exec_module(authz)


NOW = "2026-06-07T00:30:00Z"


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def endpoint_summary(*, passed: bool = True, generated_at: str = NOW) -> dict:
    return {
        "generated_at": generated_at,
        "ok": passed,
        "host": "89.125.1.107" if passed else "127.0.0.1",
        "bind_host": "0.0.0.0" if passed else "127.0.0.1",
        "port": 40467,
        "transport": "tcp",
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
    }


def guarded_packet(*, passed: bool = True, generated_at: str = NOW) -> dict:
    return {
        "generated_at": generated_at,
        "ok": passed,
        "host": "89.125.1.107",
        "bind_host": "0.0.0.0",
        "port": 40467,
        "transport": "tcp",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "post_apply_validation_required": True,
        "secure_material_handoff_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "checks": {
            "source_post_apply_validation_ready": passed,
            "apply_packet_requires_secure_handoff": passed,
            "manifest_secret_free": passed,
        },
        "raw_secret_material_stored_in_evidence": False,
        "repo_material_persisted": False,
    }


def make_handoff(tmp: Path, *, bad_archive_hash: bool = False) -> tuple[dict, Path, Path, Path]:
    handoff_dir = tmp / "handoff"
    handoff_dir.mkdir()
    os.chmod(handoff_dir, 0o700)
    archive = tmp / "handoff.tar.gz"
    archive.write_bytes(b"private archive placeholder")
    os.chmod(archive, 0o600)
    manifest = handoff_dir / "MANIFEST.secret-free.json"
    manifest.write_text('{"secret_free": true}\n', encoding="utf-8")
    os.chmod(manifest, 0o600)
    archive_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    summary = guarded_packet()
    summary.update(
        {
            "handoff_dir": str(handoff_dir),
            "handoff_archive": str(archive),
            "handoff_manifest": str(manifest),
            "archive_sha256": ("0" * 64 if bad_archive_hash else archive_hash),
            "manifest_sha256": manifest_hash,
            "checks": {
                "apply_packet_requires_secure_handoff": True,
                "manifest_secret_free": True,
            },
        }
    )
    return summary, handoff_dir, archive, manifest


class FirstPartyProductionAuthorizationTests(unittest.TestCase):
    def test_build_payload_accepts_bound_guarded_private_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            handoff_summary, _, _, _ = make_handoff(tmp)
            payload = authz.build_payload(
                endpoint_summary_path=write_json(tmp / "endpoint.json", endpoint_summary()),
                apply_packet_summary_path=write_json(tmp / "apply.json", guarded_packet()),
                handoff_summary_path=write_json(tmp / "handoff.json", handoff_summary),
                rollout_summary_path=write_json(tmp / "rollout.json", guarded_packet()),
                preapply_summary_path=write_json(tmp / "preapply.json", guarded_packet()),
                generated_at=NOW,
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertFalse(payload["production_mutation_allowed"])
        self.assertTrue(payload["manual_approval_still_required"])
        self.assertTrue(payload["checks"]["handoff_archive_hash_matches_summary"])
        self.assertTrue(payload["checks"]["handoff_manifest_hash_matches_summary"])
        self.assertTrue(payload["checks"]["approval_blocked_apply_packet"])

    def test_build_payload_rejects_stale_or_tampered_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_raw:
            tmp = Path(tmp_raw)
            handoff_summary, _, _, _ = make_handoff(tmp, bad_archive_hash=True)
            payload = authz.build_payload(
                endpoint_summary_path=write_json(
                    tmp / "endpoint.json",
                    endpoint_summary(generated_at="2026-06-05T00:00:00Z"),
                ),
                apply_packet_summary_path=write_json(tmp / "apply.json", guarded_packet()),
                handoff_summary_path=write_json(tmp / "handoff.json", handoff_summary),
                rollout_summary_path=write_json(tmp / "rollout.json", guarded_packet()),
                preapply_summary_path=write_json(tmp / "preapply.json", guarded_packet()),
                generated_at=NOW,
                max_evidence_age_hours=24,
            )

        self.assertFalse(payload["ok"])
        self.assertIn("all_evidence_fresh", payload["failed_checks"])
        self.assertIn("handoff_archive_hash_matches_summary", payload["failed_checks"])


if __name__ == "__main__":
    unittest.main()
