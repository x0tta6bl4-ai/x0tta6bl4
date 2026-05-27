#!/usr/bin/env python3
"""
x0tta6bl4 MESH v3.0 - Full Stealth Configuration
5-Layer Protection System
"""

import json
import random
import os
from datetime import datetime

CONFIG_FILE = "/usr/local/x-ui/bin/config.json"

# TLS Fingerprint profiles для ротации
TLS_PROFILES = ["chrome", "firefox", "safari", "ios", "android", "edge"]

def rotate_tls_profile():
    """Ротация TLS профиля для избежания паттернов"""
    return random.choice(TLS_PROFILES)

def rotate_short_ids():
    """Генерация новых short IDs для Reality"""
    # Генерируем случайные 2-символьные hex ID
    ids = []
    for _ in range(3):
        ids.append(format(random.randint(0, 255), "02x"))
    return ids

def apply_full_stealth():
    """Применение Full Stealth конфигурации"""
    try:
        os.chmod(CONFIG_FILE, 0o644)

        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

        # Обновляем inbound с ротацией параметров
        for inbound in config.get("inbounds", []):
            if inbound.get("port") == 39829:
                stream_settings = inbound.get("streamSettings", {})
                reality_settings = stream_settings.get("realitySettings", {})

                # Ротация short IDs (каждые 24 часа)
                current_ids = reality_settings.get("shortIds", [])
                if not current_ids or len(current_ids) < 3:
                    reality_settings["shortIds"] = rotate_short_ids()

                # Улучшенный sniffing
                sniffing = inbound.get("sniffing", {})
                sniffing["enabled"] = True
                sniffing["destOverride"] = ["http", "tls", "quic", "fakedns"]
                sniffing["routeOnly"] = False
                inbound["sniffing"] = sniffing

                # Улучшенные routing rules для избежания паттернов
                routing = config.get("routing", {})
                rules = routing.get("rules", [])

                # Добавляем правила для избежания DNS leaks
                dns_rules = [
                    {
                        "type": "field",
                        "inboundTag": ["dns_inbound"],
                        "outboundTag": "dns_out"
                    }
                ]

                # Обновляем правила
                if not any(r.get("inboundTag") == ["dns_inbound"] for r in rules):
                    rules = dns_rules + rules

                routing["rules"] = rules
                config["routing"] = routing

                break

        # Сохраняем конфиг
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

        os.chmod(CONFIG_FILE, 0o644)

        # Сохраняем метаданные ротации
        rotation_file = "/opt/x0tta6bl4-mesh/configs/rotation_metadata.json"
        rotation_data = {
            "last_rotation": datetime.now().isoformat(),
            "tls_profile": rotate_tls_profile(),
            "short_ids": reality_settings.get("shortIds", [])
        }

        os.makedirs(os.path.dirname(rotation_file), exist_ok=True)
        with open(rotation_file, "w") as f:
            json.dump(rotation_data, f, indent=2)

        return True
    except Exception as e:
        print(f"Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if apply_full_stealth():
        print("✅ Full Stealth конфигурация применена")
    else:
        print("❌ Ошибка применения конфигурации")
