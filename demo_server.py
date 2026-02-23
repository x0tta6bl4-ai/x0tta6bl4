from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta
from src.database import SessionLocal, User, MarketplaceListing, MarketplaceEscrow, AuditLog

app = FastAPI(title="x0tta6bl4 Demo API")

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@app.get("/health")
def health(): return {"status": "ok", "mode": "demo"}

@app.get("/api/v1/maas/dashboard/summary")
def dashboard(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.role == "admin").first()
    return {
        "user": {"email": user.email, "plan": user.plan},
        "stats": {"total_nodes": db.query(MarketplaceListing).count(), "active_rentals": 0},
        "recent_audit": [{"action": l.action, "created_at": l.created_at} for l in db.query(AuditLog).limit(5).all()]
    }

@app.get("/api/v1/maas/marketplace/search")
def search(db: Session = Depends(get_db)):
    nodes = db.query(MarketplaceListing).filter(MarketplaceListing.status == "available").all()
    return [{
        "id": n.id, "node_id": n.node_id, "region": n.region, 
        "price_per_hour": n.price_per_hour / 100.0, "status": n.status
    } for n in nodes]

@app.post("/api/v1/maas/marketplace/rent/{listing_id}")
def rent(listing_id: str, mesh_id: str, hours: int = 1, db: Session = Depends(get_db)):
    l = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
    if not l: raise HTTPException(404)
    escrow_id = f"esc-{uuid.uuid4().hex[:8]}"
    db.add(MarketplaceEscrow(id=escrow_id, listing_id=listing_id, renter_id="demo-user", amount_cents=100, status="held"))
    db.add(AuditLog(action="MARKETPLACE_RENT_INITIATED", method="POST", path=f"/rent/{listing_id}", status_code=200))
    db.commit()
    return {"escrow_id": escrow_id, "message": "Demo escrow created"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)
