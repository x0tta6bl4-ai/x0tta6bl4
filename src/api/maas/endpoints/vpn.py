"""
VPN API Endpoints
==================

REST API endpoints for VPN configuration and management.
"""

import hmac
import hashlib
import logging
import os
import secrets
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from src.core.cache import cache, cached
from src.coordination.events import EventBus, EventType, get_event_bus
from src.api.cross_plane_claim_gate import cross_plane_claim_gate_metadata
from src.core.reliability_policy import mark_degraded_dependency
from src.database import User, get_db
from src.api.maas_auth import require_permission, get_current_user_from_maas
from src.network.vpn_leak_protection import get_vpn_protector
from src.services.service_event_identity import service_event_identity
from vpn_config_generator import XUIAPIClient
from vpn_config_generator import generate_config_text, generate_vless_link
try:
    from new_vpn_config_generator import (
        generate_vless_link as generate_experimental_link,
        generate_config_text as generate_experimental_text
    )
    EXPERIMENTAL_AVAILABLE = True
except ImportError:
    EXPERIMENTAL_AVAILABLE = False
    from vpn_config_generator import generate_vless_link as generate_experimental_link
    from vpn_config_generator import generate_config_text as generate_experimental_text

logger = logging.getLogger(__name__)

try:
    import database as _legacy_user_db
except Exception as legacy_import_error:  # pragma: no cover - defensive runtime fallback
    _legacy_user_db = None
    logger.warning("Legacy database module unavailable for VPN ZKP flow: %s", legacy_import_error)

router = APIRouter( tags=["vpn"])
limiter = Limiter(key_func=get_remote_address)

xui: Optional[XUIAPIClient] = None

_VPN_STATUS_SOURCE_AGENT = "vpn-api-status-read"
_VPN_STATUS_LAYER = "api_vpn_status_observed_state"
VPN_API_STATUS_CLAIM_BOUNDARY = (
    "VPN API status evidence records local API status reads, TCP/x-ui status "
    "summaries, and bounded vpn-leak-protector status evidence references only. "
    "It does not prove customer client connectivity, production dataplane "
    "routing, remote VPN provider correctness, DNS privacy, firewall correctness, "
    "or that all traffic uses the VPN tunnel."
)


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _identity_evidence() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_VPN_STATUS_SOURCE_AGENT)
    return {
        "spiffe_id_present": bool(str(identity.get("spiffe_id") or "").strip()),
        "spiffe_id_hash": _redacted_sha256_prefix(identity.get("spiffe_id")),
        "did_present": bool(str(identity.get("did") or "").strip()),
        "did_hash": _redacted_sha256_prefix(identity.get("did")),
        "wallet_address_present": bool(
            str(identity.get("wallet_address") or "").strip()
        ),
        "wallet_address_hash": _redacted_sha256_prefix(
            identity.get("wallet_address")
        ),
        "raw_identity_redacted": True,
    }


def _vpn_event_bus_from_request(request: Optional[Request]) -> Optional[EventBus]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize vpn-api-status EventBus: %s", exc)
        return None


