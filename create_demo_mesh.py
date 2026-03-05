import secrets

from src.database import SessionLocal, MeshInstance
from datetime import datetime

db = SessionLocal()
m = db.query(MeshInstance).filter_by(id='demo-mesh').first()
if not m:
    m = MeshInstance(
        id='demo-mesh', 
        name='Demo Mesh', 
        owner_id='demo-user-1', 
        plan='enterprise', 
        status='active', 
        join_token=secrets.token_urlsafe(32), 
        join_token_expires_at=datetime.utcnow()
    )
    db.add(m)
    db.commit()
    print('Mesh demo-mesh created.')
else:
    print('Mesh demo-mesh already exists.')
db.close()
