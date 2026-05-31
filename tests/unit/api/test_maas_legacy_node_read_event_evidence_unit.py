"""Unit tests for legacy MaaS node read EventBus evidence."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src.api.maas_legacy as legacy_mod
from src.coordination.events import EventBus, EventType


class _Provisioner:
    def __init__(self, instances):
        self.instances = {instance.mesh_id: instance for instance in instances}

    def get(self, mesh_id):
        return self.instances.get(mesh_id)


class _Mesh:
    def __init__(self, *, mesh_id: str, owner_id: str):
        self.mesh_id = mesh_id
        self.owner_id = owner_id
        self.join_token = "node-read-token-secret"
        self.join_token_expires_at = datetime.utcnow() + timedelta(hours=1)
        self.node_instances = {}


def _request(bus: EventBus):
    return SimpleNamespace(state=SimpleNamespace(event_bus=bus))


def _payloads(bus: EventBus):
    return [
        event.data
        for event in bus.get_event_history(
            event_type=EventType.PIPELINE_STAGE_END,
            source_agent="maas-legacy-node-read",
            limit=10,
        )
    ]


def _install_state(monkeypatch, instance: _Mesh):
    monkeypatch.setattr(legacy_mod, "mesh_provisioner", _Provisioner([instance]))
    monkeypatch.setattr(legacy_mod, "_pending_nodes", {})
    monkeypatch.setattr(legacy_mod, "_revoked_nodes", {})


def test_legacy_pending_node_list_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-pending-read"
    owner_id = "owner-secret-pending-read"
    node_id = "node-secret-pending-read"
    tag_value = "pending-tag-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    _install_state(monkeypatch, instance)
    legacy_mod._pending_nodes[mesh_id] = {
        node_id: {
            "device_class": "robot",
            "tags": [tag_value],
        }
    }

    result = legacy_mod.list_pending_nodes(
        mesh_id,
        SimpleNamespace(id=owner_id, role="admin"),
        request=request,
    )

    assert result["pending"] == [node_id]
    assert result["nodes"][0]["tags"] == [tag_value]

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_pending_node_list_read"
    assert payload["service_name"] == "maas-legacy-node-read"
    assert payload["source_alias"] == "maas-legacy-node-read"
    assert payload["layer"] == "api_legacy_node_observed_state"
    assert payload["stage"] == "pending_node_list_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["node_status_filter"] == "pending"
    assert payload["result_summary"]["node_count"] == 1
    assert payload["result_summary"]["by_status"] == {"pending": 1}
    assert payload["result_summary"]["by_device_class"] == {"robot": 1}
    assert payload["result_summary"]["tag_entry_count"] == 1
    assert payload["read_only"] is True
    assert payload["control_action"] is False
    assert payload["raw_identifiers_redacted"] is True

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id, node_id, tag_value):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_pending_node_list_role_denial_publishes_redacted_evidence(
    tmp_path,
):
    mesh_id = "mesh-secret-pending-role-denied"
    owner_id = "owner-secret-pending-role-denied"
    bus = EventBus(str(tmp_path))
    request = _request(bus)

    with pytest.raises(HTTPException) as exc:
        legacy_mod.list_pending_nodes(
            mesh_id,
            SimpleNamespace(id=owner_id, role="user"),
            request=request,
        )

    assert exc.value.status_code == 403

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_pending_node_list_read"
    assert payload["stage"] == "role_denied"
    assert payload["status"] == "denied"
    assert payload["reason"] == "operator_role_required"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["actor_user_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (mesh_id, owner_id):
        assert raw_value not in serialized
        assert raw_value not in raw_log


def test_legacy_all_nodes_publishes_redacted_read_evidence(
    monkeypatch,
    tmp_path,
):
    mesh_id = "mesh-secret-all-nodes"
    owner_id = "owner-secret-all-nodes"
    approved_node = "node-secret-approved"
    revoked_node = "node-secret-revoked"
    pending_node = "node-secret-pending"
    approved_tag = "approved-tag-secret"
    pending_tag = "pending-tag-secret"
    bus = EventBus(str(tmp_path))
    request = _request(bus)
    instance = _Mesh(mesh_id=mesh_id, owner_id=owner_id)
    instance.node_instances = {
        approved_node: {
            "status": "healthy",
            "device_class": "gateway",
            "tags": [approved_tag],
        },
        revoked_node: {
            "status": "revoked",
            "device_class": "sensor",
            "tags": [],
        },
    }
    _install_state(monkeypatch, instance)
    legacy_mod._pending_nodes[mesh_id] = {
        pending_node: {
            "device_class": "robot",
            "tags": [pending_tag],
        }
    }

    result = legacy_mod.list_all_nodes(
        mesh_id,
        current_user=SimpleNamespace(id=owner_id, role="admin"),
        request=request,
    )

    assert {node["node_id"] for node in result["nodes"]} == {
        approved_node,
        revoked_node,
        pending_node,
    }
    assert result["by_status"] == {"approved": 1, "revoked": 1, "pending": 1}

    payloads = _payloads(bus)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["operation"] == "legacy_node_list_read"
    assert payload["stage"] == "node_list_read"
    assert payload["status"] == "success"
    assert payload["mesh_id_hash"] == legacy_mod._redacted_sha256_prefix(mesh_id)
    assert payload["owner_id_hash"] == legacy_mod._redacted_sha256_prefix(owner_id)
    assert payload["result_summary"]["node_count"] == 3
    assert payload["result_summary"]["by_status"] == {
        "approved": 1,
        "pending": 1,
        "revoked": 1,
    }
    assert payload["result_summary"]["tag_entry_count"] == 2

    serialized = json.dumps(payloads, sort_keys=True)
    raw_log = (tmp_path / ".agent_coordination" / "events.log").read_text(
        encoding="utf-8"
    )
    for raw_value in (
        mesh_id,
        owner_id,
        approved_node,
        revoked_node,
        pending_node,
        approved_tag,
        pending_tag,
    ):
        assert raw_value not in serialized
        assert raw_value not in raw_log
