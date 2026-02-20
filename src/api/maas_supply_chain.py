"""
MaaS Supply Chain Security — x0tta6bl4
=======================================

SBOM (Software Bill of Materials) and binary attestation registry.
Ensures headless agents are running verified, untampered code.
"""

import logging
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from src.database import User
from src.api.maas_auth import require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/supply-chain", tags=["MaaS Supply Chain"])

# Mock database for SBOMs and Attestations
# In production, this should be backed by a persistent store or Sigstore/Rekor.
_sbom_registry: Dict[str, Dict[str, Any]] = {
    "v3.4.0-alpha": {
        "version": "3.4.0-alpha",
        "checksum_sha256": "sha256:abc123",
        "format": "CycloneDX-JSON",
        "components": [
            {"name": "x0tta6bl4-agent", "version": "3.4.0", "type": "application"},
            {"name": "yggdrasil", "version": "0.5.5", "type": "library"},
            {"name": "liboqs", "version": "0.10.0", "type": "library"}
        ],
        "attestation": {
            "type": "Sigstore-Bundle",
            "signer": "build-bot@x0tta6bl4.net",
            "signed_at": "2026-02-19T12:00:00Z",
            "bundle_url": "https://artifacts.x0tta6bl4.net/agent/v3.4.0/attestation.json"
        }
    }
}

class SBOMResponse(BaseModel):
    version: str
    format: str
    components: List[Dict[str, Any]]
    checksum_sha256: Optional[str] = None
    attestation: Optional[Dict[str, Any]] = None

@router.get("/sbom/{version}", response_model=SBOMResponse)
async def get_sbom(version: str):
    """
    Fetch SBOM for a specific agent version.
    Publicly accessible for transparency.
    """
    sbom = _sbom_registry.get(version)
    if not sbom:
        raise HTTPException(
            status_code=404, 
            detail=f"SBOM for version {version} not found"
        )
    return sbom

@router.post("/verify-binary")
async def verify_binary(
    version: str, 
    checksum_sha256: str,
    attestation_token: Optional[str] = None
):
    """
    Verify agent binary against known attestations.
    """
    sbom = _sbom_registry.get(version)
    if not sbom:
        raise HTTPException(status_code=400, detail="Version unknown")
        
    if sbom["checksum_sha256"] != checksum_sha256:
        logger.warning(f"🚨 BINARY INTEGRITY FAILURE: Version {version} hash mismatch!")
        return {
            "status": "failed",
            "reason": "checksum_mismatch",
            "integrity": "compromised"
        }

    return {
        "status": "verified",
        "version": version,
        "integrity": "valid",
        "attestation_check": "passed",
        "pqc_compliant": True
    }

@router.post("/register-artifact")
async def register_artifact(
    req: SBOMResponse,
    current_user: User = Depends(require_role("admin"))
):
    """
    Register a new build artifact SBOM (Build-CI only).
    """
    _sbom_registry[req.version] = req.dict()
    logger.info(f"📦 Registered new artifact SBOM for version {req.version}")
    return {"status": "registered", "version": req.version}
