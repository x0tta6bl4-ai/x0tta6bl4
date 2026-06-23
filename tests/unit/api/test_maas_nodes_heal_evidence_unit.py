"""Unit tests for MaaS node heal EventBus evidence links."""

from types import SimpleNamespace

import pytest

import src.api.maas_nodes as nodes_mod
from src.coordination.events import EventBus, EventType


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeDb:
    def __init__(self, node):
        self.node = node

    def query(self, model):
        if model is nodes_mod.MeshNode:
            return _FakeQuery([self.node])
        return _FakeQuery([])


@pytest.mark.asyncio
async def test_heal_node_returns_redacted_mesh_manager_evidence_links(
    monkeypatch,
    tmp_path,
):
    bus = EventBus(project_root=str(tmp_path))
    node = SimpleNamespace(
        id="node-heal-secret",
        mesh_id="mesh-heal-secret",
        status="offline",
    )
    db = _FakeDb(node)
    request = SimpleNamespace(
        state=SimpleNamespace(event_bus=bus, event_project_root=str(tmp_path))
    )
    current_user = SimpleNamespace(id="operator-secret", role="operator")
    captured = {}

    class _FakeMeshNetworkManager:
        def __init__(self, **kwargs):
            captured["manager_kwargs"] = kwargs

        async def trigger_aggressive_healing(self, **kwargs):
            captured["healing_kwargs"] = kwargs
            verification_event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "verify_node_state",
                    "status": "success",
                    "duration_ms": 12.345,
                    "identity": {
                        "service_name": "mesh-network-manager",
                        "spiffe_id_configured": False,
                        "did_configured": False,
                        "wallet_address_configured": False,
                        "redacted": True,
                    },
                    "bounded_output": {
                        "raw_node_id_redacted": True,
                        "raw_endpoint_redacted": True,
                        "return_code": None,
                    },
                    "node_id": "node-heal-secret",
                    "node_id_redacted": True,
                },
            )
            bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "trigger_aggressive_healing",
                    "status": "success",
                    "duration_ms": 23.456,
                    "identity": {
                        "service_name": "mesh-network-manager",
                        "spiffe_id_configured": False,
                        "did_configured": False,
                        "wallet_address_configured": False,
                        "redacted": True,
                    },
                    "downstream_evidence": {
                        "event_ids": [verification_event.event_id],
                        "redacted": True,
                    },
                },
            )
            return 1

    monkeypatch.setattr(
        nodes_mod,
        "_ensure_mesh_visibility_with_permission",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(nodes_mod, "MESH_HEALING_AVAILABLE", True)
    monkeypatch.setattr(
        nodes_mod,
        "VerificationMode",
        SimpleNamespace(FULL="full"),
    )
    monkeypatch.setattr(nodes_mod, "MeshNetworkManager", _FakeMeshNetworkManager)

    result = await nodes_mod.heal_node(
        node.mesh_id,
        node.id,
        current_user=current_user,
        db=db,
        request=request,
    )

    evidence = result["control_plane_evidence"]
    revalidation = result["post_action_dataplane_revalidation"]
    evidence_text = str(evidence)
    revalidation_text = str(revalidation)

    assert result["status"] == "healed"
    assert result["node_id"] == node.id
    assert result["components_healed"] == 1
    assert result["healing_claim"] == "local_control_action_applied"
    assert result["dataplane_confirmed"] is False
    assert result["restored_dataplane_claim_allowed"] is False
    assert "must not be read as restored live dataplane behavior" in result["claim_boundary"]
    assert captured["manager_kwargs"]["event_bus"] is bus
    assert captured["manager_kwargs"]["event_project_root"] == str(tmp_path)
    assert captured["healing_kwargs"] == {
        "auto_restore_nodes": True,
        "verification_mode": "full",
    }
    assert evidence["event_bus_observed"] is True
    assert evidence["events_total"] == 2
    assert evidence["source_agents"] == ["mesh-network-manager"]
    assert evidence["operations"] == [
        "trigger_aggressive_healing",
        "verify_node_state",
    ]
    assert evidence["statuses"] == ["success"]
    assert evidence["terminal_event_id"] in evidence["event_ids"]
    assert evidence["verification_events_total"] == 1
    assert evidence["verification_event_ids"][0] in evidence["event_ids"]
    assert evidence["service_identity_events_total"] == 2
    assert evidence["duration_events_total"] == 2
    assert evidence["bounded_output_events_total"] == 1
    assert evidence["return_code_events_total"] == 1
    assert evidence["dataplane_confirmed"] is False
    assert evidence["post_action_dataplane_revalidated"] is False
    assert evidence["raw_identifiers_redacted"] is True
    assert evidence["payloads_redacted"] is True
    assert revalidation == {
        "required_for_restored_dataplane_claim": True,
        "attempted": False,
        "post_action_dataplane_revalidated": False,
        "dataplane_confirmed": False,
        "restored_dataplane_claim_allowed": False,
        "reason": "no_bounded_post_action_dataplane_probe_attached",
        "claim_gate": {
            "required_for_restored_dataplane_claim": True,
            "restored_dataplane_claim_allowed": False,
            "blockers": ["no_bounded_post_action_dataplane_probe_attached"],
            "required_evidence": {
                "bounded_post_action_dataplane_probe": True,
                "dataplane_confirmed": True,
                "redacted_evidence": True,
                "event_ids_count_min": 1,
            },
            "observed_evidence": {
                "bounded_post_action_dataplane_probe": False,
                "dataplane_confirmed": False,
                "control_plane_event_ids_total": 2,
            },
            "claim_boundary": result["claim_boundary"],
            "redacted": True,
        },
        "source_agents": [],
        "event_ids": [],
        "events_total": 0,
        "control_plane_event_ids_total": 2,
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": result["claim_boundary"],
    }
    assert node.id not in evidence_text
    assert node.mesh_id not in evidence_text
    assert current_user.id not in evidence_text
    assert node.id not in revalidation_text
    assert node.mesh_id not in revalidation_text
    assert current_user.id not in revalidation_text
