#!/usr/bin/env python3
"""
Seed script for MaaS Supply Chain Demo data.
Populates SBOM registry and creates attestation records for demo nodes.
"""

import sys
import os
import json
import uuid
from datetime import datetime, timedelta

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, project_root)

try:
    from src.database import SessionLocal, SBOMEntry, NodeBinaryAttestation, MeshNode, User
except ImportError as e:
    print(f"Error importing database models (Root: {project_root}): {e}")
    sys.exit(1)

def seed_data():
    db = SessionLocal()
    try:
        print("🌱 Seeding Supply Chain Demo Data...")
        
        # 1. Ensure admin user exists
        admin = db.query(User).filter(User.role == "admin").first()
        if not admin:
            print("Admin user not found. Please run setup_maas_enterprise.py first.")
            return

        # 2. Create SBOM Entry
        version = "v3.4.0-stable"
        existing_sbom = db.query(SBOMEntry).filter(SBOMEntry.version == version).first()
        if not existing_sbom:
            sbom_id = f"sbom-{uuid.uuid4().hex[:8]}"
            components = [
                {"name": "x0tta6bl4-core", "version": "3.4.0", "type": "application"},
                {"name": "ghost-transport", "version": "1.2.0", "type": "library"},
                {"name": "pqc-crypto-lib", "version": "0.10.1", "type": "library"}
            ]
            sbom = SBOMEntry(
                id=sbom_id,
                version=version,
                format="CycloneDX-JSON",
                components_json=json.dumps(components),
                checksum_sha256="sha256:8888888888888888888888888888888888888888",
                created_by=admin.id
            )
            db.add(sbom)
            print(f"✅ Registered SBOM version {version}")
        else:
            sbom = existing_sbom
            print(f"ℹ️ SBOM version {version} already exists")

        # 3. Create Attestations for existing nodes
        nodes = db.query(MeshNode).all()
        if not nodes:
            print("No nodes found. Create some nodes first.")
        else:
            for node in nodes:
                # Add a verified attestation
                att_id = f"att-{uuid.uuid4().hex[:8]}"
                att = NodeBinaryAttestation(
                    id=att_id,
                    node_id=node.id,
                    mesh_id=node.mesh_id,
                    sbom_id=sbom.id,
                    agent_version=version,
                    checksum_sha256=sbom.checksum_sha256,
                    status="verified",
                    verified_at=datetime.utcnow()
                )
                db.add(att)
                print(f"✅ Created verified attestation for node {node.id}")

        db.commit()
        print("✨ Demo data seeding complete.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Failed to seed data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_data()
