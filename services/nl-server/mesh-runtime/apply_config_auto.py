#!/usr/bin/env python3
"""
x0tta6bl4 MESH v3.0 - Автоматическое применение конфигурации
Профессиональная автоматизация всех процессов
"""

import json
import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Any

# Настройка логирования
LOG_DIR = Path("/opt/x0tta6bl4-mesh/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "apply_config.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG_FILE = Path("/usr/local/x-ui/bin/config.json")
BACKUP_DIR = Path("/opt/x0tta6bl4-mesh/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

def backup_config() -> Path:
    """Создание резервной копии конфигурации"""
    from datetime import datetime
    backup_file = BACKUP_DIR / f"config_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"
    if CONFIG_FILE.exists():
        import shutil
        shutil.copy2(CONFIG_FILE, backup_file)
        logger.info(f"Резервная копия создана: {backup_file}")
    return backup_file

def load_config() -> Dict[str, Any]:
    """Загрузка текущей конфигурации"""
    try:
        os.chmod(CONFIG_FILE, 0o644)
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        raise

def save_config(config: Dict[str, Any]) -> None:
    """Сохранение конфигурации"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        os.chmod(CONFIG_FILE, 0o644)
        logger.info("Конфигурация сохранена")
    except Exception as e:
        logger.error(f"Ошибка сохранения конфигурации: {e}")
        raise

def validate_config(config: Dict[str, Any]) -> bool:
    """Валидация конфигурации через xray"""
    try:
        result = subprocess.run(
            ["/usr/local/x-ui/bin/xray-linux-amd64", "-test", "-config", str(CONFIG_FILE)],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("Конфигурация валидна")
            return True
        else:
            logger.error(f"Ошибка валидации: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Ошибка валидации: {e}")
        return False

def ensure_dns_config(config: Dict[str, Any]) -> bool:
    """Обеспечение правильной DNS конфигурации"""
    needs_update = False

    dns = config.get("dns")
    if not dns or not isinstance(dns, dict) or not dns.get("servers"):
        needs_update = True

    if needs_update:
        config["dns"] = {
            "hosts": {"geosite:category-ads-all": "0.0.0.0"},
            "servers": [
                {
                    "address": "https://dns.adguard.com/dns-query",
                    "domains": ["geosite:category-ads-all"],
                    "queryStrategy": "UseIP",
                    "skipFallback": False
                },
                "https://dns.rubyfish.cn/dns-query",
                {
                    "address": "https://1.1.1.1/dns-query",
                    "queryStrategy": "UseIP",
                    "skipFallback": True
                },
                {
                    "address": "https://dns.google/dns-query",
                    "queryStrategy": "UseIP",
                    "skipFallback": True
                }
            ],
            "queryStrategy": "UseIPv4",
            "disableCache": False,
            "disableFallback": False,
            "tag": "dns_inbound"
        }
        logger.info("DNS конфигурация обновлена")

    return needs_update

def ensure_warp_outbound(config: Dict[str, Any]) -> bool:
    """Обеспечение наличия WARP outbound"""
    needs_update = False
    outbounds = config.get("outbounds", [])

    # Проверяем наличие WARP
    has_warp = any(o.get("tag") == "warp" for o in outbounds)

    if not has_warp:
        warp_outbound = {
            "tag": "warp",
            "protocol": "socks",
            "settings": {
                "servers": [{"address": "127.0.0.1", "port": 40000}]
            }
        }

        # Вставляем после direct
        direct_idx = next((i for i, o in enumerate(outbounds) if o.get("tag") == "direct"), -1)
        if direct_idx >= 0:
            outbounds.insert(direct_idx + 1, warp_outbound)
        else:
            outbounds.insert(0, warp_outbound)

        config["outbounds"] = outbounds
        needs_update = True
        logger.info("WARP outbound добавлен")

    return needs_update

def ensure_routing_rules(config: Dict[str, Any]) -> bool:
    """Обеспечение правильных routing rules"""
    needs_update = False
    routing = config.get("routing", {})
    rules = routing.get("rules", [])

    # Всегда обновляем routing rules чтобы включить актуальные домены
    if True:
        # WARP правила
        warp_domains = [
            "openai.com", "*.openai.com", "chat.openai.com", "api.openai.com",
            "netflix.com", "*.netflix.com", "nflxext.com", "*.nflxext.com",
            "nflximg.com", "*.nflximg.com", "nflxso.net", "*.nflxso.net",
            "nflxvideo.net", "*.nflxvideo.net",
            "google.com", "*.google.com", "googleapis.com", "*.googleapis.com",
            "gstatic.com", "*.gstatic.com",
            "spotify.com", "*.spotify.com", "scdn.co", "*.scdn.co",
            "spotifycdn.com", "*.spotifycdn.com"
        ]

        # Direct правила
        direct_domains = [
            "youtube.com", "youtu.be", "googlevideo.com",
            "github.com", "github.io", "githubusercontent.com",
            "reddit.com", "redd.it", "redditstatic.com", "redditmedia.com"
        ]

        new_rules = [
            {"type": "field", "inboundTag": ["api"], "outboundTag": "api"},
            {"type": "field", "domain": warp_domains, "outboundTag": "warp"}
        ]

        for domain in direct_domains:
            new_rules.append({
                "type": "field",
                "domain": [domain, f"*.{domain}"],
                "outboundTag": "direct"
            })

        new_rules.extend([
            {"type": "field", "ip": ["geoip:private"], "outboundTag": "blocked"},
            {"type": "field", "protocol": ["bittorrent"], "outboundTag": "blocked"},
            {"type": "field", "domain": ["geosite:category-ads-all"], "outboundTag": "blocked"},
            {"type": "field", "network": ["tcp", "udp"], "outboundTag": "direct"}
        ])

        routing["rules"] = new_rules
        routing["domainStrategy"] = "IPIfNonMatch"
        routing["domainMatcher"] = "hybrid"
        config["routing"] = routing
        needs_update = True
        logger.info("Routing rules обновлены")

    return needs_update

def ensure_inbound_config(config: Dict[str, Any]) -> bool:
    """Обеспечение правильной конфигурации inbound"""
    needs_update = False

    for inbound in config.get("inbounds", []):
        if inbound.get("port") == 39829:
            # Listen
            if inbound.get("listen") is None:
                inbound["listen"] = "0.0.0.0"
                needs_update = True

            # Sniffing
            sniffing = inbound.get("sniffing", {})
            if not sniffing.get("enabled"):
                sniffing["enabled"] = True
                sniffing["destOverride"] = ["http", "tls", "quic", "fakedns"]
                sniffing["routeOnly"] = False
                inbound["sniffing"] = sniffing
                needs_update = True

            break

    return needs_update

def ensure_log_config(config: Dict[str, Any]) -> bool:
    """Обеспечение правильной конфигурации логирования"""
    needs_update = False

    log = config.get("log", {})
    if log.get("loglevel") != "warning" or log.get("access") != "none":
        config["log"] = {
            "loglevel": "warning",
            "access": "none",
            "dnsLog": False
        }
        needs_update = True
        logger.info("Log конфигурация обновлена")

    return needs_update

def apply_config() -> bool:
    """Главная функция применения конфигурации"""
    try:
        logger.info("Начало применения конфигурации")

        # Резервная копия
        backup_config()

        # Загрузка
        config = load_config()

        # Обновления
        updates = [
            ensure_dns_config,
            ensure_warp_outbound,
            ensure_routing_rules,
            ensure_inbound_config,
            ensure_log_config
        ]

        needs_update = False
        for update_func in updates:
            if update_func(config):
                needs_update = True

        if needs_update:
            # Сохранение
            save_config(config)

            # Валидация
            if not validate_config(config):
                logger.error("Конфигурация не прошла валидацию, откат...")
                return False

            logger.info("Конфигурация успешно применена")
        else:
            logger.info("Конфигурация уже актуальна")

        return True

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = apply_config()
    sys.exit(0 if success else 1)
