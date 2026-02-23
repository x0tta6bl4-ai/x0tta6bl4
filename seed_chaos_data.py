
from src.database import SessionLocal, MeshNode, MeshInstance, User
from datetime import datetime
import uuid

def seed():
    db = SessionLocal()
    
    # Ensure a user exists
    user = db.query(User).first()
    if not user:
        user = User(id="chaos-user", email="chaos@x0t.net", password_hash="hash", plan="pro")
        db.add(user)
        db.commit()
        print("✅ Created chaos-user")

    # Create a mesh instance
    mesh = db.query(MeshInstance).first()
    if not mesh:
        mesh = MeshInstance(id="chaos-mesh", name="Chaos Test Network", owner_id=user.id, plan="pro")
        db.add(mesh)
        db.commit()
        print("✅ Created chaos-mesh")

    # Add a node
    node = db.query(MeshNode).filter(MeshNode.id == "chaos-node-1").first()
    if not node:
        node = MeshNode(
            id="chaos-node-1", 
            mesh_id=mesh.id, 
            status="healthy", 
            last_seen=datetime.utcnow()
        )
        db.add(node)
        db.commit()
        print("✅ Created chaos-node-1")
    else:
        node.status = "healthy"
        node.last_seen = datetime.utcnow()
        db.commit()
        print("✅ Reset chaos-node-1 status to healthy")

    db.close()

if __name__ == "__main__":
    seed()
