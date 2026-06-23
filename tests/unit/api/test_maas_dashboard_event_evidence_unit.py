"""Unit tests for MaaS dashboard EventBus evidence."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_dashboard as dashboard_mod
from src.coordination.events import EventBus, EventType


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus, source_agent: str):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent=source_agent,
            limit=10,
        )
    ]


class _Query:
    def __init__(self, *, all_results=None, first_result=None, count_result=0):
        self._all_results = list(all_results or [])
        self._first_result = first_result
        self._count_result = count_result

    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def all(self):
        return list(self._all_results)

    def first(self):
        return self._first_result

    def count(self):
        return self._count_result


class _DashboardDb:
    def __init__(
        self,
        *,
        meshes=None,
        mesh=None,
        nodes=None,
        rentals=None,
        listings=None,
        logs=None,
        invoices=None,
        node_bucket_count=0,
    ):
        self.meshes = list(meshes or [])
        self.mesh = mesh
        self.nodes = list(nodes or [])
        self.rentals = list(rentals or [])
        self.listings = list(listings or [])
        self.logs = list(logs or [])
        self.invoices = list(invoices or [])
        self.node_bucket_count = node_bucket_count

    def query(self, model, *_args, **_kwargs):
        if model is dashboard_mod.MeshInstance:
            return _Query(
                all_results=self.meshes,
                first_result=self.mesh if self.mesh is not None else (
                    self.meshes[0] if self.meshes else None
                ),
            )
        if model is dashboard_mod.MeshNode:
            return _Query(all_results=self.nodes, count_result=self.node_bucket_count)
        if model is dashboard_mod.MarketplaceListing:
            # Dashboard calls this twice with different filters; bounded metadata only
            # needs counts, so returning the same list is enough for this unit test.
            return _Query(all_results=self.rentals or self.listings)
        if model is dashboard_mod.AuditLog:
            return _Query(all_results=self.logs)
        if model is dashboard_mod.Invoice:
            return _Query(all_results=self.invoices)
        return _Query()


def test_dashboard_summary_publishes_redacted_observed_state(
    monkeypatch,
    tmp_path,
):
    email = "dashboard-summary-secret@example.test"
    user_id = "dashboard-summary-user-secret"
    mesh_id = "dashboard-summary-mesh-secret"
    node_id = "dashboard-summary-node-secret"
    hardware_id = "dashboard-summary-hardware-secret"
    invoice_id = "dashboard-summary-invoice-secret"
    audit_id = "dashboard-summary-audit-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="user", plan="starter")
    mesh = SimpleNamespace(
        id=mesh_id,
        name="dashboard-summary-mesh-name-secret",
        status="active",
        created_at=datetime(2026, 5, 30, 10, 0, 0),
    )
    node = SimpleNamespace(
        id=node_id,
        mesh_id=mesh_id,
        status="approved",
        device_class="gateway",
        hardware_id=hardware_id,
        enclave_enabled=True,
        last_seen=datetime.utcnow() - timedelta(minutes=1),
    )
    invoice = SimpleNamespace(
        id=invoice_id,
        total_amount=2500,
        currency="USD",
        issued_at=datetime(2026, 5, 30, 11, 0, 0),
    )
    audit = SimpleNamespace(
        id=audit_id,
        action="PRIVATE_DASHBOARD_ACTION",
        method="POST",
        path="/private-dashboard-path",
        status_code=200,
        created_at=datetime(2026, 5, 30, 12, 0, 0),
    )
    db = _DashboardDb(
        meshes=[mesh],
        nodes=[node],
        logs=[audit],
        invoices=[invoice],
        node_bucket_count=1,
    )

    monkeypatch.setattr(
        dashboard_mod,
        "_dashboard_traffic_by_bucket",
        lambda db, mesh_ids, owner_id: [0.0] * 24,
    )

    result = asyncio.run(
        dashboard_mod.get_dashboard_summary(request, current_user=user, db=db)
    )

    assert result["stats"]["total_meshes"] == 1
    assert result["stats"]["total_nodes"] == 1
    payloads = _payloads(bus, "maas-dashboard-summary-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_dashboard_summary_read"
    assert payload["service_name"] == "maas-dashboard-summary-read"
    assert payload["layer"] == "api_dashboard_summary_observed_state"
    assert payload["actor_user_id_hash"] == dashboard_mod._redacted_sha256_prefix(user_id)
    assert payload["actor_email_hash"] == dashboard_mod._redacted_sha256_prefix(
        email.lower()
    )
    assert payload["meshes_count"] == 1
    assert payload["total_nodes"] == 1
    assert payload["pending_invoices_count"] == 1
    assert payload["audit_logs_count"] == 1
    assert payload["security_stats"]["HARDWARE_ROOTED"] == 1
    assert payload["health_stats"]["healthy"] == 1
    assert payload["observed_state"] is True
    assert payload["read_only"] is True
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        user_id,
        mesh_id,
        node_id,
        hardware_id,
        invoice_id,
        audit_id,
        "dashboard-summary-mesh-name-secret",
        "PRIVATE_DASHBOARD_ACTION",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_dashboard_analytics_uses_service_and_publishes_redacted_evidence(
    monkeypatch,
    tmp_path,
):
    email = "dashboard-analytics-secret@example.test"
    user_id = "dashboard-analytics-user-secret"
    mesh_id = "dashboard-analytics-mesh-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="user", plan="starter")
    calls = []

    class _Analytics:
        def __init__(self, db, redis_client):
            calls.append(("init", db, redis_client))

        def get_mesh_timeseries(self, mesh_id_arg, owner_id_arg, time_range):
            calls.append((mesh_id_arg, owner_id_arg, time_range))
            return {
                "mesh_id": mesh_id_arg,
                "range": time_range,
                "nodes_total": 2,
                "data": [{"timestamp": "2026-05-30T12:00:00", "health": 100.0}],
            }

    monkeypatch.setattr(dashboard_mod, "MaaSAnalyticsService", _Analytics)

    result = asyncio.run(
        dashboard_mod.get_mesh_analytics(
            mesh_id,
            request,
            current_user=user,
            db=SimpleNamespace(name="dashboard-db-secret"),
        )
    )

    assert result["mesh_id"] == mesh_id
    assert calls[-1] == (mesh_id, user_id, "24h")
    payloads = _payloads(bus, "maas-dashboard-analytics-read")
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "maas_dashboard_analytics_read"
    assert payload["service_name"] == "maas-dashboard-analytics-read"
    assert payload["layer"] == "api_dashboard_analytics_observed_state"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == dashboard_mod._redacted_sha256_prefix(mesh_id)
    assert payload["analytics_service_used"] is True
    assert payload["points_count"] == 1
    assert payload["nodes_total"] == 2

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (email, user_id, mesh_id, "dashboard-db-secret"):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_dashboard_node_read_success_and_404_publish_redacted_evidence(tmp_path):
    email = "dashboard-node-secret@example.test"
    user_id = "dashboard-node-user-secret"
    mesh_id = "dashboard-node-mesh-secret"
    node_id = "dashboard-node-node-secret"
    hardware_id = "dashboard-node-hardware-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    user = SimpleNamespace(id=user_id, email=email, role="user", plan="starter")
    mesh = SimpleNamespace(id=mesh_id, name="dashboard-node-mesh-name-secret")
    node = SimpleNamespace(
        id=node_id,
        mesh_id=mesh_id,
        status="approved",
        device_class="gateway",
        hardware_id=hardware_id,
        enclave_enabled=True,
        last_seen=datetime.utcnow() - timedelta(minutes=45),
    )

    result = asyncio.run(
        dashboard_mod.get_mesh_nodes_summary(
            mesh_id,
            request,
            current_user=user,
            db=_DashboardDb(mesh=mesh, nodes=[node]),
        )
    )

    assert result["count"] == 1
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            dashboard_mod.get_mesh_nodes_summary(
                "missing-dashboard-mesh-secret",
                request,
                current_user=user,
                db=_DashboardDb(mesh=None, nodes=[]),
            )
        )
    assert exc.value.status_code == 404

    payloads = _payloads(bus, "maas-dashboard-node-read")
    assert len(payloads) == 2
    success_payload = payloads[0]
    denial_payload = payloads[1]
    assert success_payload["operation"] == "maas_dashboard_nodes_read"
    assert success_payload["service_name"] == "maas-dashboard-node-read"
    assert success_payload["layer"] == "api_dashboard_node_observed_state"
    assert success_payload["status"] == "success"
    assert success_payload["mesh_found"] is True
    assert success_payload["nodes_count"] == 1
    assert success_payload["attestation_counts"]["HARDWARE_ROOTED"] == 1
    assert success_payload["health_counts"]["offline"] == 1
    assert success_payload["hardware_id_present_count"] == 1
    assert denial_payload["status"] == "denied"
    assert denial_payload["mesh_found"] is False
    assert denial_payload["http_status_code"] == 404

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        email,
        user_id,
        mesh_id,
        node_id,
        hardware_id,
        "dashboard-node-mesh-name-secret",
        "missing-dashboard-mesh-secret",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
