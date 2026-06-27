"""API slice for the MaaS autonomous mesh control loop."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.maas.nodes import healing as healing_mod
from src.api.maas.nodes import hash_node_runtime_credential
from src.api.maas_security import ApiKeyManager
from src.coordination.events import EventBus, EventType
from src.core.app import app
from src.database import Base, MeshInstance, MeshNode, User, get_db


@pytest.fixture()
def maas_client(tmp_path):
    db_path = tmp_path / "autonomous_mesh_loop.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, testing_session
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)


def _seed_admin_mesh_node(testing_session, *, ip_address: str | None = None):
    api_key = f"maas_test_{uuid.uuid4().hex}"
    user_id = f"usr-{uuid.uuid4().hex[:12]}"
    mesh_id = f"mesh-{uuid.uuid4().hex[:12]}"
    node_id = f"node-{uuid.uuid4().hex[:12]}"
    join_token = f"join-{uuid.uuid4().hex}"
    node_runtime_credential = f"x0tn_test_{node_id}"

    db = testing_session()
    try:
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@test.local",
                password_hash="test-hash",
                api_key=None,
                api_key_hash=ApiKeyManager.hash_key(api_key),
                role="admin",
                plan="enterprise",
            )
        )
        db.add(
            MeshInstance(
                id=mesh_id,
                name="Autonomous Mesh Loop",
                owner_id=user_id,
                plan="enterprise",
                status="active",
                join_token=join_token,
            )
        )
        db.add(
            MeshNode(
                id=node_id,
                mesh_id=mesh_id,
                device_class="edge",
                status="approved",
                ip_address=ip_address,
                runtime_credential_hash=hash_node_runtime_credential(
                    node_runtime_credential
                ),
                runtime_credential_expires_at=datetime.utcnow()
                + timedelta(hours=1),
            )
        )
        db.commit()
    finally:
        db.close()

    return {
        "api_key": api_key,
        "user_id": user_id,
        "mesh_id": mesh_id,
        "node_id": node_id,
        "join_token": join_token,
        "node_runtime_credential": node_runtime_credential,
    }


def test_agent_style_node_registration_uses_mesh_enrollment_token(maas_client):
    client, testing_session = maas_client
    seeded = _seed_admin_mesh_node(testing_session)
    mesh_id = seeded["mesh_id"]
    node_id = f"agent-{uuid.uuid4().hex[:12]}"

    registered = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/register",
        json={
            "node_id": node_id,
            "enrollment_token": seeded["join_token"],
            "device_class": "edge",
        },
    )
    assert registered.status_code == 200, registered.text
    body = registered.json()
    assert body["mesh_id"] == mesh_id
    assert body["node_id"] == node_id
    assert body["status"] == "pending_approval"

    db = testing_session()
    try:
        node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
        assert node is not None
        assert node.mesh_id == mesh_id
        assert node.status == "pending"
    finally:
        db.close()


def test_heartbeat_degrades_node_and_heal_requires_dataplane_revalidation(
    maas_client, monkeypatch
):
    client, testing_session = maas_client
    seeded = _seed_admin_mesh_node(testing_session)
    mesh_id = seeded["mesh_id"]
    node_id = seeded["node_id"]

    heartbeat = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat",
        json={
            "status": "unhealthy",
            "latency_ms": 250.0,
            "traffic_mbps": 0.0,
            "active_connections": 0,
        },
        headers={"X-API-Key": seeded["node_runtime_credential"]},
    )
    assert heartbeat.status_code == 200, heartbeat.text
    assert heartbeat.json()["node_status"] == "degraded"

    db = testing_session()
    try:
        node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
        assert node is not None
        assert node.status == "degraded"
        assert node.last_seen is not None
    finally:
        db.close()

    manager_kwargs = []

    class FakeVerificationMode:
        FULL = "full"

    class FakeMeshNetworkManager:
        def __init__(self, **kwargs):
            manager_kwargs.append(kwargs)

        async def trigger_aggressive_healing(
            self,
            *,
            auto_restore_nodes: bool,
            verification_mode: str,
            post_action_dataplane_probe_target: str | None = None,
        ) -> int:
            assert auto_restore_nodes is True
            assert verification_mode == "full"
            assert post_action_dataplane_probe_target is None
            return 1

    event_id_calls = {"count": 0}
    seen_event_buses = []

    def fake_mesh_manager_event_ids(event_bus):
        seen_event_buses.append(event_bus)
        event_id_calls["count"] += 1
        return [] if event_id_calls["count"] == 1 else ["evt-heal"]

    monkeypatch.setattr(healing_mod, "MESH_HEALING_AVAILABLE", True)
    monkeypatch.setattr(healing_mod, "VerificationMode", FakeVerificationMode)
    monkeypatch.setattr(healing_mod, "MeshNetworkManager", FakeMeshNetworkManager)
    monkeypatch.setattr(
        healing_mod, "_mesh_manager_event_ids", fake_mesh_manager_event_ids
    )

    heal = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heal",
        headers={"X-API-Key": seeded["api_key"]},
    )
    assert heal.status_code == 200, heal.text
    body = heal.json()
    assert body["status"] == "healed"
    assert body["healing_claim"] == "local_control_action_applied"
    assert body["dataplane_confirmed"] is False
    assert body["control_plane_evidence"]["event_ids"] == ["evt-heal"]
    assert body["post_action_dataplane_revalidation"]["status"] == (
        "pending_revalidation"
    )
    assert body["post_action_dataplane_revalidation"]["dataplane_probe_required"] is True
    assert manager_kwargs[0]["event_bus"] is seen_event_buses[0]


def test_heal_surfaces_bounded_dataplane_revalidation_from_eventbus(
    maas_client, monkeypatch, tmp_path
):
    client, testing_session = maas_client
    seeded = _seed_admin_mesh_node(testing_session)
    mesh_id = seeded["mesh_id"]
    node_id = seeded["node_id"]
    event_bus = EventBus(str(tmp_path))
    manager_kwargs = []

    heartbeat = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat",
        json={
            "status": "healthy",
            "dataplane_probe_target": "127.0.0.1",
            "latency_ms": 1.0,
        },
        headers={"X-API-Key": seeded["node_runtime_credential"]},
    )
    assert heartbeat.status_code == 200, heartbeat.text
    heartbeat_body = heartbeat.json()
    assert heartbeat_body["dataplane_probe_target_registered"] is True
    assert heartbeat_body["raw_dataplane_probe_target_redacted"] is True
    assert "127.0.0.1" not in str(heartbeat_body)

    db = testing_session()
    try:
        node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
        assert node is not None
        assert node.ip_address == "127.0.0.1"
    finally:
        db.close()

    class FakeVerificationMode:
        FULL = "full"

    class FakeMeshNetworkManager:
        def __init__(self, **kwargs):
            manager_kwargs.append(kwargs)
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
                "source_agents": ["bounded-dataplane-probe"],
                "event_ids": ["evt-probe"],
                "event_ids_count": 1,
                "events_total": 1,
                "redacted": True,
            }
            claim_boundary = "bounded fake dataplane probe evidence only"
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
                "claim_boundary": claim_boundary,
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
                        "claim_boundary": claim_boundary,
                        "redacted": True,
                    },
                    "claim_gate": claim_gate,
                    "payloads_redacted": True,
                },
            )
            return 1

    monkeypatch.setattr(healing_mod, "MESH_HEALING_AVAILABLE", True)
    monkeypatch.setattr(healing_mod, "VerificationMode", FakeVerificationMode)
    monkeypatch.setattr(healing_mod, "MeshNetworkManager", FakeMeshNetworkManager)
    monkeypatch.setattr(healing_mod, "get_event_bus", lambda project_root: event_bus)

    heal = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heal",
        headers={"X-API-Key": seeded["api_key"]},
    )
    assert heal.status_code == 200, heal.text
    body = heal.json()
    revalidation = body["post_action_dataplane_revalidation"]
    assert body["dataplane_confirmed"] is True
    assert body["post_action_dataplane_revalidated"] is True
    assert body["restored_dataplane_claim_allowed"] is True
    assert revalidation["status"] == "success"
    assert revalidation["reason"] == "bounded_dataplane_probe_succeeded"
    assert revalidation["probe_attempted"] is True
    assert revalidation["dataplane_confirmed"] is True
    assert revalidation["traffic_delivery_claim_allowed"] is False
    assert revalidation["production_readiness_claim_allowed"] is False
    assert revalidation["evidence"]["event_ids"] == ["evt-probe"]
    assert revalidation["claim_gate"]["restored_dataplane_claim_allowed"] is True
    assert body["control_plane_evidence"]["operations"] == [
        "trigger_aggressive_healing"
    ]
    assert manager_kwargs[0]["event_bus"] is event_bus
