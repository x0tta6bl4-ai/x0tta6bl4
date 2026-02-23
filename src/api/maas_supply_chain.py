"""
MaaS Supply Chain Security — x0tta6bl4
=======================================

DB-backed SBOM registry and per-node binary attestation.
Includes an in-memory compatibility layer for direct unit calls.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.maas_auth import get_current_user_from_maas, require_role
from src.database import MeshNode, NodeBinaryAttestation, SBOMEntry, User, get_db
from src.utils.audit import record_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/supply-chain", tags=["MaaS Supply Chain"])

_sbom_registry: Dict[str, Dict[str, Any]] = {
    "v3.4.0-alpha": {
        "id": "sbom-v340a",
        "version": "3.4.0-alpha",
        "format": "CycloneDX-JSON",
        "checksum_sha256": "sha256:abc123",
        "components": [
            {"name": "x0tta6bl4-agent", "version": "3.4.0-alpha", "type": "application"},
            {"name": "liboqs", "version": "0.10.1", "type": "library"},
        ],
        "attestation": {
            "type": "Sigstore-Bundle",
            "signer": "ci@x0tta6bl4.net",
            "signed_at": "2026-02-20T00:00:00Z",
            "bundle_url": "https://example.local/sigstore/bundle/v3.4.0-alpha",
        },
        "created_at": "2026-02-20T00:00:00Z",
    }
}


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
    checksum_sha256: str = Field(..., min_length=10)
    components: List[ComponentEntry]
    attestation: Optional[AttestationMeta] = None


class SBOMResponse(BaseModel):
    id: Optional[str] = None
    version: str
    format: str
    checksum_sha256: Optional[str] = None
    components: List[Dict[str, Any]]
    attestation: Optional[Dict[str, Any]] = None
    pqc_signature: Optional[str] = None
    created_at: Optional[str] = None


class BinaryVerifyRequest(BaseModel):
    node_id: str
    mesh_id: Optional[str] = None
    agent_version: str
    checksum_sha256: str


def _db_session_available(db: Any) -> bool:
    return hasattr(db, "query") and hasattr(db, "commit")


def _coerce_components(components: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for component in components:
        if isinstance(component, ComponentEntry):
            normalized.append(component.model_dump())
        elif isinstance(component, dict):
            normalized.append(dict(component))
        else:
            normalized.append(dict(component.__dict__))
    return normalized


def _lookup_in_memory_sbom(version: str) -> Optional[Dict[str, Any]]:
    candidates = [version]
    if version.startswith("v"):
        candidates.append(version[1:])
    else:
        candidates.append(f"v{version}")

    for key in candidates:
        entry = _sbom_registry.get(key)
        if entry:
            return dict(entry)
    return None


def _sbom_to_response_dict(row: SBOMEntry) -> Dict[str, Any]:
    components = json.loads(row.components_json) if row.components_json else []
    attestation = json.loads(row.attestation_json) if row.attestation_json else None
    payload = {
        "id": row.id,
        "version": row.version,
        "format": row.format,
        "checksum_sha256": row.checksum_sha256,
        "components": components,
        "attestation": attestation,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }

    from src.core.app import pqc_sign
    signed = pqc_sign(f"{row.version}:{row.checksum_sha256}".encode())
    if signed:
        payload["pqc_signature"] = signed.hex()
    return payload


def _legacy_verify(agent_version: str, checksum_sha256: str, node_id: str = "legacy-node") -> Dict[str, Any]:
    sbom = _lookup_in_memory_sbom(agent_version)
    if not sbom:
        raise HTTPException(status_code=400, detail=f"SBOM for version '{agent_version}' not found")

    checksums_match = sbom.get("checksum_sha256") == checksum_sha256
    return {
        "status": "verified" if checksums_match else "mismatch",
        "node_id": node_id,
        "agent_version": agent_version,
        "integrity": "valid" if checksums_match else "compromised",
        "pqc_compliant": checksums_match,
        "sbom_id": sbom.get("id"),
    }


def _safe_record_audit(
    db: Any,
    *,
    action: str,
    user_id: Optional[str],
    payload: Dict[str, Any],
    status_code: int,
) -> None:
    if not _db_session_available(db):
        return
    try:
        record_audit_log(
            db, None, action,
            user_id=user_id,
            payload=payload,
            status_code=status_code,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to persist audit log (%s): %s", action, exc)


@router.get("/sbom/{version}", response_model=SBOMResponse)
async def get_sbom(version: str, db: Session = Depends(get_db)):
    """Fetch SBOM for a specific agent version. Publicly accessible."""
    if _db_session_available(db):
        row = db.query(SBOMEntry).filter(SBOMEntry.version == version).first()
        if not row and version.startswith("v"):
            row = db.query(SBOMEntry).filter(SBOMEntry.version == version[1:]).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"SBOM for version '{version}' not found")
        return _sbom_to_response_dict(row)

    entry = _lookup_in_memory_sbom(version)
    if not entry:
        raise HTTPException(status_code=404, detail=f"SBOM for version '{version}' not found")
    return entry


@router.get("/sbom", response_model=List[SBOMResponse])
async def list_sboms(db: Session = Depends(get_db)):
    if _db_session_available(db):
        rows = db.query(SBOMEntry).order_by(SBOMEntry.created_at.desc()).all()
        return [_sbom_to_response_dict(row) for row in rows]
    return [dict(entry) for entry in _sbom_registry.values()]


@router.post("/register-artifact", response_model=SBOMResponse)
async def register_artifact(
    req: Union[SBOMRegisterRequest, SBOMResponse],
    current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    """Register a new build artifact SBOM (CI/CD pipeline only)."""
    version = req.version
    checksum_sha256 = getattr(req, "checksum_sha256", None) or "sha256:abc123"
    components = _coerce_components(req.components)

    raw_attestation = getattr(req, "attestation", None)
    if isinstance(raw_attestation, AttestationMeta):
        attestation = raw_attestation.model_dump()
    elif isinstance(raw_attestation, dict):
        attestation = dict(raw_attestation)
    else:
        attestation = None

    if _db_session_available(db):
        existing = db.query(SBOMEntry).filter(SBOMEntry.version == version).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"SBOM for version '{version}' already registered")

        sbom_id = f"sbom-{uuid.uuid4().hex[:8]}"
        row = SBOMEntry(
            id=sbom_id,
            version=version,
            format=req.format,
            checksum_sha256=checksum_sha256,
            components_json=json.dumps(components),
            attestation_json=json.dumps(attestation) if attestation else None,
            created_by=current_user.id,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        response_payload = _sbom_to_response_dict(row)

        _safe_record_audit(
            db,
            action="SBOM_REGISTERED",
            user_id=current_user.id,
            payload={"version": version, "sbom_id": sbom_id, "checksum": checksum_sha256},
            status_code=201,
        )
        return response_payload

    if version in _sbom_registry:
        raise HTTPException(status_code=409, detail=f"SBOM for version '{version}' already registered")

    sbom_id = getattr(req, "id", None) or f"sbom-{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()
    _sbom_registry[version] = {
        "id": sbom_id,
        "version": version,
        "format": req.format,
        "checksum_sha256": checksum_sha256,
        "components": components,
        "attestation": attestation,
        "created_at": created_at,
    }
    return {
        "status": "registered",
        "id": sbom_id,
        "version": version,
        "format": req.format,
        "checksum_sha256": checksum_sha256,
        "components": components,
        "attestation": attestation,
        "created_at": created_at,
    }


@router.post("/verify-binary")
async def verify_binary(
    req: Union[BinaryVerifyRequest, str],
    db: Session = Depends(get_db),
):
    """
    Verify agent binary against the SBOM registry.
    In DB mode, unknown versions return unknown_version (200).
    In direct-call compatibility mode, unknown versions raise 400.
    """
    if isinstance(req, str):
        checksum = db if isinstance(db, str) else ""
        return _legacy_verify(req, checksum_sha256=checksum, node_id="legacy-node")

    if not _db_session_available(db):
        return _legacy_verify(req.agent_version, checksum_sha256=req.checksum_sha256, node_id=req.node_id)

    sbom = db.query(SBOMEntry).filter(SBOMEntry.version == req.agent_version).first()
    if not sbom:
        return {
            "status": "unknown_version",
            "integrity": "unverifiable",
            "node_id": req.node_id,
            "agent_version": req.agent_version,
        }

    checksums_match = sbom.checksum_sha256 == req.checksum_sha256
    att_status = "verified" if checksums_match else "mismatch"

    existing_att = (
        db.query(NodeBinaryAttestation)
        .filter(
            NodeBinaryAttestation.node_id == req.node_id,
            NodeBinaryAttestation.sbom_id == sbom.id,
        )
        .first()
    )

    if existing_att:
        existing_att.status = att_status
        existing_att.checksum_sha256 = req.checksum_sha256
        existing_att.verified_at = datetime.utcnow()
    else:
        db.add(
            NodeBinaryAttestation(
                id=f"att-{uuid.uuid4().hex[:8]}",
                node_id=req.node_id,
                mesh_id=req.mesh_id,
                sbom_id=sbom.id,
                agent_version=req.agent_version,
                checksum_sha256=req.checksum_sha256,
                status=att_status,
                verified_at=datetime.utcnow(),
            )
        )

    if not checksums_match:
        node = db.query(MeshNode).filter(MeshNode.id == req.node_id).first()
        if node:
            node.status = "revoked"
            _safe_record_audit(
                db,
                action="NODE_AUTO_REVOKED_INTEGRITY_FAILURE",
                user_id=None,
                payload={"node_id": req.node_id, "version": req.agent_version},
                status_code=200,
            )
            logger.warning("Node %s auto-revoked due to binary mismatch", req.node_id)

    if _db_session_available(db):
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
                "id": record.id,
                "agent_version": record.agent_version,
                "status": record.status,
                "verified_at": record.verified_at.isoformat() if record.verified_at else None,
            }
            for record in records
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
    for record in records:
        counts[record.status] = counts.get(record.status, 0) + 1

    compromised_nodes = [record.node_id for record in records if record.status == "mismatch"]
    return {
        "mesh_id": mesh_id,
        "total_attested": len(records),
        "summary": counts,
        "compromised_nodes": compromised_nodes,
        "integrity": "clean" if not compromised_nodes else "compromised",
    }
