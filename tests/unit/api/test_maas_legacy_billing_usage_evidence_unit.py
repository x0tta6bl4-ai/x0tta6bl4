import asyncio
import json
from types import SimpleNamespace

import pytest

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


class _DummyRequest:
    def __init__(self, event_bus: EventBus):
        self.state = SimpleNamespace(event_bus=event_bus)


class _UsageService:
    def __init__(self, owner_id: str, mesh_id: str, node_id: str):
        self.owner_id = owner_id
        self.mesh_id = mesh_id
        self.node_id = node_id

    def get_mesh_usage(self, _instance):
        return {
            "mesh_id": self.mesh_id,
            "mesh_name": "secret-mesh-name",
            "status": "active",
            "active_nodes": 1,
            "total_node_hours": 1.25,
            "billing_period_start": "2026-05-29T00:00:00",
            "billing_period_end": "2026-05-29T01:15:00",
            "nodes": [{"node_id": self.node_id, "hours": 1.25}],
        }

    def get_account_usage(self, owner_id: str):
        assert owner_id == self.owner_id
        return {
            "owner_id": owner_id,
            "total_node_hours": 1.25,
            "mesh_count": 1,
            "meshes": [
                {
                    "mesh_id": self.mesh_id,
                    "mesh_name": "secret-mesh-name",
                    "status": "active",
                    "active_nodes": 1,
                    "total_node_hours": 1.25,
                }
            ],
            "generated_at": "2026-05-29T01:15:00",
        }


def _event_payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-legacy-billing-usage",
            limit=10,
        )
    ]


def test_legacy_billing_usage_reads_publish_redacted_observed_state(
    monkeypatch,
    tmp_path,
):
    owner_id = "owner-secret-123"
    mesh_id = "mesh-secret-456"
    node_id = "node-secret-789"
    bus = EventBus(str(tmp_path))
    request = _DummyRequest(bus)
    current_user = SimpleNamespace(id=owner_id)
    instance = SimpleNamespace(mesh_id=mesh_id, owner_id=owner_id)
    usage_service = _UsageService(owner_id, mesh_id, node_id)

    monkeypatch.setattr(
        legacy_mod,
        "_get_mesh_or_404",
        lambda raw_mesh_id, raw_owner_id: instance,
    )
    monkeypatch.setattr(legacy_mod, "usage_metering_service", usage_service)

    mesh_usage = asyncio.run(
        legacy_mod.legacy_mesh_usage(
            mesh_id,
            request,
            current_user=current_user,
        )
    )
    account_usage = asyncio.run(
        legacy_mod.legacy_account_usage(
            request,
            current_user=current_user,
        )
    )

    assert mesh_usage["mesh_id"] == mesh_id
    assert mesh_usage["nodes"][0]["node_id"] == node_id
    assert account_usage["owner_id"] == owner_id
    assert account_usage["meshes"][0]["mesh_id"] == mesh_id

    payloads = _event_payloads(bus)
    assert len(payloads) == 2
    assert [payload["scope"] for payload in payloads] == ["mesh", "account"]
    assert all(payload["component"] == "api.maas_legacy" for payload in payloads)
    assert all(payload["operation"] == "billing_usage_read" for payload in payloads)
    assert all(payload["service_name"] == "maas-billing" for payload in payloads)
    assert all(
        payload["source_alias"] == "maas-legacy-billing-usage"
        for payload in payloads
    )
    assert all(payload["layer"] == "billing_usage_observed_state" for payload in payloads)
    assert all(payload["observed_state"] is True for payload in payloads)
    assert all(payload["read_only"] is True for payload in payloads)
    assert all(payload["safe_actuator"] is False for payload in payloads)
    assert payloads[0]["usage_summary"]["active_nodes"] == 1
    assert payloads[0]["usage_summary"]["node_entries"] == 1
    assert payloads[1]["usage_summary"]["mesh_count"] == 1
    assert payloads[1]["usage_summary"]["mesh_entries"] == 1

    serialized_payloads = json.dumps(payloads, sort_keys=True)
    assert owner_id not in serialized_payloads
    assert mesh_id not in serialized_payloads
    assert node_id not in serialized_payloads
    assert "secret-mesh-name" not in serialized_payloads
