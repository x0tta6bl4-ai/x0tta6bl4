"""
MaaS (Mesh-as-a-Service) API Package.

Production API for deploying, managing, and monitoring
PQC-secured self-healing mesh networks.

Modules:
    - constants: PQC profiles, plan configuration
    - models: Pydantic request/response models
    - mesh_instance: MeshInstance class
    - registry: Global state management
    - services: Business logic services
    - auth: FastAPI dependencies for authentication
    - acl: Access control list evaluation
    - billing_helpers: HMAC, idempotency, billing calculations
    - endpoints: FastAPI routers for all API domains

API Endpoints:
    Auth:
        POST   /api/v1/maas/auth/register    — Register new user
        POST   /api/v1/maas/auth/login       — Login
        POST   /api/v1/maas/auth/api-key     — Rotate API key
        GET    /api/v1/maas/auth/me          — User profile
        POST   /api/v1/maas/auth/logout      — Logout

    Mesh Lifecycle:
        POST   /api/v1/maas/mesh/deploy      — Deploy a new mesh network
        GET    /api/v1/maas/mesh/list        — List user's meshes
        GET    /api/v1/maas/mesh/{id}/status — Mesh health & status
        GET    /api/v1/maas/mesh/{id}/metrics— Consciousness & MAPE-K metrics
        POST   /api/v1/maas/mesh/{id}/scale  — Scale nodes up/down
        DELETE /api/v1/maas/mesh/{id}        — Terminate mesh

    Nodes:
        POST   /api/v1/maas/nodes/register   — Register new node
        POST   /api/v1/maas/nodes/heartbeat  — Node heartbeat telemetry
        GET    /api/v1/maas/nodes/{mesh}/pending — List pending nodes
        POST   /api/v1/maas/nodes/{mesh}/{node}/approve — Approve node
        POST   /api/v1/maas/nodes/{mesh}/{node}/revoke  — Revoke node

    Billing:
        POST   /api/v1/maas/billing/webhook  — Billing webhook handler
        GET    /api/v1/maas/billing/usage/{mesh} — Usage report
        GET    /api/v1/maas/billing/estimate — Cost estimation
        GET    /api/v1/maas/billing/plans    — Available plans
"""

from typing import Any

# Public API - lazy loading
__all__ = [
    # Constants
    "PQC_SEGMENT_PROFILES",
    "PQC_DEFAULT_PROFILE",
    "get_pqc_profile",
    "PLAN_ALIASES",
    "BILLING_WEBHOOK_EVENTS",
    "PLAN_REQUEST_LIMITS",
    # Models
    "MeshDeployRequest",
    "MeshDeployResponse",
    "MeshStatusResponse",
    "MeshMetricsResponse",
    "MeshScaleRequest",
    "NodeRegisterRequest",
    "NodeRegisterResponse",
    "NodeHeartbeatRequest",
    "BillingWebhookRequest",
    "LoginRequest",
    "LoginResponse",
    "RegisterRequest",
    "RegisterResponse",
    "UserProfileResponse",
    "ApiKeyRotateRequest",
    "ApiKeyRotateResponse",
    # Classes
    "MeshInstance",
    "BillingService",
    "MeshProvisioner",
    "UsageMeteringService",
    "AuthService",
    "ACLEvaluator",
    "ACLManager",
    # Registry functions
    "get_mesh",
    "register_mesh",
    "record_audit_log",
    # Router
    "get_maas_router",
]


def __getattr__(name: str) -> Any:
    """Lazy loading for memory efficiency."""
    # Constants
    if name in ("PQC_SEGMENT_PROFILES", "PQC_DEFAULT_PROFILE", "get_pqc_profile",
                "PLAN_ALIASES", "BILLING_WEBHOOK_EVENTS", "PLAN_REQUEST_LIMITS"):
        from .constants import (
            PQC_SEGMENT_PROFILES, PQC_DEFAULT_PROFILE, get_pqc_profile,
            PLAN_ALIASES, BILLING_WEBHOOK_EVENTS, PLAN_REQUEST_LIMITS,
        )
        return locals().get(name)

    # Models
    if name in ("MeshDeployRequest", "MeshDeployResponse", "MeshStatusResponse",
                "MeshMetricsResponse", "MeshScaleRequest", "NodeRegisterRequest",
                "NodeRegisterResponse", "NodeHeartbeatRequest", "BillingWebhookRequest",
                "LoginRequest", "LoginResponse", "RegisterRequest", "RegisterResponse",
                "UserProfileResponse", "ApiKeyRotateRequest", "ApiKeyRotateResponse"):
        from . import models
        return getattr(models, name)

    # Classes
    if name == "MeshInstance":
        from .mesh_instance import MeshInstance
        return MeshInstance

    # Services
    if name == "BillingService":
        from .services import BillingService
        return BillingService
    if name == "MeshProvisioner":
        from .services import MeshProvisioner
        return MeshProvisioner
    if name == "UsageMeteringService":
        from .services import UsageMeteringService
        return UsageMeteringService
    if name == "AuthService":
        from .services import AuthService
        return AuthService

    # ACL
    if name == "ACLEvaluator":
        from .acl import ACLEvaluator
        return ACLEvaluator
    if name == "ACLManager":
        from .acl import ACLManager
        return ACLManager

    # Registry
    if name in ("get_mesh", "register_mesh", "record_audit_log"):
        from . import registry
        return getattr(registry, name)

    # Router
    if name == "get_maas_router":
        from .endpoints import get_combined_router as get_maas_router
        return get_maas_router

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Package metadata
__version__ = "2.0.0"
