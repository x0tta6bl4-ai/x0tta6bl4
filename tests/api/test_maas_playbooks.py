"""
Integration tests for MaaS Signed Playbooks:
- Create PQC-signed playbook (admin)
- Poll playbooks per node
- Acknowledge execution (upsert)
- /status endpoint merges DB + in-memory
- Expiry: expired playbooks not delivered
- RBAC: non-operator cannot create
"""

import os
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.app import app
from src.database import Base, get_db, User, SignedPlaybook, PlaybookAck

_TEST_DB_PATH = f"./test_playbooks_{uuid.uuid4().hex}.db"
engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH}", connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)


def _register(client, role="user"):
    email = f"{role}-pb-{uuid.uuid4().hex[:8]}@test.com"
    r = client.post(
        "/api/v1/maas/auth/register",
        json={"email": email, "password": "password123"},
    )
    token = r.json()["access_token"]
    if role in ("admin", "operator"):
        db = TestingSessionLocal()
        u = db.query(User).filter(User.api_key == token).first()
        u.role = role
        db.commit()
        db.close()
    return token


@pytest.fixture(scope="module")
def admin_token(client):
    return _register(client, "admin")


@pytest.fixture(scope="module")
def user_token(client):
    return _register(client, "user")


_MESH_ID = f"mesh-pb-{uuid.uuid4().hex[:6]}"
_NODE_A = f"node-a-{uuid.uuid4().hex[:6]}"
_NODE_B = f"node-b-{uuid.uuid4().hex[:6]}"


class TestPlaybookCreate:
    def test_create_playbook_as_admin(self, client, admin_token):
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            headers={"X-API-Key": admin_token},
            json={
                "name": "restart-agents",
                "target_nodes": [_NODE_A, _NODE_B],
                "actions": [{"action": "restart", "params": {"graceful": True}}],
                "expires_in_sec": 3600,
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["playbook_id"].startswith("pbk-")
        assert data["name"] == "restart-agents"
        assert data["signature"]
        assert data["algorithm"]
        pytest.shared_playbook_id = data["playbook_id"]

    def test_playbook_persisted_to_db(self, client, admin_token):
        db = TestingSessionLocal()
        row = db.query(SignedPlaybook).filter(
            SignedPlaybook.id == pytest.shared_playbook_id
        ).first()
        db.close()
        assert row is not None
        assert row.mesh_id == _MESH_ID
        assert row.name == "restart-agents"

    def test_non_operator_cannot_create(self, client, user_token):
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            headers={"X-API-Key": user_token},
            json={
                "name": "unauthorized",
                "target_nodes": [_NODE_A],
                "actions": [{"action": "restart", "params": {}}],
            },
        )
        assert r.status_code == 403

    def test_invalid_action_rejected(self, client, admin_token):
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            headers={"X-API-Key": admin_token},
            json={
                "name": "bad-action",
                "target_nodes": [_NODE_A],
                "actions": [{"action": "delete_all", "params": {}}],
            },
        )
        assert r.status_code == 422

    def test_empty_target_nodes_rejected(self, client, admin_token):
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            headers={"X-API-Key": admin_token},
            json={
                "name": "no-targets",
                "target_nodes": [],
                "actions": [{"action": "restart", "params": {}}],
            },
        )
        assert r.status_code == 422


class TestPlaybookPoll:
    def test_node_receives_playbook(self, client, admin_token):
        # Create fresh playbook for this test
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            headers={"X-API-Key": admin_token},
            json={
                "name": "poll-test",
                "target_nodes": [_NODE_A],
                "actions": [{"action": "upgrade", "params": {"version": "3.5.0"}}],
                "expires_in_sec": 3600,
            },
        )
        assert r.status_code == 200
        pb_id = r.json()["playbook_id"]

        r = client.get(f"/api/v1/maas/playbooks/poll/{_MESH_ID}/{_NODE_A}")
        assert r.status_code == 200
        data = r.json()
        assert "playbooks" in data
        pb_ids = [pb["playbook_id"] for pb in data["playbooks"]]
        assert pb_id in pb_ids

    def test_node_not_in_targets_gets_empty(self, client, admin_token):
        other_node = f"node-other-{uuid.uuid4().hex[:6]}"
        r = client.get(f"/api/v1/maas/playbooks/poll/{_MESH_ID}/{other_node}")
        assert r.status_code == 200
        assert r.json()["playbooks"] == []

    def test_wrong_mesh_id_not_delivered(self, client, admin_token):
        # Node is in _MESH_ID but polling with wrong mesh
        r = client.get(f"/api/v1/maas/playbooks/poll/mesh-wrong/{_NODE_A}")
        assert r.status_code == 200
        assert r.json()["playbooks"] == []

    def test_poll_removes_from_queue(self, client, admin_token):
        node = f"node-drain-{uuid.uuid4().hex[:6]}"
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            headers={"X-API-Key": admin_token},
            json={
                "name": "drain-test",
                "target_nodes": [node],
                "actions": [{"action": "restart", "params": {}}],
                "expires_in_sec": 3600,
            },
        )
        assert r.status_code == 200

        # First poll delivers
        r1 = client.get(f"/api/v1/maas/playbooks/poll/{_MESH_ID}/{node}")
        assert len(r1.json()["playbooks"]) >= 1

        # Second poll — queue drained (popped on delivery)
        r2 = client.get(f"/api/v1/maas/playbooks/poll/{_MESH_ID}/{node}")
        assert r2.json()["playbooks"] == []


