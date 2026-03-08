"""
MaaS Pilot Endpoints - Pilot program signup and management.

Provides REST API endpoints for pilot customer onboarding,
mesh instance creation, and billing setup.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from src.database import MeshInstance, User, get_db
from ..auth import get_current_user, UserContext
from ..services import MeshService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pilot", tags=["pilot"])


class PilotSignupRequest(BaseModel):
    """Request model for pilot signup."""
    email: EmailStr = Field(..., description="Pilot customer email")
    company: Optional[str] = Field(None, description="Company name")
    contact_name: str = Field(..., description="Contact person name")
    expected_users: int = Field(5, description="Expected number of users", ge=1, le=50)
    use_case: str = Field(..., description="Pilot use case description")
    region: str = Field("global", description="Preferred region")


class PilotSignupResponse(BaseModel):
    """Response model for pilot signup."""
    pilot_id: str
    user_id: str
    mesh_id: str
    onboarding_url: str
    billing_setup_url: Optional[str] = None
    status: str = "pending_setup"


class PilotStatusResponse(BaseModel):
    """Response model for pilot status."""
    pilot_id: str
    status: str
    mesh_id: str
    user_count: int
    billing_status: str
    created_at: str


@router.post(
    "/signup",
    response_model=PilotSignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Pilot program signup",
    description="Register a new pilot customer with mesh instance creation.",
)
async def pilot_signup(
    request: PilotSignupRequest,
    db: Session = Depends(get_db),
) -> PilotSignupResponse:
    """
    Sign up a new pilot customer.

    Creates user account, mesh instance, and initiates billing setup.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Generate IDs
    pilot_id = str(uuid.uuid4())[:8]
    user_id = f"pilot-{pilot_id}"
    mesh_id = f"pilot-mesh-{pilot_id}"

    try:
        # Create user account
        new_user = User(
            id=user_id,
            email=request.email,
            full_name=request.contact_name,
            company=request.company,
            plan="pilot",
            role="user",
        )
        db.add(new_user)

        # Create mesh instance
        join_token = str(uuid.uuid4())
        mesh = MeshInstance(
            id=mesh_id,
            name=f"Pilot Mesh - {request.company or request.contact_name}",
            owner_id=user_id,
            plan="pilot",
            region=request.region,
            nodes=request.expected_users,
            join_token=join_token,
        )
        db.add(mesh)

        db.commit()

        logger.info(f"Pilot signup completed: {pilot_id} for {request.email}")

        # In production, this would trigger:
        # - Email with onboarding instructions
        # - Stripe checkout session creation
        # - Pilot support ticket creation

        return PilotSignupResponse(
            pilot_id=pilot_id,
            user_id=user_id,
            mesh_id=mesh_id,
            onboarding_url=f"/pilot/{pilot_id}/onboarding",
            billing_setup_url=f"/pilot/{pilot_id}/billing",
            status="pending_setup",
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Pilot signup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create pilot account",
        )


@router.get(
    "/{pilot_id}/status",
    response_model=PilotStatusResponse,
    summary="Get pilot status",
    description="Get the current status of a pilot program.",
)
async def get_pilot_status(
    pilot_id: str,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PilotStatusResponse:
    """
    Get pilot status.

    Only accessible by the pilot customer or admin.
    """
    user_id = f"pilot-{pilot_id}"

    # Check permissions
    if user.user_id != user_id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    # Get user and mesh
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pilot not found",
        )

    mesh = db.query(MeshInstance).filter(MeshInstance.owner_id == user_id).first()

    # Determine billing status
    billing_status = "not_setup"
    if db_user.stripe_subscription_id:
        billing_status = "active"
    elif db_user.stripe_customer_id:
        billing_status = "customer_created"

    return PilotStatusResponse(
        pilot_id=pilot_id,
        status="active" if mesh and mesh.status == "active" else "setup",
        mesh_id=mesh.id if mesh else None,
        user_count=mesh.nodes if mesh else 0,
        billing_status=billing_status,
        created_at=db_user.created_at.isoformat() if db_user.created_at else None,
    )


@router.post(
    "/{pilot_id}/activate",
    summary="Activate pilot",
    description="Mark pilot as active and ready for production use.",
)
async def activate_pilot(
    pilot_id: str,
    user: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Activate pilot instance.

    Only accessible by admin.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    user_id = f"pilot-{pilot_id}"

    mesh = db.query(MeshInstance).filter(MeshInstance.owner_id == user_id).first()
    if not mesh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pilot mesh not found",
        )

    mesh.status = "active"
    db.commit()

    logger.info(f"Pilot activated: {pilot_id}")

    return {
        "message": "Pilot activated successfully",
        "pilot_id": pilot_id,
        "mesh_id": mesh.id,
    }


__all__ = ["router"]
