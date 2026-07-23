#!/usr/bin/env python3
"""
Telegram Chat Export Analyzer for x0tta6bl4.
Parses messages.html & messages2.html, extracts all saved notes, links, code snippets,
and categorizes them by priority for implementation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup

file1 = Path("/home/x0ttta6bl4/Telegram Desktop/ChatExport_2026-07-21/messages.html")
file2 = Path("/home/x0ttta6bl4/Telegram Desktop/ChatExport_2026-07-21/messages2.html")

def extract_messages(html_path: Path) -> list[dict]:
    if not html_path.exists():
        return []
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    extracted = []
    
    msg_divs = soup.find_all("div", class_=re.compile(r"message\s+default"))
    for div in msg_divs:
        text_div = div.find("div", class_="text")
        date_div = div.find("div", class_="date")
        if not text_div:
            continue
        
        raw_text = text_div.get_text(separator="\n", strip=True)
        links = [a["href"] for a in text_div.find_all("a", href=True)]
        date_str = date_div.get_text(strip=True) if date_div else ""
        
        extracted.append({
            "date": date_str,
            "text": raw_text,
            "links": links
        })
    return extracted

def main():
    msgs1 = extract_messages(file1)
    msgs2 = extract_messages(file2)
    all_msgs = msgs1 + msgs2
    print(f"Total extracted messages: {len(all_msgs)} (file1: {len(msgs1)}, file2: {len(msgs2)})")
    
    out_json = Path(".tmp/telegram_extracted_notes.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(all_msgs, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # Simple keyword categorizer
    high_priority = []
    med_priority = []
    low_priority = []
    
    keywords_high = ["vpn", "vless", "reality", "xray", "sing-box", "грант", "соцконтракт", "деньги", "продажи", "смета", "руб", "доход", "bot", "docker", "pqc", "ebpf", "spire"]
    keywords_med = ["ai", "llm", "claude", "mcp", "agent", "tool", "github", "python", "script", "rag", "model", "fastapi"]
    
    for m in all_msgs:
        t_lower = m["text"].lower()
        if any(k in t_lower for k in keywords_high):
            high_priority.append(m)
        elif any(k in t_lower for k in keywords_med):
            med_priority.append(m)
        else:
            low_priority.append(m)
            
    summary = {
        "total": len(all_msgs),
        "high_priority_count": len(high_priority),
        "medium_priority_count": len(med_priority),
        "low_priority_count": len(low_priority),
        "sample_high": high_priority[:15],
        "sample_med": med_priority[:10]
    }
    
    out_summary = Path(".tmp/telegram_notes_summary.json")
    out_summary.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Analysis saved to {out_summary}")

if __name__ == "__main__":
    main()
