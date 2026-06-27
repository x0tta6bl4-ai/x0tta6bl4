"""Unit tests for heartbeat-driven marketplace escrow EventBus evidence."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.api import maas_nodes as nodes_mod
from src.coordination.events import EventBus, EventType


def _hash(value: object) -> str:
    return hashlib.sha256(str(value).strip().encode("utf-8")).hexdigest()[:16]


def test_analytics_telemetry_export_passes_eventbus_context_to_helper(
    tmp_path,
    monkeypatch,
):
    bus = EventBus(project_root=str(tmp_path))
    request = SimpleNamespace(
        state=SimpleNamespace(event_bus=bus, event_project_root=str(tmp_path))
    )
    captured = {}

    def fake_set_telemetry(node_id, payload, **kwargs):
        captured["node_id"] = node_id
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    monkeypatch.setattr(nodes_mod, "_set_external_telemetry", fake_set_telemetry)

    result = nodes_mod._export_analytics_telemetry(
        "node-export-secret",
        {"mesh_id": "mesh-export-secret", "status": "healthy"},
        request=request,
    )

    assert result is True
    assert captured["node_id"] == "node-export-secret"
    assert captured["payload"]["mesh_id"] == "mesh-export-secret"
    assert captured["kwargs"]["event_bus"] is bus
    assert captured["kwargs"]["event_project_root"] == str(tmp_path)
    assert captured["kwargs"]["mesh_id"] == "mesh-export-secret"


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDb:
    def __init__(self, *, node, listing, escrow):
        self.node = node
        self.listing = listing
        self.escrow = escrow
        self.commits = 0

    def query(self, model):
        if model is nodes_mod.MeshNode:
            return _FakeQuery([self.node])
        if model is nodes_mod.MarketplaceListing:
            return _FakeQuery([self.listing])
        if model is nodes_mod.MarketplaceEscrow:
            return _FakeQuery([self.escrow])
        return _FakeQuery([])

    def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_healthy_heartbeat_auto_release_publishes_redacted_eventbus_evidence(
    tmp_path,
    monkeypatch,
):
    node = SimpleNamespace(
        id="node-heartbeat-1",
        mesh_id="mesh-heartbeat-1",
        status="approved",
        last_seen=None,
    )
    listing = SimpleNamespace(
        id="listing-heartbeat-1",
        node_id=node.id,
        status="escrow",
        renter_id="renter-heartbeat-1",
        mesh_id=node.mesh_id,
        currency="X0T",
    )
    escrow = SimpleNamespace(
        id="escrow-heartbeat-1",
        listing_id=listing.id,
        renter_id=listing.renter_id,
        amount_cents=None,
        amount_token=12.5,
        currency="X0T",
        status="held",
        released_at=None,
    )
    db = _FakeDb(node=node, listing=listing, escrow=escrow)
    bus = EventBus(project_root=str(tmp_path))
    request = SimpleNamespace(
        state=SimpleNamespace(event_bus=bus, event_project_root=str(tmp_path))
    )

    monkeypatch.setattr(nodes_mod, "record_audit_log", MagicMock())
    captured = {}

    def fake_set_telemetry(node_id, payload, **kwargs):
        event = kwargs["event_bus"].publish(
            EventType.PIPELINE_STAGE_END,
            "maas-telemetry",
            {
                "operation": "telemetry_snapshot_write",
                "node_id_hash": _hash(node_id),
                "mesh_id_hash": _hash(kwargs["mesh_id"]),
                "raw_identifiers_redacted": True,
            },
        )
        captured["telemetry_event_id"] = event.event_id
        captured["telemetry_payload"] = payload

    monkeypatch.setattr(nodes_mod, "_set_external_telemetry", fake_set_telemetry)

    result = await nodes_mod.node_heartbeat(
        node.mesh_id,
        node.id,
        nodes_mod.HeartbeatRequest(status="healthy"),
        request=request,
        db=db,
    )

    assert result["status"] == "ok"
    assert result["escrow_released"] == escrow.id
    assert result["telemetry_exported"] is True
    assert db.commits == 1
    assert escrow.status == "released"
    assert escrow.released_at is not None
    assert listing.status == "rented"

    events = bus.get_event_history(
        event_type=EventType.MARKETPLACE_ESCROW_RELEASED,
        source_agent="maas-nodes-heartbeat",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["operation"] == "marketplace_escrow_lifecycle"
    assert payload["service_name"] == "maas-nodes-heartbeat"
    assert payload["source_alias"] == "maas-nodes-heartbeat"
    assert payload["layer"] == "api_mesh_to_commerce"
    assert payload["transition"] == "released"
    assert payload["status"] == "released"
    assert payload["reason"] == "heartbeat_healthy_auto_release"
    assert payload["settlement_evidence"]["decision_basis"] == (
        "healthy_heartbeat_auto_release"
    )
    assert payload["settlement_evidence"]["source_quality"] == (
        "heartbeat_api_plus_telemetry_eventbus_link"
    )
    assert payload["settlement_evidence"]["dataplane_confirmed"] is False
    assert payload["settlement_evidence"]["threshold_met"] is True
    assert payload["settlement_evidence"]["telemetry_evidence"]["event_ids"] == [
        captured["telemetry_event_id"]
    ]
    assert payload["settlement_evidence"]["telemetry_evidence"]["source_agents"] == [
        "maas-telemetry"
    ]
    assert payload["settlement_evidence"]["telemetry_evidence"][
        "payloads_redacted"
    ] is True
    assert payload["escrow_id_hash"] == _hash(escrow.id)
    assert payload["listing_id_hash"] == _hash(listing.id)
    assert payload["renter_id_hash"] == _hash(listing.renter_id)
    assert payload["actor_id_hash"] == _hash(node.id)
    assert payload["node_id_hash"] == _hash(node.id)
    assert payload["mesh_id_hash"] == _hash(node.mesh_id)
    assert payload["amount_token"] == 12.5
    assert payload["raw_identifiers_redacted"] is True
    assert payload["identity_fields_present"]["node_id"] is True

    serialized = json.dumps(payload, sort_keys=True)
    for raw_value in (escrow.id, listing.id, listing.renter_id, node.id, node.mesh_id):
        assert raw_value not in serialized

    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    assert events[0].event_id in raw_log
    for raw_value in (escrow.id, listing.id, listing.renter_id, node.id, node.mesh_id):
        assert raw_value not in raw_log


@pytest.mark.asyncio
async def test_healthy_heartbeat_without_escrow_publishes_redacted_trace_evidence(
    tmp_path,
    monkeypatch,
):
    node = SimpleNamespace(
        id="node-ordinary-heartbeat",
        mesh_id="mesh-ordinary-heartbeat",
        status="approved",
        last_seen=None,
    )
    db = _FakeDb(node=node, listing=None, escrow=None)
    bus = EventBus(project_root=str(tmp_path))
    request = SimpleNamespace(
        state=SimpleNamespace(event_bus=bus, event_project_root=str(tmp_path))
    )

    def fake_set_telemetry(node_id, payload, **kwargs):
        kwargs["event_bus"].publish(
            EventType.PIPELINE_STAGE_END,
            "maas-telemetry",
            {
                "operation": "telemetry_snapshot_write",
                "node_id_hash": _hash(node_id),
                "mesh_id_hash": _hash(kwargs["mesh_id"]),
                "raw_identifiers_redacted": True,
            },
        )

    monkeypatch.setattr(nodes_mod, "_set_external_telemetry", fake_set_telemetry)

    result = await nodes_mod.node_heartbeat(
        node.mesh_id,
        node.id,
        nodes_mod.HeartbeatRequest(
            status="healthy",
            latency_ms=20.5,
            custom_metrics={"secret_metric": "secret-value", "load": 0.7},
        ),
        request=request,
        db=db,
    )

    assert result["status"] == "ok"
    assert result["escrow_released"] is None
    assert result["telemetry_exported"] is True
    assert db.commits == 1

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="maas-nodes-heartbeat",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["operation"] == "node_heartbeat"
    assert payload["service_name"] == "maas-nodes-heartbeat"
    assert payload["layer"] == "api_mesh_to_commerce"
    assert payload["status"] == "accepted"
    assert payload["read_only"] is False
    assert payload["heartbeat_summary"]["db_node_found"] is True
    assert payload["heartbeat_summary"]["node_approved"] is True
    assert payload["heartbeat_summary"]["db_committed"] is True
    assert payload["heartbeat_summary"]["requested_status"] == "healthy"
    assert payload["heartbeat_summary"]["custom_metrics_count"] == 2
    assert payload["heartbeat_summary"]["custom_metrics_numeric_count"] == 1
    assert payload["telemetry_summary"]["telemetry_exported"] is True
    assert payload["telemetry_summary"]["source_agents"] == ["maas-telemetry"]
    assert payload["telemetry_summary"]["events_total"] == 1
    assert payload["settlement_summary"]["escrow_release_attempted"] is True
    assert payload["settlement_summary"]["escrow_released"] is False
    assert payload["settlement_summary"]["marketplace_event_id"] is None
    assert payload["raw_identifiers_redacted"] is True
    assert "live dataplane reachability" in payload["claim_boundary"]

    serialized = json.dumps(payload, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        node.id,
        node.mesh_id,
        "secret_metric",
        "secret-value",
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
