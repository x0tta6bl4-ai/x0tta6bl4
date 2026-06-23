#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("build_firstparty_production_endpoint.py")
SPEC = importlib.util.spec_from_file_location(
    "build_firstparty_production_endpoint",
    MODULE_PATH,
)
assert SPEC and SPEC.loader
endpoint = importlib.util.module_from_spec(SPEC)
sys.modules["build_firstparty_production_endpoint"] = endpoint
SPEC.loader.exec_module(endpoint)


def candidate_artifacts(*, host: str, bind_host: str, port: int, transport: str) -> dict:
    return {
        "generate_ok": True,
        "server_service_plan_ok": True,
        "client_service_plan_ok": True,
        "deployment_epoch": "production-firstparty-endpoint-test",
        "server_bind_host": bind_host,
        "client_host": host,
        "port": port,
        "transport": transport,
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "server_unit_content": "ExecStart=/usr/bin/python3 x0vpn_node.py server-tun --config /etc/x0/server.json",
        "client_unit_content": "ExecStart=/usr/bin/python3 x0vpn_node.py client-tun --config /etc/x0/client.json",
        "server_candidate_hash": "a" * 64,
        "client_candidate_hash": "b" * 64,
        "temp_config_dir_persisted": False,
    }


class FirstPartyProductionEndpointTests(unittest.TestCase):
    def test_build_payload_accepts_free_public_firstparty_endpoint(self) -> None:
        listeners = "tcp LISTEN 0 4096 *:443 *:* users:((\"xray\",pid=1,fd=1))\n"
        with patch.object(endpoint, "_build_candidate_artifacts", side_effect=candidate_artifacts):
            payload = endpoint.build_payload(
                host="89.125.1.107",
                bind_host="0.0.0.0",
                port=40467,
                transport="tcp",
                listeners_text=listeners,
                generated_at="2026-06-06T00:00:00Z",
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["failed_checks"], [])
        self.assertTrue(payload["checks"]["candidate_port_free_on_nl_snapshot"])
        self.assertTrue(payload["checks"]["endpoint_host_public"])
        self.assertFalse(payload["raw_secret_material_stored_in_evidence"])

    def test_build_payload_rejects_occupied_or_loopback_endpoint(self) -> None:
        listeners = "tcp LISTEN 0 4096 127.0.0.1:40467 *:* users:((\"python3\",pid=1,fd=1))\n"
        with patch.object(endpoint, "_build_candidate_artifacts", side_effect=candidate_artifacts):
            payload = endpoint.build_payload(
                host="127.0.0.1",
                bind_host="127.0.0.1",
                port=40467,
                transport="tcp",
                listeners_text=listeners,
                generated_at="2026-06-06T00:00:00Z",
            )

        self.assertFalse(payload["ok"])
        self.assertIn("candidate_port_free_on_nl_snapshot", payload["failed_checks"])
        self.assertIn("endpoint_host_public", payload["failed_checks"])
        self.assertIn("server_bind_not_loopback", payload["failed_checks"])


if __name__ == "__main__":
    unittest.main()
