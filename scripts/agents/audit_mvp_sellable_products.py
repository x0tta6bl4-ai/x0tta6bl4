#!/usr/bin/env python3
"""Audit MVP and sellable product surfaces in this repo.

The audit separates installable product packages from service offers and
outbound assets. A green commercial registry row is treated as input, not proof.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OFFER_REGISTRY = ROOT / "go-to-market" / "offer_verification_registry.json"
PRODUCT_REGISTRY = ROOT / "products" / "production-readiness.json"
DEFAULT_JSON = ROOT / "docs" / "verification" / "mvp-sellable-products-audit-latest.json"
DEFAULT_MD = ROOT / "docs" / "verification" / "mvp-sellable-products-audit-latest.md"


PRICE_RE = re.compile(r"(цена|price|\$\s?\d|\d+\s?(usd|rub|₽)|фикс)", re.IGNORECASE)
TIMELINE_RE = re.compile(r"(срок|день|дня|дней|day|days|week|sprint|pilot)", re.IGNORECASE)
DELIVERABLE_RE = re.compile(
    r"(deliverables|что получите|что делаю|scope|скоуп|acceptance criteria|outputs?|результат)",
    re.IGNORECASE,
)
BOUNDARY_RE = re.compile(
    r"(out of scope|assumptions|do not|not a|not as|не обещаю|не является|boundary|claim boundary|evidence-gap|gap)",
    re.IGNORECASE,
)
MVP_RE = re.compile(r"\b(mvp|mpv)\b|минимальн", re.IGNORECASE)
OUTBOUND_ASSET_RE = re.compile(r"(upwork|proposal|profile)", re.IGNORECASE)
CANDIDATE_NAME_RE = re.compile(
    r"(offer|product|one[-_]?pager|pitch|landing|workshop|starter|launch|mvp|mpv|proposal|profile)",
    re.IGNORECASE,
)
DISCOVERY_ROOTS = (
    ROOT / "go-to-market",
    ROOT / "docs" / "sales",
    ROOT / "docs" / "commercial",
    ROOT / "products",
)
DISCOVERY_EXCLUDE_PARTS = {
    "sample_outputs",
    "demo_packs",
    "self_tests",
    "publish_waves",
    "nft_metadata",
    "out",
}


@dataclass(frozen=True)
class ProductAudit:
    name: str
    path: str
    verifier: str
    status: str
    verifier_passed: bool
    release_decision: str
    evidence_path: str
    category: str = "installable_product"

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "verifier": self.verifier,
            "status": self.status,
            "verifier_passed": self.verifier_passed,
            "release_decision": self.release_decision,
            "evidence_path": self.evidence_path,
            "category": self.category,
        }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def rel(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def classify_offer(offer: dict[str, Any], primary_text: str) -> str:
    name = str(offer.get("name") or "")
    primary = str(offer.get("primary_artifact") or "")
    haystack = f"{name}\n{primary}"
    if OUTBOUND_ASSET_RE.search(haystack):
        return "outbound_asset"
    if "MVP" in name or MVP_RE.search(primary_text):
        return "mvp_service_offer"
    return "service_offer"


def validate_offer(offer: dict[str, Any]) -> dict[str, Any]:
    primary = Path(str(offer.get("primary_artifact") or ""))
    supporting = [Path(str(item)) for item in offer.get("supporting_artifacts", []) if isinstance(item, str)]
    missing = [str(path) for path in [primary, *supporting] if not path.exists()]
    primary_text = read_text(primary)
    category = classify_offer(offer, primary_text)

    signals = {
        "has_primary_artifact": primary.exists(),
        "has_all_supporting_artifacts": not any(not path.exists() for path in supporting),
        "has_price": bool(PRICE_RE.search(primary_text)),
        "has_timeline": bool(TIMELINE_RE.search(primary_text)),
        "has_deliverables": bool(DELIVERABLE_RE.search(primary_text)),
        "has_boundary_or_assumptions": bool(BOUNDARY_RE.search(primary_text)),
        "has_sample_or_demo_support": any(
            "sample_outputs" in str(path) or "demo_packs" in str(path) for path in supporting
        ),
    }
    green = offer.get("status") == "green"
    sale_ready = (
        green
        and signals["has_primary_artifact"]
        and signals["has_all_supporting_artifacts"]
        and signals["has_deliverables"]
    )
    price_ready = sale_ready and (
        signals["has_price"]
        or category == "outbound_asset"
    )
    weak_points: list[str] = []
    if not green:
        weak_points.append("registry status is not green")
    if missing:
        weak_points.append("missing artifact(s): " + ", ".join(missing))
    if not signals["has_deliverables"]:
        weak_points.append("no explicit deliverables/scope signal in primary artifact")
    if not signals["has_price"] and category != "outbound_asset":
        weak_points.append("no explicit price signal in primary artifact")
    if not signals["has_timeline"] and category != "outbound_asset":
        weak_points.append("no explicit timeline signal in primary artifact")
    if not signals["has_boundary_or_assumptions"]:
        weak_points.append("no clear boundary/assumptions signal in primary artifact")

    return {
        "id": offer.get("id"),
        "name": offer.get("name"),
        "cluster": offer.get("cluster"),
        "registry_status": offer.get("status"),
        "category": category,
        "primary_artifact": rel(primary) if primary.is_absolute() and primary.exists() else str(primary),
        "supporting_artifacts": [rel(path) if path.is_absolute() and path.exists() else str(path) for path in supporting],
        "signals": signals,
        "sale_ready": sale_ready,
        "price_ready": price_ready,
        "weak_points": weak_points,
    }


def registered_paths(product_registry: dict[str, Any], offer_registry: dict[str, Any]) -> set[str]:
    paths: set[str] = {rel(PRODUCT_REGISTRY), rel(OFFER_REGISTRY)}
    for product in product_registry.get("products", []):
        if not isinstance(product, dict):
            continue
        product_path = ROOT / str(product.get("path") or "")
        if product_path.exists():
            for child in product_path.rglob("*"):
                if child.is_file():
                    paths.add(rel(child))
    for offer in offer_registry.get("offers", []):
        if not isinstance(offer, dict):
            continue
        for key in ("primary_artifact",):
            value = offer.get(key)
            if isinstance(value, str):
                path = Path(value)
                if path.exists():
                    paths.add(rel(path))
        for value in offer.get("supporting_artifacts", []):
            if isinstance(value, str):
                path = Path(value)
                if path.exists():
                    paths.add(rel(path))
    return paths


def discover_unregistered_candidates(
    product_registry: dict[str, Any],
    offer_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    registered = registered_paths(product_registry, offer_registry)
    candidates: list[dict[str, Any]] = []
    for root in DISCOVERY_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".md", ".html"}:
                continue
            rel_path = rel(path)
            if rel_path in registered:
                continue
            if any(part in DISCOVERY_EXCLUDE_PARTS for part in path.parts):
                continue
            text = read_text(path)
            name_hit = bool(CANDIDATE_NAME_RE.search(path.name))
            price_hit = bool(PRICE_RE.search(text))
            deliverable_hit = bool(DELIVERABLE_RE.search(text))
            mvp_hit = bool(MVP_RE.search(text) or MVP_RE.search(path.name))
            if not (name_hit or (price_hit and deliverable_hit) or mvp_hit):
                continue
            candidates.append(
                {
                    "path": rel_path,
                    "signals": {
                        "name_hit": name_hit,
                        "has_price": price_hit,
                        "has_deliverables": deliverable_hit,
                        "mvp_hit": mvp_hit,
                    },
                    "classification": "unregistered_commercial_surface",
                    "note": "Not in product registry or offer verification registry; treat as background/draft unless promoted.",
                }
            )
    return candidates


def run_products_verifier(output_dir: Path) -> dict[str, Any]:
    command = [
        sys.executable or "python3",
        "scripts/agents/verify_products_production_readiness.py",
        "--output-dir",
        str(output_dir),
        "--json",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {
            "production_decision": "BLOCKED",
            "products": [],
            "parse_error": "products verifier did not emit JSON",
        }
    payload["command"] = command
    payload["exit_code"] = result.returncode
    payload["stdout_tail"] = (result.stdout or "")[-2000:]
    return payload


def audit_products(product_registry: dict[str, Any], verifier_payload: dict[str, Any]) -> list[ProductAudit]:
    verifier_by_name = {
        item.get("name"): item
        for item in verifier_payload.get("products", [])
        if isinstance(item, dict)
    }
    audits: list[ProductAudit] = []
    for product in product_registry.get("products", []):
        if not isinstance(product, dict):
            continue
        name = str(product.get("name") or "")
        verified = verifier_by_name.get(name, {})
        audits.append(
            ProductAudit(
                name=name,
                path=str(product.get("path") or ""),
                verifier=str(product.get("verifier") or ""),
                status=str(product.get("status") or ""),
                verifier_passed=bool(verified.get("passed")),
                release_decision=str(verified.get("release_decision") or ""),
                evidence_path=str(verified.get("evidence_path") or ""),
            )
        )
    return audits


def build_payload(product_verifier_dir: Path, run_product_verifiers: bool) -> dict[str, Any]:
    product_registry = load_json(PRODUCT_REGISTRY)
    offer_registry = load_json(OFFER_REGISTRY)
    product_verifier_payload = (
        run_products_verifier(product_verifier_dir)
        if run_product_verifiers
        else {"production_decision": "NOT RUN", "products": []}
    )
    product_audits = audit_products(product_registry, product_verifier_payload)
    offer_audits = [
        validate_offer(offer)
        for offer in offer_registry.get("offers", [])
        if isinstance(offer, dict)
    ]
    unregistered_candidates = discover_unregistered_candidates(product_registry, offer_registry)
    mvp_candidates = [
        item for item in offer_audits if item["category"] == "mvp_service_offer"
    ] + [
        audit.to_json() for audit in product_audits
    ]
    summary = {
        "installable_products_total": len(product_audits),
        "installable_products_verified": sum(1 for item in product_audits if item.verifier_passed),
        "offers_total": len(offer_audits),
        "offers_sale_ready": sum(1 for item in offer_audits if item["sale_ready"]),
        "offers_price_ready": sum(1 for item in offer_audits if item["price_ready"]),
        "mvp_candidates_total": len(mvp_candidates),
        "outbound_assets_total": sum(1 for item in offer_audits if item["category"] == "outbound_asset"),
        "offers_with_weak_points": sum(1 for item in offer_audits if item["weak_points"]),
        "unregistered_candidates_total": len(unregistered_candidates),
    }
    return {
        "schema_version": "mvp-sellable-products-audit-v1",
        "generated_at_utc": utc_stamp(),
        "source_of_truth": [
            rel(PRODUCT_REGISTRY),
            rel(OFFER_REGISTRY),
            "STATUS_REALITY.md",
            "x0tta://vpn/doc/status-reality",
        ],
        "summary": summary,
        "product_verifier": {
            "production_decision": product_verifier_payload.get("production_decision"),
            "exit_code": product_verifier_payload.get("exit_code"),
            "output_dir": str(product_verifier_dir),
        },
        "installable_products": [item.to_json() for item in product_audits],
        "offers": offer_audits,
        "unregistered_candidates": unregistered_candidates,
        "mvp_candidates": mvp_candidates,
        "claim_boundary": (
            "This audit validates repo-local product and offer artifacts. It does not validate external demand, "
            "customer willingness to pay, or live Ghost Access/SPB/NL/Open5GS production status."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# MVP And Sellable Products Audit",
        "",
        f"Generated: `{payload['generated_at_utc']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(
        [
            "",
            f"- product_verifier_decision: `{payload['product_verifier']['production_decision']}`",
            "",
            "## Installable Products",
            "",
            "| Product | Status | Verifier | Decision |",
            "|---|---|---|---|",
        ]
    )
    for product in payload["installable_products"]:
        verifier = "PASS" if product["verifier_passed"] else "FAIL"
        lines.append(
            f"| {product['name']} | {product['status']} | {verifier} | {product['release_decision']} |"
        )
    lines.extend(
        [
            "",
            "## Offer Surfaces",
            "",
            "| ID | Offer | Category | Sale Ready | Price Ready | Weak Points |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for offer in payload["offers"]:
        weak = "; ".join(offer["weak_points"]) if offer["weak_points"] else "none"
        lines.append(
            f"| {offer['id']} | {offer['name']} | {offer['category']} | "
            f"{offer['sale_ready']} | {offer['price_ready']} | {weak} |"
        )
    lines.extend(["", "## MVP Candidates", ""])
    for item in payload["mvp_candidates"]:
        lines.append(f"- {item.get('name')} ({item.get('category', 'installable_product')})")
    lines.extend(["", "## Unregistered Candidate Surfaces", ""])
    if payload["unregistered_candidates"]:
        for item in payload["unregistered_candidates"]:
            signals = ", ".join(key for key, value in item["signals"].items() if value)
            lines.append(f"- `{item['path']}` — {signals or 'weak signal'}")
    else:
        lines.append("- none")
    lines.extend(["", "## Boundary", "", payload["claim_boundary"]])
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit MVP and sellable product artifacts")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    parser.add_argument(
        "--product-verifier-dir",
        type=Path,
        default=ROOT / "docs" / "verification" / f"mvp-sellable-products-product-verifiers-{utc_stamp()}",
    )
    parser.add_argument("--skip-product-verifiers", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = build_payload(
        product_verifier_dir=args.product_verifier_dir,
        run_product_verifiers=not args.skip_product_verifiers,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    args.output_md.write_text(render_markdown(payload), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(f"installable_products={payload['summary']['installable_products_verified']}/{payload['summary']['installable_products_total']}")
        print(f"offers_sale_ready={payload['summary']['offers_sale_ready']}/{payload['summary']['offers_total']}")
        print(f"offers_price_ready={payload['summary']['offers_price_ready']}/{payload['summary']['offers_total']}")
        print(f"mvp_candidates={payload['summary']['mvp_candidates_total']}")
        print(f"report={args.output_md}")
    complete = (
        payload["summary"]["installable_products_verified"] == payload["summary"]["installable_products_total"]
        and payload["summary"]["offers_sale_ready"] == payload["summary"]["offers_total"]
    )
    return 0 if complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
