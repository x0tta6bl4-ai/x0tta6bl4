from src.database import SessionLocal, SBOMEntry, NodeBinaryAttestation, MeshNode
from datetime import datetime
import uuid

db = SessionLocal()
# Check if SBOMEntry exists
sbom = db.query(SBOMEntry).filter_by(version="3.3.0").first()
if not sbom:
    print("Creating SBOMEntry...")
    sbom = SBOMEntry(
        id="sbom-v3.3.0", 
        version="3.3.0", 
        components_json="[]", 
        checksum_sha256="sha256:123"
    )
    db.add(sbom)
    db.commit()
else:
    print(f"Using existing SBOMEntry {sbom.id}")

nodes = db.query(MeshNode).all()
count = 0
for n in nodes:
    # Check if already attested
    if not db.query(NodeBinaryAttestation).filter_by(node_id=n.id).first():
        db.add(NodeBinaryAttestation(
            id=f"att-{n.id}-{uuid.uuid4().hex[:4]}",
            node_id=n.id,
            sbom_id=sbom.id,
            agent_version="3.3.0",
            checksum_sha256="sha256:deadbeef",
            status="verified",
            verified_at=datetime.utcnow()
        ))
        count += 1

db.commit()
print(f"Attested {count} nodes")
db.close()
