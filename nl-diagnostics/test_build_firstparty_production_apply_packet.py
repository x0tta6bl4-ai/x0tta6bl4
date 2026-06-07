#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_apply_packet.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_apply_packet",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
apply_packet = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_apply_packet"] = apply_packet
SPEC.loader.exec_module(apply_packet)


def sample_endpoint(*, passed: bool = True) -> dict:
    checks = {
        "candidate_port_free_on_nl_snapshot": passed,
    }
    return {
        "ok": passed,
        "host": "89.125.1.107" if passed else "127.0.0.1",
        "bind_host": "0.0.0.0" if passed else "127.0.0.1",
        "port": 40467,
        "transport": "tcp",
        "deployment_epoch": "production-firstparty-endpoint-test",
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "raw_secret_material_stored_in_evidence": False,
        "checks": checks,
    }


def sample_candidate(*, passed: bool = True) -> dict:
    server_unit = (
        "ExecStart=/usr/bin/python3 /opt/x0tta-firstparty-vpn-server/"
        "x0vpn_node.py server-tun --config /etc/x0tta-firstparty-vpn-server/"
        "server.json --allow-os-mutation --uplink-interface eth0"
    )
    client_unit = (
        "ExecStart=/usr/bin/python3 /opt/x0tta-firstparty-vpn-client/"
        "x0vpn_node.py client-tun --config /etc/x0tta-firstparty-vpn-client/"
        "client.json --allow-os-mutation --apply-client-policy --enable-kill-switch\n"
        "ExecStopPost=/usr/bin/python3 /opt/x0tta-firstparty-vpn-client/"
        "x0vpn_node.py client-policy-rollback --config "
        "/etc/x0tta-firstparty-vpn-client/client.json --enable-kill-switch"
    )
    apply = {
        "ok": passed,
        "dry_run": True,
        "file_mutation_performed": False,
        "os_mutation_performed": False,
        "service_restart_performed": False,
        "rollback_on_failure": True,
        "rollback_performed": False,
        "candidate_hash": "a" * 64,
    }
    client_apply = dict(apply)
    client_apply["candidate_hash"] = "b" * 64
    return {
        "generate_ok": passed,
        "server_service_plan_ok": passed,
        "client_service_plan_ok": passed,
        "server_apply_dry_run": apply,
        "client_apply_dry_run": client_apply,
        "export_client_kits_ok": passed,
        "verify_client_kits_ok": passed,
        "deployment_epoch": "production-firstparty-apply-test",
        "server_bind_host": "0.0.0.0",
        "client_host": "89.125.1.107",
        "port": 40467,
        "transport": "tcp",
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "server_unit_path": "/etc/systemd/system/x0tta-firstparty-vpn.service",
        "client_unit_path": "/etc/systemd/system/x0tta-firstparty-vpn-client.service",
        "server_unit_content": server_unit if passed else server_unit + " xray",
        "client_unit_content": client_unit,
        "server_candidate_hash": "a" * 64,
        "client_candidate_hash": "b" * 64,
        "server_apply_candidate_hash": "a" * 64,
        "client_apply_candidate_hash": "b" * 64,
        "client_kit_count": 2,
        "verified_kit_count": 2 if passed else 1,
        "server_secrets_included": False,
        "temp_config_dir_persisted": False,
    }


class FirstPartyProductionApplyPacketTests(unittest.TestCase):
    def test_build_payload_accepts_guarded_public_apply_packet(self):
        with tempfile.TemporaryDirectory() as tmp_raw:
            endpoint_path = Path(tmp_raw) / "endpoint.json"
            endpoint_path.write_text(json.dumps(sample_endpoint()), encoding="utf-8")
            with patch.object(
                apply_packet,
                "_build_candidate_artifacts",
                return_value=sample_candidate(),
            ):
                payload = apply_packet.build_payload(endpoint_summary_path=endpoint_path)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["host"], "89.125.1.107")
        self.assertEqual(payload["bind_host"], "0.0.0.0")
        self.assertEqual(payload["port"], 40467)
        self.assertFalse(payload["production_mutation_allowed"])
        self.assertFalse(payload["raw_secret_material_stored_in_evidence"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["server_apply_dry_run_ok"])
        self.assertTrue(payload["checks"]["client_kits_signed"])
        self.assertTrue(payload["checks"]["temp_config_dir_removed"])

    def test_build_payload_rejects_loopback_or_legacy_apply_packet(self):
        with tempfile.TemporaryDirectory() as tmp_raw:
            endpoint_path = Path(tmp_raw) / "endpoint.json"
            endpoint_path.write_text(
                json.dumps(sample_endpoint(passed=False)),
                encoding="utf-8",
            )
            with patch.object(
                apply_packet,
                "_build_candidate_artifacts",
                return_value=sample_candidate(passed=False),
            ):
                payload = apply_packet.build_payload(endpoint_summary_path=endpoint_path)

        self.assertFalse(payload["ok"])
        self.assertIn("endpoint_host_public", payload["failed_checks"])
        self.assertIn("endpoint_bind_not_loopback", payload["failed_checks"])
        self.assertIn("endpoint_port_free_on_nl_snapshot", payload["failed_checks"])
        self.assertIn("service_units_firstparty_only", payload["failed_checks"])
        self.assertIn("client_kits_signed", payload["failed_checks"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
