"""
VPN API Endpoints
==================

REST API endpoints for VPN configuration and management.
"""

import hmac
import logging
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from src.core.cache import cache, cached
from src.database import User, get_db
from vpn_config_generator import generate_config_text, generate_vless_link

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn", tags=["vpn"])
limiter = Limiter(key_func=get_remote_address)


async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin token not configured (access forbidden)",
        )
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )


class VPNConfigRequest(BaseModel):
    user_id: int
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


@router.get("/config")
@limiter.limit("30/minute")
async def get_vpn_config(
    request: Request,
    user_id: int,
    username: Optional[str] = None,
    server: Optional[str] = None,
    port: Optional[int] = None,
) -> VPNConfigResponse:
    """
    Generate VPN configuration for a user.

    Args:
        user_id: Telegram user ID
        username: Optional username for the VPN config
        server: Optional custom server address
        port: Optional custom server port

    Returns:
        VPN configuration with VLESS link and detailed instructions
    """
    try:
        import uuid

        # Get default values from environment
        default_server = os.getenv("VPN_SERVER")
        default_port = int(os.getenv("VPN_PORT", "0")) or None

        # Use custom values or defaults
        server = server or default_server
        port = port or default_port

        # Generate user UUID
        user_uuid = str(uuid.uuid4())

        # Generate config
        config_text = generate_config_text(
            user_id, user_uuid=user_uuid, server=server, port=port
        )
        vless_link = generate_vless_link(user_uuid=user_uuid, server=server, port=port)

        return VPNConfigResponse(
            user_id=user_id,
            username=username,
            vless_link=vless_link,
            config_text=config_text,
        )
    except Exception as e:
        logger.error(f"Error generating VPN config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
@limiter.limit("30/minute")
async def create_vpn_config(
    request: Request, config_request: VPNConfigRequest
) -> VPNConfigResponse:
    """
    Create VPN configuration for a user.

    Args:
        request: VPN config request data

    Returns:
        VPN configuration with VLESS link and detailed instructions
    """
    return await get_vpn_config(
        request=request,
        user_id=config_request.user_id,
        username=config_request.username,
        server=config_request.server,
        port=config_request.port,
    )


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
    """Get VPN status with caching (30 seconds TTL)."""
    server = os.getenv("VPN_SERVER", "")
    port = int(os.getenv("VPN_PORT", "0")) or 0

    status = await _check_vpn_connectivity(server, port)
    active_users = int(os.getenv("VPN_ACTIVE_USERS", "0"))
    uptime = int(os.getenv("VPN_UPTIME_SECONDS", "0"))

    return {
        "status": status,
        "server": server,
        "port": port,
        "protocol": "VLESS+Reality",
        "active_users": active_users,
        "uptime": uptime,
    }


@router.get("/status")
@limiter.limit("60/minute")
async def get_vpn_status(request: Request) -> VPNStatusResponse:
    """
    Get VPN server status.

    Returns:
        Current VPN server status (cached for 30 seconds)
    """
    try:
        data = await _get_vpn_status_cached()
        return VPNStatusResponse(**data)
    except Exception as e:
        logger.error(f"Error getting VPN status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


VPN_USERS_CACHE_KEY = "vpn:users:list"


async def _fetch_vpn_users_from_db(db: Session) -> Dict[str, Any]:
    """Fetch VPN users from database."""
    db_users = db.query(User).filter(User.plan != "free").all()
    users = [
        {
            "user_id": u.id,
            "username": u.email.split("@")[0] if u.email else "unknown",
            "vless_link": "vless://...",
            "last_connected": "2024-01-20 10:30:00",
        }
        for u in db_users
    ]
    return {"total": len(users), "users": users}


@router.get("/users")
@limiter.limit("10/minute")
async def get_vpn_users(
    request: Request, admin=Depends(verify_admin_token), db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get list of active VPN users.

    Returns:
        List of active VPN users (cached for 60 seconds)
    """
    try:
        # Try to get from cache first
        cached_result = await cache.get(VPN_USERS_CACHE_KEY)
        if cached_result is not None:
            logger.debug("VPN users cache hit")
            return cached_result

        # Cache miss - fetch from database
        logger.debug("VPN users cache miss")
        result = await _fetch_vpn_users_from_db(db)

        # Cache for 60 seconds
        await cache.set(VPN_USERS_CACHE_KEY, result, ttl=60)

        return result
    except Exception as e:
        logger.error(f"Error getting VPN users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user/{user_id}")
@limiter.limit("5/minute")
async def delete_vpn_user(
    request: Request,
    user_id: int,
    admin=Depends(verify_admin_token),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Delete VPN user.

    Args:
        user_id: User ID to delete

    Returns:
        Confirmation of deletion
    """
    try:
        user = db.query(User).filter(User.id == str(user_id)).first()
        if user:
            user.plan = "free"  # Downgrade to free
            db.commit()

            # Invalidate users cache
            await cache.delete(VPN_USERS_CACHE_KEY)
            logger.info(f"Downgraded user {user_id} to free plan, cache invalidated")

            return {
                "success": True,
                "message": f"User {user_id} downgraded to free plan",
            }
        else:
            return {"success": False, "message": f"User {user_id} not found"}
    except Exception as e:
        logger.error(f"Error deleting VPN user: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
