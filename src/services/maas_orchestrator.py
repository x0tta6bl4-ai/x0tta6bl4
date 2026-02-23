import logging
import json
from sqlalchemy.orm import Session
from src.database import MarketplaceListing, MarketplaceEscrow, MeshInstance
from src.api.maas_playbooks import create_playbook, PlaybookCreateRequest, PlaybookAction

logger = logging.getLogger(__name__)

class MaaSOrchestrator:
    """
    Orchestrates the lifecycle of rented infrastructure.
    Binds Marketplace events to Playbook execution.
    """
    
    @staticmethod
    async def provision_rented_node(db: Session, listing_id: str, renter_id: str, mesh_id: str):
        """
        Generates a signed playbook to move a rented node into the renter's mesh.
        """
        listing = db.query(MarketplaceListing).filter(MarketplaceListing.id == listing_id).first()
        mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
        
        if not listing or not mesh:
            logger.error(f"Failed to provision: Listing {listing_id} or Mesh {mesh_id} not found")
            return False

        logger.info(f"🚚 Orchestrating node {listing.node_id} migration to mesh {mesh_id}")

        # Define actions for the node
        actions = [
            PlaybookAction(
                action="update_config",
                params={
                    "mesh_id": mesh_id,
                    "join_token": mesh.join_token,
                    "role": "rented_worker",
                    "sla_priority": "high"
                }
            ),
            PlaybookAction(action="restart", params={"reason": "mesh_migration"})
        ]

        # Use the existing internal logic to create a signed playbook
        try:
            req = PlaybookCreateRequest(
                name=f"MaaS Migration: {listing.node_id} -> {mesh_id}",
                target_nodes=[listing.node_id],
                actions=actions,
                expires_in_sec=3600
            )
            
            from src.api.maas_playbooks import create_playbook
            # We must mock a User object for create_playbook
            from src.database import User
            system_actor = db.query(User).filter(User.id == listing.owner_id).first()
            
            await create_playbook(
                mesh_id=listing.mesh_id or "system-management",
                req=req,
                current_user=system_actor,
                db=db
            )
            return True
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return False

maas_orchestrator = MaaSOrchestrator()
