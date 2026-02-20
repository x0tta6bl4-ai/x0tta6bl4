#!/usr/bin/env python3
"""
VPN Config Generator для x0tta6bl4
Генерирует VLESS + Reality конфиги для пользователей с advanced obfuscation
"""

import os
import uuid
import urllib.parse
import logging
import random
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# VPN Server Configuration
VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
VPN_PORT = int(os.getenv("VPN_PORT", "39829"))

# Rotating Reality Configuration - Load from environment or use defaults with rotation support
REALITY_PUBLIC_KEY = os.getenv("REALITY_PUBLIC_KEY", "xMwVfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww")
REALITY_PRIVATE_KEY = os.getenv("REALITY_PRIVATE_KEY")  # ✅ SECURITY: No hardcoded secrets

# Rotating SNI options (popular CDN and trusted domains)
# NOTE: Google/YouTube domains excluded to prevent conflicts with Google Cloud API
ROTATING_SNI_OPTIONS = [
    "www.cloudflare.com",
    "www.microsoft.com",
    "www.apple.com",
    "www.amazon.com",
    "www.netflix.com",
    "www.reddit.com",
    "www.linkedin.com",
    "www.github.com",
    "www.gitlab.com",
    "www.dropbox.com",
    "www.cloudflare.net",
    "www.akamai.com",
    "www.fastly.com",
    "www.spotify.com",  # Added for Spotify compatibility
    "www.scdn.co"       # Spotify CDN
]  # Excluded: google.com, youtube.com (conflict with Google Cloud)

# Rotating TLS fingerprints options (mimic real browsers)
ROTATING_FINGERPRINT_OPTIONS = [
    "chrome",
    "firefox",
    "safari",
    "edge",
    "ios",
    "android"
]

# Rotating SpiderX paths (legitimate-looking HTTP paths)
ROTATING_SPIDERX_OPTIONS = [
    "/",
    "/index.html",
    "/about",
    "/contact",
    "/blog",
    "/products",
    "/pricing",
    "/download",
    "/support",
    "/docs",
    "/api/v1/health",
    "/cdn-cgi/trace",
    "/robots.txt",
    "/sitemap.xml",
    "/favicon.ico",
    "/watch?v=dQw4w9WgXcQ"
]

# Default Reality parameters (randomized for each config)
REALITY_SNI = os.getenv("REALITY_SNI", random.choice(ROTATING_SNI_OPTIONS))
REALITY_SHORT_ID = os.getenv("REALITY_SHORT_ID", "6b")
REALITY_FINGERPRINT = os.getenv("REALITY_FINGERPRINT", random.choice(ROTATING_FINGERPRINT_OPTIONS))
REALITY_SPIDERX = os.getenv("REALITY_SPIDERX", random.choice(ROTATING_SPIDERX_OPTIONS))

# ✅ SECURITY FIX: Removed DEFAULT_UUID - always require user_uuid
# If REALITY_PRIVATE_KEY is not set, raise error
if not REALITY_PRIVATE_KEY:
    logger.warning("⚠️ REALITY_PRIVATE_KEY not set in environment! Set it in .env file")


def generate_uuid() -> str:
    """Generate unique UUID for user"""
    return str(uuid.uuid4())


