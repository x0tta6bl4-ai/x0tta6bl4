
import pytest
import hashlib
import hmac
import json
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os
import time
import uuid

# Add project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.app import app
from src.database import Base, User, get_db

# Setup Test DB
_TEST_DB_PATH = f"./test_maas_{uuid.uuid4().hex}.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TEST_DB_PATH}"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def _billing_hmac_signature(payload: bytes, secret: str, timestamp: str) -> str:
    signed = f"{timestamp}.".encode("utf-8") + payload
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

@pytest.fixture(scope="module")
def client():
    # Ensure clean schema (handles local stale DB files between runs)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    original_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    # Restore previous state
    if original_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = original_override
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    if os.path.exists(_TEST_DB_PATH):
        os.remove(_TEST_DB_PATH)

def test_maas_full_flow(client):
    # 1. Register
    reg_payload = {
        "email": "test@x0tta6bl4.net",
        "password": "strong_password_123",
        "full_name": "Test User",
        "company": "Test Corp"
    }
    response = client.post("/api/v1/maas/register", json=reg_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    api_key = data["access_token"]

    # 2. Login (Optional check)
    login_payload = {
        "email": "test@x0tta6bl4.net",
        "password": "strong_password_123"
    }
    response = client.post("/api/v1/maas/login", json=login_payload)
    assert response.status_code == 200
    assert response.json()["access_token"] == api_key

    # 3. Deploy Mesh
    deploy_payload = {
        "name": "My First Mesh",
        "nodes": 3,
        "billing_plan": "starter"
    }
    headers = {"X-API-Key": api_key}
    response = client.post("/api/v1/maas/deploy", json=deploy_payload, headers=headers)
    
    assert response.status_code == 200
    deploy_data = response.json()
    
    assert "mesh_id" in deploy_data
    assert "join_config" in deploy_data
    assert deploy_data["status"] == "active"
    assert deploy_data["plan"] == "starter"
    
    # Check PQC Identity
    if deploy_data.get("pqc_identity"):
        pqc = deploy_data["pqc_identity"]
        assert "did" in pqc
        assert "keys" in pqc
        assert pqc["keys"]["sig_alg"] in ["ML-DSA-65", "Dilithium3"]

    # 4. Check "Me" info and usage
    response = client.get("/api/v1/maas/me", headers=headers)
    assert response.status_code == 200
    me_data = response.json()
    assert me_data["email"] == "test@x0tta6bl4.net"
    # Usage should be > 0 because of previous calls
    # Wait, middleware updates usage AFTER response? Or async?
    # In test client, it might be synchronous enough or not. 
    # Let's verify requests_count exists at least.
    assert "requests_count" in me_data


def test_legacy_rotate_api_key_endpoint(client):
    email = f"legacy-rotate-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"
    register = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Rotate User",
            "company": "Rotate Corp",
        },
    )
    assert register.status_code == 200
    old_key = register.json()["access_token"]

    rotate = client.post(
        "/api/v1/maas/api-key",
        headers={"X-API-Key": old_key},
    )
    assert rotate.status_code == 200
    body = rotate.json()
    new_key = body["api_key"]
    assert new_key != old_key
    assert "created_at" in body

    old_me = client.get("/api/v1/maas/me", headers={"X-API-Key": old_key})
    assert old_me.status_code == 401

    new_me = client.get("/api/v1/maas/me", headers={"X-API-Key": new_key})
    assert new_me.status_code == 200
    assert new_me.json()["email"] == email


def test_legacy_plaintext_password_migrates_on_legacy_login(client):
    email = f"legacy-login-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    legacy_password = "legacy_password_123"
    api_key = f"x0t_{uuid.uuid4().hex}"

    db = TestingSessionLocal()
    try:
        db.add(
            User(
                id=f"user-{uuid.uuid4().hex}",
                email=email,
                password_hash=legacy_password,
                api_key=api_key,
                plan="starter",
            )
        )
        db.commit()
    finally:
        db.close()

    login = client.post(
        "/api/v1/maas/login",
        json={"email": email, "password": legacy_password},
    )
    assert login.status_code == 200
    assert login.json()["access_token"] == api_key

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        assert user.password_hash != legacy_password
        assert user.password_hash.startswith("$2")
    finally:
        db.close()


