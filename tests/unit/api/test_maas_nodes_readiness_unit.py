from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import src.api.maas_nodes as nodes_mod


def _force_optional_dependencies_ready(monkeypatch) -> None:
    monkeypatch.setattr(nodes_mod, "_set_external_telemetry", lambda *args, **kwargs: None)
    monkeypatch.setattr(nodes_mod, "_get_external_telemetry", lambda *args, **kwargs: {})
    monkeypatch.setattr(nodes_mod, "_get_external_telemetry_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(nodes_mod, "MESH_HEALING_AVAILABLE", True)
    monkeypatch.setattr(nodes_mod, "MeshNetworkManager", object)
    monkeypatch.setattr(nodes_mod, "VerificationMode", SimpleNamespace(FULL="full"))


def test_node_readiness_ready_when_core_and_optional_dependencies_are_available(monkeypatch):
    _force_optional_dependencies_ready(monkeypatch)
    db = MagicMock(spec=["query", "add", "commit", "delete"])

    payload = nodes_mod._node_readiness_status(db)

    assert payload["status"] == "ready"
    assert payload["route_registered"] is True
    assert payload["registration_mode"] == "full_mode_only"
    assert payload["route_present_in_light_mode"] is False
    assert payload["lifecycle_binding"] == "route_import_only"
    assert payload["startup_hook_completed"] is None
    assert payload["node_runtime_ready"] is True
    assert payload["node_db_ready"] is True
    assert payload["node_model_ready"] is True
    assert payload["node_rbac_ready"] is True
    assert payload["token_signer_ready"] is True
    assert payload["audit_log_ready"] is True
    assert payload["telemetry_bridge_ready"] is True
    assert payload["healing_service_ready"] is True
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert "dataplane_delivery" in payload["cross_plane_claim_gate"]["requested_claim_ids"]
    assert payload["legacy_route_shadowing"]["shadowed_by_legacy"] == [
        "POST /{mesh_id}/nodes/register",
        "GET /{mesh_id}/nodes/pending",
        "POST /{mesh_id}/nodes/{node_id}/approve",
        "POST /{mesh_id}/nodes/{node_id}/revoke",
    ]
    assert payload["legacy_route_shadowing"]["db_backed_routes_active"] == [
        "POST /{mesh_id}/nodes/{node_id}/heartbeat",
        "GET /{mesh_id}/nodes/{node_id}/telemetry",
        "POST /{mesh_id}/nodes/check-access",
        "GET /{mesh_id}/node-config/{node_id}",
        "GET /{mesh_id}/nodes/all",
        "DELETE /{mesh_id}/nodes/{node_id}",
        "POST /{mesh_id}/nodes/{node_id}/heal",
    ]
    assert payload["degraded_dependencies"] == []


def test_node_readiness_degraded_when_runtime_dependencies_are_missing(monkeypatch):
    monkeypatch.setattr(nodes_mod, "MeshNode", SimpleNamespace(id="id"))
    monkeypatch.setattr(nodes_mod, "MeshInstance", SimpleNamespace(id="id"))
    monkeypatch.setattr(nodes_mod, "ACLPolicy", SimpleNamespace(id="id"))
    monkeypatch.setattr(nodes_mod, "MarketplaceListing", SimpleNamespace(id="id"))
    monkeypatch.setattr(nodes_mod, "MarketplaceEscrow", SimpleNamespace(id="id"))
    monkeypatch.setattr(nodes_mod, "require_role", None)
    monkeypatch.setattr(nodes_mod, "require_mesh_access", None)
    monkeypatch.setattr(nodes_mod, "token_signer", SimpleNamespace())
    monkeypatch.setattr(nodes_mod, "record_audit_log", None)
    monkeypatch.setattr(nodes_mod, "_set_external_telemetry", None)
    monkeypatch.setattr(nodes_mod, "_get_external_telemetry", None)
    monkeypatch.setattr(nodes_mod, "_get_external_telemetry_history", None)
    monkeypatch.setattr(nodes_mod, "MESH_HEALING_AVAILABLE", False)
    monkeypatch.setattr(nodes_mod, "MeshNetworkManager", None)
    monkeypatch.setattr(nodes_mod, "VerificationMode", None)

    payload = nodes_mod._node_readiness_status(SimpleNamespace())

    assert payload["status"] == "degraded"
    assert payload["node_runtime_ready"] is False
    assert payload["node_db_ready"] is False
    assert payload["node_model_ready"] is False
    assert payload["node_rbac_ready"] is False
    assert payload["token_signer_ready"] is False
    assert payload["audit_log_ready"] is False
    assert payload["telemetry_bridge_ready"] is False
    assert payload["healing_service_ready"] is False
    assert payload["degraded_dependencies"] == [
        "database",
        "node_models",
        "rbac",
        "token_signing",
        "audit_log",
        "telemetry_bridge",
        "healing_service",
    ]
    assert "legacy route precedence" in payload["claim_boundary"]


def test_node_readiness_endpoint_marks_degraded_dependencies(monkeypatch):
    _force_optional_dependencies_ready(monkeypatch)
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(
        nodes_mod.node_readiness(request=request, db=SimpleNamespace())
    )

    assert payload["status"] == "degraded"
    assert request.state.degraded_dependencies == {"database"}