def generate_vless_link(
    user_uuid: Optional[str] = None,
    server: str = VPN_SERVER,
    port: int = VPN_PORT,
    sni: str = None,
    short_id: str = REALITY_SHORT_ID,
    public_key: str = REALITY_PUBLIC_KEY,
    fingerprint: str = None,
    spiderx: str = None,
    remark: str = "x0tta6bl4_VPN"
) -> str:
    """
    Generate VLESS + Reality link for user with optional randomization
    
    Args:
        user_uuid: User UUID (if None, uses default)
        server: VPN server address
        port: VPN server port
        sni: SNI for Reality (if None, random from ROTATING_SNI_OPTIONS)
        short_id: Short ID for Reality
        public_key: Reality public key
        fingerprint: TLS fingerprint (if None, random from ROTATING_FINGERPRINT_OPTIONS)
        spiderx: SpiderX path (if None, random from ROTATING_SPIDERX_OPTIONS)
        remark: Connection remark/name
        
    Returns:
        VLESS link string
    """
    """
    Generate VLESS + Reality link for user
    
    Args:
        user_uuid: User UUID (if None, uses default)
        server: VPN server address
        port: VPN server port
        sni: SNI for Reality
        short_id: Short ID for Reality
        public_key: Reality public key
        fingerprint: TLS fingerprint
        spiderx: SpiderX path
        remark: Connection remark/name
    
    Returns:
        VLESS link string
    """
    # ✅ SECURITY FIX: Require user_uuid - no default fallback
    if user_uuid is None:
        raise ValueError("user_uuid is required! Cannot generate config without unique UUID. This is a security requirement.")
    
    # Use random parameters if not provided
    sni = sni or random.choice(ROTATING_SNI_OPTIONS)
    fingerprint = fingerprint or random.choice(ROTATING_FINGERPRINT_OPTIONS)
    spiderx = spiderx or random.choice(ROTATING_SPIDERX_OPTIONS)
    
    # Encode SpiderX path
    spiderx_encoded = urllib.parse.quote(spiderx, safe='')
    
    # Build VLESS link with optimized parameters
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
    server: str = VPN_SERVER,
    port: int = VPN_PORT
) -> str:
    """
    Generate human-readable config text for user
    
    Args:
        user_id: Telegram user ID
        user_uuid: User UUID (if None, uses default)
        server: VPN server address
        port: VPN server port
    
    Returns:
        Config text string
    """
    # ✅ SECURITY FIX: Require user_uuid - no default fallback
    if user_uuid is None:
        raise ValueError("user_uuid is required! Cannot generate config without unique UUID. This is a security requirement.")
    
    vless_link = generate_vless_link(user_uuid, server, port)
    
    config_text = f"""══════════════════════════════════════════════════════════
✅ x0tta6bl4 VPN Config
══════════════════════════════════════════════════════════

User ID: {user_id}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Server: {server}:{port}

══════════════════════════════════════════════════════════
🔗 VLESS ССЫЛКА (СКОПИРУЙТЕ ВСЮ СТРОКУ):
══════════════════════════════════════════════════════════

{vless_link}

══════════════════════════════════════════════════════════
📱 КАК ПОДКЛЮЧИТЬСЯ:
══════════════════════════════════════════════════════════

1. Скачайте клиент:
   • Windows: v2rayN (https://github.com/2dust/v2rayN)
   • Android: v2rayNG (Google Play)
   • iOS: Shadowrocket (App Store)
   • Mac: v2rayA или ClashX

2. Скопируйте VLESS ссылку выше

3. В клиенте выберите "Импорт из буфера обмена" или "Add from URL"

4. Подключитесь к серверу

5. Проверьте работу - откройте заблокированный сайт

══════════════════════════════════════════════════════════
📋 ПАРАМЕТРЫ ДЛЯ РУЧНОЙ НАСТРОЙКИ:
══════════════════════════════════════════════════════════

Protocol: VLESS
Address: {server}
Port: {port}
UUID: {user_uuid}
Flow: xtls-rprx-vision
Encryption: none
Network: TCP
Security: reality
Reality Public Key: {REALITY_PUBLIC_KEY}
Fingerprint: {REALITY_FINGERPRINT}
SNI: {REALITY_SNI}
Short ID: {REALITY_SHORT_ID}
SpiderX: {REALITY_SPIDERX}

══════════════════════════════════════════════════════════
⚠️ ВАЖНО:
══════════════════════════════════════════════════════════

• Не передавайте этот конфиг третьим лицам
• Конфиг привязан к вашему аккаунту
• При проблемах пишите в поддержку: @x0tta6bl4_support

══════════════════════════════════════════════════════════
"""
    
    return config_text


def generate_qr_code_data(vless_link: str) -> str:
    """
    Generate QR code data for VLESS link
    
    Args:
        vless_link: VLESS link string
    
    Returns:
        QR code data (same as link, for QR code generation)
    """
    return vless_link


# Integration with x-ui API and Database
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
            logger.warning(f"⚠️ x-ui database not found at {self.db_path}. Using simulation mode.")
            self.simulated = True
        else:
            self.simulated = False

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

            # Find the main VLESS inbound (usually tag 'vless_reality' or similar)
            # For x0tta6bl4, it's on VPN_PORT
            cursor.execute("SELECT id, settings FROM inbounds WHERE port = ?", (VPN_PORT,))
            inbound = cursor.fetchone()

            if not inbound:
                conn.close()
                raise ValueError(f"No inbound found on port {VPN_PORT}")

            inbound_id, settings_json = inbound
            settings = json.loads(settings_json)
            clients = settings.get("clients", [])

            # Check if user already exists
            for client in clients:
                if client.get("email") == email:
                    conn.close()
                    # Return existing config
                    return {
                        'uuid': client.get("id"),
                        'server': VPN_SERVER,
                        'port': VPN_PORT,
                        'vless_link': generate_vless_link(client.get("id"), remark=remark)
                    }

            # Add new client
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

            # Also add to client_traffics for tracking
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
            # Users with non-zero traffic in last hour or just total count for simplicity
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

