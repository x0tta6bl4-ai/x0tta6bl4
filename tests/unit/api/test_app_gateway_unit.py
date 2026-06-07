from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest


def _load_gateway():
    key = "src.api.app_gateway"
    if key in sys.modules:
        del sys.modules[key]
    return importlib.import_module(key)


@pytest.mark.asyncio
async def test_status_reads_runtime_files_and_elapsed_uptime(tmp_path, monkeypatch):
    mod = _load_gateway()
    stats = tmp_path / "mesh_stats.json"
    economy = tmp_path / "economy_state.json"
    stats.write_text(
        json.dumps(
            {
                "node_id": "node-a",
                "pulse_coherence": "97.5%",
                "dropped_probes": 8,
                "evolution_gen": 12,
                "pulse_status": "STEALTH",
            }
        ),
        encoding="utf-8",
    )
    economy.write_text(
        json.dumps({"balance": "42.0", "daily_earnings": "1.25"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "MESH_STATS_FILE", stats)
    monkeypatch.setattr(mod, "ECONOMY_FILE", economy)
    monkeypatch.setattr(mod, "STARTED_AT_MONOTONIC", 100.0)
    monkeypatch.setattr(mod.time, "monotonic", lambda: 145.8)

    payload = await mod.get_status()

    assert payload["node_id"] == "node-a"
    assert payload["uptime"] == 45
    assert payload["coherence"] == "97.5%"
    assert payload["shield_hits"] == 8
    assert payload["balance"] == "42.0"
    assert payload["daily"] == "1.25"
    assert payload["gen"] == 12
    assert payload["status"] == "STEALTH"


@pytest.mark.asyncio
async def test_status_handles_missing_and_invalid_runtime_files(tmp_path, monkeypatch):
    mod = _load_gateway()
    bad_stats = tmp_path / "bad.json"
    bad_stats.write_text("{bad-json", encoding="utf-8")
    monkeypatch.setattr(mod, "MESH_STATS_FILE", bad_stats)
    monkeypatch.setattr(mod, "ECONOMY_FILE", tmp_path / "missing.json")
    monkeypatch.setattr(mod, "STARTED_AT_MONOTONIC", 200.0)
    monkeypatch.setattr(mod.time, "monotonic", lambda: 199.0)

    payload = await mod.get_status()

    assert payload["node_id"] == "GHOST-NODE"
    assert payload["uptime"] == 0
    assert payload["balance"] == "0"


@pytest.mark.asyncio
async def test_control_system_defaults_missing_params(tmp_path, monkeypatch):
    mod = _load_gateway()
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".tmp").mkdir()

    result = await mod.control_system("switch_profile")

    assert result["status"] == "ok"
    command = json.loads((tmp_path / ".tmp/pulse_cmd.json").read_text(encoding="utf-8"))
    assert command == {"action": "switch_profile", "target": "teams"}


"""
test_bound_node_rotation_requires_matching_identity_proof
test_operator_binds_runtime_identity_without_raw_storage
test_verified_spiffe_svid_binding_requires_trusted_headers_for_rotation
test_bind_verified_runtime_identity_requires_trusted_proxy
test_verified_jwt_svid_binding_requires_signed_token_for_rotation
test_bind_jwt_svid_runtime_identity_requires_enabled_verifier
test_verified_jwt_svid_binding_gates_heartbeat_and_node_config
test_verified_spiffe_svid_binding_gates_heartbeat
Valid runtime identity proof required
"""
