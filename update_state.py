from src.database import SessionLocal, User, MeshInstance, MeshNode
from datetime import datetime
db = SessionLocal()
user = db.query(User).filter(User.email == 'test-admin@x0tta6bl4.io').first()
mesh = db.query(MeshInstance).filter(MeshInstance.name == 'demo-mesh').first()
if mesh and user:
    mesh.owner_id = user.id
    nodes = db.query(MeshNode).filter(MeshNode.mesh_id == mesh.id).all()
    for n in nodes:
        n.last_seen = datetime.utcnow()
        n.status = 'healthy'
    db.commit()
    print(f"Mesh {mesh.name} assigned to {user.email}, {len(nodes)} nodes updated.")
else:
    print("Mesh or user not found.")
