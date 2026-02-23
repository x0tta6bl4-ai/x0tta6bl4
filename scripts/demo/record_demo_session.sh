#!/bin/bash
# record_demo_session.sh — Swarm Intelligence Demo
export PYTHONPATH=$PYTHONPATH:.
export DATABASE_URL="sqlite:////mnt/projects/x0tta6bl4_enterprise.db"

echo "🎥 Starting Demo Session Recording..."

# 1. Reset state
python3 seed_chaos_data.py

# 2. Start visualizer in a way we can 'snapshot' it
echo "--- STATE: STABLE ---"
python3 -c "from src.database import SessionLocal, MeshNode; db=SessionLocal(); n=db.query(MeshNode).first(); print(f'Node {n.id} is {n.status}'); db.close()"

sleep 2

# 3. Inject Chaos
echo "--- STATE: CHAOS INJECTED ---"
python3 -c "from src.database import SessionLocal, MeshNode; db=SessionLocal(); n=db.query(MeshNode).first(); n.status='offline'; db.commit(); print(f'💥 KILLED Node {n.id}'); db.close()"

sleep 2

# 4. Trigger Healing
echo "--- STATE: SELF-HEALING ---"
python3 debug_healing.py

sleep 2

# 5. Verify Recovery
echo "--- STATE: RECOVERED ---"
python3 -c "from src.database import SessionLocal, MeshNode; db=SessionLocal(); n=db.query(MeshNode).first(); print(f'🛡️ Node {n.id} is back to {n.status}'); db.close()"

echo "✅ Demo Session Complete. Logs are ready for visualization."
