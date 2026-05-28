"""
MaaS Compatibility Endpoints
============================

Backwards-compatible aliases for historical client paths that are no longer
first-class in the canonical MaaS v1 router layout.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.api import maas_legacy
from src.api.maas_auth import get_current_user_from_maas, register as register_v1
from src.api.maas_auth_models import TokenResponse, UserRegisterRequest
from src.api.maas_billing import create_subscription_session
from src.core.reliability_policy import mark_degraded_dependency
from src.database import User, get_db

router = APIRouter(tags=["MaaS Compatibility"])


def _compat_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "add", "commit"))


def _compat_auth_alias_available() -> bool:
    return callable(register_v1) and callable(get_current_user_from_maas)


def _compat_legacy_deploy_available() -> bool:
    return (
        callable(getattr(maas_legacy, "deploy_mesh", None))
        and callable(getattr(maas_legacy, "require_permission", None))
        and hasattr(maas_legacy, "MeshDeployRequest")
        and hasattr(maas_legacy, "MeshDeployResponse")
    )


def _compat_billing_alias_available() -> bool:
    return callable(create_subscription_session)


def _compat_models_available() -> bool:
    return (
        callable(UserRegisterRequest)
        and callable(TokenResponse)
        and hasattr(User, "id")
        and hasattr(User, "api_key")
    )


def _compat_readiness_status(db: Any) -> Dict[str, Any]:
    compat_db_ready = _compat_db_session_available(db)
    auth_alias_ready = _compat_auth_alias_available()
    legacy_deploy_ready = _compat_legacy_deploy_available()
    billing_alias_ready = _compat_billing_alias_available()
    compat_models_ready = _compat_models_available()
    compat_runtime_ready = (
        compat_db_ready
        and auth_alias_ready
        and legacy_deploy_ready
        and billing_alias_ready
        and compat_models_ready
    )

    degraded_dependencies = []
    if not compat_db_ready:
        degraded_dependencies.append("database")
    if not auth_alias_ready:
        degraded_dependencies.append("auth_alias")
    if not legacy_deploy_ready:
        degraded_dependencies.append("legacy_deploy_alias")
    if not billing_alias_ready:
        degraded_dependencies.append("billing_alias")
    if not compat_models_ready:
        degraded_dependencies.append("compat_models")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "always",
        "route_present_in_light_mode": True,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "compat_runtime_ready": compat_runtime_ready,
        "compat_db_ready": compat_db_ready,
        "auth_alias_ready": auth_alias_ready,
        "legacy_deploy_ready": legacy_deploy_ready,
        "billing_alias_ready": billing_alias_ready,
        "compat_models_ready": compat_models_ready,
        "route_precedence": {
            "router_prefix": "",
            "absolute_paths": [
                "/api/v3/maas/auth/register",
                "/api/v1/maas/mesh/deploy",
                "/api/v1/maas/billing/pay",
            ],
            "shadowed_by_legacy": [],
            "boundary": (
                "Compatibility routes are absolute aliases on a prefixless router. "
                "They delegate to canonical auth, legacy deploy, and MaaS billing "
                "handlers instead of owning separate runtime state."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "backing_state": {
            "database": (
                "Aliases pass the SQLAlchemy session through to canonical auth, "
                "legacy deploy, and billing handlers."
            ),
            "auth_alias": (
                "The v3 register alias delegates to maas_auth.register and uses "
                "get_current_user_from_maas for authenticated billing alias calls."
            ),
            "legacy_deploy_alias": (
                "The mesh/deploy alias depends on maas_legacy deploy request, "
                "response, permission, and deploy_mesh surfaces."
            ),
            "billing_alias": (
                "The billing/pay alias delegates to create_subscription_session "
                "for stripe checkout and rejects crypto locally."
            ),
            "compat_models": (
                "Compatibility response validation depends on auth request/response "
                "models and User identity/API-key fields."
            ),
        },
        "claim_boundary": (
            "Compatibility readiness proves alias route availability and delegated "
            "function surfaces only. It does not register a user, deploy a mesh, "
            "create a checkout session, or prove historical clients still send "
            "valid payloads."
        ),
    }


@router.get("/api/v1/maas/compat/readiness", include_in_schema=False)
async def maas_compat_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _compat_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


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
