from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "deploy_spiffe_to_mesh_nodes.py"
    spec = importlib.util.spec_from_file_location("deploy_spiffe_to_mesh_nodes", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load deploy_spiffe_to_mesh_nodes module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_explicit_node_ids_deduplicates_and_trims():
    mod = _load_module()

    assert mod.resolve_node_ids(" node-a, node-b\nnode-a ,, node-c ") == [
        "node-a",
        "node-b",
        "node-c",
    ]


def test_nodes_all_requires_real_inventory(monkeypatch):
    mod = _load_module()
    monkeypatch.delenv("X0TTA6BL4_MESH_NODES_FILE", raising=False)
    monkeypatch.delenv("X0TTA6BL4_MESH_NODE_IDS", raising=False)

    with pytest.raises(ValueError, match="requires a real mesh inventory"):
        mod.resolve_node_ids("all")


def test_nodes_all_loads_json_inventory(tmp_path, monkeypatch):
    mod = _load_module()
    monkeypatch.delenv("X0TTA6BL4_MESH_NODES_FILE", raising=False)
    monkeypatch.delenv("X0TTA6BL4_MESH_NODE_IDS", raising=False)
    inventory = tmp_path / "mesh-nodes.json"
    inventory.write_text(
        json.dumps(
            {
                "nodes": [
                    {"id": "node-a"},
                    {"node_id": "node-b"},
                    "node-c",
                    {"name": "node-d"},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert mod.resolve_node_ids("all", inventory) == [
        "node-a",
        "node-b",
        "node-c",
        "node-d",
    ]


def test_extract_join_token_supports_spire_cli_output():
    mod = _load_module()

    assert mod._extract_join_token("Generated token\nToken: join-token-123\n") == "join-token-123"


def test_generate_join_token_runs_spire_server_cli(monkeypatch):
    mod = _load_module()
    calls = []

    class _Result:
        returncode = 0
        stdout = "Token: join-token-node-a\n"
        stderr = ""

    def fake_run(cmd, capture_output, text, timeout, env, check):
        calls.append(
            {
                "cmd": cmd,
                "capture_output": capture_output,
                "text": text,
                "timeout": timeout,
                "env": env,
                "check": check,
            }
        )
        return _Result()

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    deployer = mod.MeshNodeSPIFFEDeployer(
        trust_domain="test.mesh",
        spire_server_address="spire-server:8081",
        spire_server_bin="/opt/spire/bin/spire-server",
    )

    token = asyncio.run(deployer._generate_join_token("node-a"))

    assert token == "join-token-node-a"
    assert calls[0]["cmd"] == [
        "/opt/spire/bin/spire-server",
        "token",
        "generate",
        "-spiffeID",
        "spiffe://test.mesh/node/node-a",
    ]
    assert calls[0]["env"]["X0TTA6BL4_SPIFFE_NODE_ID"] == "node-a"
    assert calls[0]["env"]["X0TTA6BL4_SPIFFE_TRUST_DOMAIN"] == "test.mesh"
    assert calls[0]["env"]["X0TTA6BL4_SPIRE_SERVER_ADDRESS"] == "spire-server:8081"