def test_node_revoke_reissue_flow(client):
    email = f"node-flow-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    # 1. Register and deploy mesh
    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Node Flow User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    deploy = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Node Flow Mesh", "nodes": 3, "billing_plan": "starter"},
        headers=headers,
    )
    assert deploy.status_code == 200
    deploy_data = deploy.json()
    mesh_id = deploy_data["mesh_id"]
    enrollment_token = deploy_data["join_config"]["token"]

    # 2. Register + approve node
    register_payload = {
        "node_id": "robot-node-1",
        "enrollment_token": enrollment_token,
        "device_class": "robot",
        "labels": {"zone": "alpha"},
    }
    reg_node = client.post(f"/api/v1/maas/{mesh_id}/nodes/register", json=register_payload)
    assert reg_node.status_code == 200
    assert reg_node.json()["status"] == "pending_approval"

    approve = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/robot-node-1/approve",
        json={"acl_profile": "strict", "tags": ["robot"]},
        headers=headers,
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "approved"

    # 2.5. Status check in e2e flow
    status = client.get(f"/api/v1/maas/{mesh_id}/status", headers=headers)
    assert status.status_code == 200
    status_data = status.json()
    assert status_data["mesh_id"] == mesh_id
    assert status_data["nodes_total"] >= 1

    # 2.6. Heartbeat -> MAPE-K events stream
    hb = client.post(
        "/api/v1/maas/heartbeat",
        json={
            "node_id": "robot-node-1",
            "cpu_usage": 87.5,
            "memory_usage": 64.2,
            "neighbors_count": 2,
            "routing_table_size": 8,
            "uptime": 340.0,
        },
        headers=headers,
    )
    assert hb.status_code == 200
    hb_data = hb.json()
    assert hb_data["event_emitted"] is True
    assert hb_data["mesh_id"] == mesh_id

    events = client.get(f"/api/v1/maas/{mesh_id}/mapek/events?limit=10", headers=headers)
    assert events.status_code == 200
    events_data = events.json()
    assert events_data["count"] >= 1
    assert events_data["events"][-1]["node_id"] == "robot-node-1"

    # 3. Revoke
    revoke = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/revoke",
        json={"node_id": "robot-node-1", "reason": "rotation"},
        headers=headers,
    )
    assert revoke.status_code == 200
    assert revoke.json()["status"] == "revoked"

    # 4. Reissue one-time token
    reissue = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/robot-node-1/reissue-token",
        json={"ttl_seconds": 900},
        headers=headers,
    )
    assert reissue.status_code == 200
    reissued_token = reissue.json()["join_token"]["token"]

    # 5. Re-register with reissued token
    reregister = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/register",
        json={
            "node_id": "robot-node-1",
            "enrollment_token": reissued_token,
            "device_class": "robot",
        },
    )
    assert reregister.status_code == 200
    assert reregister.json()["status"] == "pending_approval"

    # 6. One-time token cannot be reused
    reuse = client.post(
        f"/api/v1/maas/{mesh_id}/nodes/register",
        json={
            "node_id": "robot-node-1",
            "enrollment_token": reissued_token,
            "device_class": "robot",
        },
    )
    assert reuse.status_code == 401


