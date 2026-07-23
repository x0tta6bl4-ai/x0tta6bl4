#!/usr/bin/env python3
"""
Deep Categorizer for 1011 Telegram Exported Notes.
Groups notes into actionable priority buckets for x0tta6bl4 execution.
"""

from __future__ import annotations

import json
from pathlib import Path

def main():
    json_path = Path(".tmp/telegram_extracted_notes.json")
    if not json_path.exists():
        print("Notes file not found.")
        return

    notes = json.loads(json_path.read_text(encoding="utf-8"))

    # Priority Categories
    cat_vpn_monetization = []
    cat_grants_social = []
    cat_ai_agents_mcp = []
    cat_infrastructure_mesh = []
    cat_tools_utilities = []
    cat_other = []

    for item in notes:
        text = item.get("text", "").lower()
        links = item.get("links", [])
        entry = {"date": item.get("date"), "text": item.get("text"), "links": links}

        if any(w in text for w in ["vpn", "vless", "reality", "xray", "sing-box", "подписка", "клиент", "бот", "ghost"]):
            cat_vpn_monetization.append(entry)
        elif any(w in text for w in ["грант", "соцконтракт", "соцзащита", "фси", "старт", "деньги", "доход", "руб"]):
            cat_grants_social.append(entry)
        elif any(w in text for w in ["agent", "claude", "mcp", "llm", "ai", "gpt", "prompts", "prompt"]):
            cat_ai_agents_mcp.append(entry)
        elif any(w in text for w in ["mesh", "pqc", "ebpf", "spire", "docker", "kernel", "linux", "zero trust"]):
            cat_infrastructure_mesh.append(entry)
        elif any(w in text for w in ["github.com", "tool", "python", "cli", "app", "ui"]):
            cat_tools_utilities.append(entry)
        else:
            cat_other.append(entry)

    report = {
        "summary_counts": {
            "total_notes": len(notes),
            "vpn_and_monetization": len(cat_vpn_monetization),
            "grants_and_social_contract": len(cat_grants_social),
            "ai_agents_and_mcp": len(cat_ai_agents_mcp),
            "infrastructure_and_mesh": len(cat_infrastructure_mesh),
            "tools_and_utilities": len(cat_tools_utilities),
            "other_archived_notes": len(cat_other)
        },
        "vpn_monetization": cat_vpn_monetization[:25],
        "grants_social": cat_grants_social[:25],
        "ai_agents_mcp": cat_ai_agents_mcp[:25],
        "infrastructure_mesh": cat_infrastructure_mesh[:25],
        "tools_utilities": cat_tools_utilities[:25]
    }

    out_file = Path(".tmp/telegram_categorized_analysis.json")
    out_file.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Deep categorization complete. Saved to {out_file}")
    print(json.dumps(report["summary_counts"], indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
