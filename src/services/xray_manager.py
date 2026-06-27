from __future__ import annotations
import json
import logging
import os
import sys
import urllib.parse
from typing import Any, Dict, Optional

import httpx

from src.core.thinking.agent_thinking import AgentThinkingCoach

# Ensure project root is in path for relative imports if needed
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    from vpn_config_generator import generate_vless_link as _gen_link_legacy
except ImportError:
    _gen_link_legacy = None

logger = logging.getLogger(__name__)

_XRAY_THINKING_COACH = AgentThinkingCoach(
    agent_id="xray-manager",
    role="security",
    capabilities=("zero-trust", "ops", "network"),
)
_XRAY_LAST_THINKING_CONTEXT: Dict[str, Any] = {}


def _hash_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    import hashlib

    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _prepare_xray_thinking_context(
    *,
    task_type: str,
    goal: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Prepare redacted thinking context for Xray config/link decisions."""
    global _XRAY_LAST_THINKING_CONTEXT
    context: Dict[str, Any] = {
        "type": task_type,
        "goal": goal,
        "constraints": {
            "redact_user_uuid": True,
            "redact_email": True,
            "redact_reality_public_key": True,
            "redact_docker_socket_details": True,
        },
        "safety_boundary": (
            "Do not expose user identifiers, emails, Reality keys, generated VPN "
            "links, Docker socket details, or claim client connectivity from local "
            "configuration mutations."
        ),
    }
    if extra:
        context.update(extra)
    _XRAY_LAST_THINKING_CONTEXT = _XRAY_THINKING_COACH.prepare_task(context)
    return _XRAY_LAST_THINKING_CONTEXT


class XrayManager:
    @staticmethod
    def get_thinking_status() -> Dict[str, Any]:
        """Expose thinking profile and latest redacted Xray decision context."""
        return {
            "thinking": _XRAY_THINKING_COACH.status(),
            "last_thinking_context": _XRAY_LAST_THINKING_CONTEXT,
        }

    @staticmethod
    def generate_vless_link(
        user_uuid: str, email: str, server: str = None, port: int = 443
    ) -> str:
        """Generate a VLESS Reality link."""
        host = (
            server
            or os.getenv("PUBLIC_DOMAIN")
            or os.getenv("XRAY_HOST")
            or "localhost"
        )
        _prepare_xray_thinking_context(
            task_type="xray_vless_link_generation",
            goal="generate a VLESS Reality link without exposing user or key material",
            extra={
                "host_hash": _hash_text(host),
                "host_present": bool(host),
                "port": int(port),
                "legacy_generator_available": _gen_link_legacy is not None,
                "user_uuid_present": bool(user_uuid),
                "email_present": bool(email),
            },
        )
        # Use legacy generator if available, otherwise construct manually
        if _gen_link_legacy:
            return _gen_link_legacy(user_uuid, server=host, port=port)

        # Fallback construction
        sni = os.getenv("REALITY_SNI", "google.com")
        fp = os.getenv("REALITY_FINGERPRINT", "chrome")
        pbk = os.getenv("REALITY_PUBLIC_KEY", "")
        sid = os.getenv("REALITY_SHORT_ID", "6b")
        spiderx = urllib.parse.quote(os.getenv("REALITY_SPIDERX", "/"), safe="")

        if not pbk:
            _prepare_xray_thinking_context(
                task_type="xray_vless_link_generation",
                goal="reject VLESS link generation when Reality public key is missing",
                extra={
                    "host_hash": _hash_text(host),
                    "port": int(port),
                    "reality_public_key_present": False,
                },
            )
            raise ValueError("REALITY_PUBLIC_KEY environment variable must be set")

        link = (
            f"vless://{user_uuid}@{host}:{port}"
            f"?type=tcp"
            f"&encryption=none"
            f"&security=reality"
            f"&pbk={pbk}"
            f"&fp={fp}"
            f"&sni={sni}"
            f"&sid={sid}"
            f"&spx={spiderx}"
            f"&flow=xtls-rprx-vision"
            f"#{urllib.parse.quote(email)}"
        )
        return link

    @staticmethod
    async def add_user(user_uuid: str, email: str, restart: bool = True):
        """Add user to Xray config and optionally restart."""
        config_path = "/etc/xray/config.json"
        _prepare_xray_thinking_context(
            task_type="xray_add_user",
            goal="add a VLESS client to local Xray config without exposing user data",
            extra={
                "user_uuid_present": bool(user_uuid),
                "email_present": bool(email),
                "restart_requested": bool(restart),
            },
        )

        # In non-Docker dev env, might be local
        if not os.path.exists(config_path):
            if os.path.exists("xray_main_config.json"):
                config_path = "xray_main_config.json"
            else:
                _prepare_xray_thinking_context(
                    task_type="xray_add_user",
                    goal="record missing Xray config without exposing user data",
                    extra={
                        "status": "config_missing",
                        "restart_requested": bool(restart),
                    },
                )
                logger.warning(f"Xray config not found at {config_path}")
                return False

        try:
            with open(config_path, "r") as f:
                config = json.load(f)

            # Find VLESS inbound
            updated = False
            if "inbounds" in config:
                for inbound in config["inbounds"]:
                    if inbound["protocol"] == "vless":
                        clients = inbound["settings"]["clients"]
                        # Check duplication
                        if not any(c.get("id") == user_uuid for c in clients):
                            clients.append(
                                {
                                    "id": user_uuid,
                                    "email": email,
                                    "flow": (
                                        "xtls-rprx-vision"
                                        if inbound.get("streamSettings", {}).get(
                                            "network"
                                        )
                                        == "tcp"
                                        else ""
                                    ),
                                }
                            )
                            updated = True
                            logger.info(f"Added user {email} ({user_uuid}) to config")
                        else:
                            logger.info(f"User {email} already exists")
            _prepare_xray_thinking_context(
                task_type="xray_add_user",
                goal="record Xray client config mutation outcome",
                extra={
                    "status": "updated" if updated else "unchanged",
                    "updated": bool(updated),
                    "restart_requested": bool(restart),
                    "inbound_count": len(config.get("inbounds", [])),
                },
            )

            if updated:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)

                if restart:
                    return await XrayManager.restart_container()

            return True

        except Exception as e:
            _prepare_xray_thinking_context(
                task_type="xray_add_user",
                goal="record Xray config update failure without exposing user data",
                extra={"status": "failed", "error_type": type(e).__name__},
            )
            logger.error(f"Failed to update Xray config: {e}")
            return False

    @staticmethod
    async def restart_container(container_name: str = "x0tta6bl4-xray"):
        """Restart Xray container via Docker Socket."""
        # Clean way to interact with Docker socket
        socket_path = "/var/run/docker.sock"
        _prepare_xray_thinking_context(
            task_type="xray_container_restart",
            goal="restart Xray container through local Docker socket when available",
            extra={
                "container_name_hash": _hash_text(container_name),
                "docker_socket_expected": True,
            },
        )
        if not os.path.exists(socket_path):
            _prepare_xray_thinking_context(
                task_type="xray_container_restart",
                goal="record unavailable Docker socket for Xray restart",
                extra={
                    "status": "docker_socket_missing",
                    "container_name_hash": _hash_text(container_name),
                },
            )
            logger.warning("Docker socket not found, cannot restart container")
            return False

        try:
            async with httpx.AsyncClient(
                transport=httpx.HTTPTransport(uds=socket_path)
            ) as client:
                resp = await client.post(
                    f"http://localhost/containers/{container_name}/restart"
                )
                _prepare_xray_thinking_context(
                    task_type="xray_container_restart",
                    goal="record Docker restart response without exposing socket details",
                    extra={
                        "status_code": int(resp.status_code),
                        "container_name_hash": _hash_text(container_name),
                    },
                )
                if resp.status_code == 204:
                    logger.info(f"✅ Container {container_name} restarted")
                    return True
                else:
                    logger.error(
                        f"❌ Failed to restart container: {resp.status_code} {resp.text}"
                    )
                    return False
        except Exception as e:
            _prepare_xray_thinking_context(
                task_type="xray_container_restart",
                goal="record Docker restart failure without exposing socket details",
                extra={
                    "status": "failed",
                    "error_type": type(e).__name__,
                    "container_name_hash": _hash_text(container_name),
                },
            )
            logger.error(f"Docker API error: {e}")
            return False

