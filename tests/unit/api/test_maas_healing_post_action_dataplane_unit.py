"""Unit tests for MaaS heal post-action dataplane evidence surfacing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api.maas.nodes import healing as healing_mod
from src.coordination.events import EventBus, EventType


@pytest.mark.asyncio
async def test_trigger_node_healing_passes_redacted_probe_target_and_surfaces_gate(
    monkeypatch,
    tmp_path,
) -> None:
    event_bus = EventBus(project_root=str(tmp_path))
    manager_calls = []
    node = SimpleNamespace(
        id="node-secret-1",
        mesh_id="mesh-1",
        ip_address="127.0.0.1",
    )

    class FakeQuery:
        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return node

    class FakeDB:
        def query(self, _model):
            return FakeQuery()

    class FakeVerificationMode:
        FULL = "full"

    class FakeMeshNetworkManager:
        def __init__(self, **kwargs):
            manager_calls.append(kwargs)
            self.event_bus = kwargs["event_bus"]

        async def trigger_aggressive_healing(
            self,
            *,
            auto_restore_nodes: bool,
            verification_mode: str,
            post_action_dataplane_probe_target: str | None = None,
        ) -> int:
            assert auto_restore_nodes is True
            assert verification_mode == "full"
            assert post_action_dataplane_probe_target == "127.0.0.1"
            evidence = {
                "source_agents": ["real-network-adapter"],
                "event_ids": ["evt-probe-1"],
                "events_total": 1,
                "event_ids_count": 1,
                "redacted": True,
            }
            claim_gate = {
                "schema": "x0tta6bl4.mesh_network_manager.healing_claim_gate.v1",
                "decision": "RESTORED_DATAPLANE_CLAIM_ALLOWED",
                "post_action_probe_enabled": True,
                "post_action_probe_target_present": True,
                "post_action_probe_attempted": True,
                "post_action_dataplane_revalidated": True,
                "dataplane_confirmed": True,
                "restored_dataplane_claim_allowed": True,
                "traffic_delivery_claim_allowed": False,
                "customer_traffic_claim_allowed": False,
                "external_reachability_claim_allowed": False,
                "production_slo_claim_allowed": False,
                "production_readiness_claim_allowed": False,
                "requires_post_action_dataplane_revalidation": True,
                "blockers": [],
                "evidence": evidence,
                "claim_boundary": "bounded local dataplane proof only",
                "redacted": True,
            }
            self.event_bus.publish(
                EventType.PIPELINE_STAGE_END,
                "mesh-network-manager",
                {
                    "operation": "trigger_aggressive_healing",
                    "status": "success",
                    "post_action_dataplane_revalidation": {
                        "probe_enabled": True,
                        "probe_target_present": True,
                        "probe_attempted": True,
                        "dataplane_confirmed": True,
                        "post_action_dataplane_revalidated": True,
                        "restored_dataplane_claim_allowed": True,
                        "claim_gate": claim_gate,
                        "evidence": evidence,
                        "claim_boundary": "bounded local dataplane proof only",
                        "redacted": True,
                    },
                    "claim_gate": claim_gate,
                    "payloads_redacted": True,
                },
            )
            return 1

    monkeypatch.setattr(
        healing_mod,
        "ensure_mesh_visibility_with_permission",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(healing_mod, "MESH_HEALING_AVAILABLE", True)
    monkeypatch.setattr(healing_mod, "VerificationMode", FakeVerificationMode)
    monkeypatch.setattr(healing_mod, "MeshNetworkManager", FakeMeshNetworkManager)

    result = await healing_mod.trigger_node_healing(
        mesh_id="mesh-1",
        node_id="node-secret-1",
        db=FakeDB(),
        current_user=SimpleNamespace(id="user-1"),
        request=SimpleNamespace(
            state=SimpleNamespace(
                event_bus=event_bus,
                event_project_root=str(tmp_path),
            )
        ),
    )

    payload_text = str(result)
    assert manager_calls[0]["event_bus"] is event_bus
    assert result["status"] == "healed"
    assert result["dataplane_confirmed"] is True
    assert result["post_action_dataplane_revalidated"] is True
    assert result["restored_dataplane_claim_allowed"] is True
    assert result["post_action_dataplane_revalidation"]["status"] == "success"
    assert result["post_action_dataplane_revalidation"][
        "traffic_delivery_claim_allowed"
    ] is False
    assert result["post_action_dataplane_revalidation"][
        "production_readiness_claim_allowed"
    ] is False
    assert result["control_plane_evidence"]["operations"] == [
        "trigger_aggressive_healing"
    ]
    assert "127.0.0.1" not in payload_text


def test_post_action_revalidation_does_not_overclaim_when_gate_denies(tmp_path) -> None:
    event_bus = EventBus(project_root=str(tmp_path))
    event = event_bus.publish(
        EventType.PIPELINE_STAGE_END,
        "mesh-network-manager",
        {
            "operation": "trigger_aggressive_healing",
            "status": "success",
            "post_action_dataplane_revalidation": {
                "probe_enabled": True,
                "probe_target_present": True,
                "probe_attempted": True,
                "dataplane_confirmed": True,
                "post_action_dataplane_revalidated": True,
                "restored_dataplane_claim_allowed": True,
                "claim_gate": {
                    "schema": "x0tta6bl4.mesh_network_manager.healing_claim_gate.v1",
                    "decision": "LOCAL_HEALING_LIFECYCLE_ONLY",
                    "post_action_probe_enabled": True,
                    "post_action_probe_target_present": True,
                    "post_action_probe_attempted": True,
                    "post_action_dataplane_revalidated": False,
                    "dataplane_confirmed": True,
                    "restored_dataplane_claim_allowed": False,
                    "traffic_delivery_claim_allowed": False,
                    "customer_traffic_claim_allowed": False,
                    "external_reachability_claim_allowed": False,
                    "production_slo_claim_allowed": False,
                    "production_readiness_claim_allowed": False,
                    "requires_post_action_dataplane_revalidation": True,
                    "blockers": ["post_action_probe_evidence_missing"],
                    "evidence": {
                        "source_agents": [],
                        "event_ids": [],
                        "events_total": 0,
                        "event_ids_count": 0,
                        "redacted": True,
                    },
                    "claim_boundary": "bounded local dataplane proof only",
                    "redacted": True,
                },
                "evidence": {
                    "source_agents": [],
                    "event_ids": [],
                    "events_total": 0,
                    "event_ids_count": 0,
                    "redacted": True,
                },
                "claim_boundary": "bounded local dataplane proof only",
                "redacted": True,
            },
            "payloads_redacted": True,
        },
    )

    result = healing_mod._mesh_healing_post_action_revalidation(
        healed=1,
        control_plane_evidence={
            "source_agents": ["mesh-network-manager"],
            "event_ids": [event.event_id],
            "events_total": 1,
            "payloads_redacted": True,
        },
        event_bus=event_bus,
    )

    assert result["status"] == "failed"
    assert result["dataplane_confirmed"] is True
    assert result["post_action_dataplane_revalidated"] is False
    assert result["restored_dataplane_claim_allowed"] is False
    assert result["claim_gate"]["restored_dataplane_claim_allowed"] is False
    assert result["claim_gate"]["blockers"] == ["post_action_probe_evidence_missing"]
