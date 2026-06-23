"""Unit tests for MaaS compatibility lifecycle read EventBus evidence."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response

import src.api.maas_compat as compat_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-compat-lifecycle-read",
            limit=10,
        )
    ]


def _mesh(*, mesh_id: str, owner_id: str, status: str = "active"):
    return SimpleNamespace(
        mesh_id=mesh_id,
        owner_id=owner_id,
        status=status,
        node_instances={
            f"{mesh_id}-secret-node-1": {"status": "healthy"},
            f"{mesh_id}-secret-node-2": {"status": "degraded"},
        },
        pqc_enabled=True,
        obfuscation="none",
        traffic_profile="voip",
    )


def test_compat_mesh_list_publishes_redacted_lifecycle_read_evidence(
    monkeypatch,
    tmp_path,
):
    owner_id = "owner-secret-compat-list"
    mesh_id = "mesh-secret-compat-list"
    other_mesh_id = "mesh-secret-other-list"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_all_meshes",
        lambda: {
            mesh_id: _mesh(mesh_id=mesh_id, owner_id=owner_id),
            other_mesh_id: _mesh(mesh_id=other_mesh_id, owner_id="other-owner"),
            "mesh-secret-terminated": _mesh(
                mesh_id="mesh-secret-terminated",
                owner_id=owner_id,
                status="terminated",
            ),
        },
    )

    result = asyncio.run(
        compat_mod.list_meshes_alias(
            request,
            http_response=http_response,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result["count"] == 1
    assert result["meshes"][0]["mesh_id"] == mesh_id
    assert result["meshes"][0]["peers"][0]["node_id"].startswith(mesh_id)
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_compat_lifecycle_read_claim_boundary_headers.v1"
    )
    assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == (
        "maas_compat.lifecycle.list"
    )
    assert http_response.headers[
        "X-X0TTA6BL4-Local-Lifecycle-State-Observation-Claim-Allowed"
    ] == "true"
    assert http_response.headers[
        "X-X0TTA6BL4-External-Infrastructure-Convergence-Claim-Allowed"
    ] == "false"
    assert http_response.headers[
        "X-X0TTA6BL4-Production-Readiness-Claim-Allowed"
    ] == "false"

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "compat_mesh_list_read"
    assert payload["service_name"] == "maas-compat-lifecycle-read"
    assert payload["source_alias"] == "maas-compat-lifecycle-read"
    assert payload["layer"] == "api_compat_lifecycle_observed_state"
    assert payload["stage"] == "mesh_list_read"
    assert payload["status"] == "success"
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["mesh_count"] == 1
    assert payload["node_count"] == 2
    assert payload["healthy_node_count"] == 1
    assert payload["result_summary"]["status_counts"] == {"active": 1}
    assert (
        payload["result_summary"][
            "compat_lifecycle_read_claim_boundary_headers_present"
        ]
        is True
    )
    assert payload["result_summary"]["claim_surface"] == (
        "maas_compat.lifecycle.list"
    )
    assert (
        payload["result_summary"][
            "local_lifecycle_state_observation_claim_allowed"
        ]
        is True
    )
    assert payload["result_summary"]["mesh_lifecycle_claim_gate_present"] is True
    assert payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert (
        payload["result_summary"][
            "external_infrastructure_convergence_claim_allowed"
        ]
        is False
    )
    assert payload["result_summary"]["production_readiness_claim_allowed"] is False
    assert payload["read_only"] is True
    assert payload["control_action"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (owner_id, mesh_id, other_mesh_id, f"{mesh_id}-secret-node-1"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_mesh_status_success_publishes_redacted_lifecycle_read_evidence(
    monkeypatch,
    tmp_path,
):
    owner_id = "owner-secret-compat-status"
    mesh_id = "mesh-secret-compat-status"
    node_id = "node-secret-compat-status"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()

    async def _status(*, mesh_id, user):
        return compat_mod.MeshStatusResponse(
            mesh_id=mesh_id,
            status="active",
            nodes_total=1,
            nodes_healthy=1,
            uptime_seconds=12.0,
            pqc_enabled=True,
            obfuscation="none",
            traffic_profile="voip",
            peers=[{"node_id": node_id, "status": "healthy"}],
            health_score=1.0,
            control_policy_evidence={"basis": "dataplane_confirmed"},
            mesh_lifecycle_claim_gate={"schema": "unit.lifecycle.v1"},
            cross_plane_claim_gate={"schema": "unit.cross_plane.v1"},
        )

    monkeypatch.setattr(compat_mod.modular_mesh, "get_mesh_status", _status)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mesh",
        lambda candidate: SimpleNamespace(owner_id=owner_id)
        if candidate == mesh_id
        else None,
    )

    result = asyncio.run(
        compat_mod.get_mesh_status_alias(
            mesh_id,
            request,
            http_response=http_response,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result.mesh_id == mesh_id
    assert result.peers[0]["node_id"] == node_id
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_compat_lifecycle_read_claim_boundary_headers.v1"
    )
    assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == (
        "maas_compat.lifecycle.status"
    )
    assert http_response.headers[
        "X-X0TTA6BL4-Node-Reachability-Claim-Allowed"
    ] == "false"
    assert http_response.headers[
        "X-X0TTA6BL4-Fresh-Dataplane-Health-Claim-Allowed"
    ] == "false"

    payload = _payloads(bus)[0]
    assert payload["operation"] == "compat_mesh_status_read"
    assert payload["stage"] == "mesh_status_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == compat_mod._redacted_sha256_prefix(owner_id)
    assert payload["result_summary"]["peer_count"] == 1
    assert payload["result_summary"]["control_policy_evidence_present"] is True
    assert (
        payload["result_summary"][
            "compat_lifecycle_read_claim_boundary_headers_present"
        ]
        is True
    )
    assert payload["result_summary"]["claim_surface"] == (
        "maas_compat.lifecycle.status"
    )
    assert payload["result_summary"]["mesh_lifecycle_claim_gate_present"] is True
    assert payload["result_summary"]["mesh_metrics_claim_gate_present"] is False
    assert payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert payload["result_summary"]["node_reachability_claim_allowed"] is False
    assert payload["result_summary"]["fresh_dataplane_health_claim_allowed"] is False

    serialized = json.dumps(_payloads(bus), sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (owner_id, mesh_id, node_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_mesh_metrics_success_publishes_redacted_lifecycle_read_evidence(
    monkeypatch,
    tmp_path,
):
    owner_id = "owner-secret-compat-metrics"
    mesh_id = "mesh-secret-compat-metrics"
    secret_metric_value = "private-metric-signal"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    http_response = Response()

    async def _metrics(*, mesh_id, user):
        return compat_mod.MeshMetricsResponse(
            mesh_id=mesh_id,
            consciousness={"state": secret_metric_value},
            mape_k={"phase": "MONITOR", "private": secret_metric_value},
            network={"latency": secret_metric_value},
            control_policy_evidence={"basis": "estimate_or_fallback_based"},
            mesh_metrics_claim_gate={"schema": "unit.metrics.v1"},
            cross_plane_claim_gate={"schema": "unit.cross_plane.v1"},
            timestamp="2026-05-30T00:00:00",
        )

    monkeypatch.setattr(compat_mod.modular_mesh, "get_mesh_metrics", _metrics)
    monkeypatch.setattr(
        compat_mod.maas_registry,
        "get_mesh",
        lambda candidate: SimpleNamespace(owner_id=owner_id)
        if candidate == mesh_id
        else None,
    )

    result = asyncio.run(
        compat_mod.get_mesh_metrics_alias(
            mesh_id,
            request,
            http_response=http_response,
            current_user=SimpleNamespace(id=owner_id, role="admin"),
        )
    )

    assert result.mesh_id == mesh_id
    assert result.consciousness["state"] == secret_metric_value
    assert (
        http_response.headers["X-X0TTA6BL4-Claim-Gate-Schema"]
        == "x0tta6bl4.maas_compat_lifecycle_read_claim_boundary_headers.v1"
    )
    assert http_response.headers["X-X0TTA6BL4-Claim-Surface"] == (
        "maas_compat.lifecycle.metrics"
    )
    assert http_response.headers[
        "X-X0TTA6BL4-Dataplane-Delivery-Claim-Allowed"
    ] == "false"
    assert http_response.headers[
        "X-X0TTA6BL4-External-DPI-Bypass-Claim-Allowed"
    ] == "false"

    payload = _payloads(bus)[0]
    assert payload["operation"] == "compat_mesh_metrics_read"
    assert payload["stage"] == "mesh_metrics_read"
    assert payload["status"] == "success"
    assert payload["result_summary"]["consciousness_metric_count"] == 1
    assert payload["result_summary"]["mape_k_metric_count"] == 2
    assert payload["result_summary"]["network_metric_count"] == 1
    assert payload["result_summary"]["control_policy_evidence_present"] is True
    assert (
        payload["result_summary"][
            "compat_lifecycle_read_claim_boundary_headers_present"
        ]
        is True
    )
    assert payload["result_summary"]["claim_surface"] == (
        "maas_compat.lifecycle.metrics"
    )
    assert payload["result_summary"]["mesh_lifecycle_claim_gate_present"] is False
    assert payload["result_summary"]["mesh_metrics_claim_gate_present"] is True
    assert payload["result_summary"]["cross_plane_claim_gate_present"] is True
    assert payload["result_summary"]["dataplane_delivery_claim_allowed"] is False
    assert payload["result_summary"]["external_dpi_bypass_claim_allowed"] is False

    serialized = json.dumps(_payloads(bus), sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (owner_id, mesh_id, secret_metric_value):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_compat_mesh_status_denial_publishes_redacted_lifecycle_read_evidence(
    monkeypatch,
    tmp_path,
):
    actor_id = "actor-secret-compat-status-denied"
    mesh_id = "mesh-secret-compat-status-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    async def _status_denied(*, mesh_id, user):
        raise HTTPException(status_code=404, detail=f"Mesh {mesh_id} not found")

    monkeypatch.setattr(compat_mod.modular_mesh, "get_mesh_status", _status_denied)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            compat_mod.get_mesh_status_alias(
                mesh_id,
                request,
                current_user=SimpleNamespace(id=actor_id, role="admin"),
            )
        )

    assert exc.value.status_code == 404
    payload = _payloads(bus)[0]
    assert payload["operation"] == "compat_mesh_status_read"
    assert payload["stage"] == "access_denied"
    assert payload["status"] == "denied"
    assert payload["mesh_id_hash"] == compat_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == compat_mod._redacted_sha256_prefix(actor_id)
    assert payload["owner_id_hash"] is None
    assert payload["reason"] == "http_404"

    serialized = json.dumps(_payloads(bus), sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (actor_id, mesh_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log
