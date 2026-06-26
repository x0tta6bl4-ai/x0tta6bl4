#!/usr/bin/env python3
"""
VPN Config Generator для x0tta6bl4
Генерирует VLESS + Reality конфиги для пользователей с advanced obfuscation
"""
from __future__ import annotations

import os
import uuid
import urllib.parse
import logging
import random
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Default VPN parameters
VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
VPN_PORT = int(os.getenv("VPN_PORT", "443"))
VPN_SESSION_TOKEN = os.getenv("VPN_SESSION_TOKEN", "")

# Reality parameters
REALITY_PRIVATE_KEY = os.getenv("REALITY_PRIVATE_KEY", "")
REALITY_PUBLIC_KEY = os.getenv("REALITY_PUBLIC_KEY", "xMwVfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww")
REALITY_SNI = os.getenv("REALITY_SNI", "google.com")
REALITY_SHORT_ID = os.getenv("REALITY_SHORT_ID", "6b")
REALITY_FINGERPRINT = os.getenv("REALITY_FINGERPRINT", "chrome")
REALITY_SPIDERX = os.getenv("REALITY_SPIDERX", "/watch?v=dQw4w9WgXcQ")
ENABLE_OBFUSCATION_ROTATION = os.getenv("ENABLE_OBFUSCATION_ROTATION", "false").lower() == "true"

# NODE CONFIGURATIONS (Saturday multi-node setup)
NODE_CONFIGS = {
    "nl": {
        "server": "89.125.1.107",
        "port": 443,
        "public_key": "xMwVfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww",
        "remark": "x0tta6bl4_NL_Master"
    },
    "ru": {
        "server": "TBD_RU_IP", # Will be updated Saturday
        "port": 443,
        "public_key": "TBD_RU_PUB_KEY",
        "remark": "x0tta6bl4_RU_Entry"
    },
    "us": {
        "server": "TBD_US_IP",
        "port": 443,
        "public_key": "TBD_US_PUB_KEY",
        "remark": "x0tta6bl4_US_Exit"
    }
}

# Rotating SNI options
ROTATING_SNI_OPTIONS = [
    "www.cloudflare.com", "www.microsoft.com", "www.apple.com", "www.amazon.com",
    "www.netflix.com", "www.reddit.com", "www.linkedin.com", "www.github.com"
]

# ✅ SECURITY FIX: Removed DEFAULT_UUID - always require user_uuid.
# Private Reality keys are not needed for ordinary config rendering, so missing
# key checks must not run at import time.
if not REALITY_PRIVATE_KEY and os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true":
    logger.warning("⚠️ REALITY_PRIVATE_KEY not set in environment! Set it in .env file")


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_vless_link(
    user_uuid: Optional[str] = None,
    node_id: str = "nl",
    sni: str = None,
    short_id: str = REALITY_SHORT_ID,
    fingerprint: str = None,
    spiderx: str = None
) -> str:
    if user_uuid is None:
        raise ValueError("user_uuid is required!")
    
    node = NODE_CONFIGS.get(node_id, NODE_CONFIGS["nl"])
    server = node["server"]
    port = node["port"]
    public_key = node["public_key"]
    remark = node["remark"]
    
    if sni is None:
        sni = random.choice(ROTATING_SNI_OPTIONS) if ENABLE_OBFUSCATION_ROTATION else "google.com"
    if fingerprint is None:
        fingerprint = REALITY_FINGERPRINT
    if spiderx is None:
        spiderx = REALITY_SPIDERX
    
    spiderx_encoded = urllib.parse.quote(spiderx, safe='')
    
    vless_link = (
        f"vless://{user_uuid}@{server}:{port}"
        f"?type=tcp"
        f"&encryption=none"
        f"&security=reality"
        f"&pbk={public_key}"
        f"&fp={fingerprint}"
        f"&sni={sni}"
        f"&sid={short_id}"
        f"&spx={spiderx_encoded}"
        f"&flow=xtls-rprx-vision"
        f"#{urllib.parse.quote(remark)}"
    )
    return vless_link


def generate_config_text(
    user_id: int,
    user_uuid: Optional[str] = None,
    node_id: str = "nl"
) -> str:
    if user_uuid is None:
        raise ValueError("user_uuid is required!")
    
    node = NODE_CONFIGS.get(node_id, NODE_CONFIGS["nl"])
    vless_link = generate_vless_link(user_uuid, node_id=node_id)
    
    config_text = f"""══════════════════════════════════════════════════════════
✅ x0tta6bl4 VPN Config ({node['remark']})
══════════════════════════════════════════════════════════

User ID: {user_id}
Node: {node_id.upper()} ({node['server']})
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{vless_link}

📱 Инструкция: Скопируйте ссылку и вставьте в v2rayNG/Shadowrocket.
══════════════════════════════════════════════════════════
"""
    return config_text


def generate_qr_code_data(vless_link: str) -> str:
    return vless_link