class TestPlaybookAck:
    def test_ack_playbook(self, client, admin_token):
        pb_id = pytest.shared_playbook_id
        r = client.post(
            f"/api/v1/maas/playbooks/ack/{pb_id}/{_NODE_A}?status=completed",
        )
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "received"
        assert data["playbook_id"] == pb_id

    def test_ack_persisted_to_db(self, client):
        db = TestingSessionLocal()
        row = db.query(PlaybookAck).filter(
            PlaybookAck.playbook_id == pytest.shared_playbook_id,
            PlaybookAck.node_id == _NODE_A,
        ).first()
        db.close()
        assert row is not None
        assert row.status == "completed"

    def test_ack_upsert_updates_status(self, client):
        pb_id = pytest.shared_playbook_id
        # Re-ack with failed status
        r = client.post(
            f"/api/v1/maas/playbooks/ack/{pb_id}/{_NODE_A}?status=failed",
        )
        assert r.status_code == 200

        db = TestingSessionLocal()
        rows = db.query(PlaybookAck).filter(
            PlaybookAck.playbook_id == pb_id,
            PlaybookAck.node_id == _NODE_A,
        ).all()
        db.close()
        assert len(rows) == 1  # Upserted, not duplicated
        assert rows[0].status == "failed"

    def test_ack_multiple_nodes(self, client):
        pb_id = pytest.shared_playbook_id
        client.post(f"/api/v1/maas/playbooks/ack/{pb_id}/{_NODE_B}?status=completed")

        db = TestingSessionLocal()
        rows = db.query(PlaybookAck).filter(
            PlaybookAck.playbook_id == pb_id
        ).all()
        db.close()
        node_ids = {r.node_id for r in rows}
        assert _NODE_A in node_ids
        assert _NODE_B in node_ids


class TestPlaybookStatus:
    def test_status_shows_acks(self, client, admin_token):
        pb_id = pytest.shared_playbook_id
        r = client.get(
            f"/api/v1/maas/playbooks/status/{pb_id}",
            headers={"X-API-Key": admin_token},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["playbook_id"] == pb_id
        assert data["total_acks"] >= 2
        assert _NODE_A in data["node_statuses"]
        assert _NODE_B in data["node_statuses"]

    def test_status_unknown_playbook_404(self, client, admin_token):
        r = client.get(
            "/api/v1/maas/playbooks/status/pbk-nonexistent",
            headers={"X-API-Key": admin_token},
        )
        assert r.status_code == 404


class TestPlaybookList:
    def test_list_playbooks_for_mesh(self, client, admin_token):
        r = client.get(
            f"/api/v1/maas/playbooks/list/{_MESH_ID}",
            headers={"X-API-Key": admin_token},
        )
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        pb_ids = [pb["playbook_id"] for pb in data]
        assert pytest.shared_playbook_id in pb_ids

    def test_list_other_mesh_empty(self, client, admin_token):
        r = client.get(
            "/api/v1/maas/playbooks/list/mesh-nonexistent",
            headers={"X-API-Key": admin_token},
        )
        assert r.status_code == 200
        # Either empty list or list without our playbooks
        data = r.json()
        assert isinstance(data, list)
        pb_ids = [pb.get("playbook_id", "") for pb in data]
        assert pytest.shared_playbook_id not in pb_ids


# ---------------------------------------------------------------------------
# Auth guard tests for endpoints that require permission
# ---------------------------------------------------------------------------

class TestPlaybookAuthGuards:
    def test_create_no_auth_401(self, client):
        r = client.post(
            f"/api/v1/maas/playbooks/create?mesh_id={_MESH_ID}",
            json={
                "name": "no-auth-test",
                "target_nodes": [_NODE_A],
                "actions": [{"action": "restart", "params": {}}],
            },
        )
        assert r.status_code == 401

    def test_list_no_auth_401(self, client):
        r = client.get(f"/api/v1/maas/playbooks/list/{_MESH_ID}")
        assert r.status_code == 401

    def test_status_no_auth_401(self, client):
        r = client.get("/api/v1/maas/playbooks/status/pbk-any")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Expired playbook is NOT delivered on poll
# ---------------------------------------------------------------------------

class TestPlaybookExpiry:
    def test_expired_playbook_not_delivered(self, client, admin_token):
        """
        Inject an expired entry directly into the in-memory store, then poll.
        The poll should skip expired playbooks (expires_at <= now → continue).
        """
        import src.api.maas_playbooks as pb_mod
        from datetime import datetime, timedelta

        node_id = f"node-exp-{uuid.uuid4().hex[:8]}"
        pb_id = f"pbk-exp-{uuid.uuid4().hex[:8]}"
        mesh_id = f"mesh-exp-{uuid.uuid4().hex[:6]}"

        # Insert a playbook that already expired 1 hour ago
        pb_mod._playbook_store[pb_id] = {
            "playbook_id": pb_id,
            "mesh_id": mesh_id,
            "name": "expired-test",
            "payload": "{}",
            "signature": "sig",
            "algorithm": "HMAC-SHA256",
            "target_nodes": [node_id],
            "created_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
        }
        pb_mod._node_queues.setdefault(node_id, []).append(pb_id)

        r = client.get(f"/api/v1/maas/playbooks/poll/{mesh_id}/{node_id}")
        assert r.status_code == 200
        data = r.json()
        # Expired playbook must NOT appear in delivery list
        delivered_ids = [pb["playbook_id"] for pb in data["playbooks"]]
        assert pb_id not in delivered_ids

        # Cleanup
        pb_mod._playbook_store.pop(pb_id, None)
        pb_mod._node_queues.pop(node_id, None)
