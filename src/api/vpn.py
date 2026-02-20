"""
VPN API Endpoints
==================

REST API endpoints for VPN configuration and management.
"""

import hmac
import logging
import os
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


@router.get("/config")
@limiter.limit("30/minute")
async def get_vpn_config(
    request: Request,
    server: Optional[str] = Query(default=None),
    port: Optional[int] = Query(default=None),
    current_user: User = Depends(require_permission("vpn:config")),
) -> VPNConfigResponse:
    """Generate VPN configuration for the authenticated user."""
    # For backward compatibility, map current_user attributes
    # The user_id is now implicitly the current user's ID
    try:
        # Convert UUID to integer if needed by legacy systems, 
        # or handle string IDs properly. For now, assume int based on legacy code.
        # But x0tta6bl4 uses UUIDs mostly. Let's handle both.
        uid_val = hash(current_user.id) % 100000 # Mock int ID from UUID for legacy XUI
        
        return _build_vpn_config(uid_val, current_user.email, current_user.full_name, server, port)
    except Exception as e:
         logger.error(f"Config generation failed: {e}")
         raise HTTPException(status_code=500, detail="Failed to generate config")


@router.post("/config")
@limiter.limit("30/minute")
async def create_vpn_config(
    request: Request,
    config_req: VPNConfigRequest,
    current_user: User = Depends(require_permission("vpn:config")),
) -> VPNConfigResponse:
    """Generate VPN configuration via JSON body."""
    uid_val = hash(current_user.id) % 100000
    return _build_vpn_config(
        uid_val,
        current_user.email,
        current_user.full_name,
        config_req.server,
        config_req.port,
    )


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

        # Use XUI Client to ensure user exists
        vpn_info = xui.create_user(uid, u_email, remark=u_name)

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
    server = os.getenv("VPN_SERVER", "89.125.1.107")
    port = int(os.getenv("VPN_PORT", "39829"))

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
    current_user: User = Depends(require_permission("vpn:status")),
) -> VPNStatusResponse:
    """
    Get VPN server status.
    """
    try:
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
    current_user: User = Depends(require_permission("vpn:admin")),
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
    current_user: User = Depends(require_permission("vpn:admin")),
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
    current_user: User = Depends(require_permission("vpn:admin")),
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
