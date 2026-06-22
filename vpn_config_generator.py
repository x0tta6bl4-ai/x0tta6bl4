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

# Default Reality parameters
REALITY_SHORT_ID = os.getenv("REALITY_SHORT_ID", "6b")
REALITY_FINGERPRINT = os.getenv("REALITY_FINGERPRINT", "chrome")
REALITY_SPIDERX = os.getenv("REALITY_SPIDERX", "/")
ENABLE_OBFUSCATION_ROTATION = os.getenv("VPN_ROTATE_OBFUSCATION", "false").lower() == "true"

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
