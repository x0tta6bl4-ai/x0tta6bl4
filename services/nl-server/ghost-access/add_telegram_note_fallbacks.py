#!/usr/bin/env python3
"""
Integrates discovered VLESS Reality nodes from Telegram notes into Ghost Access Fallback Registry.
"""

from __future__ import annotations

import json
from pathlib import Path

FALLBACK_REGISTRY = Path("/mnt/projects/.tmp/vless_fallback_registry.json")

TELEGRAM_DISCOVERED_NODES = [
    {
        "name": "VLESS-DeepL-Fallback-185",
        "ip": "185.42.163.126",
        "port": 443,
        "uuid": "8aba88fb-afb9-4320-ae28-c1bb27d332a2",
        "public_key": "LVFBktLLFmSMfq1893eEvf9u66WzkoayasM5XUHYFSA",
        "sni": "deepl.com",
        "short_id": "ba7338c9a5fb2956",
        "fingerprint": "firefox",
        "flow": "xtls-rprx-vision",
        "uri": "vless://8aba88fb-afb9-4320-ae28-c1bb27d332a2@185.42.163.126:443?security=reality&encryption=none&pbk=LVFBktLLFmSMfq1893eEvf9u66WzkoayasM5XUHYFSA&headerType=none&fp=firefox&spx=%2F&type=tcp&flow=xtls-rprx-vision&sni=deepl.com&sid=ba7338c9a5fb2956#Vless-users-x0tta6bl4-salut"
    }
]


def update_fallback_registry():
    FALLBACK_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    
    existing = []
    if FALLBACK_REGISTRY.exists():
        try:
            existing = json.loads(FALLBACK_REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    # Merge nodes
    existing_uris = {node.get("uri") for node in existing}
    added = 0
    for node in TELEGRAM_DISCOVERED_NODES:
        if node["uri"] not in existing_uris:
            existing.append(node)
            added += 1

    FALLBACK_REGISTRY.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Integrated {added} new VLESS Reality fallback nodes into registry ({FALLBACK_REGISTRY})")


if __name__ == "__main__":
    update_fallback_registry()
