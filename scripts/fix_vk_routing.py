#!/usr/bin/env python3
"""
Fix VK & RU routing in Xray config for Moscow and NL servers.
Ensures all VK domains & CDNs (vk.com, vk.me, userapi.com, vkuseraccess.com, vk-cdn.net, geosite:vk)
go to 'direct' outbound.
On NL, ensures default fallback outbound is 'direct' instead of looping to 'nl-beta'.
"""

import json
import sys
from pathlib import Path

VK_DOMAINS = [
    "geosite:category-ru",
    "geosite:vk",
    "domain:vk.com",
    "domain:vk.ru",
    "domain:vk.me",
    "domain:userapi.com",
    "domain:vkuseraccess.com",
    "domain:vk-cdn.net",
    "domain:vk-portal.net"
]

def update_config(config_dict, is_nl=False):
    routing = config_dict.get("routing", {})
    rules = routing.get("rules", [])

    # 1. Update or insert VK / RU domain rule
    ru_domain_rule_found = False
    for rule in rules:
        domains = rule.get("domain", [])
        if "geosite:category-ru" in domains or any("vk" in d for d in domains):
            # Update domain list
            rule["domain"] = list(dict.fromkeys(domains + VK_DOMAINS))
            rule["outboundTag"] = "direct"
            ru_domain_rule_found = True
            break

    if not ru_domain_rule_found:
        # Add new rule
        rules.insert(3, {
            "type": "field",
            "domain": VK_DOMAINS,
            "outboundTag": "direct"
        })

    # 2. On NL server, fallback rule should be 'direct'
    if is_nl:
        for rule in rules:
            if rule.get("network") == "tcp,udp" and rule.get("outboundTag") == "nl-beta":
                rule["outboundTag"] = "direct"

    routing["rules"] = rules
    config_dict["routing"] = routing
    return config_dict

def main():
    if len(sys.argv) < 2:
        print("Usage: fix_vk_routing.py <input_config.json> [is_nl]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    is_nl = len(sys.argv) > 2 and sys.argv[2] in ("1", "true", "nl")

    with open(input_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    updated = update_config(config, is_nl=is_nl)

    with open(input_path, "w", encoding="utf-8") as f:
        json.dump(updated, f, indent=2, ensure_ascii=False)

    print(f"Successfully updated VK routing in {input_path} (is_nl={is_nl})")

if __name__ == "__main__":
    main()
