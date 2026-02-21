"""
MaaS Billing Endpoints - Billing and invoicing.

Provides REST API endpoints for billing webhooks and usage reports.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from ..auth import UserContext, get_current_user
from ..billing_helpers import (
    generate_invoice,
    get_idempotency_store,
    verify_webhook_with_timestamp,
    with_idempotency,
)
from ..models import BillingWebhookRequest
from ..services import BillingService, UsageMeteringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# Service instances
_billing_service: Optional[BillingService] = None
_usage_service: Optional[UsageMeteringService] = None


def get_billing_service() -> BillingService:
    """Get or create the billing service."""
    global _billing_service
    if _billing_service is None:
        _billing_service = BillingService()
    return _billing_service


def get_usage_service() -> UsageMeteringService:
    """Get or create the usage metering service."""
    global _usage_service
    if _usage_service is None:
        _usage_service = UsageMeteringService()
    return _usage_service


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Handle billing webhook",
    description="Receive and process billing webhooks from payment provider.",
)
async def billing_webhook(
    request: Request,
    x_signature: str = Header(..., alias="X-Signature"),
    x_timestamp: str = Header(..., alias="X-Timestamp"),
    x_event_id: str = Header(..., alias="X-Event-Id"),
) -> Dict[str, Any]:
    """
    Handle billing webhook from payment provider.

    Verifies HMAC signature and processes the event idempotently.
    """
    billing = get_billing_service()

    # Read raw body for signature verification
    body = await request.body()

    # Verify signature
    if not verify_webhook_with_timestamp(
        payload=body,
        signature=x_signature,
        timestamp=x_timestamp,
        secret=billing.webhook_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    # Parse JSON body
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    event_type = data.get("type", "unknown")

    # Process with idempotency
    async def process():
        return await billing.process_webhook(
            event_type=event_type,
            event_data=data.get("data", {}),
            event_id=x_event_id,
        )

    result = await with_idempotency(x_event_id, process)

    return result


@router.get(
    "/usage/{mesh_id}",
    summary="Get usage report",
    description="Get usage metrics for a mesh.",
)
async def get_usage_report(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get usage report for a mesh."""
    from ..auth import require_mesh_access

    # Check access
    await require_mesh_access(mesh_id, user)

    usage = get_usage_service()
    return usage.get_usage_report(mesh_id)


@router.get(
    "/estimate",
    summary="Estimate monthly cost",
    description="Estimate monthly cost for a mesh configuration.",
)
async def estimate_cost(
    node_count: int = Query(..., ge=1, le=1000),
    node_type: str = Query("standard", description="Node type"),
    plan: str = Query("pro", description="Subscription plan"),
    region: str = Query("us-east-1", description="Deployment region"),
) -> Dict[str, Any]:
    """Estimate monthly cost for a mesh configuration."""
    from ..billing_helpers import (
        calculate_mesh_cost,
        estimate_monthly_cost,
        format_currency,
    )

    monthly = estimate_monthly_cost(node_count, node_type, plan, region)
    hourly = calculate_mesh_cost(node_count, node_type, plan, region, 1)

    return {
        "node_count": node_count,
        "node_type": node_type,
        "plan": plan,
        "region": region,
        "hourly_cost": format_currency(hourly),
        "monthly_cost": format_currency(monthly),
        "monthly_cost_raw": str(monthly),
    }


@router.get(
    "/plans",
    summary="List available plans",
    description="Get available subscription plans and their limits.",
)
async def list_plans() -> List[Dict[str, Any]]:
    """List available subscription plans."""
    from ..constants import PLAN_ALIASES, PLAN_REQUEST_LIMITS

    plans = []
    for plan_name in ["free", "pro", "enterprise"]:
        billing = get_billing_service()
        limits = billing.get_plan_limits(plan_name)

        plans.append({
            "name": plan_name,
            "display_name": plan_name.title(),
            "limits": limits,
        })

    return plans


@router.post(
    "/invoice/{mesh_id}",
    summary="Generate invoice",
    description="Generate an invoice for mesh usage.",
)
async def create_invoice(
    mesh_id: str,
    user: UserContext = Depends(get_current_user),
    hours: float = Query(730, description="Billing period in hours"),
) -> Dict[str, Any]:
    """Generate an invoice for mesh usage."""
    from ..auth import require_mesh_access
    from ..registry import get_mesh

    # Check access
    await require_mesh_access(mesh_id, user)

    instance = get_mesh(mesh_id)
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mesh {mesh_id} not found",
        )

    # Generate invoice
    invoice = generate_invoice(
        customer_id=user.user_id,
        mesh_usage=[{
            "mesh_id": mesh_id,
            "node_count": len(instance.node_instances),
            "node_type": "standard",  # Would come from instance config
            "plan": instance.plan,
            "region": instance.region,
            "hours": hours,
        }],
    )

    return invoice.to_dict()


@router.get(
    "/limits",
    summary="Get plan limits",
    description="Get limits for the current user's plan.",
)
async def get_limits(
    user: UserContext = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get limits for the user's current plan."""
    billing = get_billing_service()
    return billing.get_plan_limits(user.plan)


__all__ = ["router"]
