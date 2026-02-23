
import asyncio
import logging
from src.mesh.network_manager import MeshNetworkManager
from src.database import SessionLocal, MeshNode

async def debug_heal():
    logging.basicConfig(level=logging.INFO)
    print("🔧 Direct healing attempt...")
    
    mesh = MeshNetworkManager(node_id="debug-manager")
    healed = await mesh.trigger_aggressive_healing()
    
    print(f"✅ Healed components count: {healed}")
    
    db = SessionLocal()
    node = db.query(MeshNode).filter(MeshNode.id == "chaos-node-1").first()
    print(f"🛡️ Node status after healing: {node.status}")
    db.close()

if __name__ == "__main__":
    asyncio.run(debug_heal())
