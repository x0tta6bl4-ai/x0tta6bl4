"""
MaaS Compatibility Endpoints
============================

Backwards-compatible aliases for historical client paths that are no longer
first-class in the canonical MaaS v1 router layout.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.api import maas_legacy
from src.api.maas_auth import get_current_user_from_maas, register as register_v1
from src.api.maas_auth_models import TokenResponse, UserRegisterRequest
from src.api.maas_billing import create_subscription_session
from src.database import User, get_db

router = APIRouter(tags=["MaaS Compatibility"])


@router.post(
    "/api/v3/maas/auth/register",
    response_model=TokenResponse,
    include_in_schema=False,
)
async def register_v3_alias(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Alias /api/v3/maas/auth/register -> /api/v1/maas/auth/register."""
    return await register_v1(req, db)


@router.post(
    "/api/v1/maas/mesh/deploy",
    response_model=maas_legacy.MeshDeployResponse,
    include_in_schema=False,
)
async def deploy_mesh_alias(
    req: maas_legacy.MeshDeployRequest,
    current_user: User = Depends(maas_legacy.require_permission("mesh:create")),
    db: Session = Depends(get_db),
):
    """Alias /api/v1/maas/mesh/deploy -> /api/v1/maas/deploy."""
    return await maas_legacy.deploy_mesh(req=req, current_user=current_user, db=db)


@router.post("/api/v1/maas/billing/pay", include_in_schema=False)
async def billing_pay_alias(
    request: Request,
    plan: str = Query(..., pattern="^(starter|pro|enterprise)$"),
    method: str = Query("stripe", pattern="^(stripe|crypto)$"),
    current_user: User = Depends(get_current_user_from_maas),
    db: Session = Depends(get_db),
):
    """
    Alias /api/v1/maas/billing/pay -> /api/v1/maas/billing/subscriptions/checkout.

    The compatibility endpoint keeps historical query-based input shape.
    """
    if method == "crypto":
        raise HTTPException(
            status_code=501,
            detail=(
                "Crypto billing is not enabled in this deployment. "
                "Use method=stripe or configure a crypto billing backend."
            ),
        )

    payload = await create_subscription_session(
        plan=plan,
        request=request,
        current_user=current_user,
        db=db,
    )
    checkout_url = payload.get("url") if isinstance(payload, dict) else None

    return {
        "payment_url": checkout_url,
        "status": "created",
        "method": method,
        "plan": plan,
    }
