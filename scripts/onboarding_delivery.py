"""Onboarding Delivery Matrix - Single Source of Truth for Ghost Access.

Defines client recommendations, delivery methods, and official store links.
"""

from typing import Dict, List, Optional, TypedDict

class DeliveryPayload(TypedDict):
    primary: str
    deep_link_scheme: Optional[str]
    store_url: str
    store_hint: str
    fallbacks: List[str]

# Matrix from docs/ghost-access/ghost-access-bot-newbie-onboarding-ru.md v3.3
DELIVERY_MATRIX: Dict[tuple, DeliveryPayload] = {
    ("iphone", "happ"): {
        "primary": "deep_link",
        "deep_link_scheme": "happ://add/",
        "store_url": "https://apps.apple.com/app/happ-proxy/id6444651333",
        "store_hint": "App Store, поиск 'Happ'",
        "fallbacks": ["qr", "plain_vless"],
    },
    ("iphone", "hiddify"): {
        "primary": "deep_link",
        "deep_link_scheme": "hiddify://import/",
        "store_url": "https://apps.apple.com/app/hiddify-next/id6477340058",
        "store_hint": "App Store, поиск 'Hiddify Next'",
        "fallbacks": ["qr", "plain_vless"],
    },
    ("android", "hiddify"): {
        "primary": "deep_link",
        "deep_link_scheme": "hiddify://import/",
        "store_url": "https://play.google.com/store/apps/details?id=app.hiddify.com",
        "store_hint": "Google Play или GitHub, 'Hiddify Next'",
        "fallbacks": ["qr", "plain_vless"],
    },
    ("windows", "v2rayn"): {
        "primary": "subscription_url",
        "deep_link_scheme": None,
        "store_url": "https://github.com/2dust/v2rayN/releases",
        "store_hint": "GitHub 2dust/v2rayN releases",
        "fallbacks": ["qr", "plain_vless"],
    },
    ("mac", "hiddify"): {
        "primary": "deep_link",
        "deep_link_scheme": "hiddify://import/",
        "store_url": "https://apps.apple.com/app/hiddify-next/id6477340058",
        "store_hint": "Mac App Store или GitHub, 'Hiddify Next'",
        "fallbacks": ["subscription_url", "qr", "plain_vless"],
    },
}

def get_delivery_config(device: str, client: str) -> Optional[DeliveryPayload]:
    device = (device or "").lower().strip()
    client = (client or "").lower().strip()
    return DELIVERY_MATRIX.get((device, client))

def render_delivery(device: str, client: str, vless_url: str, subscription_url: str) -> Dict:
    config = get_delivery_config(device, client)
    if not config:
        return {
            "primary": "plain_vless",
            "vless_url": vless_url,
            "qr_data": vless_url,
            "subscription_url": subscription_url,
            "store_url": "https://t.me/ghost_access_news/4", # Fallback help channel
            "store_hint": "поддерживаемое приложение"
        }
        
    result = {
        "primary": config["primary"],
        "store_url": config["store_url"],
        "store_hint": config["store_hint"],
        "vless_url": vless_url,
        "subscription_url": subscription_url,
        "qr_data": vless_url,
    }
    
    if config["deep_link_scheme"]:
        result["deep_link"] = f"{config['deep_link_scheme']}{vless_url}"
        
    return result
