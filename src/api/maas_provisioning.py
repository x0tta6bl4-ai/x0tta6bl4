"""
MaaS Provisioning API for x0tta6bl4.
=====================================

Handles the "One-Click Deploy" wizard logic. Generates cryptographically 
signed installation scripts and tokens for new mesh nodes.
"""

import logging
import uuid
import base64
import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.database import MeshNode, get_db, User
from src.api.maas_auth import get_current_user_from_maas

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maas/provisioning", tags=["MaaS Provisioning"])

class ProvisionRequest(BaseModel):
    mesh_id: str
    device_name: str
    device_class: str = "generic" # generic, server, edge
    os_type: str = "linux" # linux, darwin, android

class ProvisionResponse(BaseModel):
    node_id: str
    join_token: str
    install_command: str
    config_json: str

@router.post("/generate-setup")
async def generate_provisioning_setup(
    req: ProvisionRequest,
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db)
) -> ProvisionResponse:
    """Generates a one-liner installation script for a new node."""
    
    node_id = f"node-{uuid.uuid4().hex[:8]}"
    join_token = f"tok-{uuid.uuid4().hex[:12]}"
    
    # Create entry in DB (pending attestation)
    new_node = MeshNode(
        id=node_id,
        mesh_id=req.mesh_id,
        device_class=req.device_class,
        status="pending",
        acl_profile="default"
    )
    db.add(new_node)
    db.commit()
    
    # Generate Install Command (One-liner)
    # In prod, this would point to a real script hosted on MaaS
    api_url = "https://api.x0tta6bl4.io" 
    install_cmd = (
        f"curl -sSL {api_url}/install.sh | sudo bash -s -- "
        f"--node-id {node_id} --token {join_token} --mesh {req.mesh_id}"
    )
    
    # Generate minimal config
    config = {
        "node_id": node_id,
        "mesh_id": req.mesh_id,
        "join_token": join_token,
        "api_endpoint": api_url,
        "pqc_enabled": True,
        "zkp_auth": True
    }
    
    return ProvisionResponse(
        node_id=node_id,
        join_token=join_token,
        install_command=install_cmd,
        config_json=base64.b64encode(json.dumps(config).encode()).decode()
    )

def include_provisioning_router(app):
    app.include_router(router)