class XUIAPIClient:
    """
    Client for x-ui database integration.
    Manages inbounds and clients directly in x-ui.db.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.getenv("XUI_DB_PATH", "/usr/local/x-ui/x-ui.db")
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        if not os.path.exists(self.db_path):
            logger.info("x-ui database not found at %s. Using simulation mode.", self.db_path)
            self.simulated = True
        else:
            self.simulated = False

    def rotate_reality_credentials(self) -> Dict[str, str]:
        """
        Generates new X25519 keys for Reality and updates the inbound config in x-ui.db.
        This is a critical security operation for self-healing.
        """
        if not REALITY_PRIVATE_KEY and os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true":
            raise RuntimeError("REALITY_PRIVATE_KEY must be set for production Reality rotation")
        if self.simulated:
            logger.info("Simulating Reality key rotation...")
            return {"public_key": "simulated_pub", "private_key": "simulated_priv"}

        import sqlite3
        import json
        import subprocess

        try:
            try:
                result = subprocess.run(
                    ["xray", "x25519"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10
                )
            except FileNotFoundError:
                logger.warning("⚠️ 'xray' command not found, falling back to simulated Reality rotation.")
                return {"public_key": "simulated_pub", "private_key": "simulated_priv", "short_id": "sim_id"}
                
            output = result.stdout.splitlines()
            if len(output) < 2:
                raise ValueError(f"Unexpected xray output: expected 2 lines, got {len(output)}")
            
            if ": " not in output[0] or ": " not in output[1]:
                raise ValueError(f"Unexpected xray output format: {output}")
            
            new_priv = output[0].split(": ", 1)[1].strip()
            new_pub = output[1].split(": ", 1)[1].strip()
            
            if len(new_priv) < 40 or len(new_pub) < 40:
                raise ValueError(f"Invalid key length received from xray: priv={len(new_priv)}, pub={len(new_pub)}")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT id, stream_settings FROM inbounds WHERE port = ?", (VPN_PORT,))
            row = cursor.fetchone()
            if not row:
                conn.close()
                raise ValueError(f"Reality inbound not found on port {VPN_PORT}")

            inbound_id, stream_json = row
            stream_settings = json.loads(stream_json)
            
            reality_settings = stream_settings.get("realitySettings", {})
            reality_settings["privateKey"] = new_priv
            
            new_short_id = os.urandom(4).hex()
            reality_settings["shortIds"] = [new_short_id]
            
            stream_settings["realitySettings"] = reality_settings
            
            cursor.execute(
                "UPDATE inbounds SET stream_settings = ? WHERE id = ?",
                (json.dumps(stream_settings), inbound_id)
            )
            
            conn.commit()
            conn.close()
            
            try:
                result = subprocess.run(
                    ["systemctl", "restart", "x-ui"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode != 0:
                    logger.error(f"Failed to restart x-ui: {result.stderr}")
                    raise RuntimeError(f"x-ui restart failed: {result.stderr}")
                logger.info("x-ui restarted successfully")
            except subprocess.TimeoutExpired:
                logger.error("x-ui restart timed out after 30s")
                raise RuntimeError("x-ui restart timed out after 30s")
            except FileNotFoundError:
                logger.warning("systemctl not found - cannot restart x-ui. Please restart manually.")
            
            logger.info(f"✅ Reality keys rotated successfully. New ShortID: {new_short_id}")
            return {"public_key": new_pub, "private_key": new_priv, "short_id": new_short_id}

        except Exception as e:
            logger.error(f"❌ Failed to rotate Reality credentials: {e}")
            raise RuntimeError(f"Reality rotation failed: {e}")

    def create_user(self, user_id: int, email: str, remark: Optional[str] = None) -> Dict:
        """
        Create new VPN client for the main VLESS inbound.
        """
        user_uuid = generate_uuid()
        remark = remark or f"user_{user_id}_{email.split('@')[0]}"

        if self.simulated:
            return {
                'uuid': user_uuid,
                'server': VPN_SERVER,
                'port': VPN_PORT,
                'vless_link': generate_vless_link(user_uuid, remark=remark)
            }

        import sqlite3
        import json

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT id, settings FROM inbounds WHERE port = ?", (VPN_PORT,))
            inbound = cursor.fetchone()

            if not inbound:
                conn.close()
                raise ValueError(f"No inbound found on port {VPN_PORT}")

            inbound_id, settings_json = inbound
            settings = json.loads(settings_json)
            clients = settings.get("clients", [])

            for client in clients:
                if client.get("email") == email:
                    conn.close()
                    return {
                        'uuid': client.get("id"),
                        'server': VPN_SERVER,
                        'port': VPN_PORT,
                        'vless_link': generate_vless_link(client.get("id"), remark=remark)
                    }

            new_client = {
                "id": user_uuid,
                "email": email,
                "flow": "xtls-rprx-vision",
                "totalGB": 0,
                "expiryTime": 0,
                "subscriptionId": str(uuid.uuid4())[:8]
            }
            clients.append(new_client)
            settings["clients"] = clients

            cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", (json.dumps(settings), inbound_id))

            cursor.execute(
                "INSERT INTO client_traffics (inbound_id, enable, email, up, down, expiry_time, total) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (inbound_id, 1, email, 0, 0, 0, 0)
            )

            conn.commit()
            conn.close()

            logger.info(f"✅ Created VPN user {email} (UUID: {user_uuid}) in x-ui")

            return {
                'uuid': user_uuid,
                'server': VPN_SERVER,
                'port': VPN_PORT,
                'vless_link': generate_vless_link(user_uuid, remark=remark)
            }

        except Exception as e:
            logger.error(f"Failed to create user in x-ui: {e}")
            raise

    def get_active_users_count(self) -> int:
        """Get count of active users from client_traffics."""
        if self.simulated:
            return random.randint(5, 15)

        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM client_traffics WHERE enable = 1")
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0

    def delete_user(self, email: str) -> bool:
        """Remove user from inbound settings and client_traffics."""
        if self.simulated:
            return True

        import sqlite3
        import json

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT id, settings FROM inbounds WHERE port = ?", (VPN_PORT,))
            inbound = cursor.fetchone()
            if not inbound:
                conn.close()
                return False

            inbound_id, settings_json = inbound
            settings = json.loads(settings_json)
            clients = [c for c in settings.get("clients", []) if c.get("email") != email]
            settings["clients"] = clients

            cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", (json.dumps(settings), inbound_id))
            cursor.execute("DELETE FROM client_traffics WHERE email = ?", (email,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to delete user {email} from x-ui: {e}")
            return False

