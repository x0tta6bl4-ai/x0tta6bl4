"""
VPN API Endpoints
==================

REST API endpoints for VPN configuration and management.
"""

import hmac
import logging
import os
import secrets
import sys
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from src.core.cache import cache, cached
from src.database import User, get_db
from src.api.maas_auth import require_permission, get_current_user_from_maas
from vpn_config_generator import generate_config_text, generate_vless_link, XUIAPIClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn", tags=["vpn"])
limiter = Limiter(key_func=get_remote_address)

# Initialize XUI Client
xui = XUIAPIClient()


class VPNConfigRequest(BaseModel):
    user_id: int
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

from database import get_user, is_user_active


def _get_user_public_key(user_id: int) -> Optional[int]:
    """
    Get the registered ZKP public key for a user.
    
    Returns the public key as integer if registered, None otherwise.
    In production, this should query a secure key registry.
    """
    user = get_user(user_id)
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
    from database import update_user
    return update_user(user_id, zkp_public_key=str(public_key))


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
    if not is_user_active(user_id):
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

@router.get("/config")
@limiter.limit("30/minute")
async def get_vpn_config(
    request: Request,
    user_id: int = Query(...),
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
        if not user_has_admin and user.id != user_id:
            logger.warning(
                f"User {user.id} attempted to access config for user {user_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Cannot access other user's VPN configuration"
            )
    
    try:
        return _build_vpn_config(user_id, email, username, server, port)
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
    await _enforce_permission_if_authenticated(request, db, "vpn:config")
    return _build_vpn_config(
        config_req.user_id,
        config_req.email,
        config_req.username,
        config_req.server,
        config_req.port,
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
        return 39829
    return int(port_str)


def _build_vpn_config(
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
            vpn_info = xui.create_user(uid, u_email, remark=u_name)
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
    active_users = xui.get_active_users_count()
    
    # Try to get uptime from system if possible
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
    except:
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
    try:
        await _enforce_permission_if_authenticated(request, db, "vpn:status")
        data = await _get_vpn_status_cached()
        return VPNStatusResponse(**data)
    except Exception as e:
        logger.error(f"Error getting VPN status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


VPN_USERS_CACHE_KEY = "vpn:users:list"


async def _fetch_vpn_users_from_xui() -> Dict[str, Any]:
    """Fetch all VPN users directly from x-ui database for admin list."""
    if xui.simulated:
        users = [
            {"user_id": 123, "username": "demo", "email": "demo@x0t.net", "vless_link": "vless://..."}
        ]
        return {"total": len(users), "users": users}

    import sqlite3
    import json
    try:
        conn = sqlite3.connect(xui.db_path)
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
        if xui.delete_user(email):
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
                xui.delete_user(user_email)
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
