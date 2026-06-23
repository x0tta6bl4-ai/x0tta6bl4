#!/usr/bin/env python3
"""Submit all public x0tta6bl4 x402 services to 402directory/Jaypay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ops import jaypay_402directory_submit as single
from src.sales.x402_paid_api import PaidApiSettings, build_public_services


ARTIFACT_DIR = ROOT / ".tmp" / "non-bounty"
DEFAULT_STATUS_FILE = ARTIFACT_DIR / "jaypay_402directory_submit_all_status.json"
CLAIM_BOUNDARY = (
    "This status proves only 402directory API reachability, per-service submission attempts, "
    "and public directory search. It does not prove review approval, buyer demand, paid calls, "
    "settlement, or received funds."
)


def _safe_filename(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value).strip("_") or "service"


def _service_status_file(service_id: str) -> Path:
    return ARTIFACT_DIR / f"jaypay_402directory_{_safe_filename(service_id)}_status.json"


def _service_args(args: argparse.Namespace, service: dict[str, Any]) -> argparse.Namespace:
    return SimpleNamespace(
        api_base=args.api_base,
        public_base_url=args.public_base_url.rstrip("/"),
        endpoint=service["url"],
        service_path="",
        name=service["name"],
        description=service["description"],
        method="POST",
        price_usdc=float(service["price_usd"]),
        chain=str(service.get("network") or "base"),
        protocol="x402",
        category=str(service.get("category") or "developer-tool"),
        tags=",".join(str(tag) for tag in service.get("tags", []) if str(tag)),
        example=service["url"],
        submitter_email=args.submitter_email,
        status_file=_service_status_file(str(service["id"])),
        timeout_seconds=args.timeout_seconds,
        skip_submit=args.skip_submit,
        force_submit=args.force_submit,
    )


def run_all(args: argparse.Namespace) -> dict[str, Any]:
    public_base_url = args.public_base_url.rstrip("/")
    settings = PaidApiSettings.from_env()
    services = build_public_services(public_base_url, settings)
    results = []
    for service in services:
        service_run = single.run(_service_args(args, service))
        summary = service_run.get("summary") if isinstance(service_run.get("summary"), dict) else {}
        results.append(
            {
                "service_id": service["id"],
                "name": service["name"],
                "endpoint": service["url"],
                "status_file": str(_service_status_file(str(service["id"]))),
                "summary": summary,
            }
        )
    submitted_total = sum(1 for item in results if item["summary"].get("submitted") is True)
    known_total = sum(1 for item in results if item["summary"].get("submission_known") is True)
    visible_total = sum(1 for item in results if item["summary"].get("directory_visible") is True)
    failed_total = sum(1 for item in results if not item["summary"].get("submission_known"))
    status = {
        "schema": "x0tta6bl4.jaypay_402directory_submit_all_status.v1",
        "checked_at_utc": single.utc_now(),
        "claim_boundary": CLAIM_BOUNDARY,
        "api_base": args.api_base,
        "public_base_url": public_base_url,
        "services_total": len(results),
        "submitted_total": submitted_total,
        "submission_known_total": known_total,
        "directory_visible_total": visible_total,
        "failed_total": failed_total,
        "results": results,
        "next_action": "watch_402directory_indexing" if failed_total == 0 else "inspect_failed_402directory_submissions",
    }
    args.status_file.parent.mkdir(parents=True, exist_ok=True)
    args.status_file.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=single.DEFAULT_API_BASE)
    parser.add_argument("--public-base-url", default=single._default_public_base_url())
    parser.add_argument("--submitter-email", default="")
    parser.add_argument("--status-file", type=Path, default=DEFAULT_STATUS_FILE)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--skip-submit", action="store_true")
    parser.add_argument("--force-submit", action="store_true")
    return parser.parse_args()


def main() -> int:
    status = run_all(parse_args())
    print(
        json.dumps(
            {
                "services_total": status["services_total"],
                "submitted_total": status["submitted_total"],
                "submission_known_total": status["submission_known_total"],
                "directory_visible_total": status["directory_visible_total"],
                "failed_total": status["failed_total"],
                "next_action": status["next_action"],
                "status_file": str(DEFAULT_STATUS_FILE),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status["failed_total"] == 0 or status["submitted_total"] > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
