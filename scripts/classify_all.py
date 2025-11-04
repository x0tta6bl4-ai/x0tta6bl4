#!/usr/bin/env python3
"""
classify_all.py - Inventory & classification generator for x0tta6bl4.

Usage:
  python3 scripts/classify_all.py --output INVENTORY.json

Heuristics:
  - Category inferred by path keywords
  - Criticality based on filename patterns (architecture, security, spire, mape_k, drift, benchmark)
  - Type: code | doc | asset | artifact

Outputs JSON array of objects:
  {
    "path": "relative/path",
    "category": "Core|Security|DevOps|Infra|ML|Quantum|Governance|Research|Resilience|Docs|Archive|Asset|Other",
    "criticality": "High|Medium|Low|Experimental",
    "type": "code|doc|asset|artifact",
    "size": <bytes>
  }

Exit codes:
  0 success
  1 failure
"""
import argparse
import json
import os
from pathlib import Path

CATEGORY_MAP = [
    ("spire", "Security"),
    ("mtls", "Security"),
    ("security", "Security"),
    ("infra", "Infra"),
    ("infrastructure", "Infra"),
    ("terraform", "Infra"),
    ("k8s", "Infra"),
    ("helm", "Infra"),
    ("devops", "DevOps"),
    ("monitoring", "Resilience"),
    ("drift", "Resilience"),
    ("mape", "Resilience"),
    ("mesh", "Core"),
    ("core", "Core"),
    ("rag", "ML"),
    ("lora", "ML"),
    ("ml", "ML"),
    ("quantum", "Quantum"),
    ("governance", "Governance"),
    ("dao", "Governance"),
    ("research", "Research"),
    ("benchmark", "Performance"),
    ("docs", "Docs"),
    ("archive", "Archive"),
    ("backup", "Archive"),
    ("Camera", "Asset"),
    ("papercraft", "Asset"),
    ("фрезер", "Asset"),
]

CRITICALITY_PATTERNS = {
    "High": ["ARCHITECTURE", "SECURITY", "ROADMAP", "spire", "mtls", "envoy", "MAPE_K", "auto-recovery", "unified-reliability"],
    "Medium": ["benchmark", "drift", "governance", "optimizer", "rag_core", "lora_adapter"],
    "Experimental": ["quantum", "paradox", "snapshot", "prototype"],
}

CODE_EXT = {".py", ".sh", ".yaml", ".yml", ".tf", ".Dockerfile", "Dockerfile"}
DOC_EXT = {".md", ".txt"}
ASSET_EXT = {".jpg", ".png", ".jpeg", ".gif", ".cdr", ".dxf", ".max", ".pdf"}
ARTIFACT_EXT = {".tar.gz", ".zip"}


def infer_category(path: str) -> str:
    lower = path.lower()
    for key, cat in CATEGORY_MAP:
        if key.lower() in lower:
            return cat
    return "Other"


def infer_type(p: Path) -> str:
    name = p.name
    if any(name.endswith(ext) for ext in ARTIFACT_EXT) or name.endswith(".tar.gz"):
        return "artifact"
    if p.suffix in CODE_EXT or name == "Dockerfile":
        return "code"
    if p.suffix in DOC_EXT:
        return "doc"
    if p.suffix in ASSET_EXT:
        return "asset"
    return "other"


def infer_criticality(path: str) -> str:
    upper = path.upper()
    for level, patterns in CRITICALITY_PATTERNS.items():
        for pat in patterns:
            if pat.upper() in upper:
                return level
    return "Low"


def build_inventory(root: Path):
    entries = []
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            rel_path = os.path.relpath(os.path.join(dirpath, fn), root)
            # Skip .git dir
            if rel_path.startswith('.git/'):
                continue
            p = Path(dirpath) / fn
            try:
                size = p.stat().st_size
            except OSError:
                size = 0
            cat = infer_category(rel_path)
            ftype = infer_type(p)
            crit = infer_criticality(rel_path)
            entries.append({
                "path": rel_path,
                "category": cat,
                "criticality": crit,
                "type": ftype,
                "size": size,
            })
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='INVENTORY.json')
    args = ap.parse_args()
    root = Path('.')
    inventory = build_inventory(root)
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(inventory, f, ensure_ascii=False, indent=2)
    print(f"Inventory written: {args.output} (items={len(inventory)})")

if __name__ == '__main__':
    main()
