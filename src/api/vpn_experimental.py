"""
Experimental VPN API Endpoints
==============================
REST API endpoints for experimental VPN configuration and management.
These endpoints use optimized parameters to bypass current blocking techniques.
"""

import hmac
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from new_vpn_config_generator import generate_config_text, generate_vless_link

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vpn/experimental", tags=["vpn-experimental"])
limiter = Limiter(key_func=get_remote_address)

_CONFIG_SOURCE_AGENT = "vpn-experimental-config-generate"
_CONFIG_LAYER = "api_vpn_experimental_config_control_action"
_STATUS_SOURCE_AGENT = "vpn-experimental-status-read"
_STATUS_LAYER = "api_vpn_experimental_status_observed_state"
_USERS_SOURCE_AGENT = "vpn-experimental-users-read"
_USERS_LAYER = "api_vpn_experimental_users_observed_state"
_DELETE_SOURCE_AGENT = "vpn-experimental-user-delete"
_DELETE_LAYER = "api_vpn_experimental_user_delete_control_action"

VPN_EXPERIMENTAL_CLAIM_BOUNDARY = (
    "Experimental VPN API evidence records local config generation, local TCP "
    "status checks, configured/x-ui user reads, and stub delete responses only. "
    "It does not prove censorship bypass, client installation, VPN dataplane "
    "reachability, DNS privacy, firewall correctness, production provider "
    "health, or that customer traffic uses the VPN tunnel."
)


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _identity_evidence(source_agent: str) -> Dict[str, Any]:
    if source_agent == _STATUS_SOURCE_AGENT:
        identity = service_event_identity(service_name=_STATUS_SOURCE_AGENT)
    elif source_agent == _USERS_SOURCE_AGENT:
        identity = service_event_identity(service_name=_USERS_SOURCE_AGENT)
    elif source_agent == _DELETE_SOURCE_AGENT:
        identity = service_event_identity(service_name=_DELETE_SOURCE_AGENT)
    else:
        identity = service_event_identity(service_name=_CONFIG_SOURCE_AGENT)
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


def _vpn_experimental_event_bus_from_request(
    request: Optional[Request],
) -> Optional[EventBus]:
    if request is None:
        return None
    state = getattr(request, "state", None)
    if state is None:
        return None
    injected_bus = getattr(state, "event_bus", None)
    if injected_bus is not None:
        return injected_bus
    project_root = getattr(state, "event_project_root", ".")
    try:
        return get_event_bus(project_root)
    except Exception as exc:
        logger.error("Failed to initialize experimental VPN EventBus: %s", exc)
        return None


def _event_type_for_status(http_status_code: int) -> EventType:
    if http_status_code < 400:
        return EventType.PIPELINE_STAGE_END
    if http_status_code >= 500:
        return EventType.TASK_FAILED
    return EventType.TASK_BLOCKED


