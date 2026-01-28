"""
VPN API Endpoints
==================

REST API endpoints for VPN configuration and management.
"""
from fastapi import APIRouter, HTTPException, Depends, Request, Header, status
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import os
import hmac

from slowapi import Limiter
from slowapi.util import get_remote_address

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from vpn_config_generator import generate_vless_link, generate_config_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn", tags=["vpn"])
limiter = Limiter(key_func=get_remote_address)


async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Admin token not configured")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, admin_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


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
    port: Optional[int] = None
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
        default_server = os.getenv("VPN_SERVER", "89.125.1.107")
        default_port = int(os.getenv("VPN_PORT", "39829"))
        
        # Use custom values or defaults
        server = server or default_server
        port = port or default_port
        
        # Generate user UUID
        user_uuid = str(uuid.uuid4())
        
        # Generate config
        config_text = generate_config_text(user_id, user_uuid=user_uuid, server=server, port=port)
        vless_link = generate_vless_link(user_uuid=user_uuid, server=server, port=port)
        
        return VPNConfigResponse(
            user_id=user_id,
            username=username,
            vless_link=vless_link,
            config_text=config_text
        )
    except Exception as e:
        logger.error(f"Error generating VPN config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
@limiter.limit("30/minute")
async def create_vpn_config(
    request: Request,
    config_request: VPNConfigRequest
) -> VPNConfigResponse:
    """
    Create VPN configuration for a user.
    
    Args:
        request: VPN config request data
        
    Returns:
        VPN configuration with VLESS link and detailed instructions
    """
    return await get_vpn_config(
        user_id=config_request.user_id,
        username=config_request.username,
        server=config_request.server,
        port=config_request.port
    )


@router.get("/status")
@limiter.limit("60/minute")
async def get_vpn_status(request: Request) -> VPNStatusResponse:
    """
    Get VPN server status.
    
    Returns:
        Current VPN server status
    """
    try:
        # Get default values from environment
        server = os.getenv("VPN_SERVER", "89.125.1.107")
        port = int(os.getenv("VPN_PORT", "39829"))
        
        # Check if VPN is reachable (simple TCP connect test)
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect((server, port))
            status = "online"
        except Exception:
            status = "offline"
        finally:
            sock.close()
        
        # Mock data for active users and uptime (in production, this should come from real stats)
        active_users = 5
        uptime = 86400  # 24 hours
        
        return VPNStatusResponse(
            status=status,
            server=server,
            port=port,
            protocol="VLESS+Reality",
            active_users=active_users,
            uptime=uptime
        )
    except Exception as e:
        logger.error(f"Error getting VPN status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
@limiter.limit("10/minute")
async def get_vpn_users(request: Request, admin=Depends(verify_admin_token)) -> Dict[str, Any]:
    """
    Get list of active VPN users.
    
    Returns:
        List of active VPN users
    """
    try:
        # Mock data (in production, this should come from x-ui API or database)
        users = [
            {"user_id": 12345, "username": "user1", "vless_link": "vless://...", "last_connected": "2024-01-20 10:30:00"},
            {"user_id": 67890, "username": "user2", "vless_link": "vless://...", "last_connected": "2024-01-20 11:45:00"},
            {"user_id": 11223, "username": "user3", "vless_link": "vless://...", "last_connected": "2024-01-20 12:15:00"}
        ]
        
        return {
            "total": len(users),
            "users": users
        }
    except Exception as e:
        logger.error(f"Error getting VPN users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user/{user_id}")
@limiter.limit("5/minute")
async def delete_vpn_user(
    request: Request,
    user_id: int,
    admin=Depends(verify_admin_token)
) -> Dict[str, Any]:
    """
    Delete VPN user.
    
    Args:
        user_id: User ID to delete
        
    Returns:
        Confirmation of deletion
    """
    try:
        # Mock deletion (in production, this should call x-ui API)
        logger.info(f"Deleting VPN user {user_id}")
        
        return {
            "success": True,
            "message": f"User {user_id} deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting VPN user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
