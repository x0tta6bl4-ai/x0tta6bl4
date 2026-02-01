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


# Future: Integration with x-ui API
class XUIAPIClient:
    """
    Client for x-ui API (future implementation)
    For now, uses static config
    """
    
    def __init__(self, api_url: str = "http://89.125.1.107:628", api_key: Optional[str] = None):
        self.api_url = api_url
        self.api_key = api_key
    
    def create_user(self, user_id: int, username: Optional[str] = None) -> Dict:
        """
        Create new VPN user via x-ui API
        
        TODO: Implement when x-ui API is available
        """
        # Generate unique UUID for user
        user_uuid = generate_uuid()
        
        # TODO: Call x-ui API to create inbound
        # For now, return static config
        
        logger.warning("x-ui API integration not implemented yet, using static config")
        
        return {
            'uuid': user_uuid,
            'server': VPN_SERVER,
            'port': VPN_PORT,
            'vless_link': generate_vless_link(user_uuid)
        }
    
    def delete_user(self, user_id: int) -> bool:
        """
        Delete VPN user via x-ui API
        
        TODO: Implement when x-ui API is available
        """
        logger.warning("x-ui API integration not implemented yet")
        return False

