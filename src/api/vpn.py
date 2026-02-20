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
from vpn_config_generator import generate_config_text, generate_vless_link, XUIAPIClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn", tags=["vpn"])
limiter = Limiter(key_func=get_remote_address)

# Initialize XUI Client
xui = XUIAPIClient()


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
    email: str  # Required for x-ui
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
@router.post("/config")
async def handle_vpn_config(
    request: Request,
    config_req: Optional[VPNConfigRequest] = None,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    username: Optional[str] = None,
    server: Optional[str] = None,
    port: Optional[int] = None,
) -> VPNConfigResponse:
    """
    Generate or create VPN configuration. (Handles both GET and POST)
    """
    try:
        if config_req:
            uid = config_req.user_id
            u_email = config_req.email
            u_name = config_req.username
            srv = config_req.server
            prt = config_req.port
        else:
            uid = user_id
            u_email = email
            u_name = username
            srv = server
            prt = port

        if not uid or not u_email:
            raise HTTPException(status_code=400, detail="user_id and email are required")

        # Use XUI Client to ensure user exists
        vpn_info = xui.create_user(uid, u_email, remark=u_name)
        
        # Override server/port if custom ones provided (for config text only)
        final_server = srv or vpn_info['server']
        final_port = prt or vpn_info['port']

        config_text = generate_config_text(
            uid, user_uuid=vpn_info['uuid'], server=final_server, port=final_port
        )

        return VPNConfigResponse(
            user_id=uid,
            username=u_name,
            vless_link=vpn_info['vless_link'],
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
async def get_vpn_status(request: Request) -> VPNStatusResponse:
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


@router.get("/users")
@limiter.limit("10/minute")
async def get_vpn_users(
    request: Request, admin=Depends(verify_admin_token)
) -> Dict[str, Any]:
    """
    Get list of active VPN users from x-ui.
    """
    try:
        cached_result = await cache.get(VPN_USERS_CACHE_KEY)
        if cached_result is not None:
            return cached_result

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
    admin=Depends(verify_admin_token)
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
