#!/usr/bin/env python3
"""Generate NFT metadata JSON for supporter badges.

Usage:
  python generate_nft_metadata.py --output all_badges_metadata.json
Optionally --separate-dir nft_metadata to create individual files.
"""
import json
import argparse
from pathlib import Path
from datetime import datetime

BADGES = [
    {
        "code": "NODE",
        "name": "Node Supporter",
        "tier": 1,
        "governance_weight": 1.0,
        "domain": "infrastructure",
        "description": "Early supporter ensuring base mesh stability.",
        "rarity": "common"
    },
    {
        "code": "ARCH",
        "name": "Mesh Architect",
        "tier": 2,
        "governance_weight": 1.5,
        "domain": "architecture",
        "description": "Contributor to mesh topology & design patterns.",
        "rarity": "uncommon"
    },
    {
        "code": "GUARD",
        "name": "Resilience Guardian",
        "tier": 3,
        "governance_weight": 2.0,
        "domain": "security",
        "description": "High-tier guardian supporting audits & resilience.",
        "rarity": "rare"
    },
    {
        "code": "POL",
        "name": "Policy Sentinel",
        "tier": 2,
        "governance_weight": 1.5,
        "domain": "policy",
        "description": "Focus on Zero-Trust policies & enforcement.",
        "rarity": "uncommon"
    },
    {
        "code": "QNT",
        "name": "Quantum Pioneer",
        "tier": 3,
        "governance_weight": 2.0,
        "domain": "cryptography",
        "description": "Advocate for post-quantum readiness.",
        "rarity": "rare"
    },
    {
        "code": "ACC",
        "name": "Accessibility Champion",
        "tier": 2,
        "governance_weight": 1.5,
        "domain": "inclusion",
        "description": "Ensures inclusive participation & localization.",
        "rarity": "uncommon"
    },
    {
        "code": "RTG",
        "name": "Routing Alchemist",
        "tier": 3,
        "governance_weight": 2.0,
        "domain": "optimization",
        "description": "Improves ML routing & adaptive heuristics.",
        "rarity": "rare"
    },
    {
        "code": "DRP",
        "name": "Disaster Response Ally",
        "tier": 2,
        "governance_weight": 1.5,
        "domain": "field",
        "description": "Supports real-world deployment in crisis zones.",
        "rarity": "uncommon"
    },
    {
        "code": "DAO",
        "name": "DAO Steward",
        "tier": 3,
        "governance_weight": 2.0,
        "domain": "governance",
        "description": "Enhances decentralized decision processes.",
        "rarity": "rare"
    },
    {
        "code": "SIG",
        "name": "Signal Bearer",
        "tier": 1,
        "governance_weight": 1.0,
        "domain": "advocacy",
        "description": "Spreads awareness & uplifts outreach.",
        "rarity": "common"
    }
]


def build_metadata():
    ts = datetime.utcnow().isoformat()+"Z"
    out = []
    for b in BADGES:
        meta = {
            "name": f"x0tta6bl4 Badge: {b['name']}",
            "description": b['description'],
            "image": f"ipfs://CID/{b['code'].lower()}.png",  # placeholder
            "external_url": "https://example.com/x0tta6bl4/badges",
            "attributes": [
                {"trait_type": "Code", "value": b['code']},
                {"trait_type": "Tier", "value": b['tier']},
                {"trait_type": "Governance Weight", "value": b['governance_weight']},
                {"trait_type": "Domain", "value": b['domain']},
                {"trait_type": "Rarity", "value": b['rarity']},
                {"trait_type": "Generated At", "value": ts}
            ]
        }
        out.append(meta)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', default='all_badges_metadata.json')
    ap.add_argument('--separate-dir', default=None)
    args = ap.parse_args()
    meta = build_metadata()
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Metadata written: {args.output} ({len(meta)} badges)")
    if args.separate_dir:
        out_dir = Path(args.separate_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, m in enumerate(meta, start=1):
            code = m['attributes'][0]['value'].lower()
            p = out_dir / f"{i:02d}_{code}.json"
            p.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"Individual metadata files written to {out_dir}")

if __name__ == '__main__':
    main()
