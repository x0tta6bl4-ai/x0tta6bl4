"""
MaaS Supply Chain Security — x0tta6bl4
=======================================

DB-backed SBOM registry and per-node binary attestation.
Ensures headless agents are running verified, untampered code.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.database import NodeBinaryAttestation, SBOMEntry, User, get_db
from src.api.maas_auth import get_current_user_from_maas, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/supply-chain", tags=["MaaS Supply Chain"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ComponentEntry(BaseModel):
    name: str
    version: str
    type: str = "library"


class AttestationMeta(BaseModel):
    type: str = "Sigstore-Bundle"
    signer: str
    signed_at: str
    bundle_url: Optional[str] = None


class SBOMRegisterRequest(BaseModel):
    version: str = Field(..., min_length=3)
    format: str = Field(default="CycloneDX-JSON")
    checksum_sha256: str = Field(..., min_length=16)
    components: List[ComponentEntry]
    attestation: Optional[AttestationMeta] = None


class SBOMResponse(BaseModel):
    id: str
    version: str
    format: str
    checksum_sha256: str
    components: List[Dict[str, Any]]
    attestation: Optional[Dict[str, Any]]
    created_at: Optional[str]


class BinaryVerifyRequest(BaseModel):
    node_id: str
    mesh_id: Optional[str] = None
    agent_version: str
    checksum_sha256: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sbom_to_response(row: SBOMEntry) -> SBOMResponse:
    return SBOMResponse(
        id=row.id,
        version=row.version,
        format=row.format,
        checksum_sha256=row.checksum_sha256,
        components=json.loads(row.components_json) if row.components_json else [],
        attestation=json.loads(row.attestation_json) if row.attestation_json else None,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/sbom/{version}", response_model=SBOMResponse)
async def get_sbom(version: str, db: Session = Depends(get_db)):
    """Fetch SBOM for a specific agent version. Publicly accessible for transparency."""
    row = db.query(SBOMEntry).filter(SBOMEntry.version == version).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"SBOM for version '{version}' not found")
    return _sbom_to_response(row)


@router.get("/sbom", response_model=List[SBOMResponse])
async def list_sboms(db: Session = Depends(get_db)):
    """List all registered SBOM versions."""
    rows = db.query(SBOMEntry).order_by(SBOMEntry.created_at.desc()).all()
    return [_sbom_to_response(r) for r in rows]


@router.post("/register-artifact", response_model=SBOMResponse)
async def register_artifact(
    req: SBOMRegisterRequest,
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Register a new build artifact SBOM (CI/CD pipeline only)."""
    existing = db.query(SBOMEntry).filter(SBOMEntry.version == req.version).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"SBOM for version '{req.version}' already registered")

    sbom_id = f"sbom-{uuid.uuid4().hex[:8]}"
    row = SBOMEntry(
        id=sbom_id,
        version=req.version,
        format=req.format,
        checksum_sha256=req.checksum_sha256,
        components_json=json.dumps([c.dict() for c in req.components]),
        attestation_json=json.dumps(req.attestation.dict()) if req.attestation else None,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    logger.info("📦 Registered SBOM %s (version=%s)", sbom_id, req.version)
    return _sbom_to_response(row)


@router.post("/verify-binary")
async def verify_binary(
    req: BinaryVerifyRequest,
    db: Session = Depends(get_db),
):
    """
    Verify agent binary against the SBOM registry.
    Records the attestation result per node.
    """
    sbom = db.query(SBOMEntry).filter(SBOMEntry.version == req.agent_version).first()
    if not sbom:
        logger.warning("⚠️  Unknown agent version %s from node %s", req.agent_version, req.node_id)
        return {
            "status": "unknown_version",
            "integrity": "unverifiable",
            "node_id": req.node_id,
            "agent_version": req.agent_version,
        }

    checksums_match = (sbom.checksum_sha256 == req.checksum_sha256)
    att_status = "verified" if checksums_match else "mismatch"

    if not checksums_match:
        logger.warning(
            "🚨 BINARY INTEGRITY FAILURE: node=%s version=%s expected=%s got=%s",
            req.node_id, req.agent_version, sbom.checksum_sha256, req.checksum_sha256,
        )

    # Upsert attestation record for this node
    existing_att = (
        db.query(NodeBinaryAttestation)
        .filter(
            NodeBinaryAttestation.node_id == req.node_id,
            NodeBinaryAttestation.sbom_id == sbom.id,
        )
        .first()
    )
    if existing_att:
        existing_att.checksum_sha256 = req.checksum_sha256
        existing_att.status = att_status
        existing_att.verified_at = datetime.utcnow()
    else:
        db.add(NodeBinaryAttestation(
            id=f"att-{uuid.uuid4().hex[:8]}",
            node_id=req.node_id,
            mesh_id=req.mesh_id,
            sbom_id=sbom.id,
            agent_version=req.agent_version,
            checksum_sha256=req.checksum_sha256,
            status=att_status,
            verified_at=datetime.utcnow(),
        ))
    db.commit()

    return {
        "status": att_status,
        "node_id": req.node_id,
        "agent_version": req.agent_version,
        "integrity": "valid" if checksums_match else "compromised",
        "pqc_compliant": checksums_match,
        "sbom_id": sbom.id,
    }


@router.get("/attestations/{node_id}")
async def get_node_attestations(
    node_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """Get binary attestation history for a specific node."""
    records = (
        db.query(NodeBinaryAttestation)
        .filter(NodeBinaryAttestation.node_id == node_id)
        .order_by(NodeBinaryAttestation.verified_at.desc())
        .all()
    )
    return {
        "node_id": node_id,
        "attestations": [
            {
                "id": r.id,
                "agent_version": r.agent_version,
                "status": r.status,
                "verified_at": r.verified_at.isoformat() if r.verified_at else None,
            }
            for r in records
        ],
    }


@router.get("/mesh-attestation-report/{mesh_id}")
async def get_mesh_attestation_report(
    mesh_id: str,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """
    Aggregate attestation status across all nodes in a mesh.
    Returns counts of verified, mismatch, and unknown nodes.
    """
    records = (
        db.query(NodeBinaryAttestation)
        .filter(NodeBinaryAttestation.mesh_id == mesh_id)
        .all()
    )

    counts: Dict[str, int] = {"verified": 0, "mismatch": 0, "unknown": 0}
    for r in records:
        counts[r.status] = counts.get(r.status, 0) + 1

    compromised_nodes = [r.node_id for r in records if r.status == "mismatch"]

    return {
        "mesh_id": mesh_id,
        "total_attested": len(records),
        "summary": counts,
        "compromised_nodes": compromised_nodes,
        "integrity": "clean" if not compromised_nodes else "compromised",
    }
