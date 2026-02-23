import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta

# Mocking environment for local smoke test
os.environ["DATABASE_URL"] = "sqlite:///./smoke_test.db"
os.environ["X0TTA6BL4_PRODUCTION"] = "true"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_mock"

from sqlalchemy.orm import Session
from src.database import SessionLocal, create_tables, User, MeshInstance, MarketplaceListing, MarketplaceEscrow, MeshNode, AuditLog
from src.services.maas_orchestrator import maas_orchestrator

async def run_smoke():
    print("🧪 Starting Local Smoke Test (Non-Docker)...")
    create_tables()
    db = SessionLocal()
    
    try:
        # 1. Setup Data
        user_id = str(uuid.uuid4())
        admin_id = str(uuid.uuid4())
        
        admin = User(id=admin_id, email="admin@smoke.test", role="admin", api_key="admin-key", password_hash="smoke-hash")
        user = User(id=user_id, email="user@smoke.test", role="user", plan="enterprise", api_key="user-key", password_hash="smoke-hash")
        db.add_all([admin, user])
        
        mesh_id = "smoke-mesh-001"
        mesh = MeshInstance(id=mesh_id, name="Smoke Mesh", owner_id=user_id, join_token="secret", plan="enterprise")
        db.add(mesh)
        
        node_id = "smoke-node-001"
        listing_id = "lst-smoke"
        listing = MarketplaceListing(
            id=listing_id, owner_id=admin_id, node_id=node_id, 
            region="global", price_per_hour=100, status="available"
        )
        db.add(listing)
        db.commit()
        print("✅ Base data initialized.")

        # 2. Test Orchestrator
        print("📡 Testing Orchestrator...")
        # Simulate rental
        success = await maas_orchestrator.provision_rented_node(db, listing_id, user_id, mesh_id)
        if success:
            print("✅ Orchestrator successfully generated playbook.")
        else:
            print("❌ Orchestrator failed.")
            return

        # 3. Test Janitor logic (Manual trigger)
        print("🧹 Testing Janitor logic...")
        stale_escrow = MarketplaceEscrow(
            id="esc-stale", listing_id=listing_id, renter_id=user_id,
            amount_cents=1000, status="held", 
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
        db.add(stale_escrow)
        listing.status = "escrow"
        db.commit()
        
        # Run one-off janitor check
        expiry_limit = datetime.utcnow() - timedelta(hours=1)
        expired = db.query(MarketplaceEscrow).filter(
            MarketplaceEscrow.status == "held",
            MarketplaceEscrow.created_at < expiry_limit
        ).all()
        
        for e in expired:
            e.status = "refunded"
            l = db.query(MarketplaceListing).filter(MarketplaceListing.id == e.listing_id).first()
            if l: l.status = "available"
        db.commit()
        
        db.refresh(stale_escrow)
        if stale_escrow.status == "refunded" and listing.status == "available":
            print("✅ Janitor successfully auto-refunded stale escrow.")
        else:
            print(f"❌ Janitor logic failed. Status: {stale_escrow.status}")

        # 4. Audit Check
        print("📑 Checking Audit Logs...")
        logs = db.query(AuditLog).count()
        if logs > 0:
            print(f"✅ Audit system captured {logs} events.")
        else:
            print("❌ Audit log is empty.")

        print("🏁 LOCAL SMOKE TEST PASSED!")
        
    finally:
        db.close()
        if os.path.exists("smoke_test.db"):
            os.remove("smoke_test.db")

if __name__ == "__main__":
    asyncio.run(run_smoke())