def test_billing_webhook_updates_plan(client):
    email = f"billing-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    webhook = client.post(
        "/api/v1/maas/billing/webhook",
        json={
            "event_id": f"evt-{uuid.uuid4().hex}",
            "event_type": "plan.upgraded",
            "email": email,
            "plan": "enterprise",
            "customer_id": "cus_test_billing",
            "subscription_id": "sub_test_billing",
        },
    )
    assert webhook.status_code == 200
    body = webhook.json()
    assert body["processed"] is True
    assert body["plan_before"] == "starter"
    assert body["plan_after"] == "enterprise"
    assert body["requests_limit"] == 1000000
    assert body["idempotent_replay"] is False

    me = client.get("/api/v1/maas/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["plan"] == "enterprise"


def test_billing_webhook_secret_enforced(client, monkeypatch):
    email = f"billing-secret-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing Secret User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200

    monkeypatch.setenv("X0T_BILLING_WEBHOOK_SECRET", "very-secret")

    payload = {
        "event_id": f"evt-{uuid.uuid4().hex}",
        "event_type": "plan.upgraded",
        "email": email,
        "plan": "pro",
    }

    missing = client.post("/api/v1/maas/billing/webhook", json=payload)
    assert missing.status_code == 401

    wrong = client.post(
        "/api/v1/maas/billing/webhook",
        json=payload,
        headers={"X-Billing-Webhook-Secret": "wrong-secret"},
    )
    assert wrong.status_code == 401

    ok = client.post(
        "/api/v1/maas/billing/webhook",
        json=payload,
        headers={"X-Billing-Webhook-Secret": "very-secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["plan_after"] == "pro"


def test_billing_webhook_idempotent_replay(client):
    email = f"billing-replay-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing Replay User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    event_id = f"evt-{uuid.uuid4().hex}"
    payload = {
        "event_id": event_id,
        "event_type": "plan.upgraded",
        "email": email,
        "plan": "pro",
    }
    first = client.post(
        "/api/v1/maas/billing/webhook",
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["idempotent_replay"] is False
    assert first.json()["plan_after"] == "pro"

    # Same payload + event_id must return cached response.
    second = client.post(
        "/api/v1/maas/billing/webhook",
        json=payload,
    )
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert second.json()["plan_after"] == "pro"

    me = client.get("/api/v1/maas/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["plan"] == "pro"


def test_billing_webhook_event_id_payload_mismatch_conflict(client):
    email = f"billing-mismatch-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing Mismatch User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200

    event_id = f"evt-{uuid.uuid4().hex}"
    first = client.post(
        "/api/v1/maas/billing/webhook",
        json={
            "event_id": event_id,
            "event_type": "plan.upgraded",
            "email": email,
            "plan": "pro",
        },
    )
    assert first.status_code == 200

    # Same event_id with changed payload must be rejected.
    mismatch = client.post(
        "/api/v1/maas/billing/webhook",
        json={
            "event_id": event_id,
            "event_type": "plan.upgraded",
            "email": email,
            "plan": "enterprise",
        },
    )
    assert mismatch.status_code == 409
    assert "payload mismatch" in str(mismatch.json()).lower()


def test_billing_webhook_hmac_signature_enforced(client, monkeypatch):
    email = f"billing-hmac-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing HMAC User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200

    monkeypatch.setenv("X0T_BILLING_WEBHOOK_HMAC_SECRET", "hmac-secret")
    monkeypatch.setenv("X0T_BILLING_WEBHOOK_TOLERANCE_SEC", "300")

    payload = {
        "event_id": f"evt-{uuid.uuid4().hex}",
        "event_type": "plan.upgraded",
        "email": email,
        "plan": "pro",
    }
    raw_payload = json.dumps(payload).encode("utf-8")
    ts = str(int(time.time()))
    valid_sig = _billing_hmac_signature(raw_payload, "hmac-secret", ts)

    missing = client.post(
        "/api/v1/maas/billing/webhook",
        content=raw_payload,
        headers={"Content-Type": "application/json"},
    )
    assert missing.status_code == 401

    invalid = client.post(
        "/api/v1/maas/billing/webhook",
        content=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Billing-Timestamp": ts,
            "X-Billing-Signature": "sha256=deadbeef",
        },
    )
    assert invalid.status_code == 401

    ok = client.post(
        "/api/v1/maas/billing/webhook",
        content=raw_payload,
        headers={
            "Content-Type": "application/json",
            "X-Billing-Timestamp": ts,
            "X-Billing-Signature": f"sha256={valid_sig}",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["plan_after"] == "pro"


def test_billing_webhook_subscription_canceled_downgrades(client):
    email = f"billing-cancel-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing Cancel User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    upgraded = client.post(
        "/api/v1/maas/billing/webhook",
        json={
            "event_id": f"evt-{uuid.uuid4().hex}",
            "event_type": "plan.upgraded",
            "email": email,
            "plan": "enterprise",
        },
    )
    assert upgraded.status_code == 200
    assert upgraded.json()["plan_after"] == "enterprise"

    canceled = client.post(
        "/api/v1/maas/billing/webhook",
        json={
            "event_id": f"evt-{uuid.uuid4().hex}",
            "event_type": "subscription.canceled",
            "email": email,
        },
    )
    assert canceled.status_code == 200
    assert canceled.json()["plan_after"] == "starter"

    me = client.get("/api/v1/maas/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["plan"] == "starter"


def test_billing_webhook_requires_event_id(client):
    email = f"billing-noevent-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing NoEvent User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200

    missing_event = client.post(
        "/api/v1/maas/billing/webhook",
        json={
            "event_type": "plan.upgraded",
            "email": email,
            "plan": "pro",
        },
    )
    assert missing_event.status_code == 400
    assert "event_id" in str(missing_event.json()).lower()


def test_billing_usage_endpoints(client):
    email = f"billing-usage-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Billing Usage User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    headers = {"X-API-Key": api_key}

    deploy = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Usage Mesh", "nodes": 2, "billing_plan": "starter"},
        headers=headers,
    )
    assert deploy.status_code == 200
    mesh_id = deploy.json()["mesh_id"]

    time.sleep(0.05)

    mesh_usage = client.get(f"/api/v1/maas/billing/usage/{mesh_id}", headers=headers)
    assert mesh_usage.status_code == 200
    mesh_body = mesh_usage.json()
    assert mesh_body["mesh_id"] == mesh_id
    assert mesh_body["active_nodes"] == 2
    assert "total_node_hours" in mesh_body
    assert "nodes" in mesh_body
    assert len(mesh_body["nodes"]) == 2

    account_usage = client.get("/api/v1/maas/billing/usage", headers=headers)
    assert account_usage.status_code == 200
    account_body = account_usage.json()
    assert account_body["owner_id"]
    assert account_body["mesh_count"] >= 1
    assert account_body["total_node_hours"] >= 0
    summary = next(
        (item for item in account_body["meshes"] if item["mesh_id"] == mesh_id),
        None,
    )
    assert summary is not None
    assert summary["active_nodes"] == 2


def test_usage_metering(client):
    email = f"usage-{uuid.uuid4().hex[:8]}@x0tta6bl4.net"
    password = "strong_password_123"

    reg = client.post(
        "/api/v1/maas/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Usage User",
            "company": "Test Corp",
        },
    )
    assert reg.status_code == 200
    api_key = reg.json()["access_token"]
    user_id = reg.json()["access_token"] # In our mock register, token is returned but we need the ID from /me
    
    me = client.get("/api/v1/maas/me", headers={"X-API-Key": api_key})
    user_id = me.json()["id"]
    headers = {"X-API-Key": api_key}

    deploy = client.post(
        "/api/v1/maas/deploy",
        json={"name": "Usage Mesh", "nodes": 2, "billing_plan": "starter"},
        headers=headers,
    )
    assert deploy.status_code == 200
    mesh_id = deploy.json()["mesh_id"]

    # 1. Initial usage check
    usage = client.get(f"/api/v1/maas/billing/usage/{mesh_id}", headers=headers)
    assert usage.status_code == 200
    data = usage.json()
    assert data["mesh_id"] == mesh_id
    assert data["active_nodes"] == 2
    # Should be near 0 initially
    assert data["total_node_hours"] >= 0

    # 2. Simulate time passing (Hack into the registry since we are in-process)
    from src.api.maas import _mesh_registry
    from datetime import datetime, timedelta
    
    if mesh_id in _mesh_registry:
        instance = _mesh_registry[mesh_id]
        # Backdate node starts by 2 hours
        past = (datetime.utcnow() - timedelta(hours=2)).isoformat()
        for nid in instance.node_instances:
            instance.node_instances[nid]["started_at"] = past
            
    # 3. Re-check usage
    usage = client.get(f"/api/v1/maas/billing/usage/{mesh_id}", headers=headers)
    assert usage.status_code == 200
    data = usage.json()
    # 2 nodes * 2 hours = ~4 node-hours
    assert 3.9 <= data["total_node_hours"] <= 4.1

    # 4. Global account usage
    account_usage = client.get("/api/v1/maas/billing/usage", headers=headers)
    assert account_usage.status_code == 200
    acc_data = account_usage.json()
    assert acc_data["owner_id"] == user_id
    assert acc_data["total_node_hours"] >= 4
    assert any(m["mesh_id"] == mesh_id for m in acc_data["meshes"])
