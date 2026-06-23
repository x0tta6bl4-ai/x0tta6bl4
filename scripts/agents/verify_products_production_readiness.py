#!/usr/bin/env python3
"""Verify every product listed in products/production-readiness.json."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import shlex
import subprocess
from datetime import datetime, timezone
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "products" / "production-readiness.json"
DEFAULT_OUTPUT_BASE = ROOT / "products" / "out"


@dataclass(frozen=True)
class ProductResult:
    name: str
    path: str
    verifier: str
    expected_status: str
    exit_code: int
    passed: bool
    release_decision: str
    log_path: str
    evidence_path: str
    details: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "verifier": self.verifier,
            "expected_status": self.expected_status,
            "exit_code": self.exit_code,
            "passed": self.passed,
            "release_decision": self.release_decision,
            "log_path": self.log_path,
            "evidence_path": self.evidence_path,
            "details": self.details,
        }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_registry(path: Path = REGISTRY) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    products = payload.get("products")
    if not isinstance(products, list):
        raise ValueError(f"{path}: products must be a list")
    return payload


def safe_name(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")


def run_product_verifier(product: dict[str, Any], output_dir: Path) -> ProductResult:
    name = str(product.get("name") or "")
    path = str(product.get("path") or "")
    verifier = str(product.get("verifier") or "")
    expected_status = str(product.get("status") or "")
    product_output = output_dir / safe_name(name or path or "product")
    product_output.mkdir(parents=True, exist_ok=True)
    log_path = product_output / "verifier.log"
    details: list[str] = []

    if not name or not path or not verifier:
        details.append("product entry must include name, path, and verifier")
        log_path.write_text(json.dumps({"errors": details}, indent=2) + "\n", encoding="utf-8")
        return ProductResult(name, path, verifier, expected_status, 1, False, "", str(log_path), "", "; ".join(details))

    command = shlex.split(verifier) + ["--output-dir", str(product_output), "--json"]
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    stdout = result.stdout or ""
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        parsed = {}
        details.append("verifier did not emit JSON")

    release_decision = str(parsed.get("release_decision") or "")
    evidence_path = str(product_output / "release-evidence.json")
    passed = (
        result.returncode == 0
        and release_decision == "READY_FOR_CLIENT_REPO_INSTALL"
        and Path(evidence_path).exists()
    )
    if result.returncode != 0:
        details.append(f"exit={result.returncode}")
    if release_decision != "READY_FOR_CLIENT_REPO_INSTALL":
        details.append(f"release_decision={release_decision!r}")
    if not Path(evidence_path).exists():
        details.append("missing release-evidence.json")

    log_path.write_text(
        json.dumps(
            {
                "command": command,
                "exit_code": result.returncode,
                "stdout": stdout,
                "parsed_json": parsed,
                "passed": passed,
                "details": details,
            },
            indent=2,
            ensure_ascii=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return ProductResult(
        name=name,
        path=path,
        verifier=verifier,
        expected_status=expected_status,
        exit_code=result.returncode,
        passed=passed,
        release_decision=release_decision,
        log_path=str(log_path),
        evidence_path=evidence_path,
        details="; ".join(details),
    )


def production_decision(results: list[ProductResult]) -> str:
    if results and all(result.passed for result in results):
        return "ALL_REGISTERED_PRODUCTS_READY"
    return "BLOCKED"


def build_payload(registry: dict[str, Any], results: list[ProductResult], output_dir: Path, generated_at: str) -> dict[str, Any]:
    return {
        "schema_version": "products-production-verification-v1",
        "generated_at_utc": generated_at,
        "registry": str(REGISTRY.relative_to(ROOT)),
        "output_dir": str(output_dir),
        "production_decision": production_decision(results),
        "products_total": len(results),
        "products_passed": sum(1 for result in results if result.passed),
        "products_failed": sum(1 for result in results if not result.passed),
        "products": [result.to_json() for result in results],
        "runtime_exclusions": registry.get("runtime_exclusions", []),
        "claim_boundary": (
            "This verifies registered repo-local product packages only. It does not certify live "
            "Ghost Access, SPB, NL, Open5GS, or any other external runtime."
        ),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Products Production Readiness Evidence",
        "",
        f"- Generated: {payload['generated_at_utc']}",
        f"- Decision: {payload['production_decision']}",
        f"- Products: {payload['products_passed']}/{payload['products_total']} passed",
        "",
        "## Products",
        "",
        "| Product | Decision | Result |",
        "|---|---|---|",
    ]
    for product in payload["products"]:
        result = "PASS" if product["passed"] else "FAIL"
        lines.append(f"| {product['name']} | {product['release_decision']} | {result} |")
    lines.extend(["", "## Boundary", "", payload["claim_boundary"], "", "## Evidence", ""])
    for product in payload["products"]:
        lines.append(f"- {product['name']}: `{product['evidence_path']}`")
    return "\n".join(lines) + "\n"


def run_registry_verification(output_dir: Path, registry_path: Path = REGISTRY) -> dict[str, Any]:
    registry = load_registry(registry_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [
        run_product_verifier(product, output_dir)
        for product in registry.get("products", [])
        if isinstance(product, dict)
    ]
    payload = build_payload(registry, results, output_dir, utc_stamp())
    (output_dir / "products-production-evidence.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "products-production-evidence.md").write_text(render_markdown(payload), encoding="utf-8")
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify registered product production readiness")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for products-production-evidence.json and product verifier outputs",
    )
    parser.add_argument("--json", action="store_true", help="Print the full payload as JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir) if args.output_dir else DEFAULT_OUTPUT_BASE / f"production-{utc_stamp()}"
    payload = run_registry_verification(output_dir)
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print(f"decision={payload['production_decision']}")
        print(f"products={payload['products_passed']}/{payload['products_total']}")
        print(f"evidence={output_dir / 'products-production-evidence.json'}")
    return 0 if payload["production_decision"] == "ALL_REGISTERED_PRODUCTS_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
