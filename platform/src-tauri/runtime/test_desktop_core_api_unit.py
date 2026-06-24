from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("desktop_core_api.py")


def load_module():
    spec = importlib.util.spec_from_file_location("desktop_core_api_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_live_snapshot_redacts_runtime_identifiers(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    (tmp_path / "runtime-state.json").write_text(
        json.dumps(
            {
                "mode": "mesh",
                "recommended_action": "observe",
                "node_id": "node-secret-123",
                "hostname": "desktop-secret-host",
                "api_key": "api-secret",
                "peers": ["peer-secret"],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "client-profile-hint.json").write_text(
        json.dumps(
            {
                "vless_url": "vless://secret",
                "recommended_profile": "local",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "listener-loss-signal.json").write_text(
        json.dumps(
            {
                "status": "observed",
                "source": "local-probe",
            }
        ),
        encoding="utf-8",
    )

    payload = module.live_snapshot(limit=5)
    encoded = json.dumps(payload, sort_keys=True)

    assert payload["event_bus"]["payloads_redacted"] is True
    assert payload["local_state"]["raw_values_redacted"] is True
    assert payload["event_bus"]["recent_events"][0]["data"]["node_id"]["redacted"] is True
    assert payload["local_state"]["runtime_state"]["node_id"]["redacted"] is True
    assert payload["local_state"]["runtime_state"]["hostname"]["redacted"] is True
    assert payload["local_state"]["runtime_state"]["api_key"]["redacted"] is True
    assert payload["local_state"]["runtime_state"]["peers"][0]["redacted"] is True
    assert payload["local_state"]["client_profile_hint"]["vless_url"]["redacted"] is True
    assert "node-secret-123" not in encoded
    assert "desktop-secret-host" not in encoded
    assert "api-secret" not in encoded
    assert "peer-secret" not in encoded
    assert "vless://secret" not in encoded


def test_mesh_peer_and_node_surfaces_redact_ids(tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    (tmp_path / "runtime-state.json").write_text(
        json.dumps(
            {
                "mode": "mesh",
                "node_id": "node-secret-456",
                "peers": [
                    {
                        "id": "peer-secret-a",
                        "node_id": "peer-node-secret-a",
                        "spiffe_id": "spiffe://secret/peer-a",
                        "status": "visible",
                    },
                    {
                        "peer_id": "peer-secret-b",
                        "status": "visible",
                    },
                ],
                "private_key": "private-secret",
            }
        ),
        encoding="utf-8",
    )

    peers = module.get_payload("/mesh/peers", {})
    nodes_all = module.get_payload("/api/v1/maas/nodes/mesh-secret/nodes/all", {})
    readiness = module.node_readiness("mesh-secret", "node-secret-456")
    telemetry = module.node_telemetry("mesh-secret", "node-secret-456")
    vpn_status = module.get_payload("/api/v1/vpn/status", {})
    encoded = json.dumps(
        {
            "peers": peers,
            "nodes_all": nodes_all,
            "readiness": readiness,
            "telemetry": telemetry,
            "vpn": vpn_status,
        },
        sort_keys=True,
    )

    assert peers["raw_values_redacted"] is True
    assert peers["peers"][0]["id"]["redacted"] is True
    assert peers["peers"][0]["node_id"]["redacted"] is True
    assert peers["peers"][0]["spiffe_id"]["redacted"] is True
    assert peers["peers"][0]["status"] == "visible"
    assert nodes_all["raw_values_redacted"] is True
    assert nodes_all["nodes"][0]["id"]["redacted"] is True
    assert readiness["mesh_id"]["redacted"] is True
    assert readiness["node_id"]["redacted"] is True
    assert readiness["production_ready"] is False
    assert telemetry["runtime_state"]["node_id"]["redacted"] is True
    assert telemetry["runtime_state"]["private_key"]["redacted"] is True
    assert vpn_status["runtime_state"]["private_key"]["redacted"] is True
    assert "node-secret-456" not in encoded
    assert "peer-secret-a" not in encoded
    assert "peer-node-secret-a" not in encoded
    assert "spiffe://secret/peer-a" not in encoded
    assert "private-secret" not in encoded
