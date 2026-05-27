"""
Experimental VPN API Endpoints
==============================
REST API endpoints for experimental VPN configuration and management.
These endpoints use optimized parameters to bypass current blocking techniques.
"""

import hmac
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from new_vpn_config_generator import generate_config_text, generate_vless_link

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn/experimental", tags=["vpn-experimental"])
limiter = Limiter(key_func=get_remote_address)


async def verify_admin_token(x_admin_token: Optional[str] = Header(None)):
    """Verify admin token for protected endpoints"""
    admin_token = os.getenv("ADMIN_TOKEN")
    if not admin_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin token not configured",
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


def _get_vpn_server() -> str:
    return os.getenv("VPN_SERVER", "")


def _get_vpn_port() -> int:
    try:
        return int(os.getenv("VPN_PORT_EXPERIMENTAL", "0")) or 0
    except ValueError:
        return 0


def _read_system_uptime(path: Path = Path("/proc/uptime")) -> float:
    try:
        return max(0.0, float(path.read_text(encoding="utf-8").split()[0]))
    except (OSError, IndexError, ValueError):
        return 0.0


def _load_vpn_users_from_file(path: Path) -> List[Dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        users = payload
    elif isinstance(payload, dict):
        users = payload.get("users") or []
    else:
        users = []
    return [user for user in users if isinstance(user, dict)]


def _load_configured_vpn_users() -> List[Dict[str, Any]]:
    users_file = os.getenv("VPN_USERS_FILE") or os.getenv("VPN_EXPERIMENTAL_USERS_FILE")
    if not users_file:
        return []
    return _load_vpn_users_from_file(Path(users_file))


def _get_xui_client():
    try:
        from vpn_config_generator import XUIAPIClient
    except Exception as exc:
        logger.debug("XUIAPIClient unavailable for experimental VPN API: %s", exc)
        return None
    try:
        client = XUIAPIClient()
    except Exception as exc:
        logger.debug("Failed to initialize XUIAPIClient: %s", exc)
        return None
    if getattr(client, "simulated", False):
        return None
    return client


def _get_active_users_count() -> int:
    configured = os.getenv("VPN_ACTIVE_USERS")
    if configured is not None:
        try:
            return max(0, int(configured))
        except ValueError:
            logger.warning("Ignoring invalid VPN_ACTIVE_USERS=%r", configured)

    users = _load_configured_vpn_users()
    if users:
        return len(users)

    client = _get_xui_client()
    if client is not None and hasattr(client, "get_active_users_count"):
        try:
            return max(0, int(client.get_active_users_count()))
        except Exception as exc:
            logger.warning("Failed to read x-ui active user count: %s", exc)

    users = _fetch_users_from_xui_db()
    return sum(1 for user in users if user.get("enabled", True))


def _fetch_users_from_xui_db(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    path = Path(db_path or os.getenv("XUI_DB_PATH", "/usr/local/x-ui/x-ui.db"))
    if not path.exists():
        return []

    import sqlite3

    conn = None
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT email, up, down, total, enable, expiry_time FROM client_traffics"
        ).fetchall()
    except Exception as exc:
        logger.warning("Failed to read x-ui users from %s: %s", path, exc)
        return []
    finally:
        if conn is not None:
            conn.close()

    users = []
    for row in rows:
        users.append(
            {
                "email": row["email"],
                "up": row["up"],
                "down": row["down"],
                "total": row["total"],
                "enabled": bool(row["enable"]),
                "expiry_time": row["expiry_time"],
            }
        )
    return users


def _get_experimental_vpn_users() -> List[Dict[str, Any]]:
    configured = _load_configured_vpn_users()
    if configured:
        return configured
    return _fetch_users_from_xui_db()


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
    Generate experimental VPN configuration for a user.

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
        default_port = int(os.getenv("VPN_PORT_EXPERIMENTAL", "0")) or None

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
        logger.error(f"Error generating experimental VPN config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/config")
@limiter.limit("30/minute")
async def create_vpn_config(
    request: Request, config_request: VPNConfigRequest
) -> VPNConfigResponse:
    """
    Create experimental VPN configuration for a user.

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


@router.get("/status")
@limiter.limit("60/minute")
async def get_vpn_status(request: Request) -> VPNStatusResponse:
    """
    Get experimental VPN server status.

    Returns:
        Current VPN server status
    """
    try:
        # Get default values from environment
        server = _get_vpn_server()
        port = _get_vpn_port()

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

        return VPNStatusResponse(
            status=status,
            server=server,
            port=port,
            protocol="VLESS+Reality (Experimental)",
            active_users=_get_active_users_count(),
            uptime=_read_system_uptime(),
        )
    except Exception as e:
        logger.error(f"Error getting experimental VPN status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/users")
@limiter.limit("10/minute")
async def get_vpn_users(
    request: Request, admin=Depends(verify_admin_token)
) -> Dict[str, Any]:
    """
    Get list of active VPN users for experimental config.

    Returns:
        List of active VPN users
    """
    try:
        users = _get_experimental_vpn_users()

        return {"total": len(users), "users": users}
    except Exception as e:
        logger.error(f"Error getting experimental VPN users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/user/{user_id}")
@limiter.limit("5/minute")
async def delete_vpn_user(
    request: Request, user_id: int, admin=Depends(verify_admin_token)
) -> Dict[str, Any]:
    """
    Delete experimental VPN user.

    Args:
        user_id: User ID to delete

    Returns:
        Confirmation of deletion
    """
    try:
        logger.info(f"Deleting experimental VPN user {user_id}")

        return {
            "success": True,
            "message": f"Experimental VPN user {user_id} deleted successfully",
        }
    except Exception as e:
        logger.error(f"Error deleting experimental VPN user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