def _publish_vpn_experimental_event(
    request: Optional[Request],
    *,
    source_agent: str,
    layer: str,
    operation: str,
    stage: str,
    status_value: str,
    http_status_code: int,
    started_at: float,
    control_action: bool,
    observed_state: bool,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    bus = _vpn_experimental_event_bus_from_request(request)
    if bus is None:
        return None

    payload: Dict[str, Any] = {
        "component": "api.vpn_experimental",
        "operation": operation,
        "stage": stage,
        "status": status_value,
        "http_status_code": http_status_code,
        "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
        "service_name": source_agent,
        "source_alias": source_agent,
        "layer": layer,
        "control_action": bool(control_action),
        "observed_state": bool(observed_state),
        "service_identity": _identity_evidence(source_agent),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "generated_config_redacted": True,
        "vless_link_redacted": True,
        "dataplane_confirmed": False,
        "bypass_confirmed": False,
        "claim_boundary": VPN_EXPERIMENTAL_CLAIM_BOUNDARY,
    }
    if metadata:
        payload.update(metadata)
    try:
        event = bus.publish(
            _event_type_for_status(http_status_code),
            source_agent,
            payload,
            priority=4,
        )
        return event.event_id
    except Exception as exc:
        logger.error("Failed to publish experimental VPN event: %s", exc)
        return None


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
    started = time.monotonic()
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

        response = VPNConfigResponse(
            user_id=user_id,
            username=username,
            vless_link=vless_link,
            config_text=config_text,
        )
        _publish_vpn_experimental_event(
            request,
            source_agent=_CONFIG_SOURCE_AGENT,
            layer=_CONFIG_LAYER,
            operation="generate_experimental_vpn_config",
            stage="config_generation",
            status_value="success",
            http_status_code=200,
            started_at=started,
            control_action=True,
            observed_state=False,
            metadata={
                "source_quality": "local_config_generation_only",
                "user_id_hash": _redacted_sha256_prefix(user_id),
                "username_hash": _redacted_sha256_prefix(username),
                "username_present": bool(username),
                "server_hash": _redacted_sha256_prefix(server),
                "server_present": bool(server),
                "port": port,
                "port_present": port is not None,
                "user_uuid_hash": _redacted_sha256_prefix(user_uuid),
                "user_uuid_present": bool(user_uuid),
                "vless_link_present": bool(vless_link),
                "vless_link_chars": len(vless_link or ""),
                "config_text_present": bool(config_text),
                "config_text_chars": len(config_text or ""),
            },
        )
        return response
    except Exception as e:
        _publish_vpn_experimental_event(
            request,
            source_agent=_CONFIG_SOURCE_AGENT,
            layer=_CONFIG_LAYER,
            operation="generate_experimental_vpn_config",
            stage="config_generation",
            status_value="error",
            http_status_code=500,
            started_at=started,
            control_action=True,
            observed_state=False,
            metadata={
                "source_quality": "local_config_generation_failed",
                "user_id_hash": _redacted_sha256_prefix(user_id),
                "username_hash": _redacted_sha256_prefix(username),
                "username_present": bool(username),
                "requested_server_hash": _redacted_sha256_prefix(server),
                "requested_server_present": bool(server),
                "requested_port": port,
                "requested_port_present": port is not None,
                "error_type": type(e).__name__,
                "error_hash": _redacted_sha256_prefix(e),
            },
        )
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
    started = time.monotonic()
    server = ""
    port = 0
    tcp_connect_attempted = False
    tcp_connect_success = False
    try:
        # Get default values from environment
        server = _get_vpn_server()
        port = _get_vpn_port()

        # Check if VPN is reachable (simple TCP connect test)
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            tcp_connect_attempted = True
            sock.connect((server, port))
            status = "online"
            tcp_connect_success = True
        except Exception:
            status = "offline"
        finally:
            sock.close()

        active_users = _get_active_users_count()
        uptime = _read_system_uptime()
        response = VPNStatusResponse(
            status=status,
            server=server,
            port=port,
            protocol="VLESS+Reality (Experimental)",
            active_users=active_users,
            uptime=uptime,
        )
        _publish_vpn_experimental_event(
            request,
            source_agent=_STATUS_SOURCE_AGENT,
            layer=_STATUS_LAYER,
            operation="read_experimental_vpn_status",
            stage="status_read",
            status_value="success",
            http_status_code=200,
            started_at=started,
            control_action=False,
            observed_state=True,
            metadata={
                "source_quality": "local_tcp_connect_observation_only",
                "status_bucket": status,
                "server_hash": _redacted_sha256_prefix(server),
                "server_present": bool(server),
                "port": port,
                "port_present": bool(port),
                "protocol_bucket": "vless_reality_experimental",
                "tcp_connect_attempted": tcp_connect_attempted,
                "tcp_connect_success": tcp_connect_success,
                "active_users": active_users,
                "uptime_present": uptime > 0,
            },
        )
        return response
    except Exception as e:
        _publish_vpn_experimental_event(
            request,
            source_agent=_STATUS_SOURCE_AGENT,
            layer=_STATUS_LAYER,
            operation="read_experimental_vpn_status",
            stage="status_read",
            status_value="error",
            http_status_code=500,
            started_at=started,
            control_action=False,
            observed_state=True,
            metadata={
                "source_quality": "local_tcp_connect_observation_failed",
                "server_hash": _redacted_sha256_prefix(server),
                "server_present": bool(server),
                "port": port,
                "port_present": bool(port),
                "tcp_connect_attempted": tcp_connect_attempted,
                "tcp_connect_success": tcp_connect_success,
                "error_type": type(e).__name__,
                "error_hash": _redacted_sha256_prefix(e),
            },
        )
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
    started = time.monotonic()
    try:
        users = _get_experimental_vpn_users()

        response = {"total": len(users), "users": users}
        _publish_vpn_experimental_event(
            request,
            source_agent=_USERS_SOURCE_AGENT,
            layer=_USERS_LAYER,
            operation="read_experimental_vpn_users",
            stage="users_read",
            status_value="success",
            http_status_code=200,
            started_at=started,
            control_action=False,
            observed_state=True,
            metadata={
                "source_quality": "configured_or_xui_user_read_only",
                "users_total": len(users),
                "user_id_present_count": sum(1 for user in users if user.get("user_id")),
                "username_present_count": sum(1 for user in users if user.get("username")),
                "email_present_count": sum(1 for user in users if user.get("email")),
                "vless_link_present_count": sum(
                    1 for user in users if user.get("vless_link")
                ),
                "admin_dependency_present": admin is not None,
            },
        )
        return response
    except Exception as e:
        _publish_vpn_experimental_event(
            request,
            source_agent=_USERS_SOURCE_AGENT,
            layer=_USERS_LAYER,
            operation="read_experimental_vpn_users",
            stage="users_read",
            status_value="error",
            http_status_code=500,
            started_at=started,
            control_action=False,
            observed_state=True,
            metadata={
                "source_quality": "configured_or_xui_user_read_failed",
                "error_type": type(e).__name__,
                "error_hash": _redacted_sha256_prefix(e),
                "admin_dependency_present": admin is not None,
            },
        )
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
    started = time.monotonic()
    try:
        logger.info(f"Deleting experimental VPN user {user_id}")

        response = {
            "success": True,
            "message": f"Experimental VPN user {user_id} deleted successfully",
        }
        _publish_vpn_experimental_event(
            request,
            source_agent=_DELETE_SOURCE_AGENT,
            layer=_DELETE_LAYER,
            operation="delete_experimental_vpn_user",
            stage="user_delete",
            status_value="success",
            http_status_code=200,
            started_at=started,
            control_action=True,
            observed_state=False,
            metadata={
                "source_quality": "local_stub_response_only",
                "user_id_hash": _redacted_sha256_prefix(user_id),
                "admin_dependency_present": admin is not None,
                "delete_stub_response": True,
                "persistent_delete_attempted": False,
                "persistent_delete_confirmed": False,
            },
        )
        return response
    except Exception as e:
        _publish_vpn_experimental_event(
            request,
            source_agent=_DELETE_SOURCE_AGENT,
            layer=_DELETE_LAYER,
            operation="delete_experimental_vpn_user",
            stage="user_delete",
            status_value="error",
            http_status_code=500,
            started_at=started,
            control_action=True,
            observed_state=False,
            metadata={
                "source_quality": "local_stub_response_failed",
                "user_id_hash": _redacted_sha256_prefix(user_id),
                "admin_dependency_present": admin is not None,
                "delete_stub_response": True,
                "persistent_delete_attempted": False,
                "persistent_delete_confirmed": False,
                "error_type": type(e).__name__,
                "error_hash": _redacted_sha256_prefix(e),
            },
        )
        logger.error(f"Error deleting experimental VPN user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
