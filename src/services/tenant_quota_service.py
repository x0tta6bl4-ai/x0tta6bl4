"""
Tenant Quota Service — x0tta6bl4
=================================

Enforcement of service limits (node count, bandwidth, features) 
based on the tenant's current subscription plan.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from src.database import MeshInstance, MeshNode, User

logger = logging.getLogger(__name__)

# Plan Definition
PLAN_LIMITS = {
    "free": {"max_nodes": 1, "pqc_allowed": False, "ha_enabled": False},
    "trial": {"max_nodes": 3, "pqc_allowed": True, "ha_enabled": False},
    "pilot": {"max_nodes": 5, "pqc_allowed": True, "ha_enabled": True},
    "standard": {"max_nodes": 50, "pqc_allowed": True, "ha_enabled": True},
    "enterprise": {"max_nodes": 9999, "pqc_allowed": True, "ha_enabled": True},
}

class TenantQuotaService:
    def __init__(self, db: Session):
        self.db = db

    def _get_tenant_plan(self, tenant_id: str) -> str:
        """Retrieve tenant's plan from the primary owner (User)."""
        # Multi-tenancy assumption: tenant_id maps to a User or a group with a plan
        user = self.db.query(User).filter(User.tenant_id == tenant_id, User.role == "admin").first()
        if not user:
            # Fallback for individual users not in a tenant group
            user = self.db.query(User).filter(User.id == tenant_id).first()
        
        return (user.plan or "free").lower() if user else "free"

    def check_node_quota(self, tenant_id: str) -> bool:
        """
        Verify if the tenant can add a new node.
        Returns True if within limits, False otherwise.
        """
        plan = self._get_tenant_plan(tenant_id)
        limit = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["max_nodes"]
        
        current_count = self.db.query(MeshNode).filter(MeshNode.tenant_id == tenant_id).count()
        
        logger.info(f"Quota check for tenant {tenant_id}: current={current_count}, limit={limit}, plan={plan}")
        
        if current_count >= limit:
            logger.warning(f"Tenant {tenant_id} reached node quota ({current_count}/{limit}) for plan '{plan}'")
            return False
        return True

    def check_pqc_allowed(self, tenant_id: str) -> bool:
        """Verify if PQC features are unlocked for this plan."""
        plan = self._get_tenant_plan(tenant_id)
        return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])["pqc_allowed"]

    def get_quota_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get summary of current usage vs limits for a tenant."""
        plan = self._get_tenant_plan(tenant_id)
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        
        current_nodes = self.db.query(MeshNode).filter(MeshNode.tenant_id == tenant_id).count()
        
        return {
            "tenant_id": tenant_id,
            "plan": plan,
            "usage": {
                "nodes": current_nodes,
                "max_nodes": limits["max_nodes"],
                "node_utilization": round((current_nodes / limits["max_nodes"]) * 100, 1) if limits["max_nodes"] > 0 else 100
            },
            "unlocked_features": {
                "pqc": limits["pqc_allowed"],
                "high_availability": limits["ha_enabled"]
            }
        }

    def update_tenant_plan(self, tenant_id: str, new_plan: str) -> bool:
        """Update the plan for a tenant (applied to admin user)."""
        if new_plan not in PLAN_LIMITS:
            logger.error(f"Invalid plan name: {new_plan}")
            return False
            
        user = self.db.query(User).filter(User.tenant_id == tenant_id, User.role == "admin").first()
        if not user:
            user = self.db.query(User).filter(User.id == tenant_id).first()
            
        if user:
            user.plan = new_plan
            self.db.commit()
            logger.info(f"Tenant {tenant_id} upgraded to plan '{new_plan}'")
            return True
        return False