def _bounded_event_reference(evidence: Any) -> Dict[str, Any]:
    if not isinstance(evidence, dict) or not evidence:
        return {
            "available": False,
            "reason": "event_evidence_missing",
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    allowed = {
        "event_id",
        "source_agent",
        "layer",
        "operation",
        "stage",
        "status",
        "reason",
        "observed_state",
        "control_action",
        "claim_boundary",
    }
    reference = {
        key: evidence.get(key)
        for key in sorted(allowed)
        if key in evidence
    }
    reference.update(
        {
            "available": bool(reference.get("event_id")),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    )
    return reference


def _vpn_leak_status_summary(status: Any) -> Dict[str, Any]:
    if not isinstance(status, dict):
        return {
            "available": False,
            "reason": "status_payload_missing",
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    original_dns_servers = status.get("original_dns_servers")
    return {
        "available": True,
        "protection_enabled": bool(status.get("protection_enabled")),
        "kill_switch_enabled": bool(status.get("kill_switch_enabled")),
        "vpn_interface_hash": _redacted_sha256_prefix(status.get("vpn_interface")),
        "original_dns_server_count": (
            len(original_dns_servers) if isinstance(original_dns_servers, list) else 0
        ),
        "resolver_info_present": bool(status.get("resolver_info")),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


async def _read_vpn_leak_status_evidence(
    request: Request,
    event_bus: Optional[EventBus],
) -> Dict[str, Any]:
    try:
        protector = await get_vpn_protector()
        state = getattr(request, "state", None)
        project_root = getattr(state, "event_project_root", ".")
        if event_bus is not None:
            protector.event_bus = event_bus
            protector.event_project_root = project_root
            resolver = getattr(protector, "doh_resolver", None)
            if resolver is not None:
                if hasattr(resolver, "event_bus"):
                    resolver.event_bus = event_bus
                if hasattr(resolver, "event_project_root"):
                    resolver.event_project_root = project_root

        status = await protector.get_status()
        evidence_getter = getattr(protector, "get_last_event_evidence", None)
        event_reference = (
            evidence_getter() if callable(evidence_getter) else None
        )
        return {
            "available": True,
            "status_summary": _vpn_leak_status_summary(status),
            "event_reference": _bounded_event_reference(event_reference),
            "raw_status_payload_redacted": True,
            "payloads_redacted": True,
        }
    except Exception as exc:
        logger.error("Failed to read vpn-leak-protector status evidence: %s", exc)
        return {
            "available": False,
            "reason": "vpn_leak_status_read_failed",
            "error_hash": _redacted_sha256_prefix(exc),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }


def _publish_vpn_status_event(
    request: Request,
    *,
    started_at: float,
    status: str,
    http_status: int,
    status_payload: Optional[Dict[str, Any]] = None,
    leak_protection_evidence: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
) -> Optional[str]:
    bus = _vpn_event_bus_from_request(request)
    if bus is None:
        return None
    status_payload = status_payload or {}
    payload = {
        "component": "api.vpn",
        "operation": "get_vpn_status",
        "service_name": _VPN_STATUS_SOURCE_AGENT,
        "source_alias": _VPN_STATUS_SOURCE_AGENT,
        "layer": _VPN_STATUS_LAYER,
        "stage": "status_read",
        "status": status,
        "reason": reason,
        "http_status": http_status,
        "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
        "vpn_status": status_payload.get("status"),
        "vpn_server_hash": _redacted_sha256_prefix(status_payload.get("server")),
        "vpn_port": status_payload.get("port"),
        "protocol": status_payload.get("protocol"),
        "active_user_count": status_payload.get("active_users"),
        "uptime_present": status_payload.get("uptime") is not None,
        "leak_protection_status_evidence": leak_protection_evidence
        or {
            "available": False,
            "reason": "not_collected",
            "payloads_redacted": True,
        },
        "observed_state": True,
        "control_action": False,
        "service_identity": _identity_evidence(),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": VPN_API_STATUS_CLAIM_BOUNDARY,
    }
    try:
        event = bus.publish(
            EventType.PIPELINE_STAGE_END
            if status == "success"
            else EventType.TASK_BLOCKED,
            _VPN_STATUS_SOURCE_AGENT,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish vpn-api-status event: %s", exc)
        return None


def _get_xui_client() -> XUIAPIClient:
    """Initialize x-ui integration only when a VPN endpoint needs it."""
    global xui
    if xui is None:
        xui = XUIAPIClient()
    return xui


def _vpn_db_session_available(db: Any) -> bool:
    return all(hasattr(db, attr) for attr in ("query", "commit"))


def _vpn_user_model_available() -> bool:
    return all(hasattr(User, attr) for attr in ("id", "email", "plan", "vpn_uuid"))


def _vpn_config_generators_available() -> bool:
    return all(
        callable(fn)
        for fn in (
            generate_vless_link,
            generate_config_text,
            generate_experimental_link,
            generate_experimental_text,
        )
    )


def _vpn_cache_available() -> bool:
    return all(callable(getattr(cache, attr, None)) for attr in ("get", "set", "delete"))


def _vpn_auth_dependencies_available() -> bool:
    return callable(require_permission) and callable(get_current_user_from_maas)


def _vpn_legacy_admin_token_configured() -> bool:
    return bool(os.getenv("ADMIN_TOKEN"))


def _vpn_zkp_legacy_db_available() -> bool:
    if _legacy_user_db is None:
        return False
    return all(
        callable(getattr(_legacy_user_db, attr, None))
        for attr in ("get_user", "is_user_active", "update_user")
    )


def _vpn_zkp_attestor_available() -> bool:
    return callable(getattr(NIZKPAttestor, "verify_identity_proof", None))


def _vpn_production_env_ready() -> bool:
    if os.getenv("ENVIRONMENT", "development").lower() != "production":
        return True
    return all(
        bool(os.getenv(name))
        for name in (
            "VPN_SERVER",
            "VPN_PORT",
            "VPN_SESSION_TOKEN",
            "VPN_REALITY_PUBLIC_KEY",
        )
    )


def _vpn_readiness_status(db: Any) -> Dict[str, Any]:
    vpn_db_ready = _vpn_db_session_available(db)
    user_model_ready = _vpn_user_model_available()
    config_generators_ready = _vpn_config_generators_available()
    xui_client_factory_ready = callable(XUIAPIClient)
    cache_ready = _vpn_cache_available()
    auth_dependency_ready = _vpn_auth_dependencies_available()
    legacy_admin_token_ready = _vpn_legacy_admin_token_configured()
    zkp_legacy_db_ready = _vpn_zkp_legacy_db_available()
    zkp_attestor_ready = _vpn_zkp_attestor_available()
    production_env_ready = _vpn_production_env_ready()
    experimental_generator_ready = EXPERIMENTAL_AVAILABLE
    vpn_runtime_ready = (
        vpn_db_ready
        and user_model_ready
        and config_generators_ready
        and xui_client_factory_ready
        and cache_ready
        and auth_dependency_ready
        and zkp_legacy_db_ready
        and zkp_attestor_ready
        and production_env_ready
    )

    degraded_dependencies = []
    if not vpn_db_ready:
        degraded_dependencies.append("database")
    if not user_model_ready:
        degraded_dependencies.append("user_model")
    if not config_generators_ready:
        degraded_dependencies.append("vpn_config_generators")
    if not xui_client_factory_ready:
        degraded_dependencies.append("xui_client")
    if not cache_ready:
        degraded_dependencies.append("cache")
    if not auth_dependency_ready:
        degraded_dependencies.append("auth")
    if not legacy_admin_token_ready:
        degraded_dependencies.append("legacy_admin_token")
    if not zkp_legacy_db_ready:
        degraded_dependencies.append("zkp_legacy_db")
    if not zkp_attestor_ready:
        degraded_dependencies.append("zkp_attestor")
    if not production_env_ready:
        degraded_dependencies.append("production_vpn_env")

    return {
        "status": "ready" if not degraded_dependencies else "degraded",
        "route_registered": True,
        "registration_mode": "full_mode_only",
        "route_present_in_light_mode": False,
        "lifecycle_binding": "route_import_only",
        "startup_hook_completed": None,
        "vpn_runtime_ready": vpn_runtime_ready,
        "vpn_db_ready": vpn_db_ready,
        "user_model_ready": user_model_ready,
        "config_generators_ready": config_generators_ready,
        "xui_client_factory_ready": xui_client_factory_ready,
        "cache_ready": cache_ready,
        "auth_dependency_ready": auth_dependency_ready,
        "legacy_admin_token_ready": legacy_admin_token_ready,
        "zkp_legacy_db_ready": zkp_legacy_db_ready,
        "zkp_attestor_ready": zkp_attestor_ready,
        "production_env_ready": production_env_ready,
        "experimental_generator_ready": experimental_generator_ready,
        "route_precedence": {
            "shadowed_by_legacy": [],
            "fixed_prefix": "/vpn",
            "boundary": (
                "VPN routes use the /vpn prefix, so MaaS legacy catch-all routes "
                "do not shadow them. The router is still full-mode-only and has "
                "no production_lifespan startup hook."
            ),
        },
        "backing_state": {
            "database": (
                "VPN user listing and local revoke compatibility paths query and "
                "update User rows."
            ),
            "user_model": (
                "VPN routes depend on User id, email, plan, and vpn_uuid fields."
            ),
            "vpn_config_generators": (
                "Config routes require VLESS link and Xray config text generators."
            ),
            "xui_client": (
                "Config/status/admin routes lazily instantiate XUIAPIClient for "
                "x-ui backed provisioning and active-user data."
            ),
            "cache": (
                "Status and user-list routes use shared async cache get/set/delete."
            ),
            "auth": (
                "Authenticated VPN access depends on MaaS permission checks; "
                "legacy admin endpoints can also use X-Admin-Token."
            ),
            "legacy_admin_token": (
                "X-Admin-Token admin compatibility requires ADMIN_TOKEN. MaaS "
                "vpn:admin auth can still be used when configured."
            ),
            "zkp_legacy_db": (
                "ZKP /vpn/authenticate binds proof public keys to the legacy user "
                "database and checks subscription activity."
            ),
            "production_vpn_env": (
                "Production secure config requires VPN_SERVER, VPN_PORT, "
                "VPN_SESSION_TOKEN, and VPN_REALITY_PUBLIC_KEY."
            ),
        },
        "degraded_dependencies": degraded_dependencies,
        "cross_plane_claim_gate": cross_plane_claim_gate_metadata(
            (
                "production_readiness",
                "dataplane_delivery",
                "dpi_bypass",
                "customer_traffic",
            ),
            surface="vpn_readiness",
        ),
        "claim_boundary": (
            "VPN readiness separates /vpn route reachability from lazy x-ui access, "
            "config generation, local User DB state, cache, MaaS auth, legacy admin "
            "token compatibility, ZKP legacy subscription checks, and production-only "
            "VPN environment requirements. It does not prove that the VPN server is "
            "currently reachable or that a generated credential can connect."
        ),
    }


@router.get("/readiness")
async def vpn_readiness(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = _vpn_readiness_status(db)
    for dependency in payload["degraded_dependencies"]:
        mark_degraded_dependency(request, dependency)
    return payload


class VPNConfigRequest(BaseModel):
    user_id: int
    node_id: Optional[str] = "nl"
    email: Optional[str] = None  # Optional for backward compatibility
    username: Optional[str] = None
    server: Optional[str] = None
    port: Optional[int] = None


class VPNConfigResponse(BaseModel):
    user_id: int
    username: Optional[str]
    vless_link: str
    config_text: str


class VPNStatusResponse(BaseModel):
    status: str
    server: str
    port: int
    protocol: str
    active_users: int
    uptime: float


class SubscriptionStatusResponse(BaseModel):
    user_id: str
    email: str
    plan: str
    status: str  # active, expired, pending, blocked
    expires_at: Optional[datetime] = None
    days_left: Optional[int] = None
    requests_count: int
    requests_limit: int
    vpn_uuid_present: bool


def _normalize_identity(value: Any) -> str:
    """Normalize identity values for safe str/int compatibility checks."""
    if value is None:
        return ""
    return str(value).strip()


def _ids_equal(left: Any, right: Any) -> bool:
    """Compare identifiers across legacy int and string representations."""
    left_norm = _normalize_identity(left)
    right_norm = _normalize_identity(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm:
        return True
    try:
        return int(left_norm) == int(right_norm)
    except (TypeError, ValueError):
        return False


async def verify_admin_token(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> None:
    """Validate legacy admin token header for VPN admin endpoints."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=403, detail="Admin token not configured")
    if not x_admin_token:
        raise HTTPException(status_code=403, detail="Admin token required")
    if not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Invalid admin token")


async def _resolve_optional_maas_user(request: Request, db: Session) -> Optional[User]:
    """Resolve MaaS user only when auth headers are present."""
    has_auth_headers = bool(
        request.headers.get("X-API-Key") or request.headers.get("Authorization")
    )
    if not has_auth_headers:
        return None
    return await get_current_user_from_maas(request=request, db=db)


async def _enforce_permission_if_authenticated(
    request: Request,
    db: Session,
    permission: str,
) -> Optional[User]:
    """Backward compatibility: anonymous access allowed, authenticated users are scoped."""
    user = await _resolve_optional_maas_user(request, db)
    if user is None:
        # Log anonymous access for security monitoring
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            logger.warning(
                f"Anonymous access to VPN endpoint requiring '{permission}' permission. "
                f"IP: {get_remote_address(request)}, Path: {request.url.path}"
            )
        return None
    checker = require_permission(permission)
    return checker(user)


async def _require_vpn_admin_access(
    request: Request,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> Optional[User]:
    """
    Accept either MaaS scope-based auth (vpn:admin) or legacy X-Admin-Token.
    """
    user = await _resolve_optional_maas_user(request, db)
    if user is not None:
        checker = require_permission("vpn:admin")
        try:
            return checker(user)
        except HTTPException as exc:
            raise HTTPException(status_code=403, detail=exc.detail) from exc

    await verify_admin_token(x_admin_token)
    return None


from src.security.zkp_attestor import NIZKPAttestor

class ZKPAuthRequest(BaseModel):
    proof: Dict[str, Any]


def _legacy_get_user(user_id: int) -> Optional[Dict[str, Any]]:
    if _legacy_user_db is None:
        return None
    get_user_fn = getattr(_legacy_user_db, "get_user", None)
    if not callable(get_user_fn):
        return None
    return get_user_fn(user_id)


def _legacy_is_user_active(user_id: int) -> bool:
    if _legacy_user_db is None:
        return False
    is_active_fn = getattr(_legacy_user_db, "is_user_active", None)
    if not callable(is_active_fn):
        return False
    return bool(is_active_fn(user_id))


def _legacy_update_user_public_key(user_id: int, public_key: int) -> bool:
    if _legacy_user_db is None:
        return False
    update_user_fn = getattr(_legacy_user_db, "update_user", None)
    if not callable(update_user_fn):
        return False
    return bool(update_user_fn(user_id, zkp_public_key=str(public_key)))


def _get_user_public_key(user_id: int) -> Optional[int]:
    """
    Get the registered ZKP public key for a user.

    Returns the public key as integer if registered, None otherwise.
    In production, this should query a secure key registry.
    """
    user = _legacy_get_user(user_id)
    if not user:
        return None

    # Check for registered public key in user metadata
    # The public key should be registered during user onboarding
    zkp_public_key = user.get("zkp_public_key")
    if zkp_public_key is not None:
        try:
            return int(zkp_public_key)
        except (ValueError, TypeError):
            logger.warning(f"Invalid zkp_public_key format for user {user_id}")
            return None

    # In development/staging, allow first-time registration
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment in ("development", "staging"):
        logger.warning(
            f"No ZKP public key registered for user {user_id} in {environment} mode. "
            "Key will be auto-registered on first auth."
        )
        return None

    # In production, require pre-registered key
    return None


def _register_user_public_key(user_id: int, public_key: int) -> bool:
    """
    Register a ZKP public key for a user.

    Should only be called during onboarding or in development mode.
    Returns True if registration succeeded.
    """
    return _legacy_update_user_public_key(user_id, public_key)


@router.post("/authenticate")
@limiter.limit("5/minute")
async def authenticate_client(
    request: Request,
    auth_req: ZKPAuthRequest,
):
    """
    Verifies NIZKP identity proof and returns a session token if active.

    Security: Requires proof of private key possession AND that the public key
    is registered for the claimed user_id.
    """
    # 1. Basic ZKP Math Check
    is_valid = NIZKPAttestor.verify_identity_proof(auth_req.proof, message="client-auth-v1")
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid ZKP identity proof")

    # 2. Extract user identity from proof
    user_id_str = auth_req.proof.get("node_id")
    if not user_id_str:
        raise HTTPException(status_code=400, detail="node_id required in proof")

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="node_id must be a valid integer")

    # 3. Public Key Binding Check (CRITICAL for security)
    # Verify that the public key in the proof belongs to this user
    proof_public_key = auth_req.proof.get("public_key")
    if proof_public_key is None:
        raise HTTPException(status_code=401, detail="public_key required in proof")

    registered_key = _get_user_public_key(user_id)
    environment = os.getenv("ENVIRONMENT", "development").lower()

    if registered_key is not None:
        # Verify key match
        if proof_public_key != registered_key:
            logger.warning(
                f"ZKP public key mismatch for user {user_id}: "
                f"proof has {proof_public_key}, expected {registered_key}"
            )
            raise HTTPException(status_code=401, detail="Public key mismatch")
    elif environment in ("development", "staging"):
        # Auto-register in development/staging (first auth only)
        # SECURITY: Log prominently for audit - this should not happen in production
        logger.warning(
            f"SECURITY: Auto-registering ZKP public key for user {user_id} in {environment} mode. "
            f"This is allowed for development/staging but should be monitored. "
            f"Public key hash: {hash(str(proof_public_key)) % 10000:04d}"
        )
        _register_user_public_key(user_id, proof_public_key)
    else:
        # Production requires pre-registered key
        raise HTTPException(
            status_code=401,
            detail="No registered public key for user. Complete onboarding first."
        )

    # 4. Database Subscription Check
    if not _legacy_is_user_active(user_id):
        raise HTTPException(status_code=403, detail="Subscription inactive")

    # 5. Issue Session Token (cryptographically secure random token)
    session_token = secrets.token_urlsafe(32)
    logger.info(f"ZKP authentication successful for user {user_id}")
    return {"status": "authenticated", "token": session_token}

def _get_vpn_session_token() -> str:
    """Get VPN session token from environment with production safety check."""
    token = os.getenv("VPN_SESSION_TOKEN")
    if not token:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise RuntimeError(
                "VPN_SESSION_TOKEN environment variable must be set in production. "
                "Refusing to use hardcoded fallback for security."
            )
        # Development fallback only - use a random token that changes per session
        logger.warning(
            "VPN_SESSION_TOKEN not set, using random development token"
        )
        token = f"dev_{uuid.uuid4().hex}"
    return token


def _derive_user_uuid(user_id: int) -> str:
    """
    Derive a deterministic UUID from user_id.

    This ensures the same user always gets the same UUID for their VPN config,
    enabling session persistence and proper user tracking.

    Uses UUID v5 (SHA-1 based) with a namespace UUID.
    """
    # Use a fixed namespace UUID for x0tta6bl4 VPN
    NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID namespace DNS
    return str(uuid.uuid5(NAMESPACE, f"x0tta6bl4-vpn-user-{user_id}"))


@router.get("/config/secure")
async def get_secure_config(
    request: Request,
    authorization: str = Header(...),
    user_id: int = Query(..., description="User ID for UUID derivation"),
):
    """
    Returns full Xray config for the client.
    Requires valid Bearer token from VPN_SESSION_TOKEN env var.

    Security: UUID is derived deterministically from user_id for session consistency.
    """
    expected_token = _get_vpn_session_token()

    # Safely extract and compare Bearer token (prevent timing attacks)
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=403, detail="Invalid authorization format")

    token = authorization[7:]  # Remove "Bearer " prefix
    if not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid or expired token")

    # Get Reality public key from environment (CRITICAL: never hardcode in production)
    reality_public_key = os.getenv("VPN_REALITY_PUBLIC_KEY")
    if not reality_public_key:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise RuntimeError(
                "VPN_REALITY_PUBLIC_KEY environment variable must be set in production. "
                "Refusing to use hardcoded key for security."
            )
        # Development fallback only - this is a test key, NOT for production
        logger.warning(
            "VPN_REALITY_PUBLIC_KEY not set, using development test key (NOT for production!)"
        )
        reality_public_key = "DEV_TEST_KEY_DO_NOT_USE_IN_PRODUCTION"

    # Derive deterministic UUID from user_id
    user_uuid = _derive_user_uuid(user_id)

    # Generate a real VLESS+Reality config JSON
    return {
        "xray_json": {
            "inbounds": [{"port": 10808, "protocol": "socks"}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": _get_vpn_server(),
                        "port": 39830,
                        "users": [{"id": user_uuid, "encryption": "none", "flow": "xtls-rprx-vision"}]
                    }]
                },
                "streamSettings": {
                    "network": "tcp",
                    "security": "reality",
                    "realitySettings": {
                        "show": False,
                        "fingerprint": "chrome",
                        "serverName": "www.microsoft.com",
                        "publicKey": reality_public_key,
                        "shortId": "7a",
                        "spiderX": "/api/v1/status"
                    }
                }
            }]
        }
    }

@router.get("/subscription/status")
@limiter.limit("10/minute")
async def vpn_subscription_status(
    request: Request,
    db: Session = Depends(get_db),
) -> SubscriptionStatusResponse:
    """
    Get current user's subscription status.
    Requires authentication.
    """
    user = await get_current_user_from_maas(request=request, db=db)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    now = datetime.now()
    days_left = None
    status = "active"

    if user.expires_at:
        if user.expires_at < now:
            status = "expired"
            days_left = 0
        else:
            days_left = (user.expires_at - now).days
            if days_left <= 3:
                status = "warning"

    if user.plan == "free" and status != "expired":
        status = "basic"

    return SubscriptionStatusResponse(
        user_id=str(user.id),
        email=user.email,
        plan=user.plan,
        status=status,
        expires_at=user.expires_at,
        days_left=days_left,
        requests_count=user.requests_count,
        requests_limit=user.requests_limit,
        vpn_uuid_present=bool(user.vpn_uuid),
    )


@router.get("/config")
@limiter.limit("30/minute")
async def get_vpn_config(
    request: Request,
    user_id: int = Query(...),
    node_id: Optional[str] = Query(default="nl"),
    email: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    server: Optional[str] = Query(default=None),
    port: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
) -> VPNConfigResponse:
    """
    Generate VPN configuration.

    Security: In production, requires authentication and user_id must match
    the authenticated user's ID (or user must have vpn:admin permission).
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()
    user = await _enforce_permission_if_authenticated(request, db, "vpn:config")

    # SECURITY: In production, require authentication
    if environment == "production" and user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required in production environment"
        )

    # SECURITY: Authenticated users can only access their own config
    # unless they have admin permissions
    if user is not None:
        user_has_admin = any(
            scope.get("permission") == "vpn:admin"
            for scope in getattr(user, "scopes", [])
        )
        if not user_has_admin and not _ids_equal(user.id, user_id):
            logger.warning(
                f"User {user.id} attempted to access config for user {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Cannot access other user's VPN configuration"
            )

    try:
        return await _build_vpn_config(user_id, email, username, server, port, node_id=node_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Config generation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate config")


@router.post("/config")
@limiter.limit("30/minute")
async def create_vpn_config(
    request: Request,
    config_req: VPNConfigRequest,
    db: Session = Depends(get_db),
) -> VPNConfigResponse:
    """Generate VPN configuration via JSON body (legacy-compatible)."""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    user = await _enforce_permission_if_authenticated(request, db, "vpn:config")

    # Keep legacy anonymous behavior in non-production, but fail closed in production.
    if environment == "production" and user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required in production environment"
        )

    if user is not None:
        user_has_admin = any(
            scope.get("permission") == "vpn:admin"
            for scope in getattr(user, "scopes", [])
        )
        if not user_has_admin and not _ids_equal(user.id, config_req.user_id):
            logger.warning(
                f"User {user.id} attempted to create config for user {config_req.user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Cannot access other user's VPN configuration"
            )

    return await _build_vpn_config(
        config_req.user_id,
        config_req.email,
        config_req.username,
        config_req.server,
        config_req.port,
        node_id=config_req.node_id,
    )


def _get_vpn_server() -> str:
    """Get VPN server address from environment with production safety check."""
    server = os.getenv("VPN_SERVER")
    if not server:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise RuntimeError(
                "VPN_SERVER environment variable must be set in production. "
                "Refusing to use hardcoded fallback for security."
            )
        # Development fallback only
        logger.warning(
            "VPN_SERVER not set, using localhost fallback (development only)"
        )
        server = "127.0.0.1"
    return server


def _get_vpn_port() -> int:
    """Get VPN port from environment with production safety check."""
    port_str = os.getenv("VPN_PORT")
    if not port_str:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise RuntimeError(
                "VPN_PORT environment variable must be set in production. "
                "Refusing to use hardcoded fallback for security."
            )
        # Development fallback only
        logger.warning(
            "VPN_PORT not set, using default fallback (development only)"
        )
        return 443
    return int(port_str)


def _is_test_runtime() -> bool:
    """Return True when running under test harness."""
    return bool(os.getenv("PYTEST_CURRENT_TEST")) or os.getenv("TESTING", "false").lower() == "true"


async def _build_vpn_config(
    user_id: int,
    email: Optional[str],
    username: Optional[str],
    server: Optional[str],
    port: Optional[int],
) -> VPNConfigResponse:
    """Shared implementation for GET/POST config generation."""
    try:
        uid = user_id
        u_name = username
        srv = server
        prt = port
        # Keep old GET contract where email may be omitted.
        u_email = email or f"user_{uid}@vpn.local"

        # Try XUI-backed provisioning first. If local x-ui storage is unavailable
        # (readonly DB, missing files), degrade gracefully to generated credentials.
        try:
            vpn_info = _get_xui_client().create_user(uid, u_email, remark=u_name)
        except Exception as exc:
            logger.warning(
                "x-ui provisioning unavailable for user_id=%s, using fallback config: %s",
                uid,
                exc,
            )
            vpn_info = {
                "uuid": str(uuid.uuid4()),
                "server": _get_vpn_server(),
                "port": _get_vpn_port(),
            }

        # Override server/port if custom ones provided (for config text only)
        final_server = srv or vpn_info['server']
        final_port = prt or vpn_info['port']

        # Check if we should use experimental Reality V2 (port 39830)
        use_experimental = False
        if EXPERIMENTAL_AVAILABLE:
            # If default port is offline, or explicitly requested via port 39830
            if final_port == 39830:
                use_experimental = True
            else:
                if _is_test_runtime():
                    conn_status = "online"
                else:
                    conn_status = await _check_vpn_connectivity(final_server, final_port)
                if conn_status == "offline":
                    logger.info("Default VPN port offline, switching to experimental Reality V2")
                    use_experimental = True
                    final_port = 39830

        if use_experimental and EXPERIMENTAL_AVAILABLE:
            final_link = generate_experimental_link(
                vpn_info["uuid"],
                server=final_server,
                port=final_port,
                remark=u_name or f"user_{uid}_experimental"
            )
            config_text = generate_experimental_text(
                uid, user_uuid=vpn_info['uuid'], server=final_server, port=final_port
            )
        else:
            final_link = generate_vless_link(
                vpn_info["uuid"],
                server=final_server,
                port=final_port,
                remark=u_name or f"user_{uid}",
            )
            config_text = generate_config_text(
                uid, user_uuid=vpn_info['uuid'], server=final_server, port=final_port
            )

        return VPNConfigResponse(
            user_id=uid,
            username=u_name,
            vless_link=final_link,
            config_text=config_text,
        )
    except Exception as e:
        logger.error(f"Error generating VPN config: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail="Internal server error")


async def _check_vpn_connectivity(server: str, port: int) -> str:
    """Check VPN server connectivity."""
    import asyncio

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(server, port), timeout=2.0
        )
        writer.close()
        await writer.wait_closed()
        return "online"
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return "offline"


@cached(ttl=30, key_prefix="vpn_status")
async def _get_vpn_status_cached() -> Dict[str, Any]:
    """Get VPN status with real data from x-ui."""
    server = _get_vpn_server()
    port = _get_vpn_port()

    status = await _check_vpn_connectivity(server, port)
    active_users = _get_xui_client().get_active_users_count()

    # Try to get uptime from system if possible
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
    except Exception:
        uptime_seconds = 0.0

    return {
        "status": status,
        "server": server,
        "port": port,
        "protocol": "VLESS+Reality",
        "active_users": active_users,
        "uptime": uptime_seconds,
    }


@router.get("/status")
@limiter.limit("60/minute")
async def get_vpn_status(
    request: Request,
    db: Session = Depends(get_db),
) -> VPNStatusResponse:
    """
    Get VPN server status.
    """
    started_at = time.monotonic()
    try:
        await _enforce_permission_if_authenticated(request, db, "vpn:status")
        data = await _get_vpn_status_cached()
        event_bus = _vpn_event_bus_from_request(request)
        leak_protection_evidence = await _read_vpn_leak_status_evidence(
            request,
            event_bus,
        )
        _publish_vpn_status_event(
            request,
            started_at=started_at,
            status="success",
            http_status=200,
            status_payload=data,
            leak_protection_evidence=leak_protection_evidence,
        )
        return VPNStatusResponse(**data)
    except Exception as e:
        logger.error(f"Error getting VPN status: {e}", exc_info=True)
        _publish_vpn_status_event(
            request,
            started_at=started_at,
            status="error",
            http_status=500,
            reason="exception",
        )
        raise HTTPException(status_code=500, detail="Internal server error")


VPN_USERS_CACHE_KEY = "vpn:users:list"


async def _fetch_vpn_users_from_xui() -> Dict[str, Any]:
    """Fetch all VPN users directly from x-ui database for admin list."""
    xui_client = _get_xui_client()
    if xui_client.simulated:
        users = [
            {"user_id": 123, "username": "demo", "email": "demo@x0t.net", "vless_link": "vless://..."}
        ]
        return {"total": len(users), "users": users}

    import sqlite3
    try:
        conn = sqlite3.connect(xui_client.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT email, up, down, total FROM client_traffics")
        rows = cursor.fetchall()

        users = []
        for row in rows:
            users.append({
                "email": row["email"],
                "up": row["up"],
                "down": row["down"],
                "total": row["total"]
            })

        conn.close()
        return {"total": len(users), "users": users}
    except Exception as e:
        logger.error(f"Failed to fetch users from x-ui: {e}")
        return {"total": 0, "users": []}


def _fetch_vpn_users_from_db(db: Session) -> Dict[str, Any]:
    """Fetch VPN users from local DB for admin API contract compatibility."""
    users = db.query(User).filter(User.plan != "free").all()
    payload: List[Dict[str, Any]] = []
    for user in users:
        vpn_uuid = getattr(user, "vpn_uuid", None) or str(getattr(user, "id", uuid.uuid4()))
        payload.append(
            {
                "user_id": str(getattr(user, "id", "")),
                "email": getattr(user, "email", ""),
                "plan": getattr(user, "plan", "free"),
                "vless_link": generate_vless_link(vpn_uuid, remark=getattr(user, "email", "vpn-user")),
            }
        )
    return {"total": len(payload), "users": payload}


@router.get("/users")
@limiter.limit("10/minute")
async def get_vpn_users(
    request: Request,
    db: Session = Depends(get_db),
    _admin_access: Optional[User] = Depends(_require_vpn_admin_access),
) -> Dict[str, Any]:
    """
    Get list of active VPN users from x-ui.
    """
    try:
        cached_result = await cache.get(VPN_USERS_CACHE_KEY)
        if cached_result is not None:
            return cached_result

        result = _fetch_vpn_users_from_db(db)
        if result["total"] == 0:
            result = await _fetch_vpn_users_from_xui()
        await cache.set(VPN_USERS_CACHE_KEY, result, ttl=60)
        return result
    except Exception as e:
        logger.error(f"Error getting VPN users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/user")
@limiter.limit("5/minute")
async def delete_vpn_user(
    request: Request,
    email: str,
    _admin_access: Optional[User] = Depends(_require_vpn_admin_access),
) -> Dict[str, Any]:
    """
    Delete VPN user by email.
    """
    try:
        if _get_xui_client().delete_user(email):
            await cache.delete(VPN_USERS_CACHE_KEY)
            return {"success": True, "message": f"User {email} removed from VPN"}
        else:
            return {"success": False, "message": f"User {email} not found"}
    except Exception as e:
        logger.error(f"Error deleting VPN user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/user/{user_id}")
@limiter.limit("5/minute")
async def delete_vpn_user_by_id(
    request: Request,
    user_id: str,
    db: Session = Depends(get_db),
    _admin_access: Optional[User] = Depends(_require_vpn_admin_access),
) -> Dict[str, Any]:
    """
    Compatibility endpoint: downgrade local user plan to free by user_id.
    Returns success=false with 200 when user is not found.
    """
    try:
        db_user = db.query(User).filter(User.id == user_id).first()
        if not db_user:
            return {"success": False, "message": f"User {user_id} not found"}

        db_user.plan = "free"
        db.commit()

        user_email = getattr(db_user, "email", None)
        if user_email:
            try:
                _get_xui_client().delete_user(user_email)
            except Exception:
                pass

        await cache.delete(VPN_USERS_CACHE_KEY)
        return {
            "success": True,
            "message": f"User {user_id} downgraded to free plan",
        }
    except Exception as e:
        logger.error(f"Error downgrading user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
