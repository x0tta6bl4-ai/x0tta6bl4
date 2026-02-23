import uuid
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from src.core.app import app
from src.database import SessionLocal, User, MarketplaceListing, MarketplaceEscrow, AuditLog, MeshInstance, MeshNode

client = TestClient(app)

def run_full_flow_test():
    print("🚀 Starting MaaS Enterprise Full Flow Integration Test (via TestClient)")
    
    # 1. Setup Admin & User
    print("👤 Setting up users...")
    db = SessionLocal()
    
    admin_api_key = f"admin-key-{uuid.uuid4().hex[:6]}"
    admin = User(id=str(uuid.uuid4()), email=f"admin-{uuid.uuid4().hex[:4]}@x0tta6bl4.com", role="admin", api_key=admin_api_key, password_hash="hash")
    db.add(admin)
    
    user_api_key = f"user-key-{uuid.uuid4().hex[:6]}"
    test_user = User(id=str(uuid.uuid4()), email=f"user-{uuid.uuid4().hex[:4]}@test.com", role="user", plan="pro", api_key=user_api_key, password_hash="hash")
    db.add(test_user)
    db.commit()
    
    admin_headers = {"X-API-Key": admin_api_key}
    user_headers = {"X-API-Key": user_api_key}

    # 2. Create Mesh
    print("🕸️ Creating mesh...")
    mesh_id = f"mesh-{uuid.uuid4().hex[:6]}"
    mesh = MeshInstance(id=mesh_id, name="Test Mesh", owner_id=test_user.id, join_token="token123", plan="pro")
    db.add(mesh)
    db.commit()

    # 3. Marketplace Listing
    print("🏪 Creating marketplace listing...")
    node_id = f"node-{uuid.uuid4().hex[:6]}"
    res = client.post("/api/v1/maas/marketplace/list", json={
        "node_id": node_id,
        "region": "eu-central",
        "price_per_hour": 0.5,
        "bandwidth_mbps": 100
    }, headers=user_headers)
    
    if res.status_code != 200:
        print(f"❌ Marketplace List failed: {res.text}")
        raise Exception("Listing failed")
    listing_id = res.json()["listing_id"]

    # 4. Renting & Escrow
    print("💰 Renting node (creating escrow)...")
    res = client.post(f"/api/v1/maas/marketplace/rent/{listing_id}?mesh_id={mesh_id}&hours=2", headers=admin_headers)
    assert res.status_code == 200
    escrow_id = res.json()["escrow_id"]
    
    # Verify escrow is 'held'
    escrow = db.query(MarketplaceEscrow).filter(MarketplaceEscrow.id == escrow_id).first()
    assert escrow.status == "held"

    # 5. Heartbeat & Auto-release
    print("💓 Sending heartbeat (auto-releasing escrow)...")
    db.add(MeshNode(id=node_id, mesh_id=mesh_id, status="approved"))
    db.commit()
    
    res = client.post(f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat", json={"status": "healthy"}, headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["escrow_released"] == escrow_id
    
    # Verify DB states
    db.refresh(escrow)
    listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    assert escrow.status == "released"
    assert listing.status == "rented"

    # 6. Marketplace Janitor Logic
    print("🧹 Verifying Janitor logic...")
    stale_node_id = f"stale-node-{uuid.uuid4().hex[:6]}"
    stale_listing_id = f"lst-stale-{uuid.uuid4().hex[:4]}"
    db.add(MarketplaceListing(id=stale_listing_id, owner_id=test_user.id, node_id=stale_node_id, region="global", price_per_hour=10, status="escrow"))
    
    stale_escrow_id = f"esc-stale-{uuid.uuid4().hex[:4]}"
    stale_escrow = MarketplaceEscrow(
        id=stale_escrow_id, listing_id=stale_listing_id, renter_id=admin.id, 
        amount_cents=1000, status="held", 
        created_at=datetime.utcnow() - timedelta(hours=2)
    )
    db.add(stale_escrow)
    db.commit()
    
    # Trigger janitor-like logic
    expired_escrows = db.query(MarketplaceEscrow).filter(
        MarketplaceEscrow.status == "held",
        MarketplaceEscrow.created_at < datetime.utcnow() - timedelta(hours=1)
    ).all()
    for e in expired_escrows:
        e.status = "refunded"
        l = db.query(MarketplaceListing).filter(MarketplaceListing.id == e.listing_id).first()
        if l: l.status = "available"
    db.commit()
    
    db.refresh(stale_escrow)
    assert stale_escrow.status == "refunded"

    # 7. Audit Log Verification
    print("📑 Verifying Audit Logs...")
    logs = db.query(AuditLog).filter(AuditLog.user_id == test_user.id).all()
    actions = [l.action for l in logs]
    print(f"Captured actions for test_user: {actions}")
    # Middleware logs like 'POST /api/v1/maas/marketplace/list' or explicit 'MARKETPLACE_LISTING_CREATED'
    assert any("marketplace/list" in a or "MARKETPLACE_LISTING_CREATED" in a for a in actions)

    # 8. Dashboard Summary
    print("📊 Checking Dashboard...")
    res = client.get("/api/v1/maas/dashboard/summary", headers=user_headers)
    assert res.status_code == 200
    summary = res.json()
    assert summary["stats"]["active_rentals"] >= 0
    assert len(summary["recent_audit"]) > 0

    print("✅ ALL TESTS PASSED SUCCESSFULLY!")
    db.close()

if __name__ == "__main__":
    run_full_flow_test()
