import json
import logging
import os
import sys

import httpx

# Ensure project root is in path for relative imports if needed
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

try:
    from vpn_config_generator import generate_vless_link as _gen_link_legacy
except ImportError:
    _gen_link_legacy = None

logger = logging.getLogger(__name__)


class XrayManager:
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
        # Use legacy generator if available, otherwise construct manually
        if _gen_link_legacy:
            return _gen_link_legacy(user_uuid, server=host, port=port)

        # Fallback construction
        sni = os.getenv("REALITY_SNI", "google.com")
        fp = os.getenv("REALITY_FINGERPRINT", "chrome")
        pbk = os.getenv("REALITY_PUBLIC_KEY", "")
        sid = os.getenv("REALITY_SHORT_ID", "")

        if not pbk:
            raise ValueError("REALITY_PUBLIC_KEY environment variable must be set")

        link = (
            f"vless://{user_uuid}@{host}:{port}"
            f"?security=reality&encryption=none&pbk={pbk}&headerType=none&fp={fp}&type=ws&sni={sni}&sid={sid}&path=%2Fvless"
            f"#{email}"
        )
        return link

    @staticmethod
    async def add_user(user_uuid: str, email: str, restart: bool = True):
        """Add user to Xray config and optionally restart."""
        config_path = "/etc/xray/config.json"

        # In non-Docker dev env, might be local
        if not os.path.exists(config_path):
            if os.path.exists("xray_main_config.json"):
                config_path = "xray_main_config.json"
            else:
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

            if updated:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)

                if restart:
                    return await XrayManager.restart_container()

            return True

        except Exception as e:
            logger.error(f"Failed to update Xray config: {e}")
            return False

    @staticmethod
    async def restart_container(container_name: str = "x0tta6bl4-xray"):
        """Restart Xray container via Docker Socket."""
        # Clean way to interact with Docker socket
        socket_path = "/var/run/docker.sock"
        if not os.path.exists(socket_path):
            logger.warning("Docker socket not found, cannot restart container")
            return False

        try:
            async with httpx.AsyncClient(
                transport=httpx.HTTPTransport(uds=socket_path)
            ) as client:
                resp = await client.post(
                    f"http://localhost/containers/{container_name}/restart"
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
            logger.error(f"Docker API error: {e}")
            return False
