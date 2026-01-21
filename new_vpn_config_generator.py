#!/usr/bin/env python3
"""
New VPN Config Generator for x0tta6bl4 - Experimental Inbound
Generates VLESS + Reality configs with new parameters to bypass current blocks
"""

import os
import uuid
import urllib.parse
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# EXPERIMENTAL VPN Server Configuration (New Inbound)
VPN_SERVER = os.getenv("VPN_SERVER", "89.125.1.107")
VPN_PORT = int(os.getenv("VPN_PORT_EXPERIMENTAL", "39830"))

# Reality Configuration - Optimized for bypassing current blocks
REALITY_PUBLIC_KEY = os.getenv("REALITY_PUBLIC_KEY_EXPERIMENTAL", "yWfOuehQZwVHPodTvo3TJEGUYUbxmGTeAxMUBWpww")
REALITY_PRIVATE_KEY = os.getenv("REALITY_PRIVATE_KEY_EXPERIMENTAL")
REALITY_SNI = os.getenv("REALITY_SNI_EXPERIMENTAL", "www.cloudflare.com")
REALITY_SHORT_ID = os.getenv("REALITY_SHORT_ID_EXPERIMENTAL", "7a")
REALITY_FINGERPRINT = os.getenv("REALITY_FINGERPRINT_EXPERIMENTAL", "firefox")
REALITY_SPIDERX = os.getenv("REALITY_SPIDERX_EXPERIMENTAL", "/cdn-cgi/trace")

# Security check
if not REALITY_PRIVATE_KEY:
    logger.warning("⚠️ REALITY_PRIVATE_KEY_EXPERIMENTAL not set in environment! Set it in .env file")


def generate_uuid() -> str:
    """Generate unique UUID for user"""
    return str(uuid.uuid4())


def generate_vless_link(
    user_uuid: Optional[str] = None,
    server: str = VPN_SERVER,
    port: int = VPN_PORT,
    sni: str = REALITY_SNI,
    short_id: str = REALITY_SHORT_ID,
    public_key: str = REALITY_PUBLIC_KEY,
    fingerprint: str = REALITY_FINGERPRINT,
    spiderx: str = REALITY_SPIDERX,
    remark: str = "x0tta6bl4_VPN_Experimental"
) -> str:
    """
    Generate VLESS + Reality link for user with experimental parameters
    """
    if user_uuid is None:
        raise ValueError("user_uuid is required!")
    
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
    server: str = VPN_SERVER,
    port: int = VPN_PORT
) -> str:
    """
    Generate human-readable config text for user with experimental parameters
    """
    if user_uuid is None:
        raise ValueError("user_uuid is required!")
    
    vless_link = generate_vless_link(user_uuid, server, port)
    
    config_text = f"""══════════════════════════════════════════════════════════
✅ x0tta6bl4 VPN Config (EXPERIMENTAL)
══════════════════════════════════════════════════════════

User ID: {user_id}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Server: {server}:{port}
Protocol: VLESS + Reality (Experimental)

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
⚠️ ВАЖНО (ЭКСПЕРИМЕНТАЛЬНАЯ ВЕРСИЯ):
══════════════════════════════════════════════════════════

• Это экспериментальная конфигурация для обхода новых блокировок
• Использует оптимизированные параметры Reality
• Если не работает, вернитесь к стандартной конфигурации на порту 39829
• При проблемах пишите в поддержку: @x0tta6bl4_support

══════════════════════════════════════════════════════════
"""
    
    return config_text


def generate_qr_code_data(vless_link: str) -> str:
    """Generate QR code data for VLESS link"""
    return vless_link


# Test function
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_uuid = generate_uuid()
    print("Generated experimental VPN config:")
    print(generate_config_text(1001, test_uuid))
